"""Tests for plugins/genericscales.py — dynamic layout logic.

Verifies that title, question, and slider containers never overlap
and always stay within the parent scale_container bounds.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.container import Container

# ── Helpers ──────────────────────────────────────


def top(c):
    """Top edge of a container (b + h)."""
    return c.b + c.h


def overlaps_vertically(a, b):
    """True if two containers share any vertical pixels."""
    return a.b < top(b) and b.b < top(a)


def within(child, parent, tol=0.5):
    """True if child fits inside parent bounds (with tolerance for float rounding)."""
    return (
        child.b >= parent.b - tol
        and top(child) <= top(parent) + tol
        and child.l >= parent.l - tol
        and child.l + child.w <= parent.l + parent.w + tol
    )


# ── Fixture ──────────────────────────────────────


@pytest.fixture
def gs():
    """Create a Genericscales without triggering __init__ chain."""
    from plugins.genericscales import Genericscales

    obj = object.__new__(Genericscales)
    obj.alias = "genericscales"
    obj.sliders = {}
    obj.widgets = {}
    obj.container = Container("fullscreen", 0, 0, 1920, 1080)
    obj.regex_scale_pattern = r"(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)"
    obj.question_height_ratio = 0.1
    obj.question_interspace = 0.05
    obj.top_to_top = 0.15
    obj.m_draw = 1
    obj.parameters = {"showvalue": False}
    obj.verbose = False
    return obj


def run_make_slide_graphs(gs, slide_text, measure_heights):
    """Call make_slide_graphs with mocked dependencies, return captured containers.

    Parameters
    ----------
    gs : Genericscales (uninitialised)
    slide_text : str  — value for current_slide
    measure_heights : dict  — maps text content to pixel height returned by
                              _measure_text_height (before padding is added)

    Returns
    -------
    dict  — {widget_suffix: Container} for every add_widget call
    """
    gs.current_slide = slide_text

    captured = {}

    def fake_add_widget(name, cls, container, **kwargs):
        captured[name] = container
        return MagicMock()

    def fake_measure(text, font_size, wrap_width_px, bold=False):
        return measure_heights.get(text, 20)

    gs.add_widget = fake_add_widget
    gs._measure_text_height = fake_measure
    gs.get_widget_fullname = lambda name: f"genericscales_{name}"

    with patch("plugins.abstractplugin.BlockingPlugin.make_slide_graphs"):
        gs.make_slide_graphs()

    return captured


# ── Dynamic layout (show_title = True) ───────────


class TestDynamicLayoutNoOverlap:
    """Title, question, and slider containers must never overlap."""

    def test_short_text_no_overlap(self, gs):
        slide = "My Title;My Question;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"My Title": 20, "My Question": 20})

        title_c = containers["title_1"]
        question_c = containers["label_1"]
        slider_c = containers["slider_1"]

        assert not overlaps_vertically(title_c, question_c)
        assert not overlaps_vertically(question_c, slider_c)
        assert not overlaps_vertically(title_c, slider_c)

    def test_long_text_no_overlap(self, gs):
        slide = "Section Header;A very long question that wraps across multiple lines on screen;Low/High;0/100/50"
        containers = run_make_slide_graphs(
            gs,
            slide,
            {
                "Section Header": 30,
                "A very long question that wraps across multiple lines on screen": 90,
            },
        )

        title_c = containers["title_1"]
        question_c = containers["label_1"]
        slider_c = containers["slider_1"]

        assert not overlaps_vertically(title_c, question_c)
        assert not overlaps_vertically(question_c, slider_c)
        assert not overlaps_vertically(title_c, slider_c)

    def test_huge_text_no_overlap(self, gs):
        """Even when text measured heights exceed the container, no overlap."""
        slide = "Big Title;Enormous question;Low/High;0/100/50"
        # Heights exceed any reasonable container
        containers = run_make_slide_graphs(gs, slide, {"Big Title": 200, "Enormous question": 300})

        title_c = containers["title_1"]
        question_c = containers["label_1"]
        slider_c = containers["slider_1"]

        assert not overlaps_vertically(title_c, question_c)
        assert not overlaps_vertically(question_c, slider_c)
        assert not overlaps_vertically(title_c, slider_c)


class TestDynamicLayoutBounds:
    """All sub-containers must stay within the parent scale_container."""

    def _get_scale_container(self, gs):
        """Reproduce the scale_container for a single-question slide."""
        all_scales = gs.container.get_reduced(1, gs.top_to_top * 1)
        height_prop = (gs.question_height_ratio * gs.container.h) / all_scales.h
        return all_scales.reduce_and_translate(height=height_prop, y=1)

    def test_short_text_within_bounds(self, gs):
        slide = "Title;Question;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Title": 20, "Question": 20})

        parent = self._get_scale_container(gs)
        for name in ["title_1", "label_1", "slider_1"]:
            assert within(containers[name], parent), f"{name} outside parent: {containers[name]} vs {parent}"

    def test_long_text_within_bounds(self, gs):
        slide = "Title;A long question;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Title": 30, "A long question": 80})

        parent = self._get_scale_container(gs)
        for name in ["title_1", "label_1", "slider_1"]:
            assert within(containers[name], parent), f"{name} outside parent: {containers[name]} vs {parent}"


class TestSliderMinimumHeight:
    """Slider always gets at least 40% of the scale_container height."""

    def test_slider_minimum_40_percent(self, gs):
        slide = "Title;Question;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Title": 200, "Question": 200})

        all_scales = gs.container.get_reduced(1, gs.top_to_top * 1)
        height_prop = (gs.question_height_ratio * gs.container.h) / all_scales.h
        scale_container = all_scales.reduce_and_translate(height=height_prop, y=1)

        slider_c = containers["slider_1"]
        min_h = scale_container.h * 0.40
        assert slider_c.h >= min_h - 0.5  # tolerance for float rounding

    def test_short_text_slider_gets_remaining_space(self, gs):
        """When text is small, the slider gets more than 40%."""
        slide = "T;Q;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"T": 10, "Q": 10})

        all_scales = gs.container.get_reduced(1, gs.top_to_top * 1)
        height_prop = (gs.question_height_ratio * gs.container.h) / all_scales.h
        scale_container = all_scales.reduce_and_translate(height=height_prop, y=1)

        slider_c = containers["slider_1"]
        assert slider_c.h > scale_container.h * 0.40


class TestStackingOrder:
    """Title on top, then question, then slider at the bottom."""

    def test_vertical_order(self, gs):
        slide = "Title;Question;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Title": 20, "Question": 20})

        title_c = containers["title_1"]
        question_c = containers["label_1"]
        slider_c = containers["slider_1"]

        # Title top > Question top > Slider top
        assert top(title_c) >= top(question_c)
        assert top(question_c) >= top(slider_c)

        # Title bottom > Question bottom > Slider bottom
        assert title_c.b >= question_c.b
        assert question_c.b >= slider_c.b


# ── No-title layout (show_title = False) ─────────


class TestNoTitleLayout:
    """When title == label, no title widget is created."""

    def test_no_title_widget_created(self, gs):
        slide = "Same;Same;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Same": 20})

        assert "title_1" not in containers
        assert "label_1" in containers
        assert "slider_1" in containers

    def test_no_title_no_overlap(self, gs):
        slide = "Same;Same;Low/High;0/100/50"
        containers = run_make_slide_graphs(gs, slide, {"Same": 20})

        question_c = containers["label_1"]
        slider_c = containers["slider_1"]
        assert not overlaps_vertically(question_c, slider_c)


# ── Multiple scales per slide ─────────────────


class TestMultipleScales:
    """Multiple questions on the same slide should not overlap."""

    def test_two_scales_with_titles_no_overlap(self, gs):
        slide = "Title A;Question A;Low/High;0/100/50\nTitle B;Question B;Bad/Good;1/10/5"
        containers = run_make_slide_graphs(
            gs,
            slide,
            {"Title A": 20, "Question A": 20, "Title B": 20, "Question B": 20},
        )

        # Within each scale: no overlap
        assert not overlaps_vertically(containers["title_1"], containers["label_1"])
        assert not overlaps_vertically(containers["label_1"], containers["slider_1"])
        assert not overlaps_vertically(containers["title_2"], containers["label_2"])
        assert not overlaps_vertically(containers["label_2"], containers["slider_2"])


# ── Keyboard navigation ──────────────────────


@pytest.fixture
def gs_with_keys():
    """Genericscales with enough state for do_on_key testing."""
    from plugins.genericscales import Genericscales

    obj = object.__new__(Genericscales)
    obj.alias = "genericscales"
    obj.sliders = {}
    obj.widgets = {}
    obj.container = Container("fullscreen", 0, 0, 1920, 1080)
    obj.regex_scale_pattern = r"(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)"
    obj.question_height_ratio = 0.1
    obj.question_interspace = 0.05
    obj.top_to_top = 0.15
    obj.m_draw = 1
    obj.parameters = {"showvalue": False}
    obj.verbose = False
    obj.selected_slider_index = 0
    obj.keys = {"SPACE", "UP", "DOWN", "LEFT", "RIGHT"}
    obj.can_execute_keys = True
    obj.go_to_next_slide = False
    return obj


class TestKeyboardKeysRegistered:
    """Arrow keys should be in self.keys after __init__."""

    def test_arrow_keys_in_keys(self, gs_with_keys):
        for key in ["UP", "DOWN", "LEFT", "RIGHT"]:
            assert key in gs_with_keys.keys

    def test_space_still_in_keys(self, gs_with_keys):
        assert "SPACE" in gs_with_keys.keys


class TestKeyboardNavigation:
    """UP/DOWN should change selected_slider_index."""

    def _add_mock_sliders(self, gs, n=3):
        for i in range(n):
            s = MagicMock()
            s.selected = False
            gs.sliders[f"slider_{i + 1}"] = s

    def test_down_increments_index(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        with patch.object(type(gs_with_keys), "_mock_modal", None, create=True):
            pass
        # Mock the Window for filter_key
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 1

    def test_up_decrements_index_with_wrap(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("UP", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 2  # wraps to last

    def test_down_wraps_to_first(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys.selected_slider_index = 2
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 0

    def test_right_calls_adjust_value(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("RIGHT", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].adjust_value.assert_called_once_with(1)

    def test_left_calls_adjust_value(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("LEFT", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].adjust_value.assert_called_once_with(-1)

    def test_space_release_triggers_next_slide(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("SPACE", "release", emulate=True)
        assert gs_with_keys.go_to_next_slide is True

    def test_set_selected_called_on_navigation(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].set_selected.assert_called_with(False)
        slider_list[1].set_selected.assert_called_with(True)

    def test_no_action_on_release_for_arrows(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("DOWN", "release", emulate=True)
        assert gs_with_keys.selected_slider_index == 0  # unchanged

    def test_no_action_when_no_sliders(self, gs_with_keys):
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 0  # unchanged


# ── Mouse focus synchronisation ──────────────


class TestMouseFocusSync:
    """Clicking a slider should synchronise selected_slider_index."""

    @staticmethod
    def _add_mock_sliders(gs, n=3):
        for i in range(n):
            s = MagicMock()
            s.selected = False
            gs.sliders[f"slider_{i + 1}"] = s

    def test_mouse_focus_updates_index(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys._on_slider_mouse_focus(2)
        assert gs_with_keys.selected_slider_index == 2

    def test_mouse_focus_calls_set_selected(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys._on_slider_mouse_focus(1)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].set_selected.assert_called_with(False)
        slider_list[1].set_selected.assert_called_with(True)
        slider_list[2].set_selected.assert_called_with(False)

    def test_mouse_focus_then_keyboard_uses_new_index(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys._on_slider_mouse_focus(2)
        with patch("plugins.abstractplugin.Window") as mock_win:
            mock_win.MainWindow.modal_dialog = None
            gs_with_keys.do_on_key("RIGHT", "press", emulate=True)
        list(gs_with_keys.sliders.values())[2].adjust_value.assert_called_once_with(1)
