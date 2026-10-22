from collections.abc import Callable, Mapping
import sys
import threading
from typing import Any

from lib.errors import HotkeyError


VK_A = 0x41
VK_Z = 0x5A


def normalize_letter_key(key: Any, keyboard: Any, platform: str = sys.platform) -> Any:
    # On Windows, Ctrl+Alt acts as AltGr, so letter events can carry an AltGr
    # character (Ctrl+Alt+E is "€" on Nordic layouts) or no character at all.
    # Letter virtual-key codes are layout independent, so match on those.
    if platform != "win32":
        return key
    vk = getattr(key, "vk", None)
    if isinstance(vk, int) and VK_A <= vk <= VK_Z:
        return keyboard.KeyCode.from_char(chr(vk).lower())
    return key


class PynputHotkeyListener:
    def __init__(
        self,
        hotkey: str = "<ctrl>+<alt>+<space>",
        language_hotkeys: Mapping[str, str] | None = None,
    ) -> None:
        self.hotkey = hotkey
        self.language_hotkeys = dict(language_hotkeys or {})
        self._lock = threading.Lock()
        self._listener: Any | None = None
        self._stop_requested = False

    def run(
        self,
        on_press: Callable[[], None],
        on_select_language: Callable[[str], None] = lambda language: None,
    ) -> None:
        from pynput import keyboard

        hotkeys = [self._parse(keyboard, self.hotkey, on_press)]
        for language, hotkey in self.language_hotkeys.items():
            hotkeys.append(
                self._parse(
                    keyboard,
                    hotkey,
                    lambda language=language: on_select_language(language),
                )
            )

        def for_canonical(action: str) -> Callable[[Any], None]:
            def handle(key: Any) -> None:
                canonical = listener.canonical(normalize_letter_key(key, keyboard))
                for hotkey in hotkeys:
                    getattr(hotkey, action)(canonical)

            return handle

        try:
            with keyboard.Listener(
                on_press=for_canonical("press"),
                on_release=for_canonical("release"),
            ) as listener:
                with self._lock:
                    self._listener = listener
                    stop_requested = self._stop_requested
                if stop_requested:
                    listener.stop()
                listener.join()
        except Exception as error:
            raise HotkeyError(
                "hotkey listener failed",
                operation="hotkey_listener",
                hotkey=self.hotkey,
            ) from error
        finally:
            with self._lock:
                self._listener = None

    def stop(self) -> None:
        with self._lock:
            self._stop_requested = True
            listener = self._listener
        if listener is not None:
            listener.stop()

    @staticmethod
    def _parse(keyboard: Any, hotkey: str, on_activate: Callable[[], None]) -> Any:
        try:
            return keyboard.HotKey(keyboard.HotKey.parse(hotkey), on_activate)
        except Exception as error:
            raise HotkeyError(
                "failed to parse hotkey",
                operation="hotkey_listener",
                hotkey=hotkey,
            ) from error
