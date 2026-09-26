# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent
from core.constants import COLORS as C


class CooperativeAgent(AbstractAgent):
    """Cooperative mode: the automation simplifies controls, the human acts with help.

    Based on Navarro et al. (2021) — the agent modifies task parameters to make
    the human's job easier and provides visual hints.  Never injects key or
    joystick input.
    """

    def __init__(self) -> None:
        super().__init__(name="cooperative", automode_string="COOP")
        self.allows_human_input = True
        self._sysmon_configured: bool = False
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
        """Enable allowanykey so SPACE resolves any failure.
        Also set hint arrow colors like AssistedAgent."""
        if not self._sysmon_configured:
            plugin.parameters["allowanykey"] = True
            self._sysmon_configured = True

        for scale in plugin.get_scale_gauges():
            if scale["_onfailure"]:
                scale["_hint_arrow_color"] = C["RED"]
            else:
                scale["_hint_arrow_color"] = None

    # ── Track ───────────────────────────────────────────────────────────
    def _update_track(self, plugin: Any) -> None:
        """Amplify joystick force so any input toward center guarantees return."""
        if not self._track_configured:
            plugin.parameters["joystickforce"] = 10
            self._track_configured = True

    # ── Resman ──────────────────────────────────────────────────────────
    def _update_resman(self, plugin: Any) -> None:
        """Highlight pumps that need toggling with YELLOW."""
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
                this_pump["_hint_color"] = C["YELLOW"]
            else:
                this_pump["_hint_color"] = None

    # ── Communications ──────────────────────────────────────────────────
    def _update_communications(self, plugin: Any) -> None:
        """Auto-select the correct radio + highlight with YELLOW.
        Human only needs to tune the frequency and validate.
        Hint appears as soon as the prompt starts (during audio playback)."""
        target_radios = plugin.get_target_radios_list()

        for _r, radio in plugin.parameters["radios"].items():
            if radio in target_radios:
                radio["_hint_color"] = C["YELLOW"]
            else:
                radio["_hint_color"] = None

        # Auto-select: switch to the first waiting radio if it's not active
        # (only after audio ends — don't switch while prompt is still playing)
        waiting = plugin.get_waiting_response_radios()
        if waiting:
            target_radio = waiting[0]
            active = plugin.get_active_radio_dict()
            if active != target_radio:
                active["is_active"] = False
                target_radio["is_active"] = True
