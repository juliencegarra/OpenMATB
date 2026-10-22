"""Tests for plugins/genericscales.py — dynamic layout logic.

Verifies that title, question, and slider containers never overlap, are regularly spaced
and stay between the page title and the response text.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.container import Container
from plugins.genericscales import SCALE_PATTERN

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


def _set_layout(obj):
    """The layout attributes set by Genericscales.__init__."""
    from core.constants import FONT_SIZES as F

    obj.slider_height = (0.05, 0.03)
    obj.scale_gap = (0.05, 0.012)
    obj.title_question_gap = 0.006
    obj.text_layouts = [
        (F["LARGE"], F["MEDIUM"], 1000),
        (F["MEDIUM"], F["MEDIUM"], 1000),
        (F["MEDIUM"], F["MEDIUM"], None),
    ]
    obj.top_limit = {True: 0.84, False: 0.96}
    obj.bottom_limit = {True: 0.14, False: 0.04}


@pytest.fixture
def gs():
    """Create a Genericscales without triggering __init__ chain."""
    from plugins.genericscales import Genericscales

    obj = object.__new__(Genericscales)
    obj.alias = "genericscales"
    obj.sliders = {}
    obj._answers = []
    obj._first_page = True
    obj.widgets = {}
    obj.container = Container("fullscreen", 0, 0, 1920, 1080)
    obj.regex_scale_pattern = SCALE_PATTERN
    _set_layout(obj)
    obj.m_draw = 1
    obj.parameters = {"showvalue": False, "allowkeypress": True}
    obj.verbose = False
    return obj


def run_make_slide_graphs(gs, slide_text, measure_heights, measure=None):
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
    gs.captured_kwargs = {}

    def fake_add_widget(name, cls, container, **kwargs):
        captured[name] = container
        gs.captured_kwargs[name] = kwargs
        return MagicMock()

    def fake_measure(text, font_size, wrap_width_px, bold=False):
        return measure_heights.get(text, 20)

    gs.add_widget = fake_add_widget
    gs._measure_text_height = measure or fake_measure
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


class TestPageAreas:
    """The scales stay between the page title and the response text."""

    def test_within_free_area(self, gs):
        slide = "Title A;Question A;Low/High;0/100/50\nTitle B;Question B;Bad/Good;1/10/5"
        containers = run_make_slide_graphs(gs, slide, {})
        top_limit = gs.container.h * gs.top_limit[False]
        bottom_limit = gs.container.h * gs.bottom_limit[True]
        for name, c in containers.items():
            assert c.b >= bottom_limit - 0.5 and top(c) <= top_limit + 0.5, name

    def test_below_the_page_title(self, gs):
        """The page title (<h1>) was covered by the first scale of a full page."""
        gs.widgets["genericscales_title"] = MagicMock()
        slide = "\n".join(f"Title {i};Question {i};Low/High;0/10/5" for i in range(6))
        containers = run_make_slide_graphs(gs, slide, {f"Question {i}": 40 for i in range(6)})
        for name, c in containers.items():
            assert top(c) <= gs.container.h * gs.top_limit[True] + 0.5, name
            assert c.b >= gs.container.h * gs.bottom_limit[True] - 0.5, name

    def test_starts_under_the_page_title(self, gs):
        gs.widgets["genericscales_title"] = MagicMock()
        containers = run_make_slide_graphs(gs, "T;Q;Low/High;0/10/5", {})
        assert top(containers["title_1"]) == pytest.approx(gs.container.h * gs.top_limit[True])

    def test_centered_without_page_title(self, gs):
        containers = run_make_slide_graphs(gs, "T;Q;Low/High;0/10/5", {})
        free_center = gs.container.h * (gs.top_limit[False] + gs.bottom_limit[True]) / 2
        block_center = (top(containers["title_1"]) + containers["slider_1"].b) / 2
        assert block_center == pytest.approx(free_center)


class TestRegularSpacing:
    """Each scale reads as a block: the same gap between scales, larger than inside a scale."""

    def test_same_gap_whatever_the_question_height(self, gs):
        slide = "\n".join(f"Title {i};Question {i};Low/High;0/10/5" for i in range(4))
        heights = {"Question 0": 50, "Question 1": 20, "Question 2": 50, "Question 3": 20}
        containers = run_make_slide_graphs(gs, slide, heights)
        gaps = [containers[f"slider_{i}"].b - top(containers[f"title_{i + 1}"]) for i in range(1, 4)]
        assert gaps == pytest.approx([gaps[0]] * 3)
        assert gaps[0] > containers["title_1"].b - top(containers["label_1"])

    def test_texts_keep_their_height(self, gs):
        containers = run_make_slide_graphs(gs, "Title;A long question;Low/High;0/100/50", {"A long question": 80})
        assert containers["label_1"].h == pytest.approx(80 + 4)


class TestFullPage:
    """A full page thins its sliders and gaps, then uses smaller texts."""

    def test_default_sizes_when_there_is_room(self, gs):
        containers = run_make_slide_graphs(gs, "T;Q;Low/High;0/10/5", {})
        assert containers["slider_1"].h == pytest.approx(gs.slider_height[0] * gs.container.h)
        assert gs.captured_kwargs["title_1"]["font_size"] == gs.text_layouts[0][0]

    def test_sliders_thinner_on_a_full_page(self, gs):
        slide = "\n".join(f"Title {i};Question {i};Low/High;0/10/5" for i in range(6))
        containers = run_make_slide_graphs(gs, slide, {f"Question {i}": 70 for i in range(6)})
        assert containers["slider_1"].h < gs.slider_height[0] * gs.container.h
        assert containers["slider_1"].h >= gs.slider_height[1] * gs.container.h - 0.5

    def test_smaller_titles_when_texts_do_not_fit(self, gs):
        slide = "\n".join(f"Title {i};Question {i};Low/High;0/10/5" for i in range(6))

        def measure(text, font_size, wrap_width_px, bold=False):
            if text.startswith("Question"):
                return 60
            return 60 if font_size == gs.text_layouts[0][0] else 20  # The page fits only with the smaller titles

        run_make_slide_graphs(gs, slide, {}, measure=measure)
        sizes = {gs.captured_kwargs[f"title_{i}"]["font_size"] for i in range(1, 7)}
        assert sizes == {gs.text_layouts[1][0]}


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

    def test_scale_with_equal_bounds_is_not_a_scale(self, gs):
        """Equal minimum and maximum (5/5/5) divided by zero in the slider, when its page showed."""
        slide = "Effort;Low/High;5/5/5\nQuestion B;Bad/Good;1/10/5"
        containers = run_make_slide_graphs(gs, slide, {})
        assert "slider_1" not in containers
        assert "slider_2" in containers

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
def gs_with_keys(mock_window):
    """Genericscales with enough state for do_on_key testing."""
    from plugins.genericscales import Genericscales

    obj = object.__new__(Genericscales)
    obj.alias = "genericscales"
    obj.sliders = {}
    obj._answers = []
    obj._first_page = True
    obj.widgets = {}
    obj.container = Container("fullscreen", 0, 0, 1920, 1080)
    obj.regex_scale_pattern = SCALE_PATTERN
    _set_layout(obj)
    obj.m_draw = 1
    obj.parameters = {"showvalue": False, "response": {"text": "Press SPACE to validate", "key": "SPACE"}}
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
        gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 1

    def test_up_decrements_index_with_wrap(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys.do_on_key("UP", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 2  # wraps to last

    def test_down_wraps_to_first(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 3)
        gs_with_keys.selected_slider_index = 2
        gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        assert gs_with_keys.selected_slider_index == 0

    def test_right_calls_adjust_value(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        gs_with_keys.do_on_key("RIGHT", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].adjust_value.assert_called_once_with(1)

    def test_left_calls_adjust_value(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        gs_with_keys.do_on_key("LEFT", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].adjust_value.assert_called_once_with(-1)

    def test_space_release_triggers_next_slide(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        gs_with_keys.do_on_key("SPACE", "release", emulate=True)
        assert gs_with_keys.go_to_next_slide is True

    def test_set_selected_called_on_navigation(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        gs_with_keys.do_on_key("DOWN", "press", emulate=True)
        slider_list = list(gs_with_keys.sliders.values())
        slider_list[0].set_selected.assert_called_with(False)
        slider_list[1].set_selected.assert_called_with(True)

    def test_no_action_on_release_for_arrows(self, gs_with_keys):
        self._add_mock_sliders(gs_with_keys, 2)
        gs_with_keys.do_on_key("DOWN", "release", emulate=True)
        assert gs_with_keys.selected_slider_index == 0  # unchanged

    def test_no_action_when_no_sliders(self, gs_with_keys):
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
        gs_with_keys.do_on_key("RIGHT", "press", emulate=True)
        list(gs_with_keys.sliders.values())[2].adjust_value.assert_called_once_with(1)
