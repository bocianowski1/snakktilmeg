import subprocess
from collections.abc import Sequence
from os import PathLike
from pathlib import Path

import pytest

from lib.errors import TranscriptionError
from lib.transcription import WhisperTranscriber, extract_text_from_transcript


def test_extract_text_from_transcript_removes_whisper_runtime_noise() -> None:
    output = "hello world\nwhisper_init_from_file_with_params_no_state: loading model"

    assert extract_text_from_transcript(output) == "hello world"


def test_extract_text_from_transcript_keeps_output_without_delimiter() -> None:
    assert extract_text_from_transcript("  hello world\n") == "hello world"


def test_whisper_transcriber_builds_command_and_parses_stdout(tmp_path) -> None:
    calls: list[tuple[Sequence[str | PathLike[str]], dict[str, object]]] = []
    cli_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "model.bin"
    audio_path = tmp_path / "audio.wav"
    cli_path.touch()
    model_path.touch()
    audio_path.touch()

    def runner(
        args: Sequence[str | PathLike[str]],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(
            (
                args,
                {"capture_output": capture_output, "text": text, "check": check},
            )
        )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="transcribed\nwhisper_init_from_file_with_params_no_state: noise",
            stderr="",
        )

    transcriber = WhisperTranscriber(
        cli_path=cli_path,
        model_path=model_path,
        runner=runner,
    )

    result = transcriber.transcribe(audio_path)

    assert result == "transcribed"
    command, options = calls[0]
    assert command == [
        cli_path,
        "-m",
        model_path,
        "-f",
        audio_path,
        "--no-timestamps",
    ]
    assert options == {"capture_output": True, "text": True, "check": True}


def test_whisper_transcriber_rejects_missing_cli_path(tmp_path) -> None:
    model_path = tmp_path / "model.bin"
    audio_path = tmp_path / "audio.wav"
    model_path.touch()
    audio_path.touch()

    transcriber = WhisperTranscriber(
        cli_path=tmp_path / "missing-whisper-cli",
        model_path=model_path,
    )

    with pytest.raises(TranscriptionError) as error:
        transcriber.transcribe(audio_path)

    assert str(error.value) == "whisper CLI does not exist"
    assert error.value.context["operation"] == "transcribe"


def test_whisper_transcriber_rejects_missing_model_path(tmp_path) -> None:
    cli_path = tmp_path / "whisper-cli"
    audio_path = tmp_path / "audio.wav"
    cli_path.touch()
    audio_path.touch()

    transcriber = WhisperTranscriber(
        cli_path=cli_path,
        model_path=tmp_path / "missing-model.bin",
    )

    with pytest.raises(TranscriptionError) as error:
        transcriber.transcribe(audio_path)

    assert str(error.value) == "whisper model does not exist"
    assert error.value.context["path"] == str(tmp_path / "missing-model.bin")


def test_whisper_transcriber_rejects_missing_audio_path(tmp_path) -> None:
    cli_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "model.bin"
    cli_path.touch()
    model_path.touch()

    transcriber = WhisperTranscriber(
        cli_path=cli_path,
        model_path=model_path,
    )

    with pytest.raises(TranscriptionError) as error:
        transcriber.transcribe(tmp_path / "missing-audio.wav")

    assert str(error.value) == "audio file does not exist"


def test_whisper_transcriber_wraps_command_failure(tmp_path) -> None:
    cli_path = tmp_path / "whisper-cli"
    model_path = tmp_path / "model.bin"
    audio_path = tmp_path / "audio.wav"
    cli_path.touch()
    model_path.touch()
    audio_path.touch()

    def runner(
        args: Sequence[str | PathLike[str]],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=args,
            stderr="bad model",
        )

    transcriber = WhisperTranscriber(
        cli_path=cli_path,
        model_path=model_path,
        runner=runner,
    )

    with pytest.raises(TranscriptionError) as error:
        transcriber.transcribe(audio_path)

    assert str(error.value) == "whisper command failed"
    assert error.value.context["returncode"] == 2
    assert error.value.context["stderr"] == "bad model"
