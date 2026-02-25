# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from pyglet.shapes import Circle, Line, Rectangle
from pyglet.text import Label

from core.constants import Group as G
from core.container import Container

# Colors for sparklines
COLOR_TRACK: tuple[int, int, int] = (100, 180, 255)
COLOR_RESMAN_A: tuple[int, int, int] = (255, 180, 50)
COLOR_RESMAN_B: tuple[int, int, int] = (80, 200, 220)
COLOR_HIT: tuple[int, int, int] = (40, 200, 40)
COLOR_MISS: tuple[int, int, int] = (200, 40, 40)
COLOR_FA: tuple[int, int, int] = (220, 200, 40)

# Task display order and labels
TASK_ORDER: list[str] = ["track", "resman", "sysmon", "communications"]
TASK_LABELS: dict[str, str] = {
    "track": "TRACK",
    "resman": "RESMAN",
    "sysmon": "SYSMON",
    "communications": "COMMS",
}


def downsample(points: list[tuple[float, float]], max_points: int) -> list[tuple[float, float]]:
    """Downsample a list of (x, y) points by taking every Nth point."""
    if len(points) <= max_points:
        return points
    step: int = -(-len(points) // max_points)  # ceil division
    result: list[tuple[float, float]] = points[::step]
    if result[-1] != points[-1]:
        result.append(points[-1])
    return result


def normalize(values: list[float], y_bottom: float, y_top: float) -> list[float]:
    """Normalize values to fit within [y_bottom, y_top]."""
    if not values:
        return []
    min_val: float = min(values)
    max_val: float = max(values)
    span: float = max_val - min_val
    if span == 0:
        mid: float = (y_bottom + y_top) / 2
        return [mid] * len(values)
    height: float = y_top - y_bottom
    return [y_bottom + ((v - min_val) / span) * height for v in values]


class PerfOverlay:
    MAX_POINTS: int = 600

    def __init__(self, container: Container, batch: Any,
                 perf_series: dict[str, list[tuple[float, dict[str, str]]]],
                 duration_sec: float) -> None:
        self._container: Container = container
        self._batch: Any = batch
        self._duration: float = max(duration_sec, 0.001)
        self._shapes: list[Any] = []
        self._labels: list[Any] = []

        l, b, w, h = container.get_lbwh()
        self._label_width: float = 70.0
        self._sparkline_width: float = w - self._label_width
        self._x_min: float = l + self._label_width
        self._x_max: float = l + w
        self._y_bottom: float = b
        self._y_top: float = b + h

        # Determine which tasks have data
        active_tasks: list[str] = [t for t in TASK_ORDER if t in perf_series and len(perf_series[t]) > 0]
        if not active_tasks:
            self._cursor = None
            return

        # Background rectangle
        bg = Rectangle(x=l, y=b, width=w, height=h,
                        color=(30, 30, 40), batch=batch, group=G(96))
        bg.opacity = 230
        self._shapes.append(bg)

        # Divide height among active tasks
        n_tasks: int = len(active_tasks)
        row_height: float = h / n_tasks

        for i, task_name in enumerate(active_tasks):
            row_bottom: float = b + (n_tasks - 1 - i) * row_height
            row_top: float = row_bottom + row_height
            row_mid: float = (row_bottom + row_top) / 2

            # Task label
            label = Label(
                TASK_LABELS.get(task_name, task_name.upper()),
                x=l + 4, y=row_mid,
                font_size=9, color=(200, 200, 200, 255),
                anchor_y="center",
                batch=batch, group=G(98),
            )
            self._labels.append(label)

            # Separator line between rows (except at the bottom)
            if i < n_tasks - 1:
                sep = Line(l, row_bottom, l + w, row_bottom,
                           thickness=1, color=(80, 80, 80), batch=batch, group=G(97))
                sep.opacity = 150
                self._shapes.append(sep)

            # Draw the sparkline/markers for this task
            series: list[tuple[float, dict[str, str]]] = perf_series[task_name]
            margin: float = 3.0  # vertical margin inside each row

            if task_name == "track":
                self._draw_continuous_sparkline(
                    series, "center_deviation", COLOR_TRACK,
                    row_bottom + margin, row_top - margin,
                )
            elif task_name == "resman":
                # Two sub-lines: A in upper half, B in lower half
                sub_mid: float = (row_bottom + row_top) / 2
                self._draw_continuous_sparkline(
                    series, "a_deviation", COLOR_RESMAN_A,
                    sub_mid + margin / 2, row_top - margin,
                )
                self._draw_continuous_sparkline(
                    series, "b_deviation", COLOR_RESMAN_B,
                    row_bottom + margin, sub_mid - margin / 2,
                )
            elif task_name in ("sysmon", "communications"):
                sdt_key: str = "signal_detection" if task_name == "sysmon" else "sdt_value"
                self._draw_event_markers(
                    series, sdt_key, row_mid, margin,
                )

        # Cursor line
        self._cursor = Line(
            self._x_min, self._y_bottom, self._x_min, self._y_top,
            thickness=2, color=(255, 255, 255), batch=batch, group=G(99),
        )
        self._cursor.opacity = 200
        self._shapes.append(self._cursor)

    def _time_to_x(self, t: float) -> float:
        return self._x_min + (t / self._duration) * self._sparkline_width

    def _draw_continuous_sparkline(
        self,
        series: list[tuple[float, dict[str, str]]],
        address: str,
        color: tuple[int, int, int],
        y_bottom: float,
        y_top: float,
    ) -> None:
        # Extract (time, value) pairs
        raw_points: list[tuple[float, float]] = []
        for t, data in series:
            if address in data:
                try:
                    val: float = float(data[address])
                except (ValueError, TypeError):
                    continue
                raw_points.append((t, val))

        if len(raw_points) < 2:
            return

        # Downsample
        points: list[tuple[float, float]] = downsample(raw_points, self.MAX_POINTS)

        # Map X coordinates
        xs: list[float] = [self._time_to_x(t) for t, _ in points]

        # Normalize Y coordinates
        ys: list[float] = normalize([v for _, v in points], y_bottom, y_top)

        # Create line segments
        for j in range(len(xs) - 1):
            line = Line(xs[j], ys[j], xs[j + 1], ys[j + 1],
                        thickness=1, color=color, batch=self._batch, group=G(98))
            self._shapes.append(line)

    def _draw_event_markers(
        self,
        series: list[tuple[float, dict[str, str]]],
        sdt_key: str,
        y_mid: float,
        margin: float,
    ) -> None:
        color_map: dict[str, tuple[int, int, int]] = {
            "HIT": COLOR_HIT,
            "MISS": COLOR_MISS,
            "FA": COLOR_FA,
        }

        for t, data in series:
            if sdt_key not in data:
                continue
            sdt_val: str = data[sdt_key]
            if sdt_val not in color_map:
                continue

            x: float = self._time_to_x(t)
            circle = Circle(x=x, y=y_mid, radius=4,
                            color=color_map[sdt_val], batch=self._batch, group=G(98))
            self._shapes.append(circle)

    def update_cursor(self, scenario_time: float) -> None:
        if self._cursor is None:
            return
        x: float = self._time_to_x(scenario_time)
        x = max(self._x_min, min(self._x_max, x))
        self._cursor.x = x
        self._cursor.x2 = x

    def destroy(self) -> None:
        for shape in self._shapes:
            shape.delete()
        self._shapes.clear()
        for label in self._labels:
            label.batch = None
        self._labels.clear()
        self._cursor = None
