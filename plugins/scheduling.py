# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from time import gmtime, strftime
from typing import Any, Callable

from core import validation
from core.constants import COLORS as C
from core.container import Container
from core.widgets import Schedule, Simpletext, Timeline
from plugins.abstractplugin import AbstractPlugin


class Scheduling(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "topright", taskupdatetime: int = 1000) -> None:
        super().__init__(_("Scheduling"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any] | tuple[Callable[..., Any], list[str]]] = {
            "taskfeedback-overdue-active": validation.is_boolean,
            "taskfeedback-overdue-color": validation.is_color,
            "taskfeedback-overdue-delayms": validation.is_natural_integer,
            "taskfeedback-overdue-blinkdurationms": validation.is_natural_integer,
            "minduration": validation.is_positive_integer,
            "displaychronometer": validation.is_boolean,
            "reversechronometer": validation.is_boolean,
            "displayedplugins": (validation.is_in_list, ["sysmon", "track", "resman", "communications"]),
            "labels": (validation.is_in_list, ["S", "T", "C", "R"]),
        }

        self.parameters.update(
            dict(
                minduration=8,
                displaychronometer=True,
                reversechronometer=False,
                displayedplugins=["sysmon", "track", "communications", "resman"],
                labels=["S", "T", "C", "R"],
            )
        )

        for i, _p in enumerate(self.parameters["displayedplugins"]):
            self.parameters["displayedplugins"][i] = _(self.parameters["displayedplugins"][i])

        # Planning of events is set by the scheduler [set_planning(events)] because it needs
        # to know events
        self.planning: dict[str, dict[str, list[int]]] = {
            p: {"running": list(), "manual": list()} for p in self.parameters["displayedplugins"]
        }
        self.colors: dict[str, tuple[int, ...]] = dict(line=C["GREY"], running=C["RED"], manual=C["GREEN"])
        self.maximum_time_sec: int | None = None

    def create_widgets(self) -> None:
        super().create_widgets()

        timeline_container: Container = Container(
            "timeline",
            self.task_container.l + self.task_container.w * 0.1,
            self.task_container.b + self.task_container.h * 0.20,
            self.task_container.w * 0.17,
            self.task_container.h * 0.7,
        )

        self.add_widget(
            "timeline", Timeline, container=timeline_container, max_time_minute=self.parameters["minduration"]
        )

        self.add_widget("elapsed_time", Simpletext, container=self.task_container, text=self.get_chrono_str(), y=0.05)

        for p, name in enumerate(self.planning.keys()):
            planning_container: Container = Container(
                f"schedule_{name}",
                self.task_container.l + self.task_container.w * (0.15 + 0.15 * (p + 1)),
                self.task_container.b + self.task_container.h * 0.20,
                self.task_container.w * 0.17,
                self.task_container.h * 0.7,
            )
            self.add_widget(name, Schedule, container=planning_container, label=self.parameters["labels"][p])

    def refresh_widgets(self) -> None:
        if not super().refresh_widgets():
            return
        # This plugin can not be paused for now.
        # When visible, it is just synchronized with the elapsed time
        self.widgets["scheduling_timeline"].set_max_time(self.parameters["minduration"])
        self.widgets[f"{self.alias}_elapsed_time"].set_text(self.get_chrono_str())
        self.update_relative_plannings()

    def update_relative_plannings(self) -> None:
        # For each displayed plugin, and each mode, send the relative time points to the widget
        # Time points are relative to the elapsed time and the maximum displayed duration (minutes)

        self.relative_planning: dict[str, dict[str, list[list[int]]]] = {
            p: {"running": list(), "manual": list()} for p in self.parameters["displayedplugins"]
        }

        for plugin_name in self.planning:
            wdgt_adress: str = f"{self.alias}_{plugin_name}"
            if plugin_name in self.parameters["displayedplugins"]:
                # See if we should show the plugin timeline
                self.widgets[wdgt_adress].show()

                elapsed: int = self.get_elapsed_time_sec()
                # Limit the time interval with relative 0 and displayed duration (minutes)
                max_sec: int = self.parameters["minduration"] * 60

                for time_mode, abs_time_pts in self.planning[plugin_name].items():
                    rel: list[list[int]] = self.relative_planning[plugin_name][time_mode]

                    # For each time pair (start, end), take elapsed time into account
                    for start, end in self.grouped(abs_time_pts, 2):
                        rel_start: int = max(start - elapsed, 0)
                        rel_end: int = min(end - elapsed, max_sec)

                        # Do not map segments that have expired or start beyond the displayed window
                        if rel_start < rel_end:
                            rel.append([rel_start, rel_end])

                    color: tuple[int, ...] = self.colors[time_mode]
                    self.widgets[wdgt_adress].map_segment(time_mode, rel, max_sec, color)

                # The top bound is green during a manual segment, and back to the line color otherwise
                manual_pts: list[int] = self.planning[plugin_name]["manual"]
                is_manual: bool = any(start <= elapsed < end for start, end in self.grouped(manual_pts, 2))
                bound_color: tuple[int, ...] = self.colors["manual"] if is_manual else self.colors["line"]
                self.widgets[wdgt_adress].set_top_bound_color(bound_color)

            # See if we should hide the plugin timeline
            else:
                self.widgets[wdgt_adress].hide()

    def get_chrono_str(self) -> str:
        if self.parameters["displaychronometer"]:
            if self.parameters["reversechronometer"]:
                return self.get_remaining_time_string()
            else:
                return self.get_elapsed_time_string()
        else:
            return ""

    def get_elapsed_time_sec(self) -> int:
        return int(self.scenario_time)

    def get_elapsed_time_string(self) -> str:
        str_time: str = strftime("%H:%M:%S", gmtime(self.get_elapsed_time_sec()))
        return _("Elapsed time \t %s") % str_time

    def get_remaining_time_sec(self) -> int:
        return int(self.maximum_time_sec) - int(self.scenario_time)

    def get_remaining_time_string(self) -> str:
        str_time: str = strftime("%H:%M:%S", gmtime(self.get_remaining_time_sec()))
        return _("Remaining time \t %s") % str_time

    def on_scenario_loaded(self, scenario: Any) -> None:
        events: list[Any] = scenario.events
        start_stop_labels: list[str] = ["start", "stop", "resume", "pause"]
        auto_labels: list[str] = ["automaticsolver"]

        # Retrieve last event time_sec for reversed chronometer
        self.maximum_time_sec = events[-1].time_sec

        # For each task...
        for task in self.planning:
            # 1. ...compute running segments
            start_stop_events: list[tuple[int, str]] = [
                (e.time_sec, e.command[0]) for e in events if e.plugin == task and e.command[0] in start_stop_labels
            ]

            # Remove redundant consecutive events (e.g. stop -> stop), keep the earliest
            if start_stop_events:
                filtered: list[tuple[int, str]] = [start_stop_events[0]]
                for evt in start_stop_events[1:]:
                    if evt[1] != filtered[-1][1]:
                        filtered.append(evt)
                start_stop_events = filtered

            for event in start_stop_events:
                self.planning[task]["running"].append(event[0])
            if len(self.planning[task]["running"]) % 2 == 1:
                del self.planning[task]["running"][-1]

            # 2. ...retrieve automation switches
            auto_events: list[tuple[int, Any]] = [
                (e.time_sec, e.command[1]) for e in events if e.plugin == task and e.command[0] in auto_labels
            ]

            # 3. ...compute manual segments: running segments minus automated periods
            self.planning[task]["manual"] = self.subtract_periods(
                self.planning[task]["running"], self.get_automated_periods(auto_events)
            )

    @staticmethod
    def get_automated_periods(auto_events: list[tuple[int, Any]]) -> list[tuple[float, float]]:
        # Automation is off by default. Only state changes matter (e.g. True -> True is ignored)
        # An automation that is never switched off lasts until the end of the scenario
        periods: list[tuple[float, float]] = list()
        auto_start: float | None = None
        for time_sec, value in auto_events:
            if value is True and auto_start is None:
                auto_start = time_sec
            elif value is False and auto_start is not None:
                periods.append((auto_start, time_sec))
                auto_start = None
        if auto_start is not None:
            periods.append((auto_start, float("inf")))
        return periods

    def subtract_periods(self, time_pts: list[int], periods: list[tuple[float, float]]) -> list[int]:
        # Remove the periods from each (start, end) segment, return the remaining flat time points
        result: list[int] = list()
        for start, end in self.grouped(time_pts, 2):
            cursor = start
            for p_start, p_end in periods:
                if p_end <= cursor or p_start >= end:
                    continue
                if p_start > cursor:
                    result.extend([cursor, p_start])
                cursor = max(cursor, p_end)
                if cursor >= end:
                    break
            if cursor < end:
                result.extend([cursor, end])
        return result
