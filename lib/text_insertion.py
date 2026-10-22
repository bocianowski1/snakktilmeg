import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import Protocol

from lib.errors import TextInsertionError


Command = Sequence[str]

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
CLIPBOARD_OPEN_ATTEMPTS = 10
CLIPBOARD_OPEN_RETRY_SECONDS = 0.02


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


def set_windows_clipboard_text(text: str) -> None:
    if sys.platform != "win32":
        raise OSError("the Windows clipboard is only available on Windows")

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)

    # Another process may briefly hold the clipboard open, so retry a few times.
    for _ in range(CLIPBOARD_OPEN_ATTEMPTS):
        if user32.OpenClipboard(None):
            break
        time.sleep(CLIPBOARD_OPEN_RETRY_SECONDS)
    else:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        if not user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(pointer, data, size)
        kernel32.GlobalUnlock(handle)
        # On success the clipboard owns the memory; only free it on failure.
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        user32.CloseClipboard()


def send_ctrl_v() -> None:
    from pynput import keyboard

    controller = keyboard.Controller()
    with controller.pressed(keyboard.Key.ctrl):
        controller.tap("v")


class WindowsClipboardPaster:
    def __init__(
        self,
        set_clipboard: Callable[[str], None] = set_windows_clipboard_text,
        send_paste: Callable[[], None] = send_ctrl_v,
    ) -> None:
        self.set_clipboard = set_clipboard
        self.send_paste = send_paste

    def insert(self, text: str) -> None:
        try:
            self.set_clipboard(text)
        except Exception as error:
            raise TextInsertionError(
                "failed to copy text to clipboard",
                operation="copy_to_clipboard",
            ) from error
        try:
            self.send_paste()
        except Exception as error:
            raise TextInsertionError(
                "failed to send paste shortcut",
                operation="paste_shortcut",
            ) from error
