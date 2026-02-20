"""Tests for system;pause scenario command."""

from unittest.mock import MagicMock

from core.event import Event
from core.scenario import Scenario


def _make_scenario(**kwargs):
    """Create a Scenario object bypassing __init__ to avoid file I/O."""
    s = object.__new__(Scenario)
    s.events = []
    s.plugins = {}
    s.__dict__.update(kwargs)
    return s


class TestSystemEventParsing:
    def test_parse_system_pause(self):
        """Parsing '0:01:00;system;pause' yields correct plugin and command."""
        e = Event.parse_from_string(1, "0:01:00;system;pause")
        assert e.plugin == "system"
        assert e.command == ["pause"]
        assert e.time_sec == 60

    def test_parse_system_pause_roundtrip(self):
        """Event line string roundtrips correctly."""
        e = Event.parse_from_string(1, "0:01:00;system;pause")
        assert e.get_line_str() == "0:01:00;system;pause"


class TestGetPluginsNameListExcludesSystem:
    def test_system_excluded(self):
        """get_plugins_name_list() does not include 'system'."""
        s = _make_scenario(
            events=[
                Event(1, 0, "sysmon", ["start"]),
                Event(2, 60, "system", ["pause"]),
                Event(3, 120, "sysmon", ["stop"]),
            ]
        )
        names = s.get_plugins_name_list()
        assert "system" not in names
        assert "sysmon" in names

    def test_only_system_events(self):
        """Scenario with only system events yields empty plugin set."""
        s = _make_scenario(
            events=[
                Event(1, 60, "system", ["pause"]),
            ]
        )
        names = s.get_plugins_name_list()
        assert names == set()


class TestCheckEventsSystemCommands:
    def _make_scenario_with_plugins(self, events):
        """Create a scenario with mock plugins for check_events()."""
        mock_plugin = MagicMock()
        mock_plugin.blocking = False
        mock_plugin.parameters = {}
        s = _make_scenario(events=events, plugins={"sysmon": mock_plugin})
        return s

    def test_system_pause_accepted(self):
        """check_events() accepts system;pause without error."""
        events = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 60, "system", ["pause"]),
            Event(3, 120, "sysmon", ["stop"]),
        ]
        s = self._make_scenario_with_plugins(events)
        errs = s.check_events()
        # No error about system;pause
        assert not any("system" in e.lower() for e in errs)

    def test_system_invalid_command_rejected(self):
        """check_events() rejects an invalid system command."""
        events = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 60, "system", ["invalid"]),
            Event(3, 120, "sysmon", ["stop"]),
        ]
        s = self._make_scenario_with_plugins(events)
        errs = s.check_events()
        system_errors = [e for e in errs if "system command" in e.lower()]
        assert len(system_errors) == 1

    def test_system_two_args_rejected(self):
        """check_events() rejects a system event with two arguments."""
        events = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 60, "system", ["pause", "extra"]),
            Event(3, 120, "sysmon", ["stop"]),
        ]
        s = self._make_scenario_with_plugins(events)
        errs = s.check_events()
        system_errors = [e for e in errs if "system command" in e.lower()]
        assert len(system_errors) == 1


class TestExecuteSystemCommand:
    def test_pause_calls_pause_prompt(self, mock_window, monkeypatch):
        """execute_one_event() calls pause_prompt() for system;pause."""
        import core.scheduler
        from core.scheduler import Scheduler

        mock_log = MagicMock()
        monkeypatch.setattr(core.scheduler, "logger", mock_log)

        sched = object.__new__(Scheduler)
        sched.plugins = {}

        event = Event(1, 60, "system", ["pause"])
        sched.execute_one_event(event)

        mock_window.pause_prompt.assert_called_once()
        assert event.done == 1
        mock_log.record_event.assert_called_once_with(event)

    def test_normal_event_still_works(self, mock_window, monkeypatch):
        """Normal plugin events are still dispatched to the plugin."""
        import core.scheduler
        from core.scheduler import Scheduler

        mock_log = MagicMock()
        monkeypatch.setattr(core.scheduler, "logger", mock_log)

        sched = object.__new__(Scheduler)
        mock_plugin = MagicMock()
        sched.plugins = {"sysmon": mock_plugin}

        event = Event(1, 0, "sysmon", ["start"])
        sched.execute_one_event(event)

        mock_plugin.start.assert_called_once()
        assert event.done == 1
