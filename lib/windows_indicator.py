# tkinter widgets are created in prepare(), so they are optional until then.
# pyright: reportOptionalMemberAccess=false

from collections.abc import Callable
import logging
import queue
import sys
from typing import Any

from lib.errors import IndicatorError
from lib.indicator import PANEL_BOTTOM_MARGIN
from lib.indicator import PANEL_HEIGHT
from lib.indicator import PANEL_WIDTH
from lib.indicator import Rect
from lib.indicator import status_text
from lib.logging import get_logger


POLL_INTERVAL_MS = 50
SPINNER_INTERVAL_MS = 40
SPINNER_STEP_DEGREES = 20
CORNER_RADIUS = 14
TRANSPARENT_COLOR = "#ff00ff"
BACKGROUND_COLOR = "#262626"
RECORDING_COLOR = "#ff453a"
TEXT_COLOR = "#ffffff"

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
MONITOR_DEFAULTTOPRIMARY = 1


def overlay_frame(work_area: Rect) -> Rect:
    # Windows screen coordinates grow downward from the top-left corner.
    return Rect(
        x=work_area.x + (work_area.width - PANEL_WIDTH) / 2,
        y=work_area.y + work_area.height - PANEL_BOTTOM_MARGIN - PANEL_HEIGHT,
        width=PANEL_WIDTH,
        height=PANEL_HEIGHT,
    )


class WindowsActivityIndicator:
    """Click-through status pill drawn with tkinter.

    tkinter must only be touched from the thread running ``run()``, so the
    public show/hide methods enqueue work that the event loop drains.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or get_logger(__name__)
        self._prepared = False
        self._commands: queue.Queue[Callable[[], None]] = queue.Queue()
        self._interrupted = False
        self._stopping = False
        self._spinning = False
        self._spinner_start = 0
        self._root: Any | None = None
        self._canvas: Any | None = None
        self._dot: Any | None = None
        self._spinner: Any | None = None
        self._label: Any | None = None
        self._hwnd: int | None = None

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
        import signal

        # A KeyboardInterrupt raised inside a tkinter callback is swallowed by
        # tkinter's callback error reporting, so turn Ctrl-C into a flag that
        # the poll loop handles, then re-raise once the event loop has exited.
        previous_handler = signal.signal(signal.SIGINT, self._request_interrupt)
        try:
            self._root.after(POLL_INTERVAL_MS, self._poll)
            self._root.mainloop()
        finally:
            signal.signal(signal.SIGINT, previous_handler)
            self._spinning = False
            self._root.destroy()
        if self._interrupted:
            raise KeyboardInterrupt

    def stop(self) -> None:
        if not self._prepared:
            return
        self._commands.put(self._quit)

    def show_recording(self, language: str | None = None) -> None:
        self._dispatch(self._show_recording, language)

    def show_transcribing(self, language: str | None = None) -> None:
        self._dispatch(self._show_transcribing, language)

    def hide(self) -> None:
        self._dispatch(self._hide)

    def _prepare(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        root.configure(background=TRANSPARENT_COLOR)
        # Map the window off-screen once so the native frame exists, then hide
        # it through Win32 so tkinter keeps painting it when it is shown again.
        root.geometry(f"{int(PANEL_WIDTH)}x{int(PANEL_HEIGHT)}+-10000+-10000")

        canvas = tk.Canvas(
            root,
            width=PANEL_WIDTH,
            height=PANEL_HEIGHT,
            background=TRANSPARENT_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack()
        _draw_rounded_rect(
            canvas, 0, 0, PANEL_WIDTH, PANEL_HEIGHT, CORNER_RADIUS, BACKGROUND_COLOR
        )
        dot = canvas.create_oval(20, 18, 36, 34, fill=RECORDING_COLOR, outline="")
        spinner = canvas.create_arc(
            18,
            16,
            38,
            36,
            start=0,
            extent=270,
            style=tk.ARC,
            outline=TEXT_COLOR,
            width=3,
            state=tk.HIDDEN,
        )
        label = canvas.create_text(
            50,
            PANEL_HEIGHT / 2,
            anchor=tk.W,
            text="Listening…",
            fill=TEXT_COLOR,
            font=("Segoe UI", 11, "bold"),
        )
        root.update()

        hwnd = int(root.wm_frame(), 16)
        user32 = _user32()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style
            | WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
            | WS_EX_TOPMOST,
        )
        user32.ShowWindow(hwnd, SW_HIDE)

        self._root = root
        self._canvas = canvas
        self._dot = dot
        self._spinner = spinner
        self._label = label
        self._hwnd = hwnd
        self._prepared = True

    def _request_interrupt(self, signum: int, frame: object) -> None:
        self._interrupted = True

    def _poll(self) -> None:
        if self._interrupted:
            self._quit()
            return
        self._drain()
        if not self._stopping:
            self._root.after(POLL_INTERVAL_MS, self._poll)

    def _drain(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                command()
            except Exception as error:
                wrapped = IndicatorError(
                    "failed to update activity indicator",
                    operation=getattr(command, "__name__", "indicator_command"),
                )
                self.logger.error(
                    "activity indicator update failed",
                    extra={
                        "event": "indicator_update_failed",
                        **wrapped.log_context(),
                    },
                    exc_info=error,
                )

    def _quit(self) -> None:
        self._stopping = True
        self._spinning = False
        self._root.quit()

    def _dispatch(self, callback: Callable[..., None], *args: object) -> None:
        if not self._prepared:
            raise IndicatorError(
                "activity indicator is not initialized",
                operation=callback.__name__,
            )

        def command() -> None:
            callback(*args)

        command.__name__ = callback.__name__
        self._commands.put(command)

    def _show_recording(self, language: str | None) -> None:
        self._spinning = False
        self._canvas.itemconfigure(self._spinner, state="hidden")
        self._canvas.itemconfigure(self._dot, state="normal")
        self._canvas.itemconfigure(
            self._label, text=status_text("Listening…", language)
        )
        self._show_on_focused_display()

    def _show_transcribing(self, language: str | None) -> None:
        self._canvas.itemconfigure(self._dot, state="hidden")
        self._canvas.itemconfigure(self._spinner, state="normal")
        self._canvas.itemconfigure(
            self._label, text=status_text("Transcribing…", language)
        )
        if not self._spinning:
            self._spinning = True
            self._spin()
        self._show_on_focused_display()

    def _hide(self) -> None:
        self._spinning = False
        _user32().ShowWindow(self._hwnd, SW_HIDE)

    def _spin(self) -> None:
        if not self._spinning:
            return
        self._spinner_start = (self._spinner_start - SPINNER_STEP_DEGREES) % 360
        self._canvas.itemconfigure(self._spinner, start=self._spinner_start)
        self._root.after(SPINNER_INTERVAL_MS, self._spin)

    def _show_on_focused_display(self) -> None:
        frame = overlay_frame(self._focused_work_area())
        # SWP_NOACTIVATE keeps keyboard focus in the app that will receive the
        # pasted transcript.
        _user32().SetWindowPos(
            self._hwnd,
            HWND_TOPMOST,
            int(frame.x),
            int(frame.y),
            int(frame.width),
            int(frame.height),
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _focused_work_area(self) -> Rect:
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32 = _user32()
        # Without a foreground window this falls back to the primary display.
        monitor = user32.MonitorFromWindow(
            user32.GetForegroundWindow(), MONITOR_DEFAULTTOPRIMARY
        )
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            raise IndicatorError("no displays available", operation="select_display")
        work = info.rcWork
        return Rect(
            float(work.left),
            float(work.top),
            float(work.right - work.left),
            float(work.bottom - work.top),
        )


def _user32() -> Any:
    if sys.platform != "win32":
        raise IndicatorError(
            "Windows APIs are only available on Windows",
            operation="load_user32",
        )
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    return user32


def _draw_rounded_rect(
    canvas: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    fill: str,
) -> None:
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]  # fmt: skip
    canvas.create_polygon(points, smooth=True, fill=fill, outline="")
