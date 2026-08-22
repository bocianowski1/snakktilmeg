from collections.abc import Callable
import logging
from pathlib import Path
import tempfile
import threading
from typing import Protocol

from lib.logging import get_logger


class Recorder(Protocol):
    def start_recording(self) -> None: ...

    def stop_recording(self, path: Path) -> None: ...

    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None: ...


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


class TextInserter(Protocol):
    def insert(self, text: str) -> None: ...


class HotkeyListener(Protocol):
    def run(self, on_press: Callable[[], None]) -> None: ...


class NullTextInserter:
    def insert(self, text: str) -> None:
        pass


DEFAULT_HOTKEY_RECORDING_PATH = Path(tempfile.gettempdir()) / "snakktilmeg-recording.wav"


class App:
    def __init__(
        self,
        recorder: Recorder,
        transcriber: Transcriber,
        text_inserter: TextInserter | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.text_inserter = text_inserter or NullTextInserter()
        self.logger = logger or get_logger(__name__)
        self._state = "idle"
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def run(self, out_path: Path = Path("recording.wav")) -> None:
        self.recorder.record_wav_until_enter(out_path)
        self._transcribe_output_and_insert(out_path)

    def run_hotkey_loop(
        self,
        listener: HotkeyListener,
        out_path: Path = DEFAULT_HOTKEY_RECORDING_PATH,
    ) -> None:
        self.logger.info(
            "hotkey listener ready",
            extra={"event": "hotkey_listener_ready"},
        )
        listener.run(lambda: self.handle_hotkey(out_path))

    def handle_hotkey(self, out_path: Path = DEFAULT_HOTKEY_RECORDING_PATH) -> None:
        with self._lock:
            state = self._state
            if state == "idle":
                self.recorder.start_recording()
                self._state = "recording"
                self.logger.info(
                    "recording started",
                    extra={"event": "recording_started"},
                )
                return
            if state == "recording":
                self._state = "transcribing"
                self.logger.info(
                    "transcribing started",
                    extra={"event": "transcribing_started"},
                )
                self._worker = threading.Thread(
                    target=self._finish_recording,
                    args=(out_path,),
                    daemon=True,
                )
                self._worker.start()
                return

        self.logger.info(
            "hotkey ignored",
            extra={"event": "hotkey_ignored", "reason": "busy"},
        )

    def wait_for_pending_work(self) -> None:
        worker = self._worker
        if worker is not None:
            worker.join()

    def _finish_recording(self, out_path: Path) -> None:
        try:
            self.recorder.stop_recording(out_path)
            self._transcribe_output_and_insert(out_path)
        finally:
            with self._lock:
                self._state = "idle"

    def _transcribe_output_and_insert(self, out_path: Path) -> None:
        transcript = self.transcriber.transcribe(out_path)
        self.logger.info(
            "transcript ready",
            extra={"event": "transcript_ready", "transcript": transcript},
        )
        if transcript:
            self.text_inserter.insert(transcript)
