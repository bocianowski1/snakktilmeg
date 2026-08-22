import subprocess

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
