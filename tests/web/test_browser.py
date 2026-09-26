"""OpenMATB in a real browser: timing, stability and web specific behaviour.

Run with:  OPENMATB_BROWSER_TESTS=1 python -m pytest tests/web -v
(see tests/web/conftest.py for the requirements and options)

Timing thresholds (ms) are for a desktop machine; OPENMATB_TIMING_TOLERANCE multiplies them.
The scenario clock updates at most every WEB_UPDATE_INTERVAL = 8.3 ms (core/clock.py); in Chrome,
wake-ups actually come every ~9-17 ms.
"""

from __future__ import annotations

import base64
import csv
import gzip
import io
import json
import os
import re
import statistics
import sys
import time

import pytest

from tests.web.conftest import PROBE, OpenMATBPage

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

    def test_key_released_without_the_focus(self, keyboard_app):
        """A key released while the page has lost the focus sends no key up: the next press must still count."""
        app = keyboard_app
        app.page.keyboard.down("F2")
        app.page.evaluate("() => document.getElementById('pygletCanvas').blur()")
        app.page.keyboard.up("F2")
        app.page.wait_for_timeout(200)  # pyglet handles the focus change in its event loop
        app.page.focus("#pygletCanvas")
        app.page.wait_for_timeout(200)
        app.page.keyboard.press("F2")
        state = app.wait_until(lambda s: len(s["keys"]) >= 2, timeout=5)
        assert state["keys"] == ["F2", "F2"]
        app.python("import _openmatb_probe; _openmatb_probe.PROBE['keys'].clear()")


# Sysmon failures answered with their key, resman pumps switched with the numpad: checked in the session file
KEY_RESPONSES_SCENARIO: str = """0:00:00;sysmon;start
0:00:00;resman;start
0:00:02;sysmon;scales-1-failure;True
0:00:05;sysmon;scales-2-failure;True
0:00:08;sysmon;scales-3-failure;True
0:00:11;sysmon;scales-4-failure;True
0:00:13;resman;pump-3-state;failure
0:00:14;sysmon;lights-1-failure;True
0:00:17;sysmon;lights-2-failure;True
0:00:19;resman;pump-3-state;off
0:00:22;sysmon;stop
0:00:22;resman;stop
"""
KEY_RESPONSES_STATE: str = """
import json, _openmatb_probe as probe
s = probe.PROBE["scheduler"]
json.dumps({"time": s.scenario_time,
            "failures": [g["key"] for g in s.plugins["sysmon"].get_gauges_on_failure()],
            "pumps": {k: v["state"] for k, v in s.plugins["resman"].parameters["pump"].items()}})
"""
# (scenario time, key, pump, its state after the press). Pump 3 is failed from 13 to 19 s: its key does nothing
PUMP_PRESSES: list[tuple[float, str, str, str]] = [
    (1, "Numpad1", "1", "on"),
    (4, "Numpad2", "2", "on"),
    (7, "Numpad1", "1", "off"),
    (10, "Numpad2", "2", "off"),
    (15.5, "Numpad3", "3", "failure"),
    (20, "Numpad3", "3", "on"),
]
RESPONSE_DELAY_S: float = 0.3


class TestKeyResponses:
    def test_responses_are_in_the_session_file(self, page_factory):
        """Each failure is answered with its key 0.3 s after it appears. Before the F5 answer, F5 is released
        while the page has lost the focus: the answer must still count (then a second F5 press is a false alarm)."""
        app = page_factory()
        app.start(KEY_RESPONSES_SCENARIO)
        app.page.focus("#pygletCanvas")
        seen: dict[str, float] = {}
        answered: list[str] = []
        pump_presses = list(PUMP_PRESSES)
        pumps_after: list[tuple[str, str, str]] = []
        while not app.page.is_visible("#end"):
            try:
                state = json.loads(app.python(KEY_RESPONSES_STATE))
            except Exception:  # The session has just ended
                break
            for key in state["failures"]:
                seen.setdefault(key, time.monotonic())
                if key not in answered and time.monotonic() - seen[key] >= RESPONSE_DELAY_S:
                    if key == "F5":
                        app.page.keyboard.down("F5")  # Answers the failure
                        app.page.evaluate("() => document.getElementById('pygletCanvas').blur()")
                        app.page.keyboard.up("F5")  # Released outside the page
                        app.page.wait_for_timeout(200)
                        app.page.focus("#pygletCanvas")
                        app.page.wait_for_timeout(200)
                    app.page.keyboard.press(key)
                    answered.append(key)
            while pump_presses and state["time"] >= pump_presses[0][0]:
                _time, key, pump, expected = pump_presses.pop(0)
                app.page.keyboard.press(key)
                app.page.wait_for_timeout(100)
                pumps_after.append((key, json.loads(app.python(KEY_RESPONSES_STATE))["pumps"][pump], expected))
            app.page.wait_for_timeout(50)
        app.page.wait_for_selector("#end:not([hidden])", timeout=30_000)

        assert answered == ["F1", "F2", "F3", "F4", "F5", "F6"]
        assert [(key, state) for key, state, _ in pumps_after] == [(key, expected) for key, _, expected in pumps_after]
        assert len(pumps_after) == len(PUMP_PRESSES)

        rows = list(csv.DictReader(io.StringIO(app.downloads[0].path().read_text(encoding="utf-8"))))
        sysmon = [r for r in rows if r["type"] == "performance" and r["module"] == "sysmon"]
        names = [r["value"] for r in sysmon if r["address"] == "name"]
        detections = [r["value"] for r in sysmon if r["address"] == "signal_detection"]
        assert list(zip(names, detections)) == [
            ("F1", "HIT"),
            ("F2", "HIT"),
            ("F3", "HIT"),
            ("F4", "HIT"),
            ("F5", "HIT"),
            ("F5", "FA"),
            ("F6", "HIT"),
        ]
        response_times = [float(r["value"]) for r in sysmon if r["address"] == "response_time"]
        hits = [rt for rt, detection in zip(response_times, detections) if detection == "HIT"]
        assert all(RESPONSE_DELAY_S * 1000 <= rt < 2000 for rt in hits), hits
        presses = [r["address"] for r in rows if r["module"] == "keyboard" and r["value"] == "press"]
        assert presses == [
            "NUM_1",
            "F1",
            "NUM_2",
            "F2",
            "NUM_1",
            "F3",
            "NUM_2",
            "F4",
            "F5",
            "F5",
            "NUM_3",
            "F6",
            "NUM_3",
        ]


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
    def test_task_titles_after_a_fullscreen_questionnaire(self, page_factory):
        """Regression: after a fullscreen questionnaire (basic.txt starts with the NASA-TLX), the black title bands
        of the tasks had no text. Hiding the questionnaire labels removed them from the batch, and pyglet 3 then
        removed the equal group of the task titles too."""
        image_module = pytest.importorskip("PIL.Image")
        app = page_factory()
        app.start(
            "0:00:00;sysmon;start\n0:00:00;track;start\n"
            "0:00:00;genericscales;filename;nasatlx_en.txt\n0:00:00;genericscales;start\n"
            "0:00:30;sysmon;stop\n0:00:30;track;stop\n"
        )
        app.page.wait_for_timeout(1000)
        app.page.focus("#pygletCanvas")
        app.page.keyboard.press("Space")  # Validates the questionnaire
        app.page.wait_for_timeout(1000)
        image = image_module.open(io.BytesIO(app.page.screenshot())).convert("L")
        pixels, (width, height) = image.load(), image.size
        # The upper black band (task titles) is the top 5 % of the page: white text on it
        light = sum(pixels[x, y] > 200 for x in range(width) for y in range(3, int(height * 0.04)))
        assert light > 100, "no task title in the upper band"

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
    "environment": s.logreader.environment,
    "environment_label": s.environment_label.get_text() if hasattr(s, "environment_label") else None,
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

    def test_browser_of_the_session_is_shown(self, replay_run):
        loaded = replay_run["loaded"]
        expected = {"chromium": ("Chrome", "Edge"), "firefox": ("Firefox",), "webkit": ("Safari",)}[ENGINE]
        assert loaded["environment"]["browser"].startswith(expected)
        browser, system = loaded["environment_label"].split("\n")
        assert loaded["environment"]["browser"].startswith(browser) and "." not in browser  # Major version
        assert system == loaded["environment"]["os"]

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
    uploadResultFile(data, filename) {
        this.calls.push(["uploadResultFile", filename, data.type]);
        this.files[filename] = data;  // Replaces the previous upload, as JATOS does in the same component
        return Promise.resolve();
    },
    endStudy() { this.calls.push(["endStudy"]); },
    files: {},
    async text(filename) {
        const stream = this.files[filename].stream().pipeThrough(new DecompressionStream("gzip"));
        return new Response(stream).text();
    },
};
"""


class FakeDataPipe:
    """DataPipe (pipe.jspsych.org), mocked: it checks the experiment before the data, like DataPipe."""

    def __init__(self, app: OpenMATBPage, active: bool = True, existing_files: int = 0) -> None:
        self.active = active
        self.existing_files = existing_files  # Number of uploads rejected with FILE_EXISTS
        self.checks: list[dict] = []
        self.files: list[dict] = []
        app.page.route("https://pipe.jspsych.org/**", self.handle)

    def handle(self, route) -> None:
        request = {"url": route.request.url, "json": json.loads(route.request.post_data or "{}")}
        headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"}
        if route.request.method != "POST":
            route.fulfill(status=204, headers=headers)
        elif not self.active:
            body = {
                "error": "BASE64DATA_COLLECTION_NOT_ACTIVE",
                "message": "Base64 data collection is not active for this experiment",
            }
            route.fulfill(status=400, headers=headers, body=json.dumps(body), content_type="application/json")
        elif request["json"].get("data") == "!":  # Not base64: the check made when the session starts
            self.checks.append(request)
            body = {"error": "INVALID_BASE64_DATA", "message": "The data are not valid base64 data"}
            route.fulfill(status=400, headers=headers, body=json.dumps(body), content_type="application/json")
        else:
            self.files.append(request)
            if len(self.files) <= self.existing_files:
                body = {"error": "FILE_EXISTS", "message": "File exists"}
                route.fulfill(status=400, headers=headers, body=json.dumps(body), content_type="application/json")
            else:
                route.fulfill(
                    status=201, headers=headers, body='{"message": "Success"}', content_type="application/json"
                )


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


def _end_list(app: OpenMATBPage) -> list[str]:
    return app.page.eval_on_selector_all(
        "#end-destinations li", "items => items.map(i => i.className + ': ' + i.textContent)"
    )


def _end_items(app: OpenMATBPage) -> list[str]:
    app.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
    app.page.wait_for_function(
        "() => !document.querySelector('#end-destinations li:not(.ok):not(.failed)')", timeout=20_000
    )
    return _end_list(app)


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
        pipe = FakeDataPipe(app)
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "datapipe", "web_datapipe_experiment": "abc123"})
        assert _end_items(app) == ["ok: Sent to DataPipe"]
        assert len(pipe.checks) == 1  # When the session started
        assert len(pipe.files) == 1 and pipe.files[0]["url"] == "https://pipe.jspsych.org/api/base64/"
        body = pipe.files[0]["json"]
        assert body["experimentID"] == "abc123"
        # Compressed (DataPipe accepts 32 MB per request), with a random suffix (Zenodo replaces a file silently)
        assert re.fullmatch(r"\d+_\d{6}_\d{6}_[a-z0-9]+\.csv\.gz", body["filename"])
        csv_text = gzip.decompress(base64.b64decode(body["data"])).decode("utf-8")
        assert csv_text.startswith("logtime,scenario_time,") and csv_text.rstrip().endswith("manual,,,end")

    def test_datapipe_existing_file_name(self, page_factory):
        """DataPipe rejects an existing file name (OSF): the session is sent again with another random suffix."""
        app = page_factory()
        pipe = FakeDataPipe(app, existing_files=1)
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "datapipe", "web_datapipe_experiment": "abc123"})
        assert _end_items(app) == ["ok: Sent to DataPipe"]
        names = [request["json"]["filename"] for request in pipe.files]
        stem = re.compile(r"(\d+_\d{6}_\d{6})_[a-z0-9]+\.csv\.gz")
        assert len(names) == 2 and names[1] != names[0]
        assert stem.fullmatch(names[0]).group(1) == stem.fullmatch(names[1]).group(1)

    def test_datapipe_not_ready(self, page_factory):
        """Checked when the session starts, rather than lost at its end: the session does not start."""
        app = page_factory()
        pipe = FakeDataPipe(app, active=False)
        app.prepare(OUTPUT_SCENARIO, config={"web_session_output": "datapipe", "web_datapipe_experiment": "abc123"})
        app.page.click("#start")
        app.page.wait_for_selector("#config-error:not([hidden])", timeout=10_000)
        assert "Base64 data collection is not active" in app.page.text_content("#config-error")
        assert app.page.is_visible("#menu")
        assert pipe.files == []

    def test_jatos(self, page_factory):
        app = page_factory()
        app.page.route("**/jatos.js", lambda route: route.fulfill(body=FAKE_JATOS, content_type="text/javascript"))
        app.start(CHECKPOINT_SCENARIO, config={"web_session_output": "jatos"})
        app.page.wait_for_function("() => window.jatos.calls.some(c => c[0] === 'endStudy')", timeout=60_000)
        assert _end_list(app) == ["ok: Sent to JATOS", ": End of the study…"]
        # JATOS takes over: going back to the menu would reload the page and leave the study run unfinished
        assert not app.page.is_visible("#back")
        calls = app.page.evaluate("() => window.jatos.calls")
        names = [c[0] for c in calls]
        assert names.count("uploadResultFile") >= 2  # Checkpoint(s) and end
        assert names[-3:] == ["uploadResultFile", "submitResultData", "endStudy"]
        # The file goes compressed, always under the same name (JATOS limits the result data to 5 MB)
        filenames = {c[1] for c in calls if c[0] == "uploadResultFile"}
        assert len(filenames) == 1
        filename = filenames.pop()
        assert re.fullmatch(r"\d+_\d{6}_\d{6}\.csv\.gz", filename)
        assert {c[2] for c in calls if c[0] == "uploadResultFile"} == {"application/gzip"}
        csv_text = app.page.evaluate("(name) => window.jatos.text(name)", filename)
        assert csv_text.startswith("logtime,scenario_time,") and csv_text.rstrip().endswith("manual,,,end")
        # The result data only holds a summary
        summaries = [json.loads(c[1]) for c in calls if c[0] == "submitResultData"]
        assert summaries[0]["state"] == "running" and summaries[-1]["state"] == "finished"
        assert summaries[-1]["file"] == filename and summaries[-1]["csv_bytes"] == len(csv_text.encode())
        assert summaries[-1]["scenario_time"] == pytest.approx(12, abs=0.5)
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

    def test_none(self, page_factory):
        app = page_factory()
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "none"})
        assert _end_items(app) == ["ok: Not sent anywhere (web_session_output=none)"]
        assert app.downloads == []

    def test_jatos_study_not_ended(self, page_factory):
        """If JATOS refuses to end the study run, the participant sees it and can go back to the menu."""
        app = page_factory()
        refusing = FAKE_JATOS.replace(
            'endStudy() { this.calls.push(["endStudy"]); },',
            'endStudy() { this.calls.push(["endStudy"]); return Promise.reject(new Error("study run closed")); },',
        )
        app.page.route("**/jatos.js", lambda route: route.fulfill(body=refusing, content_type="text/javascript"))
        app.start(OUTPUT_SCENARIO, config={"web_session_output": "jatos"})
        assert _end_items(app) == [
            "ok: Sent to JATOS",
            "failed: The study could not be ended in JATOS: study run closed",
        ]
        assert app.page.is_visible("#back")

    def test_jatos_outside_jatos(self, page_factory):
        """jatos.js is served by JATOS: without it, a clear message instead of a broken session."""
        app = page_factory()
        app.page.route("**/jatos.js", lambda route: route.fulfill(status=404, body=""))
        app.prepare(OUTPUT_SCENARIO, config={"web_session_output": "jatos"})
        app.page.click("#start")
        app.page.wait_for_selector("#config-error:not([hidden])", timeout=10_000)
        assert "run the study from JATOS" in app.page.text_content("#config-error")
        assert app.page.is_visible("#menu")


# ── SCORM (the page run by an LMS) ──────────────────────────────────────────


# The SCORM 1.2 API of an LMS: records the calls, keeps the data model values
FAKE_SCORM_API: str = """
window.API = {
    calls: [],
    values: {"cmi.core.lesson_status": "not attempted", "cmi.core.student_id": "learner-42"},
    record(name, ...args) { this.calls.push([name, ...args]); },
    LMSInitialize(arg) { this.record("LMSInitialize"); return "true"; },
    LMSFinish(arg) { this.record("LMSFinish"); return "true"; },
    LMSGetValue(key) { this.record("LMSGetValue", key); return this.values[key] ?? ""; },
    LMSSetValue(key, value) { this.record("LMSSetValue", key, value); this.values[key] = value; return "true"; },
    LMSCommit(arg) { this.record("LMSCommit"); return "true"; },
    LMSGetLastError() { return "0"; },
};
"""


class TestScorm:
    def test_completed_at_the_end_of_the_session(self, page_factory):
        app = page_factory()
        app.page.context.add_init_script(FAKE_SCORM_API)
        app.prepare(OUTPUT_SCENARIO)
        assert not app.page.is_visible("#mode")  # Participants only run the scenario
        assert app.page.evaluate("() => window.API.values['cmi.core.lesson_status']") == "incomplete"
        app.page.click("#start")
        assert _end_items(app) == [
            "ok: Downloaded on this computer",  # The session file still goes where config.ini says
            "ok: Activity completed in the learning platform (LMS)",
        ]
        assert not app.page.is_visible("#back")  # The LMS takes over
        values = app.page.evaluate("() => window.API.values")
        assert values["cmi.core.lesson_status"] == "completed"
        assert re.fullmatch(r"\d{4}-\d\d-\d\d/\d+_\d{6}_\d{6}\.csv", values["cmi.core.lesson_location"])
        assert values["cmi.core.lesson_location"].endswith(app.downloads[0].suggested_filename)

        app.page.evaluate("() => window.dispatchEvent(new PageTransitionEvent('pagehide'))")
        calls = app.page.evaluate("() => window.API.calls")
        assert calls[0] == ["LMSInitialize"] and calls[-1] == ["LMSFinish"]
        assert [c[0] for c in calls].count("LMSFinish") == 1
        assert re.fullmatch(
            r"\d{4}:\d\d:\d\d\.\d\d", app.page.evaluate("() => window.API.values['cmi.core.session_time']")
        )

    def test_without_lms(self, page_factory):
        app = page_factory()
        app.start(OUTPUT_SCENARIO)
        assert _end_items(app) == ["ok: Downloaded on this computer"]
        assert app.page.is_visible("#back")

    def test_api_found_in_a_parent_frame(self, page_factory):
        """LMSs run the content in a frame: the API is looked for in the parent frames (SCORM 2004 here)."""
        app = page_factory()
        app.open_menu()
        result = app.page.evaluate(
            """async () => {
                const { findScormApi, ScormSession } = await import("./scorm.js");
                window.API_1484_11 = { Initialize: () => "true" };
                const outer = document.body.appendChild(document.createElement("iframe"));
                const inner = outer.contentDocument.body.appendChild(outer.contentDocument.createElement("iframe"));
                const found = findScormApi(inner.contentWindow);
                const session = new ScormSession(found);
                return [found.version, found.api === window.API_1484_11, session.names.sessionTimeFormat(3725.5)];
            }"""
        )
        assert result == ["2004", True, "PT3725.50S"]


# ── Demo (?demo=1, the Demo tab of the website) ─────────────────────────────


class TestDemo:
    def open_demo(self, app: OpenMATBPage, scenario: str | None = None) -> None:
        app.page.goto(f"{app.url}/index.html?lang=en_EN&demo=1")
        app.page.wait_for_selector("#start:not([disabled])", timeout=180_000)
        if scenario is not None:
            app.write_file("/app/includes/scenarios/demo.txt", scenario)
        app.write_file("/app/_openmatb_probe.py", PROBE.read_text(encoding="utf-8"))
        app.python("import _openmatb_probe")
        app.page.uncheck("#fullscreen")

    def test_nothing_is_recorded(self, page_factory):
        app = page_factory()
        self.open_demo(app, "0:00:00;system;mousecontrol;True\n0:00:00;sysmon;start\n0:00:03;sysmon;stop\n")
        assert not app.page.is_visible("#mode")  # Only the demo scenario
        app.page.click("#start")
        app.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
        app.page.wait_for_function("() => document.querySelector('#end-destinations').textContent !== 'Sending…'")
        assert app.page.text_content("#end-destinations") == "This was a demo: the session was not recorded."
        assert "scenario=demo.txt" in app.page.url
        assert app.downloads == []
        assert app.page.text_content("#back") == "Restart the demo"
        menu = app.new_tab()
        menu.page.goto(f"{menu.url}/index.html?lang=en_EN")
        assert _stored_sessions(menu) == []  # Not kept for replay either

    def test_the_demo_scenario_runs(self, page_factory):
        """The real includes/scenarios/demo.txt: valid, all the tasks started, mouse enabled."""
        app = page_factory()
        self.open_demo(app)
        app.page.click("#start")
        app.wait_until(lambda s: s["started"] and (s["scenario_time"] or 0) >= 2, timeout=60)
        assert app.python("from core.window import Window; Window.MainWindow.mouse_control_active") is True
        running = app.python(
            "import json, _openmatb_probe as p; "
            "json.dumps(sorted(n for n, pl in p.PROBE['scheduler'].plugins.items() if pl.alive))"
        )
        assert {"sysmon", "track", "resman", "communications", "scheduling"} <= set(json.loads(running))
        assert app.errors == []


# ── Replay: page hidden and pauses of the page ──────────────────────────────


PAGE_EVENTS_STATE: str = """
import json, _openmatb_probe as probe
s = probe.PROBE["scheduler"]
json.dumps({
    "hidden_periods": s.logreader.hidden_periods,
    "freezes": s.logreader.freezes,
    "marks": len(s.timeline_marks),
    "notice": s._page_notice_text,
    "notice_visible": s.page_notice.is_visible(),
    "replay_time": s.replay_time,
})
"""


@pytest.fixture(scope="module")
def page_events_replay(page_factory):
    """A session with a pause of the page (400 ms busy loop) and a hidden tab, then its replay."""
    session = page_factory()
    session.start(LONG_SCENARIO.replace("0:05:00", "0:00:12"))
    session.wait_until(lambda s: s["scenario_time"] >= 2, timeout=20)
    session.page.evaluate("() => { const end = performance.now() + 400; while (performance.now() < end) {} }")
    session.wait_until(lambda s: s["scenario_time"] >= 4, timeout=20)
    session.hide_tab()
    session.page.wait_for_timeout(2000)
    session.page.evaluate(
        """() => {
            Object.defineProperty(document, "visibilityState", {value: "visible", configurable: true});
            document.dispatchEvent(new Event("visibilitychange"));
        }"""
    )
    session.page.wait_for_timeout(1000)
    session.page.focus("#pygletCanvas")
    session.page.keyboard.press("Space")  # Close the pause dialog
    session.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
    replay = session.new_tab()
    replay.start_replay(int(session.page.text_content("#end-file").split("_")[0]))
    replay.wait_until(lambda s: s["running"], timeout=20)
    return replay


def _page_events_at(replay: OpenMATBPage, replay_time: float) -> dict:
    replay.python(f"import _openmatb_probe as p; p.PROBE['scheduler'].set_target_time({replay_time})")
    replay.page.wait_for_timeout(300)
    return json.loads(replay.python(PAGE_EVENTS_STATE))


class TestReplayPageEvents:
    def test_hidden_page_and_pause_are_read(self, page_events_replay):
        state = json.loads(page_events_replay.python(PAGE_EVENTS_STATE))
        ((hidden, visible, resumed),) = state["hidden_periods"]
        assert 3.5 < hidden < visible <= resumed
        assert visible - hidden == pytest.approx(2, abs=0.5)
        assert resumed - visible == pytest.approx(1, abs=0.5)  # Until the pause dialog was closed
        assert any(duration >= 0.39 for _start, duration in state["freezes"])  # The 400 ms busy loop
        assert state["marks"] == len(state["hidden_periods"]) + len(state["freezes"])

    def test_notice_while_the_page_was_hidden(self, page_events_replay):
        ((hidden, visible, resumed),) = json.loads(page_events_replay.python(PAGE_EVENTS_STATE))["hidden_periods"]
        assert _page_events_at(page_events_replay, hidden - 0.5)["notice_visible"] is False
        during = _page_events_at(page_events_replay, (hidden + visible) / 2)
        assert during["notice_visible"] and during["notice"].startswith("Page hidden")
        dialog = _page_events_at(page_events_replay, (visible + resumed) / 2)
        assert dialog["notice_visible"] and dialog["notice"].startswith("Session paused")
        assert _page_events_at(page_events_replay, resumed + 0.5)["notice_visible"] is False


# ── Start page: sessions kept in the browser ────────────────────────────────


def _stored_sessions(app: OpenMATBPage) -> list[str]:
    app.page.wait_for_function("() => window.openmatb !== undefined", timeout=180_000)
    app.page.select_option("#mode", "replay")
    app.page.wait_for_timeout(500)
    return app.page.eval_on_selector_all("#sessions-list .session-name", "items => items.map(i => i.firstChild.data)")


class TestStoredSessions:
    def test_download_again_and_delete(self, page_factory):
        session = page_factory()
        session.start(OUTPUT_SCENARIO)
        session.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
        name = session.page.text_content("#end-file")
        content = session.downloads[0].path().read_text(encoding="utf-8")

        menu = session.new_tab()
        menu.page.goto(f"{menu.url}/index.html?lang=en_EN")
        assert _stored_sessions(menu) == [name]
        assert menu.page.is_visible("#delete-all")

        with menu.page.expect_download() as download:
            menu.page.click("#sessions-list button[aria-label='Download']")
        assert download.value.suggested_filename == name
        assert download.value.path().read_text(encoding="utf-8") == content

        menu.page.once("dialog", lambda dialog: dialog.accept())
        menu.page.click("#sessions-list button[aria-label='Delete']")
        menu.page.wait_for_selector("#sessions-empty:not([hidden])", timeout=10_000)
        assert _stored_sessions(menu) == []

        menu.page.reload()  # Deleted from the browser storage too
        assert _stored_sessions(menu) == []
        assert not menu.page.is_visible("#delete-all")

    def test_delete_cancelled(self, page_factory):
        session = page_factory()
        session.start(OUTPUT_SCENARIO)
        session.page.wait_for_selector("#end:not([hidden])", timeout=40_000)
        menu = session.new_tab()
        menu.page.goto(f"{menu.url}/index.html?lang=en_EN")
        assert len(_stored_sessions(menu)) == 1
        menu.page.once("dialog", lambda dialog: dialog.dismiss())
        menu.page.click("#sessions-list button[aria-label='Delete']")
        menu.page.wait_for_timeout(500)
        assert len(_stored_sessions(menu)) == 1

    def test_import_compressed_session(self, page_factory):
        """A session file sent to JATOS (.csv.gz) is imported decompressed."""
        content = "logtime,scenario_time,type,module,address,value\n0.1,0,event,sysmon,self,start\n"
        app = page_factory()
        app.open_menu()
        app.page.select_option("#mode", "replay")
        app.page.uncheck("#fullscreen")
        compressed = {
            "name": "9_260901_100000.csv.gz",
            "mimeType": "application/gzip",
            "buffer": gzip.compress(content.encode()),
        }
        app.page.set_input_files("#session-file", files=[compressed])
        app.page.click("#start")
        path = "/data/openmatb/sessions/imported/9_260901_100000.csv"
        app.page.wait_for_function(
            "(path) => window.openmatb.pyodide.FS.analyzePath(path).exists", arg=path, timeout=30_000
        )
        assert (
            app.page.evaluate("(path) => window.openmatb.pyodide.FS.readFile(path, {encoding: 'utf8'})", path)
            == content
        )

    def test_delete_all(self, page_factory):
        menu = page_factory()
        menu.open_menu()
        for name in ("2026-09-20/1_260920_100000.csv", "2026-09-21/2_260921_100000.csv", "imported/7_260901_1.csv"):
            folder = "/data/openmatb/sessions/" + name.rsplit("/", 1)[0]
            menu.page.evaluate(f"() => window.openmatb.pyodide.FS.mkdirTree('{folder}')")
            menu.write_file(f"/data/openmatb/sessions/{name}", "logtime,scenario_time,type,module,address,value\n")
        assert len(_stored_sessions(menu)) == 3
        menu.page.once("dialog", lambda dialog: dialog.accept())
        menu.page.click("#delete-all")
        menu.page.wait_for_selector("#sessions-empty:not([hidden])", timeout=10_000)
        assert _stored_sessions(menu) == []
