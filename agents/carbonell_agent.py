# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Carbonell (1966) queueing-model agent for the AF-MATB.

Based on: Carbonell (1966) — "A Queueing Model of Many-Instrument
Visual Sampling".

The model uses cost-driven visual allocation: at each cycle, the agent
attends the instrument whose marginal cost Ci * Pi(t) / (1 - Pi(t))
is maximal, where Pi(t) is the conditional probability of exceeding
a risk threshold since the last observation.

Aspects not covered by the 1966 model (motor time, motor errors,
switching cost, bottom-up capture, vigilance decrement, auditory
channel) are implemented as independently toggleable extensions.
When all toggles are False, the agent is a pure Carbonell model.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent

# ── Instrument state ──────────────────────────────────────────


@dataclass
class InstrumentState:
    """State of a single Carbonell instrument."""

    id: str  # e.g. "sysmon_scale_1"
    plugin_alias: str  # e.g. "sysmon"
    cost: float  # Ci — unit cost (Carbonell)
    threshold: float  # Li — normalised risk threshold
    sigma_0: float  # σ0 — base noise
    divergence: float  # H — uncertainty growth rate
    decay_rate: float  # Ki — control decay rate
    last_sampled_t: float = 0.0  # time of last observation
    last_observed_value: float = 0.0  # YOi — last read value
    last_control_t: float = 0.0  # time of last control action
    is_binary: bool = False  # True for lights/comms (exponential P)
    # Computed each cycle:
    delta_t: float = 0.0
    variance: float = 0.0
    probability: float = 0.0
    marginal_cost: float = 0.0
    fault_onset_t: float | None = None  # Time when current fault was first detected


# ── Phase state machine ──────────────────────────────────────


class _Phase(Enum):
    IDLE = "idle"
    READING = "reading"  # Observation (333ms) — only if motor_time=True
    ACTING = "acting"  # Motor execution (250ms/step) — only if motor_time=True
    SWITCHING = "switching"  # Switch cost (150ms) — only if switching_cost=True


# ── Agent ─────────────────────────────────────────────────────


class CarbonellAgent(AbstractAgent):
    """Carbonell (1966) queueing-model agent with toggleable extensions."""

    # ── Constants (used only when the corresponding toggle is True) ──

    # motor_time
    READING_TIME_S = 0.333
    MOTOR_EXEC_S = 0.250
    COMMS_TUNE_INTERVAL_S = 0.200

    # motor_errors
    TRACK_NOISE_STD = 0.03
    RESMAN_FORGET_PROB = 0.05
    COMMS_OVERSHOOT_PROB = 0.10

    # switching_cost
    SWITCHING_COST_S = 0.150

    # bottom_up
    BU_INTERRUPT_PROB = 0.6
    BU_COST_MULTIPLIER = 3.0
    BU_BOOST_DURATION_S = 5.0
    BU_TRACK_THRESHOLD = 0.5  # normalised cursor distance for bottom-up
    BU_RESMAN_THRESHOLD = 500  # tank level deviation for bottom-up

    # vigilance_decrement
    VIGILANCE_DECAY_RATE = 0.001

    # auditory_channel
    COMMS_AUDIO_COST_BOOST = 3.0

    # fault_cost_growth
    FAULT_COST_GROWTH_RATE = 0.5  # α in Ci × (1 + α × ln(1 + duration))

    # ── Always-active constants (concrete control) ──

    TRACK_GAIN = 4.0
    TRACK_SETTLE_MS = 2000
    TRACK_SETTLE_FORCE = 0.3
    RESMAN_THRESHOLD_NOISE = 75
    COMMS_REACTION_S = 1.5

    def __init__(
        self,
        seed: int | None = None,
        motor_time: bool = False,
        motor_errors: bool = False,
        switching_cost: bool = False,
        bottom_up: bool = False,
        vigilance_decrement: bool = False,
        auditory_channel: bool = False,
        fault_cost_growth: bool = False,
    ) -> None:
        super().__init__(name="carbonell", automode_string="AUTO-CB")
        self._rng = random.Random(seed)
        self.show_attention = True

        # Extension toggles
        self.motor_time = motor_time
        self.motor_errors = motor_errors
        self.switching_cost = switching_cost
        self.bottom_up = bottom_up
        self.vigilance_decrement = vigilance_decrement
        self.auditory_channel = auditory_channel
        self.fault_cost_growth = fault_cost_growth

        # State machine (only used if motor_time or switching_cost)
        self._phase = _Phase.IDLE
        self._phase_start: float = 0.0
        self._current_instrument: InstrumentState | None = None
        self._action_queue: list[tuple[str, Any]] = []  # (action_type, data)

        # Bottom-up state (only if bottom_up)
        self._bu_boost_until: dict[str, float] = {}

        # Comms audio state (only if auditory_channel)
        self._comms_known_waiting: set[int] = set()
        self._comms_audio_boost_until: float = 0.0

        # Track state (always needed for settling)
        self._track_last_outside: float | None = None

        # Active plugins: alias → last time on_plugin_update was called.
        # Only instruments whose plugin called recently are eligible for selection.
        self._active_aliases: dict[str, float] = {}

        # Instruments
        self._instruments: dict[str, InstrumentState] = {}
        self._init_instruments()

    # ── Instrument initialisation ─────────────────────────────

    def _init_instruments(self) -> None:
        """Create the 10 instrument states with default parameters.

        Parameters are calibrated so that all instruments reach competitive
        marginal costs within a few seconds of not being observed.  Key
        constraint: MC(resman) ~ 1.0 at dt=5s, MC(comms) ~ 2.0 at dt=3s.
        """
        specs = [
            #  id, alias, Ci, Li, σ0, H, Ki, binary
            # Sysmon scales 1-4 (σ0 raised so P reaches ~0.20 at dt=5s)
            ("sysmon_scale_1", "sysmon", 3.0, 0.4, 0.25, 0.5, 2.0, False),
            ("sysmon_scale_2", "sysmon", 3.0, 0.4, 0.25, 0.5, 2.0, False),
            ("sysmon_scale_3", "sysmon", 3.0, 0.4, 0.25, 0.5, 2.0, False),
            ("sysmon_scale_4", "sysmon", 3.0, 0.4, 0.25, 0.5, 2.0, False),
            # Sysmon lights 1-2
            ("sysmon_light_1", "sysmon", 4.0, 0.5, 0.10, 0.3, 5.0, True),
            ("sysmon_light_2", "sysmon", 4.0, 0.5, 0.10, 0.3, 5.0, True),
            # Tracking
            ("tracking", "track", 5.0, 0.25, 0.20, 1.0, 1.5, False),
            # Resman tanks A/B (σ0, H raised so P > 0 at moderate dt)
            ("resman_a", "resman", 2.0, 0.5, 0.50, 0.8, 0.5, False),
            ("resman_b", "resman", 2.0, 0.5, 0.50, 0.8, 0.5, False),
            # Communications (rate raised so MC competitive at dt=3s)
            ("comms", "communications", 3.5, 0.5, 0.05, 0.3, 10.0, True),
        ]
        for id_, alias, cost, thresh, sigma, div, decay, binary in specs:
            self._instruments[id_] = InstrumentState(
                id=id_,
                plugin_alias=alias,
                cost=cost,
                threshold=thresh,
                sigma_0=sigma,
                divergence=div,
                decay_rate=decay,
                is_binary=binary,
            )

    # ── Carbonell math ────────────────────────────────────────

    @staticmethod
    def _norm_cdf(z: float) -> float:
        """Standard normal CDF via erfc (no scipy dependency)."""
        return 0.5 * math.erfc(-z / math.sqrt(2))

    def _compute_probability(self, inst: InstrumentState, t: float) -> float:
        """Compute P[y_i(t) >= L_i | last read = YO_i].

        For continuous instruments: Gaussian CDF with growing variance.
        For binary instruments: 1 - exp(-lambda * delta_t).

        **Persistence rule**: if the last observation showed the instrument
        already exceeding its threshold (active failure, radio waiting,
        tank deviated), the agent *knows* it still needs attention.
        Probability is floored at 0.9 so the agent stays on the task
        until the issue is resolved (multi-step comms, resman pumps, etc.).
        """
        inst.delta_t = max(0.0, t - inst.last_sampled_t)

        if inst.is_binary:
            # Exponential model for binary events (lights, comms)
            lam = inst.divergence  # Use divergence as rate parameter
            p = 1.0 - math.exp(-lam * inst.delta_t)
        else:
            # Gaussian model: variance grows with time since last observation
            dt = inst.delta_t
            if dt <= 0:
                inst.variance = inst.sigma_0**2
                p = 0.0
            else:
                # σ²(t) = σ0² * (1 + H * dt)
                inst.variance = inst.sigma_0**2 * (1.0 + inst.divergence * dt)

                # Expected value decays toward 0 with control
                dt_ctrl = max(0.0, t - inst.last_control_t)
                expected = inst.last_observed_value * math.exp(-inst.decay_rate * dt_ctrl)

                # P[y >= L] = 1 - Φ((L - E[y]) / σ)
                sigma = math.sqrt(inst.variance) if inst.variance > 0 else 1e-10
                z = (inst.threshold - abs(expected)) / sigma
                p = 1.0 - self._norm_cdf(z)

        # Persistence: if we already observed the instrument exceeding its
        # threshold, we KNOW it needs attention — keep probability high so
        # the agent finishes multi-step actions before switching away.
        if inst.last_observed_value >= inst.threshold:
            p = max(p, 0.9)

        inst.probability = p
        return p

    def _compute_marginal_cost(self, inst: InstrumentState) -> float:
        """Ci * Pi / (1 - Pi) — marginal cost of NOT observing instrument i."""
        p = inst.probability
        if p >= 1.0:
            inst.marginal_cost = inst.cost * 1e6  # Very high but finite
        elif p <= 0.0:
            inst.marginal_cost = 0.0
        else:
            inst.marginal_cost = inst.cost * p / (1.0 - p)
        return inst.marginal_cost

    # ── Instrument selection ──────────────────────────────────

    def _is_plugin_active(self, alias: str, t: float) -> bool:
        """A plugin is active if it called on_plugin_update recently."""
        last_seen = self._active_aliases.get(alias)
        if last_seen is None:
            return False
        return (t - last_seen) < 1.0  # 1 second staleness threshold

    def _select_instrument(self, t: float) -> InstrumentState:
        """Select the instrument with maximum marginal cost.

        Only considers instruments whose plugin is currently active
        (i.e., calling on_plugin_update each frame).
        """
        best: InstrumentState | None = None
        best_cost = -1.0

        for inst in self._instruments.values():
            # Skip instruments whose plugin is not running
            if not self._is_plugin_active(inst.plugin_alias, t):
                continue

            self._compute_probability(inst, t)

            # Vigilance decrement: scale costs by 1/(1 + rate * t)
            effective_cost = inst.cost
            if self.vigilance_decrement:
                effective_cost *= 1.0 / (1.0 + self.VIGILANCE_DECAY_RATE * t)

            # Fault duration cost growth (replaces fixed bottom-up boost)
            if self.fault_cost_growth and inst.fault_onset_t is not None:
                duration = t - inst.fault_onset_t
                effective_cost *= 1.0 + self.FAULT_COST_GROWTH_RATE * math.log1p(duration)
            # Fixed bottom-up boost (legacy, disabled when fault_cost_growth is active)
            elif self.bottom_up and inst.id in self._bu_boost_until:
                if t < self._bu_boost_until[inst.id]:
                    effective_cost *= self.BU_COST_MULTIPLIER
                else:
                    del self._bu_boost_until[inst.id]

            # Compute marginal cost with (possibly modified) effective cost
            p = inst.probability
            if p >= 1.0:
                mc = effective_cost * 1e6
            elif p <= 0.0:
                mc = 0.0
            else:
                mc = effective_cost * p / (1.0 - p)
            inst.marginal_cost = mc

            # Auditory channel: boost comms cost if audio prompt recently heard
            if self.auditory_channel and inst.id == "comms":
                if t < self._comms_audio_boost_until:
                    mc *= self.COMMS_AUDIO_COST_BOOST
                    inst.marginal_cost = mc

            if mc > best_cost:
                best_cost = mc
                best = inst

        # best can be None only if no plugin is active (shouldn't happen
        # since we're called from on_plugin_update, but guard anyway)
        if best is None:
            # Fallback: return tracking instrument
            return self._instruments["tracking"]
        return best

    # ── Attention property for the visual indicator ───────────

    @property
    def _attended_task(self) -> str | None:
        """Plugin alias for the currently attended instrument.
        Used by abstractplugin to render the attention border."""
        if self._current_instrument is not None:
            return self._current_instrument.plugin_alias
        return None

    # ── Observation methods ───────────────────────────────────

    def _observe_sysmon_scale(self, plugin: Any, inst: InstrumentState, t: float) -> bool:
        """Observe a sysmon scale. Returns True if action needed."""
        # Extract scale index from id: "sysmon_scale_1" → index 0
        idx = int(inst.id.split("_")[-1]) - 1
        scales = plugin.get_scale_gauges()
        if idx >= len(scales):
            return False
        gauge = scales[idx]
        # Normalised deviation: |pos - 5| / 10 (scale 0-10, center=5)
        pos = gauge.get("_pos", 5)
        inst.last_observed_value = abs(pos - 5) / 10.0
        inst.last_sampled_t = t
        if not gauge.get("_onfailure", False):
            inst.fault_onset_t = None
        return gauge.get("_onfailure", False)

    def _observe_sysmon_light(self, plugin: Any, inst: InstrumentState, t: float) -> bool:
        """Observe a sysmon light. Returns True if action needed."""
        idx = int(inst.id.split("_")[-1]) - 1
        lights = plugin.get_light_gauges()
        if idx >= len(lights):
            return False
        gauge = lights[idx]
        on_failure = gauge.get("_onfailure", False)
        inst.last_observed_value = 1.0 if on_failure else 0.0
        inst.last_sampled_t = t
        if not on_failure:
            inst.fault_onset_t = None
        return on_failure

    def _observe_tracking(self, plugin: Any, inst: InstrumentState, t: float) -> bool:
        """Observe tracking. Returns True if cursor needs compensation."""
        cx, cy = plugin.reticle.cursor_relative
        half_w = plugin.reticle.container.w / 2
        half_h = plugin.reticle.container.h / 2
        # Normalise to [0, 1] range
        norm_dist = math.sqrt((cx / half_w) ** 2 + (cy / half_h) ** 2)
        inst.last_observed_value = norm_dist
        inst.last_sampled_t = t
        in_target = plugin.reticle.is_cursor_in_target()
        if in_target:
            inst.fault_onset_t = None
        # Always compensate — tracking is continuous, even small offsets
        # accumulate if left uncorrected
        return not in_target

    def _observe_resman(self, plugin: Any, inst: InstrumentState, t: float) -> float:
        """Observe a resman tank. Returns normalised deviation."""
        tank_letter = inst.id.split("_")[-1]  # "resman_a" → "a"
        tanks = plugin.parameters["tank"]
        tank = tanks[tank_letter]
        if tank["target"] is None:
            inst.last_observed_value = 0.0
            inst.last_sampled_t = t
            return 0.0
        tolerance = 50  # Default tolerance from resman heuristics
        deviation = abs(tank["level"] - tank["target"]) / max(tolerance, 1)
        inst.last_observed_value = deviation
        inst.last_sampled_t = t
        if deviation < 1.0:
            inst.fault_onset_t = None
        return deviation

    def _observe_comms(self, plugin: Any, inst: InstrumentState, t: float) -> bool:
        """Observe communications. Returns True if radio waiting."""
        waiting = plugin.get_waiting_response_radios()
        has_waiting = len(waiting) > 0
        inst.last_observed_value = 1.0 if has_waiting else 0.0
        inst.last_sampled_t = t
        if not has_waiting:
            inst.fault_onset_t = None
        return has_waiting

    def _observe_instrument(self, plugin: Any, inst: InstrumentState, t: float) -> Any:
        """Dispatch observation to the correct method. Returns action-needed signal."""
        if inst.id.startswith("sysmon_scale_"):
            return self._observe_sysmon_scale(plugin, inst, t)
        elif inst.id.startswith("sysmon_light_"):
            return self._observe_sysmon_light(plugin, inst, t)
        elif inst.id == "tracking":
            return self._observe_tracking(plugin, inst, t)
        elif inst.id.startswith("resman_"):
            return self._observe_resman(plugin, inst, t)
        elif inst.id == "comms":
            return self._observe_comms(plugin, inst, t)
        return None

    # ── Action methods ────────────────────────────────────────

    def _act_sysmon_scale(self, plugin: Any, inst: InstrumentState, t: float) -> None:
        """Respond to a sysmon scale failure."""
        idx = int(inst.id.split("_")[-1]) - 1
        scales = plugin.get_scale_gauges()
        if idx >= len(scales):
            return
        gauge = scales[idx]
        if gauge.get("_onfailure") and gauge.get("_response_start") is not None:
            self.send_key(plugin, gauge["key"])
            inst.last_control_t = t

    def _act_sysmon_light(self, plugin: Any, inst: InstrumentState, t: float) -> None:
        """Respond to a sysmon light failure."""
        idx = int(inst.id.split("_")[-1]) - 1
        lights = plugin.get_light_gauges()
        if idx >= len(lights):
            return
        gauge = lights[idx]
        if gauge.get("_onfailure") and gauge.get("_response_start") is not None:
            self.send_key(plugin, gauge["key"])
            inst.last_control_t = t

    def _act_tracking(self, plugin: Any, inst: InstrumentState, t: float) -> None:
        """Compensate tracking cursor drift with proportional joystick."""
        cx, cy = plugin.reticle.cursor_relative
        half_w = plugin.reticle.container.w / 2
        half_h = plugin.reticle.container.h / 2

        # Track when cursor was last outside target (for settling)
        in_target = plugin.reticle.is_cursor_in_target()
        if not in_target:
            self._track_last_outside = t

        jx, jy = self.compute_tracking_compensation(
            cx,
            cy,
            half_w,
            half_h,
            gain=self.TRACK_GAIN,
            settle_force=self.TRACK_SETTLE_FORCE,
            settle_ms=self.TRACK_SETTLE_MS,
            last_outside_time=self._track_last_outside,
            current_time=t,
        )

        # Motor errors: add Gaussian noise to joystick
        if self.motor_errors:
            jx += self._rng.gauss(0, self.TRACK_NOISE_STD)
            jy += self._rng.gauss(0, self.TRACK_NOISE_STD)
            jx = max(-1.0, min(1.0, jx))
            jy = max(-1.0, min(1.0, jy))

        self.send_joystick(plugin, jx, jy)
        inst.last_control_t = t

    def _act_resman(self, plugin: Any, t: float) -> None:
        """Manage resman pumps using DefaultAgent heuristics."""
        if plugin.wait_before_leak > 0:
            return

        tanks = plugin.parameters["tank"]
        pumps = plugin.parameters["pump"]

        for _pump_n, this_pump in {p: v for p, v in pumps.items() if v["state"] != "failure"}.items():
            # Motor errors: per-pump omission
            if self.motor_errors and self._rng.random() < self.RESMAN_FORGET_PROB:
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

        # Mark both resman instruments as controlled
        for key in ("resman_a", "resman_b"):
            if key in self._instruments:
                self._instruments[key].last_control_t = t

    def _act_comms(self, plugin: Any, inst: InstrumentState, t: float) -> None:
        """Navigate, tune and validate radio communications."""
        waiting_radios = plugin.get_waiting_response_radios()
        if not waiting_radios:
            return

        autoradio = waiting_radios[0]
        active = plugin.get_active_radio_dict()

        key = self.compute_comms_action(active, autoradio, plugin.parameters["keys"])
        self.send_key(plugin, key)
        # Motor errors: overshoot on frequency tuning
        if (
            self.motor_errors
            and active == autoradio
            and round(active["targetfreq"], 1) != round(active["currentfreq"], 1)
            and self._rng.random() < self.COMMS_OVERSHOOT_PROB
        ):
            self.send_key(plugin, key)

        inst.last_control_t = t

    # ── Audio monitoring (parallel channel) ───────────────────

    def _monitor_comms_audio(self, plugin: Any, t: float) -> None:
        """Monitor communications audio channel in parallel (if enabled).
        Detects new waiting radios and boosts comms cost."""
        if plugin.alias != "communications":
            return

        waiting = plugin.get_waiting_response_radios()
        current_positions = {r["pos"] for r in waiting}

        # Detect new prompts
        for radio in waiting:
            pos = radio["pos"]
            if pos not in self._comms_known_waiting:
                self._comms_known_waiting.add(pos)
                # Boost comms cost for a duration
                self._comms_audio_boost_until = t + self.BU_BOOST_DURATION_S
                # Set fault onset for logarithmic cost growth
                comms_inst = self._instruments.get("comms")
                if comms_inst is not None and comms_inst.fault_onset_t is None:
                    comms_inst.fault_onset_t = t

        # Clean resolved
        for pos in list(self._comms_known_waiting):
            if pos not in current_positions:
                self._comms_known_waiting.discard(pos)

    # ── Bottom-up tracking monitoring ─────────────────────────

    def _monitor_track_bottom_up(self, plugin: Any, t: float) -> None:
        """Peripheral detection of large cursor drift (if bottom_up enabled).

        When the cursor exceeds BU_TRACK_THRESHOLD, the tracking instrument
        gets a cost boost and may capture attention stochastically — just
        like a sysmon failure.
        """
        cx, cy = plugin.reticle.cursor_relative
        half_w = plugin.reticle.container.w / 2
        half_h = plugin.reticle.container.h / 2
        norm_dist = math.sqrt((cx / half_w) ** 2 + (cy / half_h) ** 2)

        inst = self._instruments["tracking"]

        if norm_dist >= self.BU_TRACK_THRESHOLD:
            # Set fault onset for logarithmic cost growth
            if inst.fault_onset_t is None:
                inst.fault_onset_t = t

            # Only trigger once per boost window
            if inst.id not in self._bu_boost_until or t >= self._bu_boost_until[inst.id]:
                self._bu_boost_until[inst.id] = t + self.BU_BOOST_DURATION_S

                # Stochastic attention capture (if not already on tracking)
                if self._current_instrument is None or self._current_instrument.id != "tracking":
                    if self._rng.random() < self.BU_INTERRUPT_PROB:
                        self._current_instrument = inst
                        self._phase = _Phase.IDLE
        else:
            # Cursor back in safe zone → clear boost
            self._bu_boost_until.pop(inst.id, None)
            inst.fault_onset_t = None

    # ── Bottom-up resman monitoring ──────────────────────────

    def _monitor_resman_bottom_up(self, plugin: Any, t: float) -> None:
        """Peripheral detection of large tank deviation (if bottom_up enabled).

        When either tank A or B deviates from target by more than
        BU_RESMAN_THRESHOLD, the corresponding resman instrument gets a
        cost boost and may capture attention stochastically.
        """
        if plugin.wait_before_leak > 0:
            return

        tanks = plugin.parameters["tank"]
        for letter in ("a", "b"):
            tank = tanks[letter]
            inst = self._instruments[f"resman_{letter}"]

            if tank["target"] is None:
                self._bu_boost_until.pop(inst.id, None)
                inst.fault_onset_t = None
                continue

            deviation = abs(tank["level"] - tank["target"])

            if deviation >= self.BU_RESMAN_THRESHOLD:
                # Set fault onset for logarithmic cost growth
                if inst.fault_onset_t is None:
                    inst.fault_onset_t = t

                if inst.id not in self._bu_boost_until or t >= self._bu_boost_until[inst.id]:
                    self._bu_boost_until[inst.id] = t + self.BU_BOOST_DURATION_S

                    # Stochastic attention capture (if not already on resman)
                    if self._current_instrument is None or self._current_instrument.plugin_alias != "resman":
                        if self._rng.random() < self.BU_INTERRUPT_PROB:
                            self._current_instrument = inst
                            self._phase = _Phase.IDLE
            else:
                self._bu_boost_until.pop(inst.id, None)
                inst.fault_onset_t = None

    # ── Main dispatch ─────────────────────────────────────────

    def _get_plugin_for_instrument(self, inst: InstrumentState, available_plugins: dict[str, Any]) -> Any | None:
        """Get the plugin object for an instrument, if currently available."""
        return available_plugins.get(inst.plugin_alias)

    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        alias = plugin.alias

        # 0. Register this plugin as active (for instrument selection filtering)
        self._active_aliases[alias] = scenario_time

        # 1. Auditory channel monitoring (parallel, before selection)
        if self.auditory_channel:
            self._monitor_comms_audio(plugin, scenario_time)

        # 1b. Bottom-up peripheral monitoring (tracking drift, resman deviation)
        if self.bottom_up:
            if alias == "track":
                self._monitor_track_bottom_up(plugin, scenario_time)
            elif alias == "resman":
                self._monitor_resman_bottom_up(plugin, scenario_time)

        # 2. Continuous tracking: when the agent is attending tracking,
        #    send joystick every frame.  Tracking is a continuous visuomotor
        #    loop — the hand stays on the joystick while the eyes are on
        #    the cursor.  Only blocked during SWITCHING (eyes moving to a
        #    different display area, hand leaves the joystick).
        if (
            alias == "track"
            and self._current_instrument is not None
            and self._current_instrument.id == "tracking"
            and self._phase != _Phase.SWITCHING
        ):
            self._act_tracking(plugin, self._current_instrument, scenario_time)

        # 3. If motor_time and not IDLE, continue current phase
        if self.motor_time and self._phase != _Phase.IDLE:
            elapsed = scenario_time - self._phase_start

            if self._phase == _Phase.SWITCHING:
                if elapsed < self.SWITCHING_COST_S:
                    return  # Still switching
                # Switch done → start reading
                self._phase = _Phase.READING
                self._phase_start = scenario_time
                return

            if self._phase == _Phase.READING:
                if elapsed < self.READING_TIME_S:
                    return  # Still reading
                # Reading done → observe and decide to act
                if self._current_instrument:
                    inst = self._current_instrument
                    if inst.plugin_alias != alias:
                        return  # Wait for the correct plugin to complete reading
                    needs_action = self._observe_instrument(plugin, inst, scenario_time)
                    if needs_action:
                        # Tracking is continuous — skip discrete ACTING phase
                        if inst.id == "tracking":
                            self._act_tracking(plugin, inst, scenario_time)
                            self._phase = _Phase.IDLE
                            return
                        self._phase = _Phase.ACTING
                        self._phase_start = scenario_time
                        return
                # No action needed → back to IDLE
                self._phase = _Phase.IDLE
                return

            if self._phase == _Phase.ACTING:
                if elapsed < self.MOTOR_EXEC_S:
                    return  # Still acting
                # Acting done → execute and back to IDLE
                if self._current_instrument:
                    inst = self._current_instrument
                    if inst.plugin_alias != alias:
                        return  # Wait for the correct plugin to complete action
                    self._execute_action(plugin, inst, scenario_time)
                self._phase = _Phase.IDLE
                return

        # 4. If switching_cost only (no motor_time) and switching
        if not self.motor_time and self.switching_cost and self._phase == _Phase.SWITCHING:
            elapsed = scenario_time - self._phase_start
            if elapsed < self.SWITCHING_COST_S:
                return
            self._phase = _Phase.IDLE

        # 5. Decision point: Carbonell selection
        selected = self._select_instrument(scenario_time)

        # Only act on the instrument if its plugin matches the current call
        if selected.plugin_alias != alias:
            return

        # Check switching cost
        if self.switching_cost and self._current_instrument is not None:
            if selected.plugin_alias != self._current_instrument.plugin_alias:
                self._current_instrument = selected
                self._phase = _Phase.SWITCHING
                self._phase_start = scenario_time
                if self.motor_time:
                    return  # Will go through SWITCHING → READING → ACTING
                else:
                    return  # Will wait for SWITCHING_COST_S then act next cycle

        # If already attending this instrument, no need to re-read.
        # This avoids the 333ms READING gap every cycle for tracking.
        already_attending = self._current_instrument is not None and self._current_instrument.id == selected.id
        self._current_instrument = selected

        if self.motor_time and not already_attending:
            # Start reading phase (initial visual acquisition)
            self._phase = _Phase.READING
            self._phase_start = scenario_time
            return

        # Pure Carbonell mode (no motor_time): observe + act immediately
        needs_action = self._observe_instrument(plugin, selected, scenario_time)
        if needs_action:
            self._execute_action(plugin, selected, scenario_time)

    def _execute_action(self, plugin: Any, inst: InstrumentState, t: float) -> None:
        """Execute the corrective action for the given instrument."""
        if inst.id.startswith("sysmon_scale_"):
            self._act_sysmon_scale(plugin, inst, t)
        elif inst.id.startswith("sysmon_light_"):
            self._act_sysmon_light(plugin, inst, t)
        elif inst.id == "tracking":
            self._act_tracking(plugin, inst, t)
        elif inst.id.startswith("resman_"):
            self._act_resman(plugin, t)
        elif inst.id == "comms":
            self._act_comms(plugin, inst, t)

    # ── on_failure_started ────────────────────────────────────

    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        # Bottom-up: boost cost + stochastic capture
        if self.bottom_up:
            key = gauge.get("key", "")
            inst_id = self._gauge_key_to_instrument_id(key)
            if inst_id and inst_id in self._instruments:
                inst = self._instruments[inst_id]
                if inst.fault_onset_t is None:
                    inst.fault_onset_t = plugin.scenario_time
                self._bu_boost_until[inst_id] = plugin.scenario_time + self.BU_BOOST_DURATION_S
                # Stochastic attention capture
                if self._rng.random() < self.BU_INTERRUPT_PROB:
                    self._current_instrument = self._instruments[inst_id]
                    # If in a phase, interrupt it
                    self._phase = _Phase.IDLE

        return {"delay": plugin.parameters["alerttimeout"]}

    @staticmethod
    def _gauge_key_to_instrument_id(key: str) -> str | None:
        """Map a sysmon gauge key (F1-F6) to an instrument id."""
        mapping = {
            "F1": "sysmon_scale_1",
            "F2": "sysmon_scale_2",
            "F3": "sysmon_scale_3",
            "F4": "sysmon_scale_4",
            "F5": "sysmon_light_1",
            "F6": "sysmon_light_2",
        }
        return mapping.get(key)


class CarbonellRevisedAgent(CarbonellAgent):
    """Carbonell (1966) model with realistic cognitive extensions enabled.

    Activates: motor_time, switching_cost, bottom_up, auditory_channel.
    This produces a more human-like operator than the pure Carbonell model:
    reading takes 333 ms, motor actions take 250 ms, switching between
    plugins costs 150 ms, sysmon failures can capture attention, and
    communications prompts are detected via a parallel auditory channel.
    """

    def __init__(self, seed: int | None = None) -> None:
        super().__init__(
            seed=seed,
            motor_time=True,
            switching_cost=True,
            bottom_up=True,
            auditory_channel=True,
            fault_cost_growth=True,
        )
        self.name = "carbonell_revised"
        self.automode_string = "AUTO-CBR"
