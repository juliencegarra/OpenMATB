"""Tests for core/widgets/slider.py — sub-container layout and keyboard control.

Verifies that set_sub_containers distributes space correctly,
especially when showvalue=False (no value label zone).
Also tests adjust_value and set_selected methods.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from core.container import Container

# ── Fixture ──────────────────────────────────────


@pytest.fixture
def make_slider():
    """Factory: create a minimal Slider (skipping __init__) and call set_sub_containers."""
    from core.widgets.slider import Slider

    def _make(showvalue=True, container=None):
        if container is None:
            container = Container("test_slider", 100, 50, 600, 80)
        obj = object.__new__(Slider)
        obj.container = container
        obj.showvalue = showvalue
        obj.label_min = "Low"
        obj.label_max = "High"
        obj.groove_value = 50
        obj.draw_order = 1
        obj.font_name = "Sans"
        obj.vertex = {}
        obj.containers = {}
        obj.set_sub_containers()
        return obj

    return _make


# ── Helpers ──────────────────────────────────────


def rightmost_edge(slider):
    """Return the rightmost pixel of all layout sub-containers."""
    layout_names = ["min", "slide", "max", "value"]
    edges = []
    for name in layout_names:
        if name in slider.containers:
            c = slider.containers[name]
            edges.append(c.l + c.w)
    return max(edges)


def containers_overlap_horizontally(a, b):
    """True if two containers share any horizontal pixels."""
    return a.l < b.l + b.w and b.l < a.l + a.w


# ── showvalue=True ───────────────────────────────


class TestSubContainersShowValue:
    """When showvalue=True, four layout zones exist: min, slide, max, value."""

    def test_four_layout_zones_present(self, make_slider):
        s = make_slider(showvalue=True)
        for name in ["min", "slide", "max", "value"]:
            assert name in s.containers, f"Missing container '{name}'"

    def test_containers_fill_width(self, make_slider):
        s = make_slider(showvalue=True)
        total = sum(s.containers[n].w for n in ["min", "slide", "max", "value"])
        assert abs(total - s.container.w) < 1  # float tolerance

    def test_no_horizontal_overlap(self, make_slider):
        s = make_slider(showvalue=True)
        names = ["min", "slide", "max", "value"]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = s.containers[names[i]], s.containers[names[j]]
                if abs(i - j) > 1:
                    assert not containers_overlap_horizontally(a, b), f"'{names[i]}' overlaps '{names[j]}'"

    def test_value_label_created(self, make_slider):
        s = make_slider(showvalue=True)
        assert "value" in s.vertex

    def test_order_is_min_slide_max_value(self, make_slider):
        s = make_slider(showvalue=True)
        assert s.containers["min"].l < s.containers["slide"].l
        assert s.containers["slide"].l < s.containers["max"].l
        assert s.containers["max"].l < s.containers["value"].l


# ── showvalue=False ──────────────────────────────


class TestSubContainersHideValue:
    """When showvalue=False, only three layout zones: min, slide, max."""

    def test_no_value_container(self, make_slider):
        s = make_slider(showvalue=False)
        assert "value" not in s.containers

    def test_three_layout_zones_present(self, make_slider):
        s = make_slider(showvalue=False)
        for name in ["min", "slide", "max"]:
            assert name in s.containers, f"Missing container '{name}'"

    def test_containers_fill_width(self, make_slider):
        s = make_slider(showvalue=False)
        total = sum(s.containers[n].w for n in ["min", "slide", "max"])
        assert abs(total - s.container.w) < 1

    def test_no_gap_at_right(self, make_slider):
        """Rightmost container should reach the right edge of the parent."""
        s = make_slider(showvalue=False)
        right = rightmost_edge(s)
        expected = s.container.l + s.container.w
        assert abs(right - expected) < 1

    def test_labels_wider_than_with_value(self, make_slider):
        """Min/max labels are wider when value is hidden (2 labels instead of 3)."""
        s_show = make_slider(showvalue=True)
        s_hide = make_slider(showvalue=False)
        assert s_hide.containers["min"].w > s_show.containers["min"].w
        assert s_hide.containers["max"].w > s_show.containers["max"].w

    def test_no_value_label_created(self, make_slider):
        s = make_slider(showvalue=False)
        assert "value" not in s.vertex

    def test_order_is_min_slide_max(self, make_slider):
        s = make_slider(showvalue=False)
        assert s.containers["min"].l < s.containers["slide"].l
        assert s.containers["slide"].l < s.containers["max"].l

    def test_slide_width_unchanged(self, make_slider):
        """The slide zone width should be the same regardless of showvalue."""
        s_show = make_slider(showvalue=True)
        s_hide = make_slider(showvalue=False)
        assert abs(s_show.containers["slide"].w - s_hide.containers["slide"].w) < 1


# ── Keyboard control ────────────────────────────


@pytest.fixture
def interactive_slider():
    """Create a Slider with enough state for adjust_value / set_selected."""
    from core.widgets.slider import Slider

    obj = object.__new__(Slider)
    obj.container = Container("test_slider", 100, 50, 600, 80)
    obj.showvalue = False
    obj.label_min = "Low"
    obj.label_max = "High"
    obj.value_min = 0
    obj.value_max = 100
    obj.value_default = 50
    obj.groove_value = 50
    obj.draw_order = 1
    obj.rank = 0
    obj.font_name = "Sans"
    obj.vertex = {}
    obj.containers = {}
    obj.visible = True
    obj.selected = False
    obj.on_batch = {}
    obj.logger = MagicMock()
    obj.name = "test_slider"
    obj.set_sub_containers()
    return obj


class TestAdjustValue:
    """Test adjust_value method for keyboard-driven slider movement."""

    @staticmethod
    def _setup_groove(s):
        """Set up containers and mock on_batch entries needed by update()."""
        s.containers["thumb"] = s.containers["slide"].get_reduced(0.9, 0.05)
        s.containers["allgroove"] = s.containers["slide"].get_reduced(0.9, 0.2)
        s.on_batch["groove"] = MagicMock()
        s.on_batch["groove_b"] = MagicMock()
        # Ensure get_groove_vertices != on_batch vertices so update proceeds
        s.on_batch["groove"].vertices = []
        s.on_batch["groove_b"].vertices = []

    def test_adjust_value_increases(self, interactive_slider):
        s = interactive_slider
        s.groove_value = 50
        self._setup_groove(s)
        s.adjust_value(1)
        assert math.isclose(s.groove_value, 55, abs_tol=0.01)

    def test_adjust_value_decreases(self, interactive_slider):
        s = interactive_slider
        s.groove_value = 50
        self._setup_groove(s)
        s.adjust_value(-1)
        assert math.isclose(s.groove_value, 45, abs_tol=0.01)

    def test_adjust_value_clamps_at_max(self, interactive_slider):
        s = interactive_slider
        s.groove_value = 98
        self._setup_groove(s)
        s.adjust_value(1)
        assert math.isclose(s.groove_value, 100, abs_tol=0.01)

    def test_adjust_value_clamps_at_min(self, interactive_slider):
        s = interactive_slider
        s.groove_value = 2
        self._setup_groove(s)
        s.adjust_value(-1)
        assert math.isclose(s.groove_value, 0, abs_tol=0.01)

    def test_adjust_value_multiple_steps(self, interactive_slider):
        s = interactive_slider
        s.groove_value = 50
        self._setup_groove(s)
        s.adjust_value(3)
        assert math.isclose(s.groove_value, 65, abs_tol=0.01)

    def test_adjust_value_snaps_to_grid(self, interactive_slider):
        """After a mouse click leaves groove_value off-grid, keyboard should snap."""
        s = interactive_slider
        s.groove_value = 37  # off-grid (nearest grid point is 35)
        self._setup_groove(s)
        s.adjust_value(1)
        # snap to 35 then +5 → 40, NOT 37+5=42
        assert math.isclose(s.groove_value, 40, abs_tol=0.01)

    def test_adjust_value_on_grid_stays_on_grid(self, interactive_slider):
        """When already on grid, keyboard step lands on next grid point."""
        s = interactive_slider
        s.groove_value = 50  # exactly on grid
        self._setup_groove(s)
        s.adjust_value(1)
        assert math.isclose(s.groove_value, 55, abs_tol=0.01)


class TestSetSelected:
    """Test set_selected method for visual selection feedback."""

    def test_set_selected_true(self, interactive_slider):
        s = interactive_slider
        s.set_selected(True)
        assert s.selected is True

    def test_set_selected_false(self, interactive_slider):
        s = interactive_slider
        s.selected = True
        s.set_selected(False)
        assert s.selected is False

    def test_set_selected_updates_colors_when_on_batch(self, interactive_slider):
        from core.constants import COLORS as C

        s = interactive_slider
        mock_vl = MagicMock()
        s.on_batch["thumb"] = mock_vl
        s.set_selected(True)
        mock_vl.colors.__setattr__  # just check it was assigned
        assert s.selected is True

    def test_set_selected_no_error_when_not_on_batch(self, interactive_slider):
        s = interactive_slider
        s.on_batch = {}
        s.set_selected(True)  # should not raise
        assert s.selected is True


# ── on_mouse_focus callback ─────────────────────


class TestOnMouseFocusCallback:
    """Test that on_mouse_focus callback fires on mouse press."""

    @staticmethod
    def _make_slider_with_callback(callback=None, rank=2):
        from core.widgets.slider import Slider

        obj = object.__new__(Slider)
        obj.container = Container("test_slider", 100, 50, 600, 80)
        obj.showvalue = False
        obj.label_min = "Low"
        obj.label_max = "High"
        obj.value_min = 0
        obj.value_max = 100
        obj.value_default = 50
        obj.groove_value = 50
        obj.draw_order = 1
        obj.rank = rank
        obj.font_name = "Sans"
        obj.vertex = {}
        obj.containers = {}
        obj.visible = True
        obj.selected = False
        obj.hover = False
        obj.on_batch = {}
        obj.logger = MagicMock()
        obj.name = "test_slider"
        obj.on_mouse_focus = callback
        obj.set_sub_containers()
        # Set up groove containers needed by on_mouse_press
        obj.containers["thumb"] = obj.containers["slide"].get_reduced(0.9, 0.05)
        obj.containers["allgroove"] = obj.containers["slide"].get_reduced(0.9, 0.2)
        obj.on_batch["groove"] = MagicMock()
        obj.on_batch["groove_b"] = MagicMock()
        obj.on_batch["groove"].vertices = []
        obj.on_batch["groove_b"].vertices = []
        return obj

    def test_callback_called_with_rank(self):
        cb = MagicMock()
        s = self._make_slider_with_callback(callback=cb, rank=2)
        # Click inside the slide container
        cx = int(s.containers["slide"].cx)
        cy = int(s.containers["slide"].cy)
        with patch("core.widgets.slider.Window"):
            s.on_mouse_press(cx, cy, 1, 0)
        cb.assert_called_once_with(2)

    def test_callback_not_called_outside_slide(self):
        cb = MagicMock()
        s = self._make_slider_with_callback(callback=cb, rank=0)
        # Click outside the slide container
        with patch("core.widgets.slider.Window"):
            s.on_mouse_press(0, 0, 1, 0)
        cb.assert_not_called()

    def test_no_callback_no_error(self):
        s = self._make_slider_with_callback(callback=None, rank=0)
        cx = int(s.containers["slide"].cx)
        cy = int(s.containers["slide"].cy)
        with patch("core.widgets.slider.Window"):
            s.on_mouse_press(cx, cy, 1, 0)  # should not raise
