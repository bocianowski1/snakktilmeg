import logging

import pytest

from lib.errors import IndicatorError
from lib.indicator import Rect
from lib.windows_indicator import WindowsActivityIndicator
from lib.windows_indicator import overlay_frame


class FakeRoot:
    def __init__(self) -> None:
        self.quit_calls = 0
        self.scheduled: list[object] = []

    def quit(self) -> None:
        self.quit_calls += 1

    def after(self, delay: int, callback: object) -> None:
        self.scheduled.append(callback)


def prepared_indicator() -> tuple[WindowsActivityIndicator, FakeRoot]:
    indicator = WindowsActivityIndicator()
    root = FakeRoot()
    indicator._root = root
    indicator._prepared = True
    return indicator, root


def test_overlay_is_centered_above_work_area_bottom_edge() -> None:
    assert overlay_frame(Rect(100, 80, 1200, 800)) == Rect(605, 804, 190, 52)


def test_updates_before_prepare_raise_indicator_error() -> None:
    indicator = WindowsActivityIndicator()

    with pytest.raises(IndicatorError) as error:
        indicator.show_recording()

    assert error.value.context["operation"] == "_show_recording"


def test_run_before_prepare_raises_indicator_error() -> None:
    with pytest.raises(IndicatorError):
        WindowsActivityIndicator().run()


def test_stop_before_prepare_is_a_no_op() -> None:
    WindowsActivityIndicator().stop()


def test_updates_are_queued_until_event_loop_drains_them(monkeypatch) -> None:
    indicator, _ = prepared_indicator()
    calls: list[str] = []
    monkeypatch.setattr(indicator, "_show_recording", lambda: calls.append("rec"))
    monkeypatch.setattr(indicator, "_hide", lambda: calls.append("hide"))

    indicator.show_recording()
    indicator.hide()
    assert calls == []

    indicator._drain()

    assert calls == ["rec", "hide"]


def test_failed_update_is_logged_and_later_updates_still_run(caplog) -> None:
    indicator, _ = prepared_indicator()
    calls: list[str] = []

    def failing_update() -> None:
        raise RuntimeError("tk error")

    indicator._dispatch(failing_update)
    indicator._dispatch(lambda: calls.append("next"))

    with caplog.at_level(logging.ERROR):
        indicator._drain()

    assert calls == ["next"]
    assert caplog.records[0].event == "indicator_update_failed"
    assert caplog.records[0].operation == "failing_update"


def test_stop_quits_event_loop_from_poll() -> None:
    indicator, root = prepared_indicator()

    indicator.stop()
    indicator._poll()

    assert root.quit_calls == 1
    assert root.scheduled == []


def test_poll_reschedules_while_running() -> None:
    indicator, root = prepared_indicator()

    indicator._poll()

    assert root.quit_calls == 0
    assert root.scheduled == [indicator._poll]


def test_interrupt_quits_event_loop_on_next_poll() -> None:
    indicator, root = prepared_indicator()

    indicator._request_interrupt(2, None)
    indicator._poll()

    assert root.quit_calls == 1
    assert root.scheduled == []
