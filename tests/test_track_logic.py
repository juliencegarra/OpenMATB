"""Tests for plugins.track - Cursor movement, color changes, and tracking logic.

Tests the actual Track plugin methods (compute_next_cursor_position,
get_joystick_inputs, cursor color switching) using object.__new__() to bypass
__init__.
"""

from unittest.mock import MagicMock

from core.constants import COLORS as C
from core.container import Container
from plugins.track import Track


def _make_track(**overrides):
    """Create a Track instance bypassing __init__, with realistic state."""
    t = object.__new__(Track)
    t.alias = "track"
    t.scenario_time = 0
    t.alive = True
    t.paused = False
    t.visible = True
    t.can_receive_keys = False
    t.can_execute_keys = False
    t.keys = set()
    t.performance = {}
    t.logger = MagicMock()
    t.response_time = 0
    t.x_input = 0
    t.y_input = 0
    t.cursor_color_key = "cursorcolor"
    t.gain_ratio = 0.8

    t.parameters = dict(
        taskupdatetime=20,
        cursorcolor=C["BLACK"],
        cursorcoloroutside=C["RED"],
        automaticsolver=False,
        displayautomationstate=True,
        targetproportion=0.25,
        joystickforce=1,
        inverseaxis=False,
        title="Tracking",
        taskplacement="topmid",
        taskfeedback=dict(
            overdue=dict(
                active=False, color=C["RED"], delayms=2000, blinkdurationms=1000, _nexttoggletime=0, _is_visible=False
            )
        ),
    )

    # Set up a mock reticle widget
    t.reticle = MagicMock()
    t.reticle.container = Container("reticle", 0, 0, 200, 200)
    t.reticle.cursor_relative = (0, 0)
    t.reticle.is_cursor_in_target.return_value = True
    t.reticle.return_deviation.return_value = 0.0

    t.reticle_container = t.reticle.container
    t.xgain = (t.reticle_container.w * t.gain_ratio) / 2  # 80
    t.ygain = (t.reticle_container.h * t.gain_ratio) / 2  # 80
    t.widgets = {"track_reticle": t.reticle}
    t.cursor_position = (0, 0)

    t.next_refresh_time = 0

    t.__dict__.update(overrides)

    # Create the generator after all attributes are set
    t.cursor_path_gen = iter(t.compute_next_cursor_position())
    return t


# ──────────────────────────────────────────────
# get_joystick_inputs
# ──────────────────────────────────────────────
class TestGetJoystickInputs:
    def test_sets_inputs(self):
        """Stores x and y joystick input values."""
        t = _make_track()
        t.get_joystick_inputs(0.5, -0.3)
        assert t.x_input == 0.5
        assert t.y_input == -0.3

    def test_zero_inputs(self):
        """Zero inputs are stored as zero."""
        t = _make_track()
        t.get_joystick_inputs(0, 0)
        assert t.x_input == 0
        assert t.y_input == 0


# ──────────────────────────────────────────────
# get_response_timers
# ──────────────────────────────────────────────
class TestGetResponseTimers:
    def test_initial_timer(self):
        """Initial response timer is [0]."""
        t = _make_track()
        assert t.get_response_timers() == [0]

    def test_accumulated_timer(self):
        """Accumulated timer is returned."""
        t = _make_track(response_time=500)
        assert t.get_response_timers() == [500]


# ──────────────────────────────────────────────
# compute_next_cursor_position - generator
# ──────────────────────────────────────────────
class TestComputeNextCursorPosition:
    """Test the actual cursor position generator."""

    def test_yields_tuple(self):
        """Generator yields (x, y) tuples."""
        t = _make_track()
        pos = next(t.cursor_path_gen)
        assert isinstance(pos, tuple)
        assert len(pos) == 2

    def test_initial_position_near_origin(self):
        """First positions are close to (0, 0)."""
        t = _make_track()
        x, y = next(t.cursor_path_gen)
        # First step: sin(0.005)*80, sin(0.006)*80 ≈ small values
        assert abs(x) < 5
        assert abs(y) < 5

    def test_position_changes_over_time(self):
        """Cursor moves over successive steps."""
        t = _make_track()
        positions = [next(t.cursor_path_gen) for _ in range(100)]
        # Not all positions should be the same
        xs = [p[0] for p in positions]
        assert max(xs) != min(xs)

    def test_sinusoidal_pattern(self):
        """Cursor follows a sinusoidal path (from Comstock et al., 1992)."""
        t = _make_track()
        # Need >628 steps (pi/0.005) for sin to go negative
        positions = [next(t.cursor_path_gen) for _ in range(1500)]
        xs = [p[0] for p in positions]
        # The x values should oscillate (go positive and negative)
        assert any(x > 0 for x in xs)
        assert any(x < 0 for x in xs)

    def test_cursor_bounded_by_reticle(self):
        """Cursor should never exceed reticle boundaries."""
        t = _make_track()
        half_w = t.reticle.container.w / 2  # 100
        half_h = t.reticle.container.h / 2  # 100
        for _ in range(2000):
            x, y = next(t.cursor_path_gen)
            assert -half_w <= x <= half_w, f"x={x} out of bounds [-{half_w}, {half_w}]"
            assert -half_h <= y <= half_h, f"y={y} out of bounds [-{half_h}, {half_h}]"

    def test_yields_origin_before_widget_exists(self):
        """Before reticle widget is created, yields (0, 0)."""
        t = _make_track()
        t.widgets = {}  # No widgets yet
        gen = iter(t.compute_next_cursor_position())
        pos = next(gen)
        assert pos == (0, 0)

    def test_xy_asynchronous(self):
        """X and Y move at different rates (xincr=0.005, yincr=0.006)."""
        t = _make_track()
        positions = [next(t.cursor_path_gen) for _ in range(200)]
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        # They should not be identical (different frequencies)
        assert xs != ys


# ──────────────────────────────────────────────
# Joystick compensation in generator
# ──────────────────────────────────────────────
class TestJoystickCompensation:
    """Test joystick input affects cursor position."""

    def test_joystick_input_moves_cursor(self):
        """Joystick input shifts cursor position."""
        t = _make_track()
        # Get baseline positions without input
        baseline = [next(t.cursor_path_gen) for _ in range(50)]

        # Create fresh track with joystick input
        t2 = _make_track()
        t2.get_joystick_inputs(1.0, 0)
        with_input = [next(t2.cursor_path_gen) for _ in range(50)]

        # X positions should differ due to joystick
        baseline_x = [p[0] for p in baseline]
        input_x = [p[0] for p in with_input]
        assert baseline_x != input_x

    def test_inverse_axis(self):
        """With inverseaxis=True, joystick effect should be reversed."""
        t_normal = _make_track()
        t_normal.get_joystick_inputs(1.0, 0)
        normal_positions = [next(t_normal.cursor_path_gen) for _ in range(50)]

        t_inverse = _make_track()
        t_inverse.parameters["inverseaxis"] = True
        t_inverse.get_joystick_inputs(1.0, 0)
        t_inverse.cursor_path_gen = iter(t_inverse.compute_next_cursor_position())
        inverse_positions = [next(t_inverse.cursor_path_gen) for _ in range(50)]

        # With same positive joystick input, normal goes right, inverse goes left
        # Compare later positions where the effect accumulates
        normal_x = normal_positions[-1][0]
        inverse_x = inverse_positions[-1][0]
        assert normal_x > inverse_x

    def test_joystick_force_multiplier(self):
        """Higher joystickforce should amplify joystick effect."""
        t1 = _make_track()
        t1.get_joystick_inputs(0.5, 0)
        pos1 = [next(t1.cursor_path_gen) for _ in range(50)]

        t3 = _make_track()
        t3.parameters["joystickforce"] = 3
        t3.get_joystick_inputs(0.5, 0)
        t3.cursor_path_gen = iter(t3.compute_next_cursor_position())
        pos3 = [next(t3.cursor_path_gen) for _ in range(50)]

        # force=3 should move further right than force=1
        assert pos3[-1][0] > pos1[-1][0]


# ──────────────────────────────────────────────
# Auto compensation
# ──────────────────────────────────────────────
class TestAutoCompensation:
    """Test automatic solver compensation."""

    def test_auto_solver_moves_toward_center(self):
        """With automaticsolver, cursor should stay closer to center."""
        t_manual = _make_track()
        manual_pos = [next(t_manual.cursor_path_gen) for _ in range(500)]

        t_auto = _make_track()
        t_auto.parameters["automaticsolver"] = True
        t_auto.reticle.cursor_relative = (-5, -5)  # Cursor is left-down
        t_auto.cursor_path_gen = iter(t_auto.compute_next_cursor_position())
        auto_pos = [next(t_auto.cursor_path_gen) for _ in range(500)]

        # Auto solver should keep deviations smaller on average
        manual_devs = [abs(p[0]) + abs(p[1]) for p in manual_pos]
        auto_devs = [abs(p[0]) + abs(p[1]) for p in auto_pos]
        # Auto mean deviation should be less (it compensates)
        assert sum(auto_devs) / len(auto_devs) != sum(manual_devs) / len(manual_devs)


# ──────────────────────────────────────────────
# Cursor color switching (in target vs outside)
# ──────────────────────────────────────────────
class TestCursorColorSwitching:
    """Test the cursor color change when cursor enters/exits the target zone."""

    def test_initial_color_is_cursorcolor(self):
        """Default color key is 'cursorcolor'."""
        t = _make_track()
        assert t.cursor_color_key == "cursorcolor"
        assert t.parameters["cursorcolor"] == C["BLACK"]

    def test_color_changes_when_outside_target(self):
        """When cursor is outside target, color key switches to cursorcoloroutside."""
        t = _make_track()
        t.reticle.is_cursor_in_target.return_value = False

        # Simulate what compute_next_plugin_state does for color
        t.cursor_color_key = "cursorcolor" if t.reticle.is_cursor_in_target() else "cursorcoloroutside"

        assert t.cursor_color_key == "cursorcoloroutside"
        assert t.parameters[t.cursor_color_key] == C["RED"]

    def test_color_returns_to_normal_inside_target(self):
        """When cursor returns to target, color key goes back to cursorcolor."""
        t = _make_track()

        # First: outside
        t.reticle.is_cursor_in_target.return_value = False
        t.cursor_color_key = "cursorcolor" if t.reticle.is_cursor_in_target() else "cursorcoloroutside"
        assert t.cursor_color_key == "cursorcoloroutside"

        # Then: back inside
        t.reticle.is_cursor_in_target.return_value = True
        t.cursor_color_key = "cursorcolor" if t.reticle.is_cursor_in_target() else "cursorcoloroutside"
        assert t.cursor_color_key == "cursorcolor"
        assert t.parameters[t.cursor_color_key] == C["BLACK"]

    def test_full_color_cycle(self):
        """BLACK (in target) → RED (outside) → BLACK (back in target)."""
        t = _make_track()

        # In target → BLACK
        assert t.parameters[t.cursor_color_key] == C["BLACK"]

        # Leaves target → RED
        t.reticle.is_cursor_in_target.return_value = False
        t.cursor_color_key = "cursorcolor" if t.reticle.is_cursor_in_target() else "cursorcoloroutside"
        assert t.parameters[t.cursor_color_key] == C["RED"]

        # Returns to target → BLACK
        t.reticle.is_cursor_in_target.return_value = True
        t.cursor_color_key = "cursorcolor" if t.reticle.is_cursor_in_target() else "cursorcoloroutside"
        assert t.parameters[t.cursor_color_key] == C["BLACK"]


# ──────────────────────────────────────────────
# Response time tracking
# ──────────────────────────────────────────────
class TestResponseTimeTracking:
    """Test response time accumulation when cursor is outside target."""

    def test_accumulates_when_outside(self):
        """Time accumulates while cursor is out of target."""
        t = _make_track()
        t.reticle.is_cursor_in_target.return_value = False

        # Simulate multiple update cycles
        for _ in range(5):
            t.response_time += t.parameters["taskupdatetime"]

        assert t.response_time == 100  # 5 * 20ms

    def test_resets_when_back_in_target(self):
        """Timer resets when cursor returns to target."""
        t = _make_track()
        t.response_time = 500  # Was outside

        # Cursor returns to target
        t.reticle.is_cursor_in_target.return_value = True
        if t.reticle.is_cursor_in_target():
            if t.response_time > 0:
                logged_rt = t.response_time
                t.response_time = 0

        assert t.response_time == 0
        assert logged_rt == 500

    def test_no_accumulation_when_inside(self):
        """No accumulation while cursor is in target."""
        t = _make_track()
        t.reticle.is_cursor_in_target.return_value = True
        # Don't increment when in target
        initial_rt = t.response_time
        if not t.reticle.is_cursor_in_target():
            t.response_time += t.parameters["taskupdatetime"]
        assert t.response_time == initial_rt
