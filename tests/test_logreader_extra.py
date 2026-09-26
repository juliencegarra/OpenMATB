"""Extra tests for core.logreader - reading real CSV session logs from disk.

Covers session lookup (by ID or by path), classification of rows (events,
inputs, states, performance), blocking-segment detection and the
replay_time -> scenario_time mapping, and degraded logs (empty, header only,
truncated by a crash).
"""

from unittest.mock import patch

import pytest

import core.constants
from core.logreader import BLOCKING_THRESHOLD, LogReader

HEADER = "logtime,scenario_time,type,module,address,value"


def _write_log(path, rows, header=True):
    """Write a session CSV log (list of 6-tuples or raw strings) and return its path."""
    lines = [HEADER] if header else []
    for r in rows:
        if isinstance(r, str):
            lines.append(r)
        else:
            lines.append(",".join(f'"{c}"' if isinstance(c, str) and "," in c else str(c) for c in r))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _reader(tmp_path, rows, name="12_260101_120000.csv", **kw):
    """Write rows in tmp_path and open them with LogReader(session_path=...)."""
    path = _write_log(tmp_path / name, rows, **kw)
    return LogReader(session_path=str(path))


def _linear_rows(start_lt, start_st, n, step=0.1, module="track", addr="cursor_proportional", value="(0.0, 0.0)"):
    """Rows where logtime and scenario_time advance together (no blocking)."""
    return [(start_lt + i * step, start_st + i * step, "state", module, addr, value) for i in range(n)]


# ──── Session lookup ────


class TestSessionLookup:
    def test_session_path_sets_id_from_file_name(self, tmp_path):
        """The session ID is parsed from the '<id>_<date>.csv' file name."""
        lr = _reader(tmp_path, [(100.0, 0, "event", "sysmon", "self", "start")], name="42_260101_120000.csv")
        assert lr.replay_session_id == 42

    def test_session_path_with_non_numeric_name(self, tmp_path):
        """A file name without numeric prefix keeps the given ID and still loads."""
        path = _write_log(tmp_path / "mysession.csv", [(100.0, 0, "event", "sysmon", "self", "start")])
        lr = LogReader(replay_session_id=None, session_path=str(path))
        assert lr.replay_session_id is None
        assert lr.session_file_path == path

    def test_lookup_by_id_finds_file_in_dated_folder(self, tmp_path, mock_errors):
        """A session ID is searched recursively in the SESSIONS folder."""
        _write_log(
            tmp_path / "2026-01-01" / "7_260101_120000.csv",
            [(1.0, 0, "event", "sysmon", "self", "start"), (2.0, 1, "event", "sysmon", "self", "stop")],
        )
        _write_log(tmp_path / "2026-01-01" / "17_260101_130000.csv", [(1.0, 0, "event", "track", "self", "start")])
        with patch.dict(core.constants.PATHS, {"SESSIONS": tmp_path}):
            lr = LogReader(7)
        assert lr.session_file_path.name == "7_260101_120000.csv"
        assert lr.contents == ["0:00:01;sysmon;stop"]
        mock_errors.add_error.assert_not_called()

    def test_lookup_missing_id_is_fatal(self, tmp_path, mock_errors):
        """An unknown session ID reports a fatal error and leaves the reader empty."""
        with patch.dict(core.constants.PATHS, {"SESSIONS": tmp_path}):
            lr = LogReader(99)
        assert lr.session_file_path is None
        assert lr.contents == [] and lr.inputs == []
        msg = mock_errors.add_error.call_args[0][0]
        assert "99" in msg
        assert mock_errors.add_error.call_args[1]["fatal"] is True

    def test_lookup_ambiguous_id_is_fatal(self, tmp_path, mock_errors):
        """Two files with the same session ID are reported as a fatal error."""
        row = [(1.0, 0, "event", "sysmon", "self", "start")]
        _write_log(tmp_path / "a" / "5_260101_120000.csv", row)
        _write_log(tmp_path / "b" / "5_260102_120000.csv", row)
        with patch.dict(core.constants.PATHS, {"SESSIONS": tmp_path}):
            lr = LogReader(5)
        assert lr.session_file_path is None
        assert "Multiple" in mock_errors.add_error.call_args[0][0]
        assert mock_errors.add_error.call_args[1]["fatal"] is True

    def test_reload_without_file_is_noop(self):
        """reload_session() does nothing when no file was found."""
        lr = object.__new__(LogReader)
        lr.session_file_path = None
        lr.contents = ["sentinel"]
        lr.reload_session()
        assert lr.contents == ["sentinel"]


# ──── Degraded logs ────


class TestEmptyAndTruncatedLogs:
    def test_zero_byte_file(self, tmp_path):
        """A zero-byte file (session crashed before the header) yields an empty reader."""
        path = tmp_path / "3_260101_120000.csv"
        path.write_text("", encoding="utf-8")
        lr = LogReader(session_path=str(path))
        assert lr.contents == [] and lr.inputs == [] and lr.states == []
        assert lr.session_duration == 0 and lr.duration_sec == 0
        assert lr.replay_to_scenario_time(12.0) == 12.0

    def test_header_only(self, tmp_path):
        """A log with only its header yields an empty reader."""
        lr = _reader(tmp_path, [])
        assert lr.contents == [] and lr.perf_series == {}
        assert lr.end_sec == 0 and lr.blocking_segments == []

    def test_single_row_is_not_replayed(self, tmp_path):
        """The first row is only used as time origin, never replayed."""
        lr = _reader(tmp_path, [(50.0, 0, "event", "sysmon", "self", "start")])
        assert lr.contents == []
        assert lr.session_duration == 0
        assert lr.blocking_segments == []

    def test_blank_lines_are_skipped(self, tmp_path):
        """Blank lines in the CSV are ignored by the reader."""
        lr = _reader(
            tmp_path,
            [(10.0, 0, "event", "sysmon", "self", "start"), "", (11.0, 1, "event", "sysmon", "self", "stop"), ""],
        )
        assert lr.contents == ["0:00:01;sysmon;stop"]

    def test_row_truncated_after_type(self, tmp_path):
        """A last row cut after its type column (crash) does not break the reader."""
        lr = _reader(
            tmp_path,
            [
                (10.0, 0, "event", "sysmon", "self", "start"),
                (11.0, 1, "event", "sysmon", "self", "stop"),
                "12.0,2.0,inp",
            ],
        )
        assert lr.contents == ["0:00:01;sysmon;stop"]
        assert lr.end_sec == 2.0
        assert lr.session_duration == pytest.approx(2.0)

    def test_row_truncated_before_scenario_time(self, tmp_path):
        """A crash-truncated last row is ignored, the rest of the session is replayable."""
        lr = _reader(
            tmp_path,
            [(10.0, 0, "event", "sysmon", "self", "start"), (11.0, 1, "event", "sysmon", "self", "stop"), "12.0"],
        )
        assert lr.contents == ["0:00:01;sysmon;stop"]


# ──── Row classification ────


class TestRowClassification:
    @pytest.fixture()
    def lr(self, tmp_path):
        rows = [
            (100.0, 0, "manual", "", "scenario_path", "basic.txt"),
            (100.1, 0.1, "event", "sysmon", "self", "start"),
            (100.2, 0.2, "event", "resman", "pump-1-state", "failure"),
            (100.3, 0.3, "event", "parallelport", "self", "start"),
            (100.4, 0.4, "input", "keyboard", "F1", "press"),
            (100.5, 0.5, "input", "agent", "F2", "press"),
            (100.6, 0.6, "input", "mouse_key", "NUM_1", "press"),
            (100.7, 0.7, "input", "track", "joystick_x", "0.5"),
            (100.8, 0.8, "input", "mouse", "x", "120"),
            (100.9, 0.9, "input", "other", "whatever", "1"),
            (101.0, 1.0, "input", "labstreaminglayer", "x", "1"),
            (101.1, 1.1, "state", "communications", "own_radio_frequency", "127.5"),
            (101.2, 1.2, "state", "track", "cursor_proportional", "(0.1, -0.2)"),
            (101.3, 1.3, "state", "resman", "slider_pump", "[1, 2]"),
            (101.4, 1.4, "state", "sysmon", "light_color", "(0, 0, 0, 255)"),
            (101.5, 1.5, "parameter", "sysmon", "title", "System monitoring"),
            (101.6, 1.6, "performance", "sysmon", "signal_detection", "HIT"),
            (101.7, 1.6, "performance", "sysmon", "response_time", "0.8"),
            (101.8, 1.8, "performance", "track", "cursor_in_target", "1"),
            (101.9, 1.0, "performance", "sysmon", "signal_detection", "MISS"),
        ]
        return _reader(tmp_path, rows)

    def test_events_become_scenario_lines(self, lr):
        """Event rows are converted to scenario lines, ignored plugins excluded."""
        assert lr.contents == ["0:00:00;sysmon;start", "0:00:00;resman;pump-1-state;failure"]

    def test_keyboard_like_inputs(self, lr):
        """keyboard, agent and mouse_key inputs are keyboard inputs."""
        assert [r["address"] for r in lr.keyboard_inputs] == ["F1", "F2", "NUM_1"]

    def test_joystick_and_mouse_inputs(self, lr):
        """Joystick axes and mouse rows go to their own lists."""
        assert [r["address"] for r in lr.joystick_inputs] == ["joystick_x"]
        assert [r["address"] for r in lr.mouse_inputs] == ["x"]

    def test_all_inputs_kept_except_ignored_plugins(self, lr):
        """Every input row is kept in inputs, except those of ignored plugins."""
        assert len(lr.inputs) == 6
        assert all(r["module"] != "labstreaminglayer" for r in lr.inputs)

    def test_replayable_states_are_evaluated(self, lr):
        """Radio, cursor and slider states are kept with their evaluated value."""
        values = {r["address"]: r["value"] for r in lr.states}
        assert values == {
            "own_radio_frequency": 127.5,
            "cursor_proportional": (0.1, -0.2),
            "slider_pump": [1, 2],
        }

    def test_performance_series_grouped_and_sorted(self, lr):
        """Performance rows are grouped by module and scenario_time, sorted by time."""
        sysmon = lr.perf_series["sysmon"]
        assert [t for t, _ in sysmon] == [1.0, 1.6]
        assert sysmon[1][1] == {"signal_detection": "HIT", "response_time": "0.8"}
        assert lr.perf_series["track"] == [(1.8, {"cursor_in_target": "1"})]
        assert len(lr.perf_rows) == 4

    def test_times(self, lr):
        """end_sec is the last scenario_time, session_duration the logtime span."""
        assert lr.end_sec == 1.0
        assert lr.duration_sec == 1.0
        assert lr.session_duration == pytest.approx(1.9)

    def test_normalized_logtime(self, lr):
        """Each kept row carries its logtime relative to the first row."""
        assert lr.keyboard_inputs[0]["normalized_logtime"] == pytest.approx(0.4)

    def test_reload_is_idempotent(self, lr):
        """Reloading the same session does not duplicate any entry."""
        before = (list(lr.contents), len(lr.inputs), len(lr.states), dict(lr.perf_series))
        lr.reload_session()
        assert (lr.contents, len(lr.inputs), len(lr.states), lr.perf_series) == before
        assert lr.line_n == 2


# ──── Blocking segments and time mapping ────


class TestBlockingSegments:
    def test_no_blocking_is_identity(self, tmp_path):
        """Without frozen scenario_time, replay time equals scenario time."""
        lr = _reader(tmp_path, _linear_rows(1000.0, 0.0, 50))
        assert lr.blocking_segments == []
        assert lr.replay_to_scenario_time(3.3) == pytest.approx(3.3)
        assert not lr.is_in_blocking_segment(3.3)

    def test_short_freeze_is_not_blocking(self, tmp_path):
        """Simultaneous rows below the threshold are not a blocking segment."""
        rows = _linear_rows(0.0, 0.0, 10)
        rows += [(1.0 + i * 0.1, 1.0, "state", "track", "cursor_proportional", "(0, 0)") for i in range(5)]
        lr = _reader(tmp_path, rows)
        assert BLOCKING_THRESHOLD >= 0.4
        assert lr.blocking_segments == []

    def test_blocking_segment_mid_session(self, tmp_path):
        """A questionnaire freezing scenario_time maps replay time to a constant."""
        rows = _linear_rows(0.0, 0.0, 101)  # 0..10 s
        rows += [(10.0 + i, 10.0, "input", "keyboard", "UP", "press") for i in range(1, 31)]  # frozen 11..40
        rows += _linear_rows(40.1, 10.1, 50)  # resumes
        lr = _reader(tmp_path, rows)

        assert lr.blocking_segments == [(pytest.approx(10.0), pytest.approx(40.0), 10.0)]
        assert lr.replay_to_scenario_time(5.0) == pytest.approx(5.0)
        assert lr.replay_to_scenario_time(25.0) == pytest.approx(10.0)
        assert lr.replay_to_scenario_time(40.0) == pytest.approx(10.0)
        assert lr.replay_to_scenario_time(45.0) == pytest.approx(15.0)
        assert lr.is_in_blocking_segment(25.0)
        assert not lr.is_in_blocking_segment(45.0)
        assert lr.session_duration == pytest.approx(45.0)
        assert lr.end_sec == pytest.approx(15.0)

    def test_two_blocking_segments(self, tmp_path):
        """Consecutive pauses accumulate their offset in the mapping."""
        rows = _linear_rows(0.0, 0.0, 51)  # 0..5
        rows += [(5.0 + i, 5.0, "input", "keyboard", "SPACE", "release") for i in range(1, 11)]  # 6..15 frozen
        rows += _linear_rows(15.1, 5.1, 50)  # 15.1..20 -> 5.1..10
        rows += [(20.0 + i, 10.0, "input", "keyboard", "SPACE", "release") for i in range(1, 6)]  # 21..25 frozen
        rows += _linear_rows(25.1, 10.1, 10)
        lr = _reader(tmp_path, rows)

        assert len(lr.blocking_segments) == 2
        assert lr.replay_to_scenario_time(10.0) == pytest.approx(5.0)
        assert lr.replay_to_scenario_time(17.0) == pytest.approx(7.0)
        assert lr.replay_to_scenario_time(22.0) == pytest.approx(10.0)
        assert lr.replay_to_scenario_time(26.0) == pytest.approx(11.0)

    def test_blocking_at_session_start(self, tmp_path):
        """Instructions shown at t=0 are a blocking segment starting at 0."""
        rows = [(i * 1.0, 0.0, "input", "keyboard", "SPACE", "press") for i in range(6)]
        rows += _linear_rows(5.1, 0.1, 20)
        lr = _reader(tmp_path, rows)
        assert lr.blocking_segments == [(0.0, 5.0, 0.0)]
        assert lr.replay_to_scenario_time(3.0) == 0.0
        assert lr.replay_to_scenario_time(6.0) == pytest.approx(1.0)

    def test_blocking_at_session_end(self, tmp_path):
        """A final questionnaire (last group of rows) is detected as blocking."""
        rows = _linear_rows(0.0, 0.0, 51)
        rows += [(5.0 + i, 5.0, "input", "keyboard", "SPACE", "press") for i in range(1, 11)]
        lr = _reader(tmp_path, rows)
        assert lr.blocking_segments == [(pytest.approx(5.0), pytest.approx(15.0), 5.0)]
        assert lr.replay_to_scenario_time(12.0) == pytest.approx(5.0)
        # Past the end of the log, scenario time keeps flowing from the frozen value
        assert lr.replay_to_scenario_time(16.0) == pytest.approx(6.0)
        assert lr.is_in_blocking_segment(15.0)

    def test_negative_replay_time(self, tmp_path):
        """A replay time before the origin maps to scenario time 0."""
        lr = _reader(tmp_path, _linear_rows(0.0, 0.0, 5))
        assert lr.replay_to_scenario_time(-1.0) == 0.0

    def test_single_row_detection_guard(self):
        """Fewer than two rows cannot contain a blocking segment."""
        lr = object.__new__(LogReader)
        lr._detect_blocking_segments([{"scenario_time": 0.0, "normalized_logtime": 0.0}])
        assert lr.blocking_segments == []
