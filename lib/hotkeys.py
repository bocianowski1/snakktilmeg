from collections.abc import Callable
from typing import Any

from lib.errors import HotkeyError


class PynputHotkeyListener:
    def __init__(self, hotkey: str = "<ctrl>+<alt>+<space>") -> None:
        self.hotkey = hotkey

    def run(self, on_press: Callable[[], None]) -> None:
        from pynput import keyboard

        try:
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(self.hotkey),
                on_press,
            )
        except Exception as error:
            raise HotkeyError(
                "failed to parse hotkey",
                operation="hotkey_listener",
                hotkey=self.hotkey,
            ) from error

        def for_canonical(callback: Callable[[Any], None]) -> Callable[[Any], None]:
            return lambda key: callback(listener.canonical(key))

        try:
            with keyboard.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release),
            ) as listener:
                listener.join()
        except Exception as error:
            raise HotkeyError(
                "hotkey listener failed",
                operation="hotkey_listener",
                hotkey=self.hotkey,
            ) from error
