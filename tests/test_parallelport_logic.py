"""Tests for plugins.parallelport - Trigger state machine logic."""

import builtins
from unittest.mock import MagicMock, patch

from plugins.abstractplugin import AbstractPlugin
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
    pp.agent = None
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

    @patch("plugins.parallelport.get_logger")
    def test_logs_state(self, mock_get_logger):
        """Trigger value is logged via get_logger()."""
        pp = _make_pp()
        pp.set_trigger_value(10)
        mock_get_logger.return_value.record_state.assert_called_once()


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


# ── compute_next_plugin_state with _port=None ────


class TestComputeWithoutPort:
    def test_returns_immediately_when_port_is_none(self):
        """compute_next_plugin_state() returns without error when _port is None."""
        pp = _make_pp()
        pp._port = None
        # Should not raise AttributeError
        pp.compute_next_plugin_state()

    def test_no_side_effects_when_port_is_none(self):
        """No trigger logic runs when _port is None."""
        pp = _make_pp()
        pp._port = None
        pp.parameters["trigger"] = 42
        pp.compute_next_plugin_state()
        # trigger value should remain unchanged (guard exits before logic)
        assert pp.parameters["trigger"] == 42


# ── __init__ platform and import error handling ───


def _make_init_pp(mock_errors, platform, import_side_effect=None, parallel_side_effect=None):
    """Helper to create a Parallelport via __init__ with mocked platform/imports."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "parallel":
            if import_side_effect is not None:
                raise import_side_effect
            mod = MagicMock()
            if parallel_side_effect is not None:
                mod.Parallel.side_effect = parallel_side_effect
            return mod
        return real_import(name, *args, **kwargs)

    def fake_super_init(self, *a, **k):
        self.parameters = {}

    with (
        patch("sys.platform", platform),
        patch("plugins.parallelport.get_errors", return_value=mock_errors),
        patch("builtins.__import__", side_effect=fake_import),
    ):
        pp = Parallelport.__new__(Parallelport)
        with patch.object(AbstractPlugin, "__init__", fake_super_init):
            Parallelport.__init__(pp)
    return pp


class TestParallelportInit:
    def test_macos_reports_unsupported(self):
        """On macOS, an error about unsupported platform is reported."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "darwin")
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "macOS" in msg
        assert pp._port is None

    def test_windows_import_error(self):
        """On Windows, ImportError mentions pyparallel and InpOut32."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "win32", import_side_effect=ImportError())
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "pyparallel" in msg
        assert "InpOut32" in msg
        assert pp._port is None

    def test_linux_import_error(self):
        """On Linux, ImportError mentions pyparallel and ppdev."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "linux", import_side_effect=ImportError())
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "pyparallel" in msg
        assert "ppdev" in msg
        assert pp._port is None

    def test_windows_file_not_found(self):
        """On Windows, FileNotFoundError mentions InpOut32 driver."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "win32", parallel_side_effect=FileNotFoundError("no dll"))
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "InpOut32" in msg
        assert "simpleio.dll" in msg
        assert pp._port is None

    def test_linux_file_not_found(self):
        """On Linux, FileNotFoundError mentions /dev/parport0."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "linux", parallel_side_effect=FileNotFoundError("/dev/parport0"))
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "/dev/parport0" in msg
        assert pp._port is None

    def test_generic_os_error(self):
        """Generic OSError includes the error message."""
        errors = MagicMock()
        pp = _make_init_pp(errors, "win32", parallel_side_effect=OSError("device busy"))
        errors.add_error.assert_called_once()
        msg = errors.add_error.call_args[0][0]
        assert "device busy" in msg
        assert pp._port is None
