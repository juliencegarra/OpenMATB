"""Tests for the event-driven FileSelector (no blocking loop)."""

from pathlib import Path
from unittest.mock import MagicMock

from pyglet.window import key as winkey

from core.selector import FileSelector


def _make_selector(files):
    """Create a FileSelector bypassing __init__ (no graphics)."""
    sel = object.__new__(FileSelector)
    sel.win = MagicMock()
    sel.win.selector_visible = False
    sel.mode = "scenario"
    sel._done = False
    sel._selected_path = None
    sel._on_done = None
    sel._files = files
    sel._selected_index = 0
    sel._vertices = []
    sel._label_pool = []
    return sel


class TestEmptyFiles:
    def test_small_session_files_are_marked_empty(self, tmp_path):
        small, full = tmp_path / "1_small.csv", tmp_path / "2_full.csv"
        small.write_text("logtime\n")
        full.write_text("x" * 600)
        sel = _make_selector([small, full])
        sel.mode = "replay"
        assert sel._find_empty_indices() == {0}

    def test_short_scenarios_are_not_marked_empty(self, tmp_path):
        scenario = tmp_path / "test_1s.txt"
        scenario.write_text("0:00:00;sysmon;start\n0:00:01;sysmon;stop\n")
        assert _make_selector([scenario])._find_empty_indices() == set()


class TestOpen:
    def test_pushes_handlers_and_shows_mouse(self):
        sel = _make_selector([Path("a.txt")])
        sel.open(MagicMock())
        sel.win.push_handlers.assert_called_once()
        assert sel.win.selector_visible is True

    def test_no_files_calls_back_with_none(self):
        sel = _make_selector([])
        callback = MagicMock()
        sel.open(callback)
        callback.assert_called_once_with(None)
        sel.win.push_handlers.assert_not_called()


class TestFinish:
    def test_return_calls_back_with_selected_file(self):
        sel = _make_selector([Path("a.txt"), Path("b.txt")])
        callback = MagicMock()
        sel.open(callback)
        sel._selected_index = 1
        sel._on_key_press(winkey.RETURN, 0)
        callback.assert_called_once_with(Path("b.txt"))
        sel.win.remove_handlers.assert_called_once()
        assert sel.win.selector_visible is False

    def test_escape_calls_back_with_none(self):
        sel = _make_selector([Path("a.txt")])
        callback = MagicMock()
        sel.open(callback)
        sel._on_key_press(winkey.ESCAPE, 0)
        callback.assert_called_once_with(None)

    def test_callback_called_only_once(self):
        sel = _make_selector([Path("a.txt")])
        callback = MagicMock()
        sel.open(callback)
        sel._on_key_press(winkey.RETURN, 0)
        sel._on_key_press(winkey.RETURN, 0)
        callback.assert_called_once()
