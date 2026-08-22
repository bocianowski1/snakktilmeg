from collections.abc import Callable
import logging
from pathlib import Path
import tempfile
import threading
from typing import Protocol

from lib.errors import HotkeyError
from lib.errors import RecordingError
from lib.errors import SnakktilmegError
from lib.errors import TextInsertionError
from lib.errors import TranscriptionError
from lib.logging import get_logger


class Recorder(Protocol):
    def start_recording(self) -> None: ...

    def stop_recording(self, path: Path) -> None: ...

    def discard_recording(self) -> None: ...

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
        try:
            self.recorder.record_wav_until_enter(out_path)
            self._transcribe_output_and_insert(out_path)
        except Exception as error:
            self._log_exception(
                "app error",
                "app_error",
                error,
                operation="run",
                path=str(out_path),
            )
            raise

    def run_hotkey_loop(
        self,
        listener: HotkeyListener,
        out_path: Path = DEFAULT_HOTKEY_RECORDING_PATH,
    ) -> None:
        self.logger.info(
            "hotkey listener ready",
            extra={"event": "hotkey_listener_ready"},
        )
        try:
            listener.run(lambda: self.handle_hotkey(out_path))
        except KeyboardInterrupt:
            self.shutdown()
        except HotkeyError as error:
            self._log_exception(
                "hotkey listener failed",
                "hotkey_listener_failed",
                error,
            )
            self.shutdown()
        except Exception as error:
            self._log_exception(
                "hotkey listener failed",
                "hotkey_listener_failed",
                error,
                operation="hotkey_listener",
            )
            self.shutdown()

    def handle_hotkey(self, out_path: Path = DEFAULT_HOTKEY_RECORDING_PATH) -> None:
        with self._lock:
            state = self._state
            if state == "idle":
                try:
                    self.recorder.start_recording()
                except Exception as error:
                    self._log_exception(
                        "recording start failed",
                        "recording_start_failed",
                        error,
                        operation="start_recording",
                    )
                    self._state = "idle"
                    return
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

    def shutdown(self) -> None:
        self.logger.info(
            "shutdown requested",
            extra={"event": "shutdown_requested"},
        )

        worker: threading.Thread | None = None
        discard_recording = False
        with self._lock:
            if self._state == "recording":
                self._state = "idle"
                discard_recording = True
            elif self._state == "transcribing":
                worker = self._worker

        if discard_recording:
            try:
                self.recorder.discard_recording()
            except Exception as error:
                self._log_exception(
                    "recording discard failed",
                    "recording_discard_failed",
                    error,
                    operation="discard_recording",
                )
            else:
                self.logger.info(
                    "recording discarded",
                    extra={"event": "recording_discarded"},
                )
        if worker is not None:
            worker.join()

        self.logger.info(
            "shutdown complete",
            extra={"event": "shutdown_complete"},
        )

    def _finish_recording(self, out_path: Path) -> None:
        try:
            self.recorder.stop_recording(out_path)
            self._transcribe_output_and_insert(out_path)
        except RecordingError as error:
            self._log_exception(
                "recording stop failed",
                "recording_stop_failed",
                error,
                operation="stop_recording",
                path=str(out_path),
            )
        except TranscriptionError as error:
            self._log_exception(
                "transcription failed",
                "transcription_failed",
                error,
                operation="transcribe",
                path=str(out_path),
            )
        except TextInsertionError as error:
            self._log_exception(
                "text insertion failed",
                "text_insert_failed",
                error,
            )
        except Exception as error:
            self._log_exception(
                "worker failed",
                "worker_failed",
                error,
                operation="finish_recording",
                path=str(out_path),
            )
        finally:
            with self._lock:
                self._state = "idle"

    def _transcribe_output_and_insert(self, out_path: Path) -> None:
        transcript = self.transcriber.transcribe(out_path)
        if not transcript:
            self.logger.info(
                "empty transcript",
                extra={"event": "empty_transcript", "transcript": transcript},
            )
            return

        self.logger.info(
            "transcript ready",
            extra={"event": "transcript_ready", "transcript": transcript},
        )
        self.text_inserter.insert(transcript)

    def _log_exception(
        self,
        message: str,
        event: str,
        error: BaseException,
        **context: object,
    ) -> None:
        extra = {
            "event": event,
            "error_type": type(error).__name__,
            "error": str(error),
            **context,
        }
        if isinstance(error, SnakktilmegError):
            extra.update(error.log_context())
            extra["event"] = event

        self.logger.error(message, extra=extra, exc_info=error)
