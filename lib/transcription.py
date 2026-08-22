import subprocess
from collections.abc import Sequence
from os import PathLike
from pathlib import Path
from typing import Protocol

from lib.utils import timed


TRANSCRIPT_NOISE_DELIMITER = "whisper_init_from_file_with_params_no_state"
CommandPart = str | PathLike[str]
Command = Sequence[CommandPart]


class CommandRunner(Protocol):
    def __call__(
        self,
        args: Command,
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


def run_command(
    args: Command,
    *,
    capture_output: bool,
    text: bool,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        check=check,
    )


def extract_text_from_transcript(output_text: str) -> str:
    return output_text.split(TRANSCRIPT_NOISE_DELIMITER)[0].strip()


class WhisperTranscriber:
    def __init__(
        self,
        cli_path: Path,
        model_path: Path,
        runner: CommandRunner = run_command,
    ) -> None:
        self.cli_path = cli_path
        self.model_path = model_path
        self.runner = runner

    @timed
    def transcribe(self, audio_path: Path) -> str:
        result = self.runner(
            [
                self.cli_path,
                "-m",
                self.model_path,
                "-f",
                audio_path,
                "--no-timestamps",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return extract_text_from_transcript(result.stdout)
