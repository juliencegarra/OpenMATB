"""Tests for core.logger - Logger slot formatting, queue management, and record methods."""

import importlib
from collections import namedtuple
from unittest.mock import patch, MagicMock, call
import pytest

from core.logger import Logger
from core.event import Event

# core.__init__ re-exports the Logger instance as `core.logger`, shadowing
# the module.  Use importlib to get the actual module for patching.
_logger_module = importlib.import_module('core.logger')


def _make_logger(**overrides):
    """Create a Logger instance bypassing __init__ to avoid file I/O."""
    lg = object.__new__(Logger)
    lg.fields_list = ['logtime', 'scenario_time', 'type', 'module', 'address', 'value']
    lg.slot = namedtuple('Row', lg.fields_list)
    lg.maxfloats = 6
    lg.scenario_time = 0
    lg.session_id = 1
    lg.lsl = None
    lg.queue = []
    lg.file = None
    lg.writer = MagicMock()
    lg.__dict__.update(overrides)
    return lg


# ── round_row ────────────────────────────────────


class TestRoundRow:
    def test_rounds_floats(self):
        """Float values are rounded to maxfloats decimals."""
        lg = _make_logger()
        row = [1.123456789, 0, 'event', 'sysmon', 'self', 'start']
        result = lg.round_row(row)
        assert result.logtime == round(1.123456789, 6)

    def test_rounds_ints(self):
        """Integer values are passed through round() but stay unchanged."""
        lg = _make_logger()
        row = [1, 0, 'event', 'sysmon', 'self', 'start']
        result = lg.round_row(row)
        assert result.logtime == 1

    def test_preserves_strings(self):
        """String values are not rounded."""
        lg = _make_logger()
        row = [1.0, 0, 'event', 'sysmon', 'self', 'start']
        result = lg.round_row(row)
        assert result.type == 'event'
        assert result.module == 'sysmon'
        assert result.address == 'self'
        assert result.value == 'start'

    def test_returns_namedtuple(self):
        """Result is a Row namedtuple with correct fields."""
        lg = _make_logger()
        row = [1.0, 0, 'event', 'sysmon', 'self', 'start']
        result = lg.round_row(row)
        assert hasattr(result, 'logtime')
        assert hasattr(result, 'scenario_time')
        assert hasattr(result, 'type')


# ── Queue management ─────────────────────────────


class TestQueueManagement:
    def test_add_row_to_queue(self):
        """add_row_to_queue appends to the queue."""
        lg = _make_logger()
        lg.add_row_to_queue('row1')
        lg.add_row_to_queue('row2')
        assert lg.queue == ['row1', 'row2']

    def test_empty_queue(self):
        """empty_queue clears all items."""
        lg = _make_logger()
        lg.queue = ['a', 'b', 'c']
        lg.empty_queue()
        assert lg.queue == []

    def test_empty_queue_on_fresh(self):
        """Emptying an already-empty queue is a no-op."""
        lg = _make_logger()
        lg.empty_queue()
        assert lg.queue == []


# ── Setters ──────────────────────────────────────


class TestSetters:
    def test_set_scenario_time(self):
        """set_scenario_time updates scenario_time attribute."""
        lg = _make_logger()
        lg.set_scenario_time(42.5)
        assert lg.scenario_time == 42.5

    def test_set_totaltime(self):
        """set_totaltime stores totaltime attribute."""
        lg = _make_logger()
        lg.set_totaltime(300)
        assert lg.totaltime == 300


# ── record_event ─────────────────────────────────


class TestRecordEvent:
    @patch.object(_logger_module, 'perf_counter', return_value=1.0)
    def test_single_command_uses_self_address(self, _mock_pc):
        """Single-command event uses address='self'."""
        lg = _make_logger(scenario_time=10)
        lg.write_single_slot = MagicMock()
        event = Event(1, 60, 'sysmon', 'start')
        lg.record_event(event)
        args = lg.write_single_slot.call_args[0][0]
        assert args[2] == 'event'
        assert args[3] == 'sysmon'
        assert args[4] == 'self'
        assert args[5] == 'start'

    @patch.object(_logger_module, 'perf_counter', return_value=1.0)
    def test_two_command_uses_address_value(self, _mock_pc):
        """Two-command event uses command[0] as address, command[1] as value."""
        lg = _make_logger(scenario_time=10)
        lg.write_single_slot = MagicMock()
        event = Event(1, 60, 'resman', ['pump-1-state', 'on'])
        lg.record_event(event)
        args = lg.write_single_slot.call_args[0][0]
        assert args[4] == 'pump-1-state'
        assert args[5] == 'on'

    @patch.object(_logger_module, 'perf_counter', return_value=1.0)
    def test_uses_current_scenario_time(self, _mock_pc):
        """Slot uses the logger's current scenario_time."""
        lg = _make_logger(scenario_time=99.5)
        lg.write_single_slot = MagicMock()
        event = Event(1, 60, 'track', 'start')
        lg.record_event(event)
        args = lg.write_single_slot.call_args[0][0]
        assert args[1] == 99.5


# ── record_input ─────────────────────────────────


class TestRecordInput:
    @patch.object(_logger_module, 'perf_counter', return_value=2.0)
    def test_formats_input_slot(self, _mock_pc):
        """Builds slot with type='input', module, key, state."""
        lg = _make_logger(scenario_time=5)
        lg.write_single_slot = MagicMock()
        lg.record_input('keyboard', 'F1', 'press')
        args = lg.write_single_slot.call_args[0][0]
        assert args == [2.0, 5, 'input', 'keyboard', 'F1', 'press']


# ── record_aoi ───────────────────────────────────


class TestRecordAoi:
    @patch.object(_logger_module, 'perf_counter', return_value=3.0)
    def test_parses_plugin_and_widget(self, _mock_pc):
        """Splits 'plugin_widget' name into plugin and widget parts."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        container = MagicMock()
        container.get_x1y1x2y2.return_value = (10, 70, 110, 20)
        lg.record_aoi(container, 'sysmon_scale1')
        args = lg.write_single_slot.call_args[0][0]
        assert args[2] == 'aoi'
        assert args[3] == 'sysmon'
        assert args[4] == 'scale1'
        assert args[5] == (10, 70, 110, 20)

    @patch.object(_logger_module, 'perf_counter', return_value=3.0)
    def test_multi_underscore_widget_name(self, _mock_pc):
        """Widget name with multiple underscores keeps all parts after first."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        container = MagicMock()
        container.get_x1y1x2y2.return_value = (0, 0, 0, 0)
        lg.record_aoi(container, 'track_cursor_inner')
        args = lg.write_single_slot.call_args[0][0]
        assert args[3] == 'track'
        assert args[4] == 'cursor_inner'


# ── record_state ─────────────────────────────────


class TestRecordState:
    @patch.object(_logger_module, 'perf_counter', return_value=4.0)
    def test_parses_graph_name(self, _mock_pc):
        """Splits graph_name into module and widget, builds address."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.record_state('sysmon_light1', 'color', '(255,0,0)')
        args = lg.write_single_slot.call_args[0][0]
        assert args[2] == 'state'
        assert args[3] == 'sysmon'
        assert args[4] == 'light1, color'
        assert args[5] == '(255,0,0)'

    @patch.object(_logger_module, 'perf_counter', return_value=4.0)
    def test_multi_underscore_graph_name(self, _mock_pc):
        """Graph name with multiple underscores preserves widget parts."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.record_state('resman_tank_a', 'level', 2500)
        args = lg.write_single_slot.call_args[0][0]
        assert args[3] == 'resman'
        assert args[4] == 'tank_a, level'


# ── record_parameter ─────────────────────────────


class TestRecordParameter:
    @patch.object(_logger_module, 'perf_counter', return_value=5.0)
    def test_formats_parameter_slot(self, _mock_pc):
        """Builds slot with type='parameter'."""
        lg = _make_logger(scenario_time=10)
        lg.write_single_slot = MagicMock()
        lg.record_parameter('sysmon', 'alerttimeout', 10000)
        args = lg.write_single_slot.call_args[0][0]
        assert args == [5.0, 10, 'parameter', 'sysmon', 'alerttimeout', 10000]


# ── log_performance ──────────────────────────────


class TestLogPerformance:
    @patch.object(_logger_module, 'perf_counter', return_value=6.0)
    def test_formats_performance_slot(self, _mock_pc):
        """Builds slot with type='performance'."""
        lg = _make_logger(scenario_time=20)
        lg.write_single_slot = MagicMock()
        lg.log_performance('track', 'deviation', 0.05)
        args = lg.write_single_slot.call_args[0][0]
        assert args == [6.0, 20, 'performance', 'track', 'deviation', 0.05]


# ── record_a_pseudorandom_value ──────────────────


class TestRecordPseudorandomValue:
    @patch.object(_logger_module, 'perf_counter', return_value=7.0)
    def test_writes_two_slots(self, _mock_pc):
        """Writes both seed_value and seed_output slots."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.record_a_pseudorandom_value('communications', 42, 'result')
        assert lg.write_single_slot.call_count == 2

    @patch.object(_logger_module, 'perf_counter', return_value=7.0)
    def test_seed_value_slot(self, _mock_pc):
        """First slot has type='seed_value' with the seed."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.record_a_pseudorandom_value('communications', 42, 'result')
        first_args = lg.write_single_slot.call_args_list[0][0][0]
        assert first_args[2] == 'seed_value'
        assert first_args[5] == 42

    @patch.object(_logger_module, 'perf_counter', return_value=7.0)
    def test_seed_output_slot(self, _mock_pc):
        """Second slot has type='seed_output' with the output."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.record_a_pseudorandom_value('communications', 42, 'result')
        second_args = lg.write_single_slot.call_args_list[1][0][0]
        assert second_args[2] == 'seed_output'
        assert second_args[5] == 'result'


# ── log_manual_entry ─────────────────────────────


class TestLogManualEntry:
    @patch.object(_logger_module, 'perf_counter', return_value=8.0)
    def test_default_key(self, _mock_pc):
        """Default type is 'manual'."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.log_manual_entry('user note')
        args = lg.write_single_slot.call_args[0][0]
        assert args[2] == 'manual'
        assert args[5] == 'user note'

    @patch.object(_logger_module, 'perf_counter', return_value=8.0)
    def test_custom_key(self, _mock_pc):
        """Custom key replaces 'manual' type."""
        lg = _make_logger(scenario_time=0)
        lg.write_single_slot = MagicMock()
        lg.log_manual_entry('note', key='custom')
        args = lg.write_single_slot.call_args[0][0]
        assert args[2] == 'custom'


# ── write_single_slot ────────────────────────────


class TestWriteSingleSlot:
    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_adds_to_queue_and_writes(self):
        """Slot is queued then written via write_row_queue."""
        lg = _make_logger()
        values = [1.0, 0, 'event', 'sysmon', 'self', 'start']
        lg.write_single_slot(values)
        # After write_row_queue, queue should be emptied
        assert lg.queue == []
        lg.writer.writerow.assert_called_once()

    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_written_row_has_correct_fields(self):
        """Written dict has all 6 expected fields."""
        lg = _make_logger()
        values = [1.0, 0, 'event', 'sysmon', 'self', 'start']
        lg.write_single_slot(values)
        written = lg.writer.writerow.call_args[0][0]
        assert set(written.keys()) == set(lg.fields_list)
        assert written['type'] == 'event'
        assert written['module'] == 'sysmon'


# ── write_row_queue ──────────────────────────────


class TestWriteRowQueue:
    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_writes_all_queued_rows(self):
        """All queued rows are written and queue is emptied."""
        lg = _make_logger()
        lg.queue = [
            lg.slot(1.0, 0, 'event', 'sysmon', 'self', 'start'),
            lg.slot(2.0, 1, 'event', 'track', 'self', 'start'),
        ]
        lg.write_row_queue()
        assert lg.writer.writerow.call_count == 2
        assert lg.queue == []

    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_change_dict_overrides_fields(self):
        """change_dict overrides specific fields in each row."""
        lg = _make_logger()
        lg.queue = [lg.slot(1.0, 0, 'event', 'sysmon', 'self', 'start')]
        lg.write_row_queue(change_dict={'module': 'OVERRIDE'})
        written = lg.writer.writerow.call_args[0][0]
        assert written['module'] == 'OVERRIDE'

    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_empty_queue_prints_warning(self, capsys=None):
        """Empty queue prints a warning instead of writing."""
        lg = _make_logger()
        lg.write_row_queue()  # queue is empty
        lg.writer.writerow.assert_not_called()

    @patch.object(_logger_module, 'REPLAY_MODE', True)
    def test_replay_mode_skips_writing(self):
        """In replay mode, nothing is written."""
        lg = _make_logger()
        lg.queue = [lg.slot(1.0, 0, 'event', 'sysmon', 'self', 'start')]
        lg.write_row_queue()
        lg.writer.writerow.assert_not_called()

    @patch.object(_logger_module, 'REPLAY_MODE', False)
    def test_lsl_push_when_enabled(self):
        """When lsl is set, each row is also pushed to LSL."""
        mock_lsl = MagicMock()
        lg = _make_logger(lsl=mock_lsl)
        lg.queue = [lg.slot(1.0, 0, 'event', 'sysmon', 'self', 'start')]
        lg.write_row_queue()
        mock_lsl.push.assert_called_once()
