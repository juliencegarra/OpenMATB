# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any

from pyglet.math import Vec2
from pyglet.shapes import Arc, Circle, Line

from core.constants import COLORS as C
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


class Reticle(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        cursorcolor: tuple[int, ...],
        target_proportion: float = 0.1,
        m_draw: int | None = None,
    ) -> None:
        super().__init__(name, container)

        if m_draw is not None:
            self.m_draw = m_draw

        # Set cursor variables
        self.cursor_relative: list[float] | tuple[float, float] = (0, 0)
        self.cursor_proportional: tuple[float, ...] = self.relative_to_proportional()
        self.cursor_radius: float = self.container.w / 2 * 0.08
        self.cursor_absolute: tuple[float, ...] = self.relative_to_absolute()

        # Set widths
        self.corner_width: float = 0.07 * self.container.w
        self.graduation_width: float = 0.023 * self.container.w

        # Build axis lines using rotate_vertice_list (produces flat coordinate lists)
        cx, cy = self.container.get_center()
        _x1, _y1, x2, y2 = self.container.get_x1y1x2y2()
        v1: list[float] = [cx, cy, x2, cy, x2, y2, x2 - self.corner_width, y2, x2, y2, x2, y2 + self.corner_width]
        gw: float = self.graduation_width
        for i in range(5):
            v1.extend(
                [
                    cx + ((x2 - cx) / 4) * i,
                    cy - (gw + gw * ((i + 1) % 2)),
                    cx + ((x2 - cx) / 4) * i,
                    cy + (gw + gw * ((i + 1) % 2)),
                ]
            )

        v2: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi / 2)
        v3: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi)
        v4: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi + math.pi / 2)
        all_v: list[float] = v1 + v2 + v3 + v4

        # Convert flat vertex pairs into Line shapes
        for i in range(len(all_v) // 4):
            ax, ay = all_v[i * 4], all_v[i * 4 + 1]
            bx, by = all_v[i * 4 + 2], all_v[i * 4 + 3]
            self.vertex[f"axis_{i}"] = Line(
                ax, ay, bx, by,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 1),
            )

        # Target area
        self.target_proportion: float = target_proportion
        self.target_radius: float = self.container.w / 2 * self.target_proportion

        self.vertex["target_area"] = Circle(
            x=self.container.cx, y=self.container.cy,
            radius=self.target_radius,
            segments=500,
            color=(255, 255, 255, 255),
            batch=None,
            group=G(self.m_draw),
        )
        self.vertex["target_border"] = Arc(
            x=self.container.cx, y=self.container.cy,
            radius=self.target_radius,
            segments=500,
            color=C["BLACK"],
            batch=None,
            group=G(self.m_draw + 1),
        )

        # Cursor: circle + crosshair
        self._cursorcolor: tuple[int, ...] = cursorcolor
        self._build_cursor()

    def _build_cursor(self) -> None:
        """Create cursor shapes at current absolute position."""
        ax, ay = self.cursor_absolute
        r = self.cursor_radius

        self.vertex["cursor_circle"] = Arc(
            x=ax, y=ay, radius=r,
            segments=100,
            color=self._cursorcolor,
            batch=None,
            group=G(self.m_draw + 2),
        )
        self.vertex["cursor_h"] = Line(
            ax - r, ay, ax + r, ay,
            color=self._cursorcolor,
            batch=None,
            group=G(self.m_draw + 2),
        )
        self.vertex["cursor_v"] = Line(
            ax, ay - r, ax, ay + r,
            color=self._cursorcolor,
            batch=None,
            group=G(self.m_draw + 2),
        )

    def set_target_proportion(self, proportion: float) -> None:
        if proportion == self.get_target_proportion():
            return
        self.target_proportion = proportion
        self.target_radius = self.container.w / 2 * proportion
        self.vertex["target_area"].radius = self.target_radius
        self.vertex["target_border"].radius = self.target_radius
        self.logger.record_state(self.name, "target_proportion", proportion)

    def get_target_proportion(self) -> float:
        return self.target_proportion

    def is_cursor_in_target(self) -> bool | float:
        if self.target_radius > 0:
            return self.is_cursor_in_radius(self.target_radius)
        else:
            return float("nan")

    def return_deviation(self) -> float:
        return Vec2(*self.cursor_relative).length()

    def is_cursor_in_radius(self, radius: float) -> bool:
        return radius >= Vec2(self.container.cx, self.container.cy).distance(Vec2(*self.cursor_absolute))

    def set_cursor_position(self, x: float, y: float) -> None:
        self.cursor_relative = [x, y]
        if self.get_cursor_absolute_position() == self.relative_to_absolute():
            return
        self.cursor_absolute = self.relative_to_absolute()
        ax, ay = self.cursor_absolute
        r = self.cursor_radius

        # Update cursor shape positions
        self.vertex["cursor_circle"].x = ax
        self.vertex["cursor_circle"].y = ay
        self.vertex["cursor_h"].x = ax - r
        self.vertex["cursor_h"].y = ay
        self.vertex["cursor_h"].x2 = ax + r
        self.vertex["cursor_h"].y2 = ay
        self.vertex["cursor_v"].x = ax
        self.vertex["cursor_v"].y = ay - r
        self.vertex["cursor_v"].x2 = ax
        self.vertex["cursor_v"].y2 = ay + r

        self.logger.record_state(self.name, "cursor_relative", (x, y))
        self.logger.record_state(self.name, "cursor_proportional", self.relative_to_proportional())

    def get_cursor_absolute_position(self) -> tuple[float, ...]:
        return self.cursor_absolute

    def relative_to_absolute(self) -> tuple[float, ...]:
        return tuple([self.cursor_relative[i] + c for i, c in zip((0, 1), (self.container.cx, self.container.cy))])

    def relative_to_proportional(self) -> tuple[float, ...]:
        return tuple([self.cursor_relative[i] / c for i, c in zip((0, 1), (self.container.w, self.container.h))])

    def proportional_to_relative(self, cursor_proportional: tuple[float, ...]) -> tuple[float, ...]:
        return tuple([cursor_proportional[i] * c for i, c in zip((0, 1), (self.container.w, self.container.h))])

    def set_cursor_color(self, color: tuple[int, ...]) -> None:
        if color == self.get_cursor_color():
            return
        self._cursorcolor = color
        for key in ("cursor_circle", "cursor_h", "cursor_v"):
            self.vertex[key].color = color[:3]
            self.vertex[key].opacity = color[3]
        self.logger.record_state(self.name, "cursor_color", color)

    def get_cursor_color(self) -> tuple[int, ...]:
        return self._cursorcolor
