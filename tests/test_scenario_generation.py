"""Tests for scenario_generation — pure logic module.

Direct imports (no AST extraction needed).
"""

import random
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event import Event
from scenario_generation import (
    BlockConfig,
    ScenarioConfig,
    add_scenario_phase,
    choices,
    distribute_events,
    generate_scenario,
    get_events_from_scenario,
    get_part_durations,
    get_task_current_state,
    part_duration_sec,
    reduce,
    write_scenario_file,
)


# ── Dataclass tests ─────────────────────────────────────────────────────────


class TestBlockConfig:
    """Test BlockConfig dataclass."""

    def test_defaults(self):
        b = BlockConfig()
        assert b.duration_sec == 60
        assert b.plugins == {}

    def test_custom_values(self):
        b = BlockConfig(duration_sec=120, plugins={"track": 0.5, "sysmon": 0.3})
        assert b.duration_sec == 120
        assert b.plugins["track"] == 0.5
        assert b.plugins["sysmon"] == 0.3


class TestScenarioConfig:
    """Test ScenarioConfig dataclass."""

    def test_defaults(self):
        c = ScenarioConfig()
        assert c.scenario_name == "three_load_levels"
        assert c.events_refractory_duration == 1
        assert c.communications_target_ratio == 0.50
        assert c.average_auditory_prompt_duration == 13
        assert c.blocks == []

    def test_with_blocks(self):
        blocks = [BlockConfig(60, {"track": 0.25}), BlockConfig(90, {"sysmon": 0.5})]
        c = ScenarioConfig(blocks=blocks)
        assert len(c.blocks) == 2
        assert c.blocks[0].duration_sec == 60
        assert c.blocks[1].plugins["sysmon"] == 0.5


# ── Pure function tests (ported from test_scenario_generator.py) ─────────


class TestReduce:
    """Test GCD-based fraction simplification."""

    def test_coprime(self):
        assert reduce(3, 7) == (3, 7)

    def test_common_factor(self):
        assert reduce(4, 6) == (2, 3)

    def test_equal_numbers(self):
        assert reduce(5, 5) == (1, 1)

    def test_one_divides_other(self):
        assert reduce(3, 9) == (1, 3)

    def test_large_numbers(self):
        assert reduce(50, 100) == (1, 2)

    def test_typical_comm_ratio(self):
        assert reduce(50, 100) == (1, 2)


class TestChoices:
    """Test selection with repetition from a list."""

    def test_returns_k_items(self):
        random.seed(42)
        result = choices(["a", "b", "c"], 5, False)
        assert len(result) == 5

    def test_all_from_source(self):
        random.seed(42)
        result = choices(["a", "b", "c"], 10, False)
        assert all(item in ["a", "b", "c"] for item in result)

    def test_wraps_around(self):
        random.seed(42)
        result = choices(["x", "y"], 6, False)
        assert len(result) == 6
        assert all(item in ["x", "y"] for item in result)

    def test_single_element(self):
        result = choices(["only"], 3, False)
        assert result == ["only", "only", "only"]


class TestGetPartDurations:
    """Test random duration partitioning."""

    def test_correct_count(self):
        random.seed(42)
        parts = get_part_durations(60, 4)
        assert len(parts) == 4

    def test_sum_equals_total(self):
        random.seed(42)
        parts = get_part_durations(60, 4)
        assert sum(parts) == 60

    def test_all_non_negative(self):
        random.seed(42)
        parts = get_part_durations(100, 5)
        assert all(p >= 0 for p in parts)

    def test_single_part(self):
        parts = get_part_durations(30, 1)
        assert len(parts) == 1
        assert sum(parts) == 30


class TestGetEventsFromScenario:
    """Test filtering Event objects from mixed lists."""

    def test_filters_events(self):
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
        assert get_events_from_scenario([]) == []

    def test_no_events(self):
        lines = ["# Comment", "Block n° 1"]
        assert get_events_from_scenario(lines) == []

    def test_all_events(self):
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["stop"]),
        ]
        result = get_events_from_scenario(lines)
        assert len(result) == 2


class TestGetTaskCurrentState:
    """Test retrieving the last relevant command for a plugin."""

    def test_returns_last_start(self):
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["pause"]),
        ]
        result = get_task_current_state(lines, "sysmon")
        assert result == ["pause"]

    def test_returns_none_for_empty(self):
        assert get_task_current_state([], "sysmon") is None

    def test_filters_by_plugin(self):
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "track", ["start"]),
            Event(3, 20, "track", ["pause"]),
        ]
        result = get_task_current_state(lines, "track")
        assert result == ["pause"]

    def test_ignores_non_state_commands(self):
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 10, "sysmon", ["scales-s1-failure", "True"]),
        ]
        result = get_task_current_state(lines, "sysmon")
        assert result == ["start"]

    def test_no_matching_plugin(self):
        lines = [Event(1, 0, "sysmon", ["start"])]
        assert get_task_current_state(lines, "track") is None

    def test_only_parameter_events(self):
        lines = [
            Event(1, 0, "sysmon", ["title", "New"]),
            Event(2, 10, "sysmon", ["taskupdatetime", "200"]),
        ]
        assert get_task_current_state(lines, "sysmon") is None


class TestDistributeEvents:
    """Test distribute_events with explicit step_duration_sec parameter."""

    def test_line_numbers_are_unique_and_incrementing(self):
        random.seed(42)
        lines = [Event(1, 0, "sysmon", ["start"])]
        cmd_list = [["scales-s1-failure", True], ["scales-s2-failure", True]]
        result = distribute_events(lines, 0, 5.0, cmd_list, "sysmon", 60)
        events = get_events_from_scenario(result)
        line_numbers = [e.line for e in events]
        assert len(line_numbers) == len(set(line_numbers))
        assert line_numbers == sorted(line_numbers)

    def test_works_with_trailing_string(self):
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
        random.seed(42)
        lines = [
            "# Header comment",
            Event(5, 0, "sysmon", ["start"]),
            "# Block description",
        ]
        cmd_list = [["scales-s1-failure", True]]
        result = distribute_events(lines, 0, 5.0, cmd_list, "sysmon", 60)
        events = get_events_from_scenario(result)
        assert events[-1].line == 6

    def test_respects_step_duration(self):
        """Events fit within step_duration_sec."""
        random.seed(42)
        lines = [Event(1, 0, "sysmon", ["start"])]
        cmd_list = [["scales-s1-failure", True], ["scales-s2-failure", True]]
        result = distribute_events(lines, 10, 5.0, cmd_list, "sysmon", 120)
        events = get_events_from_scenario(result)
        # All event onset times should be >= start_sec
        for e in events[1:]:  # Skip the initial "start" event
            assert e.time_sec >= 10


class TestAddScenarioPhase:
    """Test add_scenario_phase with explicit plugins/config/block_duration parameters."""

    def _make_config(self):
        return ScenarioConfig(
            events_refractory_duration=1,
            communications_target_ratio=0.50,
            average_auditory_prompt_duration=13,
        )

    def _make_plugins(self):
        return {"track": None, "sysmon": None, "communications": None, "resman": None}

    def test_start_line_increments_for_track(self):
        lines = []
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 0, self._make_plugins(), self._make_config(), 60)
        events = get_events_from_scenario(result)
        assert len(events) == 2
        assert events[0].line != events[1].line
        assert events[1].line > events[0].line

    def test_active_plugin_gets_paused_when_not_desired(self):
        lines = [Event(1, 0, "sysmon", ["start"])]
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        sysmon_events = [e for e in get_events_from_scenario(result) if e.plugin == "sysmon"]
        assert len(sysmon_events) == 3
        assert sysmon_events[1].command == ["pause"]
        assert sysmon_events[2].command == ["hide"]

    def test_paused_plugin_gets_resumed(self):
        lines = [
            Event(1, 0, "track", ["start"]),
            Event(2, 30, "track", ["pause"]),
        ]
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        track_events = [e for e in get_events_from_scenario(result) if e.plugin == "track"]
        assert len(track_events) == 5
        assert track_events[2].command == ["show"]
        assert track_events[3].command == ["resume"]

    def test_inactive_plugin_not_paused(self):
        lines = []
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 0, self._make_plugins(), self._make_config(), 60)
        sysmon_events = [e for e in get_events_from_scenario(result) if e.plugin == "sysmon"]
        assert len(sysmon_events) == 0

    def test_all_line_numbers_unique(self):
        lines = [Event(1, 0, "sysmon", ["start"])]
        phase_tuples = (("track", 0.5),)
        result = add_scenario_phase(lines, phase_tuples, 60, self._make_plugins(), self._make_config(), 60)
        events = get_events_from_scenario(result)
        line_numbers = [e.line for e in events]
        assert len(line_numbers) == len(set(line_numbers))


# ── Stop pattern tests ───────────────────────────────────────────────────────


class TestStopTasksPattern:
    """Test the pattern used in generate_scenario for stopping tasks."""

    def test_get_events_ignores_trailing_strings(self):
        lines = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 60, "sysmon", ["stop"]),
            "# End of scenario",
        ]
        events = get_events_from_scenario(lines)
        assert events[-1].line == 2

    def test_stop_pattern_line_numbering(self):
        lines = [
            "# Block 1",
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 0, "track", ["start"]),
            "# Block 2",
            Event(3, 60, "sysmon", ["scales-s1-failure", True]),
        ]
        scenario_events = get_events_from_scenario(lines)
        start_line = scenario_events[-1].line + 1 if len(scenario_events) != 0 else 1
        task_names = set(e.plugin for e in scenario_events)
        for task in sorted(task_names):
            lines.append(Event(start_line, 120, task, "stop"))
            start_line += 1
        stop_events = [e for e in get_events_from_scenario(lines) if e.command == ["stop"]]
        stop_lines = [e.line for e in stop_events]
        assert len(stop_lines) == len(set(stop_lines))
        assert stop_lines[0] == 4


# ── generate_scenario tests ─────────────────────────────────────────────────


class TestGenerateScenario:
    """Test full scenario generation."""

    def _make_plugins(self):
        """Return plugin mocks — only track is used in track-only tests (None suffices).
        For tests involving sysmon/comms/resman, use _make_full_plugins()."""
        return {"track": None, "sysmon": None, "communications": None, "resman": None}

    def _make_full_plugins(self):
        """Return plugin mocks with realistic parameter structures."""
        sysmon = MagicMock()
        sysmon.parameters = {
            "alerttimeout": 10000,
            "lights": {"1": {}, "2": {}},
            "scales": {"1": {}, "2": {}},
        }
        comms = MagicMock()
        resman = MagicMock()
        resman.parameters = {
            "pump": {
                "1": {"flow": 800}, "2": {"flow": 600},
                "3": {"flow": 800}, "4": {"flow": 600},
                "5": {"flow": 400}, "6": {"flow": 400},
            },
            "tank": {
                "a": {"target": 2500}, "b": {"target": 2500},
                "c": {"target": None}, "d": {"target": None},
            },
        }
        return {"track": None, "sysmon": sysmon, "communications": comms, "resman": resman}

    def test_track_only_blocks(self):
        """Generate scenario with track-only blocks."""
        config = ScenarioConfig(
            blocks=[
                BlockConfig(60, {"track": 0.25}),
                BlockConfig(60, {"track": 0.50}),
                BlockConfig(60, {"track": 0.85}),
            ]
        )
        result = generate_scenario(config, self._make_plugins())
        events = get_events_from_scenario(result)
        # Must have start events, targetproportion events, and stop events
        assert len(events) > 0
        start_events = [e for e in events if e.command == ["start"]]
        stop_events = [e for e in events if e.command == ["stop"]]
        assert len(start_events) >= 1
        assert len(stop_events) >= 1
        # All line numbers unique
        line_numbers = [e.line for e in events]
        assert len(line_numbers) == len(set(line_numbers))

    def test_empty_blocks(self):
        """Empty block list produces no events."""
        config = ScenarioConfig(blocks=[])
        result = generate_scenario(config, self._make_plugins())
        assert result == []

    def test_partial_plugins(self):
        """Blocks with only some plugins active produce pause/hide for others."""
        config = ScenarioConfig(
            blocks=[
                BlockConfig(60, {"track": 0.5, "sysmon": 0.5}),
                BlockConfig(60, {"track": 0.5}),  # sysmon removed
            ]
        )
        plugins = self._make_full_plugins()
        result = generate_scenario(config, plugins)
        events = get_events_from_scenario(result)
        # sysmon should have start in block 1, then pause+hide in block 2
        sysmon_events = [e for e in events if e.plugin == "sysmon"]
        commands = [e.command for e in sysmon_events]
        assert ["start"] in commands
        assert ["pause"] in commands
        assert ["hide"] in commands

    def test_stop_events_at_end(self):
        """All active plugins receive a stop event at the end."""
        config = ScenarioConfig(
            blocks=[BlockConfig(60, {"track": 0.25})]
        )
        result = generate_scenario(config, self._make_plugins())
        events = get_events_from_scenario(result)
        stop_events = [e for e in events if e.command == ["stop"]]
        assert len(stop_events) >= 1
        # Stop time = sum of block durations
        for e in stop_events:
            assert e.time_sec == 60

    def test_block_comments_present(self):
        """Each block has a comment string in the output."""
        config = ScenarioConfig(
            blocks=[
                BlockConfig(60, {"track": 0.25}),
                BlockConfig(60, {"track": 0.50}),
            ]
        )
        result = generate_scenario(config, self._make_plugins())
        comments = [l for l in result if isinstance(l, str)]
        assert len(comments) == 2
        assert "Block" in comments[0]
        assert "Block" in comments[1]

    def test_multiple_blocks_timing(self):
        """Start times are cumulative across blocks."""
        config = ScenarioConfig(
            blocks=[
                BlockConfig(60, {"track": 0.25}),
                BlockConfig(90, {"track": 0.50}),
            ]
        )
        result = generate_scenario(config, self._make_plugins())
        events = get_events_from_scenario(result)
        # Block 2 events should start at t=60
        # Find the targetproportion for block 2 (the second one)
        tp_events = [e for e in events if e.command[0] == "targetproportion"]
        assert len(tp_events) == 2
        assert tp_events[1].time_sec == 60  # block 2 starts at 60


# ── write_scenario_file tests ───────────────────────────────────────────────


class TestWriteScenarioFile:
    """Test scenario file writing."""

    def test_writes_file(self, tmp_path):
        """File is created with correct format."""
        config = ScenarioConfig(scenario_name="test_scenario")
        lines = [
            "Block n° 1. Technical load = 25.0 %",
            Event(1, 0, "track", ["start"]),
            Event(2, 0, "track", ["targetproportion", 0.75]),
            Event(3, 60, "track", ["stop"]),
        ]
        with patch.dict("scenario_generation.PATHS", {"SCENARIOS": tmp_path}):
            path = write_scenario_file(lines, config)
        assert path.exists()
        content = path.read_text()
        assert "# OpenMATB scenario generator" in content
        assert "# Name: test_scenario" in content
        assert "track" in content
        assert "start" in content

    def test_returns_path(self, tmp_path):
        """Returns a Path object."""
        config = ScenarioConfig(scenario_name="test_output")
        lines = [Event(1, 0, "track", ["start"])]
        with patch.dict("scenario_generation.PATHS", {"SCENARIOS": tmp_path}):
            path = write_scenario_file(lines, config)
        assert isinstance(path, Path)
        assert "test_output" in path.name

