"""Tests for core.event - Event parsing and representation."""

from core.event import Event


class TestEventInit:
    def test_basic_construction(self):
        """Event stores line, time, plugin, and command."""
        e = Event(1, 60, "sysmon", "start")
        assert e.line == 1
        assert e.time_sec == 60
        assert e.plugin == "sysmon"
        assert e.command == ["start"]
        assert e.done is False

    def test_command_as_list(self):
        """List commands are stored as-is."""
        e = Event(1, 60, "sysmon", ["param", "value"])
        assert e.command == ["param", "value"]

    def test_command_as_string_becomes_list(self):
        """String command is wrapped in a list."""
        e = Event(1, 60, "sysmon", "start")
        assert isinstance(e.command, list)
        assert e.command == ["start"]


class TestParseFromString:
    def test_simple_event(self):
        """Parses 'H:MM:SS;plugin;command' format."""
        e = Event.parse_from_string(1, "0:01:00;sysmon;start")
        assert e.time_sec == 60
        assert e.plugin == "sysmon"
        assert e.command == ["start"]

    def test_event_with_parameter(self):
        """Parses command with extra parameter."""
        e = Event.parse_from_string(2, "0:02:30;resman;pump-1-state;on")
        assert e.time_sec == 150
        assert e.plugin == "resman"
        assert e.command == ["pump-1-state", "on"]

    def test_hours(self):
        """Parses full-hour timestamps."""
        e = Event.parse_from_string(1, "1:00:00;track;start")
        assert e.time_sec == 3600

    def test_complex_time(self):
        """Parses mixed hours, minutes, seconds."""
        e = Event.parse_from_string(1, "1:30:45;sysmon;stop")
        assert e.time_sec == 5445  # 3600 + 1800 + 45

    def test_zero_time(self):
        """Parses zero timestamp."""
        e = Event.parse_from_string(0, "0:00:00;track;start")
        assert e.time_sec == 0


class TestEventRepr:
    def test_repr_format(self):
        """repr includes 'Event', time, and plugin."""
        e = Event(1, 60, "sysmon", "start")
        r = repr(e)
        assert "Event" in r
        assert "60" in r
        assert "sysmon" in r

    def test_str_format(self):
        """str includes line number prefix."""
        e = Event(1, 60, "sysmon", "start")
        s = str(e)
        assert "l.1" in s


class TestEventLen:
    def test_single_command(self):
        """Single command has length 1."""
        e = Event(1, 60, "sysmon", "start")
        assert len(e) == 1

    def test_double_command(self):
        """Two-part command has length 2."""
        e = Event(1, 60, "resman", ["pump-1-state", "on"])
        assert len(e) == 2


class TestTimeHMS:
    def test_zero(self):
        """0 seconds formats as 0:00:00."""
        e = Event(1, 0, "test", "cmd")
        assert e.get_time_hms_str() == "0:00:00"

    def test_one_hour(self):
        """3600 seconds formats as 1:00:00."""
        e = Event(1, 3600, "test", "cmd")
        assert e.get_time_hms_str() == "1:00:00"

    def test_mixed(self):
        """3723 seconds formats as 1:02:03."""
        e = Event(1, 3723, "test", "cmd")
        assert e.get_time_hms_str() == "1:02:03"


class TestGetCommandStr:
    def test_single(self):
        """Single command returns plain string."""
        e = Event(1, 0, "test", "start")
        assert e.get_command_str() == "start"

    def test_double(self):
        """Multi-part command joins with semicolons."""
        e = Event(1, 0, "test", ["param", "value"])
        assert e.get_command_str() == "param;value"


class TestGetLineStr:
    def test_format(self):
        """Produces 'H:MM:SS;plugin;command' line."""
        e = Event(1, 60, "sysmon", "start")
        assert e.get_line_str() == "0:01:00;sysmon;start"

    def test_with_params(self):
        """Includes extra parameters in output."""
        e = Event(1, 150, "resman", ["pump-1-state", "on"])
        assert e.get_line_str() == "0:02:30;resman;pump-1-state;on"


class TestIsDeprecated:
    def test_deprecated_plugin(self):
        """'pumpstatus' plugin is deprecated."""
        e = Event(1, 0, "pumpstatus", "start")
        assert e.is_deprecated() is True

    def test_deprecated_command(self):
        """'end' command is deprecated."""
        e = Event(1, 0, "resman", "end")
        assert e.is_deprecated() is True

    def test_not_deprecated(self):
        """Normal event is not deprecated."""
        e = Event(1, 0, "sysmon", "start")
        assert e.is_deprecated() is False
