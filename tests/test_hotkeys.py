import sys
from types import SimpleNamespace

import pytest

from lib.errors import HotkeyError
from lib.hotkeys import PynputHotkeyListener


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
