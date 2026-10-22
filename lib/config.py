from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from lib.errors import ConfigurationError


WHISPER_REPO_PATH_ENV = "WHISPER_REPO_PATH"
WHISPER_CLI_PATH_ENV = "WHISPER_CLI_PATH"
WHISPER_MODEL_PATH_ENV = "WHISPER_MODEL_PATH"
HOTKEY_ENV = "HOTKEY"
WHISPER_LANGUAGE_ENV = "WHISPER_LANGUAGE"
LANGUAGE_MODEL_PATH_ENV_PREFIX = "WHISPER_MODEL_PATH_"
LANGUAGE_HOTKEY_ENV_PREFIX = "HOTKEY_"


@dataclass(frozen=True)
class LanguageProfile:
    language: str
    model_path: Path
    hotkey: str


@dataclass(frozen=True)
class WhisperConfig:
    whisper_repo_path: Path | None
    whisper_cli_path: Path
    whisper_model_path: Path
    hotkey: str
    whisper_language: str | None = None
    language_profiles: tuple[LanguageProfile, ...] = ()


def load_whisper_config(
    *,
    env_file: Path | str = ".env",
    environ: Mapping[str, str] | None = None,
    platform: str = sys.platform,
    defaults: Mapping[str, str] | None = None,
) -> WhisperConfig:
    load_dotenv(dotenv_path=env_file)
    values = {
        **(defaults or {}),
        **(environ if environ is not None else os.environ),
    }

    # WHISPER_CLI_PATH points straight at the binary, e.g. in the packaged
    # app; otherwise the path is derived from the whisper.cpp checkout.
    repo_path: Path | None = None
    if _read_optional_string(values, WHISPER_CLI_PATH_ENV) is not None:
        cli_path = _read_path(values, WHISPER_CLI_PATH_ENV)
    else:
        repo_path = _read_path(values, WHISPER_REPO_PATH_ENV)
        cli_path = whisper_cli_path(repo_path, platform)
    model_path = _read_path(values, WHISPER_MODEL_PATH_ENV)
    hotkey = _read_string(values, HOTKEY_ENV)
    language = _read_optional_string(values, WHISPER_LANGUAGE_ENV)
    language_profiles = _read_language_profiles(values)

    return WhisperConfig(
        whisper_repo_path=repo_path,
        whisper_cli_path=cli_path,
        whisper_model_path=model_path,
        hotkey=hotkey,
        whisper_language=language,
        language_profiles=language_profiles,
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


def _read_language_profiles(values: Mapping[str, str]) -> tuple[LanguageProfile, ...]:
    # Each WHISPER_MODEL_PATH_<CODE> enables a switchable language whose code
    # is passed to whisper as -l <code> and selected with HOTKEY_<CODE>.
    profiles: list[LanguageProfile] = []
    for name in sorted(values):
        if not name.startswith(LANGUAGE_MODEL_PATH_ENV_PREFIX):
            continue
        suffix = name.removeprefix(LANGUAGE_MODEL_PATH_ENV_PREFIX)
        if not suffix or not values[name].strip():
            continue
        profiles.append(
            LanguageProfile(
                language=suffix.lower(),
                model_path=_read_path(values, name),
                hotkey=_read_string(values, LANGUAGE_HOTKEY_ENV_PREFIX + suffix),
            )
        )
    return tuple(profiles)
