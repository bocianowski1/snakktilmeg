from lib.tray import TrayLanguage
from lib.tray import format_hotkey
from lib.tray import language_menu_label


def test_format_hotkey_shows_ctrl_alt_as_altgr() -> None:
    assert format_hotkey("<ctrl>+<alt>+n") == "AltGr+N"


def test_format_hotkey_names_other_modifiers() -> None:
    assert format_hotkey("<ctrl>+<shift>+<f9>") == "Ctrl+Shift+F9"


def test_language_menu_label_uses_language_name_and_hotkey() -> None:
    assert language_menu_label(TrayLanguage("no", "<ctrl>+<alt>+n")) == (
        "Norwegian (AltGr+N)"
    )
    assert language_menu_label(TrayLanguage("de", "<ctrl>+<alt>+d")) == (
        "DE (AltGr+D)"
    )
