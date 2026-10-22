from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from lib.errors import ConfigurationError


WHISPER_REPO_PATH_ENV = "WHISPER_REPO_PATH"
WHISPER_MODEL_PATH_ENV = "WHISPER_MODEL_PATH"
HOTKEY_ENV = "HOTKEY"
WHISPER_LANGUAGE_ENV = "WHISPER_LANGUAGE"


@dataclass(frozen=True)
class WhisperConfig:
    whisper_repo_path: Path
    whisper_cli_path: Path
    whisper_model_path: Path
    hotkey: str
    whisper_language: str | None = None


def load_whisper_config(
    *,
    env_file: Path | str = ".env",
    environ: Mapping[str, str] | None = None,
    platform: str = sys.platform,
) -> WhisperConfig:
    load_dotenv(dotenv_path=env_file)
    values = environ if environ is not None else os.environ

    repo_path = _read_path(values, WHISPER_REPO_PATH_ENV)
    model_path = _read_path(values, WHISPER_MODEL_PATH_ENV)
    hotkey = _read_string(values, HOTKEY_ENV)
    language = _read_optional_string(values, WHISPER_LANGUAGE_ENV)

    return WhisperConfig(
        whisper_repo_path=repo_path,
        whisper_cli_path=whisper_cli_path(repo_path, platform),
        whisper_model_path=model_path,
        hotkey=hotkey,
        whisper_language=language,
    )


def whisper_cli_path(repo_path: Path, platform: str = sys.platform) -> Path:
    if platform == "win32":
        # CMake's Visual Studio generator puts binaries in a per-config folder.
        return repo_path / "build" / "bin" / "Release" / "whisper-cli.exe"
    return repo_path / "build" / "bin" / "whisper-cli"


def _read_path(values: Mapping[str, str], name: str) -> Path:
    value = values.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(
            "missing required environment variable",
            operation="load_config",
            variable=name,
        )

    try:
        return Path(value).expanduser()
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            "invalid environment variable path",
            operation="load_config",
            variable=name,
            value=value,
        ) from error


def _read_string(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(
            "missing required environment variable",
            operation="load_config",
            variable=name,
        )
    return value.strip()


def _read_optional_string(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()
