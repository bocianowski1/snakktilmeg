from collections.abc import Callable
from pathlib import Path

from lib.app import App


class FakeRecorder:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None:
        self.calls.append(path)


class FakeTranscriber:
    def __init__(self, transcript: str = "hello") -> None:
        self.transcript = transcript
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> str:
        self.calls.append(audio_path)
        return self.transcript


class FakeTextInserter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def insert(self, text: str) -> None:
        self.calls.append(text)


def test_app_records_then_transcribes_outputs_and_inserts_result(tmp_path) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    output: list[str] = []
    path = tmp_path / "recording.wav"

    App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
        output=output.append,
    ).run(path)

    assert recorder.calls == [path]
    assert transcriber.calls == [path]
    assert output == ["hello"]
    assert text_inserter.calls == ["hello"]


def test_app_does_not_insert_empty_transcript(tmp_path) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber("")
    text_inserter = FakeTextInserter()
    output: list[str] = []
    path = tmp_path / "recording.wav"

    App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
        output=output.append,
    ).run(path)

    assert recorder.calls == [path]
    assert transcriber.calls == [path]
    assert output == [""]
    assert text_inserter.calls == []
