"""Tests for core.logreader - CSV session parsing logic."""

from unittest.mock import patch, MagicMock
from core.event import Event
from core.logreader import LogReader, IGNORE_PLUGINS


def _make_logreader(**overrides):
    """Create a LogReader without running __init__."""
    lr = object.__new__(LogReader)
    lr.line_n = 0
    lr.session_file_path = None
    lr.replay_session_id = None
    lr.contents = []
    lr.inputs = []
    lr.states = []
    lr.start_sec = 0
    lr.end_sec = 0
    lr.duration_sec = 0
    lr.keyboard_inputs = []
    lr.joystick_inputs = []
    lr.__dict__.update(overrides)
    return lr


# ── session_event_to_str ─────────────────────────


class TestSessionEventToStr:
    def test_self_address(self):
        """'self' address formats as simple plugin;command."""
        lr = _make_logreader()
        row = {
            'scenario_time': '60.5',
            'module': 'sysmon',
            'address': 'self',
            'value': 'start'
        }
        result = lr.session_event_to_str(row)
        assert 'sysmon' in result
        assert 'start' in result
        assert lr.line_n == 1

    def test_param_address(self):
        """Non-self address formats as plugin;address;value."""
        lr = _make_logreader()
        row = {
            'scenario_time': '120.0',
            'module': 'resman',
            'address': 'pump-1-state',
            'value': 'on'
        }
        result = lr.session_event_to_str(row)
        assert 'resman' in result
        assert 'pump-1-state' in result
        assert 'on' in result

    def test_line_counter_increments(self):
        """Line counter advances on each call."""
        lr = _make_logreader()
        row = {'scenario_time': '0.0', 'module': 'test', 'address': 'self', 'value': 'start'}
        lr.session_event_to_str(row)
        lr.session_event_to_str(row)
        assert lr.line_n == 2

    def test_time_conversion(self):
        """Seconds are formatted as H:MM:SS."""
        lr = _make_logreader()
        row = {
            'scenario_time': '3723.0',
            'module': 'test',
            'address': 'self',
            'value': 'stop'
        }
        result = lr.session_event_to_str(row)
        # 3723 seconds = 1:02:03
        assert '1:02:03' in result

    def test_fractional_time_truncated(self):
        """Fractional seconds are truncated to int."""
        lr = _make_logreader()
        row = {'scenario_time': '65.9', 'module': 'test', 'address': 'self', 'value': 'stop'}
        result = lr.session_event_to_str(row)
        # 65 seconds = 0:01:05
        assert '0:01:05' in result

    def test_returns_event_line_string(self):
        """Result is a valid Event line string (H:MM:SS;plugin;command)."""
        lr = _make_logreader()
        row = {'scenario_time': '0.0', 'module': 'sysmon', 'address': 'self', 'value': 'start'}
        result = lr.session_event_to_str(row)
        assert result == '0:00:00;sysmon;start'

    def test_param_event_line_string(self):
        """Parameterized event produces correct line string."""
        lr = _make_logreader()
        row = {'scenario_time': '150.0', 'module': 'resman', 'address': 'pump-1-state', 'value': 'on'}
        result = lr.session_event_to_str(row)
        assert result == '0:02:30;resman;pump-1-state;on'


# ── reload_session ───────────────────────────────


class TestReloadSession:
    def test_no_file_path_returns_early(self):
        """reload_session with no file path does nothing."""
        lr = _make_logreader(session_file_path=None)
        lr.reload_session()
        # Should not crash, attributes unchanged
        assert lr.contents == []

    def test_parses_event_rows(self, tmp_path):
        """Event rows are converted and added to contents."""
        csv_file = tmp_path / 'session.csv'
        # First data row is consumed by next(reader), so we need 3 event rows
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.000,0.0,event,sysmon,self,start\n'
            '0.001,30.0,event,sysmon,self,pause\n'
            '0.002,60.0,event,resman,pump-1-state,on\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.contents) == 2
        assert 'sysmon' in lr.contents[0]
        assert 'pump-1-state' in lr.contents[1]

    def test_parses_keyboard_inputs(self, tmp_path):
        """Keyboard input rows go into inputs and keyboard_inputs."""
        csv_file = tmp_path / 'session.csv'
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.001,0.0,event,sysmon,self,start\n'
            '0.002,5.0,input,keyboard,F1,press\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.keyboard_inputs) == 1
        assert lr.keyboard_inputs[0]['address'] == 'F1'

    def test_parses_joystick_inputs(self, tmp_path):
        """Joystick input rows go into joystick_inputs."""
        csv_file = tmp_path / 'session.csv'
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.001,0.0,event,track,self,start\n'
            '0.002,5.0,input,device,joystick_x,0.5\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.joystick_inputs) == 1

    def test_ignores_blacklisted_plugins(self, tmp_path):
        """Events from IGNORE_PLUGINS are skipped."""
        csv_file = tmp_path / 'session.csv'
        # First data row consumed by next(reader), so add dummy first row
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.000,0.0,event,sysmon,self,start\n'
            '0.001,5.0,event,sysmon,self,pause\n'
            '0.002,8.0,event,parallelport,self,start\n'
            '0.003,10.0,event,sysmon,self,stop\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.contents) == 2  # parallelport skipped

    def test_end_sec_from_last_row(self, tmp_path):
        """end_sec is set from the last row's scenario_time."""
        csv_file = tmp_path / 'session.csv'
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.001,0.0,event,sysmon,self,start\n'
            '0.002,300.0,event,sysmon,self,stop\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.end_sec == 300.0
        assert lr.duration_sec == 300.0

    def test_parses_state_rows(self, tmp_path):
        """State rows with matching address patterns are parsed."""
        csv_file = tmp_path / 'session.csv'
        # Use proper CSV quoting for values containing commas
        csv_file.write_text(
            'logtime,scenario_time,type,module,address,value\n'
            '0.000,0.0,event,sysmon,self,start\n'
            '0.002,5.0,state,communications,radio_frequency,"(110.0,)"\n'
            '0.003,10.0,event,sysmon,self,stop\n'
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.states) == 1
        assert lr.states[0]['value'] == (110.0,)


# ── IGNORE_PLUGINS constant ─────────────────────


class TestIgnorePlugins:
    def test_contains_expected_plugins(self):
        """Blacklist includes hardware and UI-only plugins."""
        assert 'labstreaminglayer' in IGNORE_PLUGINS
        assert 'parallelport' in IGNORE_PLUGINS
        assert 'genericscales' in IGNORE_PLUGINS
        assert 'instructions' in IGNORE_PLUGINS

    def test_does_not_contain_logic_plugins(self):
        """Core logic plugins are not blacklisted."""
        assert 'sysmon' not in IGNORE_PLUGINS
        assert 'track' not in IGNORE_PLUGINS
        assert 'resman' not in IGNORE_PLUGINS
        assert 'communications' not in IGNORE_PLUGINS
