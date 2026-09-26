"""Tests for plugins.sysmon - the plugin built by its constructor (arrows, failures, feedbacks, inputs)."""

import math
from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import mouse

from core import validation
from core.constants import COLORS as C
from core.container import Container
from plugins.abstractplugin import AbstractPlugin
from plugins.sysmon import Sysmon


@pytest.fixture
def sysmon(mock_logger):
    """A running Sysmon plugin, with mock gauge widgets and a mock logger."""
    s = Sysmon()
    s.paused = False
    s.visible = True
    s.can_execute_keys = True
    s.scenario_time = 10
    s.joystick = None
    for gauge in s.get_all_gauges():
        gauge["widget"] = MagicMock()
    return s


@pytest.fixture
def no_modal_dialog():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        yield mock_win


def _scale(s, n):
    return s.parameters["scales"][str(n)]


def _light(s, n):
    return s.parameters["lights"][str(n)]


def _performance(s):
    """Last value logged for each performance measure."""
    return {name: values[-1] for name, values in s.performance.items()}


def _nan(value):
    return isinstance(value, float) and math.isnan(value)


class TestInit:
    def test_default_parameters(self, sysmon):
        p = sysmon.parameters
        assert p["title"] == "System monitoring"
        assert p["taskplacement"] == "topleft"
        assert p["taskupdatetime"] == 200
        assert p["alerttimeout"] == 10000
        assert p["automaticsolver"] is False
        assert p["allowanykey"] is False
        assert p["feedbackduration"] == 1500
        assert p["feedbacks"]["positive"]["color"] == C["GREEN"]
        assert p["feedbacks"]["negative"]["color"] == C["RED"]
        assert sysmon.keys == {"F1", "F2", "F3", "F4", "F5", "F6"}

    def test_default_gauges(self, sysmon):
        assert [s["key"] for s in sysmon.get_scale_gauges()] == ["F1", "F2", "F3", "F4"]
        assert [g["key"] for g in sysmon.get_light_gauges()] == ["F5", "F6"]
        assert _light(sysmon, 1)["on"] is True
        assert _light(sysmon, 2)["on"] is False

    def test_every_gauge_gets_private_parameters(self, sysmon):
        for gauge in sysmon.get_all_gauges():
            assert gauge["_failuretimer"] is None
            assert gauge["_onfailure"] is False
            assert gauge["_response_start"] is None
            assert gauge["_freezetimer"] is None

    def test_only_scales_get_arrow_and_feedback_parameters(self, sysmon):
        for scale in sysmon.get_scale_gauges():
            assert scale["_pos"] == 5
            assert scale["_zone"] == 0
            assert scale["_feedbacktimer"] is None
            assert scale["_feedbacktype"] is None
            assert scale["_hint_arrow_color"] is None
        for light in sysmon.get_light_gauges():
            assert "_pos" not in light
            assert "_feedbacktimer" not in light

    def test_scale_zones_split_the_eleven_positions(self, sysmon):
        assert sysmon.scale_zones == {1: [0, 1, 2], 0: [3, 4, 5, 6, 7], -1: [8, 9, 10]}

    def test_indexed_validators(self, sysmon):
        v = sysmon.validation_dict
        assert v["lights-2-oncolor"] is validation.is_color
        assert v["lights-1-default"] == (validation.is_in_list, ["on", "off"])
        assert v["scales-4-key"] is validation.is_key
        assert v["scales-1-side"] == (validation.is_in_list, ["-1", "0", "1"])
        assert "scales-5-key" not in v
        assert "lights-3-key" not in v


class TestGaugeQueries:
    def test_response_timers_are_zero_without_failure(self, sysmon):
        assert sysmon.get_response_timers() == [0.0] * 6

    def test_response_timers_count_from_failure_start(self, sysmon):
        _scale(sysmon, 2)["_response_start"] = 8.5
        _light(sysmon, 1)["_response_start"] = 9
        assert sysmon.get_response_timers() == [0.0, 1500.0, 0.0, 0.0, 1000.0, 0.0]

    def test_active_fault(self, sysmon):
        assert sysmon.has_active_fault() is False
        _light(sysmon, 2)["_onfailure"] = True
        assert sysmon.has_active_fault() is True
        assert sysmon.get_gauges_on_failure() == [_light(sysmon, 2)]

    def test_gauge_by_key(self, sysmon):
        assert sysmon.get_gauge_by_key("F3") is _scale(sysmon, 3)
        assert sysmon.get_gauge_by_key("F6") is _light(sysmon, 2)

    def test_gauge_key_is_its_index(self, sysmon):
        assert sysmon.get_gauge_key(_scale(sysmon, 4)) == "4"
        assert sysmon.get_gauge_key(_light(sysmon, 2)) == "2"

    def test_unknown_gauge_has_no_key(self, sysmon):
        assert sysmon.get_gauge_key({"name": "unknown"}) is None

    def test_light_color(self, sysmon):
        assert sysmon.determine_light_color(_light(sysmon, 1)) == C["GREEN"]
        assert sysmon.determine_light_color(_light(sysmon, 2)) == C["BACKGROUND"]
        _light(sysmon, 2)["on"] = True
        assert sysmon.determine_light_color(_light(sysmon, 2)) == C["RED"]


class TestCreateWidgets:
    @pytest.fixture
    def created(self, sysmon):
        def base_create_widgets(plugin):
            plugin.task_container = Container("task", 0, 0, 400, 300)

        with (
            patch.object(AbstractPlugin, "create_widgets", base_create_widgets),
            patch("plugins.sysmon.Scale") as mock_scale,
            patch("plugins.sysmon.Light") as mock_light,
        ):
            sysmon.create_widgets()
        return sysmon, mock_scale, mock_light

    def test_four_scales_side_by_side(self, created):
        sysmon, mock_scale, _ = created
        assert mock_scale.call_count == 4
        for n, call in enumerate(mock_scale.call_args_list, start=1):
            name, container = call.args
            assert name == f"sysmon_scale{n}"
            assert (container.l, container.b, container.w, container.h) == (100 * (n - 1) + 30, 45, 40, 150)
            assert call.kwargs == {"label": f"F{n}", "arrow_position": 5}
            assert _scale(sysmon, n)["widget"] is sysmon.widgets[f"sysmon_scale{n}"]

    def test_two_lights_above_scales(self, created):
        sysmon, _, mock_light = created
        assert mock_light.call_count == 2
        expected_colors = [C["GREEN"], C["BACKGROUND"]]
        for n, call in enumerate(mock_light.call_args_list, start=1):
            name, container = call.args
            assert name == f"sysmon_light{n}"
            assert (container.l, container.b, container.w, container.h) == (200 * (n - 1) + 20, 225, 160, 45)
            assert call.kwargs == {"label": f"F{n + 4}", "color": expected_colors[n - 1]}
            assert _light(sysmon, n)["widget"] is sysmon.widgets[f"sysmon_light{n}"]

    def test_widget_areas_are_recorded(self, created):
        sysmon = created[0]
        names = [call.args[1] for call in sysmon.logger.record_aoi.call_args_list]
        assert names == [f"sysmon_scale{n}" for n in range(1, 5)] + ["sysmon_light1", "sysmon_light2"]


class TestComputeNextState:
    def test_nothing_happens_when_paused(self, sysmon):
        sysmon.paused = True
        _scale(sysmon, 1)["failure"] = True
        sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_onfailure"] is False
        assert sysmon.moving_seed == 1

    def test_arrow_moves_in_the_drawn_direction(self, sysmon):
        with patch("plugins.sysmon.sample", return_value=1) as mock_sample:
            sysmon.compute_next_plugin_state()
        assert [s["_pos"] for s in sysmon.get_scale_gauges()] == [6, 6, 6, 6]
        # One distinct seed per scale
        assert [c.args[3] for c in mock_sample.call_args_list] == [2, 3, 4, 5]
        assert all(c.args[:3] == ([-1, 1], "sysmon", 10) for c in mock_sample.call_args_list)

    def test_arrow_bounces_on_the_zone_limit(self, sysmon):
        _scale(sysmon, 1)["_pos"] = 7
        _scale(sysmon, 2)["_pos"] = 3
        with patch("plugins.sysmon.sample", side_effect=[1, -1, 1, 1]):
            sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_pos"] == 6
        assert _scale(sysmon, 2)["_pos"] == 4

    def test_arrow_jumps_into_its_new_zone(self, sysmon):
        _scale(sysmon, 1)["_zone"] = -1
        with patch("plugins.sysmon.sample", side_effect=[9, 1, 1, 1]) as mock_sample:
            sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_pos"] == 9
        assert mock_sample.call_args_list[0].args[0] == [8, 9, 10]

    def test_arrow_stays_in_its_zone_with_real_pseudorandom(self, sysmon):
        for n, zone in zip(range(1, 5), [1, 0, -1, 0]):
            _scale(sysmon, n)["_zone"] = zone
        for step in range(20):
            sysmon.scenario_time = 10 + step
            sysmon.compute_next_plugin_state()
            for scale in sysmon.get_scale_gauges():
                assert scale["_pos"] in sysmon.scale_zones[scale["_zone"]]

    def test_frozen_arrow_stays_centered(self, sysmon):
        _scale(sysmon, 1)["_freezetimer"] = 400
        with patch("plugins.sysmon.sample", return_value=1):
            sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_pos"] == 5
        assert _scale(sysmon, 1)["_freezetimer"] == 200
        assert _scale(sysmon, 2)["_pos"] == 6

    def test_freeze_ends_when_timer_expires(self, sysmon):
        _scale(sysmon, 1)["_freezetimer"] = 200
        with patch("plugins.sysmon.sample", return_value=1):
            sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_freezetimer"] is None
        assert _scale(sysmon, 1)["_pos"] == 6

    def test_non_integer_freeze_timer_is_ignored(self, sysmon):
        _scale(sysmon, 1)["_freezetimer"] = 400.0
        with patch("plugins.sysmon.sample", return_value=1):
            sysmon.compute_next_plugin_state()
        assert _scale(sysmon, 1)["_freezetimer"] == 400.0
        assert _scale(sysmon, 1)["_pos"] == 6

    def test_feedback_timer_counts_down_then_clears(self, sysmon):
        scale = _scale(sysmon, 3)
        sysmon.set_scale_feedback(scale, "positive")
        sysmon.compute_next_plugin_state()
        assert scale["_feedbacktimer"] == 1300
        assert scale["_feedbacktype"] == "positive"
        scale["_feedbacktimer"] = 200
        sysmon.scenario_time = 11
        sysmon.compute_next_plugin_state()
        assert scale["_feedbacktimer"] is None
        assert scale["_feedbacktype"] is None

    def test_failure_flag_starts_a_failure(self, sysmon):
        _light(sysmon, 1)["failure"] = True
        sysmon.compute_next_plugin_state()
        light = _light(sysmon, 1)
        assert light["_onfailure"] is True
        assert light["on"] is False
        assert light["failure"] is False
        assert light["_failuretimer"] == 10000
        assert light["_response_start"] == 10

    def test_failure_timer_counts_down(self, sysmon):
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.compute_next_plugin_state()
        assert _light(sysmon, 2)["_failuretimer"] == 9800
        assert _light(sysmon, 2)["_onfailure"] is True

    def test_unanswered_failure_is_a_miss(self, sysmon):
        scale = _scale(sysmon, 2)
        scale["side"] = 1
        sysmon.start_failure(scale)
        scale["_failuretimer"] = 200
        sysmon.scenario_time = 20
        sysmon.compute_next_plugin_state()
        assert scale["_onfailure"] is False
        assert scale["_zone"] == 0
        assert scale["_feedbacktype"] == "negative"
        perf = _performance(sysmon)
        assert perf["name"] == "F2"
        assert perf["signal_detection"] == "MISS"
        assert _nan(perf["response_time"])
        assert perf["resolved_by"] == ""

    def test_failure_expiring_under_automatic_solver_is_an_automatic_hit(self, sysmon):
        sysmon.parameters["automaticsolver"] = True
        light = _light(sysmon, 2)
        sysmon.start_failure(light)
        light["_failuretimer"] = 100
        sysmon.scenario_time = 12
        sysmon.compute_next_plugin_state()
        assert light["on"] is False
        perf = _performance(sysmon)
        assert perf["signal_detection"] == "HIT"
        assert perf["response_time"] == 2000
        assert perf["resolved_by"] == "auto"


class TestRefreshWidgets:
    def _refresh(self, sysmon):
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            sysmon.refresh_widgets()

    def test_nothing_is_refreshed_when_hidden(self, sysmon):
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=False):
            sysmon.refresh_widgets()
        for gauge in sysmon.get_all_gauges():
            gauge["widget"].set_label.assert_not_called()

    def test_arrows_follow_their_position(self, sysmon):
        _scale(sysmon, 2)["_pos"] = 8
        self._refresh(sysmon)
        _scale(sysmon, 1)["widget"].set_arrow_position.assert_called_once_with(5)
        _scale(sysmon, 2)["widget"].set_arrow_position.assert_called_once_with(8)

    def test_arrow_is_black_unless_an_agent_hint_is_set(self, sysmon):
        _scale(sysmon, 3)["_hint_arrow_color"] = C["BLUE"]
        self._refresh(sysmon)
        _scale(sysmon, 3)["widget"].set_arrow_color.assert_called_once_with(C["BLUE"])
        _scale(sysmon, 4)["widget"].set_arrow_color.assert_called_once_with(C["BLACK"])

    def test_feedback_is_shown_with_its_color_while_active(self, sysmon):
        sysmon.set_scale_feedback(_scale(sysmon, 1), "positive")
        sysmon.set_scale_feedback(_scale(sysmon, 2), "negative")
        self._refresh(sysmon)
        w1, w2, w3 = (_scale(sysmon, n)["widget"] for n in (1, 2, 3))
        w1.set_feedback_color.assert_called_once_with(C["GREEN"])
        w1.set_feedback_visibility.assert_called_once_with(True)
        w2.set_feedback_color.assert_called_once_with(C["RED"])
        w3.set_feedback_color.assert_not_called()
        w3.set_feedback_visibility.assert_called_once_with(False)

    def test_lights_show_their_state(self, sysmon):
        _light(sysmon, 1)["on"] = False
        _light(sysmon, 2)["on"] = True
        self._refresh(sysmon)
        _light(sysmon, 1)["widget"].set_color.assert_called_once_with(C["BACKGROUND"])
        _light(sysmon, 2)["widget"].set_color.assert_called_once_with(C["RED"])

    def test_labels_follow_gauge_names(self, sysmon):
        _light(sysmon, 1)["name"] = "PUMP"
        self._refresh(sysmon)
        _light(sysmon, 1)["widget"].set_label.assert_called_once_with("PUMP")
        _scale(sysmon, 4)["widget"].set_label.assert_called_once_with("F4")


class TestStartFailure:
    def test_light_failure_inverts_its_default_state(self, sysmon):
        sysmon.start_failure(_light(sysmon, 1))
        sysmon.start_failure(_light(sysmon, 2))
        assert _light(sysmon, 1)["on"] is False
        assert _light(sysmon, 2)["on"] is True

    def test_scale_failure_with_a_given_side_moves_to_that_zone(self, sysmon):
        scale = _scale(sysmon, 1)
        scale["side"] = -1
        with patch("plugins.sysmon.choice") as mock_choice:
            sysmon.start_failure(scale)
        mock_choice.assert_not_called()
        assert scale["_zone"] == -1
        assert scale["_onfailure"] is True

    def test_scale_failure_without_side_draws_one(self, sysmon):
        scale = _scale(sysmon, 3)
        with patch("plugins.sysmon.choice", return_value=1) as mock_choice:
            sysmon.start_failure(scale)
        # The gauge index makes the seed unique
        mock_choice.assert_called_once_with([-1, 1], "sysmon", 10, 3)
        assert scale["side"] == 1
        assert scale["_zone"] == 1

    def test_drawn_side_is_up_or_down(self, sysmon):
        sysmon.start_failure(_scale(sysmon, 2))
        assert _scale(sysmon, 2)["side"] in (-1, 1)
        assert _scale(sysmon, 2)["_zone"] == _scale(sysmon, 2)["side"]

    def test_failure_on_a_failing_gauge_is_ignored(self, sysmon):
        light = _light(sysmon, 1)
        sysmon.start_failure(light)
        light["_failuretimer"] = 500
        light["failure"] = True
        sysmon.scenario_time = 15
        sysmon.start_failure(light)
        sysmon.logger.log.assert_called_once_with("[sysmon] Failure ignored on 'F5': already on failure")
        assert light["on"] is False
        assert light["failure"] is False
        # The timers are nevertheless restarted
        assert light["_response_start"] == 15
        assert light["_failuretimer"] == 10000

    def test_agent_can_shorten_the_failure(self, sysmon):
        sysmon.parameters["automaticsolver"] = True
        sysmon.agent = MagicMock()
        sysmon.agent.on_failure_started.return_value = {"delay": 1200}
        light = _light(sysmon, 2)
        sysmon.start_failure(light)
        sysmon.agent.on_failure_started.assert_called_once_with(sysmon, light)
        assert light["_failuretimer"] == 1200

    def test_agent_without_delay_keeps_the_alert_timeout(self, sysmon):
        sysmon.parameters["automaticsolver"] = True
        sysmon.parameters["alerttimeout"] = 5000
        sysmon.agent = MagicMock()
        sysmon.agent.on_failure_started.return_value = {}
        sysmon.start_failure(_light(sysmon, 2))
        assert _light(sysmon, 2)["_failuretimer"] == 5000

    def test_agent_is_not_asked_without_automatic_solver(self, sysmon):
        sysmon.agent = MagicMock()
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.agent.on_failure_started.assert_not_called()
        assert _light(sysmon, 2)["_failuretimer"] == 10000


class TestStopFailure:
    def test_success_is_a_hit_with_response_time(self, sysmon):
        scale = _scale(sysmon, 4)
        scale["side"] = 1
        sysmon.start_failure(scale)
        sysmon.scenario_time = 12.5
        sysmon.stop_failure(scale, success=True, resolved_by="human")
        assert sysmon.performance == {
            "name": ["F4"],
            "signal_detection": ["HIT"],
            "response_time": [2500.0],
            "resolved_by": ["human"],
        }
        sysmon.logger.log_performance.assert_any_call("sysmon", "signal_detection", "HIT")

    def test_success_resets_the_scale_and_freezes_its_arrow(self, sysmon):
        scale = _scale(sysmon, 4)
        scale["side"] = -1
        sysmon.start_failure(scale)
        sysmon.stop_failure(scale, success=True)
        assert scale["_onfailure"] is False
        assert scale["_failuretimer"] is None
        assert scale["_response_start"] is None
        assert scale["_zone"] == 0
        assert scale["_freezetimer"] == 1500
        assert scale["_feedbacktype"] == "positive"
        assert scale["_feedbacktimer"] == 1500

    def test_failure_is_a_miss_without_freeze(self, sysmon):
        light = _light(sysmon, 1)
        sysmon.start_failure(light)
        sysmon.stop_failure(light)
        assert light["on"] is True
        assert light["_freezetimer"] is None
        perf = _performance(sysmon)
        assert perf["signal_detection"] == "MISS"
        assert _nan(perf["response_time"])

    def test_lights_get_no_feedback(self, sysmon):
        light = _light(sysmon, 2)
        sysmon.start_failure(light)
        sysmon.stop_failure(light, success=True)
        assert "_feedbacktimer" not in light

    def test_light_after_a_false_alarm_still_gets_no_feedback(self, sysmon, no_modal_dialog):
        """A false alarm on a light must not make its later stop_failure set a feedback."""
        light = _light(sysmon, 1)
        sysmon.do_on_key("F5", "press", False)
        sysmon.start_failure(light)
        sysmon.stop_failure(light)
        assert "_feedbacktimer" not in light
        assert "_feedbacktype" not in light

    def test_inactive_feedback_is_not_set(self, sysmon):
        sysmon.parameters["feedbacks"]["negative"]["active"] = False
        scale = _scale(sysmon, 1)
        scale["side"] = 1
        sysmon.start_failure(scale)
        sysmon.stop_failure(scale)
        assert scale["_feedbacktimer"] is None
        assert scale["_feedbacktype"] is None


@pytest.mark.usefixtures("no_modal_dialog")
class TestDoOnKey:
    def test_pressing_a_failing_gauge_key_is_a_hit(self, sysmon):
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.scenario_time = 11
        sysmon.do_on_key("F6", "press", False)
        assert _light(sysmon, 2)["_onfailure"] is False
        assert _light(sysmon, 2)["on"] is False
        assert _performance(sysmon) == {
            "name": "F6",
            "signal_detection": "HIT",
            "response_time": 1000.0,
            "resolved_by": "human",
        }

    def test_emulated_key_is_resolved_by_the_agent(self, sysmon):
        _scale(sysmon, 1)["side"] = 1
        sysmon.start_failure(_scale(sysmon, 1))
        sysmon.do_on_key("F1", "press", True)
        assert _performance(sysmon)["resolved_by"] == "agent"

    def test_pressing_a_nominal_gauge_key_is_a_false_alarm(self, sysmon):
        sysmon.do_on_key("F2", "press", False)
        perf = _performance(sysmon)
        assert perf["name"] == "F2"
        assert perf["signal_detection"] == "FA"
        assert _nan(perf["response_time"])
        assert perf["resolved_by"] == "human"
        assert _scale(sysmon, 2)["_feedbacktype"] == "negative"
        assert _scale(sysmon, 2)["_feedbacktimer"] == 1500

    def test_false_alarm_on_a_light_sets_no_feedback(self, sysmon):
        """Lights have no feedback widget: a false alarm only logs the FA."""
        sysmon.do_on_key("F6", "press", False)
        assert _performance(sysmon)["signal_detection"] == "FA"
        assert "_feedbacktimer" not in _light(sysmon, 2)
        assert "_feedbacktype" not in _light(sysmon, 2)

    def test_false_alarm_without_negative_feedback(self, sysmon):
        sysmon.parameters["feedbacks"]["negative"]["active"] = False
        sysmon.do_on_key("F2", "press", False)
        assert _performance(sysmon)["signal_detection"] == "FA"
        assert _scale(sysmon, 2)["_feedbacktimer"] is None

    def test_key_release_is_ignored(self, sysmon):
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.do_on_key("F6", "release", False)
        assert _light(sysmon, 2)["_onfailure"] is True
        assert not hasattr(sysmon, "performance")

    def test_unknown_key_is_ignored(self, sysmon):
        sysmon.do_on_key("F9", "press", False)
        assert not hasattr(sysmon, "performance")

    def test_keys_are_ignored_when_not_executable(self, sysmon):
        sysmon.can_execute_keys = False
        sysmon.do_on_key("F1", "press", False)
        assert not hasattr(sysmon, "performance")

    def test_keys_are_ignored_under_a_modal_dialog(self, sysmon, no_modal_dialog):
        no_modal_dialog.MainWindow.modal_dialog = MagicMock()
        sysmon.do_on_key("F1", "press", False)
        assert not hasattr(sysmon, "performance")

    def test_any_key_mode_resolves_the_first_failure(self, sysmon):
        sysmon.parameters["allowanykey"] = True
        sysmon.keys.add("SPACE")
        sysmon.start_failure(_light(sysmon, 1))
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.do_on_key("SPACE", "press", False)
        assert _light(sysmon, 1)["_onfailure"] is False
        assert _light(sysmon, 2)["_onfailure"] is True
        assert _performance(sysmon)["name"] == "F5"
        assert _performance(sysmon)["signal_detection"] == "HIT"

    def test_any_key_mode_without_failure_does_nothing(self, sysmon):
        sysmon.parameters["allowanykey"] = True
        sysmon.keys.add("SPACE")
        sysmon.do_on_key("SPACE", "press", False)
        assert not hasattr(sysmon, "performance")

    def test_any_key_mode_still_accepts_gauge_keys(self, sysmon):
        sysmon.parameters["allowanykey"] = True
        sysmon.keys.add("SPACE")
        sysmon.do_on_key("F3", "press", False)
        assert _performance(sysmon)["signal_detection"] == "FA"

    def test_any_key_mode_set_from_a_scenario_accepts_space(self, sysmon):
        """sysmon;allowanykey;True: SPACE resolves the failure like the gauge key."""
        sysmon.set_parameter("allowanykey", True)
        _scale(sysmon, 2)["side"] = 1
        sysmon.start_failure(_scale(sysmon, 2))
        sysmon.scenario_time = 11
        sysmon.do_on_key("SPACE", "press", False)
        assert _scale(sysmon, 2)["_onfailure"] is False
        assert _scale(sysmon, 2)["_feedbacktype"] == "positive"
        assert _performance(sysmon) == {
            "name": "F2",
            "signal_detection": "HIT",
            "response_time": 1000.0,
            "resolved_by": "human",
        }

    def test_space_is_ignored_when_any_key_mode_is_off(self, sysmon):
        """SPACE left in the keys without allowanykey does nothing (and does not crash)."""
        sysmon.keys.add("SPACE")
        sysmon.start_failure(_light(sysmon, 1))
        sysmon.do_on_key("SPACE", "press", False)
        assert _light(sysmon, 1)["_onfailure"] is True
        assert not hasattr(sysmon, "performance")

    def test_space_is_ignored_once_any_key_mode_is_switched_off(self, sysmon):
        """Turning allowanykey off from a scenario disables the SPACE shortcut again."""
        sysmon.set_parameter("allowanykey", True)
        sysmon.do_on_key("SPACE", "press", False)
        sysmon.set_parameter("allowanykey", False)
        sysmon.start_failure(_light(sysmon, 1))
        sysmon.do_on_key("SPACE", "press", False)
        assert _light(sysmon, 1)["_onfailure"] is True
        assert not hasattr(sysmon, "performance")

    def test_cooperative_agent_enables_space(self, sysmon):
        """The cooperative agent turns allowanykey on and SPACE then resolves failures."""
        from agents.cooperative_agent import CooperativeAgent

        CooperativeAgent()._update_sysmon(sysmon)
        sysmon.start_failure(_light(sysmon, 2))
        sysmon.do_on_key("SPACE", "press", False)
        assert _light(sysmon, 2)["_onfailure"] is False
        assert _performance(sysmon)["signal_detection"] == "HIT"


@pytest.mark.usefixtures("no_modal_dialog")
class TestMousePress:
    @pytest.fixture(autouse=True)
    def gauge_areas(self, sysmon):
        for n, gauge in enumerate(sysmon.get_all_gauges()):
            gauge["widget"].container = Container(f"gauge{n}", n * 100, 0, 50, 50)

    def test_click_on_a_gauge_presses_its_key(self, sysmon):
        sysmon.start_failure(_light(sysmon, 1))  # 5th gauge: x in [400, 450]
        sysmon.do_on_mouse_press(425, 25, mouse.LEFT)
        sysmon.logger.record_input.assert_called_once_with("mouse_key", "F5", "press")
        assert _light(sysmon, 1)["_onfailure"] is False
        assert _performance(sysmon)["signal_detection"] == "HIT"

    def test_click_on_a_nominal_gauge_is_a_false_alarm(self, sysmon):
        sysmon.do_on_mouse_press(125, 25, mouse.LEFT)
        assert _performance(sysmon)["name"] == "F2"
        assert _performance(sysmon)["signal_detection"] == "FA"

    def test_click_outside_the_gauges_does_nothing(self, sysmon):
        sysmon.do_on_mouse_press(75, 25, mouse.LEFT)
        sysmon.logger.record_input.assert_not_called()
        assert not hasattr(sysmon, "performance")

    def test_other_buttons_are_ignored(self, sysmon):
        sysmon.do_on_mouse_press(25, 25, mouse.RIGHT)
        sysmon.logger.record_input.assert_not_called()
        assert not hasattr(sysmon, "performance")
