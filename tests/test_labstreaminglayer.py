"""Tests for plugins.labstreaminglayer when pylsl is not available (missing module, browser)."""

from unittest.mock import MagicMock, patch

import plugins.labstreaminglayer as lsl_module
from plugins.labstreaminglayer import Labstreaminglayer


def _make_lsl():
    lsl = object.__new__(Labstreaminglayer)
    lsl.parameters = {"marker": "", "streamsession": False, "pauseatstart": False}
    lsl.stream_info = None
    lsl.stream_outlet = None
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
