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
