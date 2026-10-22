import sys

from lib.app import ActivityIndicator
from lib.app import App
from lib.app import ModelProvisioner
from lib.app import TextInserter
from lib.audio import SoundDeviceRecorder
from lib.bundle import BUNDLED_MODELS
from lib.bundle import app_dir
from lib.bundle import bundle_defaults
from lib.bundle import data_dir
from lib.bundle import is_packaged
from lib.config import WhisperConfig
from lib.config import load_whisper_config
from lib.errors import ConfigurationError
from lib.errors import TrayError
from lib.hotkeys import PynputHotkeyListener
from lib.indicator import MacOSActivityIndicator
from lib.logging import configure_logging
from lib.logging import get_logger
from lib.models import ModelDownloader
from lib.text_insertion import MacOSClipboardPaster
from lib.text_insertion import WindowsClipboardPaster
from lib.transcription import WhisperTranscriber
from lib.tray import PystrayTrayIcon
from lib.tray import TrayLanguage
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


def build_app(
    config: WhisperConfig,
    platform: str = sys.platform,
    model_provisioner: ModelProvisioner | None = None,
    log_transcripts: bool = True,
) -> App:
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
        default_language=config.whisper_language,
        model_provisioner=model_provisioner,
        log_transcripts=log_transcripts,
    )


def build_tray(
    app: App,
    config: WhisperConfig,
    platform: str = sys.platform,
) -> PystrayTrayIcon | None:
    if platform != "win32":
        return None
    return PystrayTrayIcon(
        languages=[
            TrayLanguage(profile.language, profile.hotkey)
            for profile in config.language_profiles
        ],
        on_select_language=app.select_language,
        active_language=lambda: app.active_language,
        on_quit=app.shutdown,
    )


def main() -> None:
    packaged_data_dir = data_dir() if is_packaged() else None
    configure_logging(
        log_file=(
            packaged_data_dir / "logs" / "snakktilmeg.log"
            if packaged_data_dir is not None
            else None
        )
    )
    logger = get_logger(__name__)

    model_provisioner: ModelProvisioner | None = None
    try:
        if packaged_data_dir is None:
            config = load_whisper_config()
        else:
            config = load_whisper_config(
                env_file=packaged_data_dir / "settings.env",
                defaults=bundle_defaults(app_dir(), packaged_data_dir),
            )
            model_provisioner = ModelDownloader(
                packaged_data_dir / "models", BUNDLED_MODELS
            )
    except Exception as error:
        # Windowed builds have no console, so make startup failures visible
        # in the log file before exiting.
        logger.error(
            "startup failed",
            extra={"event": "startup_failed", "error": str(error)},
            exc_info=error,
        )
        raise

    app = build_app(
        config,
        model_provisioner=model_provisioner,
        # Packaged builds log to disk; keep dictated text out of those logs.
        log_transcripts=packaged_data_dir is None,
    )
    listener = PynputHotkeyListener(
        config.hotkey,
        language_hotkeys={
            profile.language: profile.hotkey for profile in config.language_profiles
        },
    )
    tray = build_tray(app, config)
    if tray is not None:
        try:
            tray.start()
        except TrayError as error:
            logger.error(
                "tray icon unavailable",
                extra={"event": "tray_unavailable", **error.log_context()},
                exc_info=error,
            )
            tray = None
    try:
        app.run_hotkey_loop(listener)
    finally:
        if tray is not None:
            tray.stop()


if __name__ == "__main__":
    main()
