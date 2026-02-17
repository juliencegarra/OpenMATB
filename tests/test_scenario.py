"""Tests for core.scenario - Scenario parsing and validation logic."""

from unittest.mock import patch, MagicMock
import pytest

from core.scenario import Scenario
from core.event import Event


def _make_scenario(**kwargs):
    """Create a Scenario object bypassing __init__ to avoid file I/O."""
    s = object.__new__(Scenario)
    s.events = []
    s.plugins = {}
    s.__dict__.update(kwargs)
    return s


class TestGetPluginsNameList:
    def test_unique_names(self):
        """Extracts unique plugin names from events."""
        s = _make_scenario(events=[
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'sysmon', ['stop']),
            Event(3, 0, 'track', ['start']),
        ])
        names = s.get_plugins_name_list()
        assert names == {'sysmon', 'track'}

    def test_excludes_deprecated(self):
        """Filters out deprecated plugin names."""
        # DEPRECATED = ['pumpstatus', 'end', 'cutofffrequency', 'equalproportions']
        s = _make_scenario(events=[
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 0, 'pumpstatus', ['start']),
        ])
        names = s.get_plugins_name_list()
        assert 'pumpstatus' not in names
        assert 'sysmon' in names

    def test_empty_events(self):
        """Empty event list yields empty set."""
        s = _make_scenario(events=[])
        names = s.get_plugins_name_list()
        assert names == set()


class TestGetPluginEvents:
    def test_filters_by_name(self):
        """Returns only events matching the plugin name."""
        events = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 10, 'track', ['start']),
            Event(3, 20, 'sysmon', ['stop']),
        ]
        s = _make_scenario(events=events)
        result = s.get_plugin_events('sysmon')
        assert len(result) == 2
        assert all(e.plugin == 'sysmon' for e in result)

    def test_empty_for_unknown(self):
        """Unknown plugin returns empty list."""
        s = _make_scenario(events=[Event(1, 0, 'sysmon', ['start'])])
        result = s.get_plugin_events('nonexistent')
        assert result == []

    def test_returns_all_matching(self):
        """Returns all events for a given plugin."""
        events = [
            Event(1, 0, 'track', ['start']),
            Event(2, 10, 'track', ['stop']),
        ]
        s = _make_scenario(events=events)
        result = s.get_plugin_events('track')
        assert len(result) == 2


class TestEventsRetrocompatibility:
    def test_normal_event_preserved(self):
        """Non-deprecated events pass through."""
        events = [Event(1, 0, 'sysmon', ['start'])]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        assert len(result) == 1
        assert result[0].command == ['start']

    def test_deprecated_event_removed(self):
        """Deprecated commands are filtered out."""
        events = [
            Event(1, 0, 'sysmon', ['pumpstatus']),  # deprecated command
            Event(2, 10, 'sysmon', ['start']),
        ]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        assert len(result) == 1
        assert result[0].command == ['start']

    def test_sysmon_scale_failure_up_splits(self):
        """Scale failure 'up' splits into failure+side events."""
        events = [Event(1, 10, 'sysmon', ['scales-scale1-failure', 'up'])]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        assert len(result) == 2
        assert result[0].command == ['scales-scale1-failure', 'True']
        assert result[1].command == ['scales-scale1-side', '1']

    def test_sysmon_scale_failure_down_splits(self):
        """Scale failure 'down' splits into failure+side events."""
        events = [Event(1, 10, 'sysmon', ['scales-scale1-failure', 'down'])]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        assert len(result) == 2
        assert result[0].command == ['scales-scale1-failure', 'True']
        assert result[1].command == ['scales-scale1-side', '-1']

    def test_preserves_time_and_plugin(self):
        """Split events keep original line, time, plugin."""
        events = [Event(5, 30, 'sysmon', ['scales-s1-failure', 'up'])]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        for e in result:
            assert e.line == 5
            assert e.time_sec == 30
            assert e.plugin == 'sysmon'

    def test_mixed_events(self):
        """Mixed deprecated/normal/split events processed correctly."""
        events = [
            Event(1, 0, 'sysmon', ['start']),
            Event(2, 5, 'sysmon', ['pumpstatus']),  # deprecated command
            Event(3, 10, 'sysmon', ['scales-s1-failure', 'up']),
            Event(4, 20, 'track', ['start']),
        ]
        s = _make_scenario(events=events)
        result = s.events_retrocompatibility()
        # start (kept) + pumpstatus (deprecated, removed) + failure (split to 2) + track (kept)
        assert len(result) == 4
        assert result[0].command == ['start']
        assert result[1].command == ['scales-s1-failure', 'True']
        assert result[2].command == ['scales-s1-side', '1']
        assert result[3].command == ['start']


class TestGetParametersValue:
    def test_simple_parameter(self):
        """Retrieves a top-level parameter value."""
        mock_plugin = MagicMock()
        mock_plugin.parameters = {'title': 'Test', 'taskupdatetime': 100}
        s = _make_scenario(plugins={'sysmon': mock_plugin})
        val, exists = s.get_parameters_value('sysmon', ['title', 'New'])
        assert exists is True
        assert val == 'Test'

    def test_nested_parameter(self):
        """Retrieves a nested (dash-separated) parameter."""
        mock_plugin = MagicMock()
        mock_plugin.parameters = {
            'taskfeedback': {'overdue': {'active': False, 'delayms': 2000}}
        }
        s = _make_scenario(plugins={'sysmon': mock_plugin})
        val, exists = s.get_parameters_value('sysmon', ['taskfeedback-overdue-active', 'True'])
        assert exists is True
        assert val is False

    def test_nonexistent_parameter(self):
        """Missing parameter returns (None, False)."""
        mock_plugin = MagicMock()
        mock_plugin.parameters = {'title': 'Test'}
        s = _make_scenario(plugins={'sysmon': mock_plugin})
        val, exists = s.get_parameters_value('sysmon', ['nonexistent', 'val'])
        assert exists is False
        assert val is None

    def test_nonexistent_nested(self):
        """Missing nested key returns (None, False)."""
        mock_plugin = MagicMock()
        mock_plugin.parameters = {'taskfeedback': {'overdue': {'active': False}}}
        s = _make_scenario(plugins={'sysmon': mock_plugin})
        val, exists = s.get_parameters_value('sysmon', ['taskfeedback-missing-key', 'val'])
        assert exists is False
        assert val is None


class TestGetPluginMethods:
    def test_returns_callable_names(self):
        """Lists callable method names of a plugin."""
        mock_plugin = MagicMock()
        mock_plugin.start = lambda: None
        mock_plugin.stop = lambda: None
        s = _make_scenario(plugins={'sysmon': mock_plugin})
        methods = s.get_plugin_methods('sysmon')
        assert 'start' in methods
        assert 'stop' in methods
