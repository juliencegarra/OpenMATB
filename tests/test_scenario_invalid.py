"""Tests for Scenario.check_events() — invalid scenario data validation.

Covers the 4 validation rules in check_events() (core/scenario.py:140-222),
get_validation_dict() merge logic, and Event.parse_from_string() with malformed input.
"""

from unittest.mock import patch
import pytest

from core.scenario import Scenario
from core.event import Event
from core import validation


# ──── Helpers ────

def _make_scenario(**kwargs):
    """Create a Scenario bypassing __init__ to avoid file I/O."""
    s = object.__new__(Scenario)
    s.events = []
    s.plugins = {}
    s.__dict__.update(kwargs)
    return s


def _make_plugin(params=None, blocking=False, methods=None, validation_dict=None):
    """Create a plugin with controllable attributes visible to dir().

    Unlike MagicMock, a plain class gives full control over which methods
    appear in dir() — essential for Rule 3 tests.
    """
    class Plugin:
        pass

    p = Plugin()
    p.parameters = params if params is not None else {'title': 'Test', 'taskupdatetime': 100}
    p.blocking = blocking
    if validation_dict is not None:
        p.validation_dict = validation_dict
    for name in (methods or []):
        setattr(p, name, lambda: None)
    return p


def _base_events(plugin='myplugin'):
    """Return start+stop events to satisfy Rule 1."""
    return [
        Event(1, 0, plugin, ['start']),
        Event(99, 600, plugin, ['stop']),
    ]


# ──── Rule 1: start/stop commands ────

class TestRule1StartStop:

    def test_no_start_command(self):
        """Plugin without 'start' in any event triggers error."""
        plugin = _make_plugin(methods=['stop'])
        s = _make_scenario(
            plugins={'myplugin': plugin},
            events=[Event(1, 0, 'myplugin', ['stop'])],
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('does not have a start command' in e for e in errors)

    def test_nonblocking_no_stop(self):
        """Non-blocking plugin without 'stop' triggers error."""
        plugin = _make_plugin(methods=['start'])
        s = _make_scenario(
            plugins={'myplugin': plugin},
            events=[Event(1, 0, 'myplugin', ['start'])],
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('does not have a stop command' in e for e in errors)

    def test_blocking_no_stop_ok(self):
        """Blocking plugin without 'stop' does NOT trigger stop error."""
        plugin = _make_plugin(blocking=True, methods=['start'])
        s = _make_scenario(
            plugins={'myplugin': plugin},
            events=[Event(1, 0, 'myplugin', ['start'])],
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert not any('stop command' in e for e in errors)

    def test_start_and_stop_present(self):
        """Plugin with both start and stop yields no Rule 1 errors."""
        plugin = _make_plugin(methods=['start', 'stop'])
        s = _make_scenario(
            plugins={'myplugin': plugin},
            events=_base_events(),
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert not any('start command' in e or 'stop command' in e for e in errors)

    def test_multiple_plugins_one_missing_start(self):
        """Only the plugin missing 'start' is reported."""
        plug_a = _make_plugin(methods=['start', 'stop'])
        plug_b = _make_plugin(methods=['stop'])
        s = _make_scenario(
            plugins={'alpha': plug_a, 'beta': plug_b},
            events=[
                Event(1, 0, 'alpha', ['start']),
                Event(2, 60, 'alpha', ['stop']),
                Event(3, 0, 'beta', ['stop']),
            ],
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        start_errors = [e for e in errors if 'start command' in e]
        assert len(start_errors) == 1
        assert 'beta' in start_errors[0]

    def test_replay_mode_no_stop_ok(self):
        """In replay mode, missing stop is not an error."""
        plugin = _make_plugin(methods=['start'])
        s = _make_scenario(
            plugins={'myplugin': plugin},
            events=[Event(1, 0, 'myplugin', ['start'])],
        )
        with patch('core.scenario.REPLAY_MODE', True):
            errors = s.check_events()
        assert not any('stop command' in e for e in errors)


# ──── Rule 2: command length ────

class TestRule2CommandLength:

    def test_empty_command(self):
        """Event with empty command list triggers error."""
        plugin = _make_plugin(methods=['start', 'stop'])
        events = _base_events() + [Event(10, 30, 'myplugin', [])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('does not trigger any command' in e for e in errors)

    def test_command_too_long(self):
        """Event with command len > 2 triggers error."""
        plugin = _make_plugin(methods=['start', 'stop'])
        events = _base_events() + [Event(10, 30, 'myplugin', ['a', 'b', 'c'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('Maximum length of an event is 2' in e for e in errors)

    def test_valid_lengths_no_error(self):
        """Events with len 1 and 2 do not trigger length errors."""
        plugin = _make_plugin(
            params={'title': 'Test'},
            methods=['start', 'stop', 'pause'],
        )
        events = _base_events() + [
            Event(10, 30, 'myplugin', ['pause']),
            Event(11, 35, 'myplugin', ['title', 'NewTitle']),
        ]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'title': validation.is_string}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            errors = s.check_events()
        assert not any('does not trigger any command' in e for e in errors)
        assert not any('Maximum length' in e for e in errors)


# ──── Rule 3: unknown method (len == 1) ────

class TestRule3UnknownMethod:

    def test_unknown_method(self):
        """Command referencing missing method triggers error."""
        plugin = _make_plugin(methods=['start', 'stop'])
        events = _base_events() + [Event(10, 30, 'myplugin', ['nonexistent'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('Method (nonexistent) is not available' in e for e in errors)

    def test_known_method_ok(self):
        """Command referencing existing method yields no Rule 3 error."""
        plugin = _make_plugin(methods=['start', 'stop', 'pause'])
        events = _base_events() + [Event(10, 30, 'myplugin', ['pause'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert not any('is not available' in e for e in errors)

    def test_error_names_method_and_plugin(self):
        """Error message includes the unknown method name and plugin."""
        plugin = _make_plugin(methods=['start', 'stop'])
        events = _base_events() + [Event(10, 30, 'myplugin', ['wiggle'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        method_errors = [e for e in errors if 'is not available' in e]
        assert len(method_errors) == 1
        assert 'wiggle' in method_errors[0]
        assert 'myplugin' in method_errors[0]


# ──── Rule 4: parameter validation (len == 2) ────

class TestRule4ParameterValidation:

    def test_nonexistent_parameter(self):
        """Parameter not in plugin triggers 'does not have' error."""
        plugin = _make_plugin(params={'title': 'Test'}, methods=['start', 'stop'])
        events = _base_events() + [Event(10, 30, 'myplugin', ['missing_param', 'val'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('does not have a missing_param parameter' in e for e in errors)

    def test_no_validation_function_warning(self):
        """Parameter without validation method triggers warning."""
        plugin = _make_plugin(
            params={'customkey': 'default'},
            methods=['start', 'stop'],
        )
        events = _base_events() + [Event(10, 30, 'myplugin', ['customkey', 'val'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', {}):
            errors = s.check_events()
        assert any('has no verification method' in e for e in errors)

    def test_validation_fails(self):
        """Invalid value triggers validation error message."""
        plugin = _make_plugin(
            params={'taskupdatetime': 100},
            methods=['start', 'stop'],
        )
        events = _base_events() + [Event(10, 30, 'myplugin', ['taskupdatetime', 'abc'])]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'taskupdatetime': validation.is_positive_integer}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            errors = s.check_events()
        param_errors = [e for e in errors if 'taskupdatetime' in e and 'positive' in e]
        assert len(param_errors) == 1

    def test_validation_succeeds_replaces_value(self):
        """Valid string value is replaced by its evaluated version."""
        plugin = _make_plugin(
            params={'taskupdatetime': 100},
            methods=['start', 'stop'],
        )
        param_event = Event(10, 30, 'myplugin', ['taskupdatetime', '200'])
        events = _base_events() + [param_event]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'taskupdatetime': validation.is_positive_integer}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            errors = s.check_events()
        assert not any('taskupdatetime' in e for e in errors)
        assert param_event.command[1] == 200  # str '200' → int 200

    def test_is_string_preserves_spaces(self):
        """is_string validator does NOT strip spaces from value."""
        plugin = _make_plugin(
            params={'title': 'Test'},
            methods=['start', 'stop'],
        )
        param_event = Event(10, 30, 'myplugin', ['title', 'Hello World'])
        events = _base_events() + [param_event]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'title': validation.is_string}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            s.check_events()
        assert param_event.command[1] == 'Hello World'

    def test_non_string_strips_spaces(self):
        """Non-is_string validator strips spaces before validation."""
        plugin = _make_plugin(
            params={'taskupdatetime': 100},
            methods=['start', 'stop'],
        )
        param_event = Event(10, 30, 'myplugin', ['taskupdatetime', '1 00'])
        events = _base_events() + [param_event]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'taskupdatetime': validation.is_positive_integer}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            s.check_events()
        # '1 00' → spaces stripped → '100' → evaluated to int 100
        assert param_event.command[1] == 100

    def test_validation_tuple_extra_args(self):
        """Validation dict tuple unpacks extra args to validator."""
        def custom_validator(value, allowed):
            if value in allowed:
                return value, None
            return None, 'not in allowed list'

        plugin = _make_plugin(
            params={'mode': 'normal'},
            methods=['start', 'stop'],
        )
        param_event = Event(10, 30, 'myplugin', ['mode', 'turbo'])
        events = _base_events() + [param_event]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'mode': (custom_validator, ['normal', 'easy'])}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            errors = s.check_events()
        assert any('not in allowed list' in e for e in errors)


# ──── get_validation_dict merge ────

class TestValidationDictMerge:

    def test_no_plugin_dict_uses_global(self):
        """Without plugin validation_dict, global dict is used."""
        plugin = _make_plugin()  # No validation_dict attribute
        s = _make_scenario(plugins={'myplugin': plugin})
        gdict = {'title': validation.is_string}
        with patch('core.scenario.global_validation_dict', gdict):
            result = s.get_validation_dict('myplugin')
        assert 'title' in result

    def test_plugin_dict_overrides_global(self):
        """Plugin validation_dict entries override global ones."""
        custom_fn = lambda x: (x, None)
        custom_fn.__name__ = 'custom_fn'
        plugin = _make_plugin(validation_dict={'title': custom_fn})
        s = _make_scenario(plugins={'myplugin': plugin})
        with patch('core.scenario.global_validation_dict', dict()):
            result = s.get_validation_dict('myplugin')
        assert result['title'] is custom_fn

    def test_plugin_only_parameter_found(self):
        """Parameter only in plugin dict is discoverable."""
        custom_fn = lambda x: (x, None)
        custom_fn.__name__ = 'custom_fn'
        plugin = _make_plugin(validation_dict={'special': custom_fn})
        s = _make_scenario(plugins={'myplugin': plugin})
        with patch('core.scenario.global_validation_dict', dict()):
            result = s.get_validation_dict('myplugin')
        assert 'special' in result


# ──── Integration: full check_events scenarios ────

class TestCheckEventsIntegration:

    def test_multiple_errors_all_collected(self):
        """All errors are collected — no short-circuit."""
        plugin = _make_plugin(methods=['start', 'stop'])
        events = [
            Event(1, 0, 'myplugin', ['start']),
            Event(2, 600, 'myplugin', ['stop']),
            Event(10, 30, 'myplugin', []),                  # Rule 2: empty
            Event(11, 35, 'myplugin', ['a', 'b', 'c']),     # Rule 2: too long
            Event(12, 40, 'myplugin', ['unknown_method']),   # Rule 3: unknown
        ]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('does not trigger any command' in e for e in errors)
        assert any('Maximum length' in e for e in errors)
        assert any('is not available' in e for e in errors)
        assert len(errors) >= 3

    def test_valid_scenario_no_errors(self):
        """Perfectly valid scenario returns empty error list."""
        plugin = _make_plugin(
            params={'title': 'Test'},
            methods=['start', 'stop'],
        )
        events = [
            Event(1, 0, 'myplugin', ['start']),
            Event(2, 30, 'myplugin', ['title', 'NewTitle']),
            Event(3, 600, 'myplugin', ['stop']),
        ]
        s = _make_scenario(plugins={'myplugin': plugin}, events=events)
        vdict = {'title': validation.is_string}
        with patch('core.scenario.REPLAY_MODE', False), \
             patch('core.scenario.global_validation_dict', vdict):
            errors = s.check_events()
        assert errors == []

    def test_mix_rule1_rule3_rule4(self):
        """Errors from multiple rules are all reported together."""
        plug_a = _make_plugin(methods=['stop'])       # alpha: no start event
        plug_b = _make_plugin(
            params={'title': 'Test'},
            methods=['start', 'stop'],
        )
        events = [
            Event(1, 0, 'alpha', ['stop']),                   # alpha has no start
            Event(2, 0, 'beta', ['start']),
            Event(3, 30, 'beta', ['unknown_cmd']),             # Rule 3
            Event(4, 35, 'beta', ['missing_param', 'x']),      # Rule 4: param absent
            Event(5, 600, 'beta', ['stop']),
        ]
        s = _make_scenario(
            plugins={'alpha': plug_a, 'beta': plug_b},
            events=events,
        )
        with patch('core.scenario.REPLAY_MODE', False):
            errors = s.check_events()
        assert any('start command' in e for e in errors)                        # Rule 1
        assert any('is not available' in e for e in errors)                     # Rule 3
        assert any('does not have a' in e and 'parameter' in e for e in errors) # Rule 4


# ──── Event.parse_from_string — malformed input ────

class TestParseInvalidInput:

    def test_empty_timestamp(self):
        """Empty timestamp field raises ValueError."""
        with pytest.raises(ValueError):
            Event.parse_from_string(1, ';sysmon;start')

    def test_non_numeric_timestamp(self):
        """Non-numeric timestamp raises ValueError."""
        with pytest.raises(ValueError):
            Event.parse_from_string(1, 'abc:00:00;sysmon;start')

    def test_no_semicolons(self):
        """Line without semicolons raises ValueError (not enough segments)."""
        with pytest.raises(ValueError):
            Event.parse_from_string(1, 'nosemicolon')

    def test_too_many_fields_ok(self):
        """Extra fields are captured in command list (no parse error)."""
        e = Event.parse_from_string(1, '0:00:00;sysmon;a;b;c')
        assert e.command == ['a', 'b', 'c']

    def test_empty_string(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            Event.parse_from_string(1, '')
