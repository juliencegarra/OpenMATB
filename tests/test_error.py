"""Tests for core.error - Error accumulation and severity tracking."""

from core.error import Errors


def _make_errors():
    """Create a fresh Errors instance bypassing module-level singleton."""
    e = object.__new__(Errors)
    e.errors_list = []
    e.some_fatals = False
    return e


class TestIsEmpty:
    def test_empty_on_init(self):
        """Fresh instance has no errors."""
        e = _make_errors()
        assert e.is_empty() is True

    def test_not_empty_after_add(self):
        """After adding an error, is_empty returns False."""
        e = _make_errors()
        e.add_error("something went wrong")
        assert e.is_empty() is False


class TestAddError:
    def test_appends_message(self):
        """Error message is appended to errors_list."""
        e = _make_errors()
        e.add_error("test error")
        assert len(e.errors_list) == 1
        assert "test error" in e.errors_list[0]

    def test_message_prefixed_with_dash(self):
        """Error message is prefixed with '– '."""
        e = _make_errors()
        e.add_error("msg")
        assert e.errors_list[0].startswith("– ")

    def test_multiple_errors(self):
        """Multiple add_error calls accumulate."""
        e = _make_errors()
        e.add_error("first")
        e.add_error("second")
        e.add_error("third")
        assert len(e.errors_list) == 3

    def test_non_fatal_keeps_flag_false(self):
        """Non-fatal error does not set some_fatals."""
        e = _make_errors()
        e.add_error("warning", fatal=False)
        assert e.some_fatals is False

    def test_fatal_sets_flag(self):
        """Fatal error sets some_fatals to True."""
        e = _make_errors()
        e.add_error("critical", fatal=True)
        assert e.some_fatals is True

    def test_fatal_stays_true(self):
        """Once some_fatals is True, it stays True even with non-fatal errors."""
        e = _make_errors()
        e.add_error("critical", fatal=True)
        e.add_error("minor", fatal=False)
        assert e.some_fatals is True

    def test_default_is_non_fatal(self):
        """Default fatal parameter is False."""
        e = _make_errors()
        e.add_error("msg")
        assert e.some_fatals is False
