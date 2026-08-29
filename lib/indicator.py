# PyObjC exposes framework symbols dynamically, so static type checkers cannot
# discover AppKit and Quartz attributes even when they are present at runtime.
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false

from collections.abc import Callable, Sequence
import logging
from typing import Any, NamedTuple

from lib.errors import IndicatorError
from lib.logging import get_logger


class Rect(NamedTuple):
    x: float
    y: float
    width: float
    height: float


PANEL_WIDTH = 190.0
PANEL_HEIGHT = 52.0
PANEL_BOTTOM_MARGIN = 24.0


def intersection_area(first: Rect, second: Rect) -> float:
    width = max(
        0.0,
        min(first.x + first.width, second.x + second.width)
        - max(first.x, second.x),
    )
    height = max(
        0.0,
        min(first.y + first.height, second.y + second.height)
        - max(first.y, second.y),
    )
    return width * height


def select_display_id(
    window: Rect,
    displays: Sequence[tuple[int, Rect]],
) -> int | None:
    if not displays:
        return None
    display_id, area = max(
        ((display_id, intersection_area(window, bounds)) for display_id, bounds in displays),
        key=lambda item: item[1],
    )
    return display_id if area > 0 else None


def overlay_frame(visible_frame: Rect) -> Rect:
    return Rect(
        x=visible_frame.x + (visible_frame.width - PANEL_WIDTH) / 2,
        y=visible_frame.y + PANEL_BOTTOM_MARGIN,
        width=PANEL_WIDTH,
        height=PANEL_HEIGHT,
    )


class MacOSActivityIndicator:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or get_logger(__name__)
        self._prepared = False
        self._panel: Any | None = None
        self._icon: Any | None = None
        self._label: Any | None = None
        self._spinner: Any | None = None
        self._session_screen: Any | None = None

    def prepare(self) -> None:
        try:
            self._prepare()
        except Exception as error:
            raise IndicatorError(
                "failed to initialize activity indicator",
                operation="prepare_indicator",
            ) from error

    def run(self) -> None:
        if not self._prepared:
            raise IndicatorError(
                "activity indicator is not initialized",
                operation="run_indicator",
            )
        from PyObjCTools import AppHelper

        AppHelper.runEventLoop(installInterrupt=True)

    def stop(self) -> None:
        if not self._prepared:
            return
        from PyObjCTools import AppHelper

        AppHelper.callAfter(AppHelper.stopEventLoop)

    def show_recording(self) -> None:
        self._dispatch(self._show_recording)

    def show_transcribing(self) -> None:
        self._dispatch(self._show_transcribing)

    def hide(self) -> None:
        self._dispatch(self._hide)

    def _prepare(self) -> None:
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory,
            NSBackingStoreBuffered,
            NSColor,
            NSFont,
            NSImage,
            NSImageView,
            NSMakeRect,
            NSPanel,
            NSProgressIndicator,
            NSProgressIndicatorStyleSpinning,
            NSScreenSaverWindowLevel,
            NSTextField,
            NSVisualEffectBlendingModeBehindWindow,
            NSVisualEffectMaterialHUDWindow,
            NSVisualEffectStateActive,
            NSVisualEffectView,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        application = NSApplication.sharedApplication()
        application.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setIgnoresMouseEvents_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setLevel_(NSScreenSaverWindowLevel)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        background = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT)
        )
        background.setMaterial_(NSVisualEffectMaterialHUDWindow)
        background.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        background.setState_(NSVisualEffectStateActive)
        background.setWantsLayer_(True)
        background.layer().setCornerRadius_(14.0)
        background.layer().setMasksToBounds_(True)
        panel.setContentView_(background)

        icon = NSImageView.alloc().initWithFrame_(NSMakeRect(16, 14, 24, 24))
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "mic.fill", "Recording"
        )
        icon.setImage_(image)
        icon.setContentTintColor_(NSColor.systemRedColor())
        background.addSubview_(icon)

        spinner = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(17, 15, 22, 22)
        )
        spinner.setStyle_(NSProgressIndicatorStyleSpinning)
        spinner.setDisplayedWhenStopped_(False)
        spinner.setHidden_(True)
        background.addSubview_(spinner)

        label = NSTextField.alloc().initWithFrame_(NSMakeRect(50, 15, 124, 22))
        label.setStringValue_("Listening…")
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(NSFont.systemFontOfSize_weight_(14.0, 0.5))
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        background.addSubview_(label)

        self._panel = panel
        self._icon = icon
        self._label = label
        self._spinner = spinner
        self._prepared = True

    def _dispatch(self, callback: Callable[[], None]) -> None:
        if not self._prepared:
            raise IndicatorError(
                "activity indicator is not initialized",
                operation=callback.__name__,
            )
        from PyObjCTools import AppHelper

        def safely_update() -> None:
            try:
                callback()
            except Exception as error:
                wrapped = IndicatorError(
                    "failed to update activity indicator",
                    operation=callback.__name__,
                )
                self.logger.error(
                    "activity indicator update failed",
                    extra={
                        "event": "indicator_update_failed",
                        **wrapped.log_context(),
                    },
                    exc_info=error,
                )

        AppHelper.callAfter(safely_update)

    def _show_recording(self) -> None:
        self._session_screen = self._focused_screen()
        self._position_on_screen(self._session_screen)
        self._spinner.setHidden_(True)
        self._spinner.stopAnimation_(None)
        self._icon.setHidden_(False)
        self._label.setStringValue_("Listening…")
        self._panel.orderFrontRegardless()

    def _show_transcribing(self) -> None:
        if self._session_screen is None:
            self._session_screen = self._focused_screen()
            self._position_on_screen(self._session_screen)
        self._icon.setHidden_(True)
        self._spinner.setHidden_(False)
        self._spinner.startAnimation_(None)
        self._label.setStringValue_("Transcribing…")
        self._panel.orderFrontRegardless()

    def _hide(self) -> None:
        self._spinner.stopAnimation_(None)
        self._panel.orderOut_(None)
        self._session_screen = None

    def _focused_screen(self) -> Any:
        from AppKit import NSScreen, NSWorkspace
        import Quartz

        screens = list(NSScreen.screens())
        if not screens:
            raise IndicatorError("no displays available", operation="select_display")

        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        pid = frontmost.processIdentifier() if frontmost is not None else None
        if pid is not None:
            options = (
                Quartz.kCGWindowListOptionOnScreenOnly
                | Quartz.kCGWindowListExcludeDesktopElements
            )
            windows = Quartz.CGWindowListCopyWindowInfo(
                options, Quartz.kCGNullWindowID
            )
            window_bounds = self._frontmost_window_bounds(windows, pid)
            if window_bounds is not None:
                displays: list[tuple[int, Rect]] = []
                screens_by_id: dict[int, Any] = {}
                for screen in screens:
                    display_id = int(screen.deviceDescription()["NSScreenNumber"])
                    bounds = Quartz.CGDisplayBounds(display_id)
                    displays.append(
                        (
                            display_id,
                            Rect(
                                float(bounds.origin.x),
                                float(bounds.origin.y),
                                float(bounds.size.width),
                                float(bounds.size.height),
                            ),
                        )
                    )
                    screens_by_id[display_id] = screen
                selected = select_display_id(window_bounds, displays)
                if selected is not None:
                    return screens_by_id[selected]

        return NSScreen.mainScreen() or screens[0]

    @staticmethod
    def _frontmost_window_bounds(windows: Any, pid: int) -> Rect | None:
        import Quartz

        for window in windows or []:
            if window.get(Quartz.kCGWindowOwnerPID) != pid:
                continue
            if window.get(Quartz.kCGWindowLayer, 0) != 0:
                continue
            bounds = window.get(Quartz.kCGWindowBounds)
            if not bounds:
                continue
            return Rect(
                float(bounds["X"]),
                float(bounds["Y"]),
                float(bounds["Width"]),
                float(bounds["Height"]),
            )
        return None

    def _position_on_screen(self, screen: Any) -> None:
        from AppKit import NSMakeRect

        visible = screen.visibleFrame()
        frame = overlay_frame(
            Rect(
                float(visible.origin.x),
                float(visible.origin.y),
                float(visible.size.width),
                float(visible.size.height),
            )
        )
        self._panel.setFrame_display_(
            NSMakeRect(frame.x, frame.y, frame.width, frame.height), True
        )
