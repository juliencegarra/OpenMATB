"""Tests for plugins.communications - SDT and radio logic."""

from unittest.mock import patch, MagicMock
import pytest

from plugins.communications import Communications


def _make_comms_with_radios():
    """Create a minimal Communications object for testing radio helper methods."""
    c = object.__new__(Communications)
    c.alias = 'communications'
    c.parameters = {
        'radios': {
            0: {'name': 'NAV_1', 'currentfreq': 110.0, 'targetfreq': None,
                'pos': 0, 'response_time': 0, 'is_active': True,
                'is_prompting': False, '_feedbacktimer': None, '_feedbacktype': None},
            1: {'name': 'NAV_2', 'currentfreq': 120.0, 'targetfreq': None,
                'pos': 1, 'response_time': 0, 'is_active': False,
                'is_prompting': False, '_feedbacktimer': None, '_feedbacktype': None},
            2: {'name': 'COM_1', 'currentfreq': 125.0, 'targetfreq': 130.0,
                'pos': 2, 'response_time': 500, 'is_active': False,
                'is_prompting': False, '_feedbacktimer': None, '_feedbacktype': None},
            3: {'name': 'COM_2', 'currentfreq': 130.0, 'targetfreq': None,
                'pos': 3, 'response_time': 0, 'is_active': False,
                'is_prompting': False, '_feedbacktimer': None, '_feedbacktype': None},
        },
    }
    return c


class TestGetSDTValue:
    """Test Signal Detection Theory classification - entirely pure function."""

    def _get_sdt(self):
        c = object.__new__(Communications)
        return c.get_sdt_value

    def test_hit(self):
        """Response to signal on correct radio → HIT."""
        sdt = self._get_sdt()
        assert sdt(response_needed=True, was_a_radio_responded=True,
                    correct_radio=True, response_deviation=0) == 'HIT'

    def test_miss(self):
        """No response to signal → MISS."""
        sdt = self._get_sdt()
        assert sdt(response_needed=True, was_a_radio_responded=False,
                    correct_radio=False, response_deviation=0) == 'MISS'

    def test_false_alarm(self):
        """Response when no signal → FA."""
        sdt = self._get_sdt()
        assert sdt(response_needed=False, was_a_radio_responded=True,
                    correct_radio=True, response_deviation=0) == 'FA'

    def test_bad_radio(self):
        """Response on wrong radio → BAD_RADIO."""
        sdt = self._get_sdt()
        assert sdt(response_needed=True, was_a_radio_responded=True,
                    correct_radio=False, response_deviation=0) == 'BAD_RADIO'

    def test_bad_freq(self):
        """Correct radio but wrong frequency → BAD_FREQ."""
        sdt = self._get_sdt()
        assert sdt(response_needed=True, was_a_radio_responded=True,
                    correct_radio=True, response_deviation=0.5) == 'BAD_FREQ'

    def test_bad_radio_freq(self):
        """Wrong radio and wrong frequency → BAD_RADIO_FREQ."""
        sdt = self._get_sdt()
        assert sdt(response_needed=True, was_a_radio_responded=True,
                    correct_radio=False, response_deviation=0.5) == 'BAD_RADIO_FREQ'


class TestRadioHelpers:
    def test_get_target_radios(self):
        """Returns only radios with a target frequency."""
        c = _make_comms_with_radios()
        targets = c.get_target_radios_list()
        assert len(targets) == 1
        assert targets[0]['name'] == 'COM_1'

    def test_get_non_target_radios(self):
        """Returns radios without a target frequency."""
        c = _make_comms_with_radios()
        non_targets = c.get_non_target_radios_list()
        assert len(non_targets) == 3

    def test_get_active_radio(self):
        """Returns the currently active radio."""
        c = _make_comms_with_radios()
        active = c.get_active_radio_dict()
        assert active['name'] == 'NAV_1'

    def test_get_max_min_pos(self):
        """Max and min positions span the radio list."""
        c = _make_comms_with_radios()
        assert c.get_max_pos() == 3
        assert c.get_min_pos() == 0

    def test_get_response_timers(self):
        """Returns list of non-zero response timers."""
        c = _make_comms_with_radios()
        timers = c.get_response_timers()
        assert timers == [500]

    def test_get_radios_by_key_value(self):
        """Filters radios by key-value pair."""
        c = _make_comms_with_radios()
        result = c.get_radios_by_key_value('name', 'NAV_1')
        assert len(result) == 1
        assert result[0]['pos'] == 0

    def test_get_radio_dict_by_pos(self):
        """Finds a radio by its position index."""
        c = _make_comms_with_radios()
        result = c.get_radio_dict_by_pos(2)
        assert result['name'] == 'COM_1'

    def test_disable_radio_target(self):
        """Clears target frequency and resets timer."""
        c = _make_comms_with_radios()
        radio = c.parameters['radios'][2]
        assert radio['targetfreq'] == 130.0
        c.disable_radio_target(radio)
        assert radio['targetfreq'] is None
        assert radio['response_time'] == 0

    def test_get_waiting_response_radios(self):
        """Returns radios awaiting a response."""
        c = _make_comms_with_radios()
        # COM_1 has a target and is not prompting
        waiting = c.get_waiting_response_radios()
        assert len(waiting) == 1
        assert waiting[0]['name'] == 'COM_1'
