from __future__ import annotations

from core.window import Window

_errors: Errors | None = None


def get_errors() -> Errors:
    global _errors
    if _errors is None:
        _errors = Errors()
    return _errors


def set_errors(e: Errors | None) -> None:
    global _errors
    _errors = e


class Errors:
    def __init__(self) -> None:
        self.errors_list: list[str] = list()
        self.some_fatals: bool = False

    def add_error(self, error_msg: str, fatal: bool = False) -> None:
        self.some_fatals = max(self.some_fatals, fatal)
        self.errors_list.append("– " + error_msg)

    def is_empty(self) -> bool:
        return len(self.errors_list) == 0

    def show_errors(self) -> None:
        if Window.MainWindow is not None:
            if not self.is_empty():
                pass_list = list(self.errors_list)
                self.errors_list = list()
                title: str = _("Warning") if not self.some_fatals else _("Error(s)")
                continue_key: str | None = None if self.some_fatals else "SPACE"
                Window.MainWindow.open_modal_window(pass_list, title=title, continue_key=continue_key, exit_key="Q")
