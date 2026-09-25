# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""ACT-R cognitive architecture agent for the AF-MATB.

Based on: Swan, Stevens, Fisher & Klosterman (2022) — "Exploring Multitasking
Strategies in an ACT-R model of a Complex Piloting Task".

The model uses serial top-down attention scanning (clockwise through subtasks)
with configurable bottom-up interrupts. The best-fitting variant in the paper
is LR (bottom-up for Lights + Resource management).
"""

from __future__ import annotations

import math
import random
from typing import Any, ClassVar

from agents.abstract_agent import AbstractAgent


class ACTRAgent(AbstractAgent):
    """ACT-R cognitive architecture model for the AF-MATB.

    Parameters
    ----------
    seed : int or None
        Random seed for reproducibility.
    bottom_up : str
        Which subtasks have bottom-up selection. Letters: L=Lights,
        G=Gauges, R=Resource, T=Tracking.  Default "LR" (best model).
    top_down : bool
        Enable serial clockwise scanning. False = purely reactive
        ("Only LGRT" variant — agent only responds to bottom-up interrupts).
    """

    # ── ACT-R timing constants ────────────────────────────────
    PRODUCTION_CYCLE_S = 0.050  # 50 ms per production
    VISUAL_ONSET_SPAN_S = 3.0  # peripheral detection delay
    MOTOR_EXEC_S = 0.250  # motor execution time per action

    # ── Tracking constants ────────────────────────────────────
    TRACK_GAIN = 0.125  # polar radius multiplier
    TRACK_MAX_PX = 10  # max compensation per update (pixels)
    CURSOR_NOISE_STD = 0.03  # Gaussian noise std on joystick output

    # ── Declarative memory (communications) ───────────────────
    DM_BLL = 0.5  # base-level learning decay
    DM_ANS = 0.2  # activation noise (logistic scale)
    DM_BLC = 2.0  # base-level constant
    DM_RT = 2.9  # retrieval threshold

    # ── Motor error ───────────────────────────────────────────
    MOTOR_ERROR_PROB = 0.05  # 5 % wrong key probability

    # ── Resman thresholds ─────────────────────────────────────
    RESMAN_ACTION_THRESHOLD = 100  # L deviation to take action (attending)
    RESMAN_BU_THRESHOLD = 700  # L deviation for bottom-up interrupt

    # ── Tracking bottom-up ────────────────────────────────────
    TRACK_BU_THRESHOLD = 27.5  # pixels from center for bottom-up

    # ── Subtask → plugin alias mapping ────────────────────────
    _SUBTASK_TO_ALIAS: ClassVar[dict[str, str]] = {
        "sysmon_lights": "sysmon",
        "sysmon_gauges": "sysmon",
        "tracking": "track",
        "resman": "resman",
        "communications": "communications",
    }

    def __init__(
        self,
        seed: int | None = None,
        bottom_up: str = "LR",
        top_down: bool = True,
    ) -> None:
        super().__init__(name="actr", automode_string="AUTO-ACTR")
        self._rng = random.Random(seed)
        self.show_attention = True

        self._top_down = top_down

        # Scan state
        self._scan_order = [
            "sysmon_lights",
            "sysmon_gauges",
            "tracking",
            "resman",
            "communications",
        ]
        self._scan_index = 0
        self._attended: str | None = self._scan_order[0] if top_down else None
        print(f"[ACT-R] t=0.000  init: _attended={self._attended!r}  _attended_task={self._attended_task!r}")
        self._attend_start_s = 0.0
        self._busy_until_s = 0.0

        # Bottom-up config
        self._bu_lights = "L" in bottom_up.upper()
        self._bu_gauges = "G" in bottom_up.upper()
        self._bu_resource = "R" in bottom_up.upper()
        self._bu_tracking = "T" in bottom_up.upper()

        # Bottom-up event tracking
        self._bu_onset: dict[str, float] = {}

        # Pump initialization
        self._pumps_initialized = False
        self._pump_init_index = 0
        self._next_pump_time = 0.0

        # Communications memory
        self._comms_known_waiting: set[int] = set()
        self._comms_memory: dict[int, dict] = {}
        self._comms_retrieval_ok: dict[int, bool] = {}
        self._comms_last_action_s = 0.0

        # Resman pump queue
        self._resman_pump_queue: list[str] = []
        self._resman_next_pump_time = 0.0
        self._resman_checked_this_visit = False

    # ── Declarative memory retrieval ──────────────────────────

    def _logistic_sample(self, mu: float, s: float) -> float:
        u = self._rng.random()
        u = max(1e-10, min(1 - 1e-10, u))
        return mu + s * math.log(u / (1.0 - u))

    def _attempt_dm_retrieval(self, stored_at: float, retrieve_at: float) -> bool:
        t = max(0.001, retrieve_at - stored_at)
        base_level = -self.DM_BLL * math.log(t)
        activation = base_level + self.DM_BLC
        noise = self._logistic_sample(0, self.DM_ANS)
        return activation + noise > self.DM_RT

    # ── Attention model ───────────────────────────────────────

    def _alias_for_attended(self) -> str | None:
        if self._attended is None:
            return None
        return self._SUBTASK_TO_ALIAS.get(self._attended)

    @property
    def _attended_task(self) -> str | None:
        """Plugin alias for the attended subtask (used by abstractplugin attention widget)."""
        return self._alias_for_attended()

    def _has_pending_work(self, plugin: Any) -> bool:
        """Check if current subtask has pending work (prevents scan advance).

        Returns True (= don't advance) when the calling plugin cannot evaluate
        the attended subtask, so that only the *matching* plugin decides.
        """
        task = self._attended
        alias = plugin.alias
        expected_alias = self._SUBTASK_TO_ALIAS.get(task)

        # Only the plugin that matches the attended subtask can decide
        if alias != expected_alias:
            return True  # Can't evaluate → don't advance

        if task == "sysmon_lights":
            return any(g["_onfailure"] for g in plugin.get_light_gauges())
        if task == "sysmon_gauges":
            return any(g["_onfailure"] for g in plugin.get_scale_gauges())
        if task == "tracking":
            cx, cy = plugin.reticle.cursor_relative
            return math.sqrt(cx * cx + cy * cy) > 5.0
        if task == "resman":
            # Only block while actively executing queued pump actions
            return bool(self._resman_pump_queue)
        if task == "communications":
            waiting = plugin.get_waiting_response_radios()
            return any(self._comms_retrieval_ok.get(r["pos"], False) for r in waiting)
        return False

    def _maybe_advance_scan(self, scenario_time: float, caller_alias: str = "") -> None:
        if not self._top_down:
            return
        if self._attended is None:
            return
        if scenario_time - self._attend_start_s < 0.100:
            return
        # Don't advance — pending work check is done per-plugin in on_plugin_update
        # Instead, advance only when the _pending_work flag is cleared
        self._scan_index = (self._scan_index + 1) % len(self._scan_order)
        old = self._attended
        dwell = scenario_time - self._attend_start_s
        self._attended = self._scan_order[self._scan_index]
        self._attend_start_s = scenario_time
        self._resman_checked_this_visit = False
        print(
            f"[ACT-R] t={scenario_time:.3f}  top-down advance: {old!r} -> {self._attended!r}"
            f"  _attended_task={self._attended_task!r}  dwell={dwell:.3f}s  caller={caller_alias!r}"
        )

    # ── Bottom-up monitoring ──────────────────────────────────

    def _monitor_bottom_up(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias

        if alias == "sysmon":
            if self._bu_lights:
                for g in plugin.get_light_gauges():
                    key = f"light_{g['key']}"
                    if g["_onfailure"]:
                        if key not in self._bu_onset:
                            self._bu_onset[key] = scenario_time
                    else:
                        self._bu_onset.pop(key, None)

            if self._bu_gauges:
                for g in plugin.get_scale_gauges():
                    key = f"scale_{g['key']}"
                    if g["_onfailure"]:
                        if key not in self._bu_onset:
                            self._bu_onset[key] = scenario_time
                    else:
                        self._bu_onset.pop(key, None)

        if alias == "resman" and self._bu_resource:
            tanks = plugin.parameters["tank"]
            any_deviation = False
            for letter in ("a", "b"):
                tank = tanks[letter]
                if tank["target"] is not None:
                    deviation = abs(tank["level"] - tank["target"])
                    if deviation > self.RESMAN_BU_THRESHOLD:
                        any_deviation = True
            if any_deviation:
                if "resman" not in self._bu_onset:
                    self._bu_onset["resman"] = scenario_time
            else:
                self._bu_onset.pop("resman", None)

        if alias == "track" and self._bu_tracking:
            cx, cy = plugin.reticle.cursor_relative
            dist = math.sqrt(cx * cx + cy * cy)
            if dist > self.TRACK_BU_THRESHOLD:
                if "tracking" not in self._bu_onset:
                    self._bu_onset["tracking"] = scenario_time
            else:
                self._bu_onset.pop("tracking", None)

    def _check_bottom_up_interrupt(self, scenario_time: float) -> None:
        # Priority order: sysmon (lights > gauges) > resman > tracking
        priority = []
        for key, onset in list(self._bu_onset.items()):
            if scenario_time - onset < self.VISUAL_ONSET_SPAN_S:
                continue
            if key.startswith("light_"):
                priority.append((0, key, "sysmon_lights"))
            elif key.startswith("scale_"):
                priority.append((1, key, "sysmon_gauges"))
            elif key == "resman":
                priority.append((2, key, "resman"))
            elif key == "tracking":
                priority.append((3, key, "tracking"))

        if not priority:
            return

        priority.sort(key=lambda x: x[0])
        _, event_key, target_subtask = priority[0]

        # Switch attention
        old = self._attended
        self._attended = target_subtask
        if target_subtask in self._scan_order:
            self._scan_index = self._scan_order.index(target_subtask)
        self._attend_start_s = scenario_time
        self._resman_checked_this_visit = False
        del self._bu_onset[event_key]
        print(
            f"[ACT-R] t={scenario_time:.3f}  bottom-up switch: {old!r} -> {self._attended!r}"
            f"  _attended_task={self._attended_task!r}"
        )

    # ── Communications audio monitoring ───────────────────────

    def _monitor_comms_audio(self, plugin: Any, scenario_time: float) -> None:
        if plugin.alias != "communications":
            return

        waiting = plugin.get_waiting_response_radios()
        current_waiting_pos = {r["pos"] for r in waiting}

        for radio in waiting:
            pos = radio["pos"]
            if pos not in self._comms_known_waiting:
                self._comms_known_waiting.add(pos)
                self._comms_memory[pos] = {
                    "freq": radio["targetfreq"],
                    "stored_at": scenario_time,
                }
                success = self._attempt_dm_retrieval(scenario_time, scenario_time + self.PRODUCTION_CYCLE_S)
                self._comms_retrieval_ok[pos] = success

                if success:
                    old = self._attended
                    self._attended = "communications"
                    self._scan_index = self._scan_order.index("communications")
                    self._attend_start_s = scenario_time
                    self._resman_checked_this_visit = False
                    print(
                        f"[ACT-R] t={scenario_time:.3f}  comms audio switch: {old!r}"
                        f" -> {self._attended!r}  _attended_task={self._attended_task!r}"
                    )

        # Clean up resolved radios
        for pos in list(self._comms_known_waiting):
            if pos not in current_waiting_pos:
                self._comms_known_waiting.discard(pos)
                self._comms_retrieval_ok.pop(pos, None)
                self._comms_memory.pop(pos, None)

    # ── Pump initialization ───────────────────────────────────

    def _init_pumps(self, plugin: Any, scenario_time: float) -> None:
        if scenario_time < self._next_pump_time:
            return
        if self._pump_init_index < 6:
            pump_num = str(self._pump_init_index + 1)
            pump = plugin.parameters["pump"][pump_num]
            if pump["state"] == "off":
                self.send_key(plugin, pump["key"])
            self._pump_init_index += 1
            self._next_pump_time = scenario_time + self.MOTOR_EXEC_S
        else:
            self._pumps_initialized = True
            self._attend_start_s = scenario_time

    # ── Per-subtask handlers ──────────────────────────────────

    def _handle_sysmon_lights(self, plugin: Any, scenario_time: float) -> None:
        if self._attended != "sysmon_lights":
            return
        for g in plugin.get_light_gauges():
            if not g["_onfailure"]:
                continue
            if g["_response_start"] is None:
                continue
            key = g["key"]
            if self._rng.random() < self.MOTOR_ERROR_PROB:
                key = self._rng.choice(["F1", "F2", "F3", "F4", "F5", "F6"])
            self.send_key(plugin, key)
            self._busy_until_s = scenario_time + self.MOTOR_EXEC_S
            break

    def _handle_sysmon_gauges(self, plugin: Any, scenario_time: float) -> None:
        if self._attended != "sysmon_gauges":
            return
        for g in plugin.get_scale_gauges():
            if not g["_onfailure"]:
                continue
            if g["_response_start"] is None:
                continue
            key = g["key"]
            if self._rng.random() < self.MOTOR_ERROR_PROB:
                key = self._rng.choice(["F1", "F2", "F3", "F4", "F5", "F6"])
            self.send_key(plugin, key)
            self._busy_until_s = scenario_time + self.MOTOR_EXEC_S
            break

    def _handle_tracking(self, plugin: Any, scenario_time: float) -> None:
        if self._attended != "tracking":
            return

        cx, cy = plugin.reticle.cursor_relative

        dx = cx * self.TRACK_GAIN
        dy = cy * self.TRACK_GAIN

        dx = max(-self.TRACK_MAX_PX, min(self.TRACK_MAX_PX, dx))
        dy = max(-self.TRACK_MAX_PX, min(self.TRACK_MAX_PX, dy))

        jx = max(-1.0, min(1.0, -dx))
        jy = max(-1.0, min(1.0, dy))

        jx += self._rng.gauss(0, self.CURSOR_NOISE_STD)
        jy += self._rng.gauss(0, self.CURSOR_NOISE_STD)
        jx = max(-1.0, min(1.0, jx))
        jy = max(-1.0, min(1.0, jy))

        self.send_joystick(plugin, jx, jy)

    def _handle_resman(self, plugin: Any, scenario_time: float) -> None:
        if self._attended != "resman":
            return
        if plugin.wait_before_leak > 0:
            return

        # Continue cycling through pump queue
        if self._resman_pump_queue and scenario_time >= self._resman_next_pump_time:
            pump_key = self._resman_pump_queue.pop(0)
            if self._rng.random() < self.MOTOR_ERROR_PROB:
                pump_key = self._rng.choice(
                    [
                        "NUM_1",
                        "NUM_2",
                        "NUM_3",
                        "NUM_4",
                        "NUM_5",
                        "NUM_6",
                        "NUM_7",
                        "NUM_8",
                    ]
                )
            self.send_key(plugin, pump_key)
            self._resman_next_pump_time = scenario_time + self.MOTOR_EXEC_S
            return

        if self._resman_pump_queue:
            return  # waiting for next pump time

        # Only build pump queue once per visit — avoids infinite loop
        if self._resman_checked_this_visit:
            return
        self._resman_checked_this_visit = True

        # Build pump queue from tank deviations
        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        # Tank A
        tank_a = tanks["a"]
        if tank_a["target"] is not None:
            dev_a = tank_a["level"] - tank_a["target"]
            ps = {p: pumps[p]["state"] for p in ["1", "2", "3", "4", "5", "6"]}
            tank_b = tanks["b"]
            dev_b = tank_b["level"] - tank_b["target"] if tank_b["target"] is not None else "?"
            print(f"[ACT-R-DBG] t={scenario_time:.3f}  resman CHECK  dev_A={dev_a}  dev_B={dev_b}  pumps={ps}")
            if dev_a < -self.RESMAN_ACTION_THRESHOLD:
                for p_num in ["1", "5", "2"]:
                    if pumps[p_num]["state"] == "off":
                        self._resman_pump_queue.append(pumps[p_num]["key"])
            elif dev_a > self.RESMAN_ACTION_THRESHOLD:
                if pumps["2"]["state"] == "on":
                    self._resman_pump_queue.append(pumps["2"]["key"])

        # Tank B
        tank_b = tanks["b"]
        if tank_b["target"] is not None:
            dev_b = tank_b["level"] - tank_b["target"]
            if dev_b < -self.RESMAN_ACTION_THRESHOLD:
                for p_num in ["3", "6", "4"]:
                    if pumps[p_num]["state"] == "off":
                        self._resman_pump_queue.append(pumps[p_num]["key"])
            elif dev_b > self.RESMAN_ACTION_THRESHOLD:
                if pumps["4"]["state"] == "on":
                    self._resman_pump_queue.append(pumps["4"]["key"])

        print(f"[ACT-R-DBG] t={scenario_time:.3f}  resman QUEUE={[k for k in self._resman_pump_queue]}")
        if self._resman_pump_queue:
            self._resman_next_pump_time = scenario_time

    def _handle_communications(self, plugin: Any, scenario_time: float) -> None:
        if self._attended != "communications":
            return

        waiting = plugin.get_waiting_response_radios()
        if not waiting:
            return

        actionable = [r for r in waiting if self._comms_retrieval_ok.get(r["pos"], False)]
        if not actionable:
            return

        if scenario_time - self._comms_last_action_s < 4 * self.PRODUCTION_CYCLE_S:
            return

        target_radio = actionable[0]
        active = plugin.get_active_radio_dict()

        key = self.compute_comms_action(active, target_radio, plugin.parameters["keys"])
        self.send_key(plugin, key)
        self._comms_last_action_s = scenario_time

        if key == plugin.parameters["keys"]["validateresponse"]:
            pos = target_radio["pos"]
            self._comms_retrieval_ok.pop(pos, None)
            self._comms_memory.pop(pos, None)
            self._comms_known_waiting.discard(pos)

    # ── Dispatch ──────────────────────────────────────────────

    def _dispatch(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias
        if alias == "sysmon":
            self._handle_sysmon_lights(plugin, scenario_time)
            self._handle_sysmon_gauges(plugin, scenario_time)
        elif alias == "track":
            self._handle_tracking(plugin, scenario_time)
        elif alias == "resman":
            self._handle_resman(plugin, scenario_time)
        elif alias == "communications":
            self._handle_communications(plugin, scenario_time)

    # ── Main callback ─────────────────────────────────────────

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        # 1. Pump initialization (blocks everything else)
        if not self._pumps_initialized and plugin.alias == "resman":
            self._init_pumps(plugin, scenario_time)
            return
        if not self._pumps_initialized:
            return

        # 2. Bottom-up monitoring (always, for peripheral detection)
        self._monitor_bottom_up(plugin, scenario_time)

        # 3. Communications audio monitoring (parallel)
        self._monitor_comms_audio(plugin, scenario_time)

        # 4. Check bottom-up interrupt
        self._check_bottom_up_interrupt(scenario_time)

        # 5. If motor busy → return
        if scenario_time < self._busy_until_s:
            return

        # 6. Maybe advance scan (only if no pending work on current subtask)
        if not self._has_pending_work(plugin):
            self._maybe_advance_scan(scenario_time, caller_alias=plugin.alias)

        # 7. Only dispatch if this plugin matches attended subtask
        if plugin.alias != self._alias_for_attended():
            return

        # 8. Execute per-subtask handler
        self._dispatch(plugin, scenario_time)

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        key = gauge.get("key", "")
        if key in ("F5", "F6") and self._bu_lights:
            self._bu_onset.setdefault(f"light_{key}", plugin.scenario_time)
        elif key in ("F1", "F2", "F3", "F4") and self._bu_gauges:
            self._bu_onset.setdefault(f"scale_{key}", plugin.scenario_time)
        return {"delay": plugin.parameters["alerttimeout"]}
