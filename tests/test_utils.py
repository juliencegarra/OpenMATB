"""Tests for core.utils - Pure utility functions."""

from unittest.mock import patch, MagicMock, PropertyMock
import configparser
import pytest

from core.utils import clamp, get_session_numbers, find_the_first_available_session_number


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
    @patch('core.utils.P')
    def test_returns_session_ids(self, mock_paths):
        """Parses session IDs from CSV filenames."""
        mock_file1 = MagicMock()
        mock_file1.name = '1_240101_120000.csv'
        mock_file2 = MagicMock()
        mock_file2.name = '3_240102_130000.csv'
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(return_value=[mock_file1, mock_file2]))
        result = get_session_numbers()
        assert result == [1, 3]

    @patch('core.utils.P')
    def test_empty_dir_returns_zero(self, mock_paths):
        """Empty sessions directory returns [0]."""
        mock_paths.__getitem__ = lambda self, k: MagicMock(glob=MagicMock(side_effect=ValueError))
        result = get_session_numbers()
        assert result == [0]


class TestFindFirstAvailableSessionNumber:
    @patch('core.utils.get_session_numbers')
    def test_first_session(self, mock_get):
        """Empty session list returns 1."""
        mock_get.return_value = []
        assert find_the_first_available_session_number() == 1

    @patch('core.utils.get_session_numbers')
    def test_consecutive_returns_next(self, mock_get):
        """Sessions [1, 2, 3] returns 4."""
        mock_get.return_value = [1, 2, 3]
        assert find_the_first_available_session_number() == 4

    @patch('core.utils.get_session_numbers')
    def test_gap_fills_first_hole(self, mock_get):
        """Sessions [1, 3, 4] returns 2 (fills the gap)."""
        mock_get.return_value = [1, 3, 4]
        assert find_the_first_available_session_number() == 2

    @patch('core.utils.get_session_numbers')
    def test_single_session(self, mock_get):
        """Single session [1] returns 2."""
        mock_get.return_value = [1]
        assert find_the_first_available_session_number() == 2

    @patch('core.utils.get_session_numbers')
    def test_gap_at_start(self, mock_get):
        """Sessions [2, 3] returns 1 (gap at start)."""
        mock_get.return_value = [2, 3]
        assert find_the_first_available_session_number() == 1


class TestGetConfValue:
    def test_boolean_true(self):
        """'true' string parses to True for boolean keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'fullscreen': 'true'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'fullscreen') is True

    def test_boolean_false(self):
        """'false' string parses to False for boolean keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'fullscreen': 'false'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'fullscreen') is False

    def test_boolean_invalid_raises(self):
        """Non-boolean string raises TypeError for boolean keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'fullscreen': 'maybe'}})
        with patch('core.utils.CONFIG', config):
            with pytest.raises(TypeError):
                get_conf_value('General', 'fullscreen')

    def test_integer_value(self):
        """Integer string parses to int for integer keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'screen_index': '2'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'screen_index') == 2

    def test_integer_invalid_raises(self):
        """Non-integer string raises TypeError for integer keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'screen_index': 'abc'}})
        with patch('core.utils.CONFIG', config):
            with pytest.raises(TypeError):
                get_conf_value('General', 'screen_index')

    def test_float_value(self):
        """Float string parses to float for float keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'clock_speed': '1.5'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'clock_speed') == 1.5

    def test_list_value(self):
        """List string is eval'd for list keys."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'top_bounds': '[0.35, 0.85]'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'top_bounds') == [0.35, 0.85]

    def test_string_value(self):
        """Unknown key returns raw string value."""
        from core.utils import get_conf_value
        config = configparser.ConfigParser()
        config.read_dict({'General': {'some_key': 'hello'}})
        with patch('core.utils.CONFIG', config):
            assert get_conf_value('General', 'some_key') == 'hello'
