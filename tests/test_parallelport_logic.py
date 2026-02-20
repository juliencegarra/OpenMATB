"""Tests for plugins.parallelport - Trigger state machine logic."""

from unittest.mock import MagicMock, patch

from plugins.parallelport import Parallelport


def _make_pp(**overrides):
    """Create a Parallelport instance bypassing __init__ to avoid hardware access."""
    pp = object.__new__(Parallelport)
    pp.alias = "parallelport"
    pp.scenario_time = 1.0
    pp.next_refresh_time = 0
    pp.paused = False
    pp.verbose = False
    pp.automode_string = ""
    pp._port = MagicMock()
    pp._downvalue = 0
    pp._last_trigger = 0
    pp._triggertimerms = 0
    pp._awaiting_triggers = []
    pp.logger = MagicMock()
    pp.parameters = dict(
        taskupdatetime=5,
        trigger=0,
        delayms=5,
        displayautomationstate=False,
    )
    pp.__dict__.update(overrides)
    return pp


# ── is_trigger_being_sent ────────────────────────


class TestIsTriggerBeingSent:
    def test_no_trigger(self):
        """Returns False when last trigger equals down value."""
        pp = _make_pp()
        assert pp.is_trigger_being_sent() is False

    def test_trigger_active(self):
        """Returns True when last trigger differs from down value."""
        pp = _make_pp()
        pp._last_trigger = 42
        assert pp.is_trigger_being_sent() is True


# ── set_trigger_value ────────────────────────────


class TestSetTriggerValue:
    def test_sends_to_port(self):
        """Value is sent to the parallel port."""
        pp = _make_pp()
        pp.set_trigger_value(10)
        pp._port.setData.assert_called_once_with(10)

    def test_resets_timer(self):
        """Timer is reset to 0 on trigger send."""
        pp = _make_pp()
        pp._triggertimerms = 100
        pp.set_trigger_value(10)
        assert pp._triggertimerms == 0

    def test_updates_last_trigger(self):
        """_last_trigger is set to the sent value."""
        pp = _make_pp()
        pp.set_trigger_value(42)
        assert pp._last_trigger == 42

    @patch("plugins.parallelport.logger")
    def test_logs_state(self, mock_logger):
        """Trigger value is logged via module-level logger."""
        pp = _make_pp()
        pp.set_trigger_value(10)
        mock_logger.record_state.assert_called_once()


# ── compute_next_plugin_state — trigger lifecycle ─


class TestTriggerSend:
    def test_sends_new_trigger(self):
        """Non-zero trigger is sent to port and reset to 0."""
        pp = _make_pp()
        pp.parameters["trigger"] = 42
        pp.compute_next_plugin_state()
        pp._port.setData.assert_called_with(42)
        assert pp.parameters["trigger"] == 0

    def test_no_trigger_no_send(self):
        """Zero trigger causes no port activity."""
        pp = _make_pp()
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        pp._port.setData.assert_not_called()


class TestTriggerQueue:
    def test_queues_while_sending(self):
        """New trigger while one is active gets queued."""
        pp = _make_pp()
        pp._last_trigger = 10  # trigger already being sent
        pp.parameters["trigger"] = 20
        pp.compute_next_plugin_state()
        assert 20 in pp._awaiting_triggers
        assert pp.parameters["trigger"] == 0

    def test_dequeues_after_previous_ends(self):
        """Queued trigger is sent once previous trigger finishes."""
        pp = _make_pp()
        pp._awaiting_triggers = [55]
        pp._last_trigger = 0  # no active trigger
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        pp._port.setData.assert_called_with(55)
        assert pp._awaiting_triggers == []

    def test_multiple_queued_triggers(self):
        """Multiple queued triggers are dequeued one at a time."""
        pp = _make_pp()
        pp._awaiting_triggers = [10, 20, 30]
        pp._last_trigger = 0
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        # Only first is sent
        pp._port.setData.assert_called_with(10)
        assert pp._awaiting_triggers == [20, 30]


class TestTriggerTimeout:
    def test_resets_after_delay(self):
        """Trigger is reset to down value after delayms."""
        pp = _make_pp()
        pp._last_trigger = 42
        pp._triggertimerms = 5  # equals delayms
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        # Should have sent down value
        pp._port.setData.assert_called_with(0)

    def test_timer_grows_while_active(self):
        """Timer increments by taskupdatetime each cycle."""
        pp = _make_pp()
        pp._last_trigger = 42
        pp._triggertimerms = 0
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        assert pp._triggertimerms == 5  # taskupdatetime

    def test_not_reset_before_delay(self):
        """Trigger stays active before delayms is reached."""
        pp = _make_pp()
        pp._last_trigger = 42
        pp._triggertimerms = 2  # < delayms (5)
        pp.parameters["trigger"] = 0
        pp.compute_next_plugin_state()
        # setData called only for timer increment, not for reset
        # _last_trigger should still be 42 (timer was 2, now 7, but reset happens first)
        # Actually let's trace: trigger=0 (no new trigger), no awaiting,
        # is_trigger_being_sent=True and _triggertimerms(2) < delayms(5) → no reset
        # then timer grows: 2 + 5 = 7
        assert pp._triggertimerms == 7


class TestFullLifecycle:
    def test_send_wait_reset(self):
        """Full cycle: send trigger → wait → auto-reset to 0."""
        pp = _make_pp()
        pp.parameters["delayms"] = 5
        pp.parameters["taskupdatetime"] = 5

        # Step 1: set a trigger
        pp.parameters["trigger"] = 99
        pp.compute_next_plugin_state()
        assert pp._last_trigger == 99
        assert pp._triggertimerms == 5  # grew during this cycle
        pp._port.reset_mock()

        # Step 2: advance time, trigger should be reset (timer=5 >= delayms=5)
        pp.scenario_time += 0.005
        pp.next_refresh_time = pp.scenario_time
        pp.compute_next_plugin_state()
        pp._port.setData.assert_called_with(0)  # reset
        assert pp._last_trigger == 0
