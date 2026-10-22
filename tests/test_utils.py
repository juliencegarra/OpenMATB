"""Tests for core.utils - Pure utility functions."""

import configparser
from unittest.mock import MagicMock, patch

import pytest

from core.utils import (
    clamp,
    find_the_first_available_session_number,
    find_the_last_session_number,
    get_session_numbers,
)


class TestClamp:
    def test_within_range(self):
        """Value inside range is returned unchanged."""
        assert clamp(5, 0, 10) == 5

    def test_below_min(self):
        """Value below minimum is clamped to minimum."""
        assert clamp(-5, 0, 10) == 0

    def test_above_max(self):
        """Value above maximum is clamped to maximum."""
        assert clamp(15, 0, 10) == 10

    def test_at_min(self):
        """Value equal to minimum passes through."""
        assert clamp(0, 0, 10) == 0

    def test_at_max(self):
        """Value equal to maximum passes through."""
        assert clamp(10, 0, 10) == 10

    def test_float_values(self):
        """Clamping works with float arguments."""
        assert clamp(0.5, 0.0, 1.0) == 0.5
        assert clamp(-0.1, 0.0, 1.0) == 0.0
        assert clamp(1.5, 0.0, 1.0) == 1.0


class TestGetSessionNumbers:
    @patch("core.utils.P")
    def test_returns_session_ids(self, mock_paths):
        """Parses session IDs from CSV filenames."""
        mock_file1 = MagicMock()
        mock_file1.name = "1_240101_120000.csv"
        mock_file2 = MagicMock()
        mock_file2.name = "3_240102_130000.csv"
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(return_value=[mock_file1, mock_file2]))
        result = get_session_numbers()
        assert result == [1, 3]

    @patch("core.utils.P")
    def test_other_csv_files_are_ignored(self, mock_paths):
        """A CSV file that is not a session (e.g. an export) does not hide the session files."""
        files = []
        for name in ("1_240101_120000.csv", "summary.csv", "3_240102_130000.csv"):
            files.append(MagicMock())
            files[-1].name = name
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(return_value=files))
        assert get_session_numbers() == [1, 3]

    @patch("core.utils.P")
    def test_empty_dir_returns_zero(self, mock_paths):
        """Empty sessions directory returns [0]."""
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(side_effect=ValueError))
        result = get_session_numbers()
        assert result == [0]

    @patch("core.utils.P")
    def test_no_csv_files_returns_zero(self, mock_paths):
        """No CSV files in directory returns [0]."""
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(return_value=[]))
        result = get_session_numbers()
        assert result == [0]


class TestFindFirstAvailableSessionNumber:
    @patch("core.utils.get_session_numbers")
    def test_first_session(self, mock_get):
        """Empty session list returns 1."""
        mock_get.return_value = []
        assert find_the_first_available_session_number() == 1

    @patch("core.utils.get_session_numbers")
    def test_consecutive_returns_next(self, mock_get):
        """Sessions [1, 2, 3] returns 4."""
        mock_get.return_value = [1, 2, 3]
        assert find_the_first_available_session_number() == 4

    @patch("core.utils.get_session_numbers")
    def test_gap_fills_first_hole(self, mock_get):
        """Sessions [1, 3, 4] returns 2 (fills the gap)."""
        mock_get.return_value = [1, 3, 4]
        assert find_the_first_available_session_number() == 2

    @patch("core.utils.get_session_numbers")
    def test_single_session(self, mock_get):
        """Single session [1] returns 2."""
        mock_get.return_value = [1]
        assert find_the_first_available_session_number() == 2

    @patch("core.utils.get_session_numbers")
    def test_gap_at_start(self, mock_get):
        """Sessions [2, 3] returns 1 (gap at start)."""
        mock_get.return_value = [2, 3]
        assert find_the_first_available_session_number() == 1


class TestBrowserSessionNumbers:
    """Online, each participant has a fresh browser: every session was number 1, so every participant had the same
    pseudorandom draws (the seeds are made of the session number)."""

    @patch("core.utils.get_session_numbers", return_value=[])
    def test_a_random_6_digit_number(self, _numbers):
        with patch("core.utils.IS_WEB", True):
            numbers = {find_the_first_available_session_number() for _ in range(50)}
        assert all(100_000 <= n <= 999_999 for n in numbers)
        assert len(numbers) > 40

    def test_not_a_number_kept_in_the_browser(self):
        with (
            patch("core.utils.IS_WEB", True),
            patch("core.utils.get_session_numbers", return_value=[123_456]),
            patch("core.utils.random.SystemRandom") as generator,
        ):
            generator.return_value.choice.side_effect = [123_456, 654_321]
            assert find_the_first_available_session_number() == 654_321

    def test_the_draws_of_the_scenario_are_not_changed(self):
        """Drawn by an independent generator: the random module is seeded by the pseudorandom draws."""
        import random

        random.seed(1)
        expected = random.random()
        random.seed(1)
        with patch("core.utils.IS_WEB", True), patch("core.utils.get_session_numbers", return_value=[]):
            find_the_first_available_session_number()
        assert random.random() == expected

    def test_the_last_session_is_the_most_recent(self, tmp_path):
        for name in ["731004_261021_090000.csv", "120345_261022_101500.csv", "998877_261022_093000.csv"]:
            (tmp_path / name).write_text("")
        with patch("core.utils.IS_WEB", True), patch.dict("core.utils.P", {"SESSIONS": tmp_path}):
            assert find_the_last_session_number() == 120_345


class TestFindLastSessionNumber:
    @patch("core.utils.get_session_numbers")
    def test_returns_max(self, mock_get):
        """Returns the highest session number."""
        mock_get.return_value = [1, 3, 5]
        assert find_the_last_session_number() == 5

    @patch("core.utils.get_session_numbers")
    def test_single_session(self, mock_get):
        """Single session returns that number."""
        mock_get.return_value = [2]
        assert find_the_last_session_number() == 2

    @patch("core.utils.get_session_numbers")
    def test_empty_returns_zero(self, mock_get):
        """Empty session list returns 0."""
        mock_get.return_value = []
        assert find_the_last_session_number() == 0


class TestGetConfValue:
    def test_boolean_true(self):
        """'true' string parses to True for boolean keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"fullscreen": "true"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "fullscreen") is True

    def test_boolean_false(self):
        """'false' string parses to False for boolean keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"fullscreen": "false"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "fullscreen") is False

    def test_boolean_invalid_defaults_to_false(self, mock_errors):
        """A non-boolean string is a non-fatal error, and False is used (as the message says)."""
        from core.utils import _warned_conf_values, get_conf_value

        _warned_conf_values.clear()
        config = configparser.ConfigParser()
        config.read_dict({"General": {"fullscreen": "maybe", "highlight_aoi": "yes"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "fullscreen") is False
            assert get_conf_value("General", "highlight_aoi") is True
        mock_errors.add_error.assert_called_once()
        assert mock_errors.add_error.call_args.kwargs == {"fatal": False}

    def test_integer_value(self):
        """Integer string parses to int for integer keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"screen_index": "2"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "screen_index") == 2

    def test_integer_invalid_raises(self):
        """Non-integer string raises TypeError for integer keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"screen_index": "abc"}})
        with patch("core.utils.CONFIG", config), pytest.raises(TypeError):
            get_conf_value("General", "screen_index")

    def test_float_value(self):
        """Float string parses to float for float keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"clock_speed": "1.5"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "clock_speed") == 1.5

    def test_list_value(self):
        """List string is eval'd for list keys."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"top_bounds": "[0.35, 0.85]"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "top_bounds") == [0.35, 0.85]

    def test_string_value(self):
        """Unknown key returns raw string value."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"some_key": "hello"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("General", "some_key") == "hello"


class TestGetConfValueDefaults:
    """Tests for _CONFIG_DEFAULTS fallback in get_conf_value()."""

    def _empty_config(self):
        """Return a ConfigParser with no sections."""
        return configparser.ConfigParser()

    def test_missing_bool_returns_default(self):
        """Missing 'fullscreen' key returns True."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "fullscreen") is True

    def test_missing_bool_false_default(self):
        """Missing 'highlight_aoi' key returns False."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "highlight_aoi") is False

    def test_missing_int_returns_default(self):
        """Missing 'screen_index' key returns 0."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            result = get_conf_value("Openmatb", "screen_index")
            assert result == 0
            assert isinstance(result, int)

    def test_missing_float_returns_default(self):
        """Missing 'clock_speed' key returns 1.0."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            result = get_conf_value("Openmatb", "clock_speed")
            assert result == 1.0
            assert isinstance(result, float)

    def test_missing_list_returns_default(self):
        """Missing 'top_bounds' key returns [0.35, 0.85]."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "top_bounds") == [0.35, 0.85]

    def test_missing_string_returns_default(self):
        """Missing 'language' key returns 'en_EN'."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "language") == "en_EN"

    def test_missing_font_name_returns_empty(self):
        """Missing 'font_name' key returns empty string."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "font_name") == ""

    def test_missing_section_returns_default(self):
        """Missing entire section still returns default."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "fullscreen") is True

    def test_missing_scenario_path_opens_the_selector(self):
        """Missing scenario_path is empty, as in the default config.ini (the scenario selector opens)."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()):
            assert get_conf_value("Openmatb", "scenario_path") == ""

    def test_unknown_key_raises_keyerror(self):
        """Completely unknown key raises KeyError."""
        from core.utils import get_conf_value

        with patch("core.utils.CONFIG", self._empty_config()), pytest.raises(KeyError):
            get_conf_value("NoSection", "no_key")

    def test_present_key_overrides_default(self):
        """Config value wins over default when present."""
        from core.utils import get_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"Openmatb": {"fullscreen": "false"}})
        with patch("core.utils.CONFIG", config):
            assert get_conf_value("Openmatb", "fullscreen") is False

    def test_default_types_are_correct(self):
        """All defaults are already the correct Python types (not strings)."""
        from core.utils import _CONFIG_DEFAULTS

        assert isinstance(_CONFIG_DEFAULTS[("Openmatb", "fullscreen")], bool)
        assert isinstance(_CONFIG_DEFAULTS[("Openmatb", "screen_index")], int)
        assert isinstance(_CONFIG_DEFAULTS[("Openmatb", "clock_speed")], float)
        assert isinstance(_CONFIG_DEFAULTS[("Openmatb", "top_bounds")], list)
        assert isinstance(_CONFIG_DEFAULTS[("Openmatb", "language")], str)


class TestHasConfValue:
    def test_existing_option(self):
        """Return True when section and key both exist."""
        from core.utils import has_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"fullscreen": "true"}})
        with patch("core.utils.CONFIG", config):
            assert has_conf_value("General", "fullscreen") is True

    def test_missing_option(self):
        """Return False when section exists but key does not."""
        from core.utils import has_conf_value

        config = configparser.ConfigParser()
        config.read_dict({"General": {"fullscreen": "true"}})
        with patch("core.utils.CONFIG", config):
            assert has_conf_value("General", "no_such_key") is False

    def test_missing_section(self):
        """Return False when section does not exist."""
        from core.utils import has_conf_value

        config = configparser.ConfigParser()
        with patch("core.utils.CONFIG", config):
            assert has_conf_value("NoSection", "key") is False
