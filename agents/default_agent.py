# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from agents.abstract_agent import AbstractAgent


class DefaultAgent(AbstractAgent):
    """Reproduces the original inline automaticsolver behavior via input injection."""

    def __init__(self) -> None:
        super().__init__(name="default", automode_string="AUTO")

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias
        if alias == "resman":
            self._update_resman(plugin)
        elif alias == "track":
            self._update_track(plugin)
        elif alias == "communications":
            self._update_communications(plugin)
        elif alias == "sysmon":
            self._update_sysmon(plugin)

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        return {"delay": plugin.parameters["alerttimeout"]}

    def _update_sysmon(self, plugin: Any) -> None:
        delay = plugin.parameters["automaticsolverdelay"]
        for gauge in plugin.get_gauges_on_failure():
            if gauge["_response_start"] is not None and (plugin.scenario_time - gauge["_response_start"]) * 1000 >= delay:
                self.send_key(plugin, gauge["key"])

    def _update_resman(self, plugin: Any) -> None:
        if plugin.wait_before_leak > 0:
            return

        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        for _pump_n, this_pump in {p: v for p, v in pumps.items() if v["state"] != "failure"}.items():
            from_tank = tanks[this_pump["_fromtank"]]
            to_tank = tanks[this_pump["_totank"]]

            desired = self._compute_desired_pump_state(this_pump, from_tank, to_tank)
            if desired is not None and desired != this_pump["state"]:
                self.send_key(plugin, this_pump["key"])  # Toggle pump

    @staticmethod
    def _compute_desired_pump_state(
        pump: dict[str, Any], from_tank: dict[str, Any], to_tank: dict[str, Any],
        threshold_noise: float = 0,
    ) -> str | None:
        """Decide the desired pump state given tank levels and heuristics.
        Returns 'on', 'off', or None (no opinion)."""
        desired: str | None = None

        # Heuristic 1: Systematically activate pumps draining non-depletable tanks
        if not from_tank["depletable"] and pump["state"] == "off":
            desired = "on"

        # Heuristic 2: Activate/deactivate pump whose target tank is too low/high
        if to_tank["target"] is not None:
            if to_tank["level"] <= to_tank["target"] - 50 + threshold_noise:
                desired = "on"
            elif to_tank["level"] >= to_tank["target"] + 50 + threshold_noise:
                desired = "off"

        # Heuristic 3: Equilibrate between the two A/B tanks if sufficient level
        if from_tank["target"] is not None and to_tank["target"] is not None:
            if from_tank["level"] >= to_tank["target"] >= to_tank["level"]:
                desired = "on"
            else:
                desired = "off"

        return desired

    def _update_track(self, plugin: Any) -> None:
        cx, cy = plugin.reticle.cursor_relative
        jx = 1.0 if -cx >= 0 else -1.0
        jy = -1.0 if -cy >= 0 else 1.0  # y inverted in get_joystick_inputs
        self.send_joystick(plugin, jx, jy)

    def _update_communications(self, plugin: Any) -> None:
        waiting_radios = plugin.get_waiting_response_radios()

        if len(waiting_radios) == 0:
            return

        autoradio = waiting_radios[0]
        active = plugin.get_active_radio_dict()

        if active != autoradio:
            # Switch radio via UP/DOWN key
            direction_key = ("selectradioup" if autoradio["pos"] < active["pos"]
                             else "selectradiodown")
            self.send_key(plugin, plugin.parameters["keys"][direction_key])

        elif active["targetfreq"] != active["currentfreq"]:
            # Tune frequency via LEFT/RIGHT key
            direction_key = ("tunefrequencyup" if active["targetfreq"] > active["currentfreq"]
                             else "tunefrequencydown")
            self.send_key(plugin, plugin.parameters["keys"][direction_key])

        else:
            self.send_key(plugin, plugin.parameters["keys"]["validateresponse"])
