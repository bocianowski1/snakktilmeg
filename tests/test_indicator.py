import sys
from types import SimpleNamespace

from lib.indicator import MacOSActivityIndicator
from lib.indicator import Rect
from lib.indicator import intersection_area
from lib.indicator import overlay_frame
from lib.indicator import select_display_id


def test_intersection_area_returns_overlap() -> None:
    assert intersection_area(Rect(0, 0, 100, 100), Rect(50, 25, 100, 100)) == 3750


def test_select_display_uses_largest_window_overlap() -> None:
    displays = [
        (1, Rect(0, 0, 1000, 800)),
        (2, Rect(1000, 0, 1000, 800)),
    ]

    assert select_display_id(Rect(900, 100, 500, 500), displays) == 2


def test_select_display_returns_none_when_window_is_offscreen() -> None:
    assert select_display_id(
        Rect(2000, 2000, 100, 100), [(1, Rect(0, 0, 1000, 800))]
    ) is None


def test_overlay_is_centered_above_visible_bottom_edge() -> None:
    assert overlay_frame(Rect(100, 80, 1200, 800)) == Rect(605, 104, 190, 52)


def test_run_installs_interrupt_handler_before_starting_event_loop(monkeypatch) -> None:
    calls: list[object] = []

    def install_mach_interrupt() -> None:
        calls.append("install_interrupt")

    def run_event_loop(*, installInterrupt: bool) -> None:
        calls.append(("run_event_loop", installInterrupt))

    monkeypatch.setitem(
        sys.modules,
        "PyObjCTools",
        SimpleNamespace(
            AppHelper=SimpleNamespace(
                installMachInterrupt=install_mach_interrupt,
                runEventLoop=run_event_loop,
            )
        ),
    )
    indicator = MacOSActivityIndicator()
    indicator._prepared = True

    indicator.run()

    assert calls == ["install_interrupt", ("run_event_loop", False)]
