"""Tests for core.selector - the scenario / replay session selection screen."""

from unittest.mock import MagicMock, patch

import pytest

from core.constants import COLORS as C
from core.constants import PATHS as P
from core.selector import FileSelector, mouse, winkey

# Window of 800 x 600: (600 - 2 * 40 margin - 70 title - 50 footer) / 32 px rows = 12 visible rows
VISIBLE_ROWS = 12


@pytest.fixture(autouse=True)
def graphics():
    """Each Label / Rectangle is a distinct mock (real ones need an OpenGL context)."""
    with (
        patch("core.selector.Label", side_effect=lambda *args, **kwargs: MagicMock(text=args[0] if args else "")),
        patch("core.selector.Rectangle", side_effect=lambda **kwargs: MagicMock()),
    ):
        yield


@pytest.fixture
def folders(tmp_path):
    scenarios, sessions = tmp_path / "scenarios", tmp_path / "sessions"
    scenarios.mkdir()
    sessions.mkdir()
    with patch.dict(P, {"SCENARIOS": scenarios, "SESSIONS": sessions}):
        yield scenarios, sessions


def _write(path, size=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x" * size)
    return path


def _window():
    return MagicMock(width=800, height=600)


def _scenarios(folders, n):
    for i in range(n):
        _write(folders[0] / f"s{i:02d}.txt")
    return FileSelector(_window())


class TestScanAndFormat:
    def test_scenarios_sorted_with_subfolders(self, folders):
        scenarios = folders[0]
        _write(scenarios / "default.txt")
        _write(scenarios / "basic" / "track.txt")
        _write(scenarios / "notes.md")
        fs = FileSelector(_window())
        assert fs._display_texts == [str((scenarios / "basic" / "track").relative_to(scenarios)), "default"]

    def test_sessions_sorted_by_number(self, folders):
        sessions = folders[1]
        for name in ("10_240105_093000.csv", "2_240101_120000.csv", "notanumber.csv"):
            _write(sessions / "2024" / name)
        fs = FileSelector(_window(), mode="replay")
        assert [f.name for f in fs._files] == ["notanumber.csv", "2_240101_120000.csv", "10_240105_093000.csv"]
        assert fs._display_texts == ["notanumber", "#2 — 2024-01-01 12:00:00", "#10 — 2024-01-05 09:30:00"]

    def test_session_with_an_invalid_date(self, folders):
        _write(folders[1] / "3_999999_000000.csv")
        fs = FileSelector(_window(), mode="replay")
        assert fs._display_texts == ["3_999999_000000"]

    def test_small_files_are_marked_empty(self, folders):
        _write(folders[0] / "a.txt", size=10)
        _write(folders[0] / "b.txt")
        fs = FileSelector(_window())
        assert fs._display_texts == ["a  (vide)", "b"]
        assert fs._empty_indices == {0}


class TestBuildUi:
    def test_layout(self, folders):
        fs = _scenarios(folders, 3)
        assert fs._visible_rows == VISIBLE_ROWS
        assert len(fs._label_pool) == VISIBLE_ROWS
        assert fs._title_label.text == "Select a scenario"
        assert [lbl.text for lbl in fs._label_pool[:4]] == ["s00", "s01", "s02", ""]

    def test_replay_title(self, folders):
        fs = FileSelector(_window(), mode="replay")
        assert fs._title_label.text == "Select a session"

    def test_no_files(self, folders):
        fs = FileSelector(_window())
        assert fs._selected_index == -1
        assert any(v.text == "No files found" for v in fs._vertices)
        assert fs._highlight.visible is False

    def test_row_colors_and_highlight(self, folders):
        _write(folders[0] / "a.txt")
        _write(folders[0] / "b.txt", size=10)
        _write(folders[0] / "c.txt")
        fs = FileSelector(_window())
        assert [lbl.color for lbl in fs._label_pool[:3]] == [C["WHITE"], C["GREY"], C["BLACK"]]
        assert fs._highlight.visible is True
        assert (fs._highlight.x, fs._highlight.y) == (40, 600 - 40 - 70 - 32)
        assert (fs._highlight.width, fs._highlight.height) == (800 - 80, 32)


class TestKeyboard:
    def test_up_down_stop_at_the_ends(self, folders):
        fs = _scenarios(folders, 3)
        fs._on_key_press(winkey.UP, 0)
        assert fs._selected_index == 0
        for _ in range(5):
            fs._on_key_press(winkey.DOWN, 0)
        assert fs._selected_index == 2

    def test_down_scrolls_the_list(self, folders):
        fs = _scenarios(folders, 20)
        for _ in range(VISIBLE_ROWS):
            fs._on_key_press(winkey.DOWN, 0)
        assert fs._selected_index == VISIBLE_ROWS
        assert fs._scroll_offset == 1
        assert fs._label_pool[0].text == "s01"
        assert fs._label_pool[-1].color == C["WHITE"]

    def test_up_scrolls_back(self, folders):
        fs = _scenarios(folders, 20)
        fs._on_key_press(winkey.END, 0)
        assert (fs._selected_index, fs._scroll_offset) == (19, 8)
        for _ in range(12):
            fs._on_key_press(winkey.UP, 0)
        assert (fs._selected_index, fs._scroll_offset) == (7, 7)
        fs._on_key_press(winkey.HOME, 0)
        assert (fs._selected_index, fs._scroll_offset) == (0, 0)

    def test_page_up_and_down(self, folders):
        fs = _scenarios(folders, 30)
        fs._on_key_press(winkey.PAGEDOWN, 0)
        assert fs._selected_index == VISIBLE_ROWS
        fs._on_key_press(winkey.PAGEDOWN, 0)
        fs._on_key_press(winkey.PAGEDOWN, 0)
        assert fs._selected_index == 29
        fs._on_key_press(winkey.PAGEUP, 0)
        assert fs._selected_index == 29 - VISIBLE_ROWS
        fs._on_key_press(winkey.PAGEUP, 0)
        fs._on_key_press(winkey.PAGEUP, 0)
        assert fs._selected_index == 0

    @pytest.mark.parametrize("enter", ["RETURN", "NUM_ENTER"])
    def test_enter_selects(self, folders, enter):
        fs = _scenarios(folders, 3)
        fs._on_key_press(winkey.DOWN, 0)
        fs._on_key_press(getattr(winkey, enter), 0)
        assert fs._done is True
        assert fs._selected_path == fs._files[1]

    def test_escape_quits_without_selection(self, folders):
        fs = _scenarios(folders, 3)
        fs._on_key_press(winkey.ESCAPE, 0)
        assert fs._done is True
        assert fs._selected_path is None

    def test_no_files(self, folders):
        fs = FileSelector(_window())
        for symbol in (winkey.RETURN, winkey.END, winkey.PAGEDOWN):
            assert fs._on_key_press(symbol, 0) is True
        assert fs._done is False
        assert fs._selected_index == -1

    def test_events_are_consumed(self, folders):
        fs = _scenarios(folders, 1)
        assert fs._on_key_press(winkey.SPACE, 0) is True
        assert fs._on_key_release(winkey.SPACE, 0) is True


class TestMouse:
    def _row_y(self, row):
        return 600 - 40 - 70 - (row + 0.5) * 32

    def test_scroll_keeps_the_selection_visible(self, folders):
        fs = _scenarios(folders, 20)
        fs._on_mouse_scroll(0, 0, 0, -3)  # Scroll down
        assert fs._scroll_offset == 3
        assert fs._selected_index == 3
        fs._on_mouse_scroll(0, 0, 0, -100)
        assert fs._scroll_offset == 8  # 20 files - 12 rows
        fs._selected_index = 19
        fs._on_mouse_scroll(0, 0, 0, 5)  # Scroll up
        assert fs._scroll_offset == 3
        assert fs._selected_index == 14

    def test_scroll_without_files(self, folders):
        fs = FileSelector(_window())
        assert fs._on_mouse_scroll(0, 0, 0, -3) is True
        assert fs._scroll_offset == 0

    def test_row_at_y(self, folders):
        fs = _scenarios(folders, 3)
        assert fs._row_index_at_y(self._row_y(1)) == 1
        assert fs._row_index_at_y(self._row_y(5)) is None  # Empty row
        assert fs._row_index_at_y(600) is None  # Title area

    def test_click_selects_and_double_click_confirms(self, folders):
        fs = _scenarios(folders, 3)
        with patch("core.selector._time.monotonic", side_effect=[10.0, 10.2]):
            fs._on_mouse_press(100, self._row_y(2), mouse.LEFT, 0)
            assert fs._selected_index == 2
            assert fs._done is False
            fs._on_mouse_press(100, self._row_y(2), mouse.LEFT, 0)
        assert fs._done is True
        assert fs._selected_path == fs._files[2]

    def test_slow_second_click_only_selects(self, folders):
        fs = _scenarios(folders, 3)
        with patch("core.selector._time.monotonic", side_effect=[10.0, 11.0]):
            fs._on_mouse_press(100, self._row_y(2), mouse.LEFT, 0)
            fs._on_mouse_press(100, self._row_y(2), mouse.LEFT, 0)
        assert fs._done is False

    def test_double_click_on_two_rows_only_selects(self, folders):
        fs = _scenarios(folders, 3)
        with patch("core.selector._time.monotonic", side_effect=[10.0, 10.1]):
            fs._on_mouse_press(100, self._row_y(0), mouse.LEFT, 0)
            fs._on_mouse_press(100, self._row_y(1), mouse.LEFT, 0)
        assert fs._done is False
        assert fs._selected_index == 1

    def test_ignored_clicks(self, folders):
        fs = _scenarios(folders, 3)
        fs._on_mouse_press(100, self._row_y(1), mouse.RIGHT, 0)
        fs._on_mouse_press(100, 600, mouse.LEFT, 0)
        assert fs._selected_index == 0
        assert fs._last_click_index == -1


class TestRun:
    def test_returns_the_selected_file(self, folders):
        fs = _scenarios(folders, 3)
        win = fs.win
        vertices = list(fs._vertices)
        win.dispatch_events.side_effect = lambda: fs._on_key_press(winkey.RETURN, 0)

        assert fs.run() == fs._files[0]

        win.push_handlers.assert_called_once()
        win.batch.draw.assert_called_once()
        win.flip.assert_called_once()
        win.pop_handlers.assert_called_once()
        assert all(v.delete.called for v in vertices)
        assert fs._vertices == [] and fs._label_pool == []

    def test_no_files_returns_none_at_once(self, folders):
        fs = FileSelector(_window())
        assert fs.run() is None
        fs.win.push_handlers.assert_not_called()
        assert fs._vertices == []
