# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Response times measured as in experiment libraries (PsychoJS, lab.js).

The scenario time only advances at each clock tick (about 10-30 ms in the browser): a response time computed as the
difference of two scenario times is rounded to the tick at both ends. Here the two ends are measured instead:
- the stimulus onset is the first frame drawing it (flip()), like PsychoJS's callOnFlip,
- the response is the time of its input event: in the browser, the event.timeStamp given by the browser when the
  key or button was pressed (like lab.js), before the page could process it; on desktop, the time it is handled.
Both are converted to scenario time: the scenario time of the last tick plus the real time elapsed since it while
the scenario runs, so that pauses stay excluded as with the scenario time.
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable

from core.platform import IS_WEB

# An event timestamp older than this (seconds) is not the one being handled
MAX_INPUT_EVENT_AGE: float = 1.0
INPUT_EVENTS: tuple[str, ...] = ("keydown", "keyup", "mousedown", "mouseup", "pointerdown", "pointerup")

_tick_real: float | None = None  # perf_counter() of the last tick
_tick_scenario: float = 0.0  # Scenario time at the last tick
_previous_tick_scenario: float = 0.0
_running: bool = False  # The scenario time advances
_flip_callbacks: list[Callable[[float], None]] = []


def reset() -> None:
    global _tick_real, _tick_scenario, _previous_tick_scenario, _running
    _tick_real, _tick_scenario, _previous_tick_scenario, _running = None, 0.0, 0.0, False
    _flip_callbacks.clear()


def set_tick(scenario_time: float, running: bool) -> None:
    """Called by the scheduler at each tick, with the scenario time and whether it advances (not paused)."""
    global _tick_real, _tick_scenario, _previous_tick_scenario, _running
    _previous_tick_scenario = _tick_scenario
    _tick_real, _tick_scenario, _running = perf_counter(), scenario_time, running


def scenario_time_at(real_time: float) -> float | None:
    """Scenario time at real_time (a perf_counter() time), or None without scheduler (tests, replay)."""
    if _tick_real is None:
        return None
    if not _running:
        return _tick_scenario
    # An event can precede the tick that handles it, not the previous one
    return max(_previous_tick_scenario, _tick_scenario + real_time - _tick_real)


def input_time() -> float:
    """perf_counter() time of the input being handled: the timestamp of the browser event, else now."""
    now: float = perf_counter()
    if not IS_WEB:
        return now
    import js

    # pyglet handles keys and clicks during the dispatch of their DOM event (window.event)
    event = getattr(js.window, "event", None)
    if event is None or getattr(event, "type", None) not in INPUT_EVENTS:
        return now
    stamp: float = float(event.timeStamp) / 1000  # performance.now() time, like perf_counter()
    return stamp if 0 <= now - stamp < MAX_INPUT_EVENT_AGE else now


def call_on_flip(callback: Callable[[float], None]) -> None:
    """Call callback(perf_counter time) when the next frame is drawn."""
    _flip_callbacks.append(callback)


def flip() -> None:
    """Called by the window when it draws a frame."""
    if not _flip_callbacks:
        return
    now: float = perf_counter()
    callbacks: list[Callable[[float], None]] = list(_flip_callbacks)
    _flip_callbacks.clear()
    for callback in callbacks:
        callback(now)
