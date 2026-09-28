# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Run OpenMATB in a real desktop window with the installed pyglet, for tests/test_desktop_smoke.py.

    python tests/desktop/smoke.py OUT_DIR SCENARIO_PATH   run a scenario
    python tests/desktop/smoke.py OUT_DIR -r SESSION_ID   replay a session of OUT_DIR/sessions (for REPLAY_DURATION)

The session files are in OUT_DIR/sessions. The dialogs are answered with Space, sysmon failures with their key
(RESPONSE_DELAY after they appear). At SCREENSHOT_AT seconds, the window is captured to OUT_DIR/screenshot_run.png
(or _replay). OUT_DIR/result_run.json (or _replay) gives the pyglet version, the last session file, the number of
colors of the screenshot and the keys answered.
"""

from __future__ import annotations

import gettext
import json
import os
import runpy
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
SCREENSHOT_AT: float = 8.0
REPLAY_DURATION: float = 10.0
RESPONSE_DELAY: float = 1.0

out: Path = Path(sys.argv[1]).resolve()
replay: bool = sys.argv[2] == "-r"
name: str = "replay" if replay else "run"
sys.argv = ["main.py", *sys.argv[2:]]  # Read by core.constants when imported
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pyglet  # noqa: E402

# main.py installs the translation before importing core modules: do the same to import them first
gettext.translation("openmatb", "locales", ["en_EN"], fallback=True).install()

import core.scheduler  # noqa: E402
from core import pyglet_compat  # noqa: E402
from core.constants import CONFIG, PATHS  # noqa: E402

CONFIG["Openmatb"]["display_session_number"] = "False"
CONFIG["Openmatb"]["fullscreen"] = "False"
PATHS["SESSIONS"] = out / "sessions"
result: dict = {"pyglet": pyglet.version, "screenshot_colors": 0, "answered": []}
schedulers: list = []
_scheduler_init = core.scheduler.Scheduler.__init__


def scheduler_init(self, *args, **kwargs) -> None:
    schedulers.append(self)
    _scheduler_init(self, *args, **kwargs)


core.scheduler.Scheduler.__init__ = scheduler_init


def window():
    from core.window import Window

    return Window.MainWindow


def press(symbol: int) -> None:
    window().dispatch_event("on_key_press", symbol, 0)
    window().dispatch_event("on_key_release", symbol, 0)


def answer_dialogs(dt: float) -> None:
    if window() is not None and window().modal_dialog is not None:
        press(pyglet.window.key.SPACE)


seen: dict[str, float] = {}


def answer_failures(dt: float) -> None:
    scheduler = schedulers[-1] if schedulers else None
    sysmon = scheduler.plugins.get("sysmon") if scheduler is not None else None
    if sysmon is None or not sysmon.alive:
        return
    for gauge in sysmon.get_gauges_on_failure():
        seen.setdefault(gauge["key"], scheduler.scenario_time)
        if scheduler.scenario_time - seen[gauge["key"]] >= RESPONSE_DELAY:
            press(getattr(pyglet.window.key, gauge["key"]))
            result["answered"].append(gauge["key"])
            del seen[gauge["key"]]


def screenshot(dt: float) -> None:
    image = pyglet_compat.get_screenshot().get_image_data()
    image.save(str(out / f"screenshot_{name}.png"))
    get_bytes = image.get_bytes if pyglet_compat.PYGLET_3 else image.get_data
    data: bytes = get_bytes("RGB", image.width * 3)
    result["screenshot_colors"] = len({data[i : i + 3] for i in range(0, len(data), 3 * 7)})


pyglet.clock.schedule_interval(answer_dialogs, 0.25)
pyglet.clock.schedule_once(screenshot, SCREENSHOT_AT)
if replay:
    pyglet.clock.schedule_once(lambda dt: press(pyglet.window.key.SPACE), 1.0)  # Play
    pyglet.clock.schedule_once(lambda dt: pyglet.app.exit(), REPLAY_DURATION)
else:
    pyglet.clock.schedule_interval(answer_failures, 0.1)

runpy.run_path(str(ROOT / "main.py"), run_name="__main__")

sessions: list[Path] = sorted((out / "sessions").glob("**/*.csv"))
result["session"] = str(sessions[-1]) if sessions else None
(out / f"result_{name}.json").write_text(json.dumps(result), encoding="utf-8")
