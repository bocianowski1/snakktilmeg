from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class Recorder(Protocol):
    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None: ...


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


class TextInserter(Protocol):
    def insert(self, text: str) -> None: ...


class NullTextInserter:
    def insert(self, text: str) -> None:
        pass


class App:
    def __init__(
        self,
        recorder: Recorder,
        transcriber: Transcriber,
        text_inserter: TextInserter | None = None,
        output: Callable[[str], None] = print,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.text_inserter = text_inserter or NullTextInserter()
        self.output = output

    def run(self, out_path: Path = Path("recording.wav")) -> None:
        self.recorder.record_wav_until_enter(out_path)
        transcript = self.transcriber.transcribe(out_path)
        self.output(transcript)
        if transcript:
            self.text_inserter.insert(transcript)
