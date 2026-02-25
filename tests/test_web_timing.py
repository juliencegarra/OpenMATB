"""Timing of the browser (Pyodide) version, without a browser.

In the browser, pyglet's asyncio loop wakes up when the browser lets it (timers, animation frames)
and core.clock.Clock advances with schedule_interval(1/120) instead of schedule() (see core/clock.py).
These tests load the *real* pyglet clock (pure Python), drive it with simulated browser wake-ups
(steady, jittered, stalled, throttled) and check the timing seen by the scenario:

- the scenario time never drifts from the real (performance.now) time,
- the update rate is capped by WEB_UPDATE_INTERVAL (no busy loop),
- scenario events are never early, and late by at most one wake-up gap,
- simultaneous events are executed one per update, in line order.

The timing measured in a real browser is checked by tests/web/test_browser.py.
"""

from __future__ import annotations

import importlib
import importlib.util
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.event import Event

ROOT: Path = Path(__file__).resolve().parent.parent


# ── Real pyglet clock + core.clock in browser mode ──────────────────────────


def _import_real_pyglet_clock():
    """Import the real pyglet.clock while conftest mocks pyglet, without leaking it to other tests."""
    saved = {k: v for k, v in sys.modules.items() if k == "pyglet" or k.startswith("pyglet.")}
    for name in ("pyglet", "pyglet.event", "pyglet.clock"):
        sys.modules.pop(name, None)
    try:
        return importlib.import_module("pyglet.clock")
    finally:
        for name in [k for k in sys.modules if k == "pyglet" or k.startswith("pyglet.")]:
            del sys.modules[name]
        sys.modules.update(saved)


REAL_CLOCK = _import_real_pyglet_clock()


def _load_core_clock(is_web: bool):
    """Load a private copy of core/clock.py on top of the real pyglet clock."""
    spec = importlib.util.spec_from_file_location(
        f"_core_clock_{'web' if is_web else 'desktop'}", ROOT / "core/clock.py"
    )
    module = importlib.util.module_from_spec(spec)
    fake_pyglet = SimpleNamespace(clock=REAL_CLOCK, app=SimpleNamespace(platform_event_loop=MagicMock()))
    mocked_pyglet = sys.modules["pyglet"]
    with (
        patch("core.platform.IS_WEB", is_web),
        patch.object(mocked_pyglet, "clock", REAL_CLOCK),
        patch.object(mocked_pyglet, "app", fake_pyglet.app),
    ):
        spec.loader.exec_module(module)
    module.pyglet = fake_pyglet  # Used at run time (Clock.__init__)
    return module


class BrowserLoop:
    """Stand-in for pyglet's AsyncEventLoop: a default clock on performance.now(), ticked at each wake-up."""

    def __init__(self) -> None:
        self.now: float = 1000.0  # performance.now() / 1000 is never 0 when the scenario starts
        self.clock = REAL_CLOCK.Clock(time_function=lambda: self.now)
        self.clock.update_time()

    def wake_at(self, t: float) -> None:
        # Same as AsyncEventLoop.idle()
        self.now = t
        self.clock.call_scheduled_functions(self.clock.update_time())

    def run(self, gaps) -> None:
        for gap in gaps:
            self.wake_at(self.now + gap)


@pytest.fixture
def browser():
    previous = REAL_CLOCK.get_default()
    loop = BrowserLoop()
    REAL_CLOCK.set_default(loop.clock)
    yield loop
    REAL_CLOCK.set_default(previous)


@pytest.fixture
def web_clock_module():
    return _load_core_clock(is_web=True)


@pytest.fixture
def main_clock(browser, web_clock_module):
    """The scenario clock (core.clock.Clock("main")) created in browser mode."""
    return web_clock_module.Clock("main")


def _record_updates(clock) -> list[float]:
    """Record the dt received by a function scheduled on the scenario clock (like Scheduler.update)."""
    received: list[float] = []
    clock.schedule(received.append)
    return received


def _jittered_gaps(n: int, low: float, high: float, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(low, high) for _ in range(n)]


# ── Browser-specific scheduling ─────────────────────────────────────────────


class TestWebScheduling:
    def test_web_uses_a_fixed_interval_not_every_tick(self, browser, web_clock_module):
        """schedule() (every loop iteration) crashes Pyodide: the clock must use schedule_interval."""
        clock = web_clock_module.Clock("main")
        items = browser.clock._schedule_interval_items
        assert [i.func for i in items] == [clock.advance]
        assert items[0].interval == pytest.approx(web_clock_module.WEB_UPDATE_INTERVAL)
        assert browser.clock._schedule_items == []

    def test_web_interval_is_120_hz(self, web_clock_module):
        assert pytest.approx(1 / 120) == web_clock_module.WEB_UPDATE_INTERVAL

    def test_web_wakes_the_sleeping_browser_loop(self, browser, web_clock_module):
        """The browser loop sleeps while nothing is scheduled: creating the clock must notify it."""
        web_clock_module.pyglet.app.platform_event_loop.notify.reset_mock()
        web_clock_module.Clock("main")
        web_clock_module.pyglet.app.platform_event_loop.notify.assert_called_once()

    def test_desktop_updates_at_every_tick(self, browser):
        desktop = _load_core_clock(is_web=False)
        clock = desktop.Clock("main")
        assert [i.func for i in browser.clock._schedule_items] == [clock.advance]
        desktop.pyglet.app.platform_event_loop.notify.assert_not_called()

    def test_update_rate_is_capped_when_the_browser_wakes_up_often(self, browser, main_clock):
        """Frequent wake-ups (2 ms) must not update the scenario more than 120 times per second."""
        updates = _record_updates(main_clock)
        browser.run([0.002] * 5000)  # 10 s
        assert 1195 <= len(updates) <= 1201
        # Updates keep the 120 Hz phase: each gap is the interval rounded to a wake-up (8 or 10 ms)
        assert min(updates[1:]) >= 1 / 120 - 0.002 - 1e-9
        assert max(updates[1:]) <= 1 / 120 + 0.002 + 1e-9

    def test_every_wake_up_updates_when_the_browser_is_slower_than_120_hz(self, browser, main_clock):
        """Measured in Chrome: wake-ups every ~9-17 ms. Each one must update the scenario."""
        updates = _record_updates(main_clock)
        gaps = _jittered_gaps(2000, 0.009, 0.017)
        browser.run(gaps)
        assert len(updates) == len(gaps)
        assert updates[1:] == pytest.approx(gaps[1:], abs=1e-9)


# ── Scenario time vs real time ──────────────────────────────────────────────


class TestNoDrift:
    @pytest.mark.parametrize(
        "gaps",
        [
            pytest.param([1 / 120] * 12_000, id="steady-120Hz"),
            pytest.param([1 / 60] * 6_000, id="steady-60Hz-animation-frames"),
            pytest.param(_jittered_gaps(10_000, 0.004, 0.017, seed=1), id="jittered-4-17ms"),
            pytest.param(([0.0095] * 50 + [0.25]) * 200, id="stalls-250ms"),
            pytest.param([1.0] * 100, id="hidden-tab-throttled-1Hz"),
        ],
    )
    def test_scenario_time_follows_real_time(self, browser, main_clock, gaps):
        updates = _record_updates(main_clock)
        first_update_at: list[float] = []
        main_clock.schedule(lambda dt: first_update_at or first_update_at.append(main_clock.get_time()))
        start_real, start_scenario = browser.now, main_clock.get_time()
        browser.run(gaps)
        real_elapsed = browser.now - start_real
        assert main_clock.get_time() - start_scenario == pytest.approx(real_elapsed, abs=1e-6)
        # The first update has dt=0 (see test_first_update_has_no_dt): constant offset, no drift
        offset = first_update_at[0] - start_scenario
        assert offset <= max(gaps[0], 1 / 120) + 0.017
        assert sum(updates) == pytest.approx(real_elapsed - offset, abs=1e-6)

    def test_one_hour_session_has_no_cumulative_error(self, browser, main_clock):
        """Float accumulation over a long session (1 h of 10 ms updates) stays far below 1 ms."""
        updates = _record_updates(main_clock)
        start_real = browser.now
        gaps = _jittered_gaps(360_000, 0.009, 0.011, seed=2)
        browser.run(gaps)
        real_elapsed = browser.now - start_real
        assert real_elapsed == pytest.approx(3600, abs=5)
        assert abs(main_clock.get_time() - real_elapsed) < 1e-3
        assert abs(sum(updates) - (real_elapsed - gaps[0])) < 1e-3

    def test_first_update_has_no_dt(self, browser, main_clock):
        """pyglet's first tick returns dt=0: the scenario time starts one wake-up (<= 17 ms) after the clock."""
        updates = _record_updates(main_clock)
        browser.run([0.0125, 0.01, 0.01])
        assert updates[0] == 0
        assert sum(updates) == pytest.approx(main_clock.get_time() - 0.0125)

    def test_a_stall_is_one_long_update_not_a_burst(self, browser, main_clock):
        """After a 250 ms stall (GC, sound decoding...) the scenario gets one dt of 250 ms, not 30 updates."""
        updates = _record_updates(main_clock)
        browser.run([0.01] * 10)
        count = len(updates)
        browser.run([0.25])
        assert len(updates) == count + 1
        assert updates[-1] == pytest.approx(0.25)

    @pytest.mark.parametrize("speed", [2, 5, 10])
    def test_accelerated_speed(self, browser, main_clock, speed):
        updates = _record_updates(main_clock)
        main_clock._speed = speed
        browser.run([0.01] * 100)
        assert main_clock.get_time() == pytest.approx(speed * 1.0, abs=1e-6)
        assert len(updates) == speed * 100

    def test_fast_forward_ignores_browser_wake_ups(self, browser, main_clock):
        """During a replay fast-forward, the browser ticks must not advance the time twice."""
        updates = _record_updates(main_clock)
        main_clock.isFastForward = True
        browser.run([0.01] * 10)
        assert main_clock.get_time() == 0
        assert updates == []

    def test_fast_forward_steps_are_at_most_100_ms(self, main_clock):
        updates = _record_updates(main_clock)
        main_clock.fastforward_time(1.05)
        assert main_clock.get_time() == pytest.approx(1.05)
        assert max(updates) <= 0.1 + 1e-9
        assert main_clock.isFastForward is False


# ── Scenario events timing (Scheduler driven by the browser clock) ─────────


def _event(line: int, time_sec: float, plugin: str = "sysmon", command: str = "start") -> Event:
    return Event(line, time_sec, plugin, command)


@pytest.fixture
def scheduler(mock_logger, main_clock):
    """A Scheduler on the browser clock, recording when each event is executed."""
    from core.scheduler import Scheduler

    s = object.__new__(Scheduler)
    s.clock = main_clock
    s.events = []
    s._event_cursor = 0  # Events are sorted by (time, line) in set_scenario()
    s.events_queue = []
    s.plugins = {}
    s.paused_plugins = []
    s.pause_scenario_time = False
    s.scenario_time = 0
    s._dialog_paused = False
    s.joystick = None
    s.executed = []  # (event, scenario time when executed, update index)
    s.update_count = 0

    def execute_one_event(event: Event) -> None:
        event.done = 1
        s.executed.append((event, s.scenario_time, s.update_count))

    def count_update(dt: float) -> None:
        s.update_count += 1

    s.execute_one_event = execute_one_event
    s.check_if_must_exit = lambda: None
    main_clock.schedule(count_update)
    main_clock.schedule(s.update)

    window = SimpleNamespace(MainWindow=SimpleNamespace(modal_dialog=None, alive=True))
    with patch("core.scheduler.Window", window), patch("core.scheduler.get_errors") as errors:
        errors.return_value.is_empty.return_value = True
        yield s


class TestEventTiming:
    @pytest.mark.parametrize(
        "gaps,max_late",
        [
            pytest.param([1 / 120] * 1200, 1 / 120, id="steady-120Hz"),
            pytest.param(_jittered_gaps(1000, 0.004, 0.017, seed=3), 0.017, id="jittered-4-17ms"),
            pytest.param([0.1] * 100, 0.1, id="slow-10Hz"),
        ],
    )
    def test_events_are_never_early_and_late_by_at_most_one_gap(self, browser, scheduler, gaps, max_late):
        scheduler.events = [_event(i, t) for i, t in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9])]
        browser.run(gaps)
        assert len(scheduler.executed) == 9
        for event, scenario_time, _ in scheduler.executed:
            assert scenario_time >= event.time_sec
            assert scenario_time - event.time_sec <= max_late + 1e-9

    def test_simultaneous_events_run_one_per_update_in_line_order(self, browser, scheduler):
        """Events of the same second are executed on consecutive updates (~8 ms apart at 120 Hz)."""
        # Written in any order in the scenario: set_scenario() sorts them by (time, line)
        scheduler.events = sorted((_event(line, 2) for line in (5, 3, 9, 1, 7)), key=lambda e: e.line)
        browser.run([1 / 120] * 400)
        lines = [e.line for e, _, _ in scheduler.executed]
        assert lines == [1, 3, 5, 7, 9]
        update_indexes = [u for _, _, u in scheduler.executed]
        assert update_indexes == list(range(update_indexes[0], update_indexes[0] + 5))
        last_late = scheduler.executed[-1][1] - 2
        assert last_late == pytest.approx(5 / 120, abs=1 / 120 + 1e-9)

    def test_events_due_during_a_stall_are_all_executed_after_it(self, browser, scheduler):
        scheduler.events = [_event(1, 1.0), _event(2, 1.1), _event(3, 1.2)]
        browser.run([0.01] * 95)  # 0.95 s
        assert scheduler.executed == []
        browser.run([0.3])  # Stall until 1.25 s: the three events are due
        browser.run([0.01] * 5)
        assert [e.line for e, _, _ in scheduler.executed] == [1, 2, 3]
        # Scenario time = real time - first gap (10 ms)
        assert [u for _, _, u in scheduler.executed] == [96, 97, 98]
        assert all(t >= 1.24 - 1e-9 for _, t, _ in scheduler.executed)

    def test_modal_dialog_freezes_scenario_time(self, browser, scheduler):
        """The pause prompt shown when the tab is hidden stops the scenario time (no jump on return)."""
        browser.run([0.01] * 100)
        frozen = scheduler.scenario_time
        with patch("core.scheduler.Window") as window:
            window.MainWindow.modal_dialog = object()
            browser.run([1.0] * 30)  # Hidden tab: throttled to 1 Hz for 30 s
        assert scheduler.scenario_time == frozen
        browser.run([0.01] * 10)
        assert scheduler.scenario_time == pytest.approx(frozen + 0.1, abs=1e-6)


class TestFreezeLog:
    """Pauses of the page (e.g. Firefox garbage collection) are written to the session file."""

    def test_a_stall_is_logged_with_its_duration(self, browser, scheduler, mock_logger):
        with patch("core.scheduler.IS_WEB", True):
            browser.run([0.01] * 50)
            browser.run([0.25])
            browser.run([0.01] * 10)
        assert [c.args[0] for c in mock_logger.log_manual_entry.call_args_list if c.kwargs.get("key") == "freeze"] == [
            "250"
        ]

    def test_logged_at_the_scenario_time_when_the_page_stopped(self, browser, scheduler, mock_logger):
        logged_at: list[float] = []
        mock_logger.log_manual_entry.side_effect = lambda value, key: logged_at.append(scheduler.scenario_time)
        with patch("core.scheduler.IS_WEB", True):
            browser.run([0.01] * 50)
            before = scheduler.scenario_time
            browser.run([0.25])
        assert logged_at == [before]

    def test_normal_updates_are_not_logged(self, browser, scheduler, mock_logger):
        with patch("core.scheduler.IS_WEB", True):
            browser.run(_jittered_gaps(3000, 0.004, 0.017, seed=5) + [0.1])  # 100 ms: at the threshold
        mock_logger.log_manual_entry.assert_not_called()

    def test_not_logged_while_the_pause_dialog_is_shown(self, browser, scheduler, mock_logger):
        """A hidden tab is throttled to ~1 Hz, but the scenario is paused: not a freeze."""
        with patch("core.scheduler.IS_WEB", True), patch("core.scheduler.Window") as window:
            window.MainWindow.modal_dialog = object()
            browser.run([1.0] * 5)
        mock_logger.log_manual_entry.assert_not_called()

    def test_not_logged_on_desktop(self, browser, scheduler, mock_logger):
        browser.run([0.01] * 10 + [0.5])
        mock_logger.log_manual_entry.assert_not_called()


# ── Plugin pace (taskupdatetime) ────────────────────────────────────────────


class TestPluginPace:
    """Plugins count taskupdatetime per step (response times, failure timers, tracking drift...).

    Regression: the next step was scheduled from the update time, so the lateness of each update
    accumulated: in Chrome the tracking task ran at 70 % of its speed (28.6 ms steps instead of 20 ms).
    """

    @pytest.mark.parametrize("taskupdatetime", [20, 80, 200, 2000])
    @pytest.mark.parametrize(
        "gaps",
        [
            pytest.param(_jittered_gaps(6000, 0.004, 0.017, seed=4), id="browser-jittered"),
            pytest.param([0.0095] * 6300, id="browser-steady-9.5ms"),
            pytest.param([0.031] * 2000, id="webkit-31ms"),
        ],
    )
    def test_steps_follow_real_time(self, browser, scheduler, taskupdatetime, gaps):
        from tests.test_abstractplugin import _make_plugin

        plugin = _make_plugin(paused=False, alive=True, visible=False)
        plugin.parameters["taskupdatetime"] = taskupdatetime
        steps: list[float] = []
        compute = plugin.compute_next_plugin_state

        def counted() -> bool:
            done = compute()
            if done:
                steps.append(plugin.scenario_time)
            return done

        plugin.compute_next_plugin_state = counted
        scheduler.plugins = {"p": plugin}
        browser.run(gaps)

        period = taskupdatetime / 1000
        # Deadlines are 0, period, 2 * period... (the plugin starts at scenario time 0)
        assert abs(len(steps) - scheduler.scenario_time / period) <= 1
        lateness = [t - i * period for i, t in enumerate(steps)]
        assert min(lateness) >= -1e-9  # Never early
        assert max(lateness) <= max(gaps) + 0.020  # About one update, including after catching up steps
