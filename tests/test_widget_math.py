"""Tests for widget math functions - geometry without rendering."""

import math

from core.widgets.abstractwidget import AbstractWidget


def _make_bare_widget():
    """Create an AbstractWidget bypassing __init__ to avoid GUI dependencies."""
    w = object.__new__(AbstractWidget)
    return w


class TestGetTriangleCentroid:
    def test_equilateral_like(self):
        """Centroid of (0,0),(10,0),(5,10) is (5, 3.33)."""
        w = _make_bare_widget()
        vertice = (0, 0, 10, 0, 5, 10)
        cx, cy = w.get_triangle_centroid(vertice)
        assert cx == 5.0
        assert cy == round(10 / 3, 2)

    def test_right_triangle(self):
        """Centroid of right triangle at (2, 2)."""
        w = _make_bare_widget()
        vertice = (0, 0, 6, 0, 0, 6)
        cx, cy = w.get_triangle_centroid(vertice)
        assert cx == 2.0
        assert cy == 2.0


class TestRotateVerticeList:
    def test_no_rotation(self):
        """0-degree rotation leaves vertices unchanged."""
        w = _make_bare_widget()
        origin = (5, 5)
        vertices = [0, 0, 10, 0, 10, 10, 0, 10]
        result = w.rotate_vertice_list(origin, vertices, 0)
        for orig, rotated in zip(vertices, result):
            assert abs(orig - rotated) < 1e-10

    def test_90_degrees(self):
        """90-degree rotation maps (1,0) to (0,1)."""
        w = _make_bare_widget()
        origin = (0, 0)
        vertices = [1, 0]
        result = w.rotate_vertice_list(origin, vertices, math.pi / 2)
        assert abs(result[0] - 0) < 1e-10  # x should be ~0
        assert abs(result[1] - 1) < 1e-10  # y should be ~1

    def test_180_degrees(self):
        """180-degree rotation maps (1,0) to (-1,0)."""
        w = _make_bare_widget()
        origin = (0, 0)
        vertices = [1, 0]
        result = w.rotate_vertice_list(origin, vertices, math.pi)
        assert abs(result[0] - (-1)) < 1e-10
        assert abs(result[1] - 0) < 1e-10

    def test_360_degrees(self):
        """Full rotation returns to original positions."""
        w = _make_bare_widget()
        origin = (5, 5)
        vertices = [0, 0, 10, 0, 10, 10]
        result = w.rotate_vertice_list(origin, vertices, 2 * math.pi)
        for orig, rotated in zip(vertices, result):
            assert abs(orig - rotated) < 1e-10


class TestGrouped:
    def test_pairs(self):
        """Groups list into consecutive pairs."""
        w = _make_bare_widget()
        result = list(w.grouped([1, 2, 3, 4, 5, 6], 2))
        assert result == [(1, 2), (3, 4), (5, 6)]

    def test_triples(self):
        """Groups list into consecutive triples."""
        w = _make_bare_widget()
        result = list(w.grouped([1, 2, 3, 4, 5, 6], 3))
        assert result == [(1, 2, 3), (4, 5, 6)]
