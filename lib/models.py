from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import BinaryIO, Protocol

from lib.errors import ModelDownloadError


CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class ModelSpec:
    filename: str
    url: str
    sha256: str
    size: int


# Pinned to fixed Hugging Face revisions so the checksums stay valid.
BASE_EN_MODEL = ModelSpec(
    filename="ggml-base.en.bin",
    url=(
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/"
        "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.en.bin"
    ),
    sha256="a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002",
    size=147_964_211,
)
NB_WHISPER_SMALL_MODEL = ModelSpec(
    filename="ggml-nb-whisper-small.bin",
    url=(
        "https://huggingface.co/NbAiLab/nb-whisper-small/resolve/"
        "e9bb5cb83cb74c96239fd506163aa97cff2fce4c/ggml-model.bin"
    ),
    sha256="a0fc1555f5bd51044b0ea88bb9b7891e1ee331a8087eddb0afc3a05839db48ab",
    size=487_601_984,
)


class ReadableStream(Protocol):
    def read(self, size: int, /) -> bytes: ...


Opener = Callable[[str], AbstractContextManager[ReadableStream]]


@contextmanager
def open_url(url: str) -> Iterator[BinaryIO]:
    from urllib.request import urlopen

    with urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        yield response


class ModelDownloader:
    def __init__(
        self,
        models_dir: Path,
        models: Sequence[ModelSpec],
        opener: Opener = open_url,
    ) -> None:
        self.models_dir = models_dir
        self.models = list(models)
        self.opener = opener

    def missing(self) -> list[ModelSpec]:
        # A size match is enough here; checksums are verified on download.
        return [
            model
            for model in self.models
            if not self._path(model).is_file()
            or self._path(model).stat().st_size != model.size
        ]

    def ensure(self, on_progress: Callable[[float], None]) -> None:
        missing = self.missing()
        total = sum(model.size for model in missing)
        downloaded = 0
        for model in missing:
            def report(model_bytes: int, base: int = downloaded) -> None:
                on_progress(min(1.0, (base + model_bytes) / total))

            self._download(model, report)
            downloaded += model.size

    def _path(self, model: ModelSpec) -> Path:
        return self.models_dir / model.filename

    def _download(self, model: ModelSpec, report: Callable[[int], None]) -> None:
        path = self._path(model)
        partial = path.with_name(path.name + ".part")
        digest = hashlib.sha256()
        received = 0
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            with self.opener(model.url) as response, partial.open("wb") as file:
                while chunk := response.read(CHUNK_SIZE):
                    file.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    report(received)
        except Exception as error:
            partial.unlink(missing_ok=True)
            raise ModelDownloadError(
                "failed to download model",
                operation="download_model",
                model=model.filename,
                url=model.url,
            ) from error

        if received != model.size or digest.hexdigest() != model.sha256:
            partial.unlink(missing_ok=True)
            raise ModelDownloadError(
                "downloaded model failed verification",
                operation="verify_model",
                model=model.filename,
                expected_size=model.size,
                received_size=received,
            )
        try:
            partial.replace(path)
        except OSError as error:
            raise ModelDownloadError(
                "failed to save downloaded model",
                operation="save_model",
                model=model.filename,
                path=str(path),
            ) from error
