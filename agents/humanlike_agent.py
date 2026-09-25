# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
import random
from typing import Any

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent


class HumanLikeAgent(AbstractAgent):
    """Simulates a realistic human operator using a central attention model.

    A human cannot monitor 4 tasks simultaneously. This agent scans tasks
    sequentially — dwelling on each for a few seconds before switching.
    Unattended tasks degrade (cursor drifts, tanks empty, prompts wait).
    """

    def __init__(self, seed: int | None = None) -> None:
        super().__init__(name="humanlike", automode_string="AUTO-HL")
        # Random seed for reproducibility. None = different random behavior each run.
        self._rng = random.Random(seed)

        # Visual indicator: highlight the currently attended task with a border.
        self.show_attention: bool = True

        # ── Attention parameters ─────────────────────────────────

        # Typical scan order observed in trained MATB operators (Wickens, 2002).
        # Sysmon first because visual alarms attract peripheral gaze; track next
        # as the most attention-demanding continuous task.
        self.scan_order: list[str] = ["sysmon", "track", "resman", "communications"]

        # Mean fixation duration on an area of interest in monitoring tasks.
        # Cockpit eye-tracking studies show 2-5s fixations per instrument zone
        # (Sarter & Woods, 1995). 3s is a realistic median.
        self.dwell_mean_ms: float = 3000

        # Inter-fixation variability. std=1s gives a typical range of [1s, 5s]
        # (+-2 sigma), consistent with operator variability.
        self.dwell_std_ms: float = 1000

        # Cognitive task-switching cost. Literature reports 200-500ms residual
        # cost even with preparation (Monsell, 2003). 300ms is conservative.
        self.switching_cost_ms: float = 300

        # Probability that a salient event (sysmon failure) captures attention.
        # Salient visual stimuli capture attention ~80% of the time under
        # moderate workload (Yantis & Jonides, 1990).
        self.interrupt_prob: float = 0.8

        # ── Sysmon parameters ────────────────────────────────────

        # Mean RT for detecting and responding to a visual anomaly. Includes:
        # detection (~500ms) + identification (~500ms) + decision (~500ms) +
        # motor response (~300ms) + variability margin. MATB studies report
        # 2-4s RT for sysmon failures (Comstock & Arnegard, 1992).
        self.sysmon_rt_mean: float = 2500

        # RT standard deviation. Log-normal distribution is standard for human
        # RTs (Luce, 1986). std=800ms produces a realistic right-skewed tail.
        self.sysmon_rt_std: float = 800

        # Mean RT increase per detected failure. Models the vigilance decrement
        # effect (Mackworth, 1948). +50ms/failure is conservative; actual decline
        # can reach +100-200ms over 30 min (Warm et al., 2008).
        self.vigilance_decrement: float = 50

        # ── Track parameters ─────────────────────────────────────

        # Visuomotor reaction time to initiate a correction after detecting
        # cursor deviation. Simple visuomotor RT is ~250ms (Welford, 1980);
        # add ~150ms for spatial processing (direction + amplitude).
        self.track_reaction_ms: float = 400

        # Per-frame probability of a "micro-hesitation" (no compensation).
        # Models motor noise, tremor, and brief attentional lapses during
        # continuous tracking (Poulton, 1974).
        self.track_noise_prob: float = 0.15

        # Proportional gain for track compensation. The joystick value is
        # cursor_offset / half_container * track_gain, clamped to [-1, 1].
        # With gain=4.0, the agent reaches full joystick when the cursor is
        # at ~25% of the reticle half-width (≈ the target zone edge),
        # matching human behavior of applying strong correction as soon as
        # the cursor visibly deviates.
        self.track_gain: float = 4.0

        # After the cursor enters the target, the sinus disturbance is still
        # present. If the proportional gain drops too fast (cursor near 0),
        # moff won't accumulate enough to resist the next half-cycle.
        # Maintain a minimum force for track_settle_ms after target entry.
        self.track_settle_ms: float = 2000
        self.track_settle_force: float = 0.3

        # ── Communications parameters ────────────────────────────

        # Delay between audio prompt end and start of radio manipulation.
        # Includes: message comprehension (~500ms) + action planning (~500ms) +
        # motor initiation (~500ms). Shorter than sysmon RT because information
        # is explicit (no detection needed).
        self.comms_reaction_ms: float = 1500

        # Interval between frequency tuning steps. Corresponds to natural
        # manipulation rate of a rotary knob or repeated clicks (~5 Hz).
        # Interface studies show inter-click times of 150-300ms
        # (Card, Moran & Newell, 1983).
        self.comms_tune_interval_ms: float = 200

        # Probability of overshooting the target frequency. Overshoot in
        # discrete pointing tasks (0.1 MHz steps) is ~5-15% per Fitts' law
        # (Fitts, 1954). 10% is a median value for discrete steps.
        self.comms_overshoot_prob: float = 0.1

        # ── Resman parameters ────────────────────────────────────

        # Gaussian noise std added to decision thresholds (+-50 in DefaultAgent).
        # Models imprecision in reading analog gauges. std=75 means effective
        # threshold varies approx [-100, +200] around target (+-2 sigma),
        # consistent with gauge reading error (Roscoe, 1968).
        self.resman_threshold_noise: float = 75

        # Per-pump probability of failing to execute an identified pump action.
        # Models omission errors ("slips") under cognitive load (Reason, 1990).
        # 5% is a typical execution error rate for well-learned tasks.
        self.resman_forget_prob: float = 0.05

        # Maximum additional time (beyond dwell) the agent will stay on a task
        # to finish active work. Prevents indefinite lock on one task.
        self.persist_max_ms: float = 10000

        # Minimum time (ms) on current task before idle-switch is allowed.
        # Prevents jittery instant exits — agent at least glances at the task.
        self.idle_switch_delay_ms: float = 500

        # ── Internal state ───────────────────────────────────────

        self._scan_index: int = 0
        self._attended_task: str = self.scan_order[0]
        self._attend_start: float = 0.0
        self._current_dwell: float = self._sample_dwell()
        self._switching_until: float = 0.0

        # Sysmon state
        self._failure_count: int = 0
        self._sysmon_pending: bool = False

        # Track state
        self._track_react_start: float | None = None
        self._track_last_outside: float | None = None

        # Communications state
        self._comms_react_start: float | None = None
        self._comms_last_tune: float = 0.0

    # ── Log-normal sampling utilities ────────────────────────

    @staticmethod
    def _log_normal_params(mean: float, std: float) -> tuple[float, float]:
        """Convert desired mean/std (in ms) to log-normal mu/sigma parameters."""
        variance = std * std
        mu = math.log(mean * mean / math.sqrt(variance + mean * mean))
        sigma = math.sqrt(math.log(1 + variance / (mean * mean)))
        return mu, sigma

    def _sample_rt(self, mean: float, std: float) -> float:
        """Sample a reaction time (ms) from a log-normal distribution."""
        mu, sigma = self._log_normal_params(mean, std)
        return self._rng.lognormvariate(mu, sigma)

    def _sample_dwell(self) -> float:
        """Sample a dwell duration (ms) from a Gaussian, clamped to >= 100ms."""
        return max(100, self._rng.gauss(self.dwell_mean_ms, self.dwell_std_ms))

    # ── Attention model ──────────────────────────────────────

    def _is_idle(self) -> bool:
        """Return True if nothing demands attention on the current task."""
        task = self._attended_task
        if task == "sysmon":
            return not self._sysmon_pending
        if task == "track":
            return self._track_react_start is None
        if task == "communications":
            return self._comms_react_start is None
        # resman: always monitoring gauges
        return False

    def _find_salient_task(self) -> str | None:
        """Return a task with a salient event, or None."""
        if self._attended_task != "sysmon" and self._sysmon_pending:
            return "sysmon"
        # Comms prompts are audio-based — no persistent visual saliency.
        # Handled during normal scan, not via idle-switch.
        return None

    def _is_actively_working(self, scenario_time: float) -> bool:
        """Return True if the agent is mid-action on the current task."""
        task = self._attended_task

        if task == "track":
            # Actively compensating: cursor out of target AND past reaction delay
            return (
                self._track_react_start is not None
                and (scenario_time - self._track_react_start) * 1000 >= self.track_reaction_ms
            )

        if task == "sysmon":
            # Failure visible and not yet resolved
            return self._sysmon_pending

        if task == "communications":
            # Actively tuning: past reaction delay and prompt still pending
            return (
                self._comms_react_start is not None
                and (scenario_time - self._comms_react_start) * 1000 >= self.comms_reaction_ms
            )

        return False

    def _update_attention(self, scenario_time: float) -> None:
        """Advance the scanning cycle if the current dwell time has elapsed."""
        elapsed_ms = (scenario_time - self._attend_start) * 1000

        # Idle-switch: nothing to do here + salient event elsewhere → switch early
        if elapsed_ms >= self.idle_switch_delay_ms and self._is_idle():
            salient = self._find_salient_task()
            if salient:
                self._advance_scan(scenario_time, target=salient)
                return

        if elapsed_ms < self._current_dwell:
            return

        # Stay on current task while actively working (with safety cap)
        if elapsed_ms < self._current_dwell + self.persist_max_ms:
            if self._is_actively_working(scenario_time):
                return

        self._advance_scan(scenario_time)

    def _advance_scan(self, scenario_time: float, target: str | None = None) -> None:
        """Move to the next task in the scan order, or jump to *target*."""
        if target and target in self.scan_order:
            self._scan_index = self.scan_order.index(target)
        else:
            self._scan_index = (self._scan_index + 1) % len(self.scan_order)
        self._attended_task = self.scan_order[self._scan_index]
        self._attend_start = scenario_time
        self._current_dwell = self._sample_dwell()
        self._switching_until = scenario_time + self.switching_cost_ms / 1000
        # Reset per-plugin reaction states for the new task.
        # Comms reaction persists — once comprehended, agent remembers on return.
        # Reset happens in _update_communications when prompt resolved.
        self._track_react_start = None
        # _sysmon_pending is NOT reset — it's cross-task state

    def _switch_to(self, task: str) -> None:
        """Immediately switch attention to a specific task (e.g. interrupt)."""
        if task in self.scan_order:
            self._scan_index = self.scan_order.index(task)
        self._attended_task = task
        # Keep _attend_start unchanged — the interrupt steals the current dwell
        self._current_dwell = self._sample_dwell()
        # Reset per-plugin reaction states (track only; comms persists).
        self._track_react_start = None
        # _sysmon_pending is NOT reset — it's cross-task state

    # ── Main callbacks ───────────────────────────────────────

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        # 1. Advance scanning cycle if dwell elapsed
        self._update_attention(scenario_time)

        # 2. During switching cost → do nothing
        if scenario_time < self._switching_until:
            return

        # 3. Dispatch to per-plugin handler
        alias = plugin.alias
        if alias == "sysmon":
            self._update_sysmon(plugin, scenario_time)
        elif alias == "track":
            self._update_track(plugin, scenario_time)
        elif alias == "communications":
            self._update_communications(plugin, scenario_time)
        elif alias == "resman":
            self._update_resman(plugin, scenario_time)

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        self._sysmon_pending = True  # Cross-task saliency signal
        # Attention capture: if looking elsewhere, probability of switching
        if self._attended_task != "sysmon" and self._rng.random() < self.interrupt_prob:
            self._switch_to("sysmon")

        self._failure_count += 1
        # Safety-net (identical to DefaultAgent) — if the agent doesn't resolve
        # the failure before alerttimeout, it expires as a MISS
        return {"delay": plugin.parameters["alerttimeout"]}

    # ── Per-plugin handlers ──────────────────────────────────

    def _update_sysmon(self, plugin: Any, scenario_time: float) -> None:
        if self._attended_task != "sysmon":
            return  # Not attending → failures accumulate

        failures = plugin.get_gauges_on_failure()
        self._sysmon_pending = len(failures) > 0

        # RT with vigilance decrement (log-normal)
        delay = self._sample_rt(
            self.sysmon_rt_mean + self._failure_count * self.vigilance_decrement,
            self.sysmon_rt_std,
        )

        for gauge in failures:
            if (
                gauge["_response_start"] is not None
                and (plugin.scenario_time - gauge["_response_start"]) * 1000 >= delay
            ):
                self.send_key(plugin, gauge["key"])

    def _update_track(self, plugin: Any, scenario_time: float) -> None:
        if self._attended_task != "track":
            return  # Cursor drifts freely

        reticle = plugin.reticle

        # Reaction delay: detect that cursor left the target zone
        if reticle.is_cursor_in_target():
            self._track_react_start = None
        elif self._track_react_start is None:
            self._track_react_start = scenario_time

        if self._track_react_start is not None:
            if (scenario_time - self._track_react_start) * 1000 < self.track_reaction_ms:
                return

        # Micro-hesitation (motor noise)
        if self._rng.random() < self.track_noise_prob:
            return

        # Proportional compensation with settling
        cx, cy = reticle.cursor_relative
        half_w = reticle.container.w / 2
        half_h = reticle.container.h / 2

        if not reticle.is_cursor_in_target():
            self._track_last_outside = scenario_time

        jx, jy = self.compute_tracking_compensation(
            cx,
            cy,
            half_w,
            half_h,
            gain=self.track_gain,
            settle_force=self.track_settle_force,
            settle_ms=self.track_settle_ms,
            last_outside_time=self._track_last_outside,
            current_time=scenario_time,
        )
        self.send_joystick(plugin, jx, jy)

    def _update_communications(self, plugin: Any, scenario_time: float) -> None:
        if self._attended_task != "communications":
            return  # Prompt waits, no tuning

        waiting_radios = plugin.get_waiting_response_radios()
        if not waiting_radios:
            self._comms_react_start = None  # Prompt resolved, reset for the next
            return

        # Reaction delay (only the first time we look at a pending prompt)
        if self._comms_react_start is None:
            self._comms_react_start = scenario_time
        if (scenario_time - self._comms_react_start) * 1000 < self.comms_reaction_ms:
            return

        # Inter-step tuning interval
        if (scenario_time - self._comms_last_tune) * 1000 < self.comms_tune_interval_ms:
            return
        self._comms_last_tune = scenario_time

        # Tuning logic via key injection, with overshoot
        autoradio = waiting_radios[0]
        active = plugin.get_active_radio_dict()

        key = self.compute_comms_action(active, autoradio, plugin.parameters["keys"])
        self.send_key(plugin, key)
        # Overshoot on frequency tuning only
        if (
            active == autoradio
            and round(active["targetfreq"], 1) != round(active["currentfreq"], 1)
            and self._rng.random() < self.comms_overshoot_prob
        ):
            self.send_key(plugin, key)

    def _update_resman(self, plugin: Any, scenario_time: float) -> None:
        if plugin.wait_before_leak > 0:
            return
        if self._attended_task != "resman":
            return  # Tanks drift, pumps unchanged

        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        for _pump_n, this_pump in {p: v for p, v in pumps.items() if v["state"] != "failure"}.items():
            # Per-pump omission error ("slip")
            if self._rng.random() < self.resman_forget_prob:
                continue

            from_tank = tanks[this_pump["_fromtank"]]
            to_tank = tanks[this_pump["_totank"]]

            # Noisy threshold (gaussian noise on the +-50 threshold)
            noise = self._rng.gauss(0, self.resman_threshold_noise)

            desired = DefaultAgent._compute_desired_pump_state(
                this_pump,
                from_tank,
                to_tank,
                threshold_noise=noise,
            )
            if desired is not None and desired != this_pump["state"]:
                self.send_key(plugin, this_pump["key"])  # Toggle pump
