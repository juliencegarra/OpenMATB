"""Tests for scenario_generator - Pure helper functions.

The scenario_generator.py module performs heavy initialization at import time
(creates a Window, instantiates plugins). To test its pure functions without
triggering that initialization, we extract function definitions via AST parsing.
"""

import ast
import random
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from core.event import Event

# ──────────────────────────────────────────────
# Extract pure functions from scenario_generator.py
# without executing module-level initialization code
# ──────────────────────────────────────────────

_source_path = Path(__file__).parent.parent / 'scenario_generator.py'
_source = _source_path.read_text()
_tree = ast.parse(_source)

# Namespace with dependencies needed by the functions
_ns = {
    '__builtins__': __builtins__,
    'Event': Event,
    'randint': random.randint,
    'shuffle': random.shuffle,
    'random': random.random,
    'EVENTS_REFRACTORY_DURATION': 1,
    'STEP_DURATION_SEC': 60,
}

# Compile and exec each function definition in isolation
for _node in _tree.body:
    if isinstance(_node, ast.FunctionDef):
        _func_code = compile(
            ast.Module(body=[_node], type_ignores=[]),
            str(_source_path), 'exec'
        )
        exec(_func_code, _ns)

# Bind the extracted functions
reduce = _ns['reduce']
choices = _ns['choices']
part_duration_sec = _ns['part_duration_sec']
get_part_durations = _ns['get_part_durations']
get_events_from_scenario = _ns['get_events_from_scenario']
get_task_current_state = _ns['get_task_current_state']


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
        # Used for COMMUNICATIONS_TARGET_RATIO * 100 = 50
        assert reduce(50, 100) == (1, 2)


class TestChoices:
    """Test selection with repetition from a list."""

    def test_returns_k_items(self):
        """Returns exactly k items."""
        random.seed(42)
        result = choices(['a', 'b', 'c'], 5, False)
        assert len(result) == 5

    def test_all_from_source(self):
        """All items come from the source list."""
        random.seed(42)
        result = choices(['a', 'b', 'c'], 10, False)
        assert all(item in ['a', 'b', 'c'] for item in result)

    def test_wraps_around(self):
        """Wraps when k exceeds list length."""
        random.seed(42)
        # k > len(l) requires wrapping
        result = choices(['x', 'y'], 6, False)
        assert len(result) == 6
        assert all(item in ['x', 'y'] for item in result)

    def test_single_element(self):
        """Single-element list repeats k times."""
        result = choices(['only'], 3, False)
        assert result == ['only', 'only', 'only']


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
            '# Comment',
            Event(1, 0, 'sysmon', ['start']),
            'Block n° 1',
            Event(2, 10, 'track', ['start']),
        ]
        result = get_events_from_scenario(lines)
        assert len(result) == 2
        assert all(isinstance(e, Event) for e in result)

    def test_empty_list(self):
        """Empty input returns empty list."""
        assert get_events_from_scenario([]) == []

    def test_no_events(self):
        """List with no Events returns empty."""
        lines = ['# Comment', 'Block n° 1']
        assert get_events_from_scenario(lines) == []

    def test_all_events(self):
        """All-Event list returned as-is."""
        lines = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'sysmon', ['stop']),
        ]
        result = get_events_from_scenario(lines)
        assert len(result) == 2


class TestGetTaskCurrentState:
    """Test retrieving the last relevant command for a plugin."""

    def test_returns_last_start(self):
        """Returns the last state command for a plugin."""
        lines = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'sysmon', ['pause']),
        ]
        result = get_task_current_state(lines, 'sysmon')
        assert result == ['pause']

    def test_returns_none_for_empty(self):
        """Empty list returns None."""
        result = get_task_current_state([], 'sysmon')
        assert result is None

    def test_filters_by_plugin(self):
        """Only considers events for the given plugin."""
        lines = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'track', ['start']),
            Event(3, 20, 'track', ['pause']),
        ]
        result = get_task_current_state(lines, 'track')
        assert result == ['pause']

    def test_ignores_non_state_commands(self):
        """Ignores parameter-setting commands."""
        lines = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'sysmon', ['scales-s1-failure', 'True']),
        ]
        # Only start/pause/resume are kept as state commands
        result = get_task_current_state(lines, 'sysmon')
        assert result == ['start']

    def test_no_matching_plugin(self):
        """Returns None when plugin is absent."""
        lines = [Event(1, 0, 'sysmon', ['start'])]
        result = get_task_current_state(lines, 'track')
        assert result is None

    def test_only_parameter_events(self):
        """Returns None when only parameter events exist."""
        lines = [
            Event(1, 0, 'sysmon', ['title', 'New']),
            Event(2, 10, 'sysmon', ['taskupdatetime', '200']),
        ]
        # No start/pause/resume => None
        result = get_task_current_state(lines, 'sysmon')
        assert result is None
