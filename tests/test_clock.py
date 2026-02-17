"""Tests for core.clock - Time management logic."""

from unittest.mock import patch, MagicMock


class TestClockSpeed:
    def _make_clock(self):
        """Create a Clock-like object for testing speed logic."""
        # Clock inherits from pyglet.clock.Clock (a MagicMock),
        # so we test the methods directly on a simple namespace
        class FakeClock:
            _time = 0.0
            _speed = 1
            isFastForward = False
            name = 'test'

        # Bind Clock methods to our fake
        from core.clock import Clock
        fc = FakeClock()
        fc.increase_speed = Clock.increase_speed.__get__(fc)
        fc.decrease_speed = Clock.decrease_speed.__get__(fc)
        fc.reset_speed = Clock.reset_speed.__get__(fc)
        fc.set_time = Clock.set_time.__get__(fc)
        fc.get_time = Clock.get_time.__get__(fc)
        return fc

    def test_initial_speed(self):
        """Default speed is 1."""
        c = self._make_clock()
        assert c._speed == 1

    def test_increase_speed(self):
        """Increase bumps speed by 1."""
        c = self._make_clock()
        c.increase_speed()
        assert c._speed == 2

    def test_max_speed_cap(self):
        """Speed cannot exceed 10."""
        c = self._make_clock()
        for _ in range(20):
            c.increase_speed()
        assert c._speed == 10

    def test_decrease_speed(self):
        """Decrease drops speed by 1."""
        c = self._make_clock()
        c._speed = 5
        c.decrease_speed()
        assert c._speed == 4

    def test_min_speed_cap(self):
        """Speed cannot go below 1."""
        c = self._make_clock()
        c.decrease_speed()
        assert c._speed == 1  # Can't go below 1

    def test_reset_speed(self):
        """Reset returns speed to 1."""
        c = self._make_clock()
        c._speed = 7
        c.reset_speed()
        assert c._speed == 1


class TestClockTime:
    def _make_clock(self):
        class FakeClock:
            _time = 0.0
            _speed = 1
            isFastForward = False
            name = 'test'

        from core.clock import Clock
        fc = FakeClock()
        fc.set_time = Clock.set_time.__get__(fc)
        fc.get_time = Clock.get_time.__get__(fc)
        return fc

    def test_set_and_get_time(self):
        """set_time/get_time round-trip preserves value."""
        c = self._make_clock()
        c.set_time(42.5)
        assert c.get_time() == 42.5

    def test_initial_time(self):
        """Default time is 0.0."""
        c = self._make_clock()
        assert c.get_time() == 0.0
