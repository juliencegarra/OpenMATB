"""Replay of a web session: fidelity (the replay gives the same results as the session) and robustness (playback,
seeking and speed changes do not stop it).

One session is recorded with what a real session has: a questionnaire answered with the mouse, system monitoring
responses (hits and a false alarm), a resources management pump, the page hidden (then the pause dialog), and
instructions of three pages. It is then replayed in another tab of the same browser (the sessions are kept in the
browser storage). Run with: OPENMATB_BROWSER_TESTS=1 python -m pytest tests/web/test_replay.py -v
"""

from __future__ import annotations

import csv
import io
import json
import time
from typing import Any, Callable

import pytest

from tests.web.conftest import OpenMATBPage

SCENARIO: str = (
    "0:00:00;genericscales;filename;nasatlx_en.txt\n0:00:00;genericscales;start\n"
    "0:00:00;sysmon;start\n0:00:00;resman;start\n0:00:00;track;start\n"
    "0:00:02;sysmon;scales-1-failure;True\n"
    "0:00:04;sysmon;lights-1-failure;True\n"
    "0:00:07;instructions;filename;instructions_example_en.txt\n0:00:07;instructions;start\n"
    "0:00:11;sysmon;stop\n0:00:11;resman;stop\n0:00:11;track;stop\n"
)

SESSION_STATE: str = """
import json, _openmatb_probe as probe
from core.window import Window
s = probe.PROBE["scheduler"]
json.dumps({"st": s.scenario_time, "alive": sorted(n for n, p in s.plugins.items() if p.alive),
            "modal": Window.MainWindow.modal_dialog is not None,
            "pump_1": s.plugins["resman"].parameters["pump"]["1"]["state"]})
"""

REPLAY_STATE: str = """
import json, pyglet.app, _openmatb_probe as probe
s = probe.PROBE["scheduler"]
perf = lambda alias: getattr(s.plugins[alias], "performance", {}) if alias in s.plugins else {}
json.dumps({
    "running": bool(pyglet.app.event_loop.is_running),
    "paused": s.is_paused,
    "replay_time": s.replay_time,
    "scenario_time": s.scenario_time,
    "duration": s.logreader.session_duration,
    "alive": sorted(n for n, p in s.plugins.items() if p.alive),
    "sysmon_detections": perf("sysmon").get("signal_detection", []),
    "questionnaire": {k: v for k, v in perf("genericscales").items() if k != "presentation_number"},
    "pump_1": s.plugins["resman"].parameters["pump"]["1"]["state"],
    "notice": s._page_notice_text,
    "hidden_periods": s.logreader.hidden_periods,
    "blocking_segments": s.logreader.blocking_segments,
    "events_done": sum(1 for e in s.events if e.done),
    "events": len(s.events),
})
"""


def _wait(check: Callable[[], dict], predicate: Callable[[dict], bool], timeout: float, what: str) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        state = check()
        if predicate(state):
            return state
        if time.monotonic() > deadline:
            raise AssertionError(f"Timeout waiting for {what}; last state: {state}")
        time.sleep(0.1)


def _show_tab(app: OpenMATBPage) -> None:
    app.page.evaluate(
        """() => {
            Object.defineProperty(document, "visibilityState", {value: "visible", configurable: true});
            document.dispatchEvent(new Event("visibilitychange"));
        }"""
    )


@pytest.fixture(scope="module")
def recorded(page_factory) -> dict[str, Any]:
    """The session: its rows, its id, and what it gave (read in the page)."""
    session = page_factory()
    session.start(SCENARIO)
    state = lambda: json.loads(session.python(SESSION_STATE))  # noqa: E731
    page = session.page
    page.wait_for_timeout(2000)

    # The questionnaire (fullscreen, the scenario is paused): move a slider with the mouse, validate with SPACE
    box = page.locator("#pygletCanvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.25)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.25, steps=8)
    page.mouse.up()
    page.wait_for_timeout(500)
    page.focus("#pygletCanvas")
    page.keyboard.press("Space")

    for at, key in [(2.4, "F1"), (3.0, "F3"), (4.4, "F5"), (5.0, "Numpad1")]:  # Hit, false alarm, hit, pump
        _wait(state, lambda s, at=at: s["st"] >= at, 20, f"scenario time {at}")
        page.keyboard.press(key)

    # The page is hidden for 1.5 s: the scenario is paused, then the pause dialog is closed with SPACE
    _wait(state, lambda s: s["st"] >= 5.5, 20, "scenario time 5.5")
    session.hide_tab()
    page.wait_for_timeout(1500)
    _show_tab(session)
    page.wait_for_timeout(300)
    assert state()["modal"]
    page.keyboard.press("Space")

    # The instructions (three pages): SPACE until they close
    _wait(state, lambda s: "instructions" in s["alive"], 20, "the instructions")
    for _ in range(6):
        page.wait_for_timeout(800)
        if "instructions" not in state()["alive"]:
            break
        page.keyboard.press("Space")
    pump_1 = _wait(state, lambda s: s["st"] >= 10.5, 20, "scenario time 10.5")["pump_1"]

    page.wait_for_selector("#end:not([hidden])", timeout=30_000)
    rows = list(csv.DictReader(io.StringIO(session.downloads[0].path().read_text(encoding="utf-8"))))
    perf = [r for r in rows if r["type"] == "performance"]
    return {
        "app": session,
        "id": int(session.downloads[0].suggested_filename.split("_")[0]),
        "rows": rows,
        "sysmon_detections": [
            r["value"] for r in perf if r["module"] == "sysmon" and r["address"] == "signal_detection"
        ],
        "questionnaire": {
            r["address"]: r["value"]
            for r in perf
            if r["module"] == "genericscales" and r["address"] != "presentation_number"
        },
        "pump_1": pump_1,
    }


@pytest.fixture(scope="module")
def replayed(recorded) -> dict[str, Any]:
    """The replay played once from its start to its end, in real time, with its states along the way."""
    replay = recorded["app"].new_tab()
    replay.start_replay(recorded["id"])
    state = lambda: json.loads(replay.python(REPLAY_STATE))  # noqa: E731
    _wait(state, lambda s: s["running"], 20, "the replay loop")
    replay.page.focus("#pygletCanvas")
    replay.page.keyboard.press("Space")  # Play
    states: list[dict] = []
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        current = state()
        states.append(current)
        if not current["running"] or (current["paused"] and current["replay_time"] >= current["duration"] - 0.05):
            break
        time.sleep(0.2)
    return {"app": replay, "state": state, "states": states, "end": states[-1]}


class TestReplayPlayback:
    def test_the_session_is_complete(self, recorded):
        assert recorded["sysmon_detections"] == ["HIT", "FA", "HIT"]
        assert recorded["pump_1"] == "on"
        assert recorded["questionnaire"]  # The answers are logged
        assert any(r["type"] == "visibility" for r in recorded["rows"])

    def test_plays_to_the_end_without_stopping(self, replayed):
        assert all(s["running"] for s in replayed["states"]), replayed["app"].console
        end = replayed["end"]
        assert end["replay_time"] == pytest.approx(end["duration"], abs=0.05)
        assert end["events_done"] == end["events"]
        assert end["alive"] == []

    def test_follows_the_session_time(self, replayed):
        """Played in real time: the replay time advances like the clock (no freeze, no double speed)."""
        states = replayed["states"]
        assert len(states) > 10
        # Between two polls (0.2 s + the time of the poll), the replay time never stays still while playing
        stills = [
            a
            for a, b in zip(states, states[1:])
            if not a["paused"] and not b["paused"] and b["replay_time"] == a["replay_time"]
        ]
        assert stills == []

    def test_the_questionnaire_is_shown_during_its_segment(self, replayed):
        segments = replayed["end"]["blocking_segments"]
        assert segments  # The questionnaire and the instructions stopped the scenario time
        # Inside the segment (its ends are those of logged rows, a replay update away from the plugin start/stop)
        during = [s for s in replayed["states"] if segments[0][0] + 0.2 < s["replay_time"] < segments[0][1] - 0.2]
        assert during and all("genericscales" in s["alive"] for s in during)

    def test_the_hidden_page_is_shown(self, replayed):
        hidden = replayed["end"]["hidden_periods"]
        assert len(hidden) == 1
        start, end = hidden[0][0], hidden[0][1]
        during = [s for s in replayed["states"] if start + 0.1 < s["replay_time"] < end - 0.1]
        assert during and all(s["notice"] for s in during)


class TestReplayFidelity:
    """The replay replays the inputs of the session: its tasks must give the same results."""

    def test_same_system_monitoring_responses(self, recorded, replayed):
        assert replayed["end"]["sysmon_detections"] == recorded["sysmon_detections"]

    def test_same_questionnaire_answers(self, recorded, replayed):
        answers = {k: float(v[-1]) for k, v in replayed["end"]["questionnaire"].items()}
        logged = {k: float(v) for k, v in recorded["questionnaire"].items()}  # Logged with 6 decimals
        assert answers == pytest.approx(logged, abs=1e-6)

    def test_same_pump_state(self, recorded, replayed):
        assert replayed["end"]["pump_1"] == recorded["pump_1"]


class TestReplaySeeking:
    def test_back_to_the_start_then_to_the_end(self, replayed):
        """Home restarts the replay (the plugins are reloaded), End jumps to the end: all the events are done."""
        replay, state = replayed["app"], replayed["state"]
        replay.page.focus("#pygletCanvas")
        replay.page.keyboard.press("Home")
        _wait(state, lambda s: s["replay_time"] < 0.5, 10, "the start")
        replay.page.keyboard.press("End")
        end = _wait(state, lambda s: s["replay_time"] >= s["duration"] - 0.05, 20, "the end")
        assert end["running"]
        assert end["events_done"] == end["events"]
        assert end["alive"] == []

    def test_seek_into_the_questionnaire_then_play(self, replayed):
        """A jump into the questionnaire shows it; playing goes on to the end."""
        replay, state = replayed["app"], replayed["state"]
        start, end = replayed["end"]["blocking_segments"][0][:2]
        replay.python(
            f"import _openmatb_probe as probe\nprobe.PROBE['scheduler'].set_target_time({(start + end) / 2})\n"
        )
        inside = _wait(state, lambda s: s["paused"], 10, "the seek")
        assert "genericscales" in inside["alive"]
        replay.page.focus("#pygletCanvas")
        replay.page.keyboard.press("Space")  # Play
        final = _wait(state, lambda s: s["paused"] and s["replay_time"] >= s["duration"] - 0.05, 60, "the end")
        assert final["running"]
        assert final["alive"] == []

    def test_seek_after_the_questionnaire_stops_it(self, replayed):
        """A jump past the questionnaire (from before it) stops it and resumes the tasks."""
        replay, state = replayed["app"], replayed["state"]
        end = replayed["end"]["blocking_segments"][0][1]
        replay.python("import _openmatb_probe as probe\nprobe.PROBE['scheduler'].set_target_time(0)\n")
        _wait(state, lambda s: s["replay_time"] < 0.5, 10, "the start")
        replay.python(f"import _openmatb_probe as probe\nprobe.PROBE['scheduler'].set_target_time({end + 1})\n")
        after = _wait(state, lambda s: s["paused"] and s["replay_time"] >= end + 0.9, 20, "the seek")
        assert after["running"]
        assert "genericscales" not in after["alive"]
        assert {"sysmon", "resman", "track"} <= set(after["alive"])


class TestReplaySpeed:
    def test_faster_playback_reaches_the_end_sooner(self, replayed):
        """UP speeds the replay up: from the start, the whole session is played in less than its duration."""
        replay, state = replayed["app"], replayed["state"]
        replay.page.focus("#pygletCanvas")
        replay.page.keyboard.press("Home")
        _wait(state, lambda s: s["replay_time"] < 0.5, 10, "the start")
        for _ in range(3):
            replay.page.keyboard.press("ArrowUp")
        duration = state()["duration"]
        started = time.monotonic()
        replay.page.keyboard.press("Space")  # Play
        end = _wait(state, lambda s: s["paused"] and s["replay_time"] >= s["duration"] - 0.05, 60, "the end")
        assert time.monotonic() - started < duration * 0.6
        assert end["running"]
        not_done = replay.python(
            "import json, _openmatb_probe as probe; "
            "json.dumps([[e.time_sec, e.plugin, e.get_command_str()] for e in probe.PROBE['scheduler'].events if not e.done])"
        )
        assert end["events_done"] == end["events"], not_done
