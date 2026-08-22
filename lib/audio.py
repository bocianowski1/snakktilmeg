from collections.abc import Callable
import logging
from pathlib import Path
import queue
import wave
from typing import Any

import numpy as np

from lib.errors import RecordingError
from lib.logging import get_logger


AudioBuffer = np.ndarray


def write_wav(
    path: Path,
    audio: AudioBuffer,
    *,
    sample_rate: int,
    channels: int,
) -> None:
    try:
        with wave.open(str(path), "wb") as f:
            f.setnchannels(channels)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            f.writeframes(audio.tobytes())
    except OSError as error:
        raise RecordingError(
            "failed to write WAV file",
            operation="write_wav",
            path=str(path),
        ) from error


class SoundDeviceRecorder:
    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        logger: logging.Logger | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.logger = logger or get_logger(__name__)
        self._chunks: queue.Queue[AudioBuffer] | None = None
        self._stream: Any | None = None

    def start_recording(self) -> None:
        import sounddevice as sd

        if self._stream is not None:
            raise RecordingError(
                "recording already in progress",
                operation="start_recording",
            )

        chunks: queue.Queue[AudioBuffer] = queue.Queue()

        def callback(
            indata: AudioBuffer, frames: int, time: object, status: object
        ) -> None:
            if status:
                self.logger.warning(
                    "audio input status",
                    extra={"event": "audio_input_status", "status": str(status)},
                )
            chunks.put(indata.copy())

        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            )
            stream.start()
        except Exception as error:
            raise RecordingError(
                "failed to start audio input stream",
                operation="start_recording",
            ) from error
        self._chunks = chunks
        self._stream = stream

    def stop_recording(self, path: Path) -> None:
        if self._stream is None or self._chunks is None:
            raise RecordingError(
                "no recording in progress",
                operation="stop_recording",
                path=str(path),
            )

        chunks = self._chunks
        self._close_stream()
        if chunks.empty():
            raise RecordingError(
                "no audio captured",
                operation="stop_recording",
                path=str(path),
            )

        captured_chunks: list[AudioBuffer] = []
        while not chunks.empty():
            captured_chunks.append(chunks.get())

        write_wav(
            path,
            np.concatenate(captured_chunks),
            sample_rate=self.sample_rate,
            channels=self.channels,
        )

    def discard_recording(self) -> None:
        self._close_stream()

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        self._chunks = None

        if stream is None:
            return

        try:
            stream.stop()
            stream.close()
        except Exception as error:
            raise RecordingError(
                "failed to close audio input stream",
                operation="close_recording_stream",
            ) from error

    def record_wav_until_enter(
        self,
        path: Path,
        wait_for_stop: Callable[[], str] = input,
    ) -> None:
        self.logger.info(
            "recording prompt",
            extra={"event": "recording_prompt", "prompt": "press Enter to stop"},
        )
        self.start_recording()
        try:
            wait_for_stop()
        finally:
            self.stop_recording(path)
