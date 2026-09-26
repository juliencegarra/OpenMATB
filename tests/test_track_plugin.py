"""Tests for plugins.track - the plugin built by its constructor (widgets, cursor, performance, mouse drag)."""

from math import sin
from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import mouse

from core.constants import COLORS as C
from core.container import Container
from plugins.abstractplugin import AbstractPlugin
from plugins.track import Track


def _fake_reticle(fullname, container, **kwargs):
    """Reticle stand-in keeping its real container and its creation arguments."""
    reticle = MagicMock(container=container, kwargs=kwargs)
    reticle.is_cursor_in_target.return_value = True
    reticle.return_deviation.return_value = 0.0
    return reticle


def _create_widgets(track):
    def base_create_widgets(plugin):
        plugin.task_container = Container("task", 0, 0, 400, 300)

    with (
        patch.object(AbstractPlugin, "create_widgets", base_create_widgets),
        patch("plugins.track.Reticle", side_effect=_fake_reticle) as mock_reticle,
    ):
        track.create_widgets()
    return mock_reticle


@pytest.fixture
def track(mock_logger):
    """A running Track plugin with a mock reticle (task area 400x300 at the origin)."""
    t = Track()
    t.paused = False
    t.visible = True
    t.can_execute_keys = True
    t.scenario_time = 1
    t.joystick = None
    _create_widgets(t)
    return t


@pytest.fixture
def no_modal_dialog():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        yield mock_win


def _step(track, in_target, deviation=0.0):
    """Run one update step with the cursor in (or out of) the target."""
    track.reticle.is_cursor_in_target.return_value = in_target
    track.reticle.return_deviation.return_value = deviation
    track.compute_next_plugin_state()
    track.scenario_time += track.parameters["taskupdatetime"] / 1000


class TestInit:
    def test_default_parameters(self, mock_logger):
        t = Track()
        p = t.parameters
        assert p["title"] == "Tracking"
        assert p["taskplacement"] == "topmid"
        assert p["taskupdatetime"] == 20
        assert p["cursorcolor"] == C["BLACK"]
        assert p["cursorcoloroutside"] == C["RED"]
        assert p["automaticsolver"] is False
        assert p["targetproportion"] == 0.25
        assert p["joystickforce"] == 1
        assert p["inverseaxis"] is False

    def test_every_parameter_has_a_validator(self, mock_logger):
        t = Track()
        for name in ("automaticsolver", "cursorcolor", "targetproportion", "joystickforce", "inverseaxis"):
            assert callable(t.validation_dict[name])

    def test_initial_state_is_idle(self, mock_logger):
        t = Track()
        assert t.cursor_position is None
        assert t.cursor_color_key == "cursorcolor"
        assert (t.x_input, t.y_input) == (0, 0)
        assert t.has_active_fault() is False
        assert t.get_response_timers() == [0.0]

    def test_cursor_stays_at_origin_before_the_reticle_exists(self, mock_logger):
        t = Track()
        assert next(t.cursor_path_gen) == (0, 0)


class TestCreateWidgets:
    def test_reticle_is_a_centered_square_in_the_task_area(self, mock_logger):
        t = Track()
        mock_reticle = _create_widgets(t)
        fullname, container = mock_reticle.call_args.args
        assert fullname == "track_reticle"
        # 80% of the 300 px height, centered horizontally in the 400 px width
        assert (container.l, container.b, container.w, container.h) == (80, 30, 240, 240)
        assert t.reticle is t.widgets["track_reticle"]
        assert t.reticle_container is container

    def test_reticle_receives_target_and_cursor_parameters(self, mock_logger):
        t = Track()
        t.parameters["targetproportion"] = 0.4
        mock_reticle = _create_widgets(t)
        kwargs = mock_reticle.call_args.kwargs
        assert kwargs == {"target_proportion": 0.4, "cursorcolor": C["BLACK"]}

    def test_gains_cover_80_percent_of_the_reticle(self, track):
        assert track.xgain == pytest.approx(96)
        assert track.ygain == pytest.approx(96)

    def test_first_cursor_position_follows_the_sinusoid(self, track):
        x, y = track.cursor_position
        assert x == pytest.approx(sin(0.005) * 96)
        assert y == pytest.approx(sin(0.006) * 96)

    def test_reticle_area_is_recorded(self, track, mock_logger):
        mock_logger.record_aoi.assert_any_call(track.reticle_container, "track_reticle")


class TestJoystickInputs:
    def test_joystick_is_ignored_while_the_mouse_drags(self, track):
        track._mouse_dragging = True
        track.x_input, track.y_input = 0.5, -0.5
        track.get_joystick_inputs(1.0, 1.0)
        assert (track.x_input, track.y_input) == (0.5, -0.5)


class TestComputeNextPluginState:
    def test_cursor_moves_along_its_path(self, track):
        first = track.cursor_position
        _step(track, in_target=True)
        second = track.cursor_position
        assert second != first
        assert second[0] == pytest.approx(sin(0.010) * 96)
        assert second[1] == pytest.approx(sin(0.012) * 96)

    def test_no_update_while_paused(self, track):
        track.paused = True
        position = track.cursor_position
        _step(track, in_target=False)
        assert track.cursor_position == position
        assert not hasattr(track, "performance")
        assert track.has_active_fault() is False

    def test_cursor_is_not_computed_in_replay_mode(self, track):
        position = track.cursor_position
        with patch("plugins.track.REPLAY_MODE", True):
            _step(track, in_target=True)
        assert track.cursor_position == position
        assert track.performance["cursor_in_target"] == [True]

    def test_performance_is_logged_at_each_step(self, track, mock_logger):
        _step(track, in_target=True, deviation=3.5)
        _step(track, in_target=False, deviation=42.0)
        assert track.performance["cursor_in_target"] == [True, False]
        assert track.performance["center_deviation"] == [3.5, 42.0]
        mock_logger.log_performance.assert_any_call("track", "center_deviation", 42.0)

    def test_cursor_turns_red_outside_the_target(self, track):
        _step(track, in_target=False)
        assert track.cursor_color_key == "cursorcoloroutside"
        _step(track, in_target=True)
        assert track.cursor_color_key == "cursorcolor"

    def test_leaving_the_target_starts_a_response_timer(self, track):
        track.scenario_time = 10
        _step(track, in_target=False)
        assert track.has_active_fault() is True
        assert track._response_start == 10
        # The timer keeps its start while the cursor stays out
        _step(track, in_target=False)
        assert track._response_start == 10
        assert track.get_response_timers() == [pytest.approx(40)]

    def test_response_time_is_logged_when_the_cursor_is_recovered(self, track):
        track.scenario_time = 10
        _step(track, in_target=False)  # t = 10.00
        _step(track, in_target=False)  # t = 10.02
        _step(track, in_target=False)  # t = 10.04
        _step(track, in_target=True)  # t = 10.06
        assert track.performance["response_time"] == [pytest.approx(60)]
        assert track.has_active_fault() is False

    def test_no_response_time_while_the_cursor_stays_in(self, track):
        _step(track, in_target=True)
        _step(track, in_target=True)
        assert "response_time" not in track.performance

    def test_stale_inputs_are_reset_when_the_solver_is_on_without_agent(self, track):
        track.parameters["automaticsolver"] = True
        track.x_input, track.y_input = 2, -2
        _step(track, in_target=True)
        assert (track.x_input, track.y_input) == (0, 0)

    def test_cooperative_agent_keeps_human_inputs(self, track):
        track.parameters["automaticsolver"] = True
        track.agent = MagicMock(allows_human_input=True)
        track.agent.get_automode_string.return_value = "ASSISTED"
        track.x_input, track.y_input = 2, -2
        _step(track, in_target=True)
        assert (track.x_input, track.y_input) == (2, -2)
        assert track.automode_string == "ASSISTED"

    def test_joystick_input_offsets_the_cursor(self, track):
        track.get_joystick_inputs(5, 0)
        _step(track, in_target=True)
        assert track.cursor_position[0] == pytest.approx(sin(0.010) * 96 + 5)


class TestReticleLimits:
    """The reticle is 240 px wide: the cursor must stay within +/-120 px of its center."""

    def _run(self, track, steps):
        return [next(track.cursor_path_gen) for _ in range(steps)]

    def test_inverse_axis_mirrors_the_joystick(self, track):
        track.parameters["inverseaxis"] = True
        track.get_joystick_inputs(5, 5)
        x, y = next(track.cursor_path_gen)
        assert x == pytest.approx(sin(0.010) * 96 - 5)
        assert y == pytest.approx(sin(0.012) * 96 + 5)

    def test_holding_the_stick_right_keeps_the_cursor_on_the_edge(self, track):
        track.get_joystick_inputs(1, 0)
        positions = self._run(track, 300)
        assert max(x for x, _ in positions) == pytest.approx(120)
        assert all(x == pytest.approx(120, abs=1) for x, _ in positions[-50:])

    def test_holding_the_stick_forward_keeps_the_cursor_on_the_bottom_edge(self, track):
        # Joystick convention: pushing forward (positive y) moves the cursor down
        track.get_joystick_inputs(0, 1)
        positions = self._run(track, 300)
        assert min(y for _, y in positions) == pytest.approx(-120)
        assert all(y == pytest.approx(-120, abs=1) for _, y in positions[-50:])

    def test_cursor_leaves_the_edge_as_soon_as_the_stick_is_reversed(self, track):
        track.get_joystick_inputs(-1, 1)
        assert self._run(track, 300)[-1] == (-120, -120)
        track.get_joystick_inputs(1, -1)
        x, y = next(track.cursor_path_gen)
        assert -120 < x < -110
        assert -120 < y < -110

    @pytest.mark.parametrize(
        "inverseaxis, inputs, edge",
        [
            (False, (1, 0), (120, None)),
            (False, (-1, 0), (-120, None)),
            (False, (0, 1), (None, -120)),
            (False, (0, -1), (None, 120)),
            (True, (-1, 0), (120, None)),
            (True, (0, -1), (None, -120)),
        ],
    )
    def test_strong_joystick_rests_on_the_edge_without_sawtooth(self, track, inverseaxis, inputs, edge):
        """With joystickforce > 1, the cursor rests on the edge instead of bouncing back inside."""
        track.parameters["joystickforce"] = 10
        track.parameters["inverseaxis"] = inverseaxis
        track.get_joystick_inputs(*inputs)
        positions = self._run(track, 300)
        axis = 0 if edge[0] is not None else 1
        tail = [p[axis] for p in positions[-100:]]
        assert all(v == pytest.approx(edge[axis], abs=1) for v in tail)

    def test_large_input_does_not_overshoot_to_the_opposite_edge(self, track):
        """Once on the edge, a strong push never throws the cursor to the other side."""
        track.parameters["joystickforce"] = 10
        track.get_joystick_inputs(5, -5)
        positions = self._run(track, 100)
        first_on_edge = next(i for i, (x, _) in enumerate(positions) if x == pytest.approx(120))
        assert all(x == pytest.approx(120) for x, _ in positions[first_on_edge:])
        assert all(y == pytest.approx(120) for _, y in positions[first_on_edge:])

    def test_strong_joystick_leaves_the_edge_as_soon_as_reversed(self, track):
        """With joystickforce > 1, reversing the stick moves the cursor off the edge at once."""
        track.parameters["joystickforce"] = 10
        track.get_joystick_inputs(1, -1)
        assert self._run(track, 300)[-1] == pytest.approx((120, 120), abs=1)
        track.get_joystick_inputs(-1, 1)
        x, y = next(track.cursor_path_gen)
        assert 100 < x < 120
        assert 100 < y < 120

    def test_cursor_never_leaves_the_reticle(self, track):
        track.parameters["joystickforce"] = 3
        for inputs in [(2, -2)] * 100 + [(-2, 2)] * 200 + [(0, 0)] * 50:
            track.get_joystick_inputs(*inputs)
            x, y = next(track.cursor_path_gen)
            assert -120 <= x <= 120
            assert -120 <= y <= 120


class TestRefreshWidgets:
    def test_reticle_shows_cursor_position_color_and_target(self, track):
        track.cursor_position = (12.0, -7.0)
        track.cursor_color_key = "cursorcoloroutside"
        track.parameters["targetproportion"] = 0.3
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            track.refresh_widgets()
        track.reticle.set_cursor_position.assert_called_once_with(12.0, -7.0)
        track.reticle.set_cursor_color.assert_called_once_with(C["RED"])
        track.reticle.set_target_proportion.assert_called_once_with(0.3)

    def test_nothing_is_drawn_when_hidden(self, track):
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=False):
            track.refresh_widgets()
        track.reticle.set_cursor_position.assert_not_called()
        track.reticle.set_cursor_color.assert_not_called()


class TestMouseDrag:
    """The reticle spans x 80..320 and y 30..270 (center 200, 150)."""

    def test_left_press_in_the_reticle_starts_a_drag(self, track):
        track.x_input, track.y_input = 1, 1
        track.do_on_mouse_press(150, 100, mouse.LEFT)
        assert track._mouse_dragging is True
        assert (track._drag_origin_x, track._drag_origin_y) == (150, 100)
        assert (track.x_input, track.y_input) == (0, 0)

    def test_press_outside_the_reticle_is_ignored(self, track):
        track.do_on_mouse_press(10, 10, mouse.LEFT)
        assert track._mouse_dragging is False

    def test_other_buttons_are_ignored(self, track):
        track.do_on_mouse_press(150, 100, mouse.RIGHT)
        assert track._mouse_dragging is False

    def test_drag_pushes_the_cursor_like_a_joystick(self, track):
        track.do_on_mouse_press(200, 150, mouse.LEFT)
        # 60 px right (half width 120 -> 0.5) and 24 px up (half height 120 -> 0.2)
        track.do_on_mouse_drag(260, 174, 60, 24, mouse.LEFT)
        assert track.x_input == pytest.approx(1.5)
        assert track.y_input == pytest.approx(-0.6)

    def test_drag_force_is_capped(self, track):
        track.do_on_mouse_press(200, 150, mouse.LEFT)
        track.do_on_mouse_drag(1000, -1000, 800, -1150, mouse.LEFT)
        assert (track.x_input, track.y_input) == (3.0, 3.0)

    def test_dragged_mouse_moves_the_cursor_in_the_drag_direction(self, track):
        track.do_on_mouse_press(200, 150, mouse.LEFT)
        track.do_on_mouse_drag(320, 270, 120, 120, mouse.LEFT)
        before = track.cursor_position
        _step(track, in_target=True)
        after = track.cursor_position
        # Sinusoid step is < 1 px: the 3 px mouse force dominates, right and up
        assert after[0] - before[0] > 2
        assert after[1] - before[1] > 2

    def test_drag_without_press_does_nothing(self, track):
        track.do_on_mouse_drag(300, 200, 10, 10, mouse.LEFT)
        assert (track.x_input, track.y_input) == (0, 0)

    def test_release_ends_the_drag_and_the_force(self, track):
        track.do_on_mouse_press(200, 150, mouse.LEFT)
        track.do_on_mouse_drag(260, 150, 60, 0, mouse.LEFT)
        track.do_on_mouse_release(260, 150, mouse.LEFT)
        assert track._mouse_dragging is False
        assert (track.x_input, track.y_input) == (0, 0)

    def test_release_without_drag_keeps_joystick_inputs(self, track):
        track.get_joystick_inputs(0.7, 0.2)
        track.do_on_mouse_release(200, 150, mouse.LEFT)
        assert (track.x_input, track.y_input) == (0.7, 0.2)

    def test_joystick_takes_over_after_release(self, track):
        track.do_on_mouse_press(200, 150, mouse.LEFT)
        track.get_joystick_inputs(1.0, 1.0)
        assert (track.x_input, track.y_input) == (0, 0)
        track.do_on_mouse_release(200, 150, mouse.LEFT)
        track.get_joystick_inputs(1.0, 1.0)
        assert (track.x_input, track.y_input) == (1.0, 1.0)

    def test_window_mouse_events_reach_the_drag(self, track, no_modal_dialog):
        track.update_can_receive_mouse()
        assert track.can_receive_mouse is True
        track.on_mouse_press(200, 150, mouse.LEFT, 0)
        track.on_mouse_drag(320, 150, 120, 0, mouse.LEFT, 0)
        assert track.x_input == pytest.approx(3.0)
        track.on_mouse_release(320, 150, mouse.LEFT, 0)
        assert track._mouse_dragging is False

    def test_mouse_is_disabled_under_automatic_solver(self, track, no_modal_dialog):
        track.parameters["automaticsolver"] = True
        track.update_can_receive_mouse()
        track.on_mouse_press(200, 150, mouse.LEFT, 0)
        assert track._mouse_dragging is False
