# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any, Callable, Optional

from core import validation
from core.constants import COLORS as C
from core.widgets import Performancescale
from plugins.abstractplugin import AbstractPlugin


class Performance(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "topright", taskupdatetime: int = 50) -> None:
        super().__init__(_("Performance"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "levelmin": validation.is_positive_integer,
            "levelmax": validation.is_positive_integer,
            "ticknumber": validation.is_positive_integer,
            "criticallevel": validation.is_positive_integer,
            "shadowundercritical": validation.is_boolean,
            "defaultcolor": validation.is_color,
            "criticalcolor": validation.is_color,
        }

        new_par: dict[str, Any] = dict(
            levelmin=0,
            levelmax=100,
            ticknumber=5,
            criticallevel=20,
            shadowundercritical=True,
            defaultcolor=C["GREEN"],
            criticalcolor=C["RED"],
        )
        self.parameters.update(new_par)

        self.current_level: int | float = int(self.parameters["levelmax"])
        self.displayed_level: int | float = int(self.parameters["levelmax"])
        self.displayed_color: tuple[int, ...] = self.parameters["defaultcolor"]
        self.plugins: Optional[dict[str, Any]] = None
        self.performance_levels: dict[str, float] = dict()
        self.under_critical: Optional[bool] = None

    def on_scenario_loaded(self, scenario: Any) -> None:
        self.plugins = scenario.plugins

    def create_widgets(self) -> None:
        super().create_widgets()

        # Compute performance widget container
        widget_container = self.task_container.reduce_and_translate(0.35, 0.8, 0.5, 0.5)
        self.add_widget(
            "bar",
            Performancescale,
            container=widget_container,
            level_min=self.parameters["levelmin"],
            level_max=self.parameters["levelmax"],
            tick_number=self.parameters["ticknumber"],
            color=C["GREEN"],
        )

    def compute_next_plugin_state(self) -> None:
        if not super().compute_next_plugin_state():
            return

        # Below is a specific policy to compute the global performance level
        # Each task as its own performance level
        # : the global level is simply the worst performance level encountered
        # Other various global performance calculations could be used

        for p, plugin in self.plugins.items():
            if hasattr(plugin, "performance") and len(plugin.performance) > 0:
                # System monitoring
                if p == "sysmon":
                    # Only considering hits and missed for system monitoring
                    # HIT = 1   |   MISS = 0
                    # Compute average of 4 last signal detection events
                    perf_list: list[str] = [p for p in plugin.performance["signal_detection"] if p in ["HIT", "FA", "MISS"]]
                    if len(perf_list) >= 4:
                        self.performance_levels[p] = sum([int(p == "HIT") for p in perf_list]) / 4

                # Tracking
                elif p == "track":
                    # Time proportion spent in target for the last 5 seconds
                    frames_n: int = int(5000 / plugin.parameters["taskupdatetime"])
                    if len(plugin.performance["cursor_in_target"]) >= frames_n:
                        perf_list_track: list[int] = plugin.performance["cursor_in_target"][-frames_n:]
                        self.performance_levels[p] = sum(perf_list_track) / len(perf_list_track)

                # Resman
                elif p == "resman":
                    # Time proportion spent in target for the last 5 seconds
                    frames_n_res: int = int(5000 / plugin.parameters["taskupdatetime"])
                    if (
                        len(plugin.performance["a_in_tolerance"]) >= frames_n_res
                        and len(plugin.performance["b_in_tolerance"]) >= frames_n_res
                    ):
                        a_perf_list: list[int] = plugin.performance["a_in_tolerance"][-frames_n_res:]
                        b_perf_list: list[int] = plugin.performance["b_in_tolerance"][-frames_n_res:]

                        perf: float = (sum(a_perf_list) / len(a_perf_list)) + (sum(b_perf_list) / len(b_perf_list))

                        self.performance_levels[p] = perf / 2

                #       Communications
                elif p == "communications":
                    if len(plugin.performance["correct_radio"]) >= 4:
                        perf_radio: list[bool] = plugin.performance["correct_radio"][-4:]
                        perf_freq: list[float] = plugin.performance["response_deviation"][-4:]
                        all_good: list[bool] = [r and round(f, 1) == 0 for r, f in zip(perf_radio, perf_freq)]

                        self.performance_levels[p] = sum(all_good) / len(all_good)

        if len(self.performance_levels) > 0:
            self.current_level = min([p for _, p in self.performance_levels.items()]) * 100
        else:
            self.current_level = self.parameters["levelmax"]

        self.under_critical = self.current_level < self.parameters["criticallevel"]
        self.displayed_color = (
            self.parameters["defaultcolor"] if not self.under_critical else self.parameters["criticalcolor"]
        )

        # If must hide what happens when the level is below the critical performance
        # Stick displayed level to critical level
        if self.under_critical is True and self.parameters["shadowundercritical"]:
            self.displayed_level = self.parameters["criticallevel"]
        else:
            self.displayed_level = self.current_level

    def refresh_widgets(self) -> None:
        if not super().refresh_widgets():
            return
        self.widgets["performance_bar"].set_tick_number(self.parameters["ticknumber"])
        self.widgets["performance_bar"].set_level_min(self.parameters["levelmin"])
        self.widgets["performance_bar"].set_level_max(self.parameters["levelmax"])
        self.widgets["performance_bar"].set_performance_level(self.displayed_level)
        self.widgets["performance_bar"].set_performance_color(self.displayed_color)
