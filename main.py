from lib.app import App
from lib.audio import SoundDeviceRecorder
from lib.config import WhisperConfig
from lib.config import load_whisper_config
from lib.hotkeys import PynputHotkeyListener
from lib.indicator import MacOSActivityIndicator
from lib.logging import configure_logging
from lib.text_insertion import MacOSClipboardPaster
from lib.transcription import WhisperTranscriber


def build_app(config: WhisperConfig) -> App:
    return App(
        recorder=SoundDeviceRecorder(),
        transcriber=WhisperTranscriber(
            cli_path=config.whisper_cli_path,
            model_path=config.whisper_model_path,
        ),
        text_inserter=MacOSClipboardPaster(),
        indicator=MacOSActivityIndicator(),
    )


def main() -> None:
    configure_logging()
    config = load_whisper_config()
    build_app(config).run_hotkey_loop(PynputHotkeyListener(config.hotkey))


if __name__ == "__main__":
    main()
