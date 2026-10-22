from collections.abc import Mapping
import os
from pathlib import Path
import sys

from lib.models import BASE_EN_MODEL
from lib.models import NB_WHISPER_SMALL_MODEL
from lib.models import ModelSpec


APP_NAME = "snakktilmeg"
BUNDLED_MODELS: tuple[ModelSpec, ...] = (BASE_EN_MODEL, NB_WHISPER_SMALL_MODEL)


def is_packaged() -> bool:
    # PyInstaller sets sys.frozen on the bundled executable.
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent


def data_dir(environ: Mapping[str, str] = os.environ) -> Path:
    local_app_data = environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / APP_NAME


def bundle_defaults(app_path: Path, data_path: Path) -> dict[str, str]:
    """Configuration for the packaged Windows app.

    Values in ``settings.env`` in the data directory override these.
    """
    models = data_path / "models"
    english = str(models / BASE_EN_MODEL.filename)
    norwegian = str(models / NB_WHISPER_SMALL_MODEL.filename)
    return {
        "WHISPER_CLI_PATH": str(app_path / "whisper" / "whisper-cli.exe"),
        "WHISPER_MODEL_PATH": norwegian,
        "WHISPER_LANGUAGE": "no",
        "HOTKEY": "<ctrl>+<alt>+<space>",
        "WHISPER_MODEL_PATH_EN": english,
        "HOTKEY_EN": "<ctrl>+<alt>+e",
        "WHISPER_MODEL_PATH_NO": norwegian,
        "HOTKEY_NO": "<ctrl>+<alt>+n",
    }
