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

from collections import Counter
from math import sqrt
from time import perf_counter
from typing import Callable

from core.platform import IS_WEB

# An event timestamp older than this (seconds) is not the one being handled
MAX_INPUT_EVENT_AGE: float = 1.0
INPUT_EVENTS: tuple[str, ...] = ("keydown", "keyup", "mousedown", "mouseup", "pointerdown", "pointerup")
FRAME_BINS_PER_MS: int = 100  # The intervals between frames are counted by steps of 0.01 ms
LATE_FRAME_RATIO: float = 1.5  # A frame later than this times the median interval missed at least one refresh

_tick_real: float | None = None  # perf_counter() of the last tick
_tick_scenario: float = 0.0  # Scenario time at the last tick
_previous_tick_scenario: float = 0.0
_running: bool = False  # The scenario time advances
_flip_callbacks: list[Callable[[float], None]] = []
_last_flip: float | None = None
# Counted rather than kept: a session draws hundreds of thousands of frames
_frame_intervals: Counter[int] = Counter()


def reset() -> None:
    global _tick_real, _tick_scenario, _previous_tick_scenario, _running, _last_flip
    _tick_real, _tick_scenario, _previous_tick_scenario, _running = None, 0.0, 0.0, False
    _flip_callbacks.clear()
    _last_flip = None
    _frame_intervals.clear()


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
    global _last_flip
    now: float = perf_counter()
    if _last_flip is not None:
        _frame_intervals[round((now - _last_flip) * 1000 * FRAME_BINS_PER_MS)] += 1
    _last_flip = now
    if not _flip_callbacks:
        return
    callbacks: list[Callable[[float], None]] = list(_flip_callbacks)
    _flip_callbacks.clear()
    for callback in callbacks:
        callback(now)


def frame_statistics() -> list[tuple[str, str]]:
    """(key, value) entries on the regularity of the frames since the start of the scenario, for the session file.
    What is really displayed: the rate of the screen and the vertical sync are only the settings asked for."""
    count: int = sum(_frame_intervals.values())
    if count == 0:
        return []
    bins: list[int] = sorted(_frame_intervals)
    cumulated: int = 0
    median: int = bins[-1]
    for interval in bins:
        cumulated += _frame_intervals[interval]
        if cumulated * 2 >= count:
            median = interval
            break
    # The deviation of the frames on time: a single long pause (a dialog, a file loaded) would make it meaningless.
    # The others are given by frames_late and frame_max_ms
    on_time: list[int] = [interval for interval in bins if interval <= LATE_FRAME_RATIO * median]
    on_time_count: int = sum(_frame_intervals[interval] for interval in on_time)
    mean: float = sum(interval * _frame_intervals[interval] for interval in on_time) / on_time_count
    variance: float = sum(_frame_intervals[interval] * (interval - mean) ** 2 for interval in on_time) / on_time_count
    late: int = count - on_time_count
    return [
        ("frames", str(count)),
        ("frame_median_ms", f"{median / FRAME_BINS_PER_MS:.2f}"),
        ("frame_sd_ms", f"{sqrt(variance) / FRAME_BINS_PER_MS:.2f}"),
        ("frame_max_ms", f"{bins[-1] / FRAME_BINS_PER_MS:.2f}"),
        ("frames_late", str(late)),
    ]
