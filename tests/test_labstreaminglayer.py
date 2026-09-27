"""Tests for plugins.labstreaminglayer when pylsl is not available (missing module, browser)."""

from unittest.mock import MagicMock, patch

import plugins.labstreaminglayer as lsl_module
from plugins.labstreaminglayer import Labstreaminglayer


def _make_lsl():
    lsl = object.__new__(Labstreaminglayer)
    lsl.parameters = {"marker": "", "streamsession": False, "pauseatstart": False}
    lsl.stream_info = None
    lsl.stream_outlet = None
    lsl._logged_offset = None
    lsl.lsl_wait_msg = "Please enable the OpenMATB stream into your LabRecorder."
    lsl.logger = MagicMock()
    return lsl


class TestWithoutPylsl:
    def test_start_reports_error_instead_of_crashing(self):
        lsl = _make_lsl()
        errors = MagicMock()
        with (
            patch.object(lsl_module, "pylsl", None),
            patch.object(lsl_module, "get_errors", return_value=errors),
            patch("plugins.instructions.Instructions.start"),
        ):
            lsl.start()
        errors.add_error.assert_called_once()
        assert lsl.stream_outlet is None

    def test_push_without_outlet_is_ignored(self):
        lsl = _make_lsl()
        lsl.push("marker")  # must not raise


class FakeWebOutlet:
    """core.platform.WebLslOutlet: the markers go to the LSL bridge through the page."""

    def __init__(self) -> None:
        self.samples: list = []
        self.offset: float | None = None

    def push_sample(self, sample, timestamp=None) -> None:
        self.samples.append(sample)

    def clock_offset(self):
        return self.offset


class TestInTheBrowser:
    def start(self, lsl, outlet, **parameters):
        lsl.parameters.update(parameters)
        errors = MagicMock()
        with (
            patch.object(lsl_module, "IS_WEB", True),
            patch.object(lsl_module, "pylsl", None),
            patch.object(lsl_module, "web_lsl_outlet", return_value=outlet),
            patch.object(lsl_module, "get_errors", return_value=errors),
            patch("plugins.instructions.Instructions.start"),
        ):
            lsl.start()
        return errors

    def test_markers_go_to_the_bridge(self):
        lsl = _make_lsl()
        outlet = FakeWebOutlet()
        errors = self.start(lsl, outlet, pauseatstart=True)
        errors.add_error.assert_not_called()
        assert lsl.stream_outlet is outlet
        assert len(lsl.slides) == 1  # "Please enable the OpenMATB stream into your LabRecorder."
        lsl.push("sysmon;failure")
        assert outlet.samples == [["sysmon;failure"]]

    def test_without_the_bridge(self):
        lsl = _make_lsl()
        errors = self.start(lsl, None)
        errors.add_error.assert_called_once()
        assert "web_lsl_bridge" in errors.add_error.call_args[0][0]
        assert lsl.stream_outlet is None

    def test_clock_offset_is_logged_when_it_changes(self):
        lsl = _make_lsl()
        lsl.stream_outlet = FakeWebOutlet()
        with patch.object(lsl_module, "IS_WEB", True):
            lsl.log_clock_offset()  # Not measured yet
            lsl.stream_outlet.offset = -1000.0
            lsl.log_clock_offset()
            lsl.stream_outlet.offset = -1000.00002  # Same, within 0.1 ms
            lsl.log_clock_offset()
            lsl.stream_outlet.offset = -1000.0003
            lsl.log_clock_offset()
        assert lsl.logger.log_manual_entry.call_args_list == [
            (("-1000.000000",), {"key": "lsl_offset"}),
            (("-1000.000300",), {"key": "lsl_offset"}),
        ]
