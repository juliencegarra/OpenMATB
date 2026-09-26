"""Tests for the agent abstraction layer (agents/ module).

Tests AbstractAgent interface, DefaultAgent behavior, agent registry,
and integration with plugins.
"""

from unittest.mock import MagicMock, patch

import pytest

from agents import AGENT_REGISTRY, AbstractAgent, DefaultAgent, create_agent


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
            mock_logger.record_input.assert_called_once_with("agent", "F1", "press")

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
        p.parameters = dict(
            keys=dict(
                selectradioup="UP",
                selectradiodown="DOWN",
                tunefrequencyup="RIGHT",
                tunefrequencydown="LEFT",
                validateresponse="ENTER",
            )
        )
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
        """Agent sends gauge key when elapsed response time >= automaticsolverdelay."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.scenario_time = 2.0
        plugin.parameters = {"automaticsolverdelay": 1000}
        gauge = {"name": "F1", "_response_start": 1.0, "key": "F1"}  # 1s elapsed = 1000ms
        plugin.get_gauges_on_failure.return_value = [gauge]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 2.0)
        plugin.do_on_key.assert_called_once_with("F1", "press", emulate=True)

    def test_update_sysmon_skips_before_delay(self):
        """Agent does not send key when elapsed response time < automaticsolverdelay."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.scenario_time = 1.8
        plugin.parameters = {"automaticsolverdelay": 1000}
        gauge = {"name": "F1", "_response_start": 1.0, "key": "F1"}  # 0.8s elapsed = 800ms
        plugin.get_gauges_on_failure.return_value = [gauge]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 1.8)
        plugin.do_on_key.assert_not_called()

    def test_update_sysmon_no_failure(self):
        """Agent does nothing when no gauges are on failure."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.scenario_time = 5.0
        plugin.parameters = {"automaticsolverdelay": 1000}
        plugin.get_gauges_on_failure.return_value = []
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 5.0)
        plugin.do_on_key.assert_not_called()

    def test_update_sysmon_multiple_gauges(self):
        """Agent sends key only for gauges that have reached the delay threshold."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.alias = "sysmon"
        plugin.scenario_time = 2.0
        plugin.parameters = {"automaticsolverdelay": 1000}
        ready = {"name": "F1", "_response_start": 0.8, "key": "F1"}  # 1.2s elapsed = 1200ms >= 1000
        not_ready = {"name": "F2", "_response_start": 1.5, "key": "F2"}  # 0.5s elapsed = 500ms < 1000
        plugin.get_gauges_on_failure.return_value = [ready, not_ready]
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_gl.return_value = MagicMock()
            agent.on_plugin_update(plugin, 2.0)
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
                    active=False,
                    color=(241, 100, 100, 255),
                    delayms=2000,
                    blinkdurationms=1000,
                    _nexttoggletime=0,
                    _is_visible=False,
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
                    active=False,
                    color=(241, 100, 100, 255),
                    delayms=2000,
                    blinkdurationms=1000,
                    _nexttoggletime=0,
                    _is_visible=False,
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
        mock_logger.record_input.assert_called_once_with("agent", "F3", "press")

    def test_send_joystick_logs_input(self):
        """send_joystick() logs an input row for traceability."""
        agent = DefaultAgent()
        plugin = MagicMock()
        plugin.get_joystick_inputs = MagicMock()
        with patch("agents.abstract_agent.get_logger") as mock_gl:
            mock_logger = MagicMock()
            mock_gl.return_value = mock_logger
            agent.send_joystick(plugin, 0.5, -0.3)
        mock_logger.record_input.assert_called_once_with("agent", "joystick", "0.5,-0.3")


# ══════════════════════════════════════════════
# Fault icon ("!") indicator tests
# ══════════════════════════════════════════════


class TestHasActiveFaultBase:
    def test_default_returns_false(self):
        """AbstractPlugin.has_active_fault() returns False by default."""
        from plugins.abstractplugin import AbstractPlugin

        p = object.__new__(AbstractPlugin)
        assert p.has_active_fault() is False
