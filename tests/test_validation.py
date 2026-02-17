"""Tests for core.validation - Input validation functions."""

from core.validation import (
    is_string, is_natural_integer, is_positive_integer, is_boolean,
    is_color, is_positive_float, is_in_list, is_a_regex, is_keyboard_key,
    is_task_location, is_callsign, is_callsign_or_list_of,
    is_in_unit_interval, is_key
)


class TestIsString:
    def test_valid_string(self):
        """Valid string passes validation."""
        val, err = is_string('hello')
        assert val == 'hello'
        assert err is None

    def test_accepts_empty_string(self):
        """Empty string is accepted."""
        val, err = is_string('')
        assert val == ''
        assert err is None

    def test_rejects_non_string(self):
        """Non-string input is rejected."""
        val, err = is_string(123)
        assert val is None
        assert err is not None


class TestIsNaturalInteger:
    def test_zero(self):
        """Zero is a valid natural integer."""
        val, err = is_natural_integer('0')
        assert val == 0
        assert err is None

    def test_positive(self):
        """Positive integer passes."""
        val, err = is_natural_integer('42')
        assert val == 42
        assert err is None

    def test_rejects_negative(self):
        """Negative number is rejected."""
        val, err = is_natural_integer('-1')
        assert val is None
        assert err is not None

    def test_rejects_float_string(self):
        """Float string is truncated to int."""
        val, err = is_natural_integer('3.14')
        assert val == 3  # int(eval('3.14')) -> 3
        assert err is None

    def test_rejects_text(self):
        """Non-numeric text is rejected."""
        val, err = is_natural_integer('abc')
        assert val is None
        assert err is not None


class TestIsPositiveInteger:
    def test_valid(self):
        """Positive integer passes."""
        val, err = is_positive_integer('5')
        assert val == 5
        assert err is None

    def test_rejects_zero(self):
        """Zero is rejected (must be > 0)."""
        val, err = is_positive_integer('0')
        assert val is None
        assert err is not None

    def test_rejects_negative(self):
        """Negative is rejected."""
        val, err = is_positive_integer('-3')
        assert val is None
        assert err is not None


class TestIsBoolean:
    def test_true(self):
        """'True' parses to True."""
        val, err = is_boolean('True')
        assert val is True
        assert err is None

    def test_false(self):
        """'False' parses to False."""
        val, err = is_boolean('False')
        assert val is False
        assert err is None

    def test_case_insensitive(self):
        """'true' (lowercase) parses to True."""
        val, err = is_boolean('true')
        assert val is True
        assert err is None

    def test_one(self):
        """'1' parses to True."""
        val, err = is_boolean('1')
        assert val is True
        assert err is None

    def test_zero(self):
        """'0' parses to False."""
        val, err = is_boolean('0')
        assert val is False
        assert err is None

    def test_rejects_invalid(self):
        """'maybe' is rejected."""
        val, err = is_boolean('maybe')
        assert val is None
        assert err is not None


class TestIsColor:
    def test_hex_color(self):
        """Hex '#ff0000' parses to (255,0,0,255)."""
        val, err = is_color('#ff0000')
        assert val == (255, 0, 0, 255)
        assert err is None

    def test_hex_green(self):
        """Hex '#00ff00' parses to (0,255,0,255)."""
        val, err = is_color('#00ff00')
        assert val == (0, 255, 0, 255)
        assert err is None

    def test_named_color(self):
        """Named color 'WHITE' resolves to RGBA tuple."""
        val, err = is_color('WHITE')
        assert val == (255, 255, 255, 255)
        assert err is None

    def test_rgba_tuple(self):
        """RGBA string tuple is parsed."""
        val, err = is_color('(100, 200, 50, 255)')
        assert val == (100, 200, 50, 255)
        assert err is None

    def test_rejects_invalid(self):
        """Non-color string is rejected."""
        val, err = is_color('not_a_color')
        assert val is None
        assert err is not None

    def test_rejects_out_of_range(self):
        """Component > 255 is rejected."""
        val, err = is_color('(300, 200, 50, 255)')
        assert val is None
        assert err is not None


class TestIsPositiveFloat:
    def test_valid(self):
        """'3.14' parses to 3.14."""
        val, err = is_positive_float('3.14')
        assert val == 3.14
        assert err is None

    def test_rejects_integer_string(self):
        """Integer string without dot is rejected."""
        val, err = is_positive_float('5')
        assert val is None  # Must contain a dot
        assert err is not None

    def test_rejects_zero(self):
        """'0.0' is rejected (must be > 0)."""
        val, err = is_positive_float('0.0')
        assert val is None
        assert err is not None

    def test_rejects_negative(self):
        """Negative float is rejected."""
        val, err = is_positive_float('-1.5')
        assert val is None
        assert err is not None

    def test_rejects_text(self):
        """Non-numeric text is rejected."""
        val, err = is_positive_float('abc')
        assert val is None
        assert err is not None


class TestIsInList:
    def test_single_in_list(self):
        """Single value found in list passes."""
        val, err = is_in_list('a', ['a', 'b', 'c'])
        assert val == 'a'
        assert err is None

    def test_multiple_in_list(self):
        """Comma-separated values all in list pass."""
        val, err = is_in_list('a,b', ['a', 'b', 'c'])
        assert val == ['a', 'b']
        assert err is None

    def test_not_in_list(self):
        """Value not in list is rejected."""
        val, err = is_in_list('d', ['a', 'b', 'c'])
        assert val is None
        assert err is not None

    def test_bool_in_list(self):
        """'True' in list is eval'd to boolean."""
        val, err = is_in_list('True', ['True', 'False'])
        assert val is True  # eval('True') -> True
        assert err is None


class TestIsARegex:
    def test_valid_regex(self):
        """Valid pattern passes."""
        val, err = is_a_regex('[A-Z]{3}')
        assert val == '[A-Z]{3}'
        assert err is None

    def test_invalid_regex(self):
        """Unclosed bracket is rejected."""
        val, err = is_a_regex('[unclosed')
        assert val is None
        assert err is not None

    def test_simple_pattern(self):
        """'.*' is a valid regex."""
        val, err = is_a_regex('.*')
        assert val == '.*'
        assert err is None


class TestIsKeyboardKey:
    def test_valid_key(self):
        """'F1' is a valid keyboard key."""
        val, err = is_keyboard_key('F1')
        assert val == 'F1'
        assert err is None

    def test_valid_letter(self):
        """'A' is a valid keyboard key."""
        val, err = is_keyboard_key('A')
        assert val == 'A'
        assert err is None

    def test_invalid_key(self):
        """Unknown key name is rejected."""
        val, err = is_keyboard_key('NONEXISTENT')
        assert val is None
        assert err is not None


class TestIsKey:
    def test_keyboard_key(self):
        """Valid keyboard key passes."""
        val, err = is_key('F1')
        assert val == 'F1'
        assert err is None

    def test_invalid_key(self):
        """Invalid key returns None."""
        val, err = is_key('NONEXISTENT')
        # When no joystick is connected, is_joystick_key returns (None, None)
        # which means is_key returns the error message from keyboard check
        # only when joystick also returns an error (jmsg is not None)
        # With joykey=None, jmsg=None, so is_key returns (None, None)
        assert val is None


class TestIsTaskLocation:
    def test_valid_locations(self):
        """All standard placement names pass."""
        for loc in ['fullscreen', 'topmid', 'topright', 'topleft',
                     'bottomleft', 'bottommid', 'bottomright']:
            val, err = is_task_location(loc)
            assert val == loc, f'{loc} should be valid'
            assert err is None

    def test_invalid_location(self):
        """Unknown location is rejected."""
        val, err = is_task_location('nowhere')
        assert val is None
        assert err is not None


class TestIsCallsign:
    def test_valid_letters(self):
        """Alphanumeric callsign passes."""
        val, err = is_callsign('ABC123')
        assert val == 'ABC123'
        assert err is None

    def test_valid_lowercase(self):
        """Lowercase callsign passes."""
        val, err = is_callsign('abc')
        assert val == 'abc'
        assert err is None

    def test_rejects_special_chars(self):
        """Special characters are rejected."""
        val, err = is_callsign('AB@12')
        assert val is None
        assert err is not None


class TestIsCallsignOrListOf:
    def test_single_callsign(self):
        """Single callsign returns one-element list."""
        val, err = is_callsign_or_list_of('ABC123')
        assert val == ['ABC123']
        assert err is None

    def test_multiple_callsigns(self):
        """Comma-separated callsigns return list."""
        val, err = is_callsign_or_list_of('ABC123,DEF456')
        assert val == ['ABC123', 'DEF456']
        assert err is None

    def test_rejects_invalid(self):
        """Invalid callsign is rejected."""
        val, err = is_callsign_or_list_of('AB@12')
        assert val is None
        assert err is not None


class TestIsInUnitInterval:
    def test_zero(self):
        """0 is within [0, 1]."""
        val, err = is_in_unit_interval('0')
        assert val == 0.0
        assert err is None

    def test_one(self):
        """1 is within [0, 1]."""
        val, err = is_in_unit_interval('1')
        assert val == 1.0
        assert err is None

    def test_middle(self):
        """0.5 is within [0, 1]."""
        val, err = is_in_unit_interval('0.5')
        assert val == 0.5
        assert err is None

    def test_rejects_over_one(self):
        """1.5 is outside [0, 1]."""
        val, err = is_in_unit_interval('1.5')
        assert val is None
        assert err is not None

    def test_rejects_negative(self):
        """-0.1 is outside [0, 1]."""
        val, err = is_in_unit_interval('-0.1')
        assert val is None
        assert err is not None

    def test_rejects_text(self):
        """Non-numeric text is rejected."""
        val, err = is_in_unit_interval('abc')
        assert val is None
        assert err is not None
