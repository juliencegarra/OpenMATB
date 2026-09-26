"""Tests for core.utils (config.ini values, replay session ID) and core.validation (keys, callsigns, files)."""

import configparser
import sys
from unittest.mock import patch

import pytest

from core import validation
from core.constants import PATHS as P
from core.utils import get_conf_value, get_replay_session_id


def _config(**values):
    config = configparser.ConfigParser()
    config["Openmatb"] = {k: str(v) for k, v in values.items()}
    return config


class TestConfigValues:
    @pytest.mark.parametrize("value, expected", [("1.5", 1.5), ("2", 2.0)])
    def test_clock_speed_is_a_float(self, value, expected):
        with patch("core.utils.CONFIG", _config(clock_speed=value)):
            assert get_conf_value("Openmatb", "clock_speed") == expected

    def test_invalid_clock_speed(self):
        with patch("core.utils.CONFIG", _config(clock_speed="fast")), pytest.raises(TypeError, match="clock_speed"):
            get_conf_value("Openmatb", "clock_speed")

    def test_bounds_are_a_list(self):
        with patch("core.utils.CONFIG", _config(top_bounds="[0.2, 0.9]")):
            assert get_conf_value("Openmatb", "top_bounds") == [0.2, 0.9]

    @pytest.mark.parametrize("value", ["[0.2, 0.9", "high"])
    def test_invalid_bounds(self, value):
        with patch("core.utils.CONFIG", _config(bottom_bounds=value)), pytest.raises(TypeError, match="bottom_bounds"):
            get_conf_value("Openmatb", "bottom_bounds")

    def test_empty_font_name_means_default_font(self):
        with patch("core.utils.CONFIG", _config(font_name="")):
            assert get_conf_value("Openmatb", "font_name") is None

    def test_available_font(self):
        with patch("core.utils.CONFIG", _config(font_name="Arial")), patch("core.utils.font") as mock_font:
            mock_font.have_font.return_value = True
            assert get_conf_value("Openmatb", "font_name") == "Arial"
        mock_font.have_font.assert_called_once_with("Arial")

    def test_unavailable_font(self):
        with patch("core.utils.CONFIG", _config(font_name="NoSuchFont")), patch("core.utils.font") as mock_font:
            mock_font.have_font.return_value = False
            with pytest.raises(TypeError, match="font"):
                get_conf_value("Openmatb", "font_name")

    def test_other_values_are_strings(self):
        with patch("core.utils.CONFIG", _config(language="fr_FR")):
            assert get_conf_value("Openmatb", "language") == "fr_FR"


class TestReplaySessionId:
    def test_command_line_first(self):
        with patch.object(sys, "argv", ["main.py", "replay", "12"]):
            assert get_replay_session_id() == 12

    def test_then_config(self):
        config = configparser.ConfigParser()
        config["Replay"] = {"replay_session_id": "7"}
        with patch.object(sys, "argv", ["main.py"]), patch("core.utils.CONFIG", config):
            assert get_replay_session_id() == 7

    def test_else_the_last_session(self):
        with (
            patch.object(sys, "argv", ["main.py"]),
            patch("core.utils.CONFIG", configparser.ConfigParser()),
            patch("core.utils.find_the_last_session_number", return_value=42),
        ):
            assert get_replay_session_id() == 42


class TestJoystickKeys:
    def test_no_joystick_plugged(self):
        with patch.object(validation, "joykey", None):
            assert validation.is_joystick_key("JOY_1") == (None, None)

    def test_joystick_key(self):
        with patch.object(validation, "joykey", ["JOY_1", "JOY_2"]):
            assert validation.is_joystick_key("JOY_2") == ("JOY_2", None)
            value, msg = validation.is_joystick_key("JOY_9")
        assert value is None and "JOY_9" in msg

    def test_is_key_accepts_a_joystick_key(self):
        with patch.object(validation, "joykey", ["JOY_1"]):
            assert validation.is_key("JOY_1") == ("JOY_1", None)

    def test_is_key_rejects_an_unknown_key(self):
        with patch.object(validation, "joykey", ["JOY_1"]):
            value, msg = validation.is_key("NOT_A_KEY")
        assert value is None and "NOT_A_KEY" in msg


class TestCallsign:
    def test_valid(self):
        assert validation.is_callsign("AF123") == ("AF123", None)

    def test_one_forbidden_character(self):
        value, msg = validation.is_callsign("AF-12")
        assert value is None
        assert "- in AF-12" in msg

    def test_several_forbidden_characters(self):
        value, msg = validation.is_callsign("AF-1_2")
        assert value is None
        assert "AF-1_2" in msg

    def test_list_of_callsigns(self):
        assert validation.is_callsign_or_list_of("AF123,BZ456") == (["AF123", "BZ456"], None)
        value, msg = validation.is_callsign_or_list_of("AF123,B-Z")
        assert value is None and "B-Z" in msg


class TestAvailableTextFile:
    def test_found_in_questionnaires_or_instructions(self, tmp_path):
        questionnaires, instructions = tmp_path / "q", tmp_path / "i"
        questionnaires.mkdir()
        instructions.mkdir()
        (questionnaires / "nasatlx.txt").touch()
        (instructions / "welcome.txt").touch()
        with patch.dict(P, {"QUESTIONNAIRES": questionnaires, "INSTRUCTIONS": instructions}):
            assert validation.is_available_text_file("nasatlx.txt") == ("nasatlx.txt", None)
            assert validation.is_available_text_file("welcome.txt") == ("welcome.txt", None)
            value, msg = validation.is_available_text_file("missing.txt")
        assert value is None and "missing.txt" in msg
