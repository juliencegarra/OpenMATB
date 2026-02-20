"""Tests for plugins/scheduling.py — pure time computation methods."""

from plugins.scheduling import Scheduling


def _make_scheduling(**overrides):
    """Create a Scheduling instance without triggering __init__ imports."""
    s = object.__new__(Scheduling)
    s.alias = "scheduling"
    s.scenario_time = 0
    s.maximum_time_sec = 480
    s.parameters = dict(
        displaychronometer=True,
        reversechronometer=False,
        minduration=8,
    )
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


# ── get_elapsed_time_sec ─────────────────────────


class TestGetElapsedTimeSec:
    def test_zero(self):
        """At scenario start, elapsed time is 0."""
        s = _make_scheduling(scenario_time=0)
        assert s.get_elapsed_time_sec() == 0

    def test_truncates_to_int(self):
        """Fractional seconds are truncated (65.7 → 65)."""
        s = _make_scheduling(scenario_time=65.7)
        assert s.get_elapsed_time_sec() == 65

    def test_large_value(self):
        """Works correctly for values over one hour."""
        s = _make_scheduling(scenario_time=3723.9)
        assert s.get_elapsed_time_sec() == 3723


# ── get_elapsed_time_string ──────────────────────


class TestGetElapsedTimeString:
    def test_zero_seconds(self):
        """0 seconds formats as 00:00:00."""
        s = _make_scheduling(scenario_time=0)
        assert s.get_elapsed_time_string() == "Elapsed time \t 00:00:00"

    def test_one_minute_five_seconds(self):
        """65 seconds formats as 00:01:05."""
        s = _make_scheduling(scenario_time=65)
        assert s.get_elapsed_time_string() == "Elapsed time \t 00:01:05"

    def test_one_hour_two_min_three_sec(self):
        """3723 seconds formats as 01:02:03."""
        s = _make_scheduling(scenario_time=3723)
        assert s.get_elapsed_time_string() == "Elapsed time \t 01:02:03"


# ── get_remaining_time_sec ───────────────────────


class TestGetRemainingTimeSec:
    def test_full_remaining(self):
        """At scenario start, remaining equals total duration."""
        s = _make_scheduling(scenario_time=0, maximum_time_sec=480)
        assert s.get_remaining_time_sec() == 480

    def test_half_remaining(self):
        """Halfway through, remaining is half the total."""
        s = _make_scheduling(scenario_time=240, maximum_time_sec=480)
        assert s.get_remaining_time_sec() == 240


# ── get_remaining_time_string ────────────────────


class TestGetRemainingTimeString:
    def test_full_remaining(self):
        """480 sec remaining formats as 00:08:00."""
        s = _make_scheduling(scenario_time=0, maximum_time_sec=480)
        assert s.get_remaining_time_string() == "Remaining time \t 00:08:00"

    def test_partial_remaining(self):
        """240 sec remaining formats as 00:04:00."""
        s = _make_scheduling(scenario_time=240, maximum_time_sec=480)
        assert s.get_remaining_time_string() == "Remaining time \t 00:04:00"


# ── get_chrono_str ───────────────────────────────


class TestGetChronoStr:
    def test_chronometer_disabled(self):
        """When chronometer is off, return empty string."""
        s = _make_scheduling(scenario_time=100)
        s.parameters["displaychronometer"] = False
        assert s.get_chrono_str() == ""

    def test_elapsed_mode(self):
        """Forward chronometer delegates to elapsed time string."""
        s = _make_scheduling(scenario_time=65)
        s.parameters["displaychronometer"] = True
        s.parameters["reversechronometer"] = False
        result = s.get_chrono_str()
        assert "Elapsed" in result
        assert "00:01:05" in result

    def test_remaining_mode(self):
        """Reverse chronometer delegates to remaining time string."""
        s = _make_scheduling(scenario_time=0, maximum_time_sec=480)
        s.parameters["displaychronometer"] = True
        s.parameters["reversechronometer"] = True
        result = s.get_chrono_str()
        assert "Remaining" in result
        assert "00:08:00" in result
