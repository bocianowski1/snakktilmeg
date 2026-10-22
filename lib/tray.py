# pystray and Pillow are only installed on Windows.
# pyright: reportMissingImports=false

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import logging
import threading
from typing import Any

from lib.errors import TrayError
from lib.logging import get_logger


ICON_SIZE = 64
ICON_BACKGROUND = (38, 38, 38, 255)
ICON_DOT = (255, 69, 58, 255)
LANGUAGE_NAMES = {"en": "English", "no": "Norwegian"}


@dataclass(frozen=True)
class TrayLanguage:
    code: str
    hotkey: str


def language_menu_label(language: TrayLanguage) -> str:
    name = LANGUAGE_NAMES.get(language.code, language.code.upper())
    return f"{name} ({format_hotkey(language.hotkey)})"


def format_hotkey(hotkey: str) -> str:
    names = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "altgr": "AltGr",
        "shift": "Shift",
        "cmd": "Win",
    }
    parts = [part.strip("<>") for part in hotkey.split("+")]
    # On Windows, Ctrl+Alt is AltGr, which is how people press these keys.
    if parts[:2] == ["ctrl", "alt"]:
        parts = ["altgr", *parts[2:]]
    return "+".join(names.get(part, part.upper()) for part in parts)


class PystrayTrayIcon:
    """Notification-area icon with language selection and Quit."""

    def __init__(
        self,
        languages: Sequence[TrayLanguage],
        on_select_language: Callable[[str], None],
        active_language: Callable[[], str | None],
        on_quit: Callable[[], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self.languages = list(languages)
        self.on_select_language = on_select_language
        self.active_language = active_language
        self.on_quit = on_quit
        self.logger = logger or get_logger(__name__)
        self._icon: Any | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            import pystray

            self._icon = pystray.Icon(
                "snakktilmeg",
                icon=_icon_image(),
                title="snakktilmeg",
                menu=pystray.Menu(*self._menu_items(pystray)),
            )
        except Exception as error:
            raise TrayError(
                "failed to create tray icon",
                operation="start_tray",
            ) from error
        # The Windows backend runs its own message loop on any thread.
        self._thread = threading.Thread(
            target=self._run, name="tray-icon", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        icon = self._icon
        if icon is not None:
            icon.stop()

    def _run(self) -> None:
        try:
            assert self._icon is not None
            self._icon.run()
        except Exception as error:
            wrapped = TrayError("tray icon failed", operation="run_tray")
            self.logger.error(
                "tray icon failed",
                extra={"event": "tray_failed", **wrapped.log_context()},
                exc_info=error,
            )

    def _menu_items(self, pystray: Any) -> list[Any]:
        items: list[Any] = []
        for language in self.languages:
            items.append(
                pystray.MenuItem(
                    language_menu_label(language),
                    self._select_action(language.code),
                    checked=self._is_active(language.code),
                    radio=True,
                )
            )
        if items:
            items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", self._quit))
        return items

    def _select_action(self, code: str) -> Callable[[Any, Any], None]:
        def select(icon: Any, item: Any) -> None:
            self.on_select_language(code)

        return select

    def _is_active(self, code: str) -> Callable[[Any], bool]:
        return lambda item: self.active_language() == code

    def _quit(self, icon: Any, item: Any) -> None:
        self.on_quit()


def _icon_image() -> Any:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, ICON_SIZE - 2, ICON_SIZE - 2), fill=ICON_BACKGROUND)
    draw.ellipse((20, 20, ICON_SIZE - 20, ICON_SIZE - 20), fill=ICON_DOT)
    return image
