"""Tests for widget math functions - geometry without rendering."""

import math

from core.widgets.abstractwidget import AbstractWidget


def _make_bare_widget():
    """Create an AbstractWidget bypassing __init__ to avoid GUI dependencies."""
    w = object.__new__(AbstractWidget)
    return w


class TestVerticeStrip:
    def test_square(self):
        """Square vertices produce 4 line segments."""
        w = _make_bare_widget()
        # A square: (0,0), (10,0), (10,10), (0,10) as flat list
        vertice = [0, 0, 10, 0, 10, 10, 0, 10]
        result = w.vertice_strip(vertice)
        # Should create line segments connecting consecutive points + closing
        # Each segment is 4 values: x1,y1,x2,y2
        assert len(result) == 16  # 4 segments * 4 values

    def test_triangle(self):
        """Triangle vertices produce 3 line segments."""
        w = _make_bare_widget()
        vertice = [0, 0, 10, 0, 5, 10]
        result = w.vertice_strip(vertice)
        # 3 points -> 3 segments (including closing)
        assert len(result) == 12

    def test_none_input(self):
        """None input returns None."""
        w = _make_bare_widget()
        result = w.vertice_strip(None)
        assert result is None

    def test_closing_segment(self):
        """Last segment closes back to first point."""
        w = _make_bare_widget()
        vertice = [0, 0, 10, 0, 10, 10, 0, 10]
        result = w.vertice_strip(vertice)
        # Last segment should close: from last point back to first
        assert result[-4:] == [0, 10, 0, 0]

    def test_first_segment(self):
        """First segment connects first two points."""
        w = _make_bare_widget()
        vertice = [0, 0, 10, 0, 10, 10, 0, 10]
        result = w.vertice_strip(vertice)
        assert result[0:4] == [0, 0, 10, 0]


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


class TestVerticeCircle:
    def test_point_count(self):
        """30 points produce 60 coordinate values."""
        w = _make_bare_widget()
        result = w.vertice_circle((100, 100), 50, points_n=30)
        assert len(result) == 60  # 30 points * 2 coords

    def test_custom_point_count(self):
        """4 points produce 8 coordinate values."""
        w = _make_bare_widget()
        result = w.vertice_circle((0, 0), 10, points_n=4)
        assert len(result) == 8

    def test_radius_constraint(self):
        """All points lie at exactly the given radius."""
        w = _make_bare_widget()
        center = (100, 100)
        radius = 50
        result = w.vertice_circle(center, radius, points_n=100)
        # All points should be at distance ~radius from center
        for i in range(0, len(result), 2):
            x, y = result[i], result[i + 1]
            dist = math.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
            assert abs(dist - radius) < 1e-10


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


class TestVerticeBorder:
    def test_border_vertices(self):
        """Returns 4 corners as (x1,y1, x2,y1, x2,y2, x1,y2)."""
        w = _make_bare_widget()
        from core.container import Container

        c = Container("test", 10, 20, 100, 50)
        result = w.vertice_border(c)
        # Should return x1, y1, x2, y1, x2, y2, x1, y2
        assert result == (10, 70, 110, 70, 110, 20, 10, 20)
