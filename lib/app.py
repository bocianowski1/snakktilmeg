from collections.abc import Callable
import logging
from pathlib import Path
import tempfile
import threading
from typing import Protocol

from lib.errors import HotkeyError
from lib.errors import IndicatorError
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

    def stop(self) -> None: ...


class ActivityIndicator(Protocol):
    def prepare(self) -> None: ...

    def run(self) -> None: ...

    def stop(self) -> None: ...

    def show_recording(self) -> None: ...

    def show_transcribing(self) -> None: ...

    def hide(self) -> None: ...


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
        indicator: ActivityIndicator | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.text_inserter = text_inserter or NullTextInserter()
        self.indicator = indicator
        self.logger = logger or get_logger(__name__)
        self._state = "idle"
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._listener: HotkeyListener | None = None
        self._listener_worker: threading.Thread | None = None
        self._shutdown_started = False

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
        self._listener = listener
        self.logger.info(
            "hotkey listener ready",
            extra={"event": "hotkey_listener_ready"},
        )
        if self.indicator is not None:
            try:
                self.indicator.prepare()
            except Exception as error:
                self._log_exception(
                    "activity indicator unavailable",
                    "indicator_initialization_failed",
                    error,
                    operation="prepare_indicator",
                )
                self.indicator = None
            else:
                self._run_hotkey_loop_with_indicator(listener, out_path)
                return

        self._run_blocking_hotkey_loop(listener, out_path)

    def _run_blocking_hotkey_loop(
        self,
        listener: HotkeyListener,
        out_path: Path,
    ) -> None:
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

    def _run_hotkey_loop_with_indicator(
        self,
        listener: HotkeyListener,
        out_path: Path,
    ) -> None:
        def listen() -> None:
            try:
                listener.run(lambda: self.handle_hotkey(out_path))
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

        self._listener_worker = threading.Thread(
            target=listen,
            name="hotkey-listener",
            daemon=True,
        )
        self._listener_worker.start()
        try:
            assert self.indicator is not None
            self.indicator.run()
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as error:
            self._log_exception(
                "activity indicator event loop failed",
                "indicator_event_loop_failed",
                error,
                operation="run_indicator",
            )
            self.shutdown()
        finally:
            self.shutdown()
            self._listener_worker.join()

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
                self._update_indicator("show_recording")
                return
            if state == "recording":
                self._state = "transcribing"
                self.logger.info(
                    "transcribing started",
                    extra={"event": "transcribing_started"},
                )
                self._update_indicator("show_transcribing")
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
        with self._lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True

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

        listener = self._listener
        stop_listener = getattr(listener, "stop", None)
        if callable(stop_listener):
            try:
                stop_listener()
            except Exception as error:
                self._log_exception(
                    "hotkey listener stop failed",
                    "hotkey_listener_stop_failed",
                    error,
                    operation="stop_hotkey_listener",
                )

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

        self._update_indicator("hide")
        indicator = self.indicator
        if indicator is not None:
            try:
                indicator.stop()
            except Exception as error:
                self._log_exception(
                    "activity indicator stop failed",
                    "indicator_stop_failed",
                    error,
                    operation="stop_indicator",
                )

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
            self._update_indicator("hide")

    def _update_indicator(self, operation: str) -> None:
        indicator = self.indicator
        if indicator is None:
            return
        try:
            getattr(indicator, operation)()
        except Exception as error:
            wrapped = (
                error
                if isinstance(error, IndicatorError)
                else IndicatorError(
                    "failed to update activity indicator",
                    operation=operation,
                )
            )
            self._log_exception(
                "activity indicator update failed",
                "indicator_update_failed",
                wrapped,
                operation=operation,
            )

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
