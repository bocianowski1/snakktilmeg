from pathlib import Path

import main
from lib.config import WhisperConfig


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
        def __init__(self, hotkey: str) -> None:
            self.hotkey = hotkey

    def build_app(received_config: WhisperConfig) -> FakeApp:
        captured["config"] = received_config
        return FakeApp()

    monkeypatch.setattr(main, "configure_logging", lambda: None)
    monkeypatch.setattr(main, "load_whisper_config", lambda: config)
    monkeypatch.setattr(main, "build_app", build_app)
    monkeypatch.setattr(main, "PynputHotkeyListener", FakeListener)

    main.main()

    assert captured["config"] is config
    assert isinstance(captured["listener"], FakeListener)
    assert captured["listener"].hotkey == "<cmd>+<shift>+space"
