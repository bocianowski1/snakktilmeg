from contextlib import contextmanager
import hashlib
import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from lib.errors import ModelDownloadError
from lib.models import ModelDownloader
from lib.models import ModelSpec


def spec(name: str, content: bytes) -> ModelSpec:
    return ModelSpec(
        filename=name,
        url=f"https://example.test/{name}",
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


class FakeOpener:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    @contextmanager
    def __call__(self, url: str) -> Iterator[io.BytesIO]:
        self.urls.append(url)
        yield io.BytesIO(self.responses[url])


def test_ensure_downloads_missing_models_and_reports_progress(tmp_path) -> None:
    first = spec("a.bin", b"a" * 30)
    second = spec("b.bin", b"b" * 10)
    opener = FakeOpener({first.url: b"a" * 30, second.url: b"b" * 10})
    progress: list[float] = []

    ModelDownloader(tmp_path / "models", [first, second], opener=opener).ensure(
        progress.append
    )

    assert (tmp_path / "models" / "a.bin").read_bytes() == b"a" * 30
    assert (tmp_path / "models" / "b.bin").read_bytes() == b"b" * 10
    assert progress[-1] == 1.0
    assert progress == sorted(progress)
    assert not list((tmp_path / "models").glob("*.part"))


def test_ensure_skips_models_that_are_already_present(tmp_path) -> None:
    model = spec("a.bin", b"model")
    (tmp_path / "a.bin").write_bytes(b"model")
    opener = FakeOpener({})
    progress: list[float] = []

    ModelDownloader(tmp_path, [model], opener=opener).ensure(progress.append)

    assert opener.urls == []
    assert progress == []


def test_ensure_redownloads_incomplete_model(tmp_path) -> None:
    model = spec("a.bin", b"model")
    (tmp_path / "a.bin").write_bytes(b"mod")
    opener = FakeOpener({model.url: b"model"})

    ModelDownloader(tmp_path, [model], opener=opener).ensure(lambda fraction: None)

    assert (tmp_path / "a.bin").read_bytes() == b"model"


def test_checksum_mismatch_removes_download_and_raises(tmp_path) -> None:
    model = spec("a.bin", b"model")
    opener = FakeOpener({model.url: b"MODEL"})

    with pytest.raises(ModelDownloadError) as error:
        ModelDownloader(tmp_path, [model], opener=opener).ensure(lambda f: None)

    assert error.value.context["operation"] == "verify_model"
    assert list(tmp_path.iterdir()) == []


def test_network_failure_is_wrapped(tmp_path) -> None:
    model = spec("a.bin", b"model")

    @contextmanager
    def failing_opener(url: str) -> Iterator[io.BytesIO]:
        raise OSError("connection refused")
        yield io.BytesIO()

    with pytest.raises(ModelDownloadError) as error:
        ModelDownloader(tmp_path, [model], opener=failing_opener).ensure(
            lambda fraction: None
        )

    assert error.value.context["operation"] == "download_model"
    assert error.value.context["url"] == model.url
    assert not Path(tmp_path / "a.bin.part").exists()
