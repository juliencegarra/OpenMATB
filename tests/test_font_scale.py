"""Tests for core.constants.scale_font_sizes - the texts scaled to the window, as the task areas."""

import pytest

from core.constants import FONT_SIZES, scale_font_sizes, scaled


@pytest.fixture(autouse=True)
def reset_scale():
    """The other tests expect the sizes of a 1920 x 1080 window."""
    yield
    scale_font_sizes(1920, 1080)


class TestScaleFontSizes:
    def test_unchanged_in_a_1920_x_1080_window(self):
        assert scale_font_sizes(1920, 1080) == 1
        assert dict(SMALL=12, MEDIUM=16, LARGE=20, XLARGE=30) == FONT_SIZES

    def test_larger_in_a_larger_window(self):
        """2560 x 1440: the texts keep their place in the task areas (they looked small)."""
        assert scale_font_sizes(2560, 1440) == pytest.approx(4 / 3)
        assert dict(SMALL=16, MEDIUM=21, LARGE=27, XLARGE=40) == FONT_SIZES

    def test_the_narrowest_side_gives_the_scale(self):
        """The task areas follow the width and the height: the texts must fit in both."""
        assert scale_font_sizes(1920, 1620) == 1  # Taller, not wider
        assert scale_font_sizes(2400, 1080) == 1  # Wider, not taller

    def test_not_below_the_readable_minimum(self):
        """1024 x 768: 0.53 of the width, but 12 pt texts at 9 pt at least."""
        assert scale_font_sizes(1024, 768) == 0.75
        assert FONT_SIZES["SMALL"] == 9

    def test_scaled_from_the_base_sizes_every_time(self):
        """A second window (e.g. the replay after a session) does not scale already scaled sizes."""
        scale_font_sizes(1366, 768)
        scale_font_sizes(2560, 1440)
        assert FONT_SIZES["SMALL"] == 16


class TestScaled:
    def test_a_length_at_the_scale_of_the_fonts(self):
        scale_font_sizes(2560, 1440)
        assert scaled(12) == pytest.approx(16)
        scale_font_sizes(1920, 1080)
        assert scaled(12) == 12
