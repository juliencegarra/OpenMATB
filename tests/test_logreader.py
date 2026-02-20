"""Tests for core.logreader - CSV session parsing logic."""

from core.logreader import IGNORE_PLUGINS, LogReader


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
    lr.session_duration = 0
    lr.keyboard_inputs = []
    lr.joystick_inputs = []
    lr.blocking_segments = []
    lr._bp_replay_times = [0.0]
    lr._bp_scenario_times = [0.0]
    lr.__dict__.update(overrides)
    return lr


# ── session_event_to_str ─────────────────────────


class TestSessionEventToStr:
    def test_self_address(self):
        """'self' address formats as simple plugin;command."""
        lr = _make_logreader()
        row = {"scenario_time": "60.5", "module": "sysmon", "address": "self", "value": "start"}
        result = lr.session_event_to_str(row)
        assert "sysmon" in result
        assert "start" in result
        assert lr.line_n == 1

    def test_param_address(self):
        """Non-self address formats as plugin;address;value."""
        lr = _make_logreader()
        row = {"scenario_time": "120.0", "module": "resman", "address": "pump-1-state", "value": "on"}
        result = lr.session_event_to_str(row)
        assert "resman" in result
        assert "pump-1-state" in result
        assert "on" in result

    def test_line_counter_increments(self):
        """Line counter advances on each call."""
        lr = _make_logreader()
        row = {"scenario_time": "0.0", "module": "test", "address": "self", "value": "start"}
        lr.session_event_to_str(row)
        lr.session_event_to_str(row)
        assert lr.line_n == 2

    def test_time_conversion(self):
        """Seconds are formatted as H:MM:SS."""
        lr = _make_logreader()
        row = {"scenario_time": "3723.0", "module": "test", "address": "self", "value": "stop"}
        result = lr.session_event_to_str(row)
        # 3723 seconds = 1:02:03
        assert "1:02:03" in result

    def test_fractional_time_truncated(self):
        """Fractional seconds are truncated to int."""
        lr = _make_logreader()
        row = {"scenario_time": "65.9", "module": "test", "address": "self", "value": "stop"}
        result = lr.session_event_to_str(row)
        # 65 seconds = 0:01:05
        assert "0:01:05" in result

    def test_returns_event_line_string(self):
        """Result is a valid Event line string (H:MM:SS;plugin;command)."""
        lr = _make_logreader()
        row = {"scenario_time": "0.0", "module": "sysmon", "address": "self", "value": "start"}
        result = lr.session_event_to_str(row)
        assert result == "0:00:00;sysmon;start"

    def test_param_event_line_string(self):
        """Parameterized event produces correct line string."""
        lr = _make_logreader()
        row = {"scenario_time": "150.0", "module": "resman", "address": "pump-1-state", "value": "on"}
        result = lr.session_event_to_str(row)
        assert result == "0:02:30;resman;pump-1-state;on"


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
        csv_file = tmp_path / "session.csv"
        # First data row is consumed by next(reader), so we need 3 event rows
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.000,0.0,event,sysmon,self,start\n"
            "0.001,30.0,event,sysmon,self,pause\n"
            "0.002,60.0,event,resman,pump-1-state,on\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.contents) == 2
        assert "sysmon" in lr.contents[0]
        assert "pump-1-state" in lr.contents[1]

    def test_parses_keyboard_inputs(self, tmp_path):
        """Keyboard input rows go into inputs and keyboard_inputs."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.001,0.0,event,sysmon,self,start\n"
            "0.002,5.0,input,keyboard,F1,press\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.keyboard_inputs) == 1
        assert lr.keyboard_inputs[0]["address"] == "F1"

    def test_parses_joystick_inputs(self, tmp_path):
        """Joystick input rows go into joystick_inputs."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.001,0.0,event,track,self,start\n"
            "0.002,5.0,input,device,joystick_x,0.5\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.joystick_inputs) == 1

    def test_ignores_blacklisted_plugins(self, tmp_path):
        """Events from IGNORE_PLUGINS are skipped."""
        csv_file = tmp_path / "session.csv"
        # First data row consumed by next(reader), so add dummy first row
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.000,0.0,event,sysmon,self,start\n"
            "0.001,5.0,event,sysmon,self,pause\n"
            "0.002,8.0,event,parallelport,self,start\n"
            "0.003,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.contents) == 2  # parallelport skipped

    def test_end_sec_from_last_row(self, tmp_path):
        """end_sec is set from the last row's scenario_time."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.001,0.0,event,sysmon,self,start\n"
            "0.002,300.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.end_sec == 300.0
        assert lr.duration_sec == 300.0

    def test_parses_state_rows(self, tmp_path):
        """State rows with matching address patterns are parsed."""
        csv_file = tmp_path / "session.csv"
        # Use proper CSV quoting for values containing commas
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.000,0.0,event,sysmon,self,start\n"
            '0.002,5.0,state,communications,radio_frequency,"(110.0,)"\n'
            "0.003,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.states) == 1
        assert lr.states[0]["value"] == (110.0,)

    def test_session_duration_from_logtime(self, tmp_path):
        """session_duration is based on normalized logtime, not scenario_time."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "100.0,0.0,event,sysmon,self,start\n"
            "110.0,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.session_duration == 10.0  # 110 - 100

    def test_normalized_logtime_in_inputs(self, tmp_path):
        """Inputs have normalized_logtime field."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "100.0,0.0,event,sysmon,self,start\n"
            "105.0,5.0,input,keyboard,F1,press\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.keyboard_inputs[0]["normalized_logtime"] == 5.0

    def test_instructions_events_not_ignored(self, tmp_path):
        """Instructions events are now included (not in IGNORE_PLUGINS)."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            "5.0,5.0,event,instructions,self,start\n"
            "10.0,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert any("instructions" in c for c in lr.contents)

    def test_genericscales_events_not_ignored(self, tmp_path):
        """Genericscales events are now included (not in IGNORE_PLUGINS)."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            "5.0,5.0,event,genericscales,self,start\n"
            "10.0,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert any("genericscales" in c for c in lr.contents)


# ── IGNORE_PLUGINS constant ─────────────────────


class TestIgnorePlugins:
    def test_contains_expected_plugins(self):
        """Blacklist includes hardware-only plugins."""
        assert "labstreaminglayer" in IGNORE_PLUGINS
        assert "parallelport" in IGNORE_PLUGINS

    def test_does_not_contain_logic_plugins(self):
        """Core logic plugins are not blacklisted."""
        assert "sysmon" not in IGNORE_PLUGINS
        assert "track" not in IGNORE_PLUGINS
        assert "resman" not in IGNORE_PLUGINS
        assert "communications" not in IGNORE_PLUGINS

    def test_blocking_plugins_not_ignored(self):
        """Blocking plugins (instructions, genericscales) are no longer ignored."""
        assert "genericscales" not in IGNORE_PLUGINS
        assert "instructions" not in IGNORE_PLUGINS


# ── is_in_blocking_segment ───────────────────────


class TestIsInBlockingSegment:
    def test_before_segment(self):
        """Time before any segment returns False."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0)])
        assert lr.is_in_blocking_segment(3.0) is False

    def test_at_segment_start(self):
        """Time exactly at segment start returns True."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0)])
        assert lr.is_in_blocking_segment(5.0) is True

    def test_inside_segment(self):
        """Time inside a segment returns True."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0)])
        assert lr.is_in_blocking_segment(10.0) is True

    def test_at_segment_end(self):
        """Time exactly at segment end returns True."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0)])
        assert lr.is_in_blocking_segment(15.0) is True

    def test_after_segment(self):
        """Time after segment returns False."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0)])
        assert lr.is_in_blocking_segment(16.0) is False

    def test_no_segments(self):
        """No blocking segments always returns False."""
        lr = _make_logreader(blocking_segments=[])
        assert lr.is_in_blocking_segment(5.0) is False

    def test_multiple_segments(self):
        """Correctly identifies time inside second segment."""
        lr = _make_logreader(blocking_segments=[(5.0, 15.0, 5.0), (25.0, 35.0, 15.0)])
        assert lr.is_in_blocking_segment(3.0) is False
        assert lr.is_in_blocking_segment(10.0) is True
        assert lr.is_in_blocking_segment(20.0) is False
        assert lr.is_in_blocking_segment(30.0) is True
        assert lr.is_in_blocking_segment(40.0) is False


# ── Blocking segment detection ───────────────────


class TestBlockingSegmentDetection:
    def test_no_segments_normal_session(self, tmp_path):
        """No blocking segments in a session without frozen scenario_time."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            "5.0,5.0,event,sysmon,self,pause\n"
            "10.0,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.blocking_segments == []

    def test_detects_blocking_segment(self, tmp_path):
        """Detects a period where scenario_time is frozen."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            "5.0,5.0,event,instructions,self,start\n"
            "5.1,5.0,input,keyboard,SPACE,press\n"
            "8.0,5.0,input,keyboard,SPACE,press\n"
            "12.0,5.0,input,keyboard,SPACE,press\n"
            "12.1,5.1,event,sysmon,self,resume\n"
            "20.0,13.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.blocking_segments) == 1
        lt_start, lt_end, frozen_st = lr.blocking_segments[0]
        assert frozen_st == 5.0
        assert lt_start == 5.0  # normalized logtime of first frozen row
        assert lt_end == 12.0  # normalized logtime of last frozen row

    def test_ignores_short_same_time_groups(self, tmp_path):
        """Groups of same scenario_time shorter than threshold are not blocking."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            "5.0,5.0,event,sysmon,light-1-color,green\n"
            "5.1,5.0,event,sysmon,light-2-color,red\n"
            "10.0,10.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert lr.blocking_segments == []

    def test_multiple_blocking_segments(self, tmp_path):
        """Detects multiple blocking segments in one session."""
        csv_file = tmp_path / "session.csv"
        csv_file.write_text(
            "logtime,scenario_time,type,module,address,value\n"
            "0.0,0.0,event,sysmon,self,start\n"
            # First block: scenario_time frozen at 5.0, logtime 5.0-15.0
            "5.0,5.0,event,instructions,self,start\n"
            "10.0,5.0,input,keyboard,SPACE,press\n"
            "15.0,5.0,input,keyboard,SPACE,press\n"
            # Normal
            "15.1,5.1,event,sysmon,self,resume\n"
            "25.0,15.0,event,sysmon,self,pause\n"
            # Second block: scenario_time frozen at 15.0, logtime 25.0-35.0
            "25.0,15.0,event,genericscales,self,start\n"
            "30.0,15.0,input,keyboard,SPACE,press\n"
            "35.0,15.0,input,keyboard,SPACE,press\n"
            "35.1,15.1,event,sysmon,self,resume\n"
            "45.0,25.0,event,sysmon,self,stop\n"
        )
        lr = _make_logreader(session_file_path=csv_file)
        lr.reload_session()
        assert len(lr.blocking_segments) == 2


# ── replay_to_scenario_time mapping ──────────────


class TestReplayToScenarioTime:
    def test_identity_no_blocks(self):
        """Without blocking segments, replay_time == scenario_time."""
        lr = _make_logreader()
        lr.blocking_segments = []
        lr._build_replay_mapping()
        assert lr.replay_to_scenario_time(0.0) == 0.0
        assert lr.replay_to_scenario_time(5.0) == 5.0
        assert lr.replay_to_scenario_time(100.0) == 100.0

    def test_frozen_during_block(self):
        """scenario_time is frozen during a blocking segment."""
        lr = _make_logreader()
        lr.blocking_segments = [(5.0, 15.0, 5.0)]
        lr._build_replay_mapping()
        # Before block
        assert lr.replay_to_scenario_time(3.0) == 3.0
        # At block start
        assert lr.replay_to_scenario_time(5.0) == 5.0
        # During block
        assert lr.replay_to_scenario_time(10.0) == 5.0
        # At block end
        assert lr.replay_to_scenario_time(15.0) == 5.0

    def test_resumes_after_block(self):
        """scenario_time resumes advancing after a blocking segment."""
        lr = _make_logreader()
        lr.blocking_segments = [(5.0, 15.0, 5.0)]
        lr._build_replay_mapping()
        # Just after block
        assert lr.replay_to_scenario_time(15.1) == 5.1
        assert lr.replay_to_scenario_time(20.0) == 10.0

    def test_multiple_blocks(self):
        """Mapping handles multiple blocking segments correctly."""
        lr = _make_logreader()
        lr.blocking_segments = [(5.0, 15.0, 5.0), (25.0, 35.0, 15.0)]
        lr._build_replay_mapping()
        # Before first block
        assert lr.replay_to_scenario_time(3.0) == 3.0
        # During first block
        assert lr.replay_to_scenario_time(10.0) == 5.0
        # Between blocks
        assert lr.replay_to_scenario_time(20.0) == 10.0
        # During second block
        assert lr.replay_to_scenario_time(30.0) == 15.0
        # After second block
        assert lr.replay_to_scenario_time(40.0) == 20.0

    def test_zero_time(self):
        """replay_time=0 always returns scenario_time=0."""
        lr = _make_logreader()
        lr.blocking_segments = [(5.0, 15.0, 5.0)]
        lr._build_replay_mapping()
        assert lr.replay_to_scenario_time(0.0) == 0.0
