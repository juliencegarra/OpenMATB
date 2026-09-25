# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent
from core.constants import COLORS as C


class AssistedAgent(AbstractAgent):
    """Assisted mode: the automation provides visual cues, the human acts.

    Based on Navarro et al. (2021) — the agent highlights anomalies but never
    injects key or joystick input.
    """

    def __init__(self) -> None:
        super().__init__(name="assisted", automode_string="ASSISTED")
        self.allows_human_input = True
        self._track_configured: bool = False

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias
        if alias == "sysmon":
            self._update_sysmon(plugin)
        elif alias == "track":
            self._update_track(plugin)
        elif alias == "resman":
            self._update_resman(plugin)
        elif alias == "communications":
            self._update_communications(plugin)

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        # Human must respond — use the full alerttimeout
        return {"delay": plugin.parameters["alerttimeout"]}

    # ── Sysmon ──────────────────────────────────────────────────────────
    def _update_sysmon(self, plugin: Any) -> None:
        """Set arrow hint color to RED on scales that are currently in failure."""
        for scale in plugin.get_scale_gauges():
            if scale["_onfailure"]:
                scale["_hint_arrow_color"] = C["RED"]
            else:
                scale["_hint_arrow_color"] = None

    # ── Track ───────────────────────────────────────────────────────────
    def _update_track(self, plugin: Any) -> None:
        """One-time setup: make cursor blue inside target, red outside."""
        if not self._track_configured:
            plugin.parameters["cursorcolor"] = C["BLUE"]
            plugin.parameters["cursorcoloroutside"] = C["RED"]
            self._track_configured = True

    # ── Resman ──────────────────────────────────────────────────────────
    def _update_resman(self, plugin: Any) -> None:
        """Highlight pumps that need toggling with CYAN."""
        if plugin.wait_before_leak > 0:
            return

        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        for _pump_n, this_pump in pumps.items():
            if this_pump["state"] == "failure":
                this_pump["_hint_color"] = None
                continue
            from_tank = tanks[this_pump["_fromtank"]]
            to_tank = tanks[this_pump["_totank"]]
            desired = DefaultAgent._compute_desired_pump_state(this_pump, from_tank, to_tank)
            if desired is not None and desired != this_pump["state"]:
                this_pump["_hint_color"] = C["CYAN"]
            else:
                this_pump["_hint_color"] = None

    # ── Communications ──────────────────────────────────────────────────
    def _update_communications(self, plugin: Any) -> None:
        """Highlight radios that have a target frequency with CYAN.
        Shows the hint as soon as the prompt starts (during audio playback),
        not just after the audio ends."""
        for _r, radio in plugin.parameters["radios"].items():
            if radio["targetfreq"] is not None:
                radio["_hint_color"] = C["CYAN"]
            else:
                radio["_hint_color"] = None
