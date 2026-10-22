from pathlib import Path

from lib.bundle import bundle_defaults
from lib.bundle import data_dir


def test_data_dir_uses_local_app_data() -> None:
    assert data_dir({"LOCALAPPDATA": "C:/Users/me/AppData/Local"}) == (
        Path("C:/Users/me/AppData/Local") / "snakktilmeg"
    )


def test_bundle_defaults_point_at_bundled_cli_and_downloaded_models() -> None:
    defaults = bundle_defaults(Path("app"), Path("data"))

    assert defaults["WHISPER_CLI_PATH"] == str(Path("app/whisper/whisper-cli.exe"))
    assert defaults["WHISPER_MODEL_PATH_EN"] == str(
        Path("data/models/ggml-base.en.bin")
    )
    assert defaults["WHISPER_MODEL_PATH_NO"] == str(
        Path("data/models/ggml-nb-whisper-small.bin")
    )
    assert defaults["WHISPER_MODEL_PATH"] == defaults["WHISPER_MODEL_PATH_NO"]
    assert defaults["WHISPER_LANGUAGE"] == "no"
    assert defaults["HOTKEY_EN"] == "<ctrl>+<alt>+e"
    assert defaults["HOTKEY_NO"] == "<ctrl>+<alt>+n"
