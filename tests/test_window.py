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
    w.mouse_control_active = False
    w.on_key_press_replay = None
    w.__dict__.update(overrides)
    return w


class TestGetContainerList:
    """Test container layout generation from screen dimensions."""

    @patch("core.window.REPLAY_MODE", False)
    @patch("core.window.get_conf_value")
    def test_returns_11_containers(self, mock_conf):
        """Layout produces 11 named containers."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        assert len(containers) == 11

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
        assert "perfstrip" in names

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
    @patch("core.window.REPLAY_PERF_STRIP_PROPORTION", 0.08)
    @patch("core.window.get_conf_value")
    def test_replay_mode_reduces_area(self, mock_conf):
        """Replay mode shrinks containers by strip + perf strip proportions."""
        mock_conf.side_effect = lambda section, key: {
            "top_bounds": [0.35, 0.85],
            "bottom_bounds": [0.30, 0.85],
        }[key]
        w = _make_window()
        containers = w.get_container_list()
        fs = [c for c in containers if c.name == "fullscreen"][0]
        # In replay mode, mar=0.08, perf_mar=0.08, so w = 0.92*1920, h = 0.84*1080
        assert fs.w == pytest.approx(0.92 * 1920)
        assert fs.h == pytest.approx(0.84 * 1080)
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
        mock_get_logger.return_value.record_input.assert_called_once_with("mouse", "click", "press;512;384;1")

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
        mock_get_logger.return_value.record_input.assert_called_once_with("mouse", "click", "release;512;384;1")


class TestOpenModalWindow:
    @patch("core.window.ModalDialog")
    def test_passes_exit_key(self, MockDialog):
        """exit_key parameter is forwarded to ModalDialog."""
        w = _make_window()
        w.open_modal_window(["msg"], title="T", continue_key="SPACE", exit_key="X")
        MockDialog.assert_called_once_with(w, ["msg"], title="T", continue_key="SPACE", exit_key="X")

    @patch("core.window.ModalDialog")
    def test_default_q_key(self, MockDialog):
        """Caller passing Q works as before."""
        w = _make_window()
        w.open_modal_window(["msg"], title="T", continue_key=None, exit_key="Q")
        MockDialog.assert_called_once_with(w, ["msg"], title="T", continue_key=None, exit_key="Q")


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
