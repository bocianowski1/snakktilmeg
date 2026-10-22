from pathlib import Path

import pytest

import main
from lib.config import LanguageProfile
from lib.config import WhisperConfig
from lib.errors import ConfigurationError
from lib.indicator import MacOSActivityIndicator
from lib.models import ModelDownloader
from lib.text_insertion import MacOSClipboardPaster
from lib.text_insertion import WindowsClipboardPaster
from lib.transcription import WhisperTranscriber
from lib.windows_indicator import WindowsActivityIndicator


def test_main_passes_configured_hotkey_to_listener(monkeypatch) -> None:
    config = WhisperConfig(
        whisper_repo_path=Path("/whisper.cpp"),
        whisper_cli_path=Path("/whisper.cpp/build/bin/whisper-cli"),
        whisper_model_path=Path("/models/base.bin"),
        hotkey="<cmd>+<shift>+space",
    )
    captured: dict[str, object] = {}

    class FakeApp:
        def run_hotkey_loop(self, listener: object) -> None:
            captured["listener"] = listener

    class FakeListener:
        def __init__(self, hotkey: str, language_hotkeys: dict[str, str]) -> None:
            self.hotkey = hotkey
            self.language_hotkeys = language_hotkeys

    def build_app(received_config: WhisperConfig, **options: object) -> FakeApp:
        captured["config"] = received_config
        captured["options"] = options
        return FakeApp()

    monkeypatch.setattr(main, "is_packaged", lambda: False)
    monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "load_whisper_config", lambda: config)
    monkeypatch.setattr(main, "build_app", build_app)
    monkeypatch.setattr(main, "build_tray", lambda app, config: None)
    monkeypatch.setattr(main, "PynputHotkeyListener", FakeListener)

    main.main()

    assert captured["config"] is config
    assert isinstance(captured["listener"], FakeListener)
    assert captured["listener"].hotkey == "<cmd>+<shift>+space"
    assert captured["listener"].language_hotkeys == {}
    assert captured["options"] == {"model_provisioner": None, "log_transcripts": True}


def test_build_platform_adapters_uses_macos_adapters_on_darwin() -> None:
    text_inserter, indicator = main.build_platform_adapters("darwin")

    assert isinstance(text_inserter, MacOSClipboardPaster)
    assert isinstance(indicator, MacOSActivityIndicator)


def test_build_platform_adapters_uses_windows_adapters_on_win32() -> None:
    text_inserter, indicator = main.build_platform_adapters("win32")

    assert isinstance(text_inserter, WindowsClipboardPaster)
    assert isinstance(indicator, WindowsActivityIndicator)


def test_build_platform_adapters_rejects_unsupported_platform() -> None:
    with pytest.raises(ConfigurationError) as error:
        main.build_platform_adapters("linux")

    assert str(error.value) == "unsupported platform"
    assert error.value.context["platform"] == "linux"


def test_build_app_creates_transcriber_per_language_profile() -> None:
    config = WhisperConfig(
        whisper_repo_path=Path("/whisper.cpp"),
        whisper_cli_path=Path("/whisper.cpp/whisper-cli"),
        whisper_model_path=Path("/models/base.bin"),
        hotkey="<ctrl>+<alt>+<space>",
        language_profiles=(
            LanguageProfile("en", Path("/models/en.bin"), "<ctrl>+<alt>+e"),
            LanguageProfile("no", Path("/models/no.bin"), "<ctrl>+<alt>+n"),
        ),
    )

    app = main.build_app(config, platform="win32")

    english = app.language_transcribers["en"]
    norwegian = app.language_transcribers["no"]
    assert isinstance(english, WhisperTranscriber)
    assert isinstance(norwegian, WhisperTranscriber)
    assert (english.model_path, english.language) == (Path("/models/en.bin"), "en")
    assert (norwegian.model_path, norwegian.language) == (Path("/models/no.bin"), "no")


def test_main_uses_bundle_defaults_and_downloads_models_when_packaged(
    monkeypatch, tmp_path
) -> None:
    captured: dict[str, object] = {}
    config = WhisperConfig(
        whisper_repo_path=None,
        whisper_cli_path=tmp_path / "whisper" / "whisper-cli.exe",
        whisper_model_path=tmp_path / "models" / "nb.bin",
        hotkey="<ctrl>+<alt>+<space>",
    )

    class FakeApp:
        def run_hotkey_loop(self, listener: object) -> None:
            pass

    def load_config(**kwargs: object) -> WhisperConfig:
        captured["load"] = kwargs
        return config

    def build_app(received_config: WhisperConfig, **options: object) -> FakeApp:
        captured["options"] = options
        return FakeApp()

    monkeypatch.setattr(main, "is_packaged", lambda: True)
    monkeypatch.setattr(main, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(main, "app_dir", lambda: tmp_path / "app")
    monkeypatch.setattr(
        main, "configure_logging", lambda **kwargs: captured.update(logging=kwargs)
    )
    monkeypatch.setattr(main, "load_whisper_config", load_config)
    monkeypatch.setattr(main, "build_app", build_app)
    monkeypatch.setattr(main, "build_tray", lambda app, config: None)
    monkeypatch.setattr(main, "PynputHotkeyListener", lambda *args, **kwargs: None)

    main.main()

    assert captured["logging"] == {"log_file": tmp_path / "logs" / "snakktilmeg.log"}
    load = captured["load"]
    assert isinstance(load, dict)
    assert load["env_file"] == tmp_path / "settings.env"
    assert load["defaults"]["WHISPER_CLI_PATH"] == str(
        tmp_path / "app" / "whisper" / "whisper-cli.exe"
    )
    options = captured["options"]
    assert isinstance(options, dict)
    provisioner = options["model_provisioner"]
    assert isinstance(provisioner, ModelDownloader)
    assert provisioner.models_dir == tmp_path / "models"
    assert options["log_transcripts"] is False


def test_build_tray_is_windows_only() -> None:
    config = WhisperConfig(
        whisper_repo_path=None,
        whisper_cli_path=Path("whisper-cli"),
        whisper_model_path=Path("model.bin"),
        hotkey="<ctrl>+<alt>+<space>",
    )
    app = main.build_app(config, platform="darwin")

    assert main.build_tray(app, config, platform="darwin") is None
    assert main.build_tray(app, config, platform="win32") is not None
