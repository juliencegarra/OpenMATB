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
import json
import os
import re
import statistics
import sys
import time

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
    # The end screen is shown when the session file is handed over; pyglet's loop stops just after
    final = app.wait_until(lambda s: not s["running"], timeout=10)
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


def _dark_runs(flags: list[bool]) -> list[tuple[int, int]]:
    runs, i = [], 0
    while i < len(flags):
        if flags[i]:
            start = i
            while i < len(flags) and flags[i]:
                i += 1
            runs.append((start, i))
        i += 1
    return runs


class TestTextRendering:
    def test_letters_share_the_same_baseline(self, page_factory):
        """Regression: with fractional font metrics (Firefox), pyglet drew some letters one pixel too high
        or too low. Measured on the session ID dialog: the bottom of every letter is on the baseline, except
        descenders (a few pixels lower)."""
        image_module = pytest.importorskip("PIL.Image")
        app = page_factory()
        app.start(LONG_SCENARIO, config={"display_session_number": "True"})
        app.wait_until(lambda s: s["modal"], timeout=10)
        app.page.wait_for_timeout(500)
        image = image_module.open(io.BytesIO(app.page.screenshot())).convert("L")
        pixels, (width, height) = image.load(), image.size
        dark = lambda x, y: pixels[x, y] < 128  # noqa: E731

        # The dialog is centered (white background): its 2nd text line is the session ID
        cx, y0 = width // 2, height // 2 - 55
        x0 = next(x for x in range(cx, 0, -1) if pixels[x, y0 + 5] < 250) + 3
        x1 = next(x for x in range(cx, width) if pixels[x, y0 + 5] < 250) - 3
        rows = _dark_runs([any(dark(x, y) for x in range(x0, x1)) for y in range(y0, height // 2 + 55)])
        top, bottom = y0 + rows[1][0], y0 + rows[1][1] + 6
        letters = _dark_runs([any(dark(x, y) for y in range(top, bottom)) for x in range(x0, x1)])
        bottoms = [max(y for y in range(top, bottom) for x in range(x0 + a, x0 + b) if dark(x, y)) for a, b in letters]

        baseline = max(set(bottoms), key=bottoms.count)
        offsets = [b - baseline for b in bottoms]
        print(f"\n{len(letters)} letters, offsets from the baseline: {sorted(set(offsets))}")
        assert len(letters) >= 10
        assert all(offset == 0 or offset >= 3 for offset in offsets)  # Aligned, or a descender (g, p, q, y...)


class TestPageResize:
    @pytest.mark.parametrize("width,height", [(1280, 720), (1000, 800), (1600, 900)])
    def test_display_follows_the_page(self, page_factory, width, height):
        """Leaving fullscreen shrinks the page: the whole interface stays visible and centered, and mouse
        positions are still converted to the right place."""
        app = page_factory()
        app.page.set_viewport_size({"width": 1600, "height": 900})
        app.start(LONG_SCENARIO)
        app.python(
            "import _openmatb_probe as probe\n"
            "from core.window import Window\n"
            "probe.clicks = []\n"
            "def on_press(x, y, button, modifiers):\n"
            "    probe.clicks.append([x, y])\n"
            "probe.PROBE['handlers'].append(on_press)\n"
            "Window.MainWindow.push_handlers(on_mouse_press=on_press)"
        )
        app.page.set_viewport_size({"width": width, "height": height})
        app.page.wait_for_timeout(500)
        box = app.page.evaluate(
            """() => { const c = document.getElementById("pygletCanvas"); const r = c.getBoundingClientRect();
                return {left: r.left, top: r.top, width: r.width, height: r.height, fw: c.width, fh: c.height}; }"""
        )
        factor = min(width / 1600, height / 900)
        assert box["width"] == pytest.approx(1600 * factor, abs=1)
        assert box["height"] == pytest.approx(900 * factor, abs=1)
        assert box["left"] == pytest.approx((width - box["width"]) / 2, abs=1)  # Centered
        assert box["top"] == pytest.approx((height - box["height"]) / 2, abs=1)

        app.page.mouse.click(box["left"] + box["width"] / 4, box["top"] + box["height"] / 4)
        x, y = app.python("import json, _openmatb_probe as probe; json.dumps(probe.clicks[-1])").strip("[]").split(",")
        assert float(x) == pytest.approx(box["fw"] / 4, abs=3)
        assert float(y) == pytest.approx(box["fh"] * 3 / 4, abs=3)  # pyglet: y from the bottom


# ── Replay ──────────────────────────────────────────────────────────────────


REPLAY_SCENARIO: str = (
    "0:00:00;sysmon;start\n0:00:00;track;start\n0:00:00;resman;start\n"
    "0:00:02;sysmon;scales-1-failure;True\n"
    "0:00:08;sysmon;stop\n0:00:08;track;stop\n0:00:08;resman;stop\n"
)
REPLAY_KEYS: list[tuple[float, str]] = [(3.0, "F1"), (5.0, "Numpad1")]

REPLAY_STATE: str = """
import json, pyglet.app, _openmatb_probe as probe
from core.error import get_errors
s = probe.PROBE["scheduler"]
inputs = s.logreader.keyboard_inputs
json.dumps({
    "type": type(s).__name__,
    "session_id": s.logreader.replay_session_id,
    "running": bool(pyglet.app.event_loop.is_running),
    "paused": s.is_paused,
    "replay_time": s.replay_time,
    "duration": s.logreader.session_duration,
    "keys_in_log": [[i["address"], i["value"]] for i in inputs],
    "keys_replayed": [[inputs[i]["address"], inputs[i]["value"]] for i in sorted(s._executed_key_indices)],
    "events_done": sum(1 for e in s.events if e.done),
    "events": len(s.events),
    "alive": sorted(name for name, plugin in s.plugins.items() if plugin.alive),
    "errors": list(get_errors().errors_list),
})
"""


@pytest.fixture(scope="module")
def replay_run(page_factory):
    """Run a session, then replay it in another tab of the same browser (same storage): play it in real time
    to its end, then restart it and jump to its end."""
    session = page_factory()
    session.start(REPLAY_SCENARIO)
    session.page.focus("#pygletCanvas")
    for at, key in REPLAY_KEYS:
        session.wait_until(lambda s, at=at: s["scenario_time"] >= at, timeout=20)
        session.page.keyboard.press(key)
    session.page.wait_for_selector("#end:not([hidden])", timeout=30_000)
    rows = list(csv.DictReader(io.StringIO(session.downloads[0].path().read_text(encoding="utf-8"))))
    session_id = int(session.downloads[0].suggested_filename.split("_")[0])

    replay = session.new_tab()
    replay.start_replay(session_id)
    state = lambda: json.loads(replay.python(REPLAY_STATE))  # noqa: E731
    replay.wait_until(lambda s: s["running"], timeout=20)  # pyglet starts its loop just after the replay
    result = {"session_id": session_id, "rows": rows, "loaded": state(), "errors": replay.errors}

    replay.page.focus("#pygletCanvas")
    replay.page.keyboard.press("Space")  # Play
    replay.page.wait_for_timeout(2000)
    result["after_2s"] = state()
    deadline = time.monotonic() + 20
    while not (current := state())["paused"] and time.monotonic() < deadline:
        time.sleep(0.2)
    result["natural_end"] = current

    replay.page.keyboard.press("Home")  # Back to the start, then jump to the end
    replay.page.wait_for_timeout(500)
    replay.page.keyboard.press("End")
    replay.page.wait_for_timeout(1500)
    result["jump_end"] = state()
    return result


class TestReplay:
    def test_session_is_found_in_the_browser_storage(self, replay_run):
        loaded = replay_run["loaded"]
        assert loaded["type"] == "ReplayScheduler"
        assert loaded["session_id"] == replay_run["session_id"]
        assert loaded["running"]
        assert loaded["paused"]  # A replay starts paused
        assert loaded["errors"] == []
        assert replay_run["errors"] == []

    def test_log_contents(self, replay_run):
        session_keys = [
            [r["address"], r["value"]] for r in replay_run["rows"] if r["type"] == "input" and r["module"] == "keyboard"
        ]
        assert session_keys == [["F1", "press"], ["F1", "release"], ["NUM_1", "press"], ["NUM_1", "release"]]
        assert replay_run["loaded"]["keys_in_log"] == session_keys
        assert replay_run["loaded"]["events"] == 7
        assert replay_run["loaded"]["duration"] == pytest.approx(8, abs=0.5)

    def test_plays_in_real_time(self, replay_run):
        after = replay_run["after_2s"]
        assert not after["paused"]
        assert after["replay_time"] == pytest.approx(2, abs=0.4)

    def test_played_to_the_end_replays_everything(self, replay_run):
        end = replay_run["natural_end"]
        assert end["paused"]  # Paused by the end of the session
        assert end["replay_time"] == pytest.approx(end["duration"], abs=0.01)
        assert end["keys_replayed"] == end["keys_in_log"]
        assert end["events_done"] == end["events"]
        assert end["alive"] == []  # All the tasks were stopped
        assert end["running"] and end["errors"] == []

    def test_jump_to_the_end(self, replay_run):
        end = replay_run["jump_end"]
        assert end["replay_time"] == pytest.approx(end["duration"], abs=0.01)
        assert end["keys_replayed"] == end["keys_in_log"]
        assert end["running"] and end["errors"] == []

    def test_jump_to_the_end_executes_all_the_events(self, replay_run):
        """Regression: fast-forward ran one event per 0.1 s step, so simultaneous events at the end of the
        session (the three stops at 0:00:08) were not all executed."""
        end = replay_run["jump_end"]
        assert end["events_done"] == end["events"]
        assert end["alive"] == []


class TestScreenshot:
    def test_f12_downloads_a_png(self, page_factory):
        """F12 saves a screenshot: in the browser it is handed to the user as a download."""
        app = page_factory()
        app.start(LONG_SCENARIO)
        app.wait_until(lambda s: s["scenario_time"] >= 1, timeout=20)
        app.page.focus("#pygletCanvas")
        with app.page.expect_download(timeout=10_000) as download:
            app.page.keyboard.press("F12")
        assert download.value.suggested_filename.startswith("screenshot_")
        assert download.value.suggested_filename.endswith(".png")
        assert download.value.path().read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        image_module = pytest.importorskip("PIL.Image")
        colors = image_module.open(download.value.path()).convert("RGB").getcolors(maxcolors=1 << 16)
        assert colors is None or len(colors) > 10  # The tasks are drawn: not a blank (cleared) image


# ── Session file destinations (web_session_output) ──────────────────────────


OUTPUT_SCENARIO: str = "0:00:00;sysmon;start\n0:00:03;sysmon;stop\n"
# Longer than the checkpoint interval (10 s): the file is also sent during the session
CHECKPOINT_SCENARIO: str = "0:00:00;sysmon;start\n0:00:12;sysmon;stop\n"
FAKE_JATOS: str = """
window.jatos = {
    calls: [],
    onLoad(callback) { setTimeout(callback, 0); },
    submitResultData(data) { this.calls.push(["submitResultData", data]); return Promise.resolve(); },
    uploadResultFile(data, filename) { this.calls.push(["uploadResultFile", filename, data]); return Promise.resolve(); },
    endStudy() { this.calls.push(["endStudy"]); },
};
"""


class Requests:
    """Requests received by a mocked service (page.route)."""

    def __init__(self) -> None:
        self.received: list[dict] = []

    def record(self, route, status: int = 201, body: str = "") -> None:
        request = route.request
        self.received.append(
            {"method": request.method, "url": request.url, "headers": request.headers, "body": request.post_data}
        )
        route.fulfill(status=status, body=body, headers={"Access-Control-Allow-Origin": "*"})


def _end_items(app: OpenMATBPage) -> list[str]:
    app.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
    app.page.wait_for_function(
        "() => !document.querySelector('#end-destinations li:not(.ok):not(.failed)')", timeout=20_000
    )
    return app.page.eval_on_selector_all(
        "#end-destinations li", "items => items.map(i => i.className + ': ' + i.textContent)"
    )


class TestSessionOutput:
    def test_default_is_the_download_only(self, page_factory):
        app = page_factory()
        requests = Requests()
        app.page.route("**/dav/**", lambda route: requests.record(route))
        app.page.route("https://pipe.jspsych.org/**", lambda route: requests.record(route))
        app.start(OUTPUT_SCENARIO)
        assert _end_items(app) == ["ok: Downloaded on this computer"]
        assert len(app.downloads) == 1
        assert requests.received == []

    def test_webdav_during_the_session_and_at_the_end(self, page_factory):
        """Same structure as desktop: <folder>/<YYYY-MM-DD>/<N>_<yymmdd>_<hhmmss>.csv, sent every 10 s."""
        app = page_factory()
        dav = Requests()
        app.page.route("**/dav/**", lambda route: dav.record(route))
        app.start(CHECKPOINT_SCENARIO, config={"web_session_output": "webdav", "web_webdav_url": f"{app.url}/dav/"})
        assert _end_items(app) == ["ok: Sent to the server (WebDAV)"]
        assert app.downloads == []  # Not downloaded
        methods = [r["method"] for r in dav.received]
        assert methods[0] == "MKCOL" and methods.count("MKCOL") == 1
        puts = [r for r in dav.received if r["method"] == "PUT"]
        assert len(puts) >= 2  # During the session (checkpoint) and at the end
        pattern = rf"{re.escape(app.url)}/dav/\d{{4}}-\d\d-\d\d/\d+_\d{{6}}_\d{{6}}\.csv"
        assert re.fullmatch(pattern, puts[-1]["url"])
        assert dav.received[0]["url"] == puts[-1]["url"].rsplit("/", 1)[0] + "/"  # MKCOL of the day folder
        assert puts[0]["headers"].get("if-none-match") == "*"  # Never overwrite another session
        assert "if-none-match" not in puts[-1]["headers"]
        rows = list(csv.DictReader(io.StringIO(puts[-1]["body"])))
        assert [r["value"] for r in rows if r["type"] == "event"] == ["start", "stop"]
        assert len(puts[-1]["body"]) > len(puts[0]["body"])  # The checkpoint sent the file written so far

    def test_webdav_does_not_overwrite_another_session(self, page_factory):
        """A file with the same name already on the server (412): the session is sent as <name>_2.csv."""
        app = page_factory()
        dav = Requests()

        def handler(route):
            first_put = route.request.method == "PUT" and not any(r["method"] == "PUT" for r in dav.received)
            dav.record(route, status=412 if first_put else 201)

        app.page.route("**/dav/**", handler)
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "webdav", "web_webdav_url": f"{app.url}/dav/"})
        assert _end_items(app) == ["ok: Sent to the server (WebDAV)"]
        puts = [r["url"] for r in dav.received if r["method"] == "PUT"]
        assert puts[1].endswith("_2.csv") and puts[1][: -len("_2.csv")] == puts[0][: -len(".csv")]

    def test_datapipe_at_the_end(self, page_factory):
        app = page_factory()
        pipe = Requests()
        app.page.route("https://pipe.jspsych.org/**", lambda route: pipe.record(route, body='{"message": "Success"}'))
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "datapipe", "web_datapipe_experiment": "abc123"})
        assert _end_items(app) == ["ok: Sent to the OSF (DataPipe)"]
        posts = [r for r in pipe.received if r["method"] == "POST"]
        assert len(posts) == 1 and posts[0]["url"] == "https://pipe.jspsych.org/api/data/"
        body = json.loads(posts[0]["body"])
        assert body["experimentID"] == "abc123"
        assert re.fullmatch(r"\d+_\d{6}_\d{6}\.csv", body["filename"])
        assert "sysmon" in body["data"]

    def test_datapipe_existing_file_name(self, page_factory):
        """DataPipe rejects an existing file name: the session is sent again with a random suffix."""
        app = page_factory()
        pipe = Requests()

        def handler(route):
            if route.request.method != "POST":
                return pipe.record(route, status=204)
            if not [r for r in pipe.received if r["method"] == "POST"]:
                return pipe.record(route, status=400, body='{"error": "FILE_EXISTS", "message": "File exists"}')
            return pipe.record(route, body='{"message": "Success"}')

        app.page.route("https://pipe.jspsych.org/**", handler)
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "datapipe", "web_datapipe_experiment": "abc123"})
        assert _end_items(app) == ["ok: Sent to the OSF (DataPipe)"]
        names = [json.loads(r["body"])["filename"] for r in pipe.received if r["method"] == "POST"]
        assert len(names) == 2 and names[1] != names[0] and names[1].startswith(names[0][: -len(".csv")] + "_")

    def test_jatos(self, page_factory):
        app = page_factory()
        app.page.route("**/jatos.js", lambda route: route.fulfill(body=FAKE_JATOS, content_type="text/javascript"))
        app.start(CHECKPOINT_SCENARIO, config={"web_session_output": "jatos"})
        assert _end_items(app) == ["ok: Sent to JATOS"]
        app.page.wait_for_function("() => window.jatos.calls.some(c => c[0] === 'endStudy')", timeout=10_000)
        calls = app.page.evaluate("() => window.jatos.calls")
        names = [c[0] for c in calls]
        assert names.count("submitResultData") >= 2  # Checkpoint(s) and end
        assert names[-2:] == ["uploadResultFile", "endStudy"]
        assert re.fullmatch(r"\d+_\d{6}_\d{6}\.csv", calls[-2][1]) and "sysmon" in calls[-2][2]
        assert app.downloads == []

    def test_server_and_download(self, page_factory):
        app = page_factory()
        dav = Requests()
        app.page.route("**/dav/**", lambda route: dav.record(route))
        config = {"web_session_output": "webdav, download", "web_webdav_url": f"{app.url}/dav/"}
        app.start(OUTPUT_SCENARIO, config=config)
        assert _end_items(app) == ["ok: Sent to the server (WebDAV)", "ok: Downloaded on this computer"]
        assert len(app.downloads) == 1

    def test_failed_upload_falls_back_to_the_download(self, page_factory):
        app = page_factory()
        app.page.route("**/dav/**", lambda route: route.fulfill(status=500, body="Server error"))
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "webdav", "web_webdav_url": f"{app.url}/dav/"})
        items = _end_items(app)
        assert items[0].startswith("failed: Not sent to WebDAV: HTTP 500")
        assert items[1] == "ok: Downloaded on this computer, because it could not be sent"
        assert len(app.downloads) == 1

    def test_configuration_error_prevents_starting(self, page_factory):
        app = page_factory()
        app.prepare(OUTPUT_SCENARIO, config={"web_session_output": "webdav"})  # No web_webdav_url
        app.page.click("#start")
        app.page.wait_for_selector("#config-error:not([hidden])", timeout=10_000)
        assert "web_webdav_url" in app.page.text_content("#config-error")
        assert app.page.is_visible("#menu")
        assert not app.state()["started"]

    def test_jatos_outside_jatos(self, page_factory):
        """jatos.js is served by JATOS: without it, a clear message instead of a broken session."""
        app = page_factory()
        app.page.route("**/jatos.js", lambda route: route.fulfill(status=404, body=""))
        app.prepare(OUTPUT_SCENARIO, config={"web_session_output": "jatos"})
        app.page.click("#start")
        app.page.wait_for_selector("#config-error:not([hidden])", timeout=10_000)
        assert "run the study from JATOS" in app.page.text_content("#config-error")
        assert app.page.is_visible("#menu")
