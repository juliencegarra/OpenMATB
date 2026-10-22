"""Browser: a warning when the session file of the scenario may exceed what a destination accepts.

DataPipe accepts 32 MB per request (about 1 h 40 of session once compressed), JATOS 30 MB per result file by default
(about 2 h 08): a longer session file would not be received.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.event import Event
from core.scenario import Scenario


def _warnings(last_event_sec, destinations):
    scenario = object.__new__(Scenario)
    scenario.events = [Event(1, 0, "sysmon", "start"), Event(2, last_event_sec, "sysmon", "stop")]
    errors = MagicMock()
    with (
        patch("core.scenario.has_conf_value", return_value=True),
        patch("core.scenario.get_conf_value", return_value=destinations),
        patch("core.scenario.get_errors", return_value=errors),
    ):
        scenario.check_session_size()
    return [c.args[0] for c in errors.add_error.call_args_list]


@pytest.mark.parametrize(
    "minutes, destinations, warned",
    [
        (95, "datapipe", True),  # Beyond 90 min (32 MB at 19 MB per hour, 10 % of margin)
        (85, "datapipe", False),
        (95, "jatos", False),  # Up to 115 min (30 MB at 14 MB per hour)
        (120, "jatos", True),
        (95, "webdav, download", False),  # No limit known
        (95, "download, datapipe", True),
    ],
)
def test_warning_beyond_the_limit_of_a_destination(minutes, destinations, warned):
    warnings = _warnings(minutes * 60, destinations)
    assert bool(warnings) == warned
    if warned:
        assert f"{minutes} min" in warnings[0]


def test_only_in_the_browser(tmp_path, mock_errors, mock_logger):
    """Desktop: the session file stays on the disk."""
    scenario_path = tmp_path / "long.txt"
    scenario_path.write_text("0:00:00;sysmon;start\n3:00:00;sysmon;stop\n", encoding="utf-8")
    with (
        patch("core.scenario.IS_WEB", False),
        patch.object(Scenario, "check_session_size") as check,
        patch.dict("core.constants.PATHS", {"SCENARIO_ERRORS": tmp_path / "errors.log"}),
    ):
        Scenario(scenario_path=scenario_path)
    check.assert_not_called()
