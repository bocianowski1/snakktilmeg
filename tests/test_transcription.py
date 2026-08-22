import subprocess
from collections.abc import Sequence
from os import PathLike
from pathlib import Path

from lib.transcription import WhisperTranscriber, extract_text_from_transcript


def test_extract_text_from_transcript_removes_whisper_runtime_noise() -> None:
    output = "hello world\nwhisper_init_from_file_with_params_no_state: loading model"

    assert extract_text_from_transcript(output) == "hello world"


def test_extract_text_from_transcript_keeps_output_without_delimiter() -> None:
    assert extract_text_from_transcript("  hello world\n") == "hello world"


def test_whisper_transcriber_builds_command_and_parses_stdout() -> None:
    calls: list[tuple[Sequence[str | PathLike[str]], dict[str, object]]] = []

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
        cli_path=Path("/bin/whisper-cli"),
        model_path=Path("/models/base.bin"),
        runner=runner,
    )

    result = transcriber.transcribe(Path("audio.wav"))

    assert result == "transcribed"
    command, options = calls[0]
    assert command == [
        Path("/bin/whisper-cli"),
        "-m",
        Path("/models/base.bin"),
        "-f",
        Path("audio.wav"),
        "--no-timestamps",
    ]
    assert options == {"capture_output": True, "text": True, "check": True}
