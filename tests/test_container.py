"""Tests for core.container - Pure geometry, zero external dependencies."""

from core.container import Container


class TestContainerInit:
    def test_basic_attributes(self):
        """Constructor stores l, b, w, h and name."""
        c = Container("test", 10, 20, 100, 50)
        assert c.name == "test"
        assert c.l == 10
        assert c.b == 20
        assert c.w == 100
        assert c.h == 50

    def test_derived_coordinates(self):
        """x1, y1, x2, y2 are computed from l, b, w, h."""
        c = Container("t", 10, 20, 100, 50)
        # x1=l, y1=b+h, x2=l+w, y2=b
        assert c.x1 == 10
        assert c.y1 == 70  # 20 + 50
        assert c.x2 == 110  # 10 + 100
        assert c.y2 == 20

    def test_center(self):
        """Center is at (w/2, h/2) when origin is (0,0)."""
        c = Container("t", 0, 0, 100, 200)
        assert c.cx == 50.0
        assert c.cy == 100.0

    def test_center_offset(self):
        """Center accounts for non-zero origin."""
        c = Container("t", 10, 20, 100, 200)
        assert c.cx == 60.0
        assert c.cy == 120.0

    def test_zero_dimensions(self):
        """Zero-sized container has center at origin."""
        c = Container("zero", 0, 0, 0, 0)
        assert c.cx == 0.0
        assert c.cy == 0.0


class TestContainerRepr:
    def test_repr(self):
        """repr includes class name and container name."""
        c = Container("t", 1, 2, 3, 4)
        assert "Container" in repr(c)
        assert "name=t" in repr(c)


class TestGetters:
    def test_get_x1y1x2y2(self):
        """Returns corner coordinates as (x1, y1, x2, y2)."""
        c = Container("t", 10, 20, 100, 50)
        assert c.get_x1y1x2y2() == (10, 70, 110, 20)

    def test_get_lbwh(self):
        """Returns (left, bottom, width, height) tuple."""
        c = Container("t", 10, 20, 100, 50)
        assert c.get_lbwh() == (10, 20, 100, 50)

    def test_get_center(self):
        """Returns (cx, cy) center point."""
        c = Container("t", 10, 20, 100, 50)
        assert c.get_center() == (60.0, 45.0)


class TestGetReduced:
    def test_half_reduction(self):
        """50% reduction centers the sub-container."""
        c = Container("t", 0, 0, 100, 100)
        r = c.get_reduced(0.5, 0.5)
        assert r.w == 50.0
        assert r.h == 50.0
        assert r.l == 25.0
        assert r.b == 25.0

    def test_full_size(self):
        """100% reduction returns same dimensions."""
        c = Container("t", 0, 0, 100, 100)
        r = c.get_reduced(1.0, 1.0)
        assert r.w == 100.0
        assert r.h == 100.0
        assert r.l == 0.0
        assert r.b == 0.0

    def test_name_suffix(self):
        """Reduced container name includes 'reduced'."""
        c = Container("original", 0, 0, 100, 100)
        r = c.get_reduced(0.5, 0.5)
        assert "reduced" in r.name


class TestGetTranslated:
    def test_translate_x(self):
        """Positive x shifts container right."""
        c = Container("t", 10, 20, 100, 50)
        t = c.get_translated(x=5)
        assert t.l == 15
        assert t.b == 20
        assert t.w == 100
        assert t.h == 50

    def test_translate_y(self):
        """Negative y shifts container down."""
        c = Container("t", 10, 20, 100, 50)
        t = c.get_translated(y=-10)
        assert t.b == 10

    def test_translate_both(self):
        """Both x and y offsets apply."""
        c = Container("t", 0, 0, 100, 50)
        t = c.get_translated(x=10, y=20)
        assert t.l == 10
        assert t.b == 20


class TestReduceAndTranslate:
    def test_identity(self):
        """Width=1, height=1, x=0, y=0 returns same container."""
        c = Container("t", 0, 0, 100, 100)
        rt = c.reduce_and_translate(width=1, height=1, x=0, y=0)
        assert rt.w == 100.0
        assert rt.h == 100.0
        assert rt.l == 0.0
        assert rt.b == 0.0

    def test_half_centered(self):
        """Half-size centered in a 200x200 container."""
        c = Container("t", 0, 0, 200, 200)
        rt = c.reduce_and_translate(width=0.5, height=0.5, x=0.5, y=0.5)
        assert rt.w == 100.0
        assert rt.h == 100.0
        assert rt.l == 50.0
        assert rt.b == 50.0


class TestContainsXY:
    def test_center_is_contained(self):
        """Center point is inside the container."""
        c = Container("t", 0, 0, 100, 100)
        assert c.contains_xy(50, 50) is True

    def test_corner_top_left_contained(self):
        """Top-left corner is on the boundary."""
        c = Container("t", 0, 0, 100, 100)
        # x1=0, y1=100, x2=100, y2=0
        assert c.contains_xy(0, 100) is True

    def test_outside_right(self):
        """Point to the right is outside."""
        c = Container("t", 0, 0, 100, 100)
        assert c.contains_xy(150, 50) is False

    def test_outside_above(self):
        """Point above is outside."""
        c = Container("t", 0, 0, 100, 100)
        # y1=100, y2=0, so y=150 > y1 => y1 >= y is False
        assert c.contains_xy(50, 150) is False
