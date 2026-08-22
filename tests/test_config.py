from pathlib import Path

import pytest

from lib.config import load_whisper_config
from lib.errors import ConfigurationError


def test_load_whisper_config_reads_env_and_derives_cli_path(tmp_path) -> None:
    repo_path = tmp_path / "whisper.cpp"
    model_path = tmp_path / "models" / "ggml-base.en.bin"

    config = load_whisper_config(
        env_file=tmp_path / "missing.env",
        environ={
            "WHISPER_REPO_PATH": str(repo_path),
            "WHISPER_MODEL_PATH": str(model_path),
            "HOTKEY": "<cmd>+<space>",
        },
    )

    assert config.whisper_repo_path == repo_path
    assert config.whisper_cli_path == repo_path / "build" / "bin" / "whisper-cli"
    assert config.whisper_model_path == model_path
    assert config.hotkey == "<cmd>+<space>"


def test_load_whisper_config_reads_dotenv_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    repo_path = tmp_path / "whisper.cpp"
    model_path = tmp_path / "models" / "ggml-base.en.bin"
    env_file.write_text(
        f"WHISPER_REPO_PATH={repo_path}\n"
        f"WHISPER_MODEL_PATH={model_path}\n"
        "HOTKEY=<ctrl>+<alt>+<space>\n",
    )
    monkeypatch.delenv("WHISPER_REPO_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    monkeypatch.delenv("HOTKEY", raising=False)

    config = load_whisper_config(env_file=env_file)

    assert config.whisper_repo_path == repo_path
    assert config.whisper_cli_path == repo_path / "build" / "bin" / "whisper-cli"
    assert config.whisper_model_path == model_path
    assert config.hotkey == "<ctrl>+<alt>+<space>"


def test_load_whisper_config_raises_for_missing_repo_path(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_whisper_config(
            env_file=tmp_path / "missing.env",
            environ={
                "WHISPER_MODEL_PATH": "/tmp/model.bin",
                "HOTKEY": "<ctrl>+<alt>+<space>",
            },
        )

    assert str(error.value) == "missing required environment variable"
    assert error.value.context["operation"] == "load_config"
    assert error.value.context["variable"] == "WHISPER_REPO_PATH"


def test_load_whisper_config_raises_for_missing_model_path(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_whisper_config(
            env_file=tmp_path / "missing.env",
            environ={
                "WHISPER_REPO_PATH": "/tmp/whisper.cpp",
                "HOTKEY": "<ctrl>+<alt>+<space>",
            },
        )

    assert str(error.value) == "missing required environment variable"
    assert error.value.context["variable"] == "WHISPER_MODEL_PATH"


def test_load_whisper_config_raises_for_empty_env_values(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_whisper_config(
            env_file=tmp_path / "missing.env",
            environ={
                "WHISPER_REPO_PATH": "   ",
                "WHISPER_MODEL_PATH": "/tmp/model.bin",
                "HOTKEY": "<ctrl>+<alt>+<space>",
            },
        )

    assert str(error.value) == "missing required environment variable"
    assert error.value.context["variable"] == "WHISPER_REPO_PATH"


def test_load_whisper_config_expands_user_paths(tmp_path) -> None:
    config = load_whisper_config(
        env_file=tmp_path / "missing.env",
        environ={
            "WHISPER_REPO_PATH": "~/code/div/whisper.cpp",
            "WHISPER_MODEL_PATH": "~/models/ggml-base.en.bin",
            "HOTKEY": "<ctrl>+<alt>+<space>",
        },
    )

    assert config.whisper_repo_path == Path.home() / "code" / "div" / "whisper.cpp"
    assert config.whisper_model_path == Path.home() / "models" / "ggml-base.en.bin"


def test_load_whisper_config_raises_for_missing_hotkey(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_whisper_config(
            env_file=tmp_path / "missing.env",
            environ={
                "WHISPER_REPO_PATH": "/tmp/whisper.cpp",
                "WHISPER_MODEL_PATH": "/tmp/model.bin",
            },
        )

    assert str(error.value) == "missing required environment variable"
    assert error.value.context["variable"] == "HOTKEY"


def test_load_whisper_config_raises_for_empty_hotkey(tmp_path) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_whisper_config(
            env_file=tmp_path / "missing.env",
            environ={
                "WHISPER_REPO_PATH": "/tmp/whisper.cpp",
                "WHISPER_MODEL_PATH": "/tmp/model.bin",
                "HOTKEY": "  ",
            },
        )

    assert str(error.value) == "missing required environment variable"
    assert error.value.context["variable"] == "HOTKEY"
