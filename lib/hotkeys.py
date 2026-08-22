from collections.abc import Callable
from typing import Any


class PynputHotkeyListener:
    def __init__(self, hotkey: str = "<ctrl>+<alt>+<space>") -> None:
        self.hotkey = hotkey

    def run(self, on_press: Callable[[], None]) -> None:
        from pynput import keyboard

        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(self.hotkey),
            on_press,
        )

        def for_canonical(callback: Callable[[Any], None]) -> Callable[[Any], None]:
            return lambda key: callback(listener.canonical(key))

        with keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release),
        ) as listener:
            listener.join()
