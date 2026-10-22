import sys

from lib.app import ActivityIndicator
from lib.app import App
from lib.app import TextInserter
from lib.audio import SoundDeviceRecorder
from lib.config import WhisperConfig
from lib.config import load_whisper_config
from lib.errors import ConfigurationError
from lib.hotkeys import PynputHotkeyListener
from lib.indicator import MacOSActivityIndicator
from lib.logging import configure_logging
from lib.text_insertion import MacOSClipboardPaster
from lib.text_insertion import WindowsClipboardPaster
from lib.transcription import WhisperTranscriber
from lib.windows_indicator import WindowsActivityIndicator


def build_platform_adapters(platform: str) -> tuple[TextInserter, ActivityIndicator]:
    if platform == "darwin":
        return MacOSClipboardPaster(), MacOSActivityIndicator()
    if platform == "win32":
        return WindowsClipboardPaster(), WindowsActivityIndicator()
    raise ConfigurationError(
        "unsupported platform",
        operation="build_app",
        platform=platform,
    )


def build_app(config: WhisperConfig, platform: str = sys.platform) -> App:
    text_inserter, indicator = build_platform_adapters(platform)
    return App(
        recorder=SoundDeviceRecorder(),
        transcriber=WhisperTranscriber(
            cli_path=config.whisper_cli_path,
            model_path=config.whisper_model_path,
            language=config.whisper_language,
        ),
        text_inserter=text_inserter,
        indicator=indicator,
        language_transcribers={
            profile.language: WhisperTranscriber(
                cli_path=config.whisper_cli_path,
                model_path=profile.model_path,
                language=profile.language,
            )
            for profile in config.language_profiles
        },
    )


def main() -> None:
    configure_logging()
    config = load_whisper_config()
    listener = PynputHotkeyListener(
        config.hotkey,
        language_hotkeys={
            profile.language: profile.hotkey for profile in config.language_profiles
        },
    )
    build_app(config).run_hotkey_loop(listener)


if __name__ == "__main__":
    main()
