import subprocess
from pathlib import Path
import queue

import numpy as np
import sounddevice as sd
import wave
from lib.utils import timed

WHISPER_REPO_PATH = Path.home() / "code" / "div" / "whisper.cpp"
WHISPER_CLI_PATH = WHISPER_REPO_PATH / "build" / "bin" / "whisper-cli"
WHISPER_MODEL_PATH = WHISPER_REPO_PATH / "models" / "ggml-base.en.bin"


class Service:
    def __init__(self) -> None:
        self.sample_rate = 16_000
        self.channels = 1

    @timed
    def whisper(self, audio_path: Path) -> str:
        result = subprocess.run(
            [
                WHISPER_CLI_PATH,
                "-m",
                WHISPER_MODEL_PATH,
                "-f",
                audio_path,
                "--no-timestamps",
            ],
            capture_output=True,
            text=True,
        )
        return self._extract_text_from_transcript(result.stdout)

    def record_wav_until_enter(self, path: Path) -> None:
        chunks: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata, frames, time, status) -> None:
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
            input()

        if chunks.empty():
            raise RuntimeError("no audio captured")

        captured_chunks: list[np.ndarray] = []
        while not chunks.empty():
            captured_chunks.append(chunks.get())

        audio = np.concatenate(captured_chunks)

        with wave.open(str(path), "wb") as f:
            f.setnchannels(self.channels)
            f.setsampwidth(2)  # int16 = 2 bytes
            f.setframerate(self.sample_rate)
            f.writeframes(audio.tobytes())

    def _extract_text_from_transcript(self, output_text: str) -> str:
        delim = "whisper_init_from_file_with_params_no_state"
        return output_text.split(delim)[0].strip()


def main():
    svc = Service()
    out_path = Path("recording.wav")
    svc.record_wav_until_enter(out_path)
    result = svc.whisper(out_path)
    print(result)


if __name__ == "__main__":
    main()
