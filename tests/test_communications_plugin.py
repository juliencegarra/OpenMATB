"""Tests for plugins.communications - the plugin built by its constructor (prompts, responses, inputs)."""

import math
from itertools import count
from string import ascii_uppercase, digits
from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import mouse

from core.constants import COLORS as C
from core.container import Container
from plugins.abstractplugin import AbstractPlugin
from plugins.communications import CALLSIGN_MAX_ATTEMPTS, Communications


def _distinct_callsigns():
    """xeger stand-in: a new callsign without duplicate characters at each call (ABC012, BCD123...)."""
    for n in count():
        letters = "".join(ascii_uppercase[(n + i) % 26] for i in range(3))
        yield letters + "".join(str((n + i) % 10) for i in range(3))


@pytest.fixture
def comms(mock_logger):
    """A running Communications plugin, with mock radio widgets and a mock logger."""
    with patch("plugins.communications.xeger", side_effect=_distinct_callsigns()):
        c = Communications()
    c.paused = False
    c.visible = True
    c.can_execute_keys = True
    c.scenario_time = 1
    c.joystick = None
    for radio in c.parameters["radios"].values():
        radio["widget"] = MagicMock(is_selected=False)
    c.parameters["radios"][0]["is_active"] = True
    return c


@pytest.fixture
def no_modal_dialog():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        yield mock_win


def _radio(c, name):
    return c.get_radios_by_key_value("name", name)[0]


def _performance(c):
    """Last value logged for each performance measure."""
    return {name: values[-1] for name, values in c.performance.items()}


class TestInit:
    def test_default_parameters(self, comms):
        p = comms.parameters
        assert p["callsignregex"] == r"[A-Z][A-Z][A-Z]\d\d\d"
        assert p["keys"]["validateresponse"] == "ENTER"
        assert comms.keys == {"UP", "DOWN", "RIGHT", "LEFT", "ENTER"}
        assert comms.sound_path is not None and comms.sound_path.exists()

    def test_callsigns_are_all_different(self, comms):
        callsigns = [comms.parameters["owncallsign"]] + comms.parameters["othercallsign"]
        assert len(callsigns) == 6
        assert len(set(callsigns)) == 6

    def test_one_radio_per_prompt(self, comms):
        radios = comms.parameters["radios"]
        assert [r["name"] for r in radios.values()] == ["NAV_1", "NAV_2", "COM_1", "COM_2"]
        for radio in radios.values():
            assert 108.0 <= radio["currentfreq"] <= 137.0
            assert radio["targetfreq"] is None

    def test_regenerate_skips_already_used_callsigns(self, comms):
        comms.parameters["othercallsign"] = []
        comms.parameters["othercallsignnumber"] = 2
        with patch.object(Communications, "get_callsign", side_effect=["ABC123", "ABC123", "DEF456", "GHI789"]):
            comms.regenerate_callsigns()
        # The second ABC123 is already the own callsign
        assert comms.parameters["owncallsign"] == "ABC123"
        assert comms.parameters["othercallsign"] == ["DEF456", "GHI789"]


class TestGetCallsign:
    @pytest.fixture(autouse=True)
    def all_characters_available(self, comms):
        comms.letters, comms.digits = ascii_uppercase, digits

    def _get_callsign(self, comms, generated):
        with patch("plugins.communications.xeger", side_effect=generated) as mock_xeger:
            return comms.get_callsign(), mock_xeger.call_count

    def test_next_callsigns_do_not_reuse_characters(self, comms):
        assert self._get_callsign(comms, ["ABC123"])[0] == "ABC123"
        assert comms.letters == ascii_uppercase[3:]
        assert comms.digits == "0456789"
        # ABD456 reuses A and B, EFG723 reuses 2 and 3
        assert self._get_callsign(comms, ["ABD456", "EFG723", "EFG789"]) == ("EFG789", 3)
        assert comms.digits == "0456"

    def test_duplicate_characters_are_rejected(self, comms):
        assert self._get_callsign(comms, ["AAB123", "ABC113", "ABC123"]) == ("ABC123", 3)

    def test_characters_are_used_again_when_fewer_than_three_are_left(self, comms):
        comms.letters, comms.digits = "XY", "0123"
        assert self._get_callsign(comms, ["ABC123"])[0] == "ABC123"
        assert comms.letters == ascii_uppercase[3:]
        assert comms.digits == "0"

    def test_fixed_prefix_does_not_loop_forever(self, comms):
        """Once A and F are used, no callsign with the AF prefix fits the characters left: they are all used again."""
        comms.parameters["callsignregex"] = r"AF\d\d\d"
        assert self._get_callsign(comms, ["AF123"])[0] == "AF123"
        callsign, calls = self._get_callsign(comms, lambda *args: "AF456")
        assert callsign == "AF456"
        assert calls == CALLSIGN_MAX_ATTEMPTS + 1

    def test_impossible_regex_does_not_loop_forever(self, comms):
        """Lowercase characters never fit: the last callsign is accepted."""
        callsign, calls = self._get_callsign(comms, lambda *args: "abc")
        assert callsign == "abc"
        assert calls == 2 * CALLSIGN_MAX_ATTEMPTS


class TestHasActiveFault:
    def test_waiting_response_is_a_fault(self, comms):
        assert comms.has_active_fault() is False
        _radio(comms, "NAV_2").update(targetfreq=115.0, is_prompting=True)
        assert comms.has_active_fault() is False  # Not yet announced
        _radio(comms, "NAV_2")["is_prompting"] = False
        assert comms.has_active_fault() is True


class TestMissingSample:
    def test_logs_missing_wav_files(self, comms, tmp_path):
        (tmp_path / "a.wav").touch()
        with patch.object(Communications, "get_sounds_path", return_value=tmp_path):
            comms.set_sample_sounds()
        missing = [c.args[0] for c in comms.logger.log_manual_entry.call_args_list]
        assert any(m.startswith(str(tmp_path / "0.wav")) for m in missing)
        assert not any(m.startswith(str(tmp_path / "a.wav")) for m in missing)


class TestCreateWidgets:
    def test_one_radio_widget_per_radio(self, comms):
        def base_create_widgets(plugin):
            plugin.task_container = Container("task", 0, 0, 400, 300)

        with (
            patch.object(AbstractPlugin, "create_widgets", base_create_widgets),
            patch("plugins.communications.Radio") as mock_radio,
            patch("plugins.communications.Simpletext"),
            patch("plugins.communications.randint", return_value=2),
        ):
            comms.create_widgets()

        assert mock_radio.call_count == 4
        assert [r["is_active"] for r in comms.parameters["radios"].values()] == [False, False, True, False]
        assert comms.get_active_radio_dict()["name"] == "COM_1"
        first, second = (mock_radio.call_args_list[i].args[1] for i in (0, 1))
        assert first.b > second.b  # Radios are stacked from top to bottom
        assert "communications_callsign" in comms.widgets


class TestPauseResume:
    def test_pauses_and_resumes_the_prompt(self, comms):
        comms.player = MagicMock()
        comms.pause()
        comms.player.pause.assert_called_once()
        comms.resume()
        comms.player.play.assert_called_once()

    def test_resume_without_sound_does_not_play(self, comms):
        comms.player = MagicMock(source=None)
        comms.resume()
        comms.player.play.assert_not_called()

    def test_no_player_yet(self, comms):
        comms.pause()
        comms.resume()
        assert comms.paused is False


class TestGroupAudioFiles:
    def test_sound_sequence(self, comms):
        """Silence, callsign twice, radio name, frequency (with 'point'), silence."""
        with (
            patch("plugins.communications.load", side_effect=lambda path, streaming: path) as mock_load,
            patch("plugins.communications.SourceGroup") as mock_group,
        ):
            group = comms.group_audio_files("ABC123", "NAV_1", 112.5)

        names = [c.args[0].rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for c in mock_load.call_args_list]
        assert names == ["empty.wav"] * 20 + [f"{c}.wav" for c in "abc123abc123"] + [
            "radio.wav",
            "nav_1.wav",
            "frequency.wav",
            "1.wav",
            "1.wav",
            "2.wav",
            "point.wav",
            "5.wav",
            "empty.wav",
        ]
        assert group is mock_group.return_value
        assert group.add.call_count == len(names)

    def test_unreadable_files_are_logged_and_skipped(self, comms):
        with (
            patch("plugins.communications.load", side_effect=OSError),
            patch("plugins.communications.SourceGroup") as mock_group,
        ):
            group = comms.group_audio_files("ABC123", "NAV_1", 112.5)
        assert group is mock_group.return_value
        group.add.assert_not_called()
        assert "Audio file missing or unreadable" in comms.logger.log_manual_entry.call_args.args[0]

    def test_no_voice(self, comms):
        comms.sound_path = None
        with patch("plugins.communications.load") as mock_load, patch("plugins.communications.SourceGroup"):
            comms.group_audio_files("ABC123", "NAV_1", 112.5)
        mock_load.assert_not_called()


class TestPromptForANewTarget:
    @pytest.fixture(autouse=True)
    def audio(self):
        with (
            patch("plugins.communications.Player") as player,
            patch.object(Communications, "group_audio_files") as group,
        ):
            self.player, self.group = player, group
            yield

    def test_own_prompt_sets_a_target(self, comms):
        comms.parameters["radioprompt"] = "own"
        radio = _radio(comms, "NAV_2")
        comms.prompt_for_a_new_target("own", "NAV_2")

        assert comms.parameters["radioprompt"] == ""
        assert radio["is_prompting"] is True
        assert 5 < abs(radio["targetfreq"] - radio["currentfreq"]) < 6  # airbandmin/maxvariationMhz
        callsign, radio_name, freq = self.group.call_args.args
        assert (callsign, radio_name, freq) == (comms.parameters["owncallsign"], "NAV_2", radio["targetfreq"])
        self.player.return_value.queue.assert_called_once_with(self.group.return_value)
        self.player.return_value.play.assert_called_once()

    def test_other_prompt_has_no_target(self, comms):
        comms.prompt_for_a_new_target("other", "COM_1")
        radio = _radio(comms, "COM_1")
        assert radio["targetfreq"] is None
        assert radio["is_prompting"] is False
        assert self.group.call_args.args[0] in comms.parameters["othercallsign"]

    def test_playback_failure_is_logged(self, comms):
        self.player.side_effect = RuntimeError("no audio device")
        comms.prompt_for_a_new_target("own", "NAV_1")
        comms.logger.log_manual_entry.assert_called_with("Audio prompt playback failed")


class TestModulateFrequency:
    @pytest.mark.parametrize("key, delta", [("LEFT", -0.1), ("RIGHT", 0.1)])
    def test_held_key_tunes_the_active_radio(self, comms, no_modal_dialog, key, delta):
        no_modal_dialog.MainWindow.keyboard = {key: True}
        radio = comms.get_active_radio_dict()
        before = radio["currentfreq"]
        comms.modulate_frequency()
        assert radio["currentfreq"] == pytest.approx(before + delta)

    def test_no_key_held(self, comms, no_modal_dialog):
        radio = comms.get_active_radio_dict()
        before = radio["currentfreq"]
        comms.modulate_frequency()
        assert radio["currentfreq"] == before


class TestComputeNextPluginState:
    @pytest.fixture(autouse=True)
    def no_audio(self):
        with patch.object(Communications, "prompt_for_a_new_target") as prompt:
            self.prompt = prompt
            yield

    def test_skipped_when_paused(self, comms):
        comms.paused = True
        comms.parameters["radioprompt"] = "own"
        comms.compute_next_plugin_state()
        self.prompt.assert_not_called()

    def test_own_prompt_chooses_a_radio_without_target(self, comms):
        for name in ("NAV_1", "NAV_2", "COM_1"):
            _radio(comms, name)["targetfreq"] = 120.0
        comms.parameters["radioprompt"] = "OWN"
        comms.compute_next_plugin_state()
        self.prompt.assert_called_once_with("own", "COM_2")

    def test_own_prompt_without_free_radio_is_an_error(self, comms):
        for radio in comms.parameters["radios"].values():
            radio["targetfreq"] = 120.0
        comms.parameters["radioprompt"] = "own"
        comms.log_manual_entry = MagicMock()
        comms.compute_next_plugin_state()
        self.prompt.assert_not_called()
        comms.log_manual_entry.assert_called_once_with("Error. Could not trigger prompt", key="manual")

    def test_other_prompt(self, comms):
        comms.parameters["radioprompt"] = "other"
        comms.compute_next_plugin_state()
        radio_name = self.prompt.call_args.args[1]
        assert self.prompt.call_args.args[0] == "other"
        assert radio_name in comms.parameters["promptlist"]

    def test_new_prompt_interrupts_the_current_one(self, comms):
        radio = _radio(comms, "NAV_1")
        radio.update(targetfreq=115.0, is_prompting=True)
        player = comms.player = MagicMock()
        comms.parameters["radioprompt"] = "other"
        comms.compute_next_plugin_state()
        player.pause.assert_called_once()
        assert not hasattr(comms, "player")
        assert radio["is_prompting"] is False
        comms.logger.log_manual_entry.assert_any_call("Target NAV_1:115.0")

    def test_new_regex_regenerates_callsigns(self, comms):
        comms.parameters["callsignregex"] = r"[A-Z][A-Z]\d\d"
        comms.parameters["othercallsign"] = []
        comms.parameters["othercallsignnumber"] = 1
        comms.letters, comms.digits = ascii_uppercase, digits
        with patch("plugins.communications.xeger", side_effect=["AB12", "CD34"]):
            comms.compute_next_plugin_state()
        assert comms.parameters["owncallsign"] == "AB12"
        assert comms.parameters["othercallsign"] == ["CD34"]
        assert comms.old_regex == r"[A-Z][A-Z]\d\d"

    def test_keys_tune_only_when_allowed(self, comms):
        comms.modulate_frequency = MagicMock()
        comms.can_receive_keys = False
        comms.compute_next_plugin_state()
        comms.modulate_frequency.assert_not_called()
        comms.can_receive_keys = True
        comms.scenario_time = 2
        comms.compute_next_plugin_state()
        comms.modulate_frequency.assert_called_once()

    def test_end_of_prompt_starts_the_response_timer(self, comms):
        radio = _radio(comms, "NAV_2")
        radio.update(targetfreq=115.0, is_prompting=True)
        comms.player = MagicMock(source=None)  # The prompt has ended

        comms.compute_next_plugin_state()
        assert radio["is_prompting"] is False
        assert radio["_response_start"] is None
        comms.logger.log_manual_entry.assert_any_call("Target NAV_2:115.0")

        comms.scenario_time = 2
        comms.compute_next_plugin_state()
        assert radio["_response_start"] == 2

    def test_prompt_still_playing(self, comms):
        radio = _radio(comms, "NAV_2")
        radio.update(targetfreq=115.0, is_prompting=True)
        comms.player = MagicMock(source="sound")
        comms.compute_next_plugin_state()
        assert radio["is_prompting"] is True

    def test_target_missed_after_the_max_delay(self, comms):
        radio = _radio(comms, "COM_1")
        radio.update(targetfreq=115.0, _response_start=1)
        comms.scenario_time = 21  # 20 s = maxresponsedelay
        comms.compute_next_plugin_state()
        assert radio["targetfreq"] is None
        perf = _performance(comms)
        assert perf["sdt_value"] == "MISS"
        assert perf["target_radio"] == "COM_1"
        assert perf["target_frequency"] == 115.0
        assert math.isnan(perf["response_time"])

    def test_active_frequency_kept_in_the_air_band(self, comms):
        comms.get_active_radio_dict()["currentfreq"] = 200.0
        comms.compute_next_plugin_state()
        assert comms.get_active_radio_dict()["currentfreq"] == 137.0

    def test_feedback_timer_expires(self, comms):
        radio = _radio(comms, "NAV_2")
        radio.update(_feedbacktimer=100, _feedbacktype="positive")
        comms.compute_next_plugin_state()
        assert radio["_feedbacktimer"] == 20  # 100 - taskupdatetime (80)
        comms.scenario_time = 2
        comms.compute_next_plugin_state()
        assert radio["_feedbacktimer"] is None
        assert radio["_feedbacktype"] is None


class TestRefreshWidgets:
    @pytest.fixture(autouse=True)
    def base_refresh(self, comms):
        comms.widgets["communications_callsign"] = MagicMock()
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            yield

    def test_arrows_follow_the_active_radio(self, comms):
        radios = comms.parameters["radios"]
        radios[1]["widget"].is_selected = True  # Previously active
        comms.refresh_widgets()
        radios[0]["widget"].show_arrows.assert_called_once()
        radios[1]["widget"].hide_arrows.assert_called_once()
        radios[2]["widget"].show_arrows.assert_not_called()
        radios[2]["widget"].hide_arrows.assert_not_called()
        comms.widgets["communications_callsign"].set_text.assert_called_once_with(comms.parameters["owncallsign"])

    def test_frequencies_and_colors(self, comms):
        radios = comms.parameters["radios"]
        radios[1].update(_feedbacktimer=500, _feedbacktype="negative")
        radios[2]["_hint_color"] = (1, 2, 3, 255)
        comms.refresh_widgets()
        radios[0]["widget"].set_frequency_text.assert_called_once_with(radios[0]["currentfreq"])
        radios[0]["widget"].set_feedback_color.assert_called_once_with(C["BACKGROUND"])
        radios[1]["widget"].set_feedback_color.assert_called_once_with(C["RED"])
        radios[2]["widget"].set_feedback_color.assert_called_once_with((1, 2, 3, 255))

    def test_hidden_plugin_is_not_refreshed(self, comms):
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=False):
            comms.refresh_widgets()
        comms.widgets["communications_callsign"].set_text.assert_not_called()


class TestConfirmResponse:
    def _target(self, comms, name, freq, start=0.5):
        _radio(comms, name).update(targetfreq=freq, _response_start=start, is_prompting=False)

    def test_hit(self, comms):
        comms.parameters["feedbacks"]["positive"]["active"] = True
        self._target(comms, "NAV_1", _radio(comms, "NAV_1")["currentfreq"])
        comms.confirm_response()
        perf = _performance(comms)
        assert perf["sdt_value"] == "HIT"
        assert perf["correct_radio"] is True
        assert perf["response_deviation"] == 0
        assert perf["response_time"] == pytest.approx(500)
        assert perf["resolved_by"] == "human"
        radio = _radio(comms, "NAV_1")
        assert radio["targetfreq"] is None
        assert radio["_feedbacktype"] == "positive"
        assert radio["_feedbacktimer"] == 1500

    def test_bad_frequency(self, comms):
        comms.parameters["feedbacks"]["negative"]["active"] = True
        active_freq = _radio(comms, "NAV_1")["currentfreq"]
        self._target(comms, "NAV_1", round(active_freq + 1.2, 1))
        comms.confirm_response(emulate=True)
        perf = _performance(comms)
        assert perf["sdt_value"] == "BAD_FREQ"
        assert perf["response_deviation"] == pytest.approx(-1.2)
        assert perf["resolved_by"] == "agent"
        assert _radio(comms, "NAV_1")["targetfreq"] is not None  # Still to be responded
        assert _radio(comms, "NAV_1")["_feedbacktype"] == "negative"

    def test_bad_radio_measured_on_the_single_target(self, comms):
        self._target(comms, "COM_2", _radio(comms, "NAV_1")["currentfreq"])
        comms.confirm_response()
        perf = _performance(comms)
        assert perf["sdt_value"] == "BAD_RADIO"
        assert perf["target_radio"] == "COM_2"
        assert perf["responded_radio"] == "NAV_1"
        assert perf["correct_radio"] is False

    def test_two_other_targets_cannot_be_measured(self, comms):
        self._target(comms, "COM_1", 120.0)
        self._target(comms, "COM_2", 125.0)
        comms.confirm_response()
        perf = _performance(comms)
        assert math.isnan(perf["target_frequency"])
        assert math.isnan(perf["response_time"])
        assert perf["target_radio"] != perf["target_radio"]  # NaN

    def test_false_alarm(self, comms):
        comms.parameters["feedbacks"]["negative"]["active"] = True
        comms.confirm_response()
        perf = _performance(comms)
        assert perf["sdt_value"] == "FA"
        assert perf["response_was_needed"] is False
        assert math.isnan(perf["correct_radio"])
        assert _radio(comms, "NAV_1")["_feedbacktype"] == "negative"

    def test_prompting_radio_is_not_waiting_yet(self, comms):
        _radio(comms, "NAV_1").update(targetfreq=110.0, _response_start=None, is_prompting=True)
        comms.confirm_response()
        assert _performance(comms)["sdt_value"] == "FA"

    def test_inactive_feedback_is_not_set(self, comms):
        comms.confirm_response()
        assert _radio(comms, "NAV_1")["_feedbacktimer"] is None


class TestDoOnKey:
    @pytest.fixture(autouse=True)
    def window(self, no_modal_dialog):
        yield

    def _active(self, comms):
        return comms.get_active_radio_dict()["name"]

    def test_select_radio_down_and_up(self, comms):
        comms.do_on_key("DOWN", "press", False)
        assert self._active(comms) == "NAV_2"
        comms.do_on_key("UP", "press", False)
        assert self._active(comms) == "NAV_1"

    def test_selection_stops_at_the_ends(self, comms):
        comms.do_on_key("UP", "press", False)
        assert self._active(comms) == "NAV_1"
        for _ in range(5):
            comms.do_on_key("DOWN", "press", False)
        assert self._active(comms) == "COM_2"

    @pytest.mark.parametrize("key, delta", [("RIGHT", 0.1), ("LEFT", -0.1)])
    def test_tune(self, comms, key, delta):
        radio = comms.get_active_radio_dict()
        before = radio["currentfreq"]
        comms.do_on_key(key, "press", False)
        assert radio["currentfreq"] == pytest.approx(before + delta)

    def test_enter_validates(self, comms):
        comms.confirm_response = MagicMock()
        comms.do_on_key("ENTER", "press", True)
        comms.confirm_response.assert_called_once_with(emulate=True)

    def test_release_is_ignored(self, comms):
        comms.do_on_key("DOWN", "release", False)
        assert self._active(comms) == "NAV_1"

    def test_other_keys_are_ignored(self, comms):
        comms.confirm_response = MagicMock()
        comms.do_on_key("SPACE", "press", False)
        assert self._active(comms) == "NAV_1"
        comms.confirm_response.assert_not_called()

    def test_keys_ignored_when_not_executable(self, comms):
        comms.can_execute_keys = False
        comms.do_on_key("DOWN", "press", False)
        assert self._active(comms) == "NAV_1"


class TestDoOnMousePress:
    LEFT = mouse.LEFT

    @pytest.fixture(autouse=True)
    def radios_on_screen(self, comms, no_modal_dialog):
        """Radios stacked 100 px high, 400 px wide; the first one at the top."""
        for pos, radio in comms.parameters["radios"].items():
            radio["widget"].container = Container(radio["name"], 0, 300 - 100 * pos, 400, 100)
        comms.do_on_key = MagicMock(wraps=comms.do_on_key)

    def _pressed_keys(self, comms):
        return [c.args[0] for c in comms.do_on_key.call_args_list]

    def test_click_on_another_radio_selects_it(self, comms):
        comms.do_on_mouse_press(200, 50, self.LEFT)  # COM_2
        assert self._pressed_keys(comms) == ["DOWN", "DOWN", "DOWN"]
        assert comms.get_active_radio_dict()["name"] == "COM_2"
        comms.logger.record_input.assert_called_with("mouse_key", "DOWN", "press")

        comms.do_on_key.reset_mock()
        comms.do_on_mouse_press(200, 350, self.LEFT)  # NAV_1
        assert self._pressed_keys(comms) == ["UP", "UP", "UP"]

    @pytest.mark.parametrize("x, key", [(50, "LEFT"), (350, "RIGHT"), (200, "ENTER")])
    def test_zones_of_the_active_radio(self, comms, x, key):
        comms.confirm_response = MagicMock()
        comms.do_on_mouse_press(x, 350, self.LEFT)
        assert self._pressed_keys(comms) == [key]
        comms.logger.record_input.assert_called_once_with("mouse_key", key, "press")

    def test_click_outside_the_radios(self, comms):
        comms.do_on_mouse_press(200, 1000, self.LEFT)
        comms.do_on_key.assert_not_called()

    def test_right_button_is_ignored(self, comms):
        comms.do_on_mouse_press(200, 350, mouse.RIGHT)
        comms.do_on_key.assert_not_called()
