"""Tests for plugins.abstractplugin - Base plugin class logic."""

from unittest.mock import patch, MagicMock
import pytest

from plugins.abstractplugin import AbstractPlugin


def _make_plugin(**kwargs):
    """Create an AbstractPlugin with minimal state for testing pure logic."""
    p = object.__new__(AbstractPlugin)
    p.label = 'Test'
    p.alias = 'testplugin'
    p.widgets = {}
    p.container = None
    p.logger = MagicMock()
    p.can_receive_keys = False
    p.can_execute_keys = False
    p.keys = set()
    p.display_title = True
    p.automode_string = ''
    p.next_refresh_time = 0
    p.scenario_time = 0
    p.blocking = False
    p.alive = False
    p.paused = True
    p.visible = False
    p.verbose = False
    p.joystick = None
    p.parameters = dict(
        title='Test', taskplacement='topleft', taskupdatetime=100,
        taskfeedback=dict(overdue=dict(active=False, color=(241, 100, 100, 255),
                                       delayms=2000, blinkdurationms=1000,
                                       _nexttoggletime=0, _is_visible=False))
    )
    p.m_draw = 0
    p.__dict__.update(kwargs)
    return p


class TestKeepValueBetween:
    def test_within_range(self):
        """Value inside range is unchanged."""
        p = _make_plugin()
        assert p.keep_value_between(5, 0, 10) == 5

    def test_below_range(self):
        """Below-range value is clamped to minimum."""
        p = _make_plugin()
        assert p.keep_value_between(-5, 0, 10) == 0

    def test_above_range(self):
        """Above-range value is clamped to maximum."""
        p = _make_plugin()
        assert p.keep_value_between(15, 0, 10) == 10

    def test_at_boundaries(self):
        """Boundary values pass through unchanged."""
        p = _make_plugin()
        assert p.keep_value_between(0, 0, 10) == 0
        assert p.keep_value_between(10, 0, 10) == 10


class TestGrouped:
    def test_pairs(self):
        """Groups elements into consecutive pairs."""
        p = _make_plugin()
        result = list(p.grouped([1, 2, 3, 4], 2))
        assert result == [(1, 2), (3, 4)]

    def test_triples(self):
        """Groups elements into consecutive triples."""
        p = _make_plugin()
        result = list(p.grouped([1, 2, 3, 4, 5, 6], 3))
        assert result == [(1, 2, 3), (4, 5, 6)]


class TestGetWidgetFullname:
    def test_format(self):
        """Fullname is 'alias_widgetname'."""
        p = _make_plugin()
        assert p.get_widget_fullname('cursor') == 'testplugin_cursor'

    def test_with_known_alias(self):
        """Alias prefix is prepended correctly."""
        p = _make_plugin()
        name = p.get_widget_fullname('test')
        assert name == 'testplugin_test'


class TestSetParameter:
    def test_simple_parameter(self):
        """Sets a top-level parameter."""
        p = _make_plugin()
        p.set_parameter('title', 'New Title')
        assert p.parameters['title'] == 'New Title'

    def test_nested_parameter(self):
        """Sets a dash-separated nested parameter."""
        p = _make_plugin()
        p.set_parameter('taskfeedback-overdue-active', True)
        assert p.parameters['taskfeedback']['overdue']['active'] is True

    def test_key_parameter_updates_keys_set(self):
        """Changing a key parameter updates the keys set."""
        p = _make_plugin()
        p.parameters['mykey'] = 'OLD'
        p.keys.add('OLD')
        p.set_parameter('mykey', 'NEW')
        assert 'NEW' in p.keys
        assert 'OLD' not in p.keys


class TestComputeNextPluginState:
    def test_returns_false_when_paused(self):
        """Paused plugin returns False."""
        p = _make_plugin(paused=True, scenario_time=10, next_refresh_time=0)
        assert p.compute_next_plugin_state() is False

    def test_returns_false_before_refresh_time(self):
        """Before refresh time returns False."""
        p = _make_plugin(paused=False, scenario_time=5, next_refresh_time=10)
        assert p.compute_next_plugin_state() is False

    def test_returns_true_when_ready(self):
        """Ready plugin returns True."""
        p = _make_plugin(paused=False, scenario_time=10, next_refresh_time=5)
        result = p.compute_next_plugin_state()
        assert result is True

    def test_advances_next_refresh_time(self):
        """Next refresh time advances by taskupdatetime."""
        p = _make_plugin(paused=False, scenario_time=10, next_refresh_time=5)
        p.compute_next_plugin_state()
        expected = 10 + 100 / 1000  # scenario_time + taskupdatetime/1000
        assert p.next_refresh_time == expected


class TestUpdateCanReceiveKey:
    def test_paused_cannot_receive(self):
        """Paused plugin cannot receive keys."""
        p = _make_plugin(paused=True, visible=True)
        p.update_can_receive_key()
        assert p.can_receive_keys is False

    def test_invisible_cannot_receive(self):
        """Invisible plugin cannot receive keys."""
        p = _make_plugin(paused=False, visible=False)
        p.update_can_receive_key()
        assert p.can_receive_keys is False

    @patch('plugins.abstractplugin.REPLAY_MODE', False)
    def test_active_can_receive(self):
        """Active visible plugin can receive keys."""
        p = _make_plugin(paused=False, visible=True)
        p.update_can_receive_key()
        assert p.can_receive_keys is True

    @patch('plugins.abstractplugin.REPLAY_MODE', False)
    def test_automaticsolver_blocks_receive(self):
        """Auto-solver blocks key reception."""
        p = _make_plugin(paused=False, visible=True)
        p.parameters['automaticsolver'] = True
        p.update_can_receive_key()
        assert p.can_receive_keys is False

    @patch('plugins.abstractplugin.REPLAY_MODE', True)
    def test_replay_mode_blocks_receive(self):
        """Replay mode blocks receive, allows execute."""
        p = _make_plugin(paused=False, visible=True)
        p.update_can_receive_key()
        assert p.can_receive_keys is False
        assert p.can_execute_keys is True


class TestPluginStates:
    def test_initial_state(self):
        """Plugin starts dead, paused, invisible, non-blocking."""
        p = _make_plugin()
        assert p.alive is False
        assert p.paused is True
        assert p.visible is False
        assert p.blocking is False

    def test_pause_resume(self):
        """pause/resume toggle the paused flag."""
        p = _make_plugin(paused=False)
        p.pause()
        assert p.paused is True
        p.resume()
        assert p.paused is False

    def test_show_hide(self):
        """show/hide toggle the visible flag."""
        # Use fullscreen placement so hide() iterates widgets dict (empty = no-op)
        p = _make_plugin(visible=False)
        p.parameters['taskplacement'] = 'fullscreen'
        p.show()
        assert p.visible is True
        p.hide()
        assert p.visible is False

    def test_stop_sets_states(self):
        """stop() sets alive=False, paused=True, visible=False."""
        p = _make_plugin(alive=True, paused=False, visible=True)
        p.parameters['taskplacement'] = 'fullscreen'
        p.stop()
        assert p.alive is False
        assert p.paused is True
        assert p.visible is False
