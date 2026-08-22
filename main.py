from pathlib import Path

from lib.app import App
from lib.audio import SoundDeviceRecorder
from lib.hotkeys import PynputHotkeyListener
from lib.logging import configure_logging
from lib.text_insertion import MacOSClipboardPaster
from lib.transcription import WhisperTranscriber

WHISPER_REPO_PATH = Path.home() / "code" / "div" / "whisper.cpp"
WHISPER_CLI_PATH = WHISPER_REPO_PATH / "build" / "bin" / "whisper-cli"
WHISPER_MODEL_PATH = WHISPER_REPO_PATH / "models" / "ggml-base.en.bin"


def build_app() -> App:
    return App(
        recorder=SoundDeviceRecorder(),
        transcriber=WhisperTranscriber(
            cli_path=WHISPER_CLI_PATH,
            model_path=WHISPER_MODEL_PATH,
        ),
        text_inserter=MacOSClipboardPaster(),
    )


def main() -> None:
    configure_logging()
    build_app().run_hotkey_loop(PynputHotkeyListener())


if __name__ == "__main__":
    main()
