import subprocess
from collections.abc import Sequence
from typing import Protocol


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
        self.runner(
            ["/usr/bin/pbcopy"],
            input=text,
            text=True,
            check=True,
        )
        self.runner(
            [
                "/usr/bin/osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            text=True,
            check=True,
        )
