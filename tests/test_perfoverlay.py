# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from unittest.mock import MagicMock

import pytest

from core.container import Container
from core.perfoverlay import PerfOverlay, downsample, normalize

# ──────────────────────────────────────────────
# downsample()
# ──────────────────────────────────────────────


class TestDownsample:
    def test_no_downsampling_needed(self):
        pts = [(0, 1), (1, 2), (2, 3)]
        assert downsample(pts, 10) == pts

    def test_exact_max(self):
        pts = [(i, i) for i in range(5)]
        assert downsample(pts, 5) == pts

    def test_downsamples_large_list(self):
        pts = [(i, i * 0.1) for i in range(1000)]
        result = downsample(pts, 100)
        assert len(result) <= 102  # max_points + possible extra endpoint
        # First and last points preserved
        assert result[0] == pts[0]
        assert result[-1] == pts[-1]

    def test_last_point_always_included(self):
        pts = [(i, i) for i in range(10)]
        result = downsample(pts, 3)
        assert result[-1] == pts[-1]


# ──────────────────────────────────────────────
# normalize()
# ──────────────────────────────────────────────


class TestNormalize:
    def test_empty(self):
        assert normalize([], 0, 100) == []

    def test_constant_values(self):
        result = normalize([5, 5, 5], 0, 100)
        assert all(v == 50 for v in result)

    def test_linear_mapping(self):
        result = normalize([0, 50, 100], 0, 10)
        assert result[0] == pytest.approx(0)
        assert result[1] == pytest.approx(5)
        assert result[2] == pytest.approx(10)

    def test_with_offset(self):
        result = normalize([0, 100], 50, 150)
        assert result[0] == pytest.approx(50)
        assert result[1] == pytest.approx(150)

    def test_negative_values(self):
        result = normalize([-10, 0, 10], 0, 100)
        assert result[0] == pytest.approx(0)
        assert result[1] == pytest.approx(50)
        assert result[2] == pytest.approx(100)


# ──────────────────────────────────────────────
# PerfOverlay
# ──────────────────────────────────────────────


@pytest.fixture
def perf_container():
    return Container("perfstrip", 0, 900, 1920, 100)


@pytest.fixture
def mock_batch():
    return MagicMock()


class TestPerfOverlayEmpty:
    def test_no_data(self, perf_container, mock_batch):
        overlay = PerfOverlay(perf_container, mock_batch, {}, 60.0)
        assert overlay._cursor is None

    def test_empty_series(self, perf_container, mock_batch):
        overlay = PerfOverlay(perf_container, mock_batch, {"track": []}, 60.0)
        assert overlay._cursor is None


class TestPerfOverlayTrack:
    def test_creates_shapes_for_track(self, perf_container, mock_batch):
        series = {
            "track": [
                (1.0, {"cursor_in_target": "1", "center_deviation": "0.0"}),
                (2.0, {"cursor_in_target": "0", "center_deviation": "15.0"}),
                (3.0, {"cursor_in_target": "1", "center_deviation": "5.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        # Should have shapes: bg + 2 line segments + cursor
        assert overlay._cursor is not None
        assert len(overlay._shapes) > 0
        assert len(overlay._labels) == 1

    def test_single_point_no_crash(self, perf_container, mock_batch):
        series = {
            "track": [
                (1.0, {"center_deviation": "10.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        assert overlay._cursor is not None


class TestPerfOverlayResman:
    def test_creates_two_sparklines(self, perf_container, mock_batch):
        series = {
            "resman": [
                (1.0, {"a_deviation": "0", "b_deviation": "100"}),
                (2.0, {"a_deviation": "50", "b_deviation": "200"}),
                (3.0, {"a_deviation": "100", "b_deviation": "50"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        assert overlay._cursor is not None
        # Should have bg + lines for A + lines for B + cursor
        # At least: bg(1) + 2 A-lines + 2 B-lines + cursor(1) = 6
        assert len(overlay._shapes) >= 5


class TestPerfOverlaySysmon:
    def test_creates_event_markers(self, perf_container, mock_batch):
        series = {
            "sysmon": [
                (5.0, {"name": "F1", "signal_detection": "HIT", "response_time": "1200"}),
                (10.0, {"name": "F2", "signal_detection": "MISS", "response_time": "5000"}),
                (15.0, {"name": "F3", "signal_detection": "FA", "response_time": "800"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 20.0)
        assert overlay._cursor is not None
        # Should have bg + 3 circle markers + cursor
        circles = [s for s in overlay._shapes if hasattr(s, "_radius")]
        assert len(circles) == 3

    def test_cr_events_not_drawn(self, perf_container, mock_batch):
        series = {
            "sysmon": [
                (5.0, {"signal_detection": "CR"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 20.0)
        circles = [s for s in overlay._shapes if hasattr(s, "_radius")]
        assert len(circles) == 0


class TestPerfOverlayComms:
    def test_creates_event_markers(self, perf_container, mock_batch):
        series = {
            "communications": [
                (10.0, {"sdt_value": "HIT", "response_time": "3000"}),
                (20.0, {"sdt_value": "MISS", "response_time": "nan"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 30.0)
        circles = [s for s in overlay._shapes if hasattr(s, "_radius")]
        assert len(circles) == 2


class TestPerfOverlayMultipleTasks:
    def test_multiple_tasks(self, perf_container, mock_batch):
        series = {
            "track": [
                (1.0, {"center_deviation": "0.0"}),
                (2.0, {"center_deviation": "15.0"}),
            ],
            "sysmon": [
                (5.0, {"signal_detection": "HIT"}),
            ],
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        assert len(overlay._labels) == 2
        assert overlay._cursor is not None


class TestPerfOverlayCursor:
    def test_update_cursor_at_start(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        overlay.update_cursor(0.0)
        assert overlay._cursor.x == pytest.approx(overlay._x_min)

    def test_update_cursor_at_end(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        overlay.update_cursor(10.0)
        assert overlay._cursor.x == pytest.approx(overlay._x_max)

    def test_update_cursor_mid(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        overlay.update_cursor(5.0)
        expected_x = overlay._x_min + 0.5 * overlay._sparkline_width
        assert overlay._cursor.x == pytest.approx(expected_x)

    def test_update_cursor_clamps_negative(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        overlay.update_cursor(-5.0)
        assert overlay._cursor.x >= overlay._x_min

    def test_update_cursor_clamps_beyond_duration(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        overlay.update_cursor(20.0)
        assert overlay._cursor.x <= overlay._x_max

    def test_update_cursor_noop_when_no_data(self, perf_container, mock_batch):
        overlay = PerfOverlay(perf_container, mock_batch, {}, 10.0)
        overlay.update_cursor(5.0)  # Should not raise


class TestPerfOverlayDestroy:
    def test_destroy_clears_shapes(self, perf_container, mock_batch):
        series = {
            "track": [
                (0.0, {"center_deviation": "0.0"}),
                (10.0, {"center_deviation": "50.0"}),
            ]
        }
        overlay = PerfOverlay(perf_container, mock_batch, series, 10.0)
        assert len(overlay._shapes) > 0
        overlay.destroy()
        assert len(overlay._shapes) == 0
        assert len(overlay._labels) == 0
        assert overlay._cursor is None
