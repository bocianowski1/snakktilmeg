import subprocess
from collections.abc import Sequence
from typing import Protocol

from lib.errors import TextInsertionError


Command = Sequence[str]


class CommandRunner(Protocol):
    def __call__(
        self,
        args: Command,
        *,
        input: str | None = None,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


def run_command(
    args: Command,
    *,
    input: str | None = None,
    text: bool,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input,
        text=text,
        check=check,
    )


class MacOSClipboardPaster:
    def __init__(self, runner: CommandRunner = run_command) -> None:
        self.runner = runner

    def insert(self, text: str) -> None:
        self._run(
            ["/usr/bin/pbcopy"],
            operation="copy_to_clipboard",
            input=text,
        )
        self._run(
            [
                "/usr/bin/osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            operation="paste_shortcut",
        )

    def _run(
        self,
        command: Command,
        *,
        operation: str,
        input: str | None = None,
    ) -> None:
        try:
            self.runner(
                command,
                input=input,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise TextInsertionError(
                "text insertion command failed",
                operation=operation,
                command=list(command),
                returncode=error.returncode,
                stderr=error.stderr,
            ) from error
        except (FileNotFoundError, PermissionError, OSError) as error:
            raise TextInsertionError(
                "failed to run text insertion command",
                operation=operation,
                command=list(command),
            ) from error
