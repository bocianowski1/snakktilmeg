from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import logging
import sys
import threading
from typing import Any

from lib.errors import HotkeyError
from lib.logging import get_logger


VK_A = 0x41
VK_Z = 0x5A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WIN32_MODIFIER_VKS = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "cmd": 0x5B,
}


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


@dataclass(frozen=True)
class SuppressedHotkey:
    vk: int
    modifier_vks: tuple[int, ...]
    on_activate: Callable[[], None]


def win32_suppressed_hotkey(
    hotkey: str,
    on_activate: Callable[[], None],
) -> SuppressedHotkey | None:
    """Return a blockable form of ``<modifier>+...+<letter>`` hotkeys.

    Other hotkey shapes return ``None`` and are only matched, not blocked.
    """
    *modifiers, key = hotkey.lower().split("+")
    if not modifiers or len(key) != 1 or not "a" <= key <= "z":
        return None
    modifier_vks: list[int] = []
    for modifier in modifiers:
        vk = WIN32_MODIFIER_VKS.get(modifier.strip("<>"))
        if vk is None:
            return None
        modifier_vks.append(vk)
    return SuppressedHotkey(ord(key.upper()), tuple(modifier_vks), on_activate)


def win32_key_pressed(vk: int) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    return bool(ctypes.WinDLL("user32").GetAsyncKeyState(vk) & 0x8000)


class Win32HotkeyFilter:
    """Activates letter hotkeys from the Windows keyboard hook and blocks them.

    Blocked events never reach other apps or pynput's callbacks, so the hotkey
    is activated here instead. Key repeats and the matching key release are
    blocked too, so ``AltGr+E`` switches language without typing ``€``.
    """

    def __init__(
        self,
        hotkeys: Sequence[SuppressedHotkey],
        is_pressed: Callable[[int], bool] = win32_key_pressed,
        logger: logging.Logger | None = None,
    ) -> None:
        self.hotkeys = list(hotkeys)
        self.is_pressed = is_pressed
        self.logger = logger or get_logger(__name__)
        self._blocked_vks: set[int] = set()

    def should_suppress(self, msg: int, vk: int) -> bool:
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if vk in self._blocked_vks:
                return True
            for hotkey in self.hotkeys:
                if hotkey.vk == vk and all(
                    self.is_pressed(modifier) for modifier in hotkey.modifier_vks
                ):
                    self._blocked_vks.add(vk)
                    self._activate(hotkey)
                    return True
        elif msg in (WM_KEYUP, WM_SYSKEYUP) and vk in self._blocked_vks:
            self._blocked_vks.discard(vk)
            return True
        return False

    def _activate(self, hotkey: SuppressedHotkey) -> None:
        # This runs inside the keyboard hook; an exception here would stop the
        # pynput listener, so log it and keep listening.
        try:
            hotkey.on_activate()
        except Exception as error:
            self.logger.error(
                "hotkey callback failed",
                extra={"event": "hotkey_callback_failed", "vk": hotkey.vk},
                exc_info=error,
            )


class PynputHotkeyListener:
    def __init__(
        self,
        hotkey: str = "<ctrl>+<alt>+<space>",
        language_hotkeys: Mapping[str, str] | None = None,
        platform: str = sys.platform,
    ) -> None:
        self.hotkey = hotkey
        self.language_hotkeys = dict(language_hotkeys or {})
        self.platform = platform
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
        suppressed: list[SuppressedHotkey] = []
        for language, hotkey in self.language_hotkeys.items():
            def select(language: str = language) -> None:
                on_select_language(language)

            hotkeys.append(self._parse(keyboard, hotkey, select))
            if self.platform == "win32":
                blockable = win32_suppressed_hotkey(hotkey, select)
                if blockable is not None:
                    suppressed.append(blockable)

        def for_canonical(action: str) -> Callable[[Any], None]:
            def handle(key: Any) -> None:
                canonical = listener.canonical(
                    normalize_letter_key(key, keyboard, self.platform)
                )
                for hotkey in hotkeys:
                    getattr(hotkey, action)(canonical)

            return handle

        options: dict[str, Any] = {}
        if suppressed:
            hotkey_filter = Win32HotkeyFilter(suppressed, is_pressed=win32_key_pressed)

            def win32_event_filter(msg: int, data: Any) -> bool:
                if hotkey_filter.should_suppress(msg, data.vkCode):
                    listener.suppress_event()
                return True

            options["win32_event_filter"] = win32_event_filter

        try:
            # suppress_event() exists only on pynput's Windows listener.
            listener: Any = keyboard.Listener(
                on_press=for_canonical("press"),
                on_release=for_canonical("release"),
                **options,
            )
            with listener:
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
