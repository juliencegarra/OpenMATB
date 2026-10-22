"""Parallel port: a trigger being sent when the plugin stops must be lowered.

Only compute_next_plugin_state lowers the data lines after delayms, and it no longer runs once the
plugin is stopped: a trigger sent just before the stop (e.g. an end-of-block marker) stayed on
the port after the end of the session.
"""

from unittest.mock import patch

from plugins.abstractplugin import AbstractPlugin
from tests.test_parallelport_logic import _make_pp


@patch.object(AbstractPlugin, "hide")
@patch.object(AbstractPlugin, "pause")
def test_stop_lowers_the_trigger_being_sent(_pause, _hide):
    pp = _make_pp()
    pp.parameters["trigger"] = 99
    pp.compute_next_plugin_state()  # The marker is raised
    pp._port.setData.assert_called_with(99)

    pp.stop()

    pp._port.setData.assert_called_with(0)


@patch.object(AbstractPlugin, "hide")
@patch.object(AbstractPlugin, "pause")
def test_stop_drops_the_triggers_awaiting(_pause, _hide):
    pp = _make_pp(_awaiting_triggers=[5, 6])
    pp.stop()
    assert pp._awaiting_triggers == []
    pp._port.setData.assert_not_called()  # Nothing was being sent


def test_trigger_value_is_one_byte():
    """The 8 data lines: 256 was accepted (sent as 0, or a crash of pyparallel on Linux)."""
    from core.validation import is_trigger_value

    assert is_trigger_value("255") == (255, None)
    assert is_trigger_value("256")[0] is None
    assert is_trigger_value("0")[0] is None
