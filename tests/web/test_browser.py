"""OpenMATB in a real browser: timing, stability and web specific behaviour.

Run with:  OPENMATB_BROWSER_TESTS=1 python -m pytest tests/web -v
(see tests/web/conftest.py for the requirements and options)

Timing thresholds (ms) are for a desktop machine; OPENMATB_TIMING_TOLERANCE multiplies them.
The scenario clock updates at most every WEB_UPDATE_INTERVAL = 8.3 ms (core/clock.py); in Chrome,
wake-ups actually come every ~9-17 ms.
"""

from __future__ import annotations

import csv
import io
import os
import statistics
import sys

import pytest

from tests.web.conftest import OpenMATBPage

TIMING_SCENARIO_DURATION: int = 12
ENGINE: str = os.environ.get("OPENMATB_BROWSER", "chromium")
SIMULTANEOUS_AT: int = 5
SIMULTANEOUS_COUNT: int = 10


def _timing_scenario() -> str:
    lines = ["0:00:00;sysmon;start", "0:00:00;track;start"]
    lines += [f"0:00:{s:02d};sysmon;alerttimeout;{10000 + s}" for s in range(1, 10)]
    lines += [f"0:00:{SIMULTANEOUS_AT:02d};track;cursorcolor;#0099{i:02d}" for i in range(SIMULTANEOUS_COUNT)]
    lines += [f"0:00:{TIMING_SCENARIO_DURATION:02d};sysmon;stop", f"0:00:{TIMING_SCENARIO_DURATION:02d};track;stop"]
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def timing_run(page_factory):
    """One full 12 s scenario, recorded by the probe; the tests below check different aspects of it."""
    app = page_factory()
    app.start(_timing_scenario())
    middle = app.wait_until(lambda s: s["scenario_time"] >= TIMING_SCENARIO_DURATION / 2, timeout=30)
    app.page.wait_for_selector("#end:not([hidden])", timeout=(TIMING_SCENARIO_DURATION + 30) * 1000)
    final = app.state()
    return app, middle, final


@pytest.fixture(scope="module")
def fine_timers() -> None:
    """Skip the tests bound to the timer cadence in Playwright's WebKit build for Windows.

    It rounds setTimeout to the Windows timer resolution (15.6 ms): the loop wakes every ~31 ms, where
    Safari, Chrome and Firefox wake every ~8-10 ms. Plugin pace and the rest are still tested.
    """
    if ENGINE == "webkit" and sys.platform == "win32":
        pytest.skip("Playwright WebKit on Windows rounds its timers to 15.6 ms (not representative of Safari)")


def _intervals_ms(updates: list) -> list[float]:
    return [b[0] - a[0] for a, b in zip(updates, updates[1:])]


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]


# ── Stability ───────────────────────────────────────────────────────────────


class TestEventLoop:
    def test_loop_is_running_during_the_scenario(self, timing_run):
        """Regressions: schedule() crash, gamepad jsnull, 'Can't schedule in the past', detached buffers..."""
        _, middle, _ = timing_run
        assert middle["running"]

    def test_scenario_reaches_its_end(self, timing_run):
        _, _, final = timing_run
        assert final["scenario_time"] >= TIMING_SCENARIO_DURATION
        assert not final["running"]  # Stopped by the end of the scenario, not by an error

    def test_no_python_or_page_error(self, timing_run):
        app, _, _ = timing_run
        assert app.errors == []
        assert not [line for line in app.console if "Traceback" in line or "table index is out of bounds" in line]


# ── Timing ──────────────────────────────────────────────────────────────────


class TestUpdateTiming:
    def test_update_rate(self, timing_run, tolerance, fine_timers):
        _, _, final = timing_run
        intervals = _intervals_ms(final["updates"])
        median, p95 = statistics.median(intervals), _percentile(intervals, 0.95)
        print(f"\nupdates: n={len(intervals)} median={median:.2f} p95={p95:.2f} max={max(intervals):.2f} ms")
        assert median >= 1000 / 120 - 1  # Capped at 120 Hz: no busy loop
        assert median <= 12.5 * tolerance
        assert p95 <= 20 * tolerance

    def test_no_long_freeze(self, timing_run, tolerance):
        _, _, final = timing_run
        intervals = _intervals_ms(final["updates"])
        worst = max(range(len(intervals)), key=intervals.__getitem__)
        print(f"\nlongest gap: {intervals[worst]:.1f} ms at scenario time {final['updates'][worst][2]:.3f} s")
        assert max(_intervals_ms(final["updates"])) <= 100 * tolerance

    def test_dt_is_the_real_elapsed_time(self, timing_run):
        """The dt given to the scenario matches the browser clock (performance.now)."""
        _, _, final = timing_run
        updates = final["updates"]
        errors = [abs(b[1] * 1000 - (b[0] - a[0])) for a, b in zip(updates, updates[1:])]
        assert statistics.median(errors) <= 1
        assert _percentile(errors, 0.99) <= 4

    def test_update_processing_time(self, timing_run, tolerance):
        """Time spent in Scheduler.update: it delays the next update (starting plugins is the costliest)."""
        _, _, final = timing_run
        durations = [u[3] for u in final["updates"]]
        print(f"\nupdate processing: median={statistics.median(durations):.2f} max={max(durations):.2f} ms")
        assert statistics.median(durations) <= 2 * tolerance
        assert max(durations) <= 150 * tolerance

    def test_scenario_time_does_not_drift(self, timing_run):
        _, _, final = timing_run
        updates = final["updates"]
        wall = (updates[-1][0] - updates[0][0]) / 1000
        scenario = updates[-1][2] - updates[0][2]
        print(f"\ndrift over {wall:.1f} s: {(scenario - wall) * 1000:+.2f} ms")
        assert abs(scenario - wall) <= 0.005


class TestEventTiming:
    def _single_events(self, final) -> list[dict]:
        return [e for e in final["events"] if e["time_sec"] not in (0, SIMULTANEOUS_AT, TIMING_SCENARIO_DURATION)]

    def test_all_events_are_executed(self, timing_run):
        _, _, final = timing_run
        assert len(final["events"]) == 2 + 9 + SIMULTANEOUS_COUNT + 2

    def test_events_are_never_early(self, timing_run):
        _, _, final = timing_run
        assert all(e["scenario_time"] >= e["time_sec"] for e in final["events"])

    def test_event_lateness(self, timing_run, tolerance, fine_timers):
        """Lateness of an event = scenario time when executed - planned time: at most one update."""
        _, _, final = timing_run
        lateness = [(e["scenario_time"] - e["time_sec"]) * 1000 for e in self._single_events(final)]
        print(f"\nevent lateness: max={max(lateness):.2f} mean={statistics.mean(lateness):.2f} ms")
        assert max(lateness) <= 20 * tolerance

    def test_events_follow_the_wall_clock(self, timing_run, tolerance, fine_timers):
        """Planned time vs browser clock: the spacing of events 1 s apart is kept within one update."""
        _, _, final = timing_run
        events = self._single_events(final)
        first = events[0]
        for event in events[1:]:
            wall = (event["t"] - first["t"]) / 1000
            planned = event["time_sec"] - first["time_sec"]
            assert abs(wall - planned) <= 0.020 * tolerance

    def test_simultaneous_events_one_per_update_in_order(self, timing_run, tolerance, fine_timers):
        _, _, final = timing_run
        batch = [e for e in final["events"] if e["time_sec"] == SIMULTANEOUS_AT and e["line"] >= 11]
        assert [e["line"] for e in batch] == sorted(e["line"] for e in batch)
        updates = [e["update"] for e in batch]
        assert updates == list(range(updates[0], updates[0] + SIMULTANEOUS_COUNT))
        spread_ms = batch[-1]["t"] - batch[0]["t"]
        print(f"\n{SIMULTANEOUS_COUNT} simultaneous events spread over {spread_ms:.1f} ms")
        assert spread_ms <= SIMULTANEOUS_COUNT * 20 * tolerance


class TestPluginPace:
    """Plugins count taskupdatetime per step: their steps must follow real time (tracking ran at 70 %)."""

    @pytest.mark.parametrize("alias,taskupdatetime", [("track", 20), ("sysmon", 200)])
    def test_plugin_steps_follow_real_time(self, timing_run, alias, taskupdatetime):
        _, _, final = timing_run
        steps = [t for a, t in final["steps"] if a == alias]
        period = taskupdatetime / 1000
        pace = (len(steps) - 1) * period / (steps[-1] - steps[0])
        print(f"\n{alias}: {len(steps)} steps, pace {pace:.2%} of real time")
        assert pace == pytest.approx(1, abs=0.01)


# ── Session file ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def session_csv(timing_run):
    app, _, _ = timing_run
    assert len(app.downloads) == 1
    download = app.downloads[0]
    return download.suggested_filename, download.path().read_text(encoding="utf-8")


class TestSessionFile:
    def test_downloaded_at_the_end(self, timing_run, session_csv):
        app, _, _ = timing_run
        name, _ = session_csv
        assert name.endswith(".csv")
        assert app.page.text_content("#end-file") == name

    def test_kept_in_browser_storage(self, timing_run, session_csv):
        app, _, _ = timing_run
        name, content = session_csv
        stored = app.python(
            f"from core.constants import PATHS; next(PATHS['SESSIONS'].rglob({name!r})).read_text(encoding='utf-8')"
        )
        assert stored == content

    def test_scenario_times_are_logged(self, session_csv):
        _, content = session_csv
        rows = list(csv.DictReader(io.StringIO(content)))
        times = [float(r["scenario_time"]) for r in rows]
        assert times == sorted(times)
        assert times[-1] >= TIMING_SCENARIO_DURATION
        events = [r for r in rows if r["type"] == "event"]
        assert len(events) == 2 + 9 + SIMULTANEOUS_COUNT + 2

    def test_browser_is_logged(self, session_csv):
        _, content = session_csv
        rows = {r["type"]: r["value"] for r in csv.DictReader(io.StringIO(content))}
        expected = {"chromium": ("Chrome", "Edge"), "firefox": ("Firefox",), "webkit": ("Safari",)}[ENGINE]
        assert rows["browser"].startswith(expected)
        assert rows["os"] != "unknown"
        assert "Mozilla/5.0" in rows["useragent"]

    def test_freezes_are_logged(self, timing_run, session_csv):
        """Every pause of the page longer than 100 ms is in the session file, with its duration."""
        _, _, final = timing_run
        _, content = session_csv
        logged = [float(r["value"]) for r in csv.DictReader(io.StringIO(content)) if r["type"] == "freeze"]
        measured = [gap for gap in _intervals_ms(final["updates"]) if gap > 110]  # Away from the threshold
        print(f"\nfreezes logged: {logged} ms (measured by the probe: {[round(g) for g in measured]})")
        assert all(value > 100 for value in logged)
        for gap in measured:
            assert any(abs(value - gap) <= 5 for value in logged)


class TestBrowserCheck:
    """Start page notice for browsers with timing issues (Firefox), set by web_browser_check / ?browsercheck=."""

    def _menu(self, page_factory, params: str = "") -> OpenMATBPage:
        app = page_factory()
        app.open_menu(params)
        return app

    def test_default_warns_only_on_firefox(self, page_factory):
        app = self._menu(page_factory)
        assert app.page.is_visible("#browser-warning") == (ENGINE == "firefox")
        assert app.page.is_enabled("#start")

    def test_notice_is_shown_when_the_page_opens(self, page_factory):
        """Not only once OpenMATB is loaded (several seconds later)."""
        app = page_factory()
        app.page.goto(f"{app.url}/index.html?lang=en_EN")
        app.page.wait_for_selector("#lang")
        assert app.page.evaluate("() => window.openmatb === undefined")  # Still loading
        assert app.page.is_visible("#browser-warning") == (ENGINE == "firefox")

    def test_block_mode(self, page_factory):
        app = self._menu(page_factory, "&browsercheck=block")
        assert app.page.is_enabled("#start") == (ENGINE != "firefox")
        if ENGINE == "firefox":
            assert "Chrome or Edge" in app.page.text_content("#browser-warning")

    def test_off_mode(self, page_factory):
        app = self._menu(page_factory, "&browsercheck=off")
        assert not app.page.is_visible("#browser-warning")
        assert app.page.is_enabled("#start")

    def test_notice_is_translated(self, page_factory):
        if ENGINE != "firefox":
            pytest.skip("the notice is only displayed in Firefox")
        app = self._menu(page_factory)
        app.page.select_option("#lang", "fr_FR")
        assert "privilégiez Chrome ou Edge" in app.page.text_content("#browser-warning")


# ── Browser specific behaviour ──────────────────────────────────────────────


LONG_SCENARIO: str = "0:00:00;sysmon;start\n0:00:00;track;start\n0:05:00;sysmon;stop\n0:05:00;track;stop\n"


class TestHiddenTab:
    def test_hidden_tab_pauses_the_scenario(self, page_factory):
        app = page_factory()
        app.start(LONG_SCENARIO)
        app.wait_until(lambda s: s["scenario_time"] >= 1, timeout=20)
        app.hide_tab()
        paused = app.wait_until(lambda s: s["modal"], timeout=5)
        app.page.wait_for_timeout(1500)
        later = app.state()
        assert later["running"]
        assert later["scenario_time"] == pytest.approx(paused["scenario_time"], abs=0.02)


@pytest.fixture(scope="module")
def keyboard_app(page_factory):
    app = page_factory()
    app.start(LONG_SCENARIO)
    app.page.focus("#pygletCanvas")
    return app


class TestKeyboard:
    @pytest.mark.parametrize("key,symbol", [("Numpad1", "NUM_1"), ("Numpad8", "NUM_8"), ("Digit1", "_1")])
    def test_keys(self, keyboard_app, key, symbol):
        app = keyboard_app
        app.page.keyboard.press(key)
        state = app.wait_until(lambda s: s["keys"], timeout=5)
        assert state["keys"][-1] == symbol
        app.python("import _openmatb_probe; _openmatb_probe.PROBE['keys'].clear()")

    @pytest.mark.parametrize("key", ["F1", "F5", "F6"])
    def test_function_keys_stay_in_openmatb(self, keyboard_app, key):
        app = keyboard_app
        """F5 must not reload the page (sysmon uses F1-F6)."""
        app.page.evaluate("() => { window.__not_reloaded = true; }")
        app.page.keyboard.press(key)
        state = app.wait_until(lambda s: s["keys"], timeout=5)
        assert state["keys"][-1] == key
        assert app.page.evaluate("() => window.__not_reloaded === true")
        app.python("import _openmatb_probe; _openmatb_probe.PROBE['keys'].clear()")


class TestAudio:
    def test_sounds_are_played_one_after_the_other(self, page_factory, tolerance):
        """Browser SequencePlayer chains one player per sound: the sequence lasts the sum of the sounds."""
        app = page_factory()
        app.start(LONG_SCENARIO)
        if not app.has_web_audio:
            pytest.skip("this browser build has no Web Audio (Playwright WebKit on Windows)")
        sounds = ["0", "1", "2"]
        expected = app.python(
            "import wave\n"
            "from pathlib import Path\n"
            f"paths = [Path('includes/sounds/english/male/{{}}.wav'.format(n)) for n in {sounds!r}]\n"
            "sum(wave.open(str(p)).getnframes() / wave.open(str(p)).getframerate() for p in paths)"
        )
        app.python(
            "import js, pyglet.clock\n"
            "import _openmatb_probe as probe\n"
            "from core.audio import SequencePlayer, load_sound\n"
            "probe.player = SequencePlayer([load_sound(p) for p in paths])\n"
            "probe.audio = {'start': js.performance.now(), 'end': None}\n"
            "def watch(dt):\n"
            "    if probe.player.source is None and probe.audio['end'] is None:\n"
            "        probe.audio['end'] = js.performance.now()\n"
            "probe.PROBE['handlers'].append(watch)\n"
            "pyglet.clock.schedule_interval(watch, 0.005)\n"
            "probe.player.play()"
        )
        deadline_ms = (expected + 5) * 1000
        app.page.wait_for_function(
            "() => window.openmatb.pyodide.runPython(\"import _openmatb_probe as p; p.audio['end'] is not None\")",
            timeout=deadline_ms,
        )
        start, end = app.python("import _openmatb_probe as p; [p.audio['start'], p.audio['end']]")
        duration = (end - start) / 1000
        print(f"\nsequence of {len(sounds)} sounds: {duration:.3f} s (sounds: {expected:.3f} s)")
        assert duration >= expected - 0.05
        # Each sound starts on the update after the end of the previous one (+ decoding of the first)
        assert duration <= expected + (0.3 + 0.05 * len(sounds)) * tolerance


class TestFreezeLog:
    def test_a_blocked_page_is_logged(self, page_factory):
        """Block the page for 300 ms (like a Firefox garbage collection): a "freeze" row is written."""
        app = page_factory()
        app.start(LONG_SCENARIO)
        app.wait_until(lambda s: s["scenario_time"] >= 1, timeout=20)
        app.page.evaluate("() => { const end = performance.now() + 300; while (performance.now() < end) {} }")
        app.wait_until(lambda s: s["scenario_time"] >= 2, timeout=20)
        content = app.python(
            "from core.logger import get_logger\n"
            "logger = get_logger()\n"
            "logger.file.flush()\n"
            "logger.path.read_text(encoding='utf-8')"
        )
        freezes = [
            (float(r["scenario_time"]), float(r["value"]))
            for r in csv.DictReader(io.StringIO(content))
            if r["type"] == "freeze"
        ]
        print(f"\nfreeze rows (scenario time s, ms): {freezes}")
        assert any(1 <= time < 2 and 295 <= duration <= 400 for time, duration in freezes)
