"""Tests for core/widgets/slider.py — sub-container layout.

Verifies that set_sub_containers distributes space correctly,
especially when showvalue=False (no value label zone).
"""

import pytest
from unittest.mock import MagicMock
from core.container import Container


# ── Fixture ──────────────────────────────────────


@pytest.fixture
def make_slider():
    """Factory: create a minimal Slider (skipping __init__) and call set_sub_containers."""
    from core.widgets.slider import Slider

    def _make(showvalue=True, container=None):
        if container is None:
            container = Container('test_slider', 100, 50, 600, 80)
        obj = object.__new__(Slider)
        obj.container = container
        obj.showvalue = showvalue
        obj.label_min = 'Low'
        obj.label_max = 'High'
        obj.groove_value = 50
        obj.draw_order = 1
        obj.font_name = 'Sans'
        obj.vertex = {}
        obj.containers = {}
        obj.set_sub_containers()
        return obj

    return _make


# ── Helpers ──────────────────────────────────────


def rightmost_edge(slider):
    """Return the rightmost pixel of all layout sub-containers."""
    layout_names = ['min', 'slide', 'max', 'value']
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
        for name in ['min', 'slide', 'max', 'value']:
            assert name in s.containers, f"Missing container '{name}'"

    def test_containers_fill_width(self, make_slider):
        s = make_slider(showvalue=True)
        total = sum(s.containers[n].w for n in ['min', 'slide', 'max', 'value'])
        assert abs(total - s.container.w) < 1  # float tolerance

    def test_no_horizontal_overlap(self, make_slider):
        s = make_slider(showvalue=True)
        names = ['min', 'slide', 'max', 'value']
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = s.containers[names[i]], s.containers[names[j]]
                if abs(i - j) > 1:
                    assert not containers_overlap_horizontally(a, b), \
                        f"'{names[i]}' overlaps '{names[j]}'"

    def test_value_label_created(self, make_slider):
        s = make_slider(showvalue=True)
        assert 'value' in s.vertex

    def test_order_is_min_slide_max_value(self, make_slider):
        s = make_slider(showvalue=True)
        assert s.containers['min'].l < s.containers['slide'].l
        assert s.containers['slide'].l < s.containers['max'].l
        assert s.containers['max'].l < s.containers['value'].l


# ── showvalue=False ──────────────────────────────


class TestSubContainersHideValue:
    """When showvalue=False, only three layout zones: min, slide, max."""

    def test_no_value_container(self, make_slider):
        s = make_slider(showvalue=False)
        assert 'value' not in s.containers

    def test_three_layout_zones_present(self, make_slider):
        s = make_slider(showvalue=False)
        for name in ['min', 'slide', 'max']:
            assert name in s.containers, f"Missing container '{name}'"

    def test_containers_fill_width(self, make_slider):
        s = make_slider(showvalue=False)
        total = sum(s.containers[n].w for n in ['min', 'slide', 'max'])
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
        assert s_hide.containers['min'].w > s_show.containers['min'].w
        assert s_hide.containers['max'].w > s_show.containers['max'].w

    def test_no_value_label_created(self, make_slider):
        s = make_slider(showvalue=False)
        assert 'value' not in s.vertex

    def test_order_is_min_slide_max(self, make_slider):
        s = make_slider(showvalue=False)
        assert s.containers['min'].l < s.containers['slide'].l
        assert s.containers['slide'].l < s.containers['max'].l

    def test_slide_width_unchanged(self, make_slider):
        """The slide zone width should be the same regardless of showvalue."""
        s_show = make_slider(showvalue=True)
        s_hide = make_slider(showvalue=False)
        assert abs(s_show.containers['slide'].w - s_hide.containers['slide'].w) < 1
