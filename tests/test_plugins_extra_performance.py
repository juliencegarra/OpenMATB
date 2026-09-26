"""Tests for plugins.performance - the plugin built by its constructor (global level computed and displayed)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.constants import COLORS as C
from core.container import Container
from plugins.performance import Performance


def _widget_class():
    """A mock widget class whose instances remember their name, container and keyword arguments."""

    def build(name, container, **kwargs):
        w = MagicMock()
        w.fullname, w.container, w.kwargs = name, container, kwargs
        return w

    return MagicMock(side_effect=build)


@pytest.fixture
def window():
    with patch("plugins.abstractplugin.Window") as mock_win:
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        mock_win.MainWindow.get_container.side_effect = lambda placement: Container(placement, 1400, 540, 520, 540)
        yield mock_win


@pytest.fixture
def widget_classes(window):
    with (
        patch("plugins.abstractplugin.Frame", _widget_class()),
        patch("plugins.abstractplugin.Simpletext", _widget_class()),
        patch("plugins.performance.Performancescale", _widget_class()) as scale_cls,
    ):
        yield scale_cls


def _task(taskupdatetime=50, **performance):
    return SimpleNamespace(performance=performance, parameters={"taskupdatetime": taskupdatetime})


@pytest.fixture
def make_perf(mock_logger, widget_classes):
    """A started Performance plugin watching the given scenario plugins."""

    def make(plugins=None, **parameters):
        perf = Performance()
        perf.parameters.update(parameters)
        perf.on_scenario_loaded(SimpleNamespace(plugins=plugins or {}))
        perf.start()
        return perf

    return make


def _bar(perf):
    return perf.widgets["performance_bar"]


class TestInit:
    def test_default_parameters(self, mock_logger):
        perf = Performance()
        p = perf.parameters
        assert perf.label == "Performance"
        assert p["taskplacement"] == "topright"
        assert p["taskupdatetime"] == 50
        assert (p["levelmin"], p["levelmax"], p["ticknumber"], p["criticallevel"]) == (0, 100, 5, 20)
        assert p["shadowundercritical"] is True
        assert (p["defaultcolor"], p["criticalcolor"]) == (C["GREEN"], C["RED"])
        assert perf.current_level == perf.displayed_level == 100
        assert perf.displayed_color == C["GREEN"]
        assert perf.plugins is None
        assert perf.under_critical is None

    def test_parameters_are_validated(self, mock_logger):
        validation_dict = Performance().validation_dict
        assert set(validation_dict) >= {"levelmin", "levelmax", "ticknumber", "criticallevel", "criticalcolor"}

    def test_scenario_plugins_are_kept(self, mock_logger):
        perf = Performance()
        plugins = {"track": _task()}
        perf.on_scenario_loaded(SimpleNamespace(plugins=plugins))
        assert perf.plugins is plugins


class TestWidgets:
    def test_bar_uses_the_scale_parameters(self, make_perf, widget_classes):
        perf = make_perf(levelmin=10, levelmax=90, ticknumber=9)
        kwargs = _bar(perf).kwargs
        assert (kwargs["level_min"], kwargs["level_max"], kwargs["tick_number"]) == (10, 90, 9)
        assert kwargs["color"] == C["GREEN"]

    def test_bar_is_placed_in_the_task_area(self, make_perf):
        perf = make_perf()
        bar, task = _bar(perf).container, perf.task_container
        assert bar.w == pytest.approx(task.w * 0.35)
        assert bar.h == pytest.approx(task.h * 0.8)
        assert task.l <= bar.l and bar.l + bar.w <= task.l + task.w
        assert task.b <= bar.b and bar.b + bar.h <= task.b + task.h


class TestDisplayedLevel:
    def test_full_level_without_measures(self, make_perf):
        perf = make_perf({"track": _task(cursor_in_target=[1] * 10), "scheduling": SimpleNamespace()})
        perf.update(1)
        bar = _bar(perf)
        bar.set_performance_level.assert_called_with(100)
        bar.set_performance_color.assert_called_with(C["GREEN"])
        bar.set_tick_number.assert_called_with(5)
        bar.set_level_min.assert_called_with(0)
        bar.set_level_max.assert_called_with(100)

    def test_worst_task_level_is_displayed(self, make_perf):
        track = _task(cursor_in_target=[1] * 50 + [0] * 50)  # Last 5 s (100 steps): half in target
        resman = _task(a_in_tolerance=[1] * 100, b_in_tolerance=[1] * 25 + [0] * 75)
        perf = make_perf({"track": track, "resman": resman})
        perf.update(1)
        assert perf.performance_levels == {"track": 0.5, "resman": 0.625}
        _bar(perf).set_performance_level.assert_called_with(50)
        _bar(perf).set_performance_color.assert_called_with(C["GREEN"])

    def test_level_under_critical_is_shadowed(self, make_perf):
        comms = _task(correct_radio=[True, False, False, False], response_deviation=[0.0, 0.0, 0.0, 0.0])
        perf = make_perf({"communications": comms})
        perf.update(1)
        assert perf.current_level == 25
        comms.performance["correct_radio"][-1] = False
        comms.performance["correct_radio"][0] = False
        perf.update(2)
        assert perf.current_level == 0
        assert perf.under_critical is True
        _bar(perf).set_performance_level.assert_called_with(20)
        _bar(perf).set_performance_color.assert_called_with(C["RED"])

    def test_level_under_critical_without_shadow(self, make_perf):
        sysmon = _task(signal_detection=["MISS", "HIT", "MISS", "MISS"])
        perf = make_perf({"sysmon": sysmon}, shadowundercritical=False, criticallevel=30)
        perf.update(1)
        _bar(perf).set_performance_level.assert_called_with(25)
        _bar(perf).set_performance_color.assert_called_with(C["RED"])

    def test_changed_scale_parameters_are_displayed(self, make_perf):
        perf = make_perf()
        perf.set_parameter("ticknumber", 11)
        perf.set_parameter("levelmax", 50)
        perf.update(1)
        _bar(perf).set_tick_number.assert_called_with(11)
        _bar(perf).set_level_max.assert_called_with(50)
        _bar(perf).set_performance_level.assert_called_with(50)

    def test_nothing_is_computed_before_the_next_step(self, make_perf):
        perf = make_perf({"sysmon": _task(signal_detection=["MISS"] * 4)})
        perf.update(1)
        perf.plugins["sysmon"].performance["signal_detection"] = ["HIT"] * 4
        perf.update(1.01)  # Less than taskupdatetime (50 ms) later
        assert perf.current_level == 0

    def test_hidden_plugin_does_not_refresh_its_bar(self, make_perf):
        perf = make_perf()
        perf.hide()
        _bar(perf).reset_mock()
        perf.update(1)
        _bar(perf).set_performance_level.assert_not_called()

    def test_sysmon_level_uses_the_four_last_events(self, make_perf):
        """Six hits must give 100 % (not 150 %), and four recent misses must give 0 %."""
        perf = make_perf({"sysmon": _task(signal_detection=["HIT"] * 6)})
        perf.update(1)
        assert perf.current_level == 100
        perf.plugins["sysmon"].performance["signal_detection"] += ["MISS"] * 4
        perf.update(2)
        assert perf.current_level == 0
