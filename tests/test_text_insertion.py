import subprocess

import pytest

from lib.errors import TextInsertionError
from lib.text_insertion import Command
from lib.text_insertion import MacOSClipboardPaster


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[Command, str | None, bool, bool]] = []

    def __call__(
        self,
        args: Command,
        *,
        input: str | None = None,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, input, text, check))
        return subprocess.CompletedProcess(args=args, returncode=0)


def test_macos_clipboard_paster_copies_text_then_sends_paste_shortcut() -> None:
    runner = FakeRunner()

    MacOSClipboardPaster(runner=runner).insert("hello")

    assert runner.calls == [
        (
            ["/usr/bin/pbcopy"],
            "hello",
            True,
            True,
        ),
        (
            [
                "/usr/bin/osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            None,
            True,
            True,
        ),
    ]


def test_macos_clipboard_paster_wraps_copy_failure() -> None:
    def runner(
        args: Command,
        *,
        input: str | None = None,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args,
            stderr="copy failed",
        )

    with pytest.raises(TextInsertionError) as error:
        MacOSClipboardPaster(runner=runner).insert("hello")

    assert str(error.value) == "text insertion command failed"
    assert error.value.context["operation"] == "copy_to_clipboard"
    assert error.value.context["returncode"] == 1
    assert error.value.context["stderr"] == "copy failed"


def test_macos_clipboard_paster_wraps_paste_failure() -> None:
    runner = FakeRunner()

    def failing_on_paste(
        args: Command,
        *,
        input: str | None = None,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        if args[0] == "/usr/bin/osascript":
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=args,
                stderr="accessibility denied",
            )
        return runner(args, input=input, text=text, check=check)

    with pytest.raises(TextInsertionError) as error:
        MacOSClipboardPaster(runner=failing_on_paste).insert("hello")

    assert runner.calls == [(["/usr/bin/pbcopy"], "hello", True, True)]
    assert error.value.context["operation"] == "paste_shortcut"
    assert error.value.context["stderr"] == "accessibility denied"
