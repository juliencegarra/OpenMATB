# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""STOM (Strategic Task Overload Management) agent for the AF-MATB.

Based on: Wickens, Gutzwiller & Clegg (2014) — "Workload overload modeling:
An experiment with MATB II to inform a computational model of task management."

The STOM model uses a two-decision process for task switching:

  Decision 1 — Stay/Switch:  Should the operator stay on the ongoing task (OT)
      or switch?  There is an inherent bias toward staying (~60% of the time),
      reflecting "task inertia" or switch avoidance (Wickens et al., 2014).

  Decision 2 — Target Selection:  If switching, which alternative task (AT)
      should be chosen?  Selection is utility-driven via softmax over task
      attributes: difficulty, priority, interest, and salience.

Key empirical findings the model reproduces:
  - ~60% switch avoidance (95% CI [58–62%])
  - ~13% fewer switches when OT is difficult vs easy
  - 67% Comm preference over Rman (easier + auditory salience)
  - Monitoring (sysmon) consistently unfavoured across all attributes
  - Priority affects time-on-task allocation, not switch frequency directly
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent

# ── Task attribute ratings ───────────────────────────────────


@dataclass
class TaskAttributes:
    """Static STOM attribute ratings for a single task.

    Values are normalised from the paper's Table 2 subjective ratings
    (originally on a ~[-5, +5] scale) to approximately [-1, +1].
    """

    priority: float  # Higher = more important
    interest: float  # Higher = more engaging
    difficulty: float  # Higher = harder (negative weight applied in utility)
    salience: float  # Base salience level [0, 1], modulated by events


@dataclass
class TaskState:
    """Runtime state for a single STOM task."""

    alias: str
    attributes: TaskAttributes
    event_salience: float = 0.0  # Transient salience from recent events
    event_salience_start: float = 0.0  # When the latest event salience boost started
    last_attended_t: float = 0.0  # Last time this task was attended
    dynamic_difficulty: float | None = None  # Override difficulty (tracking only)


# Equal priority condition (Table 2, normalised from [-5, +5] to [-1, +1])
EQUAL_PRIORITY_ATTRIBUTES: dict[str, TaskAttributes] = {
    "sysmon": TaskAttributes(
        priority=-0.63,  # -3.13 / 5 — lowest priority
        interest=-0.78,  # -3.91 / 5 — least interesting
        difficulty=-0.58,  # -2.91 / 5 — easy, but unfavoured
        salience=0.30,  # Visual-only, moderate base salience
    ),
    "track": TaskAttributes(
        priority=0.11,  # 0.53 / 5 — medium
        interest=0.13,  # 0.66 / 5 — medium
        difficulty=0.05,  # 0.25 / 5 — medium, dynamically modulated
        salience=0.10,  # Continuous task, no discrete events
    ),
    "resman": TaskAttributes(
        priority=0.53,  # 2.65 / 5 — highest priority
        interest=0.67,  # 3.34 / 5 — most interesting
        difficulty=0.94,  # 4.69 / 5 — hardest
        salience=0.40,  # Visual events (tank deviations, pump failures)
    ),
    "communications": TaskAttributes(
        priority=0.01,  # 0.06 / 5 — medium-low
        interest=-0.02,  # -0.09 / 5 — slightly boring
        difficulty=-0.41,  # -2.03 / 5 — easy
        salience=0.70,  # AUDITORY modality — highest base salience
    ),
}

# Tracking priority condition: track priority boosted, others adjusted
TRACKING_PRIORITY_ATTRIBUTES: dict[str, TaskAttributes] = {
    "sysmon": TaskAttributes(
        priority=-0.80,  # -3.98 / 5
        interest=-0.86,  # -4.29 / 5
        difficulty=-0.71,  # -3.56 / 5
        salience=0.30,
    ),
    "track": TaskAttributes(
        priority=1.28,  # 6.41 / 5 — very high priority
        interest=0.98,  # 4.88 / 5
        difficulty=0.54,  # 2.71 / 5
        salience=0.10,
    ),
    "resman": TaskAttributes(
        priority=-0.05,  # -0.24 / 5
        interest=0.30,  # 1.51 / 5
        difficulty=0.62,  # 3.10 / 5
        salience=0.40,
    ),
    "communications": TaskAttributes(
        priority=-0.44,  # -2.20 / 5
        interest=-0.42,  # -2.10 / 5
        difficulty=-0.45,  # -2.24 / 5
        salience=0.70,
    ),
}


# ── Agent ────────────────────────────────────────────────────


class STOMAgent(AbstractAgent):
    """Wickens et al. (2014) STOM model agent.

    Implements a utility-based two-decision task switching model:
    1) Stay on the ongoing task (OT) with ~60% bias (switch avoidance)
    2) If switching, select the alternative task (AT) via softmax over utilities

    Task utility combines difficulty (easy preferred), priority, interest,
    and salience (boosted by recent events, especially auditory).
    """

    # ── Per-task action constants (reused from HumanLikeAgent/CarbonellAgent) ──

    SYSMON_RT_MEAN = 2500  # Mean reaction time for sysmon failures (ms)
    SYSMON_RT_STD = 800  # RT standard deviation (log-normal)
    VIGILANCE_DECREMENT = 50  # ms added to RT per failure (Mackworth effect)

    TRACK_GAIN = 4.0  # Proportional gain for joystick compensation
    TRACK_SETTLE_MS = 2000  # Time to maintain minimum force after target entry
    TRACK_SETTLE_FORCE = 0.3  # Minimum force during settling
    TRACK_NOISE_PROB = 0.15  # Per-frame probability of micro-hesitation

    COMMS_REACTION_MS = 1500  # Comprehension + planning + motor initiation
    COMMS_TUNE_INTERVAL_MS = 200  # Interval between frequency tuning steps
    COMMS_OVERSHOOT_PROB = 0.10  # Probability of overshooting target frequency

    RESMAN_THRESHOLD_NOISE = 75  # Gaussian std on pump decision thresholds
    RESMAN_FORGET_PROB = 0.05  # Per-pump omission error probability

    # Switching cost
    SWITCHING_COST_MS = 300  # Cognitive switching cost (Monsell, 2003)

    # Bottom-up attention capture
    ATTENTION_CAPTURE_PROB = 0.6  # Probability of sysmon failure capturing attention

    def __init__(
        self,
        seed: int | None = None,
        priority_mode: str = "equal",
        w_difficulty: float = 0.30,
        w_priority: float = 0.25,
        w_interest: float = 0.20,
        w_salience: float = 0.40,
        softmax_temperature: float = 0.35,
        switch_avoidance_bias: float = 0.60,
        decision_interval_ms: float = 2000,
        event_salience_boost: float = 0.80,
        event_salience_decay_ms: float = 5000,
        comms_salience_multiplier: float = 1.5,
    ) -> None:
        super().__init__(name="stom", automode_string="AUTO-STOM")
        self._rng = random.Random(seed)
        self.show_attention: bool = True

        # STOM model parameters
        self.w_difficulty = w_difficulty
        self.w_priority = w_priority
        self.w_interest = w_interest
        self.w_salience = w_salience
        self.softmax_temperature = softmax_temperature
        self.switch_avoidance_bias = switch_avoidance_bias
        self.decision_interval_ms = decision_interval_ms
        self.event_salience_boost = event_salience_boost
        self.event_salience_decay_ms = event_salience_decay_ms
        self.comms_salience_multiplier = comms_salience_multiplier
        self.priority_mode = priority_mode

        # Load task attributes based on priority mode
        attrs = TRACKING_PRIORITY_ATTRIBUTES if priority_mode == "tracking" else EQUAL_PRIORITY_ATTRIBUTES
        self._tasks: dict[str, TaskState] = {
            alias: TaskState(
                alias=alias,
                attributes=TaskAttributes(
                    priority=a.priority,
                    interest=a.interest,
                    difficulty=a.difficulty,
                    salience=a.salience,
                ),
            )
            for alias, a in attrs.items()
        }

        # Attention state
        self._attended_task: str = "track"  # Start on continuous tracking task
        self._last_decision_t: float = 0.0
        self._switching_until: float = 0.0

        # Active plugins: alias → last time on_plugin_update was called
        self._active_aliases: dict[str, float] = {}

        # Event tracking (for detecting new events and boosting salience)
        self._known_sysmon_failures: set[str] = set()
        self._known_comms_waiting: set[int] = set()
        self._known_resman_failures: set[str] = set()

        # Per-task motor state
        self._failure_count: int = 0
        self._track_react_start: float | None = None
        self._track_last_outside: float | None = None
        self._comms_react_start: float | None = None
        self._comms_last_tune: float = 0.0

    # ── Utility computation ──────────────────────────────────

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Sigmoid function clamped to avoid overflow."""
        x = max(-10.0, min(10.0, x))
        return 1.0 / (1.0 + math.exp(-x))

    def _get_current_salience(self, task: TaskState, scenario_time: float) -> float:
        """Compute current salience = base + decaying event salience.

        Event salience decays linearly over event_salience_decay_ms.
        Communications gets an extra multiplier (auditory modality).
        """
        base = task.attributes.salience
        if task.event_salience <= 0:
            return base

        elapsed_ms = (scenario_time - task.event_salience_start) * 1000
        decay_factor = max(0.0, 1.0 - elapsed_ms / self.event_salience_decay_ms)
        event_sal = task.event_salience * decay_factor

        # Communications has auditory salience — stronger boost
        if task.alias == "communications":
            event_sal *= self.comms_salience_multiplier

        return base + event_sal

    def _get_difficulty(self, task: TaskState) -> float:
        """Return current difficulty, using dynamic override for tracking."""
        if task.dynamic_difficulty is not None:
            return task.dynamic_difficulty
        return task.attributes.difficulty

    def compute_task_utility(self, task: TaskState, scenario_time: float) -> float:
        """Compute the STOM utility for a task.

        U(task) = w_d * (-difficulty) + w_p * priority + w_i * interest + w_s * salience

        Easier tasks get higher utility (negative weight on difficulty).
        Higher priority, interest, and salience increase utility.
        """
        difficulty = self._get_difficulty(task)
        salience = self._get_current_salience(task, scenario_time)

        return (
            self.w_difficulty * (-difficulty)
            + self.w_priority * task.attributes.priority
            + self.w_interest * task.attributes.interest
            + self.w_salience * salience
        )

    # ── Decision cycle ───────────────────────────────────────

    def _is_plugin_active(self, alias: str, t: float) -> bool:
        """A plugin is active if it called on_plugin_update recently."""
        last_seen = self._active_aliases.get(alias)
        if last_seen is None:
            return False
        return (t - last_seen) < 1.0

    def _make_switch_decision(self, scenario_time: float) -> None:
        """STOM two-decision cycle.

        Decision 1: Stay on OT with probability ~60%, modulated by
                    relative utility of OT vs best alternative.
        Decision 2: If switching, select AT via softmax over utilities.
        """
        ot = self._tasks.get(self._attended_task)
        if ot is None:
            return

        u_ot = self.compute_task_utility(ot, scenario_time)

        # Gather active alternative tasks
        alternatives: dict[str, float] = {}
        for alias, task in self._tasks.items():
            if alias != self._attended_task and self._is_plugin_active(alias, scenario_time):
                alternatives[alias] = self.compute_task_utility(task, scenario_time)

        if not alternatives:
            return  # No alternatives available — stay on OT

        u_max_alt = max(alternatives.values())

        # Decision 1: Stay probability
        # Base bias = 0.60 (paper's meta-analysis: 95% CI [58-62%])
        # Modulated by utility difference: high OT utility → more likely to stay
        utility_diff = u_ot - u_max_alt
        p_stay = self.switch_avoidance_bias + 0.1 * self._sigmoid(utility_diff)
        p_stay = max(0.1, min(0.95, p_stay))

        if self._rng.random() < p_stay:
            return  # STAY on OT

        # Decision 2: Select AT via softmax
        self._switch_to_softmax(alternatives, scenario_time)

    def _switch_to_softmax(self, utilities: dict[str, float], scenario_time: float) -> None:
        """Select alternative task using softmax probability distribution.

        P(AT_i) = exp(U_i / T) / sum(exp(U_j / T))
        where T = softmax_temperature (lower = more deterministic).
        """
        tasks = list(utilities.keys())
        values = [utilities[t] for t in tasks]
        max_v = max(values)  # Numerical stability

        exps = [math.exp((v - max_v) / self.softmax_temperature) for v in values]
        total = sum(exps)
        probs = [e / total for e in exps]

        # Weighted random selection
        r = self._rng.random()
        cumulative = 0.0
        for task, prob in zip(tasks, probs):
            cumulative += prob
            if r <= cumulative:
                self._switch_to(task, scenario_time)
                return
        # Fallback (floating-point rounding)
        self._switch_to(tasks[-1], scenario_time)

    def _switch_to(self, alias: str, scenario_time: float) -> None:
        """Switch attention to a new task with switching cost."""
        self._attended_task = alias
        self._switching_until = scenario_time + self.SWITCHING_COST_MS / 1000
        self._tasks[alias].last_attended_t = scenario_time
        # Reset per-task motor states for the new task
        self._track_react_start = None

    # ── Event monitoring (parallel, regardless of attention) ──

    def _boost_event_salience(self, alias: str, scenario_time: float) -> None:
        """Temporarily boost salience when a new event arrives."""
        task = self._tasks.get(alias)
        if task is None:
            return
        task.event_salience = self.event_salience_boost
        task.event_salience_start = scenario_time

    def _monitor_events(self, plugin: Any, scenario_time: float) -> None:
        """Monitor for new events on any task, regardless of attention.

        Runs every frame. Detects new failures/prompts and boosts the
        corresponding task's event salience.
        """
        alias = plugin.alias

        if alias == "sysmon":
            failures = plugin.get_gauges_on_failure()
            current_keys = {g["key"] for g in failures}
            new_keys = current_keys - self._known_sysmon_failures
            if new_keys:
                self._boost_event_salience("sysmon", scenario_time)
            self._known_sysmon_failures = current_keys

        elif alias == "communications":
            waiting = plugin.get_waiting_response_radios()
            current_pos = {r["pos"] for r in waiting}
            new_pos = current_pos - self._known_comms_waiting
            if new_pos:
                # Communications has auditory salience — always detected
                self._boost_event_salience("communications", scenario_time)
            self._known_comms_waiting = current_pos

        elif alias == "resman":
            pumps = plugin.parameters["pump"]
            current_failures = {k for k, p in pumps.items() if p["state"] == "failure"}
            new_failures = current_failures - self._known_resman_failures
            if new_failures:
                self._boost_event_salience("resman", scenario_time)
            self._known_resman_failures = current_failures

    # ── Dynamic tracking difficulty ──────────────────────────

    def _update_tracking_difficulty(self, plugin: Any) -> None:
        """Update tracking difficulty dynamically based on cursor deviation.

        Cursor far from center → higher difficulty → lower utility → fewer
        switches toward tracking (reproducing the paper's 13% fewer switches
        under difficult tracking). Exponential smoothing prevents jitter.
        """
        cx, cy = plugin.reticle.cursor_relative
        half_w = plugin.reticle.container.w / 2
        half_h = plugin.reticle.container.h / 2
        norm_dist = math.sqrt((cx / half_w) ** 2 + (cy / half_h) ** 2)

        task = self._tasks["track"]
        base_difficulty = task.attributes.difficulty
        raw_dynamic = base_difficulty + norm_dist * 0.5

        alpha = 0.05  # Smoothing factor
        if task.dynamic_difficulty is None:
            task.dynamic_difficulty = raw_dynamic
        else:
            task.dynamic_difficulty = alpha * raw_dynamic + (1 - alpha) * task.dynamic_difficulty

    # ── Log-normal sampling ──────────────────────────────────

    @staticmethod
    def _log_normal_params(mean: float, std: float) -> tuple[float, float]:
        """Convert desired mean/std (ms) to log-normal mu/sigma parameters."""
        variance = std * std
        mu = math.log(mean * mean / math.sqrt(variance + mean * mean))
        sigma = math.sqrt(math.log(1 + variance / (mean * mean)))
        return mu, sigma

    def _sample_rt(self, mean: float, std: float) -> float:
        """Sample a reaction time (ms) from a log-normal distribution."""
        mu, sigma = self._log_normal_params(mean, std)
        return self._rng.lognormvariate(mu, sigma)

    # ── Per-task action handlers ─────────────────────────────

    def _act_sysmon(self, plugin: Any, scenario_time: float) -> None:
        """Respond to sysmon failures when attended.

        Uses log-normal RT with vigilance decrement (Mackworth effect):
        RT increases by VIGILANCE_DECREMENT ms per detected failure.
        """
        failures = plugin.get_gauges_on_failure()
        if not failures:
            return

        rt = self._sample_rt(
            self.SYSMON_RT_MEAN + self._failure_count * self.VIGILANCE_DECREMENT,
            self.SYSMON_RT_STD,
        )

        for gauge in failures:
            if gauge["_response_start"] is not None and (plugin.scenario_time - gauge["_response_start"]) * 1000 >= rt:
                self.send_key(plugin, gauge["key"])

    def _act_track(self, plugin: Any, scenario_time: float) -> None:
        """Proportional joystick compensation when tracking is attended.

        Includes reaction delay, micro-hesitations, and settling phase.
        """
        reticle = plugin.reticle

        # Reaction delay: detect cursor leaving target zone
        if reticle.is_cursor_in_target():
            self._track_react_start = None
        elif self._track_react_start is None:
            self._track_react_start = scenario_time

        if self._track_react_start is not None:
            track_reaction_ms = 400  # Visuomotor reaction time
            if (scenario_time - self._track_react_start) * 1000 < track_reaction_ms:
                return

        # Motor noise: micro-hesitation (no compensation this frame)
        if self._rng.random() < self.TRACK_NOISE_PROB:
            return

        # Proportional compensation: force proportional to distance from center
        cx, cy = reticle.cursor_relative
        half_w = reticle.container.w / 2
        half_h = reticle.container.h / 2

        in_target = reticle.is_cursor_in_target()
        if not in_target:
            self._track_last_outside = scenario_time

        jx, jy = self.compute_tracking_compensation(
            cx,
            cy,
            half_w,
            half_h,
            gain=self.TRACK_GAIN,
            settle_force=self.TRACK_SETTLE_FORCE,
            settle_ms=self.TRACK_SETTLE_MS,
            last_outside_time=self._track_last_outside,
            current_time=scenario_time,
        )
        self.send_joystick(plugin, jx, jy)

    def _act_comms(self, plugin: Any, scenario_time: float) -> None:
        """Navigate, tune and validate radio communications when attended.

        Includes comprehension delay, inter-step tuning interval, and
        overshoot probability (Fitts' law).
        """
        waiting_radios = plugin.get_waiting_response_radios()
        if not waiting_radios:
            self._comms_react_start = None
            return

        # Reaction delay (comprehension + planning + motor initiation)
        if self._comms_react_start is None:
            self._comms_react_start = scenario_time
        if (scenario_time - self._comms_react_start) * 1000 < self.COMMS_REACTION_MS:
            return

        # Inter-step tuning interval
        if (scenario_time - self._comms_last_tune) * 1000 < self.COMMS_TUNE_INTERVAL_MS:
            return
        self._comms_last_tune = scenario_time

        autoradio = waiting_radios[0]
        active = plugin.get_active_radio_dict()

        key = self.compute_comms_action(active, autoradio, plugin.parameters["keys"])
        self.send_key(plugin, key)
        # Overshoot on frequency tuning (Fitts' law)
        if (
            active == autoradio
            and round(active["targetfreq"], 1) != round(active["currentfreq"], 1)
            and self._rng.random() < self.COMMS_OVERSHOOT_PROB
        ):
            self.send_key(plugin, key)

    def _act_resman(self, plugin: Any, scenario_time: float) -> None:
        """Manage resman pumps using DefaultAgent heuristics when attended.

        Includes Gaussian threshold noise and per-pump omission errors.
        """
        if plugin.wait_before_leak > 0:
            return

        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        for _pump_n, this_pump in {p: v for p, v in pumps.items() if v["state"] != "failure"}.items():
            # Motor error: omission slip (Reason, 1990)
            if self._rng.random() < self.RESMAN_FORGET_PROB:
                continue

            from_tank = tanks[this_pump["_fromtank"]]
            to_tank = tanks[this_pump["_totank"]]

            noise = self._rng.gauss(0, self.RESMAN_THRESHOLD_NOISE)
            desired = DefaultAgent._compute_desired_pump_state(
                this_pump,
                from_tank,
                to_tank,
                threshold_noise=noise,
            )
            if desired is not None and desired != this_pump["state"]:
                self.send_key(plugin, this_pump["key"])

    # ── Main callbacks ───────────────────────────────────────

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias

        # 0. Register this plugin as active
        self._active_aliases[alias] = scenario_time

        # 1. Update dynamic difficulty if tracking
        if alias == "track":
            self._update_tracking_difficulty(plugin)

        # 2. Monitor for new events (parallel, regardless of attention)
        self._monitor_events(plugin, scenario_time)

        # 3. Decision cycle (time-based, runs at most once per interval)
        elapsed_since_decision = (scenario_time - self._last_decision_t) * 1000
        if elapsed_since_decision >= self.decision_interval_ms:
            self._make_switch_decision(scenario_time)
            self._last_decision_t = scenario_time

        # 4. Switching cost: do nothing during cognitive transition
        if scenario_time < self._switching_until:
            return

        # 5. Only act on the attended task
        if alias != self._attended_task:
            return

        # 6. Dispatch to per-task action handler
        if alias == "sysmon":
            self._act_sysmon(plugin, scenario_time)
        elif alias == "track":
            self._act_track(plugin, scenario_time)
        elif alias == "communications":
            self._act_comms(plugin, scenario_time)
        elif alias == "resman":
            self._act_resman(plugin, scenario_time)

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        """Handle sysmon failure onset.

        Boosts sysmon event salience and may capture attention via
        bottom-up interrupt (stochastic, prob=0.6).
        """
        self._boost_event_salience("sysmon", plugin.scenario_time)
        self._failure_count += 1

        # Bottom-up attention capture: interrupt current task
        if self._attended_task != "sysmon" and self._rng.random() < self.ATTENTION_CAPTURE_PROB:
            self._switch_to("sysmon", plugin.scenario_time)

        return {"delay": plugin.parameters["alerttimeout"]}
