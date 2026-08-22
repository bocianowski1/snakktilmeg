import queue
import sys
from types import SimpleNamespace
import wave

import numpy as np
import pytest

from lib.audio import SoundDeviceRecorder
from lib.audio import write_wav
from lib.errors import RecordingError


def test_write_wav_creates_expected_mono_int16_file(tmp_path) -> None:
    path = tmp_path / "sample.wav"
    audio = np.array([[0], [1024], [-1024]], dtype=np.int16)

    write_wav(path, audio, sample_rate=16_000, channels=1)

    with wave.open(str(path), "rb") as f:
        assert f.getnchannels() == 1
        assert f.getsampwidth() == 2
        assert f.getframerate() == 16_000
        assert f.getnframes() == 3
        assert f.readframes(3) == audio.tobytes()


def test_sound_device_recorder_wraps_stream_start_failure(monkeypatch) -> None:
    class FailingInputStream:
        def __init__(self, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            raise OSError("microphone unavailable")

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(InputStream=FailingInputStream),
    )

    with pytest.raises(RecordingError) as error:
        SoundDeviceRecorder().start_recording()

    assert str(error.value) == "failed to start audio input stream"
    assert error.value.context["operation"] == "start_recording"


def test_sound_device_recorder_rejects_stop_without_recording(tmp_path) -> None:
    with pytest.raises(RecordingError) as error:
        SoundDeviceRecorder().stop_recording(tmp_path / "recording.wav")

    assert str(error.value) == "no recording in progress"
    assert error.value.context["operation"] == "stop_recording"


def test_sound_device_recorder_rejects_empty_capture(tmp_path) -> None:
    class FakeStream:
        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    recorder = SoundDeviceRecorder()
    recorder._stream = FakeStream()
    recorder._chunks = queue.Queue()

    with pytest.raises(RecordingError) as error:
        recorder.stop_recording(tmp_path / "recording.wav")

    assert str(error.value) == "no audio captured"
    assert error.value.context["operation"] == "stop_recording"
