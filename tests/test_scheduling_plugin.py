"""Tests for plugins.scheduling - the plugin built by its constructor (plannings, widgets, timelines)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.constants import COLORS as C
from core.container import Container
from core.event import Event
from plugins.abstractplugin import AbstractPlugin
from plugins.scheduling import Scheduling

TASKS = ["sysmon", "track", "communications", "resman"]


def _scenario(*events, scheduling_start=True):
    """A scenario holding (time_sec, plugin, command...) events, starting with the scheduling start."""
    rows = [(0, "scheduling", "start"), *events] if scheduling_start else list(events)
    return SimpleNamespace(
        events=[Event(line, time_sec, plugin, list(command)) for line, (time_sec, plugin, *command) in enumerate(rows)]
    )


def _new_widget(fullname, container, **kwargs):
    return MagicMock(fullname=fullname, container=container, kwargs=kwargs)


def _create_widgets(scheduling):
    def base_create_widgets(plugin):
        plugin.task_container = Container("task", 0, 0, 400, 300)

    with (
        patch.object(AbstractPlugin, "create_widgets", base_create_widgets),
        patch("plugins.scheduling.Timeline", side_effect=_new_widget),
        patch("plugins.scheduling.Simpletext", side_effect=_new_widget),
        patch("plugins.scheduling.Schedule", side_effect=_new_widget),
    ):
        scheduling.create_widgets()


@pytest.fixture
def scheduling(mock_logger):
    """A visible Scheduling plugin at the scenario start."""
    s = Scheduling()
    s.paused = False
    s.visible = True
    s.scenario_time = 0
    s.joystick = None
    return s


@pytest.fixture
def with_widgets(scheduling):
    _create_widgets(scheduling)
    return scheduling


def _refresh(scheduling):
    with patch.object(AbstractPlugin, "refresh_widgets", return_value=True):
        scheduling.refresh_widgets()


def _segments(scheduling, task, time_mode):
    """Relative segments last sent to the timeline of a task for a mode (running or manual)."""
    widget = scheduling.widgets[f"scheduling_{task}"]
    calls = [c for c in widget.map_segment.call_args_list if c.args[0] == time_mode]
    return calls[-1].args[1]


class TestInit:
    def test_default_parameters(self, scheduling):
        p = scheduling.parameters
        assert p["title"] == "Scheduling"
        assert p["taskplacement"] == "topright"
        assert p["taskupdatetime"] == 1000
        assert p["minduration"] == 8
        assert p["displaychronometer"] is True
        assert p["reversechronometer"] is False
        assert p["displayedplugins"] == TASKS
        assert p["labels"] == ["S", "T", "C", "R"]

    def test_empty_planning_for_each_displayed_task(self, scheduling):
        assert scheduling.planning == {t: {"running": [], "manual": []} for t in TASKS}
        assert scheduling.maximum_time_sec is None

    def test_segment_colors(self, scheduling):
        assert scheduling.colors == {"line": C["GREY"], "running": C["RED"], "manual": C["GREEN"]}

    def test_list_parameters_are_checked_against_allowed_values(self, scheduling):
        _validator, allowed = scheduling.validation_dict["displayedplugins"]
        assert sorted(allowed) == sorted(TASKS)
        assert scheduling.validation_dict["labels"][1] == ["S", "T", "C", "R"]


class TestCreateWidgets:
    def test_timeline_on_the_left_with_the_displayed_duration(self, with_widgets):
        timeline = with_widgets.widgets["scheduling_timeline"]
        c = timeline.container
        assert (c.l, c.b, c.w, c.h) == pytest.approx((40, 60, 68, 210))
        assert timeline.kwargs == {"max_time_minute": 8}

    def test_chronometer_text_at_the_bottom(self, with_widgets):
        chrono = with_widgets.widgets["scheduling_elapsed_time"]
        assert chrono.container is with_widgets.task_container
        assert chrono.kwargs == {"text": "Elapsed time \t 00:00:00", "y": 0.05}

    def test_one_labelled_schedule_per_task_side_by_side(self, with_widgets):
        schedules = [with_widgets.widgets[f"scheduling_{t}"] for t in TASKS]
        assert [s.kwargs["label"] for s in schedules] == ["S", "T", "C", "R"]
        assert [s.container.l for s in schedules] == pytest.approx([120, 180, 240, 300])
        assert all(s.container.w == pytest.approx(68) for s in schedules)
        assert [s.container.name for s in schedules] == [f"schedule_{t}" for t in TASKS]


class TestOnScenarioLoaded:
    def test_maximum_time_is_the_last_event(self, scheduling):
        scheduling.on_scenario_loaded(_scenario((60, "track", "start"), (480, "track", "stop")))
        assert scheduling.maximum_time_sec == 480

    def test_start_stop_pairs_become_running_segments(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (120, "track", "stop"),
                (200, "track", "start"),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 120, 200, 300]

    def test_without_automation_the_whole_run_is_manual(self, scheduling):
        scheduling.on_scenario_loaded(_scenario((10, "sysmon", "start"), (90, "sysmon", "stop")))
        assert scheduling.planning["sysmon"]["manual"] == [10, 90]

    def test_pause_and_resume_split_the_running_segment(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "resman", "start"),
                (100, "resman", "pause"),
                (150, "resman", "resume"),
                (400, "resman", "stop"),
            )
        )
        assert scheduling.planning["resman"]["running"] == [0, 100, 150, 400]

    def test_repeated_commands_keep_the_earliest(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (50, "track", "start"),
                (100, "track", "stop"),
                (130, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 100]

    def test_unfinished_run_is_not_displayed(self, scheduling):
        scheduling.on_scenario_loaded(_scenario((0, "track", "start"), (100, "track", "stop"), (200, "track", "start")))
        assert scheduling.planning["track"]["running"] == [0, 100]

    def test_tasks_without_events_have_empty_plannings(self, scheduling):
        scheduling.on_scenario_loaded(_scenario((0, "track", "start"), (100, "track", "stop")))
        for task in ["sysmon", "communications", "resman"]:
            assert scheduling.planning[task] == {"running": [], "manual": []}

    def test_parameter_events_are_not_segments(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (30, "track", "targetproportion", 0.5),
                (100, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 100]

    def test_automation_period_is_cut_out_of_the_manual_segment(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (60, "track", "automaticsolver", True),
                (120, "track", "automaticsolver", False),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 300]
        assert scheduling.planning["track"]["manual"] == [0, 60, 120, 300]

    def test_automation_until_the_end_leaves_a_single_manual_segment(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (60, "track", "automaticsolver", True),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [0, 60]

    def test_leading_manual_switches_are_ignored(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (0, "track", "automaticsolver", False),
                (60, "track", "automaticsolver", True),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [0, 60]

    def test_only_manual_switches_leave_the_whole_run_manual(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (0, "track", "automaticsolver", False),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 300]
        assert scheduling.planning["track"]["manual"] == [0, 300]

    def test_automation_of_a_task_never_stopped_gives_no_manual_segment(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (60, "track", "automaticsolver", True),
                (480, "sysmon", "stop"),
            )
        )
        assert scheduling.planning["track"] == {"running": [], "manual": []}

    def test_scenario_without_scheduling_start_is_loaded(self, scheduling):
        """Only scheduling parameter events: no scheduling start is required."""
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "scheduling", "minduration", 5),
                (0, "track", "start"),
                (100, "track", "stop"),
                scheduling_start=False,
            )
        )
        assert scheduling.planning["track"] == {"running": [0, 100], "manual": [0, 100]}

    def test_automation_is_cut_out_of_each_run(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (50, "track", "automaticsolver", True),
                (100, "track", "stop"),
                (200, "track", "start"),
                (250, "track", "automaticsolver", False),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["running"] == [0, 100, 200, 300]
        assert scheduling.planning["track"]["manual"] == [0, 50, 250, 300]

    def test_repeated_automation_switches_are_ignored(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (50, "track", "automaticsolver", True),
                (80, "track", "automaticsolver", True),
                (120, "track", "automaticsolver", False),
                (150, "track", "automaticsolver", False),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [0, 50, 120, 300]

    def test_automation_starting_before_a_run(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "automaticsolver", True),
                (10, "track", "start"),
                (60, "track", "automaticsolver", False),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [60, 300]

    def test_automation_never_switched_off_covers_the_later_runs(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (100, "track", "stop"),
                (150, "track", "automaticsolver", True),
                (200, "track", "start"),
                (300, "track", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [0, 100]

    def test_automation_inside_a_paused_run(self, scheduling):
        """Automation covering a pause leaves manual segments only where the task runs."""
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "resman", "start"),
                (80, "resman", "automaticsolver", True),
                (100, "resman", "pause"),
                (150, "resman", "resume"),
                (170, "resman", "automaticsolver", False),
                (400, "resman", "stop"),
            )
        )
        assert scheduling.planning["resman"]["manual"] == [0, 80, 170, 400]

    def test_manual_planning_is_independent_per_task(self, scheduling):
        scheduling.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (0, "resman", "start"),
                (60, "resman", "automaticsolver", True),
                (300, "track", "stop"),
                (300, "resman", "stop"),
            )
        )
        assert scheduling.planning["track"]["manual"] == [0, 300]
        assert scheduling.planning["resman"]["manual"] == [0, 60]


class TestRefreshWidgets:
    @pytest.fixture
    def loaded(self, with_widgets):
        with_widgets.on_scenario_loaded(
            _scenario(
                (0, "track", "start"),
                (0, "sysmon", "start"),
                (60, "sysmon", "automaticsolver", True),
                (120, "sysmon", "automaticsolver", False),
                (600, "track", "stop"),
                (600, "sysmon", "stop"),
                (700, "resman", "start"),
                (720, "resman", "stop"),
            )
        )
        return with_widgets

    def test_timeline_and_chronometer_follow_the_scenario_time(self, loaded):
        loaded.scenario_time = 65.4
        loaded.parameters["minduration"] = 5
        _refresh(loaded)
        loaded.widgets["scheduling_timeline"].set_max_time.assert_called_with(5)
        loaded.widgets["scheduling_elapsed_time"].set_text.assert_called_with("Elapsed time \t 00:01:05")

    def test_reversed_chronometer_counts_down_to_the_last_event(self, loaded):
        loaded.parameters["reversechronometer"] = True
        loaded.scenario_time = 20
        _refresh(loaded)
        loaded.widgets["scheduling_elapsed_time"].set_text.assert_called_with("Remaining time \t 00:11:40")

    def test_hidden_chronometer_shows_no_text(self, loaded):
        loaded.parameters["displaychronometer"] = False
        _refresh(loaded)
        loaded.widgets["scheduling_elapsed_time"].set_text.assert_called_with("")

    def test_nothing_is_refreshed_when_hidden(self, loaded):
        with patch.object(AbstractPlugin, "refresh_widgets", return_value=False):
            loaded.refresh_widgets()
        loaded.widgets["scheduling_timeline"].set_max_time.assert_not_called()
        loaded.widgets["scheduling_track"].map_segment.assert_not_called()

    def test_segments_are_clipped_to_the_displayed_duration(self, loaded):
        _refresh(loaded)
        # 8 minutes are displayed: the 0-600 s run is cut at 480 s
        assert _segments(loaded, "track", "running") == [[0, 480]]
        loaded.widgets["scheduling_track"].map_segment.assert_any_call("running", [[0, 480]], 480, C["RED"])

    def test_segments_scroll_with_the_elapsed_time(self, loaded):
        loaded.scenario_time = 400
        _refresh(loaded)
        # 700-720 s is now 300-320 s ahead; 0-600 s is running for 200 s more
        assert _segments(loaded, "resman", "running") == [[300, 320]]
        assert _segments(loaded, "track", "running") == [[0, 200]]

    def test_expired_segments_are_removed(self, loaded):
        loaded.scenario_time = 100
        _refresh(loaded)
        # The 0-60 s manual segment is over, the 120-600 s one starts in 20 s
        assert _segments(loaded, "sysmon", "manual") == [[20, 480]]
        loaded.scenario_time = 130
        _refresh(loaded)
        assert _segments(loaded, "sysmon", "manual") == [[0, 470]]

    def test_every_segment_is_redrawn_at_each_refresh(self, loaded):
        _refresh(loaded)
        _refresh(loaded)
        assert loaded.widgets["scheduling_track"].map_segment.call_count == 4
        assert loaded.relative_planning["communications"] == {"running": [], "manual": []}

    def test_top_bound_turns_green_during_a_manual_segment(self, loaded):
        loaded.scenario_time = 30
        _refresh(loaded)
        loaded.widgets["scheduling_sysmon"].set_top_bound_color.assert_called_once_with(C["GREEN"])

    def test_top_bound_keeps_the_line_color_during_automation(self, loaded):
        loaded.scenario_time = 90
        _refresh(loaded)
        loaded.widgets["scheduling_sysmon"].set_top_bound_color.assert_called_once_with(C["GREY"])

    def test_top_bound_is_reset_after_a_manual_segment(self, loaded):
        widget = loaded.widgets["scheduling_sysmon"]
        loaded.scenario_time = 30
        _refresh(loaded)
        loaded.scenario_time = 60
        _refresh(loaded)
        assert widget.set_top_bound_color.call_args_list[-1].args == (C["GREY"],)
        loaded.scenario_time = 600
        _refresh(loaded)
        assert widget.set_top_bound_color.call_args_list[-1].args == (C["GREY"],)

    def test_segments_beyond_the_displayed_window_are_not_sent(self, loaded):
        _refresh(loaded)
        # At 0 s with 8 minutes displayed, the 700-720 s run is not visible yet
        assert _segments(loaded, "resman", "running") == []
        assert _segments(loaded, "resman", "manual") == []

    def test_segment_straddling_the_window_end_is_clipped(self, loaded):
        loaded.scenario_time = 230
        _refresh(loaded)
        # 700-720 s is 470-490 s ahead: only its first 10 s are displayed
        assert _segments(loaded, "resman", "running") == [[470, 480]]

    def test_displayed_timelines_are_shown(self, loaded):
        _refresh(loaded)
        for task in TASKS:
            loaded.widgets[f"scheduling_{task}"].show.assert_called()
            loaded.widgets[f"scheduling_{task}"].hide.assert_not_called()

    def test_timelines_of_undisplayed_tasks_are_hidden(self, loaded):
        loaded.parameters["displayedplugins"] = ["sysmon", "track"]
        _refresh(loaded)
        for task in ["communications", "resman"]:
            widget = loaded.widgets[f"scheduling_{task}"]
            widget.hide.assert_called_once()
            widget.map_segment.assert_not_called()
        assert set(loaded.relative_planning) == {"sysmon", "track"}
