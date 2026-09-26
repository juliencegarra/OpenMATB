"""Tests for plugins.resman - the plugin built by its constructor (widgets, tanks, pumps, inputs)."""

import math
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import mouse

from core.constants import COLORS as C
from core.container import Container
from plugins.abstractplugin import AbstractPlugin
from plugins.resman import Resman

TARGET_TANKS = ("a", "b")


@pytest.fixture
def resman(mock_logger):
    """A running Resman plugin (tanks start leaking at once), with a mock logger."""
    r = Resman()
    r.paused = False
    r.visible = True
    r.can_execute_keys = True
    r.scenario_time = 0
    r.joystick = None
    r.wait_before_leak = 0
    return r


@pytest.fixture
def no_modal_dialog():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        yield mock_win


def _pump_widget(name, container, from_cont, to_cont, y_offset, **kwargs):
    """Pump stand-in: a triangle between the two tanks, like the real widget."""
    x = (from_cont.cx + to_cont.cx) / 2
    y = (from_cont.cy + to_cont.cy) / 2 + y_offset
    widget = MagicMock(name=name)
    widget.vertex = {"triangle": SimpleNamespace(x=x - 5, y=y - 5, x2=x + 5, y2=y - 5, x3=x, y3=y + 5)}
    return widget


def _build_widgets(plugin):
    """Run create_widgets with mock widget classes; return the mocks by class name."""

    def base_create_widgets(p):
        p.task_container = Container("task", 0, 0, 400, 300)

    with (
        patch.object(AbstractPlugin, "create_widgets", base_create_widgets),
        patch("plugins.resman.Window") as mock_window,
        patch("plugins.resman.Frame") as frame,
        patch("plugins.resman.Simpletext") as simpletext,
        patch("plugins.resman.PumpFlow") as pumpflow,
        patch("plugins.resman.Tank", side_effect=lambda name, container, **kw: MagicMock(container=container)) as tank,
        patch("plugins.resman.Pump", side_effect=_pump_widget) as pump,
    ):
        mock_window.MainWindow.get_container.return_value = Container("status", 500, 0, 200, 300)
        plugin.create_widgets()
    return dict(Frame=frame, Simpletext=simpletext, PumpFlow=pumpflow, Tank=tank, Pump=pump, Window=mock_window)


def _step(plugin, n=1):
    """Run n plugin steps (one each taskupdatetime)."""
    for _ in range(n):
        plugin.scenario_time = plugin.next_refresh_time
        plugin.compute_next_plugin_state()


def _last_performance(plugin):
    return {name: values[-1] for name, values in plugin.performance.items()}


def _tank(plugin, letter):
    return plugin.parameters["tank"][letter]


def _pump(plugin, number):
    return plugin.parameters["pump"][str(number)]


def _mock_widgets(plugin):
    for this_pump in plugin.parameters["pump"].values():
        this_pump["widget"] = MagicMock()
        this_pump["statuswidget"] = MagicMock()
    for this_tank in plugin.parameters["tank"].values():
        this_tank["widget"] = MagicMock()
    plugin._tolerance_tanks = {k for k, t in plugin.parameters["tank"].items() if t["target"] is not None}


class TestInit:
    def test_default_parameters(self, resman):
        p = resman.parameters
        assert p["title"] == "Resources management"
        assert p["taskplacement"] == "bottommid"
        assert p["taskupdatetime"] == 2000
        assert p["automaticsolver"] is False
        assert p["toleranceradius"] == 250
        assert resman.keys == {f"NUM_{n}" for n in range(1, 9)}
        assert [pump["key"] for pump in p["pump"].values()] == [f"NUM_{n}" for n in range(1, 9)]
        assert all(pump["state"] == "off" for pump in p["pump"].values())

    def test_new_plugin_waits_one_step_before_leaking(self, mock_logger):
        assert Resman().wait_before_leak == 1

    def test_only_target_tanks_have_response_timers(self, resman):
        for letter, this_tank in resman.parameters["tank"].items():
            if letter in TARGET_TANKS:
                assert this_tank["_response_start"] is None
                assert this_tank["_is_in_tolerance"] is None
                assert this_tank["_tolerance_color"] == C["BLACK"]
            else:
                assert this_tank["target"] is None
                assert "_response_start" not in this_tank

    def test_no_tolerance_display_before_widgets_exist(self, resman):
        assert resman._tolerance_tanks == set()

    def test_validates_indexed_pump_and_tank_parameters(self, resman):
        v = resman.validation_dict
        assert "pump-8-key" in v and "pump-9-key" not in v
        assert "tank-f-lossperminute" in v and "tank-g-level" not in v
        _check, choices = v["pump-3-state"]
        assert choices == ["off", "on", "failure"]


class TestResponseTimers:
    def test_one_timer_per_target_tank(self, resman):
        assert resman.get_response_timers() == [0.0, 0.0]

    def test_timer_counts_from_leaving_tolerance(self, resman):
        _tank(resman, "b")["_response_start"] = 3
        resman.scenario_time = 5.5
        assert resman.get_response_timers() == [0.0, 2500.0]


class TestHasActiveFault:
    def test_no_fault_before_first_step(self, resman):
        assert resman.has_active_fault() is False

    def test_target_tank_out_of_tolerance_is_a_fault(self, resman):
        _step(resman)
        assert resman.has_active_fault() is False
        _tank(resman, "a")["level"] = 1000
        _step(resman)
        assert resman.has_active_fault() is True


class TestCreateWidgets:
    def test_one_widget_per_tank_and_pump_and_status(self, resman):
        mocks = _build_widgets(resman)
        assert mocks["Tank"].call_count == 6
        assert mocks["Pump"].call_count == 8
        assert mocks["PumpFlow"].call_count == 8
        mocks["Window"].MainWindow.get_container.assert_called_once_with("bottomright")
        assert "resman_status_foreground" in resman.widgets
        assert "resman_status_title" in resman.widgets
        for this_pump in resman.parameters["pump"].values():
            assert this_pump["statuswidget"] is resman.widgets[f"resman_pump_{this_pump['key'][-1]}_flow"]

    def test_tank_widgets_follow_tank_parameters(self, resman):
        mocks = _build_widgets(resman)
        calls = {c.args[0]: c for c in mocks["Tank"].call_args_list}
        a = calls["resman_tank_a"].kwargs
        assert (a["letter"], a["level"], a["level_max"], a["target"]) == ("A", 2500, 4000, 2500)
        assert a["fluid_label"] == "2500"
        assert a["toleranceradius"] == 250
        # Non-depletable tanks have no level label
        assert calls["resman_tank_e"].kwargs["fluid_label"] == ""
        # Upper tanks (a, b) are above lower tanks, and wider than the smallest ones (c, d)
        cont = {k[-1]: c.args[1] for k, c in calls.items()}
        assert cont["a"].b > cont["c"].b
        assert cont["a"].w > cont["e"].w > cont["c"].w

    def test_pumps_link_their_tanks(self, resman):
        mocks = _build_widgets(resman)
        calls = {c.args[0]: c.kwargs for c in mocks["Pump"].call_args_list}
        pump1 = calls["resman_pump_1"]
        assert pump1["from_cont"] is _tank(resman, "c")["widget"].container
        assert pump1["to_cont"] is _tank(resman, "a")["widget"].container
        assert pump1["color"] == C["WHITE"]
        # Only the 7th pump (between a and b) is raised to avoid the 8th
        assert calls["resman_pump_7"]["y_offset"] > 0
        assert calls["resman_pump_8"]["y_offset"] == 0

    def test_pump_click_area_surrounds_its_triangle(self, resman):
        _build_widgets(resman)
        this_pump = _pump(resman, 1)
        tri = this_pump["widget"].vertex["triangle"]
        area = this_pump["_click_container"]
        assert area.contains_xy(tri.x3, tri.y3)
        assert area.contains_xy(tri.x, tri.y)
        assert not area.contains_xy(tri.x3, tri.y3 + 50)

    def test_no_pump_status_when_not_displayed(self, resman):
        resman.parameters["displaystatus"] = False
        mocks = _build_widgets(resman)
        mocks["PumpFlow"].assert_not_called()
        mocks["Window"].MainWindow.get_container.assert_not_called()
        assert "statuswidget" not in _pump(resman, 1)
        assert "resman_status_foreground" not in resman.widgets

    def test_only_target_tanks_display_a_tolerance(self, resman):
        _build_widgets(resman)
        assert resman._tolerance_tanks == set(TARGET_TANKS)

    def test_scenario_target_on_another_tank_is_displayed(self, resman):
        """A target set before the widgets are created (scenario start) gets a tolerance area."""
        resman.set_parameter("tank-c-target", 1000)
        mocks = _build_widgets(resman)
        calls = {c.args[0]: c.kwargs for c in mocks["Tank"].call_args_list}
        assert calls["resman_tank_c"]["target"] == 1000
        assert resman._tolerance_tanks == {"a", "b", "c"}


class TestShowHide:
    @pytest.fixture
    def plugin(self, resman):
        resman.widgets = {
            f"resman_{name}": MagicMock() for name in ("task_title", "status_title", "status_foreground", "foreground")
        }
        with patch("plugins.abstractplugin.Window"):
            yield resman

    def test_hide_covers_the_pump_status(self, plugin):
        plugin.hide()
        assert plugin.visible is False
        plugin.get_widget("status_foreground").set_visibility.assert_called_once_with(True)
        plugin.get_widget("status_title").hide.assert_called_once()

    def test_show_uncovers_the_pump_status(self, plugin):
        plugin.visible = False
        plugin.show()
        assert plugin.visible is True
        plugin.get_widget("status_foreground").set_visibility.assert_called_with(False)

    def test_no_status_foreground_when_status_is_not_displayed(self, plugin):
        plugin.parameters["displaystatus"] = False
        plugin.hide()
        plugin.show()
        plugin.get_widget("status_foreground").set_visibility.assert_not_called()

    def test_status_widgets_not_created_yet(self, resman):
        resman.widgets = {"resman_task_title": MagicMock()}
        with patch("plugins.abstractplugin.Window"):
            resman.hide()
            resman.show()
        assert resman.visible is True


class TestComputeNextState:
    def test_no_step_while_paused(self, resman):
        resman.paused = True
        _step(resman)
        assert _tank(resman, "a")["level"] == 2500
        assert not hasattr(resman, "performance")

    def test_first_step_does_not_leak(self, mock_logger):
        r = Resman()
        r.paused = False
        _step(r)
        assert r.wait_before_leak == 0
        assert _tank(r, "a")["level"] == 2500
        _step(r)
        assert _tank(r, "a")["level"] == 2500 - 26  # 800 per minute, 2 s steps (truncated)

    def test_target_tanks_leak_the_others_do_not(self, resman):
        _step(resman, 3)
        levels = {k: t["level"] for k, t in resman.parameters["tank"].items()}
        assert levels == dict(a=2500 - 3 * 26, b=2500 - 3 * 26, c=1000, d=1000, e=3000, f=3000)

    def test_pump_on_transfers_its_flow(self, resman):
        _pump(resman, 1)["state"] = "on"  # c -> a, 800 per minute
        _pump(resman, 2)["state"] = "on"  # e -> a, 600 per minute, e is not depletable
        _step(resman)
        assert _tank(resman, "c")["level"] == 1000 - 26
        assert _tank(resman, "e")["level"] == 3000
        assert _tank(resman, "a")["level"] == 2500 - 26 + 26 + 20

    def test_empty_tank_stops_its_outgoing_pumps(self, resman):
        _tank(resman, "c")["level"] = 10
        _pump(resman, 1)["state"] = "on"
        _pump(resman, 5)["state"] = "on"  # e -> c: incoming, stays on
        _step(resman)
        assert _tank(resman, "c")["level"] == 20  # Gave its last 10, received 20
        _tank(resman, "c")["level"] = 0
        _pump(resman, 5)["state"] = "off"
        _step(resman)
        assert _pump(resman, 1)["state"] == "off"

    def test_full_tank_stops_its_incoming_pumps_but_not_failed_ones(self, resman):
        _tank(resman, "a")["level"] = 4000
        _tank(resman, "a")["lossperminute"] = 0
        _pump(resman, 2)["state"] = "on"
        _pump(resman, 8)["state"] = "failure"
        _step(resman)
        assert _pump(resman, 2)["state"] == "off"
        assert _pump(resman, 8)["state"] == "failure"
        assert _tank(resman, "a")["level"] == 4000  # Nothing more fits

    def test_failed_pump_transfers_nothing(self, resman):
        _pump(resman, 1)["state"] = "failure"
        _step(resman)
        assert _tank(resman, "c")["level"] == 1000

    def test_logs_deviation_and_tolerance(self, resman):
        _step(resman)
        perf = _last_performance(resman)
        assert perf["a_deviation"] == -26
        assert perf["a_in_tolerance"] is True
        assert perf["b_in_tolerance"] is True
        assert "c_deviation" not in perf
        resman.logger.log_performance.assert_any_call("resman", "a_deviation", -26)

    def test_response_time_logged_when_back_in_tolerance(self, resman):
        resman.parameters["tolerancecoloroutside"] = C["RED"]
        _tank(resman, "a")["level"] = 2000
        _step(resman)  # scenario_time 0: out of tolerance, response expected
        a = _tank(resman, "a")
        assert a["_is_in_tolerance"] is False
        assert a["_response_start"] == 0
        assert a["_tolerance_color"] == C["RED"]
        assert "a_response_time" not in resman.performance

        _step(resman)  # Still out: the response start is kept
        assert a["_response_start"] == 0

        a["level"] = 2500
        _step(resman)  # scenario_time 4
        assert resman.performance["a_response_time"] == [4000.0]
        assert a["_response_start"] is None
        assert a["_tolerance_color"] == C["BLACK"]
        assert resman.has_active_fault() is False

    def test_no_tolerance_radius_means_no_tolerance_check(self, resman):
        resman.parameters["toleranceradius"] = 0
        _step(resman)
        perf = _last_performance(resman)
        assert math.isnan(perf["a_in_tolerance"])
        assert perf["a_deviation"] == -26
        assert _tank(resman, "a")["_response_start"] is None
        assert resman.has_active_fault() is False


class TestTargetOnAnyTank:
    """The scenario may give a target to any tank (e.g. resman;tank-c-target;1000)."""

    def test_new_target_tank_logs_performance_like_a_and_b(self, resman):
        resman.set_parameter("tank-c-target", 1000)
        _step(resman)
        perf = _last_performance(resman)
        assert perf["c_in_tolerance"] is True
        assert perf["c_deviation"] == 0  # Tank c has no loss by default
        assert "d_deviation" not in perf
        assert len(resman.get_response_timers()) == 3

    def test_new_target_tank_response_time(self, resman):
        resman.set_parameter("tank-c-target", 1000)
        _tank(resman, "c")["level"] = 500
        _step(resman)
        c = _tank(resman, "c")
        assert c["_is_in_tolerance"] is False
        assert c["_response_start"] == 0
        assert resman.has_active_fault() is True
        c["level"] = 1000
        _step(resman)
        assert resman.performance["c_response_time"] == [2000.0]

    def test_target_set_before_widgets_is_refreshed(self, resman):
        resman.set_parameter("tank-c-target", 1000)
        _build_widgets(resman)
        _step(resman)
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            resman.refresh_widgets()
        c = _tank(resman, "c")["widget"]
        c.set_tolerance_radius.assert_called_once_with(250, 1000, 2000)
        c.set_tolerance_color.assert_called_once_with(C["BLACK"])

    def test_target_set_after_widgets_is_not_displayed(self, resman):
        """The tank widget has no tolerance area to update: logged, not displayed, no crash."""
        _build_widgets(resman)
        resman.set_parameter("tank-d-target", 1000)
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            resman.refresh_widgets()  # Refresh before any step
            _step(resman)
            resman.refresh_widgets()
        d = _tank(resman, "d")["widget"]
        d.set_fluid_level.assert_called_with(1000, 2000)
        d.set_tolerance_radius.assert_not_called()
        d.set_tolerance_color.assert_not_called()
        assert _last_performance(resman)["d_in_tolerance"] is True


class TestRefreshWidgets:
    @pytest.fixture
    def plugin(self, resman):
        _mock_widgets(resman)
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            yield resman

    def test_nothing_refreshed_when_hidden(self, resman):
        _mock_widgets(resman)
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=False):
            resman.refresh_widgets()
        _pump(resman, 1)["widget"].set_color.assert_not_called()
        _tank(resman, "a")["widget"].set_fluid_level.assert_not_called()

    def test_pump_color_and_flow_follow_state(self, plugin):
        _pump(plugin, 1)["state"] = "on"
        _pump(plugin, 2)["state"] = "failure"
        plugin.refresh_widgets()
        _pump(plugin, 1)["widget"].set_color.assert_called_once_with(C["GREEN"])
        _pump(plugin, 1)["statuswidget"].set_flow.assert_called_once_with("800")
        _pump(plugin, 2)["widget"].set_color.assert_called_once_with(C["RED"])
        _pump(plugin, 2)["statuswidget"].set_flow.assert_called_once_with("0")
        _pump(plugin, 3)["widget"].set_color.assert_called_once_with(C["WHITE"])
        _pump(plugin, 3)["statuswidget"].set_flow.assert_called_once_with("0")

    def test_hint_color_shown_unless_pump_failed(self, plugin):
        _pump(plugin, 1)["_hint_color"] = C["BLUE"]
        _pump(plugin, 2).update(_hint_color=C["BLUE"], state="failure")
        plugin.refresh_widgets()
        _pump(plugin, 1)["widget"].set_color.assert_called_once_with(C["BLUE"])
        _pump(plugin, 2)["widget"].set_color.assert_called_once_with(C["RED"])

    def test_tanks_show_level_label_and_tolerance(self, plugin):
        _tank(plugin, "a")["level"] = 1234
        _tank(plugin, "a")["_tolerance_color"] = C["RED"]
        plugin.refresh_widgets()
        a = _tank(plugin, "a")["widget"]
        a.set_fluid_level.assert_called_once_with(1234, 4000)
        a.set_fluid_label.assert_called_once_with("1234")
        a.set_tolerance_radius.assert_called_once_with(250, 2500, 4000)
        a.set_tolerance_color.assert_called_once_with(C["RED"])
        e = _tank(plugin, "e")["widget"]
        e.set_fluid_label.assert_called_once_with("")
        e.set_tolerance_radius.assert_not_called()
        e.set_tolerance_color.assert_not_called()

    def test_no_pump_status_when_not_displayed(self, resman):
        """With displaystatus False, pumps and tanks are refreshed without status widgets."""
        resman.parameters["displaystatus"] = False
        _build_widgets(resman)
        _pump(resman, 1)["state"] = "on"
        _tank(resman, "a")["level"] = 1234
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
            resman.refresh_widgets()
        _pump(resman, 1)["widget"].set_color.assert_called_once_with(C["GREEN"])
        _pump(resman, 2)["widget"].set_color.assert_called_once_with(C["WHITE"])
        _tank(resman, "a")["widget"].set_fluid_level.assert_called_once_with(1234, 4000)
        _tank(resman, "a")["widget"].set_tolerance_color.assert_called_once_with(C["BLACK"])


class TestKeys:
    def test_key_toggles_pump(self, resman, no_modal_dialog):
        resman.do_on_key("NUM_1", "press", False)
        assert _pump(resman, 1)["state"] == "on"
        resman.do_on_key("NUM_1", "press", False)
        assert _pump(resman, 1)["state"] == "off"

    def test_key_press_clears_hint(self, resman, no_modal_dialog):
        _pump(resman, 4)["_hint_color"] = C["BLUE"]
        resman.do_on_key("NUM_4", "press", False)
        assert _pump(resman, 4)["_hint_color"] is None

    def test_failed_pump_cannot_be_toggled(self, resman, no_modal_dialog):
        _pump(resman, 1).update(state="failure", _hint_color=C["BLUE"])
        resman.do_on_key("NUM_1", "press", False)
        assert _pump(resman, 1)["state"] == "failure"
        assert _pump(resman, 1)["_hint_color"] == C["BLUE"]

    def test_release_does_nothing(self, resman, no_modal_dialog):
        resman.do_on_key("NUM_1", "release", False)
        assert _pump(resman, 1)["state"] == "off"

    def test_unknown_key_is_ignored(self, resman, no_modal_dialog):
        resman.do_on_key("SPACE", "press", False)
        assert all(p["state"] == "off" for p in resman.parameters["pump"].values())

    def test_plugin_key_without_pump_is_ignored(self, resman, no_modal_dialog):
        """A key kept in the plugin keys but no longer mapped to a pump (key remapped)."""
        resman.set_parameter("pump-1-key", "A")
        resman.keys.add("NUM_1")
        resman.do_on_key("NUM_1", "press", False)
        assert _pump(resman, 1)["state"] == "off"
        resman.do_on_key("A", "press", False)
        assert _pump(resman, 1)["state"] == "on"

    def test_keys_ignored_when_they_cannot_be_executed(self, resman, no_modal_dialog):
        resman.can_execute_keys = False
        resman.do_on_key("NUM_1", "press", False)
        assert _pump(resman, 1)["state"] == "off"


class TestMouse:
    @pytest.fixture
    def plugin(self, resman, no_modal_dialog):
        _build_widgets(resman)
        return resman

    def _pump_center(self, plugin, number):
        return _pump(plugin, number)["_click_container"].get_center()

    def test_left_click_on_pump_toggles_it(self, plugin):
        x, y = self._pump_center(plugin, 3)
        plugin.do_on_mouse_press(x, y, mouse.LEFT)
        assert _pump(plugin, 3)["state"] == "on"
        plugin.logger.record_input.assert_called_once_with("mouse_key", "NUM_3", "press")
        plugin.do_on_mouse_press(x, y, mouse.LEFT)
        assert _pump(plugin, 3)["state"] == "off"

    def test_click_outside_pumps_does_nothing(self, plugin):
        plugin.do_on_mouse_press(-100, -100, mouse.LEFT)
        assert all(p["state"] == "off" for p in plugin.parameters["pump"].values())
        plugin.logger.record_input.assert_not_called()

    def test_other_buttons_are_ignored(self, plugin):
        x, y = self._pump_center(plugin, 3)
        plugin.do_on_mouse_press(x, y, mouse.RIGHT)
        assert _pump(plugin, 3)["state"] == "off"
        plugin.logger.record_input.assert_not_called()
