"""Tests for scenario_generator — validates pure helper functions.

Now imports directly from scenario_generation (no AST extraction needed).
"""

import random

from core.event import Event
from scenario_generation import (
    ScenarioConfig,
    add_scenario_phase,
    choices,
    distribute_events,
    get_events_from_scenario,
    get_part_durations,
    get_task_current_state,
    reduce,
)


class TestReduce:
    """Test GCD-based fraction simplification."""

    def test_coprime(self):
        """Coprime numbers are returned unchanged."""
        assert reduce(3, 7) == (3, 7)

    def test_common_factor(self):
        """Common factor is divided out."""
        assert reduce(4, 6) == (2, 3)

    def test_equal_numbers(self):
        """Equal numbers reduce to (1, 1)."""
        assert reduce(5, 5) == (1, 1)

    def test_one_divides_other(self):
        """Divisible pair reduces correctly."""
        assert reduce(3, 9) == (1, 3)

    def test_large_numbers(self):
        """50/100 reduces to 1/2."""
        assert reduce(50, 100) == (1, 2)

    def test_typical_comm_ratio(self):
        """Typical communication ratio reduces correctly."""
        assert reduce(50, 100) == (1, 2)


class TestChoices:
    """Test selection with repetition from a list."""

    def test_returns_k_items(self):
        """Returns exactly k items."""
        random.seed(42)
        result = choices(["a", "b", "c"], 5, False)
        assert len(result) == 5

    def test_all_from_source(self):
        """All items come from the source list."""
        random.seed(42)
        result = choices(["a", "b", "c"], 10, False)
        assert all(item in ["a", "b", "c"] for item in result)

    def test_wraps_around(self):
        """Wraps when k exceeds list length."""
        random.seed(42)
        result = choices(["x", "y"], 6, False)
        assert len(result) == 6
        assert all(item in ["x", "y"] for item in result)

    def test_single_element(self):
        """Single-element list repeats k times."""
        result = choices(["only"], 3, False)
        assert result == ["only", "only", "only"]


class TestGetPartDurations:
    """Test random duration partitioning."""

    def test_correct_count(self):
        """Returns exactly n parts."""
        random.seed(42)
        parts = get_part_durations(60, 4)
        assert len(parts) == 4

    def test_sum_equals_total(self):
        """Part durations sum to the total."""
        random.seed(42)
        parts = get_part_durations(60, 4)
        assert sum(parts) == 60

    def test_all_non_negative(self):
        """All parts are non-negative."""
        random.seed(42)
        parts = get_part_durations(100, 5)
        assert all(p >= 0 for p in parts)

    def test_single_part(self):
        """Single part equals the total."""
        parts = get_part_durations(30, 1)
        assert len(parts) == 1
        assert sum(parts) == 30


class TestGetEventsFromScenario:
    """Test filtering Event objects from mixed lists."""

    def test_filters_events(self):
        """Extracts only Event objects from mixed list."""
        lines = [
            "# Comment",
            Event(1, 0, "sysmon", ["start"]),
            "Block n° 1",
            Event(2, 10, "track", ["start"]),
        ]
        result = get_events_from_scenario(lines)
        assert len(result) == 2
        assert all(isinstance(e, Event) for e in result)

    def test_empty_list(self):
        """Empty input returns empty list."""
        assert get_events_from_scenario([]) == []

    def test_no_events(self):
        """List with no Events returns empty."""
        lines = ["# Comment", "Block n° 1"]
        assert get_events_from_scenario(lines) == []

    def test_all_events(self):
        """All-Event list returned as-is."""
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["stop"]),
        ]
        result = get_events_from_scenario(lines)
        assert len(result) == 2


class TestGetTaskCurrentState:
    """Test retrieving the last relevant command for a plugin."""

    def test_returns_last_start(self):
        """Returns the last state command for a plugin."""
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["pause"]),
        ]
        result = get_task_current_state(lines, "sysmon")
        assert result == ["pause"]

    def test_returns_none_for_empty(self):
        """Empty list returns None."""
        result = get_task_current_state([], "sysmon")
        assert result is None

    def test_filters_by_plugin(self):
        """Only considers events for the given plugin."""
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "track", ["start"]),
            Event(3, 20, "track", ["pause"]),
        ]
        result = get_task_current_state(lines, "track")
        assert result == ["pause"]

    def test_ignores_non_state_commands(self):
        """Ignores parameter-setting commands."""
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["scales-s1-failure", "True"]),
        ]
        # Only start/pause/resume are kept as state commands
        result = get_task_current_state(lines, "sysmon")
        assert result == ["start"]

    def test_no_matching_plugin(self):
        """Returns None when plugin is absent."""
        lines = [Event(1, 0, "sysmon", ["start"])]
        result = get_task_current_state(lines, "track")
        assert result is None

    def test_only_parameter_events(self):
        """Returns None when only parameter events exist."""
        lines = [
            Event(1, 0, "sysmon", ["title", "New"]),
            Event(2, 10, "sysmon", ["taskupdatetime", "200"]),
        ]
        # No start/pause/resume => None
        result = get_task_current_state(lines, "sysmon")
        assert result is None


class TestDistributeEvents:
    """Test distribute_events line numbering and robustness."""

    def test_line_numbers_are_unique_and_incrementing(self):
        """Each distributed event gets a unique, incrementing line number."""
        random.seed(42)
        lines = [Event(1, 0, "sysmon", ["start"])]
        cmd_list = [["scales-s1-failure", True], ["scales-s2-failure", True]]
        result = distribute_events(lines, 0, 5.0, cmd_list, "sysmon", 60)
        events = get_events_from_scenario(result)
        line_numbers = [e.line for e in events]
        assert len(line_numbers) == len(set(line_numbers))
        assert line_numbers == sorted(line_numbers)

    def test_works_with_trailing_string(self):
        """Does not crash when last element is a string (fix for .line on str)."""
        random.seed(42)
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            "# A trailing comment",
        ]
        cmd_list = [["scales-s1-failure", True]]
        result = distribute_events(lines, 0, 5.0, cmd_list, "sysmon", 60)
        events = get_events_from_scenario(result)
        assert len(events) == 2
        assert events[-1].line == 2

    def test_continues_from_last_event_line(self):
        """Line numbering continues from last Event, not last list element."""
        random.seed(42)
        lines = [
            "# Header comment",
            Event(5, 0, "sysmon", ["start"]),
            "# Block description",
        ]
        cmd_list = [["scales-s1-failure", True]]
        result = distribute_events(lines, 0, 5.0, cmd_list, "sysmon", 60)
        events = get_events_from_scenario(result)
        assert events[-1].line == 6  # Continues from line 5


class TestAddScenarioPhase:
    """Test add_scenario_phase bug fixes (task_state comparisons and line numbering)."""

    def _make_config(self):
        return ScenarioConfig()

    def _make_plugins(self):
        return {"track": None, "sysmon": None, "communications": None, "resman": None}

    def test_start_line_increments_for_track(self):
        """start + targetproportion events get different line numbers (fix for static start_line)."""
        lines = []
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 0, self._make_plugins(), self._make_config(), 60)
        events = get_events_from_scenario(result)
        # Should have "start" event + "targetproportion" event
        assert len(events) == 2
        assert events[0].line != events[1].line
        assert events[1].line > events[0].line

    def test_active_plugin_gets_paused_when_not_desired(self):
        """A plugin with state ["start"] is correctly paused (fix for list vs str comparison)."""
        lines = [Event(1, 0, "sysmon", ["start"])]
        # Only track desired — sysmon should be paused and hidden
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        sysmon_events = [e for e in get_events_from_scenario(result) if e.plugin == "sysmon"]
        # Original start + pause + hide
        assert len(sysmon_events) == 3
        assert sysmon_events[1].command == ["pause"]
        assert sysmon_events[2].command == ["hide"]

    def test_paused_plugin_gets_resumed(self):
        """A paused plugin in the desired list is resumed (fix for list vs str comparison)."""
        lines = [
            Event(1, 0, "track", ["start"]),
            Event(2, 30, "track", ["pause"]),
        ]
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        track_events = [e for e in get_events_from_scenario(result) if e.plugin == "track"]
        # Original start, pause, then show, resume, targetproportion
        assert len(track_events) == 5
        assert track_events[2].command == ["show"]
        assert track_events[3].command == ["resume"]

    def test_inactive_plugin_not_paused(self):
        """A plugin that was never started does not crash the comparison."""
        lines = []
        phase_tuples = (("track", 0.5),)
        # Should not crash — get_task_current_state returns None for sysmon
        result = add_scenario_phase(lines, phase_tuples, 0, self._make_plugins(), self._make_config(), 60)
        sysmon_events = [e for e in get_events_from_scenario(result) if e.plugin == "sysmon"]
        assert len(sysmon_events) == 0

    def test_all_line_numbers_unique(self):
        """All events in a phase have unique line numbers."""
        lines = [Event(1, 0, "sysmon", ["start"])]
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        events = get_events_from_scenario(result)
        line_numbers = [e.line for e in events]
        assert len(line_numbers) == len(set(line_numbers))


class TestStopTasksPattern:
    """Test the pattern used in main() for stopping tasks (fix for .line on str)."""

    def test_get_events_ignores_trailing_strings(self):
        """get_events_from_scenario finds last Event even with trailing strings."""
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 60, "sysmon", ["stop"]),
            "# End of scenario",
        ]
        events = get_events_from_scenario(lines)
        # Using events[-1].line instead of lines[-1].line avoids AttributeError
        assert events[-1].line == 2

    def test_stop_pattern_line_numbering(self):
        """Simulates the main() stop-all-tasks pattern with unique line numbers."""
        lines = [
            "# Block 1",
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 0, "track", ["start"]),
            "# Block 2",
            Event(3, 60, "sysmon", ["scales-s1-failure", True]),
        ]
        # Pattern from main(): use get_events_from_scenario to get last line
        scenario_events = get_events_from_scenario(lines)
        start_line = scenario_events[-1].line + 1 if len(scenario_events) != 0 else 1
        task_names = set(e.plugin for e in scenario_events)
        for task in sorted(task_names):
            lines.append(Event(start_line, 120, task, "stop"))
            start_line += 1
        stop_events = [e for e in get_events_from_scenario(lines) if e.command == ["stop"]]
        stop_lines = [e.line for e in stop_events]
        assert len(stop_lines) == len(set(stop_lines))
        assert stop_lines[0] == 4  # Continues from line 3
