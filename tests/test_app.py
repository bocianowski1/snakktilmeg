from collections.abc import Callable
import logging
from pathlib import Path
import threading

from lib.app import App


class FakeRecorder:
    def __init__(self) -> None:
        self.calls: list[Path] = []
        self.started = 0
        self.stopped: list[Path] = []

    def start_recording(self) -> None:
        self.started += 1

    def stop_recording(self, path: Path) -> None:
        self.stopped.append(path)

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
        ("transcript_ready", "")
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
        "transcript_ready",
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
