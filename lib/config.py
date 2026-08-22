from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from lib.errors import ConfigurationError


WHISPER_REPO_PATH_ENV = "WHISPER_REPO_PATH"
WHISPER_MODEL_PATH_ENV = "WHISPER_MODEL_PATH"
HOTKEY_ENV = "HOTKEY"


@dataclass(frozen=True)
class WhisperConfig:
    whisper_repo_path: Path
    whisper_cli_path: Path
    whisper_model_path: Path
    hotkey: str


def load_whisper_config(
    *,
    env_file: Path | str = ".env",
    environ: Mapping[str, str] | None = None,
) -> WhisperConfig:
    load_dotenv(dotenv_path=env_file)
    values = environ if environ is not None else os.environ

    repo_path = _read_path(values, WHISPER_REPO_PATH_ENV)
    model_path = _read_path(values, WHISPER_MODEL_PATH_ENV)
    hotkey = _read_string(values, HOTKEY_ENV)

    return WhisperConfig(
        whisper_repo_path=repo_path,
        whisper_cli_path=repo_path / "build" / "bin" / "whisper-cli",
        whisper_model_path=model_path,
        hotkey=hotkey,
    )


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
