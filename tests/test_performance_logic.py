"""Tests for plugins/performance.py — compute_next_plugin_state logic."""

from unittest.mock import MagicMock

from core.constants import COLORS as C
from plugins.performance import Performance


def _make_performance(**overrides):
    """Create a Performance instance without triggering __init__ imports."""
    p = object.__new__(Performance)
    p.alias = "performance"
    p.scenario_time = 1.0
    p.next_refresh_time = 0
    p.paused = False
    p.verbose = False
    p.performance_levels = {}
    p.current_level = 100
    p.displayed_level = 100
    p.displayed_color = C["GREEN"]
    p.under_critical = None
    p.automode_string = ""
    p.parameters = dict(
        taskupdatetime=50,
        levelmin=0,
        levelmax=100,
        criticallevel=20,
        shadowundercritical=True,
        defaultcolor=C["GREEN"],
        criticalcolor=C["RED"],
        displayautomationstate=False,
    )
    p.plugins = {}
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _mock_plugin(performance, taskupdatetime=50):
    """Create a mock plugin with performance dict and parameters."""
    m = MagicMock()
    m.performance = performance
    m.parameters = {"taskupdatetime": taskupdatetime}
    return m


# ── Sysmon performance ──────────────────────────


class TestSysmonPerformance:
    def test_all_hits(self):
        """4 HITs → level = 1.0"""
        sysmon = _mock_plugin({"signal_detection": ["HIT", "HIT", "HIT", "HIT"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.performance_levels["sysmon"] == 1.0

    def test_half_hits_half_miss(self):
        """2 HIT + 2 MISS → 0.5"""
        sysmon = _mock_plugin({"signal_detection": ["HIT", "MISS", "HIT", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.performance_levels["sysmon"] == 0.5

    def test_all_miss(self):
        """4 MISS → 0.0"""
        sysmon = _mock_plugin({"signal_detection": ["MISS", "MISS", "MISS", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.performance_levels["sysmon"] == 0.0

    def test_fa_counts_as_non_hit(self):
        """FA counts as non-HIT: 2 HIT + 1 FA + 1 MISS → 0.5"""
        sysmon = _mock_plugin({"signal_detection": ["HIT", "FA", "HIT", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.performance_levels["sysmon"] == 0.5

    def test_fewer_than_4_events_ignored(self):
        """Less than 4 SDT events → plugin not recorded."""
        sysmon = _mock_plugin({"signal_detection": ["HIT", "MISS", "HIT"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert "sysmon" not in p.performance_levels

    def test_non_sdt_events_filtered(self):
        """Non-SDT labels are filtered out before counting."""
        sysmon = _mock_plugin({"signal_detection": ["HIT", "OTHER", "HIT", "MISS", "HIT"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        # After filtering: ['HIT', 'HIT', 'MISS', 'HIT'] → 3/4 = 0.75
        assert p.performance_levels["sysmon"] == 0.75


# ── Track performance ────────────────────────────


class TestTrackPerformance:
    def test_all_in_target(self):
        """100% in target → 1.0"""
        frames_n = int(5000 / 50)  # = 100
        track = _mock_plugin({"cursor_in_target": [1] * frames_n})
        p = _make_performance(plugins={"track": track})
        p.compute_next_plugin_state()
        assert p.performance_levels["track"] == 1.0

    def test_half_in_target(self):
        """50% in target → 0.5"""
        frames_n = int(5000 / 50)
        data = [1] * (frames_n // 2) + [0] * (frames_n // 2)
        track = _mock_plugin({"cursor_in_target": data})
        p = _make_performance(plugins={"track": track})
        p.compute_next_plugin_state()
        assert p.performance_levels["track"] == 0.5

    def test_not_enough_frames_ignored(self):
        """Fewer frames than required → plugin not recorded."""
        frames_n = int(5000 / 50)
        track = _mock_plugin({"cursor_in_target": [1] * (frames_n - 1)})
        p = _make_performance(plugins={"track": track})
        p.compute_next_plugin_state()
        assert "track" not in p.performance_levels


# ── Resman performance ───────────────────────────


class TestResmanPerformance:
    def test_full_tolerance(self):
        """100% in tolerance for both A and B → 1.0"""
        frames_n = int(5000 / 50)
        resman = _mock_plugin(
            {
                "a_in_tolerance": [1] * frames_n,
                "b_in_tolerance": [1] * frames_n,
            }
        )
        p = _make_performance(plugins={"resman": resman})
        p.compute_next_plugin_state()
        assert p.performance_levels["resman"] == 1.0

    def test_half_tolerance(self):
        """50% A, 50% B → 0.5"""
        frames_n = int(5000 / 50)
        a_data = [1] * (frames_n // 2) + [0] * (frames_n // 2)
        b_data = [1] * (frames_n // 2) + [0] * (frames_n // 2)
        resman = _mock_plugin(
            {
                "a_in_tolerance": a_data,
                "b_in_tolerance": b_data,
            }
        )
        p = _make_performance(plugins={"resman": resman})
        p.compute_next_plugin_state()
        assert p.performance_levels["resman"] == 0.5

    def test_not_enough_data_ignored(self):
        """Not enough frames for either tank → ignored."""
        frames_n = int(5000 / 50)
        resman = _mock_plugin(
            {
                "a_in_tolerance": [1] * (frames_n - 1),
                "b_in_tolerance": [1] * frames_n,
            }
        )
        p = _make_performance(plugins={"resman": resman})
        p.compute_next_plugin_state()
        assert "resman" not in p.performance_levels


# ── Communications performance ───────────────────


class TestCommsPerformance:
    def test_all_correct(self):
        """4 correct radio + 0 deviation → 1.0"""
        comms = _mock_plugin(
            {
                "correct_radio": [True, True, True, True],
                "response_deviation": [0.0, 0.0, 0.0, 0.0],
            }
        )
        p = _make_performance(plugins={"communications": comms})
        p.compute_next_plugin_state()
        assert p.performance_levels["communications"] == 1.0

    def test_mixed_results(self):
        """2 correct + 2 wrong → 0.5"""
        comms = _mock_plugin(
            {
                "correct_radio": [True, False, True, False],
                "response_deviation": [0.0, 0.0, 0.0, 0.0],
            }
        )
        p = _make_performance(plugins={"communications": comms})
        p.compute_next_plugin_state()
        assert p.performance_levels["communications"] == 0.5

    def test_correct_radio_but_deviation(self):
        """Correct radio but nonzero deviation → not 'good'."""
        comms = _mock_plugin(
            {
                "correct_radio": [True, True, True, True],
                "response_deviation": [0.0, 0.5, 0.0, 0.0],
            }
        )
        p = _make_performance(plugins={"communications": comms})
        p.compute_next_plugin_state()
        assert p.performance_levels["communications"] == 0.75

    def test_fewer_than_4_events_ignored(self):
        """Less than 4 events → ignored."""
        comms = _mock_plugin(
            {
                "correct_radio": [True, True],
                "response_deviation": [0.0, 0.0],
            }
        )
        p = _make_performance(plugins={"communications": comms})
        p.compute_next_plugin_state()
        assert "communications" not in p.performance_levels


# ── Global level ─────────────────────────────────


class TestGlobalLevel:
    def test_no_perf_recorded(self):
        """No performance data → current_level = levelmax (100)."""
        p = _make_performance(plugins={})
        p.compute_next_plugin_state()
        assert p.current_level == 100

    def test_single_plugin_determines_level(self):
        """Single plugin at 0.5 → global level = 50."""
        frames_n = int(5000 / 50)
        track = _mock_plugin({"cursor_in_target": [1] * (frames_n // 2) + [0] * (frames_n // 2)})
        p = _make_performance(plugins={"track": track})
        p.compute_next_plugin_state()
        assert p.current_level == 50.0

    def test_min_of_multiple_plugins(self):
        """Global level = min of all plugin levels × 100."""
        frames_n = int(5000 / 50)
        # track at 100%
        track = _mock_plugin({"cursor_in_target": [1] * frames_n})
        # sysmon at 50%
        sysmon = _mock_plugin({"signal_detection": ["HIT", "MISS", "HIT", "MISS"]})
        p = _make_performance(plugins={"track": track, "sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.current_level == 50.0


# ── Critical color ───────────────────────────────


class TestCriticalColor:
    def test_above_critical(self):
        """Level above critical → defaultcolor, under_critical=False."""
        p = _make_performance(plugins={})
        p.compute_next_plugin_state()
        assert p.current_level == 100
        assert p.displayed_color == C["GREEN"]
        assert p.under_critical is False

    def test_below_critical(self):
        """Level below critical → criticalcolor, under_critical=True."""
        sysmon = _mock_plugin({"signal_detection": ["MISS", "MISS", "MISS", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.current_level == 0.0
        assert p.displayed_color == C["RED"]
        assert p.under_critical is True


# ── Shadow under critical ────────────────────────


class TestShadowUnderCritical:
    def test_shadow_true_below_critical(self):
        """shadowundercritical=True + below → displayed_level = criticallevel."""
        sysmon = _mock_plugin({"signal_detection": ["MISS", "MISS", "MISS", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.compute_next_plugin_state()
        assert p.under_critical is True
        assert p.displayed_level == 20  # criticallevel

    def test_shadow_false_below_critical(self):
        """shadowundercritical=False + below → displayed_level = current_level."""
        sysmon = _mock_plugin({"signal_detection": ["MISS", "MISS", "MISS", "MISS"]})
        p = _make_performance(plugins={"sysmon": sysmon})
        p.parameters["shadowundercritical"] = False
        p.compute_next_plugin_state()
        assert p.under_critical is True
        assert p.displayed_level == 0.0

    def test_above_critical_shows_current(self):
        """Above critical → displayed_level = current_level regardless of shadow."""
        p = _make_performance(plugins={})
        p.compute_next_plugin_state()
        assert p.under_critical is False
        assert p.displayed_level == 100
