"""Tests for core.window - Window logic without OpenGL initialization."""

from unittest.mock import MagicMock, patch

import pytest

from core.window import Window


def _make_window(**overrides):
    """Create a Window object bypassing __init__ to avoid pyglet/OpenGL."""
    w = object.__new__(Window)
    w.width = 1920
    w.height = 1080
    w._width = 1920
    w._height = 1080
    w.keyboard = {}
    w.modal_dialog = None
    w.batch = MagicMock()
    w.alive = True
    w.slider_visible = False
    w.selector_visible = False
    w.on_key_press_replay = None
    w.__dict__.update(overrides)
    return w


class TestGetContainerList:
    """Test container layout generation from screen dimensions."""

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_returns_10_containers(self, mock_conf):
        """Layout produces 10 named containers."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        assert len(containers) == 10

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_container_names(self, mock_conf):
        """All expected container names are present."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        names = [c.name for c in w.get_container_list()]
        assert "fullscreen" in names
        assert "topleft" in names
        assert "topmid" in names
        assert "topright" in names
        assert "bottomleft" in names
        assert "bottommid" in names
        assert "bottomright" in names
        assert "invisible" in names
        assert "mediastrip" in names
        assert "inputstrip" in names

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_fullscreen_covers_entire_area(self, mock_conf):
        """Fullscreen container spans 1920x1080."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        fs = [c for c in containers if c.name == "fullscreen"][0]
        assert fs.w == 1920
        assert fs.h == 1080
        assert fs.l == 0
        assert fs.b == 0

    @patch("core.window.REPLAY_MODE", True)
    @patch("core.window.REPLAY_STRIP_PROPORTION", 0.08)
    @patch("core.window.get_conf_value")
    def test_replay_mode_reduces_area(self, mock_conf):
        """Replay mode shrinks containers by strip proportion."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        fs = [c for c in containers if c.name == "fullscreen"][0]
        # In replay mode, mar=0.08, so w = 0.92*1920, h = 0.92*1080
        assert fs.w == pytest.approx(0.92 * 1920)
        assert fs.h == pytest.approx(0.92 * 1080)
        assert fs.b == pytest.approx(1080 * 0.08)

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_invisible_is_zero_size(self, mock_conf):
        """Invisible container has zero dimensions."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        inv = [c for c in containers if c.name == "invisible"][0]
        assert inv.w == 0
        assert inv.h == 0

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_top_row_horizontal_split(self, mock_conf):
        """Top row splits at bounds [0.35, 0.85] of total width."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = {c.name: c for c in w.get_container_list()}
        tl = containers["topleft"]
        tm = containers["topmid"]
        tr = containers["topright"]
        # topleft width = x1 = int(1920 * 0.35) = 672
        assert tl.w == int(1920 * 0.35)
        # topmid width = x2 - x1
        assert tm.w == int(1920 * 0.85) - int(1920 * 0.35)
        # topright width = w - x2
        assert tr.w == 1920 - int(1920 * 0.85)

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_top_bottom_vertical_split(self, mock_conf):
        """Top row sits on upper half, bottom row on lower half."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = {c.name: c for c in w.get_container_list()}
        # Top row: b = h/2 = 540, h = h/2 = 540
        assert containers["topleft"].b == 540
        assert containers["topleft"].h == 540
        # Bottom row: b = 0, h = h/2 = 540
        assert containers["bottomleft"].b == 0
        assert containers["bottomleft"].h == 540


class TestGetContainer:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_finds_by_name(self, mock_conf):
        """Finds a container by its name."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        c = w.get_container("topleft")
        assert c is not None
        assert c.name == "topleft"

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_returns_none_for_unknown(self, mock_conf):
        """Returns None for non-existent name."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        c = w.get_container("nonexistent")
        assert c is None


class TestIsMouseNecessary:
    @patch("core.window.REPLAY_MODE", False)
    def test_hidden_by_default(self):
        """Mouse hidden when slider not visible."""
        w = _make_window(slider_visible=False)
        assert w.is_mouse_necessary() is False

    @patch("core.window.REPLAY_MODE", False)
    def test_visible_when_slider_shown(self):
        """Mouse visible when slider is shown."""
        w = _make_window(slider_visible=True)
        assert w.is_mouse_necessary() is True

    @patch("core.window.REPLAY_MODE", True)
    def test_visible_in_replay_mode(self):
        """Mouse always visible in replay mode."""
        w = _make_window(slider_visible=False)
        assert w.is_mouse_necessary() is True


class TestExit:
    def test_sets_alive_false(self):
        """exit() sets alive to False."""
        w = _make_window(alive=True)
        w.exit()
        assert w.alive is False


class TestOnKeyPress:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_regular_key_updates_keyboard(self, mock_get_logger):
        """Key press sets keyboard[key] to True."""
        w = _make_window()
        # Simulate pressing 'A' (code 0x41)
        w.on_key_press(0x41, 0)
        assert w.keyboard["A"] is True

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_key_press(self, mock_get_logger):
        """Key press is logged."""
        w = _make_window()
        w.on_key_press(0x41, 0)
        mock_get_logger.return_value.record_input.assert_called_once_with("keyboard", "A", "press")

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    @patch("core.window.ModalDialog")
    def test_escape_triggers_exit_prompt(self, mock_dialog, mock_get_logger):
        """Escape creates exit dialog."""
        w = _make_window()
        w.on_key_press(0xFF1B, 0)  # ESCAPE
        # exit_prompt creates a ModalDialog
        mock_dialog.assert_called_once()

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    @patch("core.window.ModalDialog")
    def test_p_triggers_pause_prompt(self, mock_dialog, mock_get_logger):
        """P key creates pause dialog."""
        w = _make_window()
        w.on_key_press(0x50, 0)  # P
        # pause_prompt creates a ModalDialog
        mock_dialog.assert_called_once()

    @patch("core.window.REPLAY_MODE", True)
    @patch("core.window.get_logger")
    def test_replay_mode_ignores_keys(self, mock_get_logger):
        """Replay mode ignores regular key presses."""
        w = _make_window()
        w.on_key_press(0x41, 0)
        assert "A" not in w.keyboard
        mock_get_logger.return_value.record_input.assert_not_called()

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_modal_dialog_blocks_key(self, mock_get_logger):
        """Active modal dialog blocks key handling."""
        w = _make_window(modal_dialog=MagicMock())
        w.on_key_press(0x41, 0)
        assert "A" not in w.keyboard


class TestOnKeyRelease:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_updates_keyboard_state(self, mock_get_logger):
        """Key release sets keyboard[key] to False."""
        w = _make_window()
        w.keyboard["A"] = True
        w.on_key_release(0x41, 0)
        assert w.keyboard["A"] is False

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_release(self, mock_get_logger):
        """Key release is logged."""
        w = _make_window()
        w.keyboard["A"] = True
        w.on_key_release(0x41, 0)
        mock_get_logger.return_value.record_input.assert_called_once_with("keyboard", "A", "release")

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_modal_dialog_captures_release(self, mock_get_logger):
        """Modal dialog captures key release."""
        mock_dialog = MagicMock()
        w = _make_window(modal_dialog=mock_dialog)
        w.on_key_release(0x41, 0)
        mock_dialog.on_key_release.assert_called_once_with(0x41, 0)
        mock_get_logger.return_value.record_input.assert_not_called()

    @patch("core.window.REPLAY_MODE", True)
    @patch("core.window.get_logger")
    def test_replay_mode_ignores_release(self, mock_get_logger):
        """Replay mode ignores key releases."""
        w = _make_window()
        w.keyboard["A"] = True
        w.on_key_release(0x41, 0)
        assert w.keyboard["A"] is True  # Unchanged
        mock_get_logger.return_value.record_input.assert_not_called()


class TestOnMouseMotion:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_mouse_position(self, mock_get_logger):
        """Mouse motion logs x and y positions."""
        w = _make_window()
        w.on_mouse_motion(512, 384, 1, 0)
        calls = mock_get_logger.return_value.record_input.call_args_list
        assert len(calls) == 2
        assert calls[0].args == ("mouse", "x", 512)
        assert calls[1].args == ("mouse", "y", 384)

    @patch("core.window.REPLAY_MODE", True)
    @patch("core.window.get_logger")
    def test_replay_mode_ignores_motion(self, mock_get_logger):
        """Replay mode ignores mouse motion."""
        w = _make_window()
        w.on_mouse_motion(512, 384, 1, 0)
        mock_get_logger.return_value.record_input.assert_not_called()


class TestOnMouseDrag:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_drag_position(self, mock_get_logger):
        """Mouse drag logs x and y positions."""
        w = _make_window()
        w.on_mouse_drag(100, 200, 5, 5, 1, 0)
        calls = mock_get_logger.return_value.record_input.call_args_list
        assert len(calls) == 2
        assert calls[0].args == ("mouse", "x", 100)
        assert calls[1].args == ("mouse", "y", 200)


class TestOnMousePress:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_click_press(self, mock_get_logger):
        """Mouse press logs click with position and button."""
        w = _make_window()
        w.on_mouse_press(512, 384, 1, 0)
        mock_get_logger.return_value.record_input.assert_called_once_with(
            "mouse", "click", "press;512;384;1"
        )

    @patch("core.window.REPLAY_MODE", True)
    @patch("core.window.get_logger")
    def test_replay_mode_ignores_press(self, mock_get_logger):
        """Replay mode ignores mouse press."""
        w = _make_window()
        w.on_mouse_press(512, 384, 1, 0)
        mock_get_logger.return_value.record_input.assert_not_called()


class TestOnMouseRelease:
    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_logger")
    def test_logs_click_release(self, mock_get_logger):
        """Mouse release logs click with position and button."""
        w = _make_window()
        w.on_mouse_release(512, 384, 1, 0)
        mock_get_logger.return_value.record_input.assert_called_once_with(
            "mouse", "click", "release;512;384;1"
        )


class TestSetSizeAndLocation:
    def test_computes_centered_position(self):
        """Centers window on matching-size screen."""
        w = _make_window()
        w.switch_to = MagicMock()
        w.set_location = MagicMock()
        mock_screen = MagicMock()
        mock_screen.x = 0
        mock_screen.y = 0
        mock_screen.width = 1920
        mock_screen.height = 1080
        w.set_size_and_location(mock_screen)
        w.switch_to.assert_called_once()
        # target_x = (0 + 960) - 960 = 0, target_y = (0 + 540) - 540 = 0
        w.set_location.assert_called_once_with(0, 0)

    def test_offset_screen(self):
        """Positions window on secondary screen."""
        w = _make_window()
        w.switch_to = MagicMock()
        w.set_location = MagicMock()
        mock_screen = MagicMock()
        mock_screen.x = 1920
        mock_screen.y = 0
        mock_screen.width = 1920
        mock_screen.height = 1080
        w.set_size_and_location(mock_screen)
        # target_x = (1920 + 960) - 960 = 1920
        w.set_location.assert_called_once_with(1920, 0)


class TestVisibilityChange:
    """In the browser, hiding the page pauses the scenario."""

    def test_hidden_opens_pause_prompt(self):
        w = _make_window(modal_dialog=None)
        w.pause_prompt = MagicMock()
        with patch("core.window.get_logger"):
            w.on_visibility_change(True)
        w.pause_prompt.assert_called_once()

    def test_visible_does_not_pause(self):
        w = _make_window(modal_dialog=None)
        w.pause_prompt = MagicMock()
        with patch("core.window.get_logger"):
            w.on_visibility_change(False)
        w.pause_prompt.assert_not_called()

    def test_no_pause_over_selector_or_dialog(self):
        w = _make_window(modal_dialog=MagicMock())
        w.pause_prompt = MagicMock()
        with patch("core.window.get_logger"):
            w.on_visibility_change(True)
            w.modal_dialog = None
            w.selector_visible = True
            w.on_visibility_change(True)
        w.pause_prompt.assert_not_called()

    def test_visibility_is_logged(self):
        w = _make_window(modal_dialog=None)
        w.pause_prompt = MagicMock()
        with patch("core.window.get_logger") as get_logger:
            w.on_visibility_change(True)
        get_logger.return_value.log_manual_entry.assert_called_once_with("hidden", key="visibility")


class TestSnapTextToPixels:
    """Text positions are rounded so that glyphs are not drawn between two pixels (jagged text)."""

    def _fake_layout_class(self):
        class FakeLayout:
            def __init__(self, x=0, y=0, z=0):
                self._x, self._y, self._z = x, y, z
                self.translations = []

            def _update_translation(self):
                self.translations.append((self._x, self._y, self._z))

            def _set_x(self, x):
                self._x = x
                self._update_translation()

            def _set_y(self, y):
                self._y = y
                self._update_translation()

            def _set_position(self, position):
                self._x, self._y, self._z = position
                self._update_translation()

        return FakeLayout

    def test_positions_are_rounded(self):
        import core.window as window_module

        layout_class = self._fake_layout_class()
        with patch.object(window_module, "TextLayout", layout_class):
            window_module._snap_text_to_pixels()
            layout = layout_class(x=464.5, y=458.4)
            assert (layout._x, layout._y) == (464, 458)
            assert layout.translations[-1][:2] == (464, 458)

            layout._set_x(10.6)
            layout._set_y(20.2)
            assert (layout._x, layout._y) == (11, 20)

            layout._set_position((1.4, 2.6, 3))
            assert (layout._x, layout._y, layout._z) == (1, 3, 3)

    def test_patch_is_applied_once(self):
        import core.window as window_module

        layout_class = self._fake_layout_class()
        with patch.object(window_module, "TextLayout", layout_class):
            window_module._snap_text_to_pixels()
            init = layout_class.__init__
            window_module._snap_text_to_pixels()
            assert layout_class.__init__ is init
