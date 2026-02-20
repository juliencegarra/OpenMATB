"""Tests for plugins.communications - SDT and radio logic."""

from pathlib import Path
from string import ascii_lowercase, digits
from unittest.mock import patch

from plugins.communications import Communications


def _make_comms_with_radios():
    """Create a minimal Communications object for testing radio helper methods."""
    c = object.__new__(Communications)
    c.alias = "communications"
    c.parameters = {
        "radios": {
            0: {
                "name": "NAV_1",
                "currentfreq": 110.0,
                "targetfreq": None,
                "pos": 0,
                "response_time": 0,
                "is_active": True,
                "is_prompting": False,
                "_feedbacktimer": None,
                "_feedbacktype": None,
            },
            1: {
                "name": "NAV_2",
                "currentfreq": 120.0,
                "targetfreq": None,
                "pos": 1,
                "response_time": 0,
                "is_active": False,
                "is_prompting": False,
                "_feedbacktimer": None,
                "_feedbacktype": None,
            },
            2: {
                "name": "COM_1",
                "currentfreq": 125.0,
                "targetfreq": 130.0,
                "pos": 2,
                "response_time": 500,
                "is_active": False,
                "is_prompting": False,
                "_feedbacktimer": None,
                "_feedbacktype": None,
            },
            3: {
                "name": "COM_2",
                "currentfreq": 130.0,
                "targetfreq": None,
                "pos": 3,
                "response_time": 0,
                "is_active": False,
                "is_prompting": False,
                "_feedbacktimer": None,
                "_feedbacktype": None,
            },
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
        assert sdt(response_needed=True, was_a_radio_responded=True, correct_radio=True, response_deviation=0) == "HIT"

    def test_miss(self):
        """No response to signal → MISS."""
        sdt = self._get_sdt()
        assert (
            sdt(response_needed=True, was_a_radio_responded=False, correct_radio=False, response_deviation=0) == "MISS"
        )

    def test_false_alarm(self):
        """Response when no signal → FA."""
        sdt = self._get_sdt()
        assert sdt(response_needed=False, was_a_radio_responded=True, correct_radio=True, response_deviation=0) == "FA"

    def test_bad_radio(self):
        """Response on wrong radio → BAD_RADIO."""
        sdt = self._get_sdt()
        assert (
            sdt(response_needed=True, was_a_radio_responded=True, correct_radio=False, response_deviation=0)
            == "BAD_RADIO"
        )

    def test_bad_freq(self):
        """Correct radio but wrong frequency → BAD_FREQ."""
        sdt = self._get_sdt()
        assert (
            sdt(response_needed=True, was_a_radio_responded=True, correct_radio=True, response_deviation=0.5)
            == "BAD_FREQ"
        )

    def test_bad_radio_freq(self):
        """Wrong radio and wrong frequency → BAD_RADIO_FREQ."""
        sdt = self._get_sdt()
        assert (
            sdt(response_needed=True, was_a_radio_responded=True, correct_radio=False, response_deviation=0.5)
            == "BAD_RADIO_FREQ"
        )


class TestRadioHelpers:
    def test_get_target_radios(self):
        """Returns only radios with a target frequency."""
        c = _make_comms_with_radios()
        targets = c.get_target_radios_list()
        assert len(targets) == 1
        assert targets[0]["name"] == "COM_1"

    def test_get_non_target_radios(self):
        """Returns radios without a target frequency."""
        c = _make_comms_with_radios()
        non_targets = c.get_non_target_radios_list()
        assert len(non_targets) == 3

    def test_get_active_radio(self):
        """Returns the currently active radio."""
        c = _make_comms_with_radios()
        active = c.get_active_radio_dict()
        assert active["name"] == "NAV_1"

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
        result = c.get_radios_by_key_value("name", "NAV_1")
        assert len(result) == 1
        assert result[0]["pos"] == 0

    def test_get_radio_dict_by_pos(self):
        """Finds a radio by its position index."""
        c = _make_comms_with_radios()
        result = c.get_radio_dict_by_pos(2)
        assert result["name"] == "COM_1"

    def test_disable_radio_target(self):
        """Clears target frequency and resets timer."""
        c = _make_comms_with_radios()
        radio = c.parameters["radios"][2]
        assert radio["targetfreq"] == 130.0
        c.disable_radio_target(radio)
        assert radio["targetfreq"] is None
        assert radio["response_time"] == 0

    def test_get_waiting_response_radios(self):
        """Returns radios awaiting a response."""
        c = _make_comms_with_radios()
        # COM_1 has a target and is not prompting
        waiting = c.get_waiting_response_radios()
        assert len(waiting) == 1
        assert waiting[0]["name"] == "COM_1"


def _make_comms_for_voice():
    """Create a minimal Communications object for testing voice/sound methods."""
    c = object.__new__(Communications)
    c.alias = "communications"
    c.parameters = {
        "voiceidiom": "french",
        "voicegender": "female",
        "promptlist": ["NAV_1", "NAV_2", "COM_1", "COM_2"],
    }
    c.sound_path = None
    return c


class TestVoiceSwitching:
    """Test voice language/gender switching logic."""

    def test_get_sounds_path_uses_current_parameters(self):
        """get_sounds_path() reflects current voicegender/voiceidiom values."""
        from core.constants import PATHS as P

        c = _make_comms_for_voice()
        result = c.get_sounds_path()
        assert result == P["SOUNDS"] / "french" / "female"

        c.parameters["voiceidiom"] = "english"
        c.parameters["voicegender"] = "male"
        result = c.get_sounds_path()
        assert result == P["SOUNDS"] / "english" / "male"

    def test_set_sample_sounds_updates_path_on_change(self, tmp_path):
        """set_sample_sounds() updates sound_path when parameters change."""
        c = _make_comms_for_voice()
        # Create a fake sounds directory with the expected wav files
        voice_dir = tmp_path / "french" / "female"
        voice_dir.mkdir(parents=True)
        expected_names = (
            [s for s in digits + ascii_lowercase]
            + [r.lower() for r in c.parameters["promptlist"]]
            + ["radio", "point", "frequency"]
        )
        for name in expected_names:
            (voice_dir / f"{name}.wav").touch()

        with patch.object(Communications, "get_sounds_path", return_value=voice_dir):
            c.set_sample_sounds()

        assert c.sound_path == voice_dir
        assert len(c.samples_path) == len(expected_names)

    def test_set_sample_sounds_skips_when_unchanged(self):
        """set_sample_sounds() is a no-op when path hasn't changed."""
        c = _make_comms_for_voice()
        fake_path = Path("/fake/french/female")
        c.sound_path = fake_path

        with patch.object(Communications, "get_sounds_path", return_value=fake_path):
            c.set_sample_sounds()

        # sound_path should remain the same, no samples_path attribute set
        assert c.sound_path == fake_path
        assert not hasattr(c, "samples_path")

    def test_set_sample_sounds_skips_invalid_path(self, tmp_path, capsys):
        """set_sample_sounds() warns and bails for non-existent idiom/gender combo."""
        c = _make_comms_for_voice()
        nonexistent = tmp_path / "english" / "female"  # Does not exist

        with patch.object(Communications, "get_sounds_path", return_value=nonexistent):
            c.set_sample_sounds()

        # sound_path should NOT be updated
        assert c.sound_path is None
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "does not exist" in captured.out
