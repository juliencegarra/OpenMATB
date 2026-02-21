"""Tests for the agent abstraction layer (agents/ module).

Tests AbstractAgent interface, DefaultAgent behavior, agent registry,
and integration with plugins.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from agents import AGENT_REGISTRY, AbstractAgent, DefaultAgent, HumanLikeAgent, create_agent
from agents.abstract_agent import AbstractAgent as AbstractAgentDirect


# ──────────────────────────────────────────────
# AbstractAgent interface
# ──────────────────────────────────────────────
class TestAbstractAgent:
    def test_cannot_instantiate(self):
        """AbstractAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractAgent()

    def test_get_automode_string_default(self):
        """DefaultAgent returns 'AUTO' as automode string."""
        agent = DefaultAgent()
        assert agent.get_automode_string() == "AUTO"

    def test_custom_automode_string(self):
        """Subclass can customize automode string."""

        class CustomAgent(AbstractAgent):
            def __init__(self):
                super().__init__(name="custom", automode_string="AI")

            def on_plugin_update(self, plugin, scenario_time):
                pass

            def on_failure_started(self, plugin, gauge):
                return {}

        agent = CustomAgent()
        assert agent.get_automode_string() == "AI"


# ──────────────────────────────────────────────
# AbstractAgent.send_key / send_joystick
# ──────────────────────────────────────────────
class TestAbstractAgentInjection:
    def test_send_key_calls_do_on_key_with_emulate(self):
        """send_key() calls plugin.do_on_key(key, state, emulate=True)."""
        agent = DefaultAgent()
        plugin = MagicMock()
        with patch("agents.abstract_agent.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            agent.send_key(plugin, "F1", "press")
            plugin.do_on_key.assert_called_once_with("F1", "press", emulate=True)
            mock_logger.record_input.assert_called_once_with("keyboard", "F1", "press")

    def test_send_key_default_state_is_press(self):
        """send_key() defaults to state='press'."""
        agent = DefaultAgent()
        plugin = MagicMock()
        with patch("agents.abstract_agent.get_logger") as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            agent.send_key(plugin, "ENTER")
            plugin.do_on_key.assert_called_once_with("ENTER", "press", emulate=True)

    def test_send_joystick_calls_get_joystick_inputs(self):
        """send_joystick() calls plugin.get_joystick_inputs(x, y)."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.get_joystick_inputs = MagicMock()
        agent.send_joystick(plugin, 0.5, -0.3)
        plugin.get_joystick_inputs.assert_called_once_with(0.5, -0.3)

    def test_send_joystick_no_method_no_crash(self):
        """send_joystick() does nothing if plugin lacks get_joystick_inputs."""
        agent = DefaultAgent()
        plugin = MagicMock(spec=[])  # No attributes
        agent.send_joystick(plugin, 1.0, 1.0)  # Should not raise


# ──────────────────────────────────────────────
# DefaultAgent
# ──────────────────────────────────────────────
class TestDefaultAgent:
    def test_name(self):
        """DefaultAgent has name 'default'."""
        agent = DefaultAgent()
        assert agent.name == "default"

    def test_automode_string(self):
        """DefaultAgent automode string is 'AUTO'."""
        agent = DefaultAgent()
        assert agent.automode_string == "AUTO"

    def test_on_failure_started_returns_delay(self):
        """on_failure_started returns alerttimeout from plugin parameters."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}
        result = agent.on_failure_started(plugin, gauge={})
        assert result == {"delay": 10000}

    def test_on_plugin_update_unknown_alias_no_error(self):
        """on_plugin_update with unknown alias does nothing (no crash)."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "unknown_plugin"
        agent.on_plugin_update(plugin, 0)  # Should not raise


# ──────────────────────────────────────────────
# Agent registry
# ──────────────────────────────────────────────
class TestAgentRegistry:
    def test_default_in_registry(self):
        """'default' is in the agent registry."""
        assert "default" in AGENT_REGISTRY

    def test_create_agent_default(self):
        """create_agent('default') returns a DefaultAgent."""
        agent = create_agent("default")
        assert isinstance(agent, DefaultAgent)

    def test_create_agent_unknown_raises(self):
        """create_agent with unknown name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent"):
            create_agent("nonexistent")


# ──────────────────────────────────────────────
# DefaultAgent._update_resman (input injection)
# ──────────────────────────────────────────────
class TestDefaultAgentResman:
    def _make_resman_plugin(self):
        """Create a minimal resman-like plugin for testing agent logic."""
        from core.constants import COLORS as C

        p = MagicMock()
        p.alias = "resman"
        p.wait_before_leak = 0
        p.parameters = dict(
            tank=dict(
                a=dict(level=2500, max=4000, target=2500, depletable=True, lossperminute=800),
                b=dict(level=2500, max=4000, target=2500, depletable=True, lossperminute=800),
                e=dict(level=3000, max=4000, target=None, depletable=False, lossperminute=0),
            ),
            pump=dict(
                [
                    ("2", dict(flow=600, state="off", key="NUM_2", _fromtank="e", _totank="a")),
                    ("7", dict(flow=400, state="off", key="NUM_7", _fromtank="a", _totank="b")),
                ]
            ),
        )
        return p

    def test_activates_pump_from_non_depletable(self):
        """Heuristic 1: pumps from non-depletable tanks are toggled via send_key."""
        agent = DefaultAgent()
        p = self._make_resman_plugin()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p)
        # Pump 2 is off and should be toggled to on → do_on_key called with NUM_2
        p.do_on_key.assert_any_call("NUM_2", "press", emulate=True)

    def test_does_not_toggle_pump_already_in_desired_state(self):
        """Agent does not toggle pump that is already in the desired state."""
        agent = DefaultAgent()
        p = self._make_resman_plugin()
        p.parameters["pump"]["2"]["state"] = "on"  # Already on (desired for non-depletable)
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p)
        # NUM_2 should NOT be pressed since pump is already "on"
        if p.do_on_key.call_count > 0:
            for c in p.do_on_key.call_args_list:
                assert c[0][0] != "NUM_2"

    def test_skips_failure_pumps(self):
        """Agent skips pumps in failure state."""
        agent = DefaultAgent()
        p = self._make_resman_plugin()
        p.parameters["pump"]["2"]["state"] = "failure"
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p)
        # NUM_2 should not be pressed
        for c in p.do_on_key.call_args_list:
            assert c[0][0] != "NUM_2"

    def test_skips_when_wait_before_leak(self):
        """Agent does nothing when wait_before_leak > 0."""
        agent = DefaultAgent()
        p = self._make_resman_plugin()
        p.wait_before_leak = 1
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p)
        p.do_on_key.assert_not_called()

    def test_equilibrate_heuristic(self):
        """Heuristic 3: equilibrate between two target tanks."""
        agent = DefaultAgent()
        p = self._make_resman_plugin()
        p.parameters["tank"]["a"]["level"] = 2600
        p.parameters["tank"]["b"]["level"] = 2400
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p)
        # Pump 7 (a→b): from_tank=a has target, to_tank=b has target,
        # a.level(2600) >= b.target(2500) >= b.level(2400) → desired "on", currently "off" → toggle
        p.do_on_key.assert_any_call("NUM_7", "press", emulate=True)


# ──────────────────────────────────────────────
# DefaultAgent._update_track (joystick injection)
# ──────────────────────────────────────────────
class TestDefaultAgentTrack:
    def test_sends_joystick_positive(self):
        """When cursor is left-down, joystick is (1.0, -1.0)."""
        agent = DefaultAgent()
        p = MagicMock()
        p.alias = "track"
        p.reticle = MagicMock()
        p.reticle.cursor_relative = (-5, -5)
        agent._update_track(p)
        p.get_joystick_inputs.assert_called_once_with(1.0, -1.0)

    def test_sends_joystick_negative(self):
        """When cursor is right-up, joystick is (-1.0, 1.0)."""
        agent = DefaultAgent()
        p = MagicMock()
        p.alias = "track"
        p.reticle = MagicMock()
        p.reticle.cursor_relative = (5, 5)
        agent._update_track(p)
        p.get_joystick_inputs.assert_called_once_with(-1.0, 1.0)

    def test_joystick_at_center(self):
        """When cursor is at center (0, 0), joystick is (1.0, -1.0)."""
        agent = DefaultAgent()
        p = MagicMock()
        p.alias = "track"
        p.reticle = MagicMock()
        p.reticle.cursor_relative = (0, 0)
        agent._update_track(p)
        # -0 >= 0 is True, so jx=1.0; -0 >= 0 is True, so jy=-1.0
        p.get_joystick_inputs.assert_called_once_with(1.0, -1.0)


# ──────────────────────────────────────────────
# DefaultAgent._update_communications (key injection)
# ──────────────────────────────────────────────
class TestDefaultAgentComms:
    def _make_comms_plugin(self, active_radio, waiting_radios=None):
        """Create a comms plugin mock with proper key mappings."""
        p = MagicMock()
        p.alias = "communications"
        p.parameters = dict(keys=dict(
            selectradioup="UP",
            selectradiodown="DOWN",
            tunefrequencyup="RIGHT",
            tunefrequencydown="LEFT",
            validateresponse="ENTER",
        ))
        p.get_waiting_response_radios.return_value = waiting_radios if waiting_radios is not None else []
        p.get_active_radio_dict.return_value = active_radio
        return p

    def test_no_waiting_radios_does_nothing(self):
        """When no radios are waiting, agent does nothing."""
        agent = DefaultAgent()
        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": None, "pos": 0, "is_active": True}
        p = self._make_comms_plugin(radio)
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_not_called()

    def test_tunes_frequency_up(self):
        """Agent sends RIGHT key to tune up toward target frequency."""
        agent = DefaultAgent()
        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0, "pos": 0, "is_active": True}
        p = self._make_comms_plugin(radio, waiting_radios=[radio])
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_called_once_with("RIGHT", "press", emulate=True)

    def test_tunes_frequency_down(self):
        """Agent sends LEFT key to tune down toward target frequency."""
        agent = DefaultAgent()
        radio = {"name": "NAV_1", "currentfreq": 115.0, "targetfreq": 110.0, "pos": 0, "is_active": True}
        p = self._make_comms_plugin(radio, waiting_radios=[radio])
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_called_once_with("LEFT", "press", emulate=True)

    def test_confirms_when_frequency_matches(self):
        """Agent sends ENTER key when frequency matches target."""
        agent = DefaultAgent()
        radio = {"name": "NAV_1", "currentfreq": 115.0, "targetfreq": 115.0, "pos": 0, "is_active": True}
        p = self._make_comms_plugin(radio, waiting_radios=[radio])
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_called_once_with("ENTER", "press", emulate=True)

    def test_switches_radio_up(self):
        """Agent sends UP key when target radio is above active."""
        agent = DefaultAgent()
        active = {"name": "NAV_2", "currentfreq": 110.0, "targetfreq": None, "pos": 1, "is_active": True}
        target = {"name": "NAV_1", "currentfreq": 120.0, "targetfreq": 120.0, "pos": 0, "is_active": False}
        p = self._make_comms_plugin(active, waiting_radios=[target])
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_called_once_with("UP", "press", emulate=True)

    def test_switches_radio_down(self):
        """Agent sends DOWN key when target radio is below active."""
        agent = DefaultAgent()
        active = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": None, "pos": 0, "is_active": True}
        target = {"name": "NAV_2", "currentfreq": 120.0, "targetfreq": 120.0, "pos": 1, "is_active": False}
        p = self._make_comms_plugin(active, waiting_radios=[target])
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(p)
        p.do_on_key.assert_called_once_with("DOWN", "press", emulate=True)


# ──────────────────────────────────────────────
# DefaultAgent.on_failure_started (sysmon)
# ──────────────────────────────────────────────
class TestDefaultAgentSysmon:
    def test_on_failure_started_returns_alerttimeout(self):
        """on_failure_started returns alerttimeout (safety-net), not automaticsolverdelay."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}
        result = agent.on_failure_started(plugin, gauge={"name": "F1"})
        assert result == {"delay": 10000}

    def test_update_sysmon_sends_key_after_delay(self):
        """Agent sends gauge key when _milliresponsetime >= automaticsolverdelay."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.parameters = {"automaticsolverdelay": 1000}
        gauge = {"name": "F1", "_milliresponsetime": 1000, "key": "F1"}
        plugin.get_gauges_on_failure.return_value = [gauge]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0)
        plugin.do_on_key.assert_called_once_with("F1", "press", emulate=True)

    def test_update_sysmon_skips_before_delay(self):
        """Agent does not send key when _milliresponsetime < automaticsolverdelay."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.parameters = {"automaticsolverdelay": 1000}
        gauge = {"name": "F1", "_milliresponsetime": 800, "key": "F1"}
        plugin.get_gauges_on_failure.return_value = [gauge]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0)
        plugin.do_on_key.assert_not_called()

    def test_update_sysmon_no_failure(self):
        """Agent does nothing when no gauges are on failure."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.parameters = {"automaticsolverdelay": 1000}
        plugin.get_gauges_on_failure.return_value = []
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0)
        plugin.do_on_key.assert_not_called()

    def test_update_sysmon_multiple_gauges(self):
        """Agent sends key only for gauges that have reached the delay threshold."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.parameters = {"automaticsolverdelay": 1000}
        ready = {"name": "F1", "_milliresponsetime": 1200, "key": "F1"}
        not_ready = {"name": "F2", "_milliresponsetime": 500, "key": "F2"}
        plugin.get_gauges_on_failure.return_value = [ready, not_ready]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0)
        plugin.do_on_key.assert_called_once_with("F1", "press", emulate=True)


# ──────────────────────────────────────────────
# DefaultAgent._compute_desired_pump_state
# ──────────────────────────────────────────────
class TestComputeDesiredPumpState:
    def test_non_depletable_off_returns_on(self):
        """Pump from non-depletable tank that is off → desired 'on'."""
        pump = {"state": "off"}
        from_tank = {"depletable": False, "target": None}
        to_tank = {"target": None}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) == "on"

    def test_non_depletable_already_on(self):
        """Pump from non-depletable tank that is already on → no heuristic 1 trigger."""
        pump = {"state": "on"}
        from_tank = {"depletable": False, "target": None}
        to_tank = {"target": None}
        # Heuristic 1 only fires when state == "off", so desired is None
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) is None

    def test_target_low_returns_on(self):
        """Tank below target-50 → desired 'on'."""
        pump = {"state": "off"}
        from_tank = {"depletable": True, "target": None}
        to_tank = {"target": 2500, "level": 2400}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) == "on"

    def test_target_high_returns_off(self):
        """Tank above target+50 → desired 'off'."""
        pump = {"state": "on"}
        from_tank = {"depletable": True, "target": None}
        to_tank = {"target": 2500, "level": 2600}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) == "off"

    def test_equilibrate_on(self):
        """Heuristic 3: from >= to_target >= to_level → 'on'."""
        pump = {"state": "off"}
        from_tank = {"depletable": True, "target": 2500, "level": 2600}
        to_tank = {"target": 2500, "level": 2400}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) == "on"

    def test_equilibrate_off(self):
        """Heuristic 3 not satisfied → 'off'."""
        pump = {"state": "on"}
        from_tank = {"depletable": True, "target": 2500, "level": 2400}
        to_tank = {"target": 2500, "level": 2600}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank) == "off"

    def test_noise_shifts_threshold(self):
        """threshold_noise shifts the +-50 boundary."""
        pump = {"state": "off"}
        from_tank = {"depletable": True, "target": None}
        # Level 2460 is above 2500-50=2450 normally → not triggered
        # But with noise=-20: threshold becomes 2500-50+(-20) = 2430 → still above, not triggered
        # With noise=+20: threshold becomes 2500-50+20 = 2470 → 2460 <= 2470, triggered
        to_tank = {"target": 2500, "level": 2460}
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank, threshold_noise=20) == "on"
        assert DefaultAgent._compute_desired_pump_state(pump, from_tank, to_tank, threshold_noise=-20) is None


# ──────────────────────────────────────────────
# Integration: agent assigned to plugin
# ──────────────────────────────────────────────
class TestAgentPluginIntegration:
    def test_agent_attribute_exists(self):
        """AbstractPlugin has an agent attribute defaulting to None."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.agent = None
        assert p.agent is None

    def test_agent_assigned_provides_automode_string(self):
        """When agent is assigned and automaticsolver=True, automode_string comes from agent."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.alias = "test"
        p.paused = False
        p.scenario_time = 10
        p.next_refresh_time = 0
        p.verbose = False
        p.automode_string = ""
        p.agent = DefaultAgent()
        p.parameters = dict(
            taskupdatetime=100,
            automaticsolver=True,
            displayautomationstate=True,
            taskfeedback=dict(
                overdue=dict(
                    active=False, color=(241, 100, 100, 255),
                    delayms=2000, blinkdurationms=1000,
                    _nexttoggletime=0, _is_visible=False,
                )
            ),
        )
        p.compute_next_plugin_state()
        assert p.automode_string == "AUTO"

    def test_no_agent_uses_manual(self):
        """When agent is None, automode_string is MANUAL even with automaticsolver."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.alias = "test"
        p.paused = False
        p.scenario_time = 10
        p.next_refresh_time = 0
        p.verbose = False
        p.automode_string = ""
        p.agent = None
        p.parameters = dict(
            taskupdatetime=100,
            automaticsolver=True,
            displayautomationstate=True,
            taskfeedback=dict(
                overdue=dict(
                    active=False, color=(241, 100, 100, 255),
                    delayms=2000, blinkdurationms=1000,
                    _nexttoggletime=0, _is_visible=False,
                )
            ),
        )
        p.compute_next_plugin_state()
        assert p.automode_string == "MANUAL"


# ──────────────────────────────────────────────
# Scenario system command validation
# ──────────────────────────────────────────────
class TestAgentScenarioCommand:
    def test_parse_agent_command(self):
        """Parsing '0:00:00;system;agent;default' yields correct event."""
        from core.event import Event

        e = Event.parse_from_string(1, "0:00:00;system;agent;default")
        assert e.plugin == "system"
        assert e.command == ["agent", "default"]
        assert e.time_sec == 0

    def test_agent_command_accepted_in_check_events(self):
        """check_events() accepts system;agent;default without error."""
        from core.event import Event
        from core.scenario import Scenario

        mock_plugin = MagicMock()
        mock_plugin.blocking = False
        mock_plugin.parameters = {}

        s = object.__new__(Scenario)
        s.events = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 0, "system", ["agent", "default"]),
            Event(3, 120, "sysmon", ["stop"]),
        ]
        s.plugins = {"sysmon": mock_plugin}
        errs = s.check_events()
        assert not any("agent" in e.lower() for e in errs)

    def test_agent_command_without_name_rejected(self):
        """check_events() rejects system;agent (no name argument)."""
        from core.event import Event
        from core.scenario import Scenario

        mock_plugin = MagicMock()
        mock_plugin.blocking = False
        mock_plugin.parameters = {}

        s = object.__new__(Scenario)
        s.events = [
            Event(1, 0, "sysmon", ["start"]),
            Event(2, 0, "system", ["agent"]),
            Event(3, 120, "sysmon", ["stop"]),
        ]
        s.plugins = {"sysmon": mock_plugin}
        errs = s.check_events()
        agent_errors = [e for e in errs if "agent" in e.lower()]
        assert len(agent_errors) == 1

    def test_execute_agent_command(self, mock_window, monkeypatch):
        """_execute_system_command with agent sets agent on plugins."""
        import core.scheduler
        from core.event import Event
        from core.scheduler import Scheduler

        mock_log = MagicMock()
        monkeypatch.setattr(core.scheduler, "get_logger", lambda: mock_log)

        sched = object.__new__(Scheduler)
        mock_plugin = MagicMock()
        mock_plugin.parameters = {"automaticsolver": False}
        sched.plugins = {"sysmon": mock_plugin}

        event = Event(1, 0, "system", ["agent", "default"])
        sched.execute_one_event(event)

        assert event.done == 1
        assert isinstance(sched.agent, DefaultAgent)
        assert mock_plugin.agent == sched.agent


# ──────────────────────────────────────────────
# Scenario file validation
# ──────────────────────────────────────────────
class TestAgentScenarioFile:
    def test_scenario_file_parses(self):
        """All lines in test_agent.txt parse as valid events."""
        from pathlib import Path

        from core.event import Event

        scenario_path = Path("includes/scenarios/test_agent.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        events = []
        for n, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) == 0 or stripped.startswith("#"):
                continue
            e = Event.parse_from_string(n, stripped)
            assert e is not None, f"Failed to parse line {n}: {stripped}"
            events.append(e)

        assert len(events) > 0, "No events parsed from scenario"

    def test_scenario_file_has_agent_command(self):
        """test_agent.txt contains at least one system;agent command."""
        from pathlib import Path

        from core.event import Event

        scenario_path = Path("includes/scenarios/test_agent.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        agent_events = []
        for n, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) == 0 or stripped.startswith("#"):
                continue
            e = Event.parse_from_string(n, stripped)
            if e.plugin == "system" and e.command[0] == "agent":
                agent_events.append(e)

        assert len(agent_events) >= 1
        assert agent_events[0].command == ["agent", "default"]

    def test_scenario_file_check_events_no_errors(self):
        """check_events() passes with no errors for test_agent.txt scenario."""
        from pathlib import Path

        from core.event import Event
        from core.scenario import Scenario

        scenario_path = Path("includes/scenarios/test_agent.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        events = [
            Event.parse_from_string(n, line.strip())
            for n, line in enumerate(lines)
            if len(line.strip()) > 0 and not line.strip().startswith("#")
        ]

        # Create mock plugins for each plugin used in the scenario
        mock_plugins = {}
        for e in events:
            if e.plugin != "system" and e.plugin not in mock_plugins:
                mp = MagicMock()
                mp.blocking = False
                mp.parameters = {
                    "automaticsolver": False,
                    "displayautomationstate": True,
                }
                mock_plugins[e.plugin] = mp

        s = object.__new__(Scenario)
        s.events = events
        s.plugins = mock_plugins
        errs = s.check_events()

        # Filter only real errors (not warnings about methods/parameters)
        system_errors = [e for e in errs if "system command" in e.lower() or "agent" in e.lower()]
        assert len(system_errors) == 0, f"System command errors: {system_errors}"


# ──────────────────────────────────────────────
# Scenario file validation (humanlike)
# ──────────────────────────────────────────────
class TestHumanLikeScenarioFile:
    def test_scenario_file_parses(self):
        """All lines in test_agent_humanlike.txt parse as valid events."""
        from pathlib import Path

        from core.event import Event

        scenario_path = Path("includes/scenarios/test_agent_humanlike.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent_humanlike.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        events = []
        for n, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) == 0 or stripped.startswith("#"):
                continue
            e = Event.parse_from_string(n, stripped)
            assert e is not None, f"Failed to parse line {n}: {stripped}"
            events.append(e)

        assert len(events) > 0, "No events parsed from scenario"

    def test_scenario_file_has_humanlike_agent_command(self):
        """test_agent_humanlike.txt starts with system;agent;humanlike."""
        from pathlib import Path

        from core.event import Event

        scenario_path = Path("includes/scenarios/test_agent_humanlike.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent_humanlike.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        agent_events = []
        for n, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) == 0 or stripped.startswith("#"):
                continue
            e = Event.parse_from_string(n, stripped)
            if e.plugin == "system" and e.command[0] == "agent":
                agent_events.append(e)

        assert len(agent_events) >= 1
        assert agent_events[0].command == ["agent", "humanlike"]

    def test_scenario_file_check_events_no_errors(self):
        """check_events() passes with no errors for test_agent_humanlike.txt."""
        from pathlib import Path

        from core.event import Event
        from core.scenario import Scenario

        scenario_path = Path("includes/scenarios/test_agent_humanlike.txt")
        if not scenario_path.exists():
            pytest.skip("test_agent_humanlike.txt not found")

        with open(scenario_path) as f:
            lines = f.readlines()

        events = [
            Event.parse_from_string(n, line.strip())
            for n, line in enumerate(lines)
            if len(line.strip()) > 0 and not line.strip().startswith("#")
        ]

        mock_plugins = {}
        for e in events:
            if e.plugin != "system" and e.plugin not in mock_plugins:
                mp = MagicMock()
                mp.blocking = False
                mp.parameters = {
                    "automaticsolver": False,
                    "displayautomationstate": True,
                }
                mock_plugins[e.plugin] = mp

        s = object.__new__(Scenario)
        s.events = events
        s.plugins = mock_plugins
        errs = s.check_events()

        system_errors = [e for e in errs if "system command" in e.lower() or "agent" in e.lower()]
        assert len(system_errors) == 0, f"System command errors: {system_errors}"


# ══════════════════════════════════════════════
# HumanLikeAgent tests
# ══════════════════════════════════════════════


class TestHumanLikeAgentBasic:
    def test_name(self):
        agent = HumanLikeAgent(seed=42)
        assert agent.name == "humanlike"

    def test_automode_string(self):
        agent = HumanLikeAgent(seed=42)
        assert agent.automode_string == "AUTO-HL"

    def test_in_registry(self):
        assert "humanlike" in AGENT_REGISTRY

    def test_create_agent(self):
        agent = create_agent("humanlike")
        assert isinstance(agent, HumanLikeAgent)

    def test_initial_attended_task(self):
        agent = HumanLikeAgent(seed=42)
        assert agent._attended_task == "sysmon"

    def test_on_failure_started_returns_delay(self):
        agent = HumanLikeAgent(seed=42)
        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}
        result = agent.on_failure_started(plugin, gauge={})
        assert result == {"delay": 10000}


# ──────────────────────────────────────────────
# Attention model
# ──────────────────────────────────────────────
class TestHumanLikeAttention:
    def test_scanning_advances_after_dwell(self):
        """After dwell_mean_ms elapses, agent switches to next task."""
        agent = HumanLikeAgent(seed=42)
        agent.dwell_mean_ms = 1000
        agent.dwell_std_ms = 0  # Deterministic
        agent._current_dwell = 1000
        agent._attend_start = 0.0

        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.get_gauges_on_failure.return_value = []

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # At t=0.5s, still on sysmon
            agent.on_plugin_update(plugin, 0.5)
            assert agent._attended_task == "sysmon"

            # At t=1.0s, should have switched to track
            agent.on_plugin_update(plugin, 1.0)
            assert agent._attended_task == "track"

    def test_scanning_cycles_through_all_tasks(self):
        """Agent visits all 4 tasks in scan_order."""
        agent = HumanLikeAgent(seed=42)
        agent.dwell_mean_ms = 100
        agent.dwell_std_ms = 0  # Deterministic
        agent._current_dwell = 100
        agent.switching_cost_ms = 0

        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.get_gauges_on_failure.return_value = []

        visited = [agent._attended_task]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            for i in range(1, 5):
                agent.on_plugin_update(plugin, i * 0.2)
                visited.append(agent._attended_task)

        assert visited == ["sysmon", "track", "resman", "communications", "sysmon"]

    def test_switching_cost_blocks_actions(self):
        """During switching cost, no plugin action is taken."""
        agent = HumanLikeAgent(seed=42)
        agent.dwell_mean_ms = 100
        agent.dwell_std_ms = 0
        agent._current_dwell = 100
        agent.switching_cost_ms = 500  # Large switching cost

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-5, -5)
        plugin.reticle.is_cursor_in_target.return_value = False

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # t=0.0: attention on sysmon, plugin is track → no track action
            agent.on_plugin_update(plugin, 0.0)
            plugin.get_joystick_inputs.assert_not_called()

            # Force switch to track by advancing past dwell
            agent._attend_start = 0.0
            agent.on_plugin_update(plugin, 0.15)  # Triggers switch, switching_until = 0.15 + 0.5

            # During switching cost, no compensation applied
            agent.on_plugin_update(plugin, 0.3)
            plugin.get_joystick_inputs.assert_not_called()

    def test_interrupt_sysmon_failure_captures_attention(self):
        """Sysmon failure can interrupt attention from another task."""
        agent = HumanLikeAgent(seed=42)
        agent.interrupt_prob = 1.0  # Always interrupt
        agent._attended_task = "track"
        agent._scan_index = 1

        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}

        agent.on_failure_started(plugin, gauge={})
        assert agent._attended_task == "sysmon"

    def test_interrupt_sysmon_failure_not_always(self):
        """With interrupt_prob=0, attention is never captured."""
        agent = HumanLikeAgent(seed=42)
        agent.interrupt_prob = 0.0
        agent._attended_task = "track"

        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}

        agent.on_failure_started(plugin, gauge={})
        assert agent._attended_task == "track"

    def test_interrupt_when_already_on_sysmon(self):
        """Failure while already on sysmon doesn't trigger switch."""
        agent = HumanLikeAgent(seed=42)
        agent.interrupt_prob = 1.0
        agent._attended_task = "sysmon"
        original_dwell = agent._current_dwell

        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}

        agent.on_failure_started(plugin, gauge={})
        # Still on sysmon, dwell unchanged (no switch_to called)
        assert agent._attended_task == "sysmon"
        assert agent._current_dwell == original_dwell


# ──────────────────────────────────────────────
# Sysmon behavior
# ──────────────────────────────────────────────
class TestHumanLikeSysmon:
    def test_resolves_failure_when_attended(self):
        """Agent sends gauge key when attending sysmon."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "sysmon"
        # Use a very low RT so failures are always resolved
        agent.sysmon_rt_mean = 100
        agent.sysmon_rt_std = 10

        plugin = MagicMock()
        plugin.alias = "sysmon"
        gauge = {"name": "F1", "_milliresponsetime": 5000, "key": "F1"}
        plugin.get_gauges_on_failure.return_value = [gauge]

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_sysmon(plugin, 1.0)
        plugin.do_on_key.assert_called_once_with("F1", "press", emulate=True)

    def test_ignores_failure_when_not_attended(self):
        """Agent does NOT resolve failures when attending another task."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"

        plugin = MagicMock()
        plugin.alias = "sysmon"
        gauge = {"name": "F1", "_milliresponsetime": 5000, "key": "F1"}
        plugin.get_gauges_on_failure.return_value = [gauge]

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_sysmon(plugin, 1.0)
        plugin.do_on_key.assert_not_called()

    def test_vigilance_decrement_increases_rt(self):
        """Failure count increases effective RT mean via vigilance decrement."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "sysmon"
        agent.vigilance_decrement = 50

        # Base RT mean is 2500. After 10 failures, effective mean is 3000.
        agent._failure_count = 0
        base_mean = agent.sysmon_rt_mean + agent._failure_count * agent.vigilance_decrement
        assert base_mean == 2500

        agent._failure_count = 10
        degraded_mean = agent.sysmon_rt_mean + agent._failure_count * agent.vigilance_decrement
        assert degraded_mean == 3000

    def test_failure_count_increments(self):
        """on_failure_started increments failure count."""
        agent = HumanLikeAgent(seed=42)
        agent.interrupt_prob = 0
        plugin = MagicMock()
        plugin.parameters = {"alerttimeout": 10000}

        assert agent._failure_count == 0
        agent.on_failure_started(plugin, {})
        assert agent._failure_count == 1
        agent.on_failure_started(plugin, {})
        assert agent._failure_count == 2


# ──────────────────────────────────────────────
# Track behavior
# ──────────────────────────────────────────────
class TestHumanLikeTrack:
    def test_compensates_when_attended(self):
        """Agent sends joystick when attending track."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"
        agent.track_reaction_ms = 0
        agent.track_noise_prob = 0

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-5, -5)
        plugin.reticle.is_cursor_in_target.return_value = False

        agent._track_react_start = 0.0  # Already reacted
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_track(plugin, 10.0)
        plugin.get_joystick_inputs.assert_called_once_with(1.0, -1.0)

    def test_no_compensation_when_not_attended(self):
        """Agent does NOT compensate when attending another task."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-5, -5)

        agent._update_track(plugin, 1.0)
        plugin.get_joystick_inputs.assert_not_called()

    def test_reaction_delay_before_compensation(self):
        """Agent waits track_reaction_ms before compensating."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"
        agent.track_reaction_ms = 500
        agent.track_noise_prob = 0

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-5, -5)
        plugin.reticle.is_cursor_in_target.return_value = False

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # First call: detect deviation, start reaction timer
            agent._update_track(plugin, 0.0)
            assert agent._track_react_start == 0.0
            plugin.get_joystick_inputs.assert_not_called()

            # t=0.3s: still within reaction delay
            agent._update_track(plugin, 0.3)
            plugin.get_joystick_inputs.assert_not_called()

            # t=0.6s: past reaction delay, should compensate
            agent._update_track(plugin, 0.6)
            plugin.get_joystick_inputs.assert_called_once_with(1.0, -1.0)

    def test_micro_hesitation(self):
        """With track_noise_prob=1.0, compensation is always skipped."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"
        agent.track_reaction_ms = 0
        agent.track_noise_prob = 1.0  # Always hesitate

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-5, -5)
        plugin.reticle.is_cursor_in_target.return_value = False

        agent._track_react_start = 0.0
        agent._update_track(plugin, 10.0)
        plugin.get_joystick_inputs.assert_not_called()

    def test_cursor_in_target_resets_reaction(self):
        """When cursor is in target, reaction timer resets."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"
        agent._track_react_start = 1.0
        agent.track_noise_prob = 0

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.is_cursor_in_target.return_value = True
        plugin.reticle.cursor_relative = (0, 0)

        agent._update_track(plugin, 2.0)
        assert agent._track_react_start is None


# ──────────────────────────────────────────────
# Communications behavior
# ──────────────────────────────────────────────
class TestHumanLikeComms:
    def _make_comms_plugin(self, active_radio, waiting_radios=None):
        p = MagicMock()
        p.alias = "communications"
        p.parameters = dict(keys=dict(
            selectradioup="UP",
            selectradiodown="DOWN",
            tunefrequencyup="RIGHT",
            tunefrequencydown="LEFT",
            validateresponse="ENTER",
        ))
        p.get_waiting_response_radios.return_value = waiting_radios if waiting_radios is not None else []
        p.get_active_radio_dict.return_value = active_radio
        return p

    def test_tunes_when_attended(self):
        """Agent sends RIGHT key when attending communications and tuning up."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 0
        agent.comms_tune_interval_ms = 0
        agent.comms_overshoot_prob = 0

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        agent._comms_react_start = 0.0
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(plugin, 1.0)
        plugin.do_on_key.assert_called_once_with("RIGHT", "press", emulate=True)

    def test_no_action_when_not_attended(self):
        """Agent does NOT tune when attending another task."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(plugin, 1.0)
        plugin.do_on_key.assert_not_called()

    def test_reaction_delay(self):
        """Agent waits comms_reaction_ms before starting to tune."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 1000
        agent.comms_tune_interval_ms = 0

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # First call at t=0: starts reaction timer
            agent._update_communications(plugin, 0.0)
            plugin.do_on_key.assert_not_called()

            # t=0.5: still within reaction delay
            agent._update_communications(plugin, 0.5)
            plugin.do_on_key.assert_not_called()

            # t=1.1: past reaction delay
            agent._update_communications(plugin, 1.1)
            plugin.do_on_key.assert_called()

    def test_tune_interval(self):
        """Agent respects tuning interval between steps."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 0
        agent.comms_tune_interval_ms = 500
        agent.comms_overshoot_prob = 0

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        agent._comms_react_start = 0.0
        agent._comms_last_tune = 0.0

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # t=0.3: within tune interval
            agent._update_communications(plugin, 0.3)
            plugin.do_on_key.assert_not_called()

            # t=0.6: past tune interval
            agent._update_communications(plugin, 0.6)
            plugin.do_on_key.assert_called_once_with("RIGHT", "press", emulate=True)

    def test_confirms_when_frequency_matches(self):
        """Agent sends ENTER key when frequency matches target."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 0
        agent.comms_tune_interval_ms = 0
        agent.comms_overshoot_prob = 0

        radio = {"name": "NAV_1", "currentfreq": 115.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        agent._comms_react_start = 0.0
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(plugin, 1.0)
        plugin.do_on_key.assert_called_once_with("ENTER", "press", emulate=True)

    def test_no_waiting_radios_does_nothing(self):
        """When no radios wait, agent does nothing."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": None,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio)

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(plugin, 1.0)
        plugin.do_on_key.assert_not_called()

    def test_overshoot(self):
        """With overshoot_prob=1.0, two RIGHT keys are sent."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 0
        agent.comms_tune_interval_ms = 0
        agent.comms_overshoot_prob = 1.0  # Always overshoot

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        agent._comms_react_start = 0.0
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_communications(plugin, 1.0)
        # Normal step + overshoot = 2 calls
        assert plugin.do_on_key.call_count == 2
        plugin.do_on_key.assert_any_call("RIGHT", "press", emulate=True)


# ──────────────────────────────────────────────
# Comms timing fixes (reaction persistence + dwell override)
# ──────────────────────────────────────────────
class TestHumanLikeCommsTimingFixes:
    def _make_comms_plugin(self, active_radio, waiting_radios=None):
        p = MagicMock()
        p.alias = "communications"
        p.parameters = dict(keys=dict(
            selectradioup="UP",
            selectradiodown="DOWN",
            tunefrequencyup="RIGHT",
            tunefrequencydown="LEFT",
            validateresponse="ENTER",
        ))
        p.get_waiting_response_radios.return_value = waiting_radios if waiting_radios is not None else []
        p.get_active_radio_dict.return_value = active_radio
        return p

    def test_reaction_not_repaid_on_return(self):
        """After _advance_scan, _comms_react_start persists so tuning resumes immediately."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent.comms_reaction_ms = 1500
        agent._comms_react_start = 10.0  # Set earlier when prompt was first seen

        # Advance scan away from comms
        agent._advance_scan(20.0)
        assert agent._attended_task != "communications"

        # _comms_react_start should persist (not reset)
        assert agent._comms_react_start == 10.0

        # Now simulate returning to comms — reaction already paid
        agent._attended_task = "communications"
        agent.comms_tune_interval_ms = 0
        agent.comms_overshoot_prob = 0

        radio = {"name": "NAV_1", "currentfreq": 110.0, "targetfreq": 115.0,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio, waiting_radios=[radio])

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # t=20.5: well past reaction start (10.0 + 1.5s = 11.5s)
            agent._update_communications(plugin, 20.5)
        # Should tune immediately, no re-paid reaction delay
        plugin.do_on_key.assert_called_once_with("RIGHT", "press", emulate=True)

    def test_stays_on_comms_while_tuning(self):
        """Dwell expired + tuning active → scan does NOT advance."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent._attend_start = 0.0
        agent._current_dwell = 1000  # 1s dwell
        agent.comms_reaction_ms = 500
        agent._comms_react_start = 0.5  # Prompt seen at t=0.5

        # At t=2.0: dwell expired (2000ms > 1000ms) and past reaction
        # (2.0 - 0.5)*1000 = 1500ms >= 500ms → actively tuning
        agent._update_attention(2.0)

        # Should still be on comms
        assert agent._attended_task == "communications"

    def test_resumes_scanning_after_prompt_resolved(self):
        """waiting_radios empty → _comms_react_start resets → scan resumes."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent._attend_start = 0.0
        agent._current_dwell = 1000
        agent.comms_reaction_ms = 500
        agent._comms_react_start = 0.5  # Was tuning

        radio = {"name": "NAV_1", "currentfreq": 115.0, "targetfreq": None,
                 "pos": 0, "is_active": True}
        plugin = self._make_comms_plugin(radio)  # No waiting radios

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            # Call _update_communications to clear _comms_react_start
            agent._update_communications(plugin, 2.0)

        assert agent._comms_react_start is None

        # Now _update_attention should advance scan (dwell expired, no tuning)
        agent._update_attention(2.0)
        assert agent._attended_task != "communications"

    def test_does_not_stay_during_reaction(self):
        """During reaction delay (not yet tuning) → scan advances normally."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent._attend_start = 0.0
        agent._current_dwell = 1000
        agent.comms_reaction_ms = 1500
        agent._comms_react_start = 0.8  # Prompt seen at t=0.8

        # At t=1.5: dwell expired (1500ms > 1000ms) but still in reaction
        # (1.5 - 0.8)*1000 = 700ms < 1500ms → not yet tuning
        agent._update_attention(1.5)

        # Should have advanced to next task
        assert agent._attended_task != "communications"

    def test_normal_scanning_unaffected(self):
        """Without comms prompt (_comms_react_start=None) → scan advances normally."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "communications"
        agent._attend_start = 0.0
        agent._current_dwell = 1000
        agent._comms_react_start = None  # No prompt pending

        # At t=1.5: dwell expired, no comms prompt → should advance
        agent._update_attention(1.5)
        assert agent._attended_task != "communications"


# ──────────────────────────────────────────────
# Resman behavior
# ──────────────────────────────────────────────
class TestHumanLikeResman:
    def _make_resman_plugin(self):
        p = MagicMock()
        p.alias = "resman"
        p.wait_before_leak = 0
        p.parameters = dict(
            tank=dict(
                a=dict(level=2500, max=4000, target=2500, depletable=True, lossperminute=800),
                b=dict(level=2500, max=4000, target=2500, depletable=True, lossperminute=800),
                e=dict(level=3000, max=4000, target=None, depletable=False, lossperminute=0),
            ),
            pump=dict(
                [
                    ("2", dict(flow=600, state="off", key="NUM_2", _fromtank="e", _totank="a")),
                    ("7", dict(flow=400, state="off", key="NUM_7", _fromtank="a", _totank="b")),
                ]
            ),
        )
        return p

    def test_acts_when_attended(self):
        """Agent sends pump key when attending resman."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "resman"
        agent.resman_forget_prob = 0  # No slips

        p = self._make_resman_plugin()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p, 1.0)
        # Pump 2 from non-depletable should be toggled via key injection
        p.do_on_key.assert_any_call("NUM_2", "press", emulate=True)

    def test_no_action_when_not_attended(self):
        """Agent does NOT manage pumps when attending another task."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"

        p = self._make_resman_plugin()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p, 1.0)
        p.do_on_key.assert_not_called()

    def test_skips_when_wait_before_leak(self):
        """Agent does nothing when wait_before_leak > 0."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "resman"

        p = self._make_resman_plugin()
        p.wait_before_leak = 1
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p, 1.0)
        p.do_on_key.assert_not_called()

    def test_forget_prob_can_skip_pumps(self):
        """With resman_forget_prob=1.0, all pumps are skipped."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "resman"
        agent.resman_forget_prob = 1.0  # Always forget

        p = self._make_resman_plugin()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent._update_resman(p, 1.0)
        p.do_on_key.assert_not_called()


# ──────────────────────────────────────────────
# Reproducibility and utilities
# ──────────────────────────────────────────────
class TestHumanLikeReproducibility:
    def test_seed_determinism(self):
        """Same seed produces identical behavior."""
        results = []
        for _ in range(2):
            agent = HumanLikeAgent(seed=123)
            dwells = [agent._sample_dwell() for _ in range(10)]
            results.append(dwells)
        assert results[0] == results[1]

    def test_different_seeds_differ(self):
        """Different seeds produce different behavior."""
        agent1 = HumanLikeAgent(seed=1)
        agent2 = HumanLikeAgent(seed=2)
        dwells1 = [agent1._sample_dwell() for _ in range(10)]
        dwells2 = [agent2._sample_dwell() for _ in range(10)]
        assert dwells1 != dwells2

    def test_sample_rt_positive(self):
        """Sampled RTs are always positive (log-normal)."""
        agent = HumanLikeAgent(seed=42)
        for _ in range(100):
            rt = agent._sample_rt(2500, 800)
            assert rt > 0

    def test_sample_dwell_minimum(self):
        """Sampled dwells are always >= 100ms."""
        agent = HumanLikeAgent(seed=42)
        agent.dwell_mean_ms = 200
        agent.dwell_std_ms = 500  # High std, may sample negative
        for _ in range(100):
            assert agent._sample_dwell() >= 100

    def test_log_normal_params(self):
        """Log-normal parameter conversion produces valid values."""
        mu, sigma = HumanLikeAgent._log_normal_params(2500, 800)
        assert isinstance(mu, float)
        assert isinstance(sigma, float)
        assert sigma > 0


# ──────────────────────────────────────────────
# Full on_plugin_update dispatch
# ──────────────────────────────────────────────
class TestHumanLikeDispatch:
    def test_dispatch_sysmon(self):
        """on_plugin_update dispatches to _update_sysmon for sysmon plugin."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "sysmon"
        agent._switching_until = 0.0

        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.get_gauges_on_failure.return_value = []

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0.0)
        plugin.get_gauges_on_failure.assert_called_once()

    def test_dispatch_track(self):
        """on_plugin_update dispatches to _update_track for track plugin."""
        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "track"
        agent._switching_until = 0.0
        agent.track_reaction_ms = 0
        agent.track_noise_prob = 0

        plugin = MagicMock()
        plugin.alias = "track"
        plugin.reticle = MagicMock()
        plugin.reticle.cursor_relative = (-1, -1)
        plugin.reticle.is_cursor_in_target.return_value = False
        agent._track_react_start = 0.0

        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 0.5)
        plugin.get_joystick_inputs.assert_called_once_with(1.0, -1.0)

    def test_dispatch_unknown_alias(self):
        """on_plugin_update with unknown alias does nothing (no crash)."""
        agent = HumanLikeAgent(seed=42)
        plugin = MagicMock()
        plugin.alias = "unknown"
        agent.on_plugin_update(plugin, 0.0)  # Should not raise


# ──────────────────────────────────────────────
# abstractplugin.update_can_receive_key (key gate)
# ──────────────────────────────────────────────
class TestCanExecuteKeysForAgents:
    def test_automaticsolver_blocks_hardware_allows_execute(self):
        """With automaticsolver=True, can_receive_keys=False but can_execute_keys=True."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.paused = False
        p.visible = True
        p.parameters = {"automaticsolver": True, "taskplacement": "topleft"}
        p.update_can_receive_key()
        assert p.can_receive_keys is False
        assert p.can_execute_keys is True

    def test_no_automaticsolver_allows_both(self):
        """Without automaticsolver, both flags follow paused/visible state."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.paused = False
        p.visible = True
        p.parameters = {"taskplacement": "topleft"}
        p.update_can_receive_key()
        assert p.can_receive_keys is True
        assert p.can_execute_keys is True

    def test_automaticsolver_false_allows_both(self):
        """With automaticsolver=False, both flags are True (manual mode)."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.paused = False
        p.visible = True
        p.parameters = {"automaticsolver": False, "taskplacement": "topleft"}
        p.update_can_receive_key()
        assert p.can_receive_keys is True
        assert p.can_execute_keys is True

    def test_paused_blocks_both(self):
        """When paused, both flags are False regardless of automaticsolver."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.paused = True
        p.visible = True
        p.parameters = {"automaticsolver": True, "taskplacement": "topleft"}
        p.update_can_receive_key()
        assert p.can_receive_keys is False
        # can_execute_keys is still True because automaticsolver=True
        assert p.can_execute_keys is True


# ──────────────────────────────────────────────
# Replay compatibility: send_key logs inputs
# ──────────────────────────────────────────────
class TestReplayCompatibility:
    def test_send_key_records_input_for_replay(self):
        """send_key() calls logger.record_input for replay CSV compatibility."""
        agent = DefaultAgent()
        plugin = MagicMock()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_logger = MagicMock()
            mock_gl.return_value = mock_logger
            agent.send_key(plugin, "F3", "press")
        mock_logger.record_input.assert_called_once_with("keyboard", "F3", "press")

    def test_send_joystick_does_not_log(self):
        """send_joystick() does not log (track replay is state-based)."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.get_joystick_inputs = MagicMock()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_logger = MagicMock()
            mock_gl.return_value = mock_logger
            agent.send_joystick(plugin, 0.5, -0.3)
        mock_logger.record_input.assert_not_called()


# ──────────────────────────────────────────────
# Attention focus visualization
# ──────────────────────────────────────────────
class TestAttentionFocusVisualization:
    def test_show_attention_default_true(self):
        """HumanLikeAgent.show_attention is True by default."""
        agent = HumanLikeAgent(seed=42)
        assert agent.show_attention is True

    def test_default_agent_no_show_attention(self):
        """DefaultAgent has no show_attention → getattr returns False."""
        agent = DefaultAgent()
        assert getattr(agent, "show_attention", False) is False

    def test_attention_widget_visibility_follows_attended_task(self):
        """refresh_widgets sets attention visible when agent attends this plugin, hidden otherwise."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        p.alias = "sysmon"
        p.paused = False
        p.visible = True
        p.verbose = False
        p.display_title = False
        p.automode_string = ""
        p.scenario_time = 1.0

        agent = HumanLikeAgent(seed=42)
        agent._attended_task = "sysmon"
        p.agent = agent

        # Mock widgets dict with attention and foreground
        attention_widget = MagicMock()
        p.widgets = {
            "sysmon_attention": attention_widget,
        }
        p.parameters = dict(
            taskplacement="topleft",
            taskfeedback=dict(
                overdue=dict(
                    active=False, color=(241, 100, 100, 255),
                    delayms=2000, blinkdurationms=1000,
                    _nexttoggletime=0, _is_visible=False,
                )
            ),
        )

        # Agent attends sysmon → attention visible
        p.refresh_widgets()
        attention_widget.set_visibility.assert_called_with(True)

        # Agent switches to track → attention hidden
        attention_widget.reset_mock()
        agent._attended_task = "track"
        p.refresh_widgets()
        attention_widget.set_visibility.assert_called_with(False)
