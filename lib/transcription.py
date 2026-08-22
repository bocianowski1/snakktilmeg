import subprocess
from collections.abc import Sequence
from os import PathLike
from pathlib import Path
from typing import Protocol

from lib.errors import TranscriptionError
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
        self._validate_paths(audio_path)
        command = [
            self.cli_path,
            "-m",
            self.model_path,
            "-f",
            audio_path,
            "--no-timestamps",
        ]
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise TranscriptionError(
                "whisper command failed",
                operation="transcribe",
                command=_command_for_log(command),
                returncode=error.returncode,
                stderr=error.stderr,
            ) from error
        except (FileNotFoundError, PermissionError, OSError) as error:
            raise TranscriptionError(
                "failed to run whisper command",
                operation="transcribe",
                command=_command_for_log(command),
            ) from error
        return extract_text_from_transcript(result.stdout)

    def _validate_paths(self, audio_path: Path) -> None:
        if not self.cli_path.is_file():
            raise TranscriptionError(
                "whisper CLI does not exist",
                operation="transcribe",
                path=str(self.cli_path),
            )
        if not self.model_path.is_file():
            raise TranscriptionError(
                "whisper model does not exist",
                operation="transcribe",
                path=str(self.model_path),
            )
        if not audio_path.is_file():
            raise TranscriptionError(
                "audio file does not exist",
                operation="transcribe",
                path=str(audio_path),
            )


def _command_for_log(command: Command) -> list[str]:
    return [str(part) for part in command]
