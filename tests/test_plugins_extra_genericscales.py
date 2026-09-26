"""Tests for plugins.genericscales - the questionnaire plugin built by its constructor (file, sliders, keys, logs)."""

from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import key

from core.constants import PATHS as P
from core.container import Container
from plugins.genericscales import Genericscales

QUESTIONNAIRE = """# A comment line, ignored
<h1>Workload</h1>
Mental;How mentally demanding was the task?;Low/High;0/100/50

Effort;Effort;Low/High;0/10/5
<newpage>
Frustration;How frustrated were you?;Low/High;0/20/0
"""


class FakeSlider:
    """Stand-in for core.widgets.Slider, with the same value arithmetic (20 steps)."""

    def __init__(self, name, container, title, label_min, label_max, value_min, value_max, value_default, rank, **kw):
        self.name, self.container, self.title, self.rank = name, container, title, rank
        self.label_min, self.label_max = label_min, label_max
        self.value_min, self.value_max, self.value = value_min, value_max, value_default
        self.kwargs = kw
        self.selected = False
        self.update = MagicMock()
        self.show = MagicMock()
        self.hide = MagicMock()

    def get_title(self):
        return self.title

    def get_value(self):
        return self.value

    def set_selected(self, is_selected):
        self.selected = is_selected

    def adjust_value(self, steps):
        step = (self.value_max - self.value_min) / 20
        self.value = max(self.value_min, min(self.value_max, self.value + steps * step))


def _widget_class():
    """A mock widget class whose instances remember their name, container and keyword arguments."""

    def build(name, container, **kwargs):
        w = MagicMock()
        w.fullname, w.container, w.kwargs = name, container, kwargs
        return w

    return MagicMock(side_effect=build)


@pytest.fixture
def window():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        mock_win.MainWindow.get_container.side_effect = lambda placement: Container(placement, 0, 0, 1920, 1080)
        yield mock_win


@pytest.fixture
def label_class():
    """Text measurement: every text is 20 px high."""
    with patch("plugins.genericscales.PygletLabel", return_value=MagicMock(content_height=20)) as mock_label:
        yield mock_label


@pytest.fixture
def widget_classes(window, label_class):
    with (
        patch("plugins.abstractplugin.Frame", _widget_class()),
        patch("plugins.abstractplugin.SimpleHTML", _widget_class()),
        patch("plugins.abstractplugin.Simpletext", _widget_class()),
        patch("plugins.genericscales.Simpletext", _widget_class()) as text_cls,
        patch("plugins.genericscales.Slider", side_effect=FakeSlider) as slider_cls,
        patch("plugins.genericscales.get_conf_value", return_value="Sans"),
    ):
        yield {"text": text_cls, "slider": slider_cls}


@pytest.fixture
def make_scales(mock_logger, widget_classes, tmp_path):
    """Build a Genericscales reading a questionnaire written in tmp_path."""

    def make(content=QUESTIONNAIRE, **parameters):
        (tmp_path / "scales.txt").write_text(content, encoding="utf8")
        gs = Genericscales()
        gs.folder = str(tmp_path)
        gs.parameters["filename"] = "scales.txt"
        gs.parameters.update(parameters)
        return gs

    return make


@pytest.fixture
def scales(make_scales):
    """A started questionnaire, displaying its first page."""
    gs = make_scales()
    gs.start()
    gs.update(1)
    return gs


def _press(gs, symbol):
    gs.on_key_press(symbol, 0)
    gs.on_key_release(symbol, 0)


def _selected(gs):
    return [s.selected for s in gs.sliders.values()]


def _next_page(gs, t=2):
    _press(gs, key.SPACE)
    gs.update(t)


class TestInit:
    def test_default_parameters(self, mock_logger):
        gs = Genericscales()
        assert gs.folder == P["QUESTIONNAIRES"]
        assert gs.parameters["filename"] is None
        assert gs.parameters["response"] == {"text": "Press SPACE to validate", "key": "SPACE"}
        assert gs.parameters["allowkeypress"] is True
        assert gs.parameters["showvalue"] is False
        assert gs.keys == {"SPACE", "UP", "DOWN", "LEFT", "RIGHT"}
        assert gs.ignore_empty_lines is True
        assert gs.blocking is True
        assert gs.sliders == {}

    def test_start_counts_presentations(self, make_scales):
        gs = make_scales()
        gs.start()
        assert gs._presentation_count == 1
        assert gs.alive and gs.is_visible() and not gs.is_paused()


class TestFileReading:
    def test_pages_are_split_and_comments_ignored(self, make_scales):
        gs = make_scales()
        gs.create_widgets()
        assert len(gs.slides) == 2
        assert "comment" not in gs.slides[0]
        assert gs.slides[0].count("\n") == 3  # Title, two scales (the empty line is ignored)
        assert gs.slides[1].startswith("Frustration;")

    def test_empty_page_has_no_slider(self, make_scales):
        """A page without any scale line (only a title) displays no slider."""
        gs = make_scales("<h1>Only a title</h1>\n")
        gs.start()
        gs.update(1)
        assert gs.sliders == {}
        assert "genericscales_title" in gs.widgets

    def test_lines_that_are_not_scales_are_skipped(self, make_scales):
        gs = make_scales("Some free text\nQ;Question;A/B;1/7/4\n")
        gs.start()
        gs.update(1)
        assert list(gs.sliders) == ["slider_2"]


class TestFirstPage:
    def test_one_slider_per_scale(self, scales):
        sliders = list(scales.sliders.values())
        assert [s.title for s in sliders] == ["Mental", "Effort"]
        assert [s.rank for s in sliders] == [0, 1]
        assert (sliders[0].label_min, sliders[0].label_max) == ("Low", "High")
        assert (sliders[0].value_min, sliders[0].value_max, sliders[0].value) == (0, 100, 50)
        assert (sliders[1].value_min, sliders[1].value_max, sliders[1].value) == (0, 10, 5)
        assert sliders[0].kwargs["showvalue"] is False
        assert sliders[0].kwargs["on_mouse_focus"] == scales._on_slider_mouse_focus

    def test_showvalue_parameter_is_given_to_sliders(self, make_scales):
        gs = make_scales(showvalue=True)
        gs.start()
        gs.update(1)
        assert all(s.kwargs["showvalue"] is True for s in gs.sliders.values())

    def test_first_slider_is_selected(self, scales):
        assert _selected(scales) == [True, False]
        assert scales.selected_slider_index == 0

    def test_question_widgets(self, scales):
        """A short title different from the question is displayed above it; an identical one is not."""
        assert scales.widgets["genericscales_label_1"].kwargs["text"] == "How mentally demanding was the task?"
        assert scales.widgets["genericscales_title_1"].kwargs["text"] == "Mental"
        assert scales.widgets["genericscales_title_1"].kwargs["bold"] is True
        assert scales.widgets["genericscales_label_2"].kwargs["text"] == "Effort"
        assert "genericscales_title_2" not in scales.widgets

    def test_page_title_and_response_text(self, scales):
        assert scales.widgets["genericscales_title"].kwargs["text"] == "<h1>Workload</h1>"
        assert "Press SPACE to validate" in scales.widgets["genericscales_press_space"].kwargs["text"]

    def test_title_question_and_slider_are_stacked(self, scales):
        title = scales.widgets["genericscales_title_1"].container
        question = scales.widgets["genericscales_label_1"].container
        slider = scales.sliders["slider_1"].container
        assert slider.b + slider.h == pytest.approx(question.b)
        assert question.b + question.h == pytest.approx(title.b)

    def test_widgets_areas_are_logged(self, scales, mock_logger):
        logged = [c.args[1] for c in mock_logger.record_aoi.call_args_list]
        assert "genericscales_slider_1" in logged
        assert "genericscales_label_2" in logged


class TestMeasureTextHeight:
    def test_returns_label_content_height(self, make_scales, label_class):
        gs = make_scales()
        assert gs._measure_text_height("Some text", 14, 500) == 20
        args, kwargs = label_class.call_args
        assert args == ("Some text",)
        assert kwargs == dict(font_size=14, multiline=True, width=500, font_name="Sans")

    def test_bold_text_is_measured_bold(self, make_scales, label_class):
        make_scales()._measure_text_height("Title", 14, 500, bold=True)
        assert label_class.call_args.kwargs["weight"] == "bold"


class TestKeyboard:
    def test_down_and_up_move_the_selection_cyclically(self, scales):
        _press(scales, key.DOWN)
        assert _selected(scales) == [False, True]
        _press(scales, key.DOWN)
        assert _selected(scales) == [True, False]
        _press(scales, key.UP)
        assert _selected(scales) == [False, True]

    def test_right_and_left_adjust_the_selected_slider(self, scales):
        _press(scales, key.RIGHT)
        _press(scales, key.RIGHT)
        assert scales.sliders["slider_1"].value == 60
        _press(scales, key.DOWN)
        _press(scales, key.LEFT)
        assert scales.sliders["slider_2"].value == 4.5
        assert scales.sliders["slider_1"].value == 60

    def test_key_release_does_not_adjust(self, scales):
        scales.on_key_release(key.RIGHT, 0)
        assert scales.sliders["slider_1"].value == 50

    def test_unhandled_key_is_ignored(self, scales):
        assert scales.do_on_key("A", "press") is None
        assert _selected(scales) == [True, False]

    def test_keys_without_slider(self, make_scales):
        gs = make_scales("<h1>Only a title</h1>\n")
        gs.start()
        gs.update(1)
        assert gs.do_on_key("RIGHT", "press") == "RIGHT"

    def test_mouse_focus_selects_the_slider(self, scales):
        scales._on_slider_mouse_focus(1)
        assert scales.selected_slider_index == 1
        assert _selected(scales) == [False, True]


class TestPages:
    def test_space_shows_the_next_page(self, scales):
        _next_page(scales)
        assert list(scales.sliders) == ["slider_1"]
        assert scales.sliders["slider_1"].title == "Frustration"
        assert _selected(scales) == [True]

    def test_previous_page_widgets_are_removed(self, scales):
        _next_page(scales)
        assert "genericscales_slider_2" not in scales.widgets
        assert "genericscales_label_2" not in scales.widgets
        assert "genericscales_title_1" in scales.widgets  # Title of the new first scale
        assert scales.widgets["genericscales_title_1"].kwargs["text"] == "Frustration"

    def test_space_on_last_page_stops_the_plugin(self, scales):
        _next_page(scales)
        _next_page(scales, t=3)
        assert not scales.alive
        assert not scales.is_visible()

    def test_page_without_title_does_not_show_previous_title(self, scales):
        _next_page(scales)
        assert "genericscales_title" not in scales.widgets


class TestRefresh:
    def test_visible_sliders_are_updated(self, scales):
        for s in scales.sliders.values():
            s.update.reset_mock()
        scales.refresh_widgets()
        assert all(s.update.call_count == 1 for s in scales.sliders.values())

    def test_hidden_sliders_are_not_updated(self, scales):
        scales.hide()
        for s in scales.sliders.values():
            s.update.reset_mock()
        scales.refresh_widgets()
        assert all(s.update.call_count == 0 for s in scales.sliders.values())


class TestStop:
    def test_answers_are_logged_as_performance(self, make_scales, mock_logger):
        gs = make_scales("Q1;Question 1;A/B;0/10/5\nQ2;Question 2;A/B;0/10/2\n")
        gs.start()
        gs.update(1)
        _press(gs, key.RIGHT)
        _next_page(gs)
        assert not gs.alive
        assert gs.performance == {"presentation_number": [1], "Q1": [5.5], "Q2": [2]}
        mock_logger.log_performance.assert_any_call("genericscales", "Q1", 5.5)

    def test_presentation_number_increases(self, make_scales):
        gs = make_scales("Q1;Question 1;A/B;0/10/5\n")
        gs.start()
        gs.stop()
        gs.start()
        gs.stop()
        assert gs.performance["presentation_number"] == [1, 2]

    def test_answers_of_every_page_are_logged(self, scales):
        _press(scales, key.RIGHT)
        _next_page(scales)
        _next_page(scales, t=3)
        assert scales.performance["Mental"] == [55]
        assert scales.performance["Effort"] == [5]
        assert scales.performance["Frustration"] == [0]


class TestSecondPresentation:
    def test_answers_are_not_logged_twice(self, scales):
        """A questionnaire presented again only logs the answers of its new presentation."""
        _press(scales, key.RIGHT)
        _next_page(scales)
        _next_page(scales, t=3)
        scales.start()
        scales.update(4)
        _next_page(scales, t=5)
        _next_page(scales, t=6)
        assert scales.performance["presentation_number"] == [1, 2]
        assert scales.performance["Mental"] == [55, 50]
        assert scales.performance["Frustration"] == [0, 0]

    def test_stop_before_the_first_page_logs_no_answer(self, scales):
        _next_page(scales)
        _next_page(scales, t=3)
        scales.start()
        scales.stop()  # Stopped by the scenario before its first page was displayed
        assert scales.performance["presentation_number"] == [1, 2]
        assert scales.performance["Mental"] == [50]


class TestLongTexts:
    def test_long_title_and_question_are_squeezed_above_the_slider(self, make_scales, label_class):
        """Texts too high for the scale area share what the slider leaves (at least 40% for the slider)."""
        label_class.return_value = MagicMock(content_height=300)
        gs = make_scales("Title;A very long question;A/B;0/10/5\n")
        gs.start()
        gs.update(1)
        slider = gs.sliders["slider_1"].container
        question = gs.widgets["genericscales_label_1"].container
        title = gs.widgets["genericscales_title_1"].container
        assert title.h == pytest.approx(question.h)
        assert slider.h + question.h + title.h == pytest.approx(slider.h / 0.4)
