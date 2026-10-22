import sys
from types import SimpleNamespace

import pytest

from lib.errors import HotkeyError
from lib.hotkeys import PynputHotkeyListener
from lib.hotkeys import SuppressedHotkey
from lib.hotkeys import WM_KEYDOWN
from lib.hotkeys import WM_KEYUP
from lib.hotkeys import WM_SYSKEYDOWN
from lib.hotkeys import WM_SYSKEYUP
from lib.hotkeys import Win32HotkeyFilter
from lib.hotkeys import normalize_letter_key
from lib.hotkeys import win32_suppressed_hotkey


def test_pynput_hotkey_listener_wraps_parse_failure(monkeypatch) -> None:
    class FakeHotKey:
        @staticmethod
        def parse(hotkey: str) -> list[str]:
            raise ValueError(f"invalid hotkey: {hotkey}")

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(
                HotKey=FakeHotKey,
                Listener=object,
            ),
        ),
    )

    with pytest.raises(HotkeyError) as error:
        PynputHotkeyListener("<bad>").run(lambda: None)

    assert str(error.value) == "failed to parse hotkey"
    assert error.value.context["operation"] == "hotkey_listener"
    assert error.value.context["hotkey"] == "<bad>"


def test_pynput_hotkey_listener_wraps_listener_failure(monkeypatch) -> None:
    class FakeHotKey:
        def __init__(self, keys: list[str], on_press: object) -> None:
            pass

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            return [hotkey]

        def press(self, key: object) -> None:
            pass

        def release(self, key: object) -> None:
            pass

    class FailingListener:
        def __init__(self, **kwargs: object) -> None:
            raise RuntimeError("listener unavailable")

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(
                HotKey=FakeHotKey,
                Listener=FailingListener,
            ),
        ),
    )

    with pytest.raises(HotkeyError) as error:
        PynputHotkeyListener("<ctrl>+<alt>+<space>").run(lambda: None)

    assert str(error.value) == "hotkey listener failed"
    assert error.value.context["operation"] == "hotkey_listener"


def test_stop_stops_active_listener(monkeypatch) -> None:
    stopped = False

    class FakeHotKey:
        def __init__(self, keys: list[str], on_press: object) -> None:
            pass

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            return [hotkey]

        def press(self, key: object) -> None:
            pass

        def release(self, key: object) -> None:
            pass

    class FakeListener:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeListener":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def canonical(self, key: object) -> object:
            return key

        def join(self) -> None:
            listener.stop()

        def stop(self) -> None:
            nonlocal stopped
            stopped = True

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(HotKey=FakeHotKey, Listener=FakeListener),
        ),
    )
    listener = PynputHotkeyListener()

    listener.run(lambda: None)

    assert stopped


def test_stop_before_run_stops_listener_as_soon_as_it_is_created(monkeypatch) -> None:
    stop_calls = 0

    class FakeHotKey:
        def __init__(self, keys: list[str], on_press: object) -> None:
            pass

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            return [hotkey]

        def press(self, key: object) -> None:
            pass

        def release(self, key: object) -> None:
            pass

    class FakeListener:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeListener":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def canonical(self, key: object) -> object:
            return key

        def join(self) -> None:
            pass

        def stop(self) -> None:
            nonlocal stop_calls
            stop_calls += 1

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(HotKey=FakeHotKey, Listener=FakeListener),
        ),
    )
    listener = PynputHotkeyListener()
    listener.stop()

    listener.run(lambda: None)

    assert stop_calls == 1


class FakeKeyCode:
    def __init__(self, char: str | None = None, vk: int | None = None) -> None:
        self.char = char
        self.vk = vk

    @classmethod
    def from_char(cls, char: str) -> "FakeKeyCode":
        return cls(char=char)


FAKE_KEYBOARD = SimpleNamespace(KeyCode=FakeKeyCode)


def test_normalize_letter_key_uses_virtual_key_on_windows() -> None:
    altgr_e = FakeKeyCode(char="€", vk=0x45)

    normalized = normalize_letter_key(altgr_e, FAKE_KEYBOARD, platform="win32")

    assert normalized.char == "e"


def test_normalize_letter_key_leaves_non_letters_and_other_platforms() -> None:
    space = FakeKeyCode(vk=0x20)
    letter = FakeKeyCode(char="€", vk=0x45)

    assert normalize_letter_key(space, FAKE_KEYBOARD, platform="win32") is space
    assert normalize_letter_key(letter, FAKE_KEYBOARD, platform="darwin") is letter


def test_language_hotkey_selects_language(monkeypatch) -> None:
    selected: list[str] = []
    pressed: list[str] = []

    class FakeHotKey:
        def __init__(self, keys: list[str], on_activate) -> None:
            self.keys = keys
            self.on_activate = on_activate

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            return [hotkey]

        def press(self, key: object) -> None:
            if [key] == self.keys:
                self.on_activate()

        def release(self, key: object) -> None:
            pass

    class FakeListener:
        def __init__(self, *, on_press, on_release) -> None:
            self.on_press = on_press

        def __enter__(self) -> "FakeListener":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def canonical(self, key: object) -> object:
            return key

        def join(self) -> None:
            self.on_press("lang-no")
            self.on_press("main")

        def stop(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(
                HotKey=FakeHotKey, Listener=FakeListener, KeyCode=FakeKeyCode
            ),
        ),
    )

    PynputHotkeyListener("main", language_hotkeys={"no": "lang-no"}).run(
        lambda: pressed.append("main"),
        selected.append,
    )

    assert selected == ["no"]
    assert pressed == ["main"]


def test_invalid_language_hotkey_reports_that_hotkey(monkeypatch) -> None:
    class FakeHotKey:
        def __init__(self, keys: list[str], on_activate: object) -> None:
            pass

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            if hotkey == "<bad>":
                raise ValueError("invalid")
            return [hotkey]

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(keyboard=SimpleNamespace(HotKey=FakeHotKey, Listener=object)),
    )

    with pytest.raises(HotkeyError) as error:
        PynputHotkeyListener("main", language_hotkeys={"no": "<bad>"}).run(
            lambda: None
        )

    assert error.value.context["hotkey"] == "<bad>"


VK_CONTROL = 0x11
VK_MENU = 0x12
VK_E = 0x45
VK_N = 0x4E


def altgr_filter(
    activations: list[str], held: set[int] | None = None
) -> Win32HotkeyFilter:
    held_keys = {VK_CONTROL, VK_MENU} if held is None else held
    return Win32HotkeyFilter(
        [
            SuppressedHotkey(VK_E, (VK_CONTROL, VK_MENU), lambda: activations.append("en")),
            SuppressedHotkey(VK_N, (VK_CONTROL, VK_MENU), lambda: activations.append("no")),
        ],
        is_pressed=held_keys.__contains__,
    )


def test_win32_suppressed_hotkey_maps_modifiers_and_letter() -> None:
    hotkey = win32_suppressed_hotkey("<ctrl>+<alt>+e", lambda: None)

    assert hotkey is not None
    assert (hotkey.vk, hotkey.modifier_vks) == (VK_E, (VK_CONTROL, VK_MENU))


def test_win32_suppressed_hotkey_skips_non_letter_hotkeys() -> None:
    assert win32_suppressed_hotkey("<ctrl>+<alt>+<space>", lambda: None) is None
    assert win32_suppressed_hotkey("<ctrl>+<f9>", lambda: None) is None
    assert win32_suppressed_hotkey("e", lambda: None) is None


def test_filter_activates_and_blocks_altgr_letter() -> None:
    activations: list[str] = []
    hotkey_filter = altgr_filter(activations)

    assert hotkey_filter.should_suppress(WM_SYSKEYDOWN, VK_E)
    assert hotkey_filter.should_suppress(WM_SYSKEYDOWN, VK_E)
    assert hotkey_filter.should_suppress(WM_SYSKEYUP, VK_E)
    assert hotkey_filter.should_suppress(WM_KEYDOWN, VK_N)
    assert hotkey_filter.should_suppress(WM_KEYUP, VK_N)

    assert activations == ["en", "no"]


def test_filter_passes_letters_without_modifiers() -> None:
    activations: list[str] = []
    hotkey_filter = altgr_filter(activations, held={VK_CONTROL})

    assert not hotkey_filter.should_suppress(WM_KEYDOWN, VK_E)
    assert not hotkey_filter.should_suppress(WM_KEYUP, VK_E)
    assert activations == []


def test_filter_passes_other_keys_while_altgr_is_held() -> None:
    activations: list[str] = []
    hotkey_filter = altgr_filter(activations)

    assert not hotkey_filter.should_suppress(WM_SYSKEYDOWN, VK_MENU)
    assert not hotkey_filter.should_suppress(WM_SYSKEYDOWN, 0x32)
    assert activations == []


def test_filter_logs_callback_failure_and_still_blocks(caplog) -> None:
    def failing() -> None:
        raise RuntimeError("boom")

    hotkey_filter = Win32HotkeyFilter(
        [SuppressedHotkey(VK_E, (VK_CONTROL,), failing)],
        is_pressed=lambda vk: True,
    )

    assert hotkey_filter.should_suppress(WM_KEYDOWN, VK_E)
    assert caplog.records[0].event == "hotkey_callback_failed"


def test_windows_listener_blocks_language_hotkey_through_event_filter(
    monkeypatch,
) -> None:
    selected: list[str] = []
    suppressed: list[int] = []

    class FakeHotKey:
        def __init__(self, keys: list[str], on_activate: object) -> None:
            pass

        @staticmethod
        def parse(hotkey: str) -> list[str]:
            return [hotkey]

        def press(self, key: object) -> None:
            pass

        def release(self, key: object) -> None:
            pass

    class FakeListener:
        def __init__(self, *, on_press, on_release, win32_event_filter) -> None:
            self.event_filter = win32_event_filter

        def __enter__(self) -> "FakeListener":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def suppress_event(self) -> None:
            suppressed.append(1)

        def join(self) -> None:
            self.event_filter(WM_SYSKEYDOWN, SimpleNamespace(vkCode=VK_N))
            self.event_filter(WM_KEYDOWN, SimpleNamespace(vkCode=0x41))

        def stop(self) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(
            keyboard=SimpleNamespace(HotKey=FakeHotKey, Listener=FakeListener),
        ),
    )
    monkeypatch.setattr(
        "lib.hotkeys.win32_key_pressed", lambda vk: vk in {VK_CONTROL, VK_MENU}
    )

    PynputHotkeyListener(
        "<ctrl>+<alt>+<space>",
        language_hotkeys={"no": "<ctrl>+<alt>+n"},
        platform="win32",
    ).run(lambda: None, selected.append)

    assert selected == ["no"]
    assert suppressed == [1]
