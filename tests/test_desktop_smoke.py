"""OpenMATB in a real desktop window, with the installed pyglet (pyglet 2 on desktop, see core/pyglet_compat.py).

Skipped unless OPENMATB_DESKTOP_TESTS=1: it opens a window for about 30 s (a display is needed).
A scenario with the five tasks is run (tests/desktop/smoke.py answers the dialogs and the sysmon failures), then
its session is replayed. Run with -s to see the pyglet version and where the screenshots are.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT: Path = Path(__file__).resolve().parents[1]
RUNNER: Path = ROOT / "tests" / "desktop" / "smoke.py"

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENMATB_DESKTOP_TESTS") != "1", reason="desktop window tests: set OPENMATB_DESKTOP_TESTS=1"
)

SCENARIO: str = """0:00:00;resman;start
0:00:00;track;start
0:00:00;sysmon;start
0:00:00;scheduling;start
0:00:00;communications;start
0:00:02;communications;radioprompt;own
0:00:03;sysmon;scales-1-failure;True
0:00:04;sysmon;lights-1-failure;True
0:00:05;resman;pump-1-state;failure
0:00:12;resman;pump-1-state;off
0:00:14;sysmon;stop
0:00:14;resman;stop
0:00:14;track;stop
0:00:14;scheduling;stop
0:00:14;communications;stop
"""


def _run(out: Path, *args: str) -> dict:
    process = subprocess.run(
        [sys.executable, str(RUNNER), str(out), *args], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    # pyglet 2 prints "Exception ignored" errors of its weak references when Python exits: only those are allowed
    assert process.returncode == 0, process.stderr
    assert process.stderr.count("Traceback") == process.stderr.count("Exception ignored"), process.stderr
    name = "replay" if args[0] == "-r" else "run"
    result: dict = json.loads((out / f"result_{name}.json").read_text(encoding="utf-8"))
    print(f"\npyglet {result['pyglet']}, {name}: {out / f'screenshot_{name}.png'}")
    return result


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> tuple[Path, dict]:
    out: Path = tmp_path_factory.mktemp("desktop")
    scenario: Path = out / "smoke.txt"
    scenario.write_text(SCENARIO, encoding="utf-8")
    return out, _run(out, str(scenario))


class TestDesktopSmoke:
    def test_scenario_runs_to_its_end(self, run):
        _out, result = run
        assert result["answered"] == ["F1", "F5"]
        assert result["screenshot_colors"] > 50  # The tasks are drawn

    def test_responses_are_in_the_session_file(self, run):
        _out, result = run
        rows = list(csv.DictReader(open(result["session"], encoding="utf-8")))
        sysmon = [r for r in rows if r["type"] == "performance" and r["module"] == "sysmon"]
        assert [r["value"] for r in sysmon if r["address"] == "signal_detection"] == ["HIT", "HIT"]
        response_times = [float(r["value"]) for r in sysmon if r["address"] == "response_time"]
        assert all(1000 <= rt < 1500 for rt in response_times), response_times  # Answered 1 s after the failure
        assert any(r["module"] == "resman" and r["type"] == "performance" for r in rows)

    def test_session_is_replayed(self, run):
        out, _result = run
        result = _run(out, "-r", "1")
        assert result["screenshot_colors"] > 50
