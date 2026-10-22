from collections.abc import Callable
import logging
from pathlib import Path
import threading

from lib.app import App
from lib.errors import HotkeyError
from lib.errors import ModelDownloadError
from lib.errors import RecordingError
from lib.errors import TextInsertionError
from lib.errors import TranscriptionError


class FakeRecorder:
    def __init__(self) -> None:
        self.calls: list[Path] = []
        self.started = 0
        self.stopped: list[Path] = []
        self.discarded = 0

    def start_recording(self) -> None:
        self.started += 1

    def stop_recording(self, path: Path) -> None:
        self.stopped.append(path)

    def discard_recording(self) -> None:
        self.discarded += 1

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


class InterruptingListener:
    def __init__(self, before_interrupt: Callable[[Callable[[], None]], None]) -> None:
        self.before_interrupt = before_interrupt

    def run(
        self,
        on_press: Callable[[], None],
        on_select_language: Callable[[str], None],
    ) -> None:
        self.before_interrupt(on_press)
        raise KeyboardInterrupt

    def stop(self) -> None:
        pass


class FailingListener:
    def run(
        self,
        on_press: Callable[[], None],
        on_select_language: Callable[[str], None],
    ) -> None:
        raise HotkeyError("listener unavailable", operation="hotkey_listener")

    def stop(self) -> None:
        pass


class FakeIndicator:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.languages: list[str | None] = []
        self.messages: list[str] = []
        self.running = threading.Event()
        self.stopped = threading.Event()

    def prepare(self) -> None:
        self.calls.append("prepare")

    def run(self) -> None:
        self.calls.append("run")
        self.running.set()
        self.stopped.wait(timeout=5)

    def stop(self) -> None:
        self.calls.append("stop")
        self.stopped.set()

    def show_recording(self, language: str | None) -> None:
        self.calls.append("recording")
        self.languages.append(language)

    def show_transcribing(self, language: str | None) -> None:
        self.calls.append("transcribing")
        self.languages.append(language)

    def show_message(self, text: str) -> None:
        self.calls.append("message")
        self.messages.append(text)

    def hide(self) -> None:
        self.calls.append("hide")


class ReturningIndicator(FakeIndicator):
    def run(self) -> None:
        self.calls.append("run")


class BlockingListener:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.stopped = threading.Event()

    def run(
        self,
        on_press: Callable[[], None],
        on_select_language: Callable[[str], None],
    ) -> None:
        self.started.set()
        self.stopped.wait(timeout=5)

    def stop(self) -> None:
        self.stopped.set()


def test_app_records_then_transcribes_outputs_and_inserts_result(tmp_path) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"

    App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    ).run(path)

    assert recorder.calls == [path]
    assert transcriber.calls == [path]
    assert text_inserter.calls == ["hello"]


def test_app_logs_transcript(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        App(
            recorder=recorder,
            transcriber=transcriber,
            text_inserter=text_inserter,
        ).run(path)

    assert [(record.event, record.transcript) for record in caplog.records] == [
        ("transcript_ready", "hello")
    ]


def test_app_does_not_insert_empty_transcript(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber("")
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        App(
            recorder=recorder,
            transcriber=transcriber,
            text_inserter=text_inserter,
        ).run(path)

    assert recorder.calls == [path]
    assert transcriber.calls == [path]
    assert [(record.event, record.transcript) for record in caplog.records] == [
        ("empty_transcript", "")
    ]
    assert text_inserter.calls == []


def test_hotkey_first_press_starts_recording(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        App(
            recorder=recorder,
            transcriber=transcriber,
            text_inserter=text_inserter,
        ).handle_hotkey(path)

    assert recorder.started == 1
    assert recorder.stopped == []
    assert transcriber.calls == []
    assert text_inserter.calls == []
    assert [record.event for record in caplog.records] == ["recording_started"]


def test_hotkey_second_press_stops_transcribes_outputs_and_inserts(
    tmp_path, caplog
) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        app.wait_for_pending_work()

    assert recorder.started == 1
    assert recorder.stopped == [path]
    assert transcriber.calls == [path]
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "transcript_ready",
    ]
    assert caplog.records[-1].transcript == "hello"
    assert text_inserter.calls == ["hello"]


def test_hotkey_updates_indicator_through_recording_session(tmp_path) -> None:
    indicator = FakeIndicator()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
        indicator=indicator,
    )

    app.handle_hotkey(tmp_path / "recording.wav")
    app.handle_hotkey(tmp_path / "recording.wav")
    app.wait_for_pending_work()

    assert indicator.calls == ["recording", "transcribing", "hide"]


def test_indicator_update_failure_does_not_interrupt_recording(tmp_path, caplog) -> None:
    class FailingIndicator(FakeIndicator):
        def show_recording(self, language: str | None) -> None:
            raise RuntimeError("display unavailable")

    recorder = FakeRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        indicator=FailingIndicator(),
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(tmp_path / "recording.wav")

    assert recorder.started == 1
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "indicator_update_failed",
    ]


def test_hotkey_does_not_insert_empty_transcript(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber("")
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        app.wait_for_pending_work()

    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "empty_transcript",
    ]
    assert caplog.records[-1].transcript == ""
    assert text_inserter.calls == []


def test_hotkey_ignores_presses_while_transcribing(tmp_path, caplog) -> None:
    can_finish = threading.Event()
    stop_started = threading.Event()

    class BlockingRecorder(FakeRecorder):
        def stop_recording(self, path: Path) -> None:
            self.stopped.append(path)
            stop_started.set()
            can_finish.wait(timeout=5)

    recorder = BlockingRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        assert stop_started.wait(timeout=5)

        app.handle_hotkey(path)
        can_finish.set()
        app.wait_for_pending_work()

    assert recorder.started == 1
    assert recorder.stopped == [path]
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "hotkey_ignored",
        "transcript_ready",
    ]
    assert caplog.records[2].reason == "busy"


def test_ctrl_c_while_idle_exits_cleanly(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(lambda on_press: None), tmp_path)

    assert recorder.started == 0
    assert recorder.stopped == []
    assert recorder.discarded == 0
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "shutdown_requested",
        "shutdown_complete",
    ]


def test_ctrl_c_while_recording_discards_audio(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    transcriber = FakeTranscriber()
    text_inserter = FakeTextInserter()
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    )
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(lambda on_press: on_press()), path)
        app.handle_hotkey(path)

    assert recorder.started == 2
    assert recorder.stopped == []
    assert recorder.discarded == 1
    assert transcriber.calls == []
    assert text_inserter.calls == []
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "recording_started",
        "shutdown_requested",
        "recording_discarded",
        "shutdown_complete",
        "recording_started",
    ]


def test_ctrl_c_while_transcribing_waits_for_pending_work(tmp_path, caplog) -> None:
    transcribe_started = threading.Event()
    can_finish = threading.Event()

    class BlockingTranscriber(FakeTranscriber):
        def transcribe(self, audio_path: Path) -> str:
            self.calls.append(audio_path)
            transcribe_started.set()
            can_finish.wait(timeout=5)
            return self.transcript

    def start_stop_then_interrupt(on_press: Callable[[], None]) -> None:
        on_press()
        on_press()
        assert transcribe_started.wait(timeout=5)
        threading.Timer(0.01, can_finish.set).start()

    recorder = FakeRecorder()
    transcriber = BlockingTranscriber()
    text_inserter = FakeTextInserter()
    path = tmp_path / "recording.wav"
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=text_inserter,
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(start_stop_then_interrupt), path)

    assert recorder.started == 1
    assert recorder.stopped == [path]
    assert recorder.discarded == 0
    assert transcriber.calls == [path]
    assert text_inserter.calls == ["hello"]
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "recording_started",
        "transcribing_started",
        "shutdown_requested",
        "transcript_ready",
        "shutdown_complete",
    ]


def test_recording_start_failure_logs_and_allows_next_hotkey(tmp_path, caplog) -> None:
    class StartFailingRecorder(FakeRecorder):
        def __init__(self) -> None:
            super().__init__()
            self.should_fail = True

        def start_recording(self) -> None:
            if self.should_fail:
                self.should_fail = False
                raise RecordingError("microphone unavailable", operation="start_recording")
            super().start_recording()

    recorder = StartFailingRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(tmp_path / "recording.wav")
        app.handle_hotkey(tmp_path / "recording.wav")

    assert recorder.started == 1
    assert [record.event for record in caplog.records] == [
        "recording_start_failed",
        "recording_started",
    ]
    assert caplog.records[0].operation == "start_recording"
    assert caplog.records[0].error_type == "RecordingError"


def test_worker_recording_failure_logs_and_allows_next_hotkey(tmp_path, caplog) -> None:
    class StopFailingRecorder(FakeRecorder):
        def stop_recording(self, path: Path) -> None:
            self.stopped.append(path)
            raise RecordingError("no audio captured", operation="stop_recording")

    recorder = StopFailingRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
    )
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        app.wait_for_pending_work()
        app.handle_hotkey(path)

    assert recorder.started == 2
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "recording_stop_failed",
        "recording_started",
    ]
    assert caplog.records[2].error_type == "RecordingError"


def test_worker_transcription_failure_logs_and_allows_next_hotkey(
    tmp_path, caplog
) -> None:
    class FailingTranscriber(FakeTranscriber):
        def transcribe(self, audio_path: Path) -> str:
            self.calls.append(audio_path)
            raise TranscriptionError("whisper failed", operation="transcribe")

    recorder = FakeRecorder()
    transcriber = FailingTranscriber()
    app = App(
        recorder=recorder,
        transcriber=transcriber,
        text_inserter=FakeTextInserter(),
    )
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        app.wait_for_pending_work()
        app.handle_hotkey(path)

    assert recorder.started == 2
    assert transcriber.calls == [path]
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "transcription_failed",
        "recording_started",
    ]
    assert caplog.records[2].operation == "transcribe"


def test_worker_text_insertion_failure_logs_after_transcript(tmp_path, caplog) -> None:
    class FailingTextInserter(FakeTextInserter):
        def insert(self, text: str) -> None:
            self.calls.append(text)
            raise TextInsertionError("paste failed", operation="paste_shortcut")

    text_inserter = FailingTextInserter()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        text_inserter=text_inserter,
    )
    path = tmp_path / "recording.wav"

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(path)
        app.handle_hotkey(path)
        app.wait_for_pending_work()

    assert text_inserter.calls == ["hello"]
    assert [record.event for record in caplog.records] == [
        "recording_started",
        "transcribing_started",
        "transcript_ready",
        "text_insert_failed",
    ]
    assert caplog.records[3].operation == "paste_shortcut"


def test_hotkey_listener_failure_logs_and_shutdowns(tmp_path, caplog) -> None:
    recorder = FakeRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(FailingListener(), tmp_path / "recording.wav")

    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "hotkey_listener_failed",
        "shutdown_requested",
        "shutdown_complete",
    ]
    assert caplog.records[1].error_type == "HotkeyError"


def test_indicator_initialization_failure_falls_back_to_blocking_loop(
    tmp_path, caplog
) -> None:
    class FailingIndicator(FakeIndicator):
        def prepare(self) -> None:
            raise RuntimeError("indicator backend unavailable")

    with caplog.at_level(logging.INFO):
        App(
            recorder=FakeRecorder(),
            transcriber=FakeTranscriber(),
            indicator=FailingIndicator(),
        ).run_hotkey_loop(InterruptingListener(lambda on_press: None), tmp_path)

    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "indicator_initialization_failed",
        "shutdown_requested",
        "shutdown_complete",
    ]


def test_listener_failure_stops_indicator_event_loop(tmp_path, caplog) -> None:
    indicator = FakeIndicator()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        indicator=indicator,
    )

    class FailingAfterIndicatorStartsListener(FailingListener):
        # The listener runs on its own thread; fail only once the indicator
        # event loop is running so the call order is deterministic.
        def run(
            self,
            on_press: Callable[[], None],
            on_select_language: Callable[[str], None],
        ) -> None:
            indicator.running.wait(timeout=5)
            super().run(on_press, on_select_language)

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(FailingAfterIndicatorStartsListener(), tmp_path)

    assert indicator.calls == ["prepare", "run", "hide", "stop"]
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "hotkey_listener_failed",
        "shutdown_requested",
        "shutdown_complete",
    ]


def test_indicator_event_loop_exit_stops_listener_and_shuts_down(
    tmp_path, caplog
) -> None:
    indicator = ReturningIndicator()
    listener = BlockingListener()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        indicator=indicator,
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(listener, tmp_path)

    assert listener.started.is_set()
    assert listener.stopped.is_set()
    assert indicator.calls == ["prepare", "run", "hide", "stop"]
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "shutdown_requested",
        "shutdown_complete",
    ]


def test_shutdown_logs_discard_failure(tmp_path, caplog) -> None:
    class DiscardFailingRecorder(FakeRecorder):
        def discard_recording(self) -> None:
            self.discarded += 1
            raise RecordingError("failed to close stream", operation="discard_recording")

    recorder = DiscardFailingRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        text_inserter=FakeTextInserter(),
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(lambda on_press: on_press()), tmp_path)

    assert recorder.discarded == 1
    assert [record.event for record in caplog.records] == [
        "hotkey_listener_ready",
        "recording_started",
        "shutdown_requested",
        "recording_discard_failed",
        "shutdown_complete",
    ]


def test_selected_language_transcriber_is_used_for_next_recording(tmp_path) -> None:
    default = FakeTranscriber("default")
    norwegian = FakeTranscriber("hei")
    text_inserter = FakeTextInserter()
    app = App(
        recorder=FakeRecorder(),
        transcriber=default,
        text_inserter=text_inserter,
        language_transcribers={"no": norwegian},
    )

    app.select_language("no")
    app.handle_hotkey(tmp_path)
    app.handle_hotkey(tmp_path)
    app.wait_for_pending_work()

    assert app.language == "no"
    assert default.calls == []
    assert norwegian.calls == [tmp_path]
    assert text_inserter.calls == ["hei"]


def test_language_switch_during_transcription_applies_to_next_recording(
    tmp_path,
) -> None:
    release = threading.Event()

    class BlockingTranscriber(FakeTranscriber):
        def transcribe(self, audio_path: Path) -> str:
            release.wait(timeout=5)
            return super().transcribe(audio_path)

    english = BlockingTranscriber("hello")
    norwegian = FakeTranscriber("hei")
    app = App(
        recorder=FakeRecorder(),
        transcriber=english,
        language_transcribers={"en": english, "no": norwegian},
    )

    app.handle_hotkey(tmp_path)
    app.handle_hotkey(tmp_path)
    app.select_language("no")
    release.set()
    app.wait_for_pending_work()

    assert english.calls == [tmp_path]
    assert norwegian.calls == []

    app.handle_hotkey(tmp_path)
    app.handle_hotkey(tmp_path)
    app.wait_for_pending_work()

    assert norwegian.calls == [tmp_path]


def test_unknown_language_is_logged_and_ignored(tmp_path, caplog) -> None:
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        language_transcribers={"no": FakeTranscriber()},
    )

    with caplog.at_level(logging.INFO):
        app.select_language("de")

    assert app.language is None
    assert caplog.records[0].event == "language_unknown"
    assert caplog.records[0].language == "de"


def test_hotkey_loop_passes_language_selection_to_listener(tmp_path) -> None:
    norwegian = FakeTranscriber("hei")
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        language_transcribers={"no": norwegian},
    )

    class SelectingListener:
        def run(
            self,
            on_press: Callable[[], None],
            on_select_language: Callable[[str], None],
        ) -> None:
            on_select_language("no")
            raise KeyboardInterrupt

        def stop(self) -> None:
            pass

    app.run_hotkey_loop(SelectingListener(), tmp_path)

    assert app.language == "no"


def test_indicator_shows_active_language_for_recording_session(tmp_path) -> None:
    indicator = FakeIndicator()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        indicator=indicator,
        language_transcribers={"en": FakeTranscriber()},
        default_language="no",
    )

    app.handle_hotkey(tmp_path)
    app.handle_hotkey(tmp_path)
    app.wait_for_pending_work()
    app.select_language("en")
    app.handle_hotkey(tmp_path)
    app.handle_hotkey(tmp_path)
    app.wait_for_pending_work()

    assert indicator.languages == ["no", "no", "en", "en"]


def test_language_selection_logs_previous_language(caplog) -> None:
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        language_transcribers={"en": FakeTranscriber(), "no": FakeTranscriber()},
        default_language="no",
    )

    with caplog.at_level(logging.INFO):
        app.select_language("en")
        app.select_language("no")

    assert [
        (record.event, record.language, record.previous_language)
        for record in caplog.records
    ] == [
        ("language_selected", "en", "no"),
        ("language_selected", "no", "en"),
    ]


def test_recording_started_log_includes_language(tmp_path, caplog) -> None:
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        default_language="no",
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(tmp_path)

    assert caplog.records[0].event == "recording_started"
    assert caplog.records[0].language == "no"


class FakeProvisioner:
    def __init__(
        self,
        progress: list[float] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.progress = progress or []
        self.error = error
        self.release = threading.Event()
        self.release.set()

    def ensure(self, on_progress: Callable[[float], None]) -> None:
        self.release.wait(timeout=5)
        for fraction in self.progress:
            on_progress(fraction)
        if self.error is not None:
            raise self.error


class StoppingListener:
    def __init__(self, app: App) -> None:
        self.app = app

    def run(
        self,
        on_press: Callable[[], None],
        on_select_language: Callable[[str], None],
    ) -> None:
        self.app.wait_for_model_provisioning()
        self.app.shutdown()

    def stop(self) -> None:
        pass


def test_hotkey_is_ignored_while_models_are_downloading(tmp_path, caplog) -> None:
    provisioner = FakeProvisioner()
    provisioner.release.clear()
    recorder = FakeRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        model_provisioner=provisioner,
    )

    def press_while_preparing(on_press: Callable[[], None]) -> None:
        on_press()
        provisioner.release.set()
        app.wait_for_model_provisioning()
        on_press()

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(press_while_preparing), tmp_path)

    assert recorder.started == 1
    ignored = [r for r in caplog.records if r.event == "hotkey_ignored"]
    assert [r.reason for r in ignored] == ["preparing"]


def test_model_download_progress_is_shown_and_logged(tmp_path, caplog) -> None:
    indicator = FakeIndicator()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        indicator=indicator,
        model_provisioner=FakeProvisioner([0.0, 0.004, 0.5, 1.0]),
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(StoppingListener(app), tmp_path)

    assert indicator.messages == [
        "Downloading… 0%",
        "Downloading… 50%",
        "Downloading… 100%",
    ]
    events = [record.event for record in caplog.records]
    assert events.count("models_download_started") == 1
    assert "models_ready" in events
    assert [
        record.percent
        for record in caplog.records
        if record.event == "models_download_progress"
    ] == [0, 50, 100]


def test_models_already_present_do_not_touch_indicator(tmp_path, caplog) -> None:
    indicator = FakeIndicator()
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        indicator=indicator,
        model_provisioner=FakeProvisioner(),
    )

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(StoppingListener(app), tmp_path)

    assert "message" not in indicator.calls
    assert "models_ready" in [record.event for record in caplog.records]


def test_model_download_failure_is_logged_and_app_becomes_idle(
    tmp_path, caplog
) -> None:
    recorder = FakeRecorder()
    app = App(
        recorder=recorder,
        transcriber=FakeTranscriber(),
        model_provisioner=FakeProvisioner(
            [0.1], error=ModelDownloadError("offline", operation="download_model")
        ),
    )

    def press_after_failure(on_press: Callable[[], None]) -> None:
        app.wait_for_model_provisioning()
        on_press()

    with caplog.at_level(logging.INFO):
        app.run_hotkey_loop(InterruptingListener(press_after_failure), tmp_path)

    failures = [r for r in caplog.records if r.event == "models_download_failed"]
    assert failures[0].error_type == "ModelDownloadError"
    assert recorder.started == 1


def test_transcript_text_can_be_kept_out_of_logs(tmp_path, caplog) -> None:
    app = App(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber("secret words"),
        log_transcripts=False,
    )

    with caplog.at_level(logging.INFO):
        app.handle_hotkey(tmp_path)
        app.handle_hotkey(tmp_path)
        app.wait_for_pending_work()

    ready = [r for r in caplog.records if r.event == "transcript_ready"][0]
    assert ready.transcript_length == len("secret words")
    assert not hasattr(ready, "transcript")
