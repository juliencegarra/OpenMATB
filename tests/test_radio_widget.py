"""Tests for the Radio widget of the communications task (labels only, no rendering)."""

from unittest.mock import MagicMock, patch

import pytest

from core.container import Container
from core.logger import get_logger, set_logger
from core.window import Window


@pytest.fixture
def radio_labels():
    """Build a Radio and return the keyword arguments and text of each label it creates."""
    labels = []

    def new_label(text, **kwargs):
        label = MagicMock(text=text, **{k: v for k, v in kwargs.items() if k in ("x", "anchor_x")})
        labels.append(label)
        return label

    previous_logger = get_logger()
    set_logger(MagicMock())
    try:
        with (
            patch("core.widgets.radio.Label", side_effect=new_label),
            patch.object(Window, "MainWindow", MagicMock(), create=True),
        ):
            from core.widgets.radio import Radio

            radio = Radio("radio_NAV_1", Container("radio", 0, 0, 400, 40), "NAV_1", 135.7, on=False)
            yield radio, labels
    finally:
        set_logger(previous_logger)


class TestRadioLabels:
    def test_name_and_frequency_do_not_rely_on_tabs(self, radio_labels):
        """Regression: the name and the frequency were separated by tabs, which have no width in a single-line
        label (Windows): "NAV 1135.7" with pyglet 2, overlapping digits with pyglet 3."""
        _radio, labels = radio_labels
        assert all("\t" not in label.text for label in labels)

    def test_name_left_of_the_frequency(self, radio_labels):
        _radio, labels = radio_labels
        texts = {label.text: label for label in labels}
        name, frequency = texts["NAV 1"], texts["135.7"]
        assert (name.anchor_x, frequency.anchor_x) == ("right", "left")
        assert name.x < frequency.x  # A gap between the right of the name and the left of the frequency

    def test_new_frequency(self, radio_labels):
        radio, _labels = radio_labels
        assert not radio.is_new_frequency(135.7)
        radio.set_frequency_text(118.25)
        assert radio.vertex["radio_frequency"].text == "118.2"
        assert not radio.is_new_frequency(118.2)
        assert radio.is_new_frequency(119.0)
