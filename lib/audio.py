from collections.abc import Callable
from pathlib import Path
import queue
import wave

import numpy as np


AudioBuffer = np.ndarray


def write_wav(
    path: Path,
    audio: AudioBuffer,
    *,
    sample_rate: int,
    channels: int,
) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(audio.tobytes())


class SoundDeviceRecorder:
    def __init__(self, sample_rate: int = 16_000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels

    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None:
        import sounddevice as sd

        chunks: queue.Queue[AudioBuffer] = queue.Queue()

        def callback(
            indata: AudioBuffer, frames: int, time: object, status: object
        ) -> None:
            if status:
                print(status)
            chunks.put(indata.copy())

        print("recording... press Enter to stop")
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=callback,
        ):
            wait_for_stop()

        if chunks.empty():
            raise RuntimeError("no audio captured")

        captured_chunks: list[AudioBuffer] = []
        while not chunks.empty():
            captured_chunks.append(chunks.get())

        write_wav(
            path,
            np.concatenate(captured_chunks),
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
