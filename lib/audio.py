from collections.abc import Callable
from pathlib import Path
import queue
import wave
from typing import Any

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
        self._chunks: queue.Queue[AudioBuffer] | None = None
        self._stream: Any | None = None

    def start_recording(self) -> None:
        import sounddevice as sd

        if self._stream is not None:
            raise RuntimeError("recording already in progress")

        chunks: queue.Queue[AudioBuffer] = queue.Queue()

        def callback(
            indata: AudioBuffer, frames: int, time: object, status: object
        ) -> None:
            if status:
                print(status)
            chunks.put(indata.copy())

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=callback,
        )
        stream.start()
        self._chunks = chunks
        self._stream = stream

    def stop_recording(self, path: Path) -> None:
        if self._stream is None or self._chunks is None:
            raise RuntimeError("no recording in progress")

        stream = self._stream
        chunks = self._chunks
        self._stream = None
        self._chunks = None

        stream.stop()
        stream.close()
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

    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None:
        print("recording... press Enter to stop")
        self.start_recording()
        try:
            wait_for_stop()
        finally:
            self.stop_recording(path)
