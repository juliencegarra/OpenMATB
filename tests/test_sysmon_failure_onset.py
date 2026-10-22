"""Sysmon: a scale failure must be visible on the frame that starts its response timer.

The response time is measured from the onset (the first frame after start_failure). If the arrow
only reaches its failure zone at the next task step, every scale response time includes a step
(taskupdatetime, 200 ms by default) during which nothing was visible, unlike the lights.
"""

from unittest.mock import patch

from plugins.abstractplugin import AbstractPlugin
from tests.test_sysmon_logic import _make_sysmon


def _step(s):
    with patch.object(AbstractPlugin, "compute_next_plugin_state", return_value=True):
        s.compute_next_plugin_state()


@patch("plugins.abstractplugin.timing.call_on_flip")
def test_scale_arrow_in_failure_zone_when_response_timer_starts(_flip):
    s = _make_sysmon()
    scale = s.parameters["scales"]["1"]
    scale["side"] = 1
    scale["failure"] = True

    _step(s)

    assert scale["_onfailure"] and scale["_response_start"] is not None
    # The frame showing this state stamps the onset: the arrow must already be in the failure zone
    assert scale["_pos"] in s.scale_zones[1], f"arrow at {scale['_pos']}, still in the normal zone"


@patch("plugins.abstractplugin.timing.call_on_flip")
def test_light_failure_visible_when_response_timer_starts(_flip):
    """The lights change on the same step (the reference behaviour)."""
    s = _make_sysmon()
    light = s.parameters["lights"]["1"]
    light["failure"] = True

    _step(s)

    assert light["_onfailure"] and light["_response_start"] is not None
    assert light["on"] is False
