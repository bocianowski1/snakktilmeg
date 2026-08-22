import wave

import numpy as np

from lib.audio import write_wav


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
