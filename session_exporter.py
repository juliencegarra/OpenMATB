# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Export OpenMATB session CSV data into analysis-ready tables.

This standalone CLI tool reads raw session CSVs (one row per event/frame) and
produces three output files suitable for statistical analysis in R, JASP, or SPSS:

  - trials.csv     : one row per discrete trial (sysmon, communications)
  - summary.csv    : one row per session with aggregated metrics
  - timeseries.csv : resampled continuous data (track, resman) at fixed intervals

Usage:
    python session_exporter.py <session.csv> [<session.csv>...] [--output-dir DIR]
    python session_exporter.py sessions/2026-02-25/ [--output-dir results/]
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class RawRow:
    """A single row from the raw session CSV."""

    logtime: float
    scenario_time: float
    type: str
    module: str
    address: str
    value: str


@dataclass
class SysmonTrial:
    """A sysmon trial extracted from three consecutive performance rows."""

    session: str
    scenario_time: float
    trial_number: int
    gauge_name: str
    signal_detection: str  # HIT, MISS, FA
    response_time_ms: float  # milliseconds or NaN
    resolved_by: str  # "human", "agent", or ""


@dataclass
class CommsTrial:
    """A communications trial extracted from nine consecutive performance rows."""

    session: str
    scenario_time: float
    trial_number: int
    sdt_value: str  # HIT, MISS, FA, BAD_RADIO, BAD_FREQ, BAD_RADIO_FREQ
    response_was_needed: str
    target_radio: str
    responded_radio: str
    target_frequency: str
    responded_frequency: str
    correct_radio: str
    response_deviation: str
    response_time_ms: float  # milliseconds or NaN
    resolved_by: str


@dataclass
class TimeSeriesRow:
    """A single resampled point in the time series."""

    session: str
    time_sec: float
    track_in_target: str  # "1"/"0" or ""
    track_deviation: str  # float string or ""
    resman_a_in_tolerance: str
    resman_b_in_tolerance: str
    resman_a_deviation: str
    resman_b_deviation: str
    track_auto: int  # 1 or 0
    resman_auto: int  # 1 or 0


@dataclass
class SessionSummary:
    """Aggregated metrics for a single session."""

    session: str
    duration_sec: float
    # Sysmon
    sysmon_n_trials: int = 0
    sysmon_hit_count: int = 0
    sysmon_miss_count: int = 0
    sysmon_fa_count: int = 0
    sysmon_hit_rate: float = float("nan")
    sysmon_mean_rt_sec: float = float("nan")
    sysmon_median_rt_sec: float = float("nan")
    sysmon_sd_rt_sec: float = float("nan")
    # Track
    track_proportion_in_target: float = float("nan")
    track_mean_deviation: float = float("nan")
    track_sd_deviation: float = float("nan")
    track_n_excursions: int = 0
    track_mean_excursion_rt_sec: float = float("nan")
    # Communications
    comms_n_trials: int = 0
    comms_hit_count: int = 0
    comms_miss_count: int = 0
    comms_fa_count: int = 0
    comms_bad_radio_count: int = 0
    comms_bad_freq_count: int = 0
    comms_hit_rate: float = float("nan")
    comms_mean_rt_sec: float = float("nan")
    comms_median_rt_sec: float = float("nan")
    comms_mean_freq_deviation: float = float("nan")
    # Resman
    resman_a_proportion_in_tolerance: float = float("nan")
    resman_b_proportion_in_tolerance: float = float("nan")
    resman_a_mean_deviation: float = float("nan")
    resman_b_mean_deviation: float = float("nan")
    resman_a_sd_deviation: float = float("nan")
    resman_b_sd_deviation: float = float("nan")
    resman_a_n_excursions: int = 0
    resman_b_n_excursions: int = 0
    resman_a_mean_excursion_rt_sec: float = float("nan")
    resman_b_mean_excursion_rt_sec: float = float("nan")
    resman_mean_deviation_ab: float = float("nan")
    # Scales (dynamic columns)
    scales: dict[str, float] = field(default_factory=dict)


# ── Value parsing ─────────────────────────────────────────────────────────────


def parse_value(raw: str):
    """Convert a CSV string to a typed Python value.

    - 'True'/'False' -> bool
    - 'nan'/'' -> float('nan')
    - numeric -> int or float
    - everything else -> str
    """
    if raw in ("True", "true"):
        return True
    if raw in ("False", "false"):
        return False
    if raw in ("nan", "NaN", ""):
        return float("nan")
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except (ValueError, TypeError):
        return raw


def _is_auto_on(value: str) -> bool:
    """Check whether an automaticsolver CSV value means 'enabled'."""
    return str(value).strip().lower() in ("true", "1", "1.0")


# ── CSV loading ───────────────────────────────────────────────────────────────


def load_session(path: Path) -> tuple[list[RawRow], list[RawRow], list[RawRow]]:
    """Read a session CSV and categorise its rows.

    Returns (performance_rows, input_rows, event_rows).
    *event_rows* includes both ``type='event'`` and ``type='parameter'`` rows.
    """
    performance_rows: list[RawRow] = []
    input_rows: list[RawRow] = []
    event_rows: list[RawRow] = []

    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            next(reader)  # skip header
        except StopIteration:
            return [], [], []

        for row in reader:
            if len(row) < 5:
                continue
            try:
                raw = RawRow(
                    logtime=float(row[0]),
                    scenario_time=float(row[1]),
                    type=row[2],
                    module=row[3],
                    address=row[4],
                    value=row[5] if len(row) > 5 else "",
                )
            except (ValueError, IndexError):
                continue

            if raw.type == "performance":
                performance_rows.append(raw)
            elif raw.type == "input":
                input_rows.append(raw)
            elif raw.type in ("event", "parameter"):
                event_rows.append(raw)

    return performance_rows, input_rows, event_rows


# ── Agent / human attribution ────────────────────────────────────────────────


def _determine_resolved_by(
    trial_time: float, sdt: str, input_rows: list[RawRow], auto_intervals: list[tuple[float, float]]
) -> str:
    """Determine whether a trial was resolved by a human or an agent.

    Looks for the last ``type=input`` row within 0.5 s before *trial_time*.
    Also checks automation intervals to catch the built-in automaticsolver
    (which resolves trials without logging ``type=input`` events).

    Returns ``'human'``, ``'agent'``, ``'auto'``, or ``''`` (MISS).
    """
    if sdt == "MISS":
        return ""

    WINDOW: float = 0.5
    best_module: str = ""
    best_time: float = -1.0

    for row in input_rows:
        if trial_time - WINDOW <= row.scenario_time <= trial_time:
            if row.scenario_time > best_time:
                best_time = row.scenario_time
                best_module = row.module

    if best_module == "agent":
        return "agent"
    if best_module == "keyboard":
        return "human"
    # No matching input — check if the built-in automaticsolver was active
    if _is_in_auto(trial_time, auto_intervals):
        return "auto"
    return ""


# ── Grouping helper ──────────────────────────────────────────────────────────


def _group_by_scenario_time(rows: list[RawRow]) -> list[list[RawRow]]:
    """Group consecutive rows that share the same ``scenario_time``."""
    if not rows:
        return []

    groups: list[list[RawRow]] = []
    current: list[RawRow] = [rows[0]]

    for row in rows[1:]:
        if row.scenario_time == current[0].scenario_time:
            current.append(row)
        else:
            groups.append(current)
            current = [row]
    groups.append(current)
    return groups


# ── Trial extraction ─────────────────────────────────────────────────────────


def extract_sysmon_trials(
    session: str, perf_rows: list[RawRow], input_rows: list[RawRow], auto_intervals: list[tuple[float, float]]
) -> list[SysmonTrial]:
    """Extract sysmon trials by grouping performance rows with the same time."""
    sysmon_rows = sorted(
        [r for r in perf_rows if r.module == "sysmon"],
        key=lambda r: r.scenario_time,
    )
    groups = _group_by_scenario_time(sysmon_rows)

    trials: list[SysmonTrial] = []
    trial_num: int = 0

    for group in groups:
        data: dict[str, str] = {r.address: r.value for r in group}
        if "name" not in data or "signal_detection" not in data:
            continue

        trial_num += 1
        rt_val = parse_value(data.get("response_time", "nan"))
        rt_ms: float = float(rt_val) if isinstance(rt_val, (int, float)) else float("nan")

        # Use resolved_by from CSV if present (new format), else fall back to heuristic
        if "resolved_by" in data:
            resolved: str = data["resolved_by"]
        else:
            resolved = _determine_resolved_by(
                group[0].scenario_time,
                data["signal_detection"],
                input_rows,
                auto_intervals,
            )

        trials.append(
            SysmonTrial(
                session=session,
                scenario_time=group[0].scenario_time,
                trial_number=trial_num,
                gauge_name=data["name"],
                signal_detection=data["signal_detection"],
                response_time_ms=rt_ms,
                resolved_by=resolved,
            )
        )

    return trials


def extract_comms_trials(
    session: str, perf_rows: list[RawRow], input_rows: list[RawRow], auto_intervals: list[tuple[float, float]]
) -> list[CommsTrial]:
    """Extract communications trials by grouping performance rows with the same time."""
    comms_rows = sorted(
        [r for r in perf_rows if r.module == "communications"],
        key=lambda r: r.scenario_time,
    )
    groups = _group_by_scenario_time(comms_rows)

    trials: list[CommsTrial] = []
    trial_num: int = 0

    for group in groups:
        data: dict[str, str] = {r.address: r.value for r in group}
        if "sdt_value" not in data:
            continue

        trial_num += 1
        sdt: str = data["sdt_value"]
        rt_val = parse_value(data.get("response_time", "nan"))
        rt_ms: float = float(rt_val) if isinstance(rt_val, (int, float)) else float("nan")

        # Use resolved_by from CSV if present (new format), else fall back to heuristic
        if "resolved_by" in data:
            resolved: str = data["resolved_by"]
        else:
            resolved = _determine_resolved_by(
                group[0].scenario_time,
                sdt,
                input_rows,
                auto_intervals,
            )

        trials.append(
            CommsTrial(
                session=session,
                scenario_time=group[0].scenario_time,
                trial_number=trial_num,
                sdt_value=sdt,
                response_was_needed=data.get("response_was_needed", ""),
                target_radio=data.get("target_radio", ""),
                responded_radio=data.get("responded_radio", ""),
                target_frequency=data.get("target_frequency", ""),
                responded_frequency=data.get("responded_frequency", ""),
                correct_radio=data.get("correct_radio", ""),
                response_deviation=data.get("response_deviation", ""),
                response_time_ms=rt_ms,
                resolved_by=resolved,
            )
        )

    return trials


# ── Automation intervals ─────────────────────────────────────────────────────


def _build_auto_intervals(event_rows: list[RawRow], module: str) -> list[tuple[float, float]]:
    """Build a list of ``(start, end)`` intervals where automaticsolver is on."""
    auto_rows = sorted(
        [r for r in event_rows if r.module == module and r.address == "automaticsolver"],
        key=lambda r: r.scenario_time,
    )

    intervals: list[tuple[float, float]] = []
    auto_on: bool = False
    auto_start: float = 0.0

    for row in auto_rows:
        on: bool = _is_auto_on(row.value)
        if on and not auto_on:
            auto_on = True
            auto_start = row.scenario_time
        elif not on and auto_on:
            auto_on = False
            intervals.append((auto_start, row.scenario_time))

    if auto_on:
        intervals.append((auto_start, float("inf")))

    return intervals


def _is_in_auto(t: float, intervals: list[tuple[float, float]]) -> bool:
    """Check if time *t* falls within any automation interval."""
    return any(start <= t < end for start, end in intervals)


# ── Summary computation helpers ──────────────────────────────────────────────


def _safe_mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else float("nan")


def _safe_median(vals: list[float]) -> float:
    return statistics.median(vals) if vals else float("nan")


def _safe_stdev(vals: list[float]) -> float:
    return statistics.stdev(vals) if len(vals) >= 2 else float("nan")


# ── Summary computation ──────────────────────────────────────────────────────


def compute_summary(
    session: str,
    perf_rows: list[RawRow],
    sysmon_trials: list[SysmonTrial],
    comms_trials: list[CommsTrial],
    event_rows: list[RawRow],
) -> SessionSummary:
    """Compute aggregated metrics for a single session.

    Only human performance is counted: agent-resolved trials are excluded,
    and continuous data during automation periods is excluded.
    """
    all_times: list[float] = [r.scenario_time for r in perf_rows]
    duration: float = max(all_times) - min(all_times) if all_times else 0.0

    summary = SessionSummary(session=session, duration_sec=duration)

    # ── Sysmon ────────────────────────────────────────────────────────────
    human_sysmon = [t for t in sysmon_trials if t.resolved_by not in ("agent", "auto")]
    summary.sysmon_n_trials = len(human_sysmon)
    summary.sysmon_hit_count = sum(1 for t in human_sysmon if t.signal_detection == "HIT")
    summary.sysmon_miss_count = sum(1 for t in human_sysmon if t.signal_detection == "MISS")
    summary.sysmon_fa_count = sum(1 for t in human_sysmon if t.signal_detection == "FA")

    denom: int = summary.sysmon_hit_count + summary.sysmon_miss_count
    if denom > 0:
        summary.sysmon_hit_rate = summary.sysmon_hit_count / denom

    hit_rts: list[float] = [
        t.response_time_ms / 1000
        for t in human_sysmon
        if t.signal_detection == "HIT" and not math.isnan(t.response_time_ms)
    ]
    summary.sysmon_mean_rt_sec = _safe_mean(hit_rts)
    summary.sysmon_median_rt_sec = _safe_median(hit_rts)
    summary.sysmon_sd_rt_sec = _safe_stdev(hit_rts)

    # ── Track ─────────────────────────────────────────────────────────────
    track_auto_intervals = _build_auto_intervals(event_rows, "track")
    track_rows = sorted(
        [r for r in perf_rows if r.module == "track" and not _is_in_auto(r.scenario_time, track_auto_intervals)],
        key=lambda r: r.scenario_time,
    )

    in_target_vals: list[bool] = []
    deviation_vals: list[float] = []
    track_excursion_rts: list[float] = []

    for group in _group_by_scenario_time(track_rows):
        data: dict[str, str] = {r.address: r.value for r in group}

        if "cursor_in_target" in data:
            v = parse_value(data["cursor_in_target"])
            if isinstance(v, (bool, int)) and not isinstance(v, float):
                in_target_vals.append(bool(v))
            elif isinstance(v, float) and not math.isnan(v):
                in_target_vals.append(bool(int(v)))

        if "center_deviation" in data:
            v = parse_value(data["center_deviation"])
            if isinstance(v, (int, float)) and not math.isnan(v):
                deviation_vals.append(float(v))

        if "response_time" in data:
            v = parse_value(data["response_time"])
            if isinstance(v, (int, float)) and not math.isnan(v):
                track_excursion_rts.append(float(v) / 1000)

    if in_target_vals:
        summary.track_proportion_in_target = sum(in_target_vals) / len(in_target_vals)
    summary.track_mean_deviation = _safe_mean(deviation_vals)
    summary.track_sd_deviation = _safe_stdev(deviation_vals)
    summary.track_n_excursions = len(track_excursion_rts)
    summary.track_mean_excursion_rt_sec = _safe_mean(track_excursion_rts)

    # ── Communications ────────────────────────────────────────────────────
    human_comms = [t for t in comms_trials if t.resolved_by not in ("agent", "auto")]
    summary.comms_n_trials = len(human_comms)
    summary.comms_hit_count = sum(1 for t in human_comms if t.sdt_value == "HIT")
    summary.comms_miss_count = sum(1 for t in human_comms if t.sdt_value == "MISS")
    summary.comms_fa_count = sum(1 for t in human_comms if t.sdt_value == "FA")
    summary.comms_bad_radio_count = sum(1 for t in human_comms if t.sdt_value == "BAD_RADIO")
    summary.comms_bad_freq_count = sum(1 for t in human_comms if t.sdt_value == "BAD_FREQ")

    # hit_rate denominator: trials where a response was needed (exclude FA)
    needed = [t for t in human_comms if t.sdt_value not in ("FA", "", "None", None)]
    if needed:
        summary.comms_hit_rate = summary.comms_hit_count / len(needed)

    # RT for all non-MISS responses
    comms_rts: list[float] = [
        t.response_time_ms / 1000 for t in human_comms if t.sdt_value != "MISS" and not math.isnan(t.response_time_ms)
    ]
    summary.comms_mean_rt_sec = _safe_mean(comms_rts)
    summary.comms_median_rt_sec = _safe_median(comms_rts)

    # Mean absolute frequency deviation
    freq_devs: list[float] = []
    for t in human_comms:
        dev = parse_value(t.response_deviation)
        if isinstance(dev, (int, float)) and not math.isnan(dev):
            freq_devs.append(abs(float(dev)))
    summary.comms_mean_freq_deviation = _safe_mean(freq_devs)

    # ── Resman ────────────────────────────────────────────────────────────
    resman_auto_intervals = _build_auto_intervals(event_rows, "resman")
    resman_rows = sorted(
        [r for r in perf_rows if r.module == "resman" and not _is_in_auto(r.scenario_time, resman_auto_intervals)],
        key=lambda r: r.scenario_time,
    )

    a_in_tol: list[bool] = []
    b_in_tol: list[bool] = []
    a_devs: list[float] = []
    b_devs: list[float] = []
    a_excursion_rts: list[float] = []
    b_excursion_rts: list[float] = []

    for group in _group_by_scenario_time(resman_rows):
        data = {r.address: r.value for r in group}

        for prefix, tol_list, dev_list, rt_list in [
            ("a", a_in_tol, a_devs, a_excursion_rts),
            ("b", b_in_tol, b_devs, b_excursion_rts),
        ]:
            key_tol: str = f"{prefix}_in_tolerance"
            key_dev: str = f"{prefix}_deviation"
            key_rt: str = f"{prefix}_response_time"

            if key_tol in data:
                v = parse_value(data[key_tol])
                if isinstance(v, (bool, int)) and not isinstance(v, float):
                    tol_list.append(bool(v))
                elif isinstance(v, float) and not math.isnan(v):
                    tol_list.append(bool(int(v)))

            if key_dev in data:
                v = parse_value(data[key_dev])
                if isinstance(v, (int, float)) and not math.isnan(v):
                    dev_list.append(float(v))

            if key_rt in data:
                v = parse_value(data[key_rt])
                if isinstance(v, (int, float)) and not math.isnan(v):
                    rt_list.append(float(v) / 1000)

    if a_in_tol:
        summary.resman_a_proportion_in_tolerance = sum(a_in_tol) / len(a_in_tol)
    if b_in_tol:
        summary.resman_b_proportion_in_tolerance = sum(b_in_tol) / len(b_in_tol)

    summary.resman_a_mean_deviation = _safe_mean(a_devs)
    summary.resman_b_mean_deviation = _safe_mean(b_devs)
    summary.resman_a_sd_deviation = _safe_stdev(a_devs)
    summary.resman_b_sd_deviation = _safe_stdev(b_devs)
    summary.resman_a_n_excursions = len(a_excursion_rts)
    summary.resman_b_n_excursions = len(b_excursion_rts)
    summary.resman_a_mean_excursion_rt_sec = _safe_mean(a_excursion_rts)
    summary.resman_b_mean_excursion_rt_sec = _safe_mean(b_excursion_rts)

    # Combined AB mean deviation (Avril et al.)
    ab_means: list[float] = [m for m in [_safe_mean(a_devs), _safe_mean(b_devs)] if not math.isnan(m)]
    if ab_means:
        summary.resman_mean_deviation_ab = statistics.mean(ab_means)

    # ── Generic scales ────────────────────────────────────────────────────
    scale_rows = sorted(
        [r for r in perf_rows if r.module == "genericscales"],
        key=lambda r: r.scenario_time,
    )
    if scale_rows:
        scale_groups = _group_by_scenario_time(scale_rows)
        title_counts: dict[str, int] = {}
        for group in scale_groups:
            data_s: dict[str, str] = {r.address: r.value for r in group}
            # Use presentation_number if logged (new format), else count occurrences
            pres_num: int | None = None
            if "presentation_number" in data_s:
                pv = parse_value(data_s["presentation_number"])
                if isinstance(pv, int) and not isinstance(pv, bool):
                    pres_num = pv
            for row in group:
                if row.address == "presentation_number":
                    continue
                title = row.address.replace(" ", "_")
                if pres_num is not None:
                    n = pres_num
                else:
                    title_counts[title] = title_counts.get(title, 0) + 1
                    n = title_counts[title]
                col = f"scale_{title}_{n}"
                v = parse_value(row.value)
                summary.scales[col] = float(v) if isinstance(v, (int, float)) else float("nan")

    return summary


# ── Time series ───────────────────────────────────────────────────────────────


def build_timeseries(
    session: str, perf_rows: list[RawRow], event_rows: list[RawRow], interval: float
) -> list[TimeSeriesRow]:
    """Resample continuous data (track + resman) at fixed intervals using LOCF."""
    # Collect raw observations sorted by scenario_time
    track_rows = sorted(
        [r for r in perf_rows if r.module == "track"],
        key=lambda r: r.scenario_time,
    )
    resman_rows = sorted(
        [r for r in perf_rows if r.module == "resman"],
        key=lambda r: r.scenario_time,
    )

    if not track_rows and not resman_rows:
        return []

    track_obs: list[tuple[float, dict[str, str]]] = []
    for group in _group_by_scenario_time(track_rows):
        data: dict[str, str] = {r.address: r.value for r in group}
        track_obs.append((group[0].scenario_time, data))

    resman_obs: list[tuple[float, dict[str, str]]] = []
    for group in _group_by_scenario_time(resman_rows):
        data = {r.address: r.value for r in group}
        resman_obs.append((group[0].scenario_time, data))

    # Time range
    all_times: list[float] = [t for t, _ in track_obs] + [t for t, _ in resman_obs]
    t_max: float = max(all_times)

    # Automation state
    track_auto = _build_auto_intervals(event_rows, "track")
    resman_auto = _build_auto_intervals(event_rows, "resman")

    # LOCF resampling
    series: list[TimeSeriesRow] = []
    last_track_in: str = ""
    last_track_dev: str = ""
    last_res_a_tol: str = ""
    last_res_b_tol: str = ""
    last_res_a_dev: str = ""
    last_res_b_dev: str = ""

    track_idx: int = 0
    resman_idx: int = 0
    n_points: int = int(t_max / interval) + 1

    for i in range(n_points):
        t: float = round(i * interval, 6)

        # Advance track pointer (consume all observations <= t)
        while track_idx < len(track_obs) and track_obs[track_idx][0] <= t:
            obs_data: dict[str, str] = track_obs[track_idx][1]
            if "cursor_in_target" in obs_data:
                last_track_in = obs_data["cursor_in_target"]
            if "center_deviation" in obs_data:
                last_track_dev = obs_data["center_deviation"]
            track_idx += 1

        # Advance resman pointer
        while resman_idx < len(resman_obs) and resman_obs[resman_idx][0] <= t:
            obs_data = resman_obs[resman_idx][1]
            if "a_in_tolerance" in obs_data:
                last_res_a_tol = obs_data["a_in_tolerance"]
            if "b_in_tolerance" in obs_data:
                last_res_b_tol = obs_data["b_in_tolerance"]
            if "a_deviation" in obs_data:
                last_res_a_dev = obs_data["a_deviation"]
            if "b_deviation" in obs_data:
                last_res_b_dev = obs_data["b_deviation"]
            resman_idx += 1

        series.append(
            TimeSeriesRow(
                session=session,
                time_sec=t,
                track_in_target=last_track_in,
                track_deviation=last_track_dev,
                resman_a_in_tolerance=last_res_a_tol,
                resman_b_in_tolerance=last_res_b_tol,
                resman_a_deviation=last_res_a_dev,
                resman_b_deviation=last_res_b_dev,
                track_auto=1 if _is_in_auto(t, track_auto) else 0,
                resman_auto=1 if _is_in_auto(t, resman_auto) else 0,
            )
        )

    return series


# ── CSV output helpers ────────────────────────────────────────────────────────


def _fmt(v) -> str:
    """Format a summary value for CSV: nan->'', float->clean number."""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return f"{v:g}"
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def _fmt_val(raw: str) -> str:
    """Format a raw CSV value for export: nan->'', True/1->1, False/0->0."""
    if raw == "" or raw is None:
        return ""
    v = parse_value(raw)
    if isinstance(v, float) and math.isnan(v):
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(raw)


# ── trials.csv ────────────────────────────────────────────────────────────────


TRIALS_COLUMNS: list[str] = [
    "session",
    "scenario_time",
    "task",
    "trial_number",
    "gauge_name",
    "signal_detection",
    "sdt_value",
    "response_was_needed",
    "target_radio",
    "responded_radio",
    "target_frequency",
    "responded_frequency",
    "correct_radio",
    "response_deviation",
    "response_time_sec",
    "resolved_by",
]


def write_trials(sysmon_trials: list[SysmonTrial], comms_trials: list[CommsTrial], output_path: Path, sep: str) -> None:
    """Write the combined trials.csv file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=sep)
        w.writerow(TRIALS_COLUMNS)

        for t in sysmon_trials:
            rt_sec: str = "" if math.isnan(t.response_time_ms) else f"{t.response_time_ms / 1000:g}"
            w.writerow(
                [
                    t.session,
                    f"{t.scenario_time:g}",
                    "sysmon",
                    t.trial_number,
                    t.gauge_name,
                    t.signal_detection,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",  # comms columns empty
                    rt_sec,
                    t.resolved_by,
                ]
            )

        for t in comms_trials:
            rt_sec = "" if math.isnan(t.response_time_ms) else f"{t.response_time_ms / 1000:g}"
            w.writerow(
                [
                    t.session,
                    f"{t.scenario_time:g}",
                    "communications",
                    t.trial_number,
                    "",  # gauge_name (sysmon only)
                    "",  # signal_detection (sysmon only)
                    t.sdt_value,
                    _fmt_val(t.response_was_needed),
                    _fmt_val(t.target_radio),
                    _fmt_val(t.responded_radio),
                    _fmt_val(t.target_frequency),
                    _fmt_val(t.responded_frequency),
                    _fmt_val(t.correct_radio),
                    _fmt_val(t.response_deviation),
                    rt_sec,
                    t.resolved_by,
                ]
            )


# ── summary.csv ──────────────────────────────────────────────────────────────


SUMMARY_FIXED_COLUMNS: list[str] = [
    "session",
    "duration_sec",
    # Sysmon
    "sysmon_n_trials",
    "sysmon_hit_count",
    "sysmon_miss_count",
    "sysmon_fa_count",
    "sysmon_hit_rate",
    "sysmon_mean_rt_sec",
    "sysmon_median_rt_sec",
    "sysmon_sd_rt_sec",
    # Track
    "track_proportion_in_target",
    "track_mean_deviation",
    "track_sd_deviation",
    "track_n_excursions",
    "track_mean_excursion_rt_sec",
    # Communications
    "comms_n_trials",
    "comms_hit_count",
    "comms_miss_count",
    "comms_fa_count",
    "comms_bad_radio_count",
    "comms_bad_freq_count",
    "comms_hit_rate",
    "comms_mean_rt_sec",
    "comms_median_rt_sec",
    "comms_mean_freq_deviation",
    # Resman
    "resman_a_proportion_in_tolerance",
    "resman_b_proportion_in_tolerance",
    "resman_a_mean_deviation",
    "resman_b_mean_deviation",
    "resman_a_sd_deviation",
    "resman_b_sd_deviation",
    "resman_a_n_excursions",
    "resman_b_n_excursions",
    "resman_a_mean_excursion_rt_sec",
    "resman_b_mean_excursion_rt_sec",
    "resman_mean_deviation_ab",
]


def write_summary(summaries: list[SessionSummary], output_path: Path, sep: str) -> None:
    """Write summary.csv with one row per session."""
    # Collect all scale columns across sessions
    scale_cols: list[str] = []
    seen: set[str] = set()
    for s in summaries:
        for col in sorted(s.scales):
            if col not in seen:
                seen.add(col)
                scale_cols.append(col)
    scale_cols.sort()

    header: list[str] = SUMMARY_FIXED_COLUMNS + scale_cols

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=sep)
        w.writerow(header)

        for s in summaries:
            row: list[str] = []
            for col in SUMMARY_FIXED_COLUMNS:
                row.append(_fmt(getattr(s, col)))
            for col in scale_cols:
                row.append(_fmt(s.scales.get(col, float("nan"))))
            w.writerow(row)


# ── timeseries.csv ────────────────────────────────────────────────────────────


TIMESERIES_COLUMNS: list[str] = [
    "session",
    "time_sec",
    "track_in_target",
    "track_deviation",
    "resman_a_in_tolerance",
    "resman_b_in_tolerance",
    "resman_a_deviation",
    "resman_b_deviation",
    "track_auto",
    "resman_auto",
]


def write_timeseries(series: list[TimeSeriesRow], output_path: Path, sep: str) -> None:
    """Write timeseries.csv with resampled continuous data."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=sep)
        w.writerow(TIMESERIES_COLUMNS)

        for row in series:
            w.writerow(
                [
                    row.session,
                    f"{row.time_sec:g}",
                    _fmt_val(row.track_in_target),
                    _fmt_val(row.track_deviation),
                    _fmt_val(row.resman_a_in_tolerance),
                    _fmt_val(row.resman_b_in_tolerance),
                    _fmt_val(row.resman_a_deviation),
                    _fmt_val(row.resman_b_deviation),
                    row.track_auto,
                    row.resman_auto,
                ]
            )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _collect_csv_paths(inputs: list[str]) -> list[Path]:
    """Resolve CLI inputs (files or directories) to a sorted list of CSV paths."""
    paths: list[Path] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.csv")))
        elif p.is_file() and p.suffix.lower() == ".csv":
            paths.append(p)
        else:
            print(f"Warning: {inp} is not a CSV file or directory, skipping", file=sys.stderr)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export OpenMATB session CSVs into analysis-ready tables.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more session CSV files, or a directory containing them",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Time series sampling interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--sep",
        choices=["comma", "tab", "semicolon"],
        default="comma",
        help="CSV separator for output files (default: comma)",
    )

    args = parser.parse_args()

    sep: str = {"comma": ",", "tab": "\t", "semicolon": ";"}[args.sep]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = _collect_csv_paths(args.inputs)
    if not paths:
        print("Error: no CSV files found", file=sys.stderr)
        sys.exit(1)

    all_sysmon: list[SysmonTrial] = []
    all_comms: list[CommsTrial] = []
    all_summaries: list[SessionSummary] = []
    all_timeseries: list[TimeSeriesRow] = []

    for path in paths:
        session: str = path.stem
        print(f"Processing {path.name}...", file=sys.stderr)

        try:
            perf_rows, input_rows, event_rows = load_session(path)
        except Exception as e:
            print(f"  Error reading {path}: {e}", file=sys.stderr)
            continue

        if not perf_rows:
            print("  Warning: no performance data, skipping", file=sys.stderr)
            continue

        sysmon_auto = _build_auto_intervals(event_rows, "sysmon")
        comms_auto = _build_auto_intervals(event_rows, "communications")

        sysmon_trials = extract_sysmon_trials(
            session,
            perf_rows,
            input_rows,
            sysmon_auto,
        )
        comms_trials = extract_comms_trials(
            session,
            perf_rows,
            input_rows,
            comms_auto,
        )

        all_sysmon.extend(sysmon_trials)
        all_comms.extend(comms_trials)

        summary = compute_summary(
            session,
            perf_rows,
            sysmon_trials,
            comms_trials,
            event_rows,
        )
        all_summaries.append(summary)

        ts = build_timeseries(session, perf_rows, event_rows, args.interval)
        all_timeseries.extend(ts)

    # Write outputs
    trials_path: Path = output_dir / "trials.csv"
    summary_path: Path = output_dir / "summary.csv"
    ts_path: Path = output_dir / "timeseries.csv"

    write_trials(all_sysmon, all_comms, trials_path, sep)
    print(f"Wrote {len(all_sysmon) + len(all_comms)} trials to {trials_path}", file=sys.stderr)

    write_summary(all_summaries, summary_path, sep)
    print(f"Wrote {len(all_summaries)} session summaries to {summary_path}", file=sys.stderr)

    write_timeseries(all_timeseries, ts_path, sep)
    print(f"Wrote {len(all_timeseries)} time series rows to {ts_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
