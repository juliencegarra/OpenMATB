# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Unit tests for session_exporter.py.

Tests cover value parsing, CSV loading, trial extraction, agent/human
attribution, automation interval detection, summary computation,
time series resampling, and CSV output formatting.  No pyglet dependency.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from session_exporter import (
    TIMESERIES_COLUMNS,
    TRIALS_COLUMNS,
    CommsTrial,
    RawRow,
    SessionSummary,
    SysmonTrial,
    TimeSeriesRow,
    _build_auto_intervals,
    _collect_csv_paths,
    _determine_resolved_by,
    _fmt,
    _fmt_val,
    _group_by_scenario_time,
    _is_auto_on,
    _is_in_auto,
    _safe_mean,
    _safe_median,
    _safe_stdev,
    build_timeseries,
    compute_summary,
    extract_comms_trials,
    extract_sysmon_trials,
    load_session,
    parse_value,
    write_summary,
    write_timeseries,
    write_trials,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _row(scenario_time: float, type_: str, module: str, address: str, value: str) -> RawRow:
    """Shortcut to build a RawRow with a dummy logtime."""
    return RawRow(
        logtime=1000.0 + scenario_time,
        scenario_time=scenario_time,
        type=type_,
        module=module,
        address=address,
        value=value,
    )


def _perf(t: float, module: str, address: str, value: str) -> RawRow:
    """Shortcut for a performance row."""
    return _row(t, "performance", module, address, value)


def _input(t: float, module: str, key: str, state: str = "press") -> RawRow:
    """Shortcut for an input row."""
    return _row(t, "input", module, key, state)


def _event(t: float, module: str, address: str, value: str) -> RawRow:
    """Shortcut for an event row."""
    return _row(t, "event", module, address, value)


def _param(t: float, module: str, address: str, value: str) -> RawRow:
    """Shortcut for a parameter row."""
    return _row(t, "parameter", module, address, value)


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    """Write a minimal session CSV with header + data rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["logtime", "scenario_time", "type", "module", "address", "value"])
        for r in rows:
            w.writerow(r)


# ── parse_value ──────────────────────────────────────────────────────────────


class TestParseValue:
    def test_true_variants(self) -> None:
        assert parse_value("True") is True
        assert parse_value("true") is True

    def test_false_variants(self) -> None:
        assert parse_value("False") is False
        assert parse_value("false") is False

    def test_nan_variants(self) -> None:
        assert math.isnan(parse_value("nan"))
        assert math.isnan(parse_value("NaN"))
        assert math.isnan(parse_value(""))

    def test_integer(self) -> None:
        assert parse_value("42") == 42
        assert isinstance(parse_value("42"), int)

    def test_negative_integer(self) -> None:
        assert parse_value("-100") == -100

    def test_float(self) -> None:
        assert parse_value("3.14") == pytest.approx(3.14)
        assert isinstance(parse_value("3.14"), float)

    def test_zero(self) -> None:
        assert parse_value("0") == 0
        assert isinstance(parse_value("0"), int)

    def test_string_passthrough(self) -> None:
        assert parse_value("F5") == "F5"
        assert parse_value("COM_2") == "COM_2"
        assert parse_value("HIT") == "HIT"


# ── _is_auto_on ─────────────────────────────────────────────────────────────


class TestIsAutoOn:
    def test_truthy_values(self) -> None:
        assert _is_auto_on("True") is True
        assert _is_auto_on("1") is True
        assert _is_auto_on("1.0") is True
        assert _is_auto_on("true") is True

    def test_falsy_values(self) -> None:
        assert _is_auto_on("False") is False
        assert _is_auto_on("0") is False
        assert _is_auto_on("") is False
        assert _is_auto_on("0.0") is False


# ── _fmt / _fmt_val ─────────────────────────────────────────────────────────


class TestFormatting:
    def test_fmt_nan(self) -> None:
        assert _fmt(float("nan")) == ""

    def test_fmt_float(self) -> None:
        assert _fmt(0.75) == "0.75"

    def test_fmt_float_integer_value(self) -> None:
        assert _fmt(3.0) == "3"

    def test_fmt_int(self) -> None:
        assert _fmt(5) == "5"

    def test_fmt_bool(self) -> None:
        assert _fmt(True) == "1"
        assert _fmt(False) == "0"

    def test_fmt_val_nan(self) -> None:
        assert _fmt_val("nan") == ""

    def test_fmt_val_empty(self) -> None:
        assert _fmt_val("") == ""

    def test_fmt_val_none(self) -> None:
        assert _fmt_val(None) == ""

    def test_fmt_val_true(self) -> None:
        assert _fmt_val("True") == "1"

    def test_fmt_val_false(self) -> None:
        assert _fmt_val("False") == "0"

    def test_fmt_val_number_passthrough(self) -> None:
        assert _fmt_val("127.9") == "127.9"

    def test_fmt_val_string_passthrough(self) -> None:
        assert _fmt_val("COM_2") == "COM_2"


# ── _safe_mean / _safe_median / _safe_stdev ──────────────────────────────────


class TestSafeStats:
    def test_mean_empty(self) -> None:
        assert math.isnan(_safe_mean([]))

    def test_mean_values(self) -> None:
        assert _safe_mean([2.0, 4.0]) == pytest.approx(3.0)

    def test_median_empty(self) -> None:
        assert math.isnan(_safe_median([]))

    def test_median_odd(self) -> None:
        assert _safe_median([1.0, 3.0, 5.0]) == pytest.approx(3.0)

    def test_stdev_too_few(self) -> None:
        assert math.isnan(_safe_stdev([]))
        assert math.isnan(_safe_stdev([1.0]))

    def test_stdev_values(self) -> None:
        assert _safe_stdev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) > 0


# ── load_session ─────────────────────────────────────────────────────────────


class TestLoadSession:
    def test_categorises_rows(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "session.csv"
        _write_csv(
            csv_path,
            [
                ["100.0", "1.0", "performance", "track", "cursor_in_target", "1"],
                ["100.1", "1.0", "input", "keyboard", "F5", "press"],
                ["100.2", "1.0", "event", "sysmon", "self", "start"],
                ["100.3", "1.0", "parameter", "track", "automaticsolver", "0"],
                ["100.4", "1.0", "state", "track", "visibility", "1"],
            ],
        )
        perf, inp, evt = load_session(csv_path)
        assert len(perf) == 1
        assert perf[0].module == "track"
        assert len(inp) == 1
        assert inp[0].address == "F5"
        assert len(evt) == 2  # event + parameter (state excluded)

    def test_empty_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(
            "logtime,scenario_time,type,module,address,value\n",
            encoding="utf-8",
        )
        perf, inp, evt = load_session(csv_path)
        assert perf == [] and inp == [] and evt == []

    def test_skips_malformed_rows(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad.csv"
        _write_csv(
            csv_path,
            [
                ["not_a_float", "1.0", "performance", "track", "x", "1"],
                ["100.0", "2.0", "performance", "track", "cursor_in_target", "1"],
            ],
        )
        perf, _inp, _evt = load_session(csv_path)
        assert len(perf) == 1

    def test_row_with_five_columns(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "five.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["logtime", "scenario_time", "type", "module", "address", "value"])
            w.writerow(["100.0", "1.0", "performance", "track", "cursor_in_target"])  # no value column
        perf, _, _ = load_session(csv_path)
        assert len(perf) == 1
        assert perf[0].value == ""


# ── _group_by_scenario_time ──────────────────────────────────────────────────


class TestGroupByScenarioTime:
    def test_empty(self) -> None:
        assert _group_by_scenario_time([]) == []

    def test_single_group(self) -> None:
        rows = [_perf(1.0, "track", "a", "1"), _perf(1.0, "track", "b", "2")]
        groups = _group_by_scenario_time(rows)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_multiple_groups(self) -> None:
        rows = [_perf(1.0, "track", "a", "1"), _perf(2.0, "track", "a", "2"), _perf(2.0, "track", "b", "3")]
        groups = _group_by_scenario_time(rows)
        assert len(groups) == 2
        assert len(groups[0]) == 1
        assert len(groups[1]) == 2


# ── _build_auto_intervals / _is_in_auto ──────────────────────────────────────


class TestAutoIntervals:
    def test_no_events(self) -> None:
        assert _build_auto_intervals([], "track") == []

    def test_on_then_off(self) -> None:
        events = [
            _event(5.0, "track", "automaticsolver", "1"),
            _event(15.0, "track", "automaticsolver", "0"),
        ]
        intervals = _build_auto_intervals(events, "track")
        assert intervals == [(5.0, 15.0)]

    def test_on_never_off(self) -> None:
        events = [_event(5.0, "track", "automaticsolver", "True")]
        intervals = _build_auto_intervals(events, "track")
        assert len(intervals) == 1
        assert intervals[0][0] == 5.0
        assert intervals[0][1] == float("inf")

    def test_ignores_other_modules(self) -> None:
        events = [
            _event(5.0, "resman", "automaticsolver", "1"),
            _event(15.0, "resman", "automaticsolver", "0"),
        ]
        assert _build_auto_intervals(events, "track") == []

    def test_parameter_rows_included(self) -> None:
        events = [
            _param(0.0, "track", "automaticsolver", "0"),
            _event(5.0, "track", "automaticsolver", "1"),
            _event(15.0, "track", "automaticsolver", "0"),
        ]
        intervals = _build_auto_intervals(events, "track")
        assert intervals == [(5.0, 15.0)]

    def test_multiple_intervals(self) -> None:
        events = [
            _event(5.0, "track", "automaticsolver", "1"),
            _event(10.0, "track", "automaticsolver", "0"),
            _event(20.0, "track", "automaticsolver", "1"),
            _event(30.0, "track", "automaticsolver", "0"),
        ]
        intervals = _build_auto_intervals(events, "track")
        assert intervals == [(5.0, 10.0), (20.0, 30.0)]

    def test_is_in_auto_inside(self) -> None:
        intervals = [(5.0, 15.0)]
        assert _is_in_auto(7.0, intervals) is True

    def test_is_in_auto_outside(self) -> None:
        intervals = [(5.0, 15.0)]
        assert _is_in_auto(3.0, intervals) is False
        assert _is_in_auto(15.0, intervals) is False  # half-open [start, end)

    def test_is_in_auto_empty(self) -> None:
        assert _is_in_auto(5.0, []) is False


# ── _determine_resolved_by ──────────────────────────────────────────────────


class TestDetermineResolvedBy:
    def test_miss_always_empty(self) -> None:
        inputs = [_input(10.0, "keyboard", "F5")]
        assert _determine_resolved_by(10.0, "MISS", inputs, []) == ""

    def test_keyboard_input(self) -> None:
        inputs = [_input(9.8, "keyboard", "F5")]
        assert _determine_resolved_by(10.0, "HIT", inputs, []) == "human"

    def test_agent_input(self) -> None:
        inputs = [_input(9.9, "agent", "F5")]
        assert _determine_resolved_by(10.0, "HIT", inputs, []) == "agent"

    def test_no_input_no_auto(self) -> None:
        assert _determine_resolved_by(10.0, "HIT", [], []) == ""

    def test_no_input_in_auto(self) -> None:
        auto = [(5.0, 20.0)]
        assert _determine_resolved_by(10.0, "HIT", [], auto) == "auto"

    def test_input_outside_window(self) -> None:
        inputs = [_input(8.0, "keyboard", "F5")]
        assert _determine_resolved_by(10.0, "HIT", inputs, []) == ""

    def test_picks_latest_input(self) -> None:
        inputs = [
            _input(9.6, "keyboard", "F5"),
            _input(9.9, "agent", "F5"),
        ]
        assert _determine_resolved_by(10.0, "HIT", inputs, []) == "agent"

    def test_keyboard_overrides_auto(self) -> None:
        inputs = [_input(9.9, "keyboard", "F5")]
        auto = [(5.0, 20.0)]
        assert _determine_resolved_by(10.0, "HIT", inputs, auto) == "human"

    def test_fa_not_miss(self) -> None:
        inputs = [_input(9.9, "keyboard", "F5")]
        assert _determine_resolved_by(10.0, "FA", inputs, []) == "human"


# ── extract_sysmon_trials ────────────────────────────────────────────────────


class TestExtractSysmonTrials:
    def _make_triplet(
        self, t: float, name: str, sdt: str, rt: str = "nan", resolved_by: str | None = None
    ) -> list[RawRow]:
        rows = [
            _perf(t, "sysmon", "name", name),
            _perf(t, "sysmon", "signal_detection", sdt),
            _perf(t, "sysmon", "response_time", rt),
        ]
        if resolved_by is not None:
            rows.append(_perf(t, "sysmon", "resolved_by", resolved_by))
        return rows

    def test_single_hit(self) -> None:
        perf = self._make_triplet(10.0, "F5", "HIT", "200")
        inputs = [_input(10.0, "keyboard", "F5")]
        trials = extract_sysmon_trials("s1", perf, inputs, [])
        assert len(trials) == 1
        assert trials[0].gauge_name == "F5"
        assert trials[0].signal_detection == "HIT"
        assert trials[0].response_time_ms == pytest.approx(200.0)
        assert trials[0].resolved_by == "human"
        assert trials[0].trial_number == 1

    def test_miss_nan_rt(self) -> None:
        perf = self._make_triplet(20.0, "F1", "MISS", "nan")
        trials = extract_sysmon_trials("s1", perf, [], [])
        assert len(trials) == 1
        assert trials[0].signal_detection == "MISS"
        assert math.isnan(trials[0].response_time_ms)
        assert trials[0].resolved_by == ""

    def test_multiple_trials_numbered(self) -> None:
        perf = (
            self._make_triplet(10.0, "F5", "HIT", "200")
            + self._make_triplet(20.0, "F1", "MISS")
            + self._make_triplet(30.0, "F3", "FA")
        )
        inputs = [_input(10.0, "keyboard", "F5"), _input(30.0, "keyboard", "F3")]
        trials = extract_sysmon_trials("s1", perf, inputs, [])
        assert len(trials) == 3
        assert [t.trial_number for t in trials] == [1, 2, 3]
        assert [t.signal_detection for t in trials] == ["HIT", "MISS", "FA"]

    def test_filters_non_sysmon(self) -> None:
        perf = self._make_triplet(10.0, "F5", "HIT", "200") + [_perf(10.0, "track", "cursor_in_target", "1")]
        inputs = [_input(10.0, "keyboard", "F5")]
        trials = extract_sysmon_trials("s1", perf, inputs, [])
        assert len(trials) == 1

    def test_incomplete_group_skipped(self) -> None:
        perf = [_perf(10.0, "sysmon", "name", "F5")]  # only 1 of 3
        trials = extract_sysmon_trials("s1", perf, [], [])
        assert len(trials) == 0

    def test_auto_resolved(self) -> None:
        perf = self._make_triplet(10.0, "F5", "HIT", "1000")
        auto = [(0.0, float("inf"))]
        trials = extract_sysmon_trials("s1", perf, [], auto)
        assert trials[0].resolved_by == "auto"

    def test_resolved_by_from_csv(self) -> None:
        """New format: resolved_by is read directly from the CSV."""
        perf = self._make_triplet(10.0, "F5", "HIT", "200", resolved_by="agent")
        trials = extract_sysmon_trials("s1", perf, [], [])
        assert trials[0].resolved_by == "agent"

    def test_resolved_by_csv_overrides_heuristic(self) -> None:
        """When resolved_by is in CSV, the heuristic is not used."""
        perf = self._make_triplet(10.0, "F5", "HIT", "200", resolved_by="human")
        # Even with auto intervals, the CSV value takes priority
        auto = [(0.0, float("inf"))]
        trials = extract_sysmon_trials("s1", perf, [], auto)
        assert trials[0].resolved_by == "human"

    def test_resolved_by_empty_for_miss(self) -> None:
        """MISS with resolved_by='' in CSV."""
        perf = self._make_triplet(20.0, "F1", "MISS", "nan", resolved_by="")
        trials = extract_sysmon_trials("s1", perf, [], [])
        assert trials[0].resolved_by == ""

    def test_fallback_heuristic_without_resolved_by(self) -> None:
        """Old format (no resolved_by): falls back to heuristic."""
        perf = self._make_triplet(10.0, "F5", "HIT", "200")
        inputs = [_input(10.0, "keyboard", "F5")]
        trials = extract_sysmon_trials("s1", perf, inputs, [])
        assert trials[0].resolved_by == "human"


# ── extract_comms_trials ─────────────────────────────────────────────────────


class TestExtractCommsTrials:
    def _make_9tuple(
        self,
        t: float,
        sdt: str = "HIT",
        needed: str = "1",
        target_radio: str = "NAV_2",
        responded_radio: str = "NAV_2",
        target_freq: str = "114.2",
        responded_freq: str = "114.2",
        correct_radio: str = "1",
        deviation: str = "0.0",
        rt: str = "4640",
        resolved_by: str | None = None,
    ) -> list[RawRow]:
        rows = [
            _perf(t, "communications", "response_was_needed", needed),
            _perf(t, "communications", "target_radio", target_radio),
            _perf(t, "communications", "responded_radio", responded_radio),
            _perf(t, "communications", "target_frequency", target_freq),
            _perf(t, "communications", "responded_frequency", responded_freq),
            _perf(t, "communications", "correct_radio", correct_radio),
            _perf(t, "communications", "response_deviation", deviation),
            _perf(t, "communications", "response_time", rt),
            _perf(t, "communications", "sdt_value", sdt),
        ]
        if resolved_by is not None:
            rows.append(_perf(t, "communications", "resolved_by", resolved_by))
        return rows

    def test_hit_trial(self) -> None:
        perf = self._make_9tuple(20.0)
        inputs = [_input(20.0, "keyboard", "SPACE")]
        trials = extract_comms_trials("s1", perf, inputs, [])
        assert len(trials) == 1
        t = trials[0]
        assert t.sdt_value == "HIT"
        assert t.target_radio == "NAV_2"
        assert t.responded_radio == "NAV_2"
        assert t.response_time_ms == pytest.approx(4640.0)
        assert t.resolved_by == "human"

    def test_miss_trial(self) -> None:
        perf = self._make_9tuple(
            20.0,
            sdt="MISS",
            responded_radio="nan",
            responded_freq="nan",
            correct_radio="0",
            deviation="nan",
            rt="nan",
        )
        trials = extract_comms_trials("s1", perf, [], [])
        assert len(trials) == 1
        assert trials[0].sdt_value == "MISS"
        assert math.isnan(trials[0].response_time_ms)
        assert trials[0].resolved_by == ""

    def test_miss_new_order(self) -> None:
        """The MISS code path now uses the same order as confirm_response."""
        t = 20.0
        perf = [
            _perf(t, "communications", "response_was_needed", "True"),
            _perf(t, "communications", "target_radio", "COM_2"),
            _perf(t, "communications", "responded_radio", "nan"),
            _perf(t, "communications", "target_frequency", "127.9"),
            _perf(t, "communications", "responded_frequency", "nan"),
            _perf(t, "communications", "correct_radio", "False"),
            _perf(t, "communications", "response_deviation", "nan"),
            _perf(t, "communications", "response_time", "nan"),
            _perf(t, "communications", "sdt_value", "MISS"),
            _perf(t, "communications", "resolved_by", ""),
        ]
        trials = extract_comms_trials("s1", perf, [], [])
        assert len(trials) == 1
        assert trials[0].target_radio == "COM_2"
        assert trials[0].target_frequency == "127.9"
        assert trials[0].sdt_value == "MISS"
        assert trials[0].resolved_by == ""

    def test_miss_old_order_backward_compat(self) -> None:
        """Old CSV format: MISS with old field order (no resolved_by) still works."""
        t = 20.0
        perf = [
            _perf(t, "communications", "target_radio", "COM_2"),
            _perf(t, "communications", "target_frequency", "127.9"),
            _perf(t, "communications", "response_was_needed", "1"),
            _perf(t, "communications", "responded_radio", "nan"),
            _perf(t, "communications", "responded_frequency", "nan"),
            _perf(t, "communications", "correct_radio", "0"),
            _perf(t, "communications", "response_deviation", "nan"),
            _perf(t, "communications", "response_time", "nan"),
            _perf(t, "communications", "sdt_value", "MISS"),
        ]
        trials = extract_comms_trials("s1", perf, [], [])
        assert len(trials) == 1
        assert trials[0].target_radio == "COM_2"
        assert trials[0].sdt_value == "MISS"
        assert trials[0].resolved_by == ""  # heuristic fallback for MISS

    def test_bad_radio(self) -> None:
        perf = self._make_9tuple(
            20.0,
            sdt="BAD_RADIO",
            target_radio="NAV_1",
            responded_radio="COM_2",
            correct_radio="0",
            deviation="0.0",
        )
        inputs = [_input(20.0, "keyboard", "SPACE")]
        trials = extract_comms_trials("s1", perf, inputs, [])
        assert trials[0].sdt_value == "BAD_RADIO"

    def test_multiple_trials(self) -> None:
        perf = self._make_9tuple(10.0, sdt="HIT") + self._make_9tuple(
            20.0, sdt="MISS", rt="nan", responded_radio="nan", responded_freq="nan", correct_radio="0", deviation="nan"
        )
        inputs = [_input(10.0, "keyboard", "SPACE")]
        trials = extract_comms_trials("s1", perf, inputs, [])
        assert len(trials) == 2
        assert [t.trial_number for t in trials] == [1, 2]

    def test_no_sdt_value_skipped(self) -> None:
        perf = [_perf(10.0, "communications", "target_radio", "NAV_2")]
        trials = extract_comms_trials("s1", perf, [], [])
        assert len(trials) == 0

    def test_resolved_by_from_csv(self) -> None:
        """New format: resolved_by is read directly from the CSV."""
        perf = self._make_9tuple(20.0, resolved_by="agent")
        trials = extract_comms_trials("s1", perf, [], [])
        assert trials[0].resolved_by == "agent"

    def test_resolved_by_csv_overrides_heuristic(self) -> None:
        """When resolved_by is in CSV, the heuristic is not used."""
        perf = self._make_9tuple(20.0, resolved_by="human")
        auto = [(0.0, float("inf"))]
        trials = extract_comms_trials("s1", perf, [], auto)
        assert trials[0].resolved_by == "human"

    def test_fallback_heuristic_without_resolved_by(self) -> None:
        """Old format (no resolved_by): falls back to heuristic."""
        perf = self._make_9tuple(20.0)
        inputs = [_input(20.0, "keyboard", "SPACE")]
        trials = extract_comms_trials("s1", perf, inputs, [])
        assert trials[0].resolved_by == "human"


# ── compute_summary ──────────────────────────────────────────────────────────


class TestComputeSummary:
    def test_duration(self) -> None:
        perf = [_perf(2.0, "track", "cursor_in_target", "1"), _perf(12.0, "track", "cursor_in_target", "0")]
        s = compute_summary("s1", perf, [], [], [])
        assert s.duration_sec == pytest.approx(10.0)

    # ── Sysmon summary ───────────────────────────────────────────────────

    def test_sysmon_counts(self) -> None:
        trials = [
            SysmonTrial("s", 10, 1, "F5", "HIT", 200, "human"),
            SysmonTrial("s", 20, 2, "F1", "HIT", 400, "human"),
            SysmonTrial("s", 30, 3, "F3", "MISS", float("nan"), ""),
            SysmonTrial("s", 40, 4, "F2", "FA", float("nan"), "human"),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, trials, [], [])
        assert s.sysmon_n_trials == 4
        assert s.sysmon_hit_count == 2
        assert s.sysmon_miss_count == 1
        assert s.sysmon_fa_count == 1
        assert s.sysmon_hit_rate == pytest.approx(2 / 3)

    def test_sysmon_rt_stats(self) -> None:
        trials = [
            SysmonTrial("s", 10, 1, "F5", "HIT", 1000, "human"),
            SysmonTrial("s", 20, 2, "F1", "HIT", 3000, "human"),
            SysmonTrial("s", 30, 3, "F3", "MISS", float("nan"), ""),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, trials, [], [])
        assert s.sysmon_mean_rt_sec == pytest.approx(2.0)
        assert s.sysmon_median_rt_sec == pytest.approx(2.0)
        assert s.sysmon_sd_rt_sec > 0

    def test_sysmon_excludes_agent(self) -> None:
        trials = [
            SysmonTrial("s", 10, 1, "F5", "HIT", 200, "human"),
            SysmonTrial("s", 20, 2, "F1", "HIT", 9000, "agent"),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, trials, [], [])
        assert s.sysmon_n_trials == 1
        assert s.sysmon_hit_count == 1
        assert s.sysmon_mean_rt_sec == pytest.approx(0.2)

    def test_sysmon_excludes_auto(self) -> None:
        trials = [
            SysmonTrial("s", 10, 1, "F5", "HIT", 1000, "auto"),
            SysmonTrial("s", 20, 2, "F1", "MISS", float("nan"), ""),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, trials, [], [])
        assert s.sysmon_n_trials == 1  # only the MISS
        assert s.sysmon_hit_count == 0

    def test_sysmon_no_trials(self) -> None:
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, [], [], [])
        assert s.sysmon_n_trials == 0
        assert math.isnan(s.sysmon_hit_rate)
        assert math.isnan(s.sysmon_mean_rt_sec)

    # ── Track summary ────────────────────────────────────────────────────

    def test_track_proportion(self) -> None:
        perf = [
            _perf(1.0, "track", "cursor_in_target", "1"),
            _perf(1.0, "track", "center_deviation", "0.0"),
            _perf(2.0, "track", "cursor_in_target", "1"),
            _perf(2.0, "track", "center_deviation", "10.0"),
            _perf(3.0, "track", "cursor_in_target", "0"),
            _perf(3.0, "track", "center_deviation", "50.0"),
            _perf(4.0, "track", "cursor_in_target", "0"),
            _perf(4.0, "track", "center_deviation", "80.0"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.track_proportion_in_target == pytest.approx(0.5)
        assert s.track_mean_deviation == pytest.approx(35.0)

    def test_track_excursions(self) -> None:
        perf = [
            _perf(1.0, "track", "cursor_in_target", "1"),
            _perf(1.0, "track", "center_deviation", "0.0"),
            _perf(1.0, "track", "response_time", "2000"),
            _perf(2.0, "track", "cursor_in_target", "1"),
            _perf(2.0, "track", "center_deviation", "5.0"),
            _perf(2.0, "track", "response_time", "4000"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.track_n_excursions == 2
        assert s.track_mean_excursion_rt_sec == pytest.approx(3.0)

    def test_track_excludes_auto_periods(self) -> None:
        perf = [
            _perf(1.0, "track", "cursor_in_target", "0"),
            _perf(1.0, "track", "center_deviation", "100.0"),
            _perf(8.0, "track", "cursor_in_target", "1"),  # during auto
            _perf(8.0, "track", "center_deviation", "0.0"),
        ]
        events = [
            _event(5.0, "track", "automaticsolver", "1"),
            _event(15.0, "track", "automaticsolver", "0"),
        ]
        s = compute_summary("s", perf, [], [], events)
        assert s.track_proportion_in_target == pytest.approx(0.0)
        assert s.track_mean_deviation == pytest.approx(100.0)

    # ── Communications summary ───────────────────────────────────────────

    def test_comms_counts(self) -> None:
        trials = [
            CommsTrial("s", 10, 1, "HIT", "1", "NAV_2", "NAV_2", "114.2", "114.2", "1", "0.0", 4000, "human"),
            CommsTrial("s", 20, 2, "MISS", "1", "COM_1", "nan", "128.1", "nan", "0", "nan", float("nan"), ""),
            CommsTrial("s", 30, 3, "FA", "0", "nan", "NAV_1", "nan", "120.0", "nan", "nan", 3000, "human"),
            CommsTrial("s", 40, 4, "BAD_RADIO", "1", "NAV_1", "COM_2", "114.2", "114.2", "0", "0.0", 5000, "human"),
            CommsTrial("s", 50, 5, "BAD_FREQ", "1", "NAV_2", "NAV_2", "114.2", "115.0", "1", "0.8", 6000, "human"),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, [], trials, [])
        assert s.comms_n_trials == 5
        assert s.comms_hit_count == 1
        assert s.comms_miss_count == 1
        assert s.comms_fa_count == 1
        assert s.comms_bad_radio_count == 1
        assert s.comms_bad_freq_count == 1
        # hit_rate = 1 / (1 + 1 + 1 + 1) = 0.25  (FA excluded from denom)
        assert s.comms_hit_rate == pytest.approx(0.25)

    def test_comms_rt_excludes_miss(self) -> None:
        trials = [
            CommsTrial("s", 10, 1, "HIT", "1", "NAV_2", "NAV_2", "114.2", "114.2", "1", "0.0", 2000, "human"),
            CommsTrial("s", 20, 2, "MISS", "1", "COM_1", "nan", "128.1", "nan", "0", "nan", float("nan"), ""),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, [], trials, [])
        assert s.comms_mean_rt_sec == pytest.approx(2.0)

    def test_comms_freq_deviation(self) -> None:
        trials = [
            CommsTrial("s", 10, 1, "BAD_FREQ", "1", "N", "N", "114.2", "115.0", "1", "0.8", 5000, "human"),
            CommsTrial("s", 20, 2, "BAD_FREQ", "1", "N", "N", "114.2", "113.0", "1", "-1.2", 5000, "human"),
        ]
        perf = [_perf(0.0, "track", "cursor_in_target", "1")]
        s = compute_summary("s", perf, [], trials, [])
        assert s.comms_mean_freq_deviation == pytest.approx(1.0)

    # ── Resman summary ───────────────────────────────────────────────────

    def test_resman_tolerance(self) -> None:
        perf = [
            _perf(1.0, "resman", "a_in_tolerance", "1"),
            _perf(1.0, "resman", "a_deviation", "10"),
            _perf(1.0, "resman", "b_in_tolerance", "0"),
            _perf(1.0, "resman", "b_deviation", "500"),
            _perf(2.0, "resman", "a_in_tolerance", "1"),
            _perf(2.0, "resman", "a_deviation", "20"),
            _perf(2.0, "resman", "b_in_tolerance", "1"),
            _perf(2.0, "resman", "b_deviation", "-30"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.resman_a_proportion_in_tolerance == pytest.approx(1.0)
        assert s.resman_b_proportion_in_tolerance == pytest.approx(0.5)
        assert s.resman_a_mean_deviation == pytest.approx(15.0)
        assert s.resman_b_mean_deviation == pytest.approx(235.0)

    def test_resman_excursions(self) -> None:
        perf = [
            _perf(1.0, "resman", "a_response_time", "3000"),
            _perf(1.0, "resman", "a_in_tolerance", "1"),
            _perf(1.0, "resman", "a_deviation", "0"),
            _perf(1.0, "resman", "b_in_tolerance", "1"),
            _perf(1.0, "resman", "b_deviation", "0"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.resman_a_n_excursions == 1
        assert s.resman_a_mean_excursion_rt_sec == pytest.approx(3.0)
        assert s.resman_b_n_excursions == 0

    def test_resman_mean_deviation_ab(self) -> None:
        perf = [
            _perf(1.0, "resman", "a_in_tolerance", "1"),
            _perf(1.0, "resman", "a_deviation", "100"),
            _perf(1.0, "resman", "b_in_tolerance", "0"),
            _perf(1.0, "resman", "b_deviation", "200"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.resman_mean_deviation_ab == pytest.approx(150.0)

    def test_resman_excludes_auto_periods(self) -> None:
        perf = [
            _perf(1.0, "resman", "a_in_tolerance", "0"),
            _perf(1.0, "resman", "a_deviation", "500"),
            _perf(1.0, "resman", "b_in_tolerance", "0"),
            _perf(1.0, "resman", "b_deviation", "500"),
            _perf(8.0, "resman", "a_in_tolerance", "1"),
            _perf(8.0, "resman", "a_deviation", "0"),
            _perf(8.0, "resman", "b_in_tolerance", "1"),
            _perf(8.0, "resman", "b_deviation", "0"),
        ]
        events = [
            _event(5.0, "resman", "automaticsolver", "1"),
            _event(15.0, "resman", "automaticsolver", "0"),
        ]
        s = compute_summary("s", perf, [], [], events)
        # Only t=1.0 should be counted (t=8.0 is during automation)
        assert s.resman_a_proportion_in_tolerance == pytest.approx(0.0)
        assert s.resman_a_mean_deviation == pytest.approx(500.0)

    # ── Genericscales summary ────────────────────────────────────────────

    def test_scales_single_passage(self) -> None:
        perf = [
            _perf(60.0, "genericscales", "Mental demand", "75"),
            _perf(60.0, "genericscales", "Physical demand", "20"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.scales["scale_Mental_demand_1"] == pytest.approx(75.0)
        assert s.scales["scale_Physical_demand_1"] == pytest.approx(20.0)

    def test_scales_two_passages(self) -> None:
        perf = [
            _perf(60.0, "genericscales", "Effort", "30"),
            _perf(120.0, "genericscales", "Effort", "70"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.scales["scale_Effort_1"] == pytest.approx(30.0)
        assert s.scales["scale_Effort_2"] == pytest.approx(70.0)

    def test_scales_with_presentation_number(self) -> None:
        """New format: presentation_number is read from CSV."""
        perf = [
            _perf(60.0, "genericscales", "presentation_number", "1"),
            _perf(60.0, "genericscales", "Effort", "30"),
            _perf(120.0, "genericscales", "presentation_number", "2"),
            _perf(120.0, "genericscales", "Effort", "70"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.scales["scale_Effort_1"] == pytest.approx(30.0)
        assert s.scales["scale_Effort_2"] == pytest.approx(70.0)
        assert "scale_presentation_number_1" not in s.scales

    def test_scales_without_presentation_number_backward_compat(self) -> None:
        """Old format: no presentation_number, uses counting fallback."""
        perf = [
            _perf(60.0, "genericscales", "Effort", "30"),
            _perf(60.0, "genericscales", "Frustration", "40"),
            _perf(120.0, "genericscales", "Effort", "70"),
            _perf(120.0, "genericscales", "Frustration", "80"),
        ]
        s = compute_summary("s", perf, [], [], [])
        assert s.scales["scale_Effort_1"] == pytest.approx(30.0)
        assert s.scales["scale_Frustration_1"] == pytest.approx(40.0)
        assert s.scales["scale_Effort_2"] == pytest.approx(70.0)
        assert s.scales["scale_Frustration_2"] == pytest.approx(80.0)


# ── build_timeseries ─────────────────────────────────────────────────────────


class TestBuildTimeseries:
    def test_empty_data(self) -> None:
        series = build_timeseries("s", [], [], 1.0)
        assert series == []

    def test_locf_resampling(self) -> None:
        perf = [
            _perf(0.5, "track", "cursor_in_target", "1"),
            _perf(0.5, "track", "center_deviation", "5.0"),
            _perf(2.5, "track", "cursor_in_target", "0"),
            _perf(2.5, "track", "center_deviation", "50.0"),
        ]
        series = build_timeseries("s", perf, [], 1.0)
        # t=0: no data yet (obs at 0.5 consumed at t=0? No, 0.5 > 0)
        assert series[0].time_sec == 0.0
        assert series[0].track_in_target == ""  # no observation yet

        # t=1: obs at 0.5 consumed (0.5 <= 1.0)
        assert series[1].time_sec == 1.0
        assert series[1].track_in_target == "1"
        assert series[1].track_deviation == "5.0"

        # t=2: still carries forward from 0.5
        assert series[2].time_sec == 2.0
        assert series[2].track_in_target == "1"

        # t=3: obs at 2.5 consumed
        # (there's no t=3 point if t_max=2.5, n_points = int(2.5/1)+1 = 3)
        # points are t=0, t=1, t=2
        assert len(series) == 3

    def test_resman_data(self) -> None:
        perf = [
            _perf(0.0, "resman", "a_in_tolerance", "1"),
            _perf(0.0, "resman", "a_deviation", "10"),
            _perf(0.0, "resman", "b_in_tolerance", "0"),
            _perf(0.0, "resman", "b_deviation", "500"),
        ]
        series = build_timeseries("s", perf, [], 1.0)
        assert len(series) == 1
        assert series[0].resman_a_in_tolerance == "1"
        assert series[0].resman_b_deviation == "500"

    def test_auto_flags(self) -> None:
        perf = [
            _perf(0.0, "track", "cursor_in_target", "1"),
            _perf(0.0, "track", "center_deviation", "0"),
            _perf(3.0, "track", "cursor_in_target", "1"),
            _perf(3.0, "track", "center_deviation", "0"),
        ]
        events = [
            _event(1.5, "track", "automaticsolver", "1"),
            _event(2.5, "track", "automaticsolver", "0"),
        ]
        series = build_timeseries("s", perf, events, 1.0)
        # t=0 → auto off, t=1 → auto off (starts at 1.5),
        # t=2 → auto on, t=3 → auto off (ends at 2.5)
        assert series[0].track_auto == 0
        assert series[1].track_auto == 0
        assert series[2].track_auto == 1
        assert series[3].track_auto == 0

    def test_custom_interval(self) -> None:
        perf = [
            _perf(0.0, "track", "cursor_in_target", "1"),
            _perf(0.0, "track", "center_deviation", "0"),
            _perf(1.0, "track", "cursor_in_target", "0"),
            _perf(1.0, "track", "center_deviation", "50"),
        ]
        series = build_timeseries("s", perf, [], 0.5)
        # t_max=1.0, n_points = int(1.0/0.5)+1 = 3 → t=0, 0.5, 1.0
        assert len(series) == 3
        assert series[0].time_sec == pytest.approx(0.0)
        assert series[1].time_sec == pytest.approx(0.5)
        assert series[2].time_sec == pytest.approx(1.0)


# ── write_trials ─────────────────────────────────────────────────────────────


class TestWriteTrials:
    def test_sysmon_row_format(self, tmp_path: Path) -> None:
        out = tmp_path / "trials.csv"
        trials = [SysmonTrial("s1", 10.5, 1, "F5", "HIT", 200.0, "human")]
        write_trials(trials, [], out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        assert rows[0] == TRIALS_COLUMNS
        data = dict(zip(rows[0], rows[1]))
        assert data["session"] == "s1"
        assert data["task"] == "sysmon"
        assert data["gauge_name"] == "F5"
        assert data["signal_detection"] == "HIT"
        assert data["response_time_sec"] == "0.2"
        assert data["resolved_by"] == "human"
        assert data["sdt_value"] == ""  # comms column empty

    def test_comms_row_format(self, tmp_path: Path) -> None:
        out = tmp_path / "trials.csv"
        trials = [
            CommsTrial(
                "s1",
                20.0,
                1,
                "HIT",
                "1",
                "NAV_2",
                "NAV_2",
                "114.2",
                "114.2",
                "1",
                "0.0",
                4640.0,
                "human",
            )
        ]
        write_trials([], trials, out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        data = dict(zip(rows[0], rows[1]))
        assert data["task"] == "communications"
        assert data["sdt_value"] == "HIT"
        assert data["target_radio"] == "NAV_2"
        assert data["response_time_sec"] == "4.64"
        assert data["gauge_name"] == ""  # sysmon column empty

    def test_miss_empty_rt(self, tmp_path: Path) -> None:
        out = tmp_path / "trials.csv"
        trials = [SysmonTrial("s1", 10.0, 1, "F1", "MISS", float("nan"), "")]
        write_trials(trials, [], out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        data = dict(zip(rows[0], rows[1]))
        assert data["response_time_sec"] == ""
        assert data["resolved_by"] == ""

    def test_nan_values_become_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "trials.csv"
        trials = [
            CommsTrial(
                "s1",
                20.0,
                1,
                "MISS",
                "1",
                "COM_2",
                "nan",
                "127.9",
                "nan",
                "0",
                "nan",
                float("nan"),
                "",
            )
        ]
        write_trials([], trials, out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        data = dict(zip(rows[0], rows[1]))
        assert data["responded_radio"] == ""
        assert data["responded_frequency"] == ""
        assert data["response_deviation"] == ""

    def test_semicolon_separator(self, tmp_path: Path) -> None:
        out = tmp_path / "trials.csv"
        trials = [SysmonTrial("s1", 10.0, 1, "F5", "HIT", 200.0, "human")]
        write_trials(trials, [], out, ";")
        rows = list(csv.reader(open(out, encoding="utf-8"), delimiter=";"))
        assert len(rows[0]) == len(TRIALS_COLUMNS)


# ── write_summary ────────────────────────────────────────────────────────────


class TestWriteSummary:
    def test_basic_output(self, tmp_path: Path) -> None:
        out = tmp_path / "summary.csv"
        s = SessionSummary("s1", 60.0)
        s.sysmon_n_trials = 3
        s.sysmon_hit_count = 2
        s.sysmon_miss_count = 1
        s.sysmon_hit_rate = 2 / 3
        write_summary([s], out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        header = rows[0]
        data = dict(zip(header, rows[1]))
        assert data["session"] == "s1"
        assert data["duration_sec"] == "60"
        assert data["sysmon_n_trials"] == "3"
        assert float(data["sysmon_hit_rate"]) == pytest.approx(2 / 3)

    def test_nan_columns_empty(self, tmp_path: Path) -> None:
        out = tmp_path / "summary.csv"
        s = SessionSummary("s1", 60.0)
        write_summary([s], out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        data = dict(zip(rows[0], rows[1]))
        assert data["sysmon_mean_rt_sec"] == ""
        assert data["track_proportion_in_target"] == ""

    def test_scale_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "summary.csv"
        s1 = SessionSummary("s1", 60.0)
        s1.scales = {"scale_Effort_1": 50.0, "scale_Effort_2": 70.0}
        s2 = SessionSummary("s2", 60.0)
        s2.scales = {"scale_Effort_1": 40.0}
        write_summary([s1, s2], out, ",")
        rows = list(csv.reader(open(out, encoding="utf-8")))
        header = rows[0]
        assert "scale_Effort_1" in header
        assert "scale_Effort_2" in header
        d1 = dict(zip(header, rows[1]))
        d2 = dict(zip(header, rows[2]))
        assert d1["scale_Effort_1"] == "50"
        assert d1["scale_Effort_2"] == "70"
        assert d2["scale_Effort_1"] == "40"
        assert d2["scale_Effort_2"] == ""  # not present in s2


# ── write_timeseries ─────────────────────────────────────────────────────────


class TestWriteTimeseries:
    def test_basic_output(self, tmp_path: Path) -> None:
        out = tmp_path / "ts.csv"
        rows = [
            TimeSeriesRow("s1", 0.0, "1", "5.0", "1", "0", "10", "500", 0, 0),
            TimeSeriesRow("s1", 1.0, "0", "50.0", "1", "1", "5", "20", 0, 1),
        ]
        write_timeseries(rows, out, ",")
        result = list(csv.reader(open(out, encoding="utf-8")))
        assert result[0] == TIMESERIES_COLUMNS
        d = dict(zip(result[0], result[1]))
        assert d["session"] == "s1"
        assert d["time_sec"] == "0"
        assert d["track_in_target"] == "1"
        assert d["track_auto"] == "0"

    def test_empty_values(self, tmp_path: Path) -> None:
        out = tmp_path / "ts.csv"
        rows = [TimeSeriesRow("s1", 0.0, "", "", "", "", "", "", 0, 0)]
        write_timeseries(rows, out, ",")
        result = list(csv.reader(open(out, encoding="utf-8")))
        d = dict(zip(result[0], result[1]))
        assert d["track_in_target"] == ""
        assert d["track_deviation"] == ""


# ── _collect_csv_paths ───────────────────────────────────────────────────────


class TestCollectCsvPaths:
    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("header\n", encoding="utf-8")
        paths = _collect_csv_paths([str(f)])
        assert len(paths) == 1
        assert paths[0] == f

    def test_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.csv").write_text("h\n", encoding="utf-8")
        (tmp_path / "b.csv").write_text("h\n", encoding="utf-8")
        (tmp_path / "c.txt").write_text("h\n", encoding="utf-8")
        paths = _collect_csv_paths([str(tmp_path)])
        assert len(paths) == 2
        assert all(p.suffix == ".csv" for p in paths)

    def test_nonexistent_warns(self, tmp_path: Path, capsys) -> None:
        paths = _collect_csv_paths([str(tmp_path / "nope.xyz")])
        assert paths == []
        assert "Warning" in capsys.readouterr().err


# ── End-to-end: load → extract → summary → write ────────────────────────────


class TestEndToEnd:
    def _build_session_csv(self, tmp_path: Path) -> Path:
        """Create a synthetic but realistic session CSV."""
        csv_path = tmp_path / "session_e2e.csv"
        rows = [
            # -- Parameters / events ---
            ["100", "0.0", "parameter", "sysmon", "automaticsolver", "0"],
            ["100", "0.0", "parameter", "track", "automaticsolver", "0"],
            ["100", "0.0", "parameter", "resman", "automaticsolver", "0"],
            # -- Track performance (4 observations) ---
            ["101", "1.0", "performance", "track", "cursor_in_target", "1"],
            ["101", "1.0", "performance", "track", "center_deviation", "5.0"],
            ["102", "2.0", "performance", "track", "cursor_in_target", "1"],
            ["102", "2.0", "performance", "track", "center_deviation", "10.0"],
            ["103", "3.0", "performance", "track", "cursor_in_target", "0"],
            ["103", "3.0", "performance", "track", "center_deviation", "80.0"],
            ["104", "4.0", "performance", "track", "cursor_in_target", "0"],
            ["104", "4.0", "performance", "track", "center_deviation", "90.0"],
            # -- Resman performance (2 observations) ---
            ["101", "1.0", "performance", "resman", "a_in_tolerance", "1"],
            ["101", "1.0", "performance", "resman", "a_deviation", "20"],
            ["101", "1.0", "performance", "resman", "b_in_tolerance", "1"],
            ["101", "1.0", "performance", "resman", "b_deviation", "-10"],
            ["103", "3.0", "performance", "resman", "a_in_tolerance", "0"],
            ["103", "3.0", "performance", "resman", "a_deviation", "400"],
            ["103", "3.0", "performance", "resman", "b_in_tolerance", "0"],
            ["103", "3.0", "performance", "resman", "b_deviation", "600"],
            # -- Sysmon: 1 HIT + 1 MISS ---
            ["102", "2.0", "input", "keyboard", "F5", "press"],
            ["102", "2.0", "performance", "sysmon", "name", "F5"],
            ["102", "2.0", "performance", "sysmon", "signal_detection", "HIT"],
            ["102", "2.0", "performance", "sysmon", "response_time", "500"],
            ["104", "4.0", "performance", "sysmon", "name", "F1"],
            ["104", "4.0", "performance", "sysmon", "signal_detection", "MISS"],
            ["104", "4.0", "performance", "sysmon", "response_time", "nan"],
            # -- Comms: 1 HIT ---
            ["103", "3.0", "input", "keyboard", "SPACE", "press"],
            ["103", "3.0", "performance", "communications", "response_was_needed", "1"],
            ["103", "3.0", "performance", "communications", "target_radio", "NAV_1"],
            ["103", "3.0", "performance", "communications", "responded_radio", "NAV_1"],
            ["103", "3.0", "performance", "communications", "target_frequency", "112.5"],
            ["103", "3.0", "performance", "communications", "responded_frequency", "112.5"],
            ["103", "3.0", "performance", "communications", "correct_radio", "1"],
            ["103", "3.0", "performance", "communications", "response_deviation", "0.0"],
            ["103", "3.0", "performance", "communications", "response_time", "6000"],
            ["103", "3.0", "performance", "communications", "sdt_value", "HIT"],
        ]
        _write_csv(csv_path, rows)
        return csv_path

    def test_load_and_extract(self, tmp_path: Path) -> None:
        csv_path = self._build_session_csv(tmp_path)
        perf, inp, evt = load_session(csv_path)

        sysmon_auto = _build_auto_intervals(evt, "sysmon")
        comms_auto = _build_auto_intervals(evt, "communications")

        sysmon_trials = extract_sysmon_trials("e2e", perf, inp, sysmon_auto)
        comms_trials = extract_comms_trials("e2e", perf, inp, comms_auto)

        assert len(sysmon_trials) == 2
        assert sysmon_trials[0].signal_detection == "HIT"
        assert sysmon_trials[0].resolved_by == "human"
        assert sysmon_trials[1].signal_detection == "MISS"
        assert sysmon_trials[1].resolved_by == ""

        assert len(comms_trials) == 1
        assert comms_trials[0].sdt_value == "HIT"
        assert comms_trials[0].resolved_by == "human"

    def test_summary_computation(self, tmp_path: Path) -> None:
        csv_path = self._build_session_csv(tmp_path)
        perf, inp, evt = load_session(csv_path)

        sysmon_auto = _build_auto_intervals(evt, "sysmon")
        comms_auto = _build_auto_intervals(evt, "communications")

        sysmon = extract_sysmon_trials("e2e", perf, inp, sysmon_auto)
        comms = extract_comms_trials("e2e", perf, inp, comms_auto)
        s = compute_summary("e2e", perf, sysmon, comms, evt)

        assert s.duration_sec == pytest.approx(3.0)
        assert s.sysmon_n_trials == 2
        assert s.sysmon_hit_count == 1
        assert s.sysmon_miss_count == 1
        assert s.sysmon_hit_rate == pytest.approx(0.5)
        assert s.sysmon_mean_rt_sec == pytest.approx(0.5)

        assert s.track_proportion_in_target == pytest.approx(0.5)
        assert s.track_mean_deviation == pytest.approx(46.25)

        assert s.comms_n_trials == 1
        assert s.comms_hit_count == 1
        assert s.comms_hit_rate == pytest.approx(1.0)
        assert s.comms_mean_rt_sec == pytest.approx(6.0)

        assert s.resman_a_proportion_in_tolerance == pytest.approx(0.5)
        assert s.resman_b_proportion_in_tolerance == pytest.approx(0.5)
        assert s.resman_a_mean_deviation == pytest.approx(210.0)
        assert s.resman_b_mean_deviation == pytest.approx(295.0)
        assert s.resman_mean_deviation_ab == pytest.approx(252.5)

    def test_timeseries(self, tmp_path: Path) -> None:
        csv_path = self._build_session_csv(tmp_path)
        perf, _inp, evt = load_session(csv_path)
        ts = build_timeseries("e2e", perf, evt, 1.0)
        # t_max = 4.0, n_points = 5 → t=0,1,2,3,4
        assert len(ts) == 5
        assert ts[0].track_in_target == ""  # no data at t=0
        assert ts[1].track_in_target == "1"
        assert ts[3].track_in_target == "0"

    def test_full_pipeline_writes(self, tmp_path: Path) -> None:
        csv_path = self._build_session_csv(tmp_path)
        perf, inp, evt = load_session(csv_path)

        sysmon_auto = _build_auto_intervals(evt, "sysmon")
        comms_auto = _build_auto_intervals(evt, "communications")

        sysmon = extract_sysmon_trials("e2e", perf, inp, sysmon_auto)
        comms = extract_comms_trials("e2e", perf, inp, comms_auto)
        summary = compute_summary("e2e", perf, sysmon, comms, evt)
        ts = build_timeseries("e2e", perf, evt, 1.0)

        write_trials(sysmon, comms, tmp_path / "trials.csv", ",")
        write_summary([summary], tmp_path / "summary.csv", ",")
        write_timeseries(ts, tmp_path / "timeseries.csv", ",")

        # Verify files exist and have correct row counts
        trials_rows = list(csv.reader(open(tmp_path / "trials.csv", encoding="utf-8")))
        assert len(trials_rows) == 4  # header + 2 sysmon + 1 comms

        summary_rows = list(csv.reader(open(tmp_path / "summary.csv", encoding="utf-8")))
        assert len(summary_rows) == 2  # header + 1 session

        ts_rows = list(csv.reader(open(tmp_path / "timeseries.csv", encoding="utf-8")))
        assert len(ts_rows) == 6  # header + 5 time points

    def test_agent_trials_excluded_from_summary(self, tmp_path: Path) -> None:
        """When an agent resolves a trial, it is excluded from summary."""
        csv_path = tmp_path / "agent.csv"
        rows = [
            ["100", "0.0", "parameter", "sysmon", "automaticsolver", "0"],
            # HIT by human
            ["101", "1.0", "input", "keyboard", "F5", "press"],
            ["101", "1.0", "performance", "sysmon", "name", "F5"],
            ["101", "1.0", "performance", "sysmon", "signal_detection", "HIT"],
            ["101", "1.0", "performance", "sysmon", "response_time", "200"],
            # HIT by agent
            ["102", "2.0", "input", "agent", "F1", "press"],
            ["102", "2.0", "performance", "sysmon", "name", "F1"],
            ["102", "2.0", "performance", "sysmon", "signal_detection", "HIT"],
            ["102", "2.0", "performance", "sysmon", "response_time", "9000"],
        ]
        _write_csv(csv_path, rows)
        perf, inp, evt = load_session(csv_path)
        sysmon_auto = _build_auto_intervals(evt, "sysmon")
        trials = extract_sysmon_trials("ag", perf, inp, sysmon_auto)
        s = compute_summary("ag", perf, trials, [], evt)

        assert len(trials) == 2
        assert trials[0].resolved_by == "human"
        assert trials[1].resolved_by == "agent"
        assert s.sysmon_n_trials == 1  # only human
        assert s.sysmon_hit_count == 1
        assert s.sysmon_mean_rt_sec == pytest.approx(0.2)

    def test_builtin_auto_excluded_from_summary(self, tmp_path: Path) -> None:
        """Built-in automaticsolver (no input events) → resolved_by='auto'."""
        csv_path = tmp_path / "auto.csv"
        rows = [
            ["100", "0.0", "event", "sysmon", "automaticsolver", "1"],
            ["100", "0.0", "parameter", "sysmon", "automaticsolver", "1"],
            ["101", "1.0", "performance", "sysmon", "name", "F2"],
            ["101", "1.0", "performance", "sysmon", "signal_detection", "HIT"],
            ["101", "1.0", "performance", "sysmon", "response_time", "1000"],
        ]
        _write_csv(csv_path, rows)
        perf, inp, evt = load_session(csv_path)
        sysmon_auto = _build_auto_intervals(evt, "sysmon")
        trials = extract_sysmon_trials("at", perf, inp, sysmon_auto)
        s = compute_summary("at", perf, trials, [], evt)

        assert len(trials) == 1
        assert trials[0].resolved_by == "auto"
        assert s.sysmon_n_trials == 0
        assert s.sysmon_hit_count == 0
