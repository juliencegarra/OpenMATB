# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from pyglet.shapes import Line, Rectangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


class Performancescale(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Container,
        level_min: int,
        level_max: int,
        tick_number: int,
        color: tuple[int, int, int, int],
    ) -> None:
        super().__init__(name, container)

        self.performance_level: int = level_max
        self.performance_color: tuple[int, int, int, int] = color
        self.level_min: int = level_min
        self.level_max: int = level_max
        self.tick_number: int = tick_number

        self._draw_scale()

    def _draw_scale(self) -> None:
        tick_inter: int = int((self.level_max - self.level_min) / (self.tick_number - 1))
        tick_values: list[int] = list(reversed(range(self.level_min, self.level_max + 1, tick_inter)))

        x1, y1, x2, y2 = self.container.get_x1y1x2y2()

        # Background fill
        self.vertex["background"] = Rectangle(
            x=x1, y=y2,
            width=self.container.w,
            height=self.container.h,
            color=C["WHITE"][:3],
            batch=None,
            group=G(self.m_draw),
        )

        # Performance bar
        perf_y: float = self.get_y_of(self.performance_level)
        self.vertex["performance"] = Rectangle(
            x=self.container.x1,
            y=y2,
            width=self.container.w,
            height=perf_y - y2,
            color=self.performance_color,
            batch=None,
            group=G(self.m_draw + 1),
        )

        # Ticks
        self.tick_width: float = self.container.w * 0.25
        x: float = self.container.l + self.container.w + self.container.w * 0.1

        for i in range(self.tick_number):
            y: float = self.container.b + self.container.h - (self.container.h / (self.tick_number - 1)) * i
            w: float = self.tick_width
            self.vertex[f"tick_{tick_values[i]}"] = Line(
                self.container.x2 - w, y, self.container.x2, y,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 2),
            )
            self.vertex[f"tick_{tick_values[i]}_label"] = Label(
                str(tick_values[i]),
                font_size=F["SMALL"],
                x=x,
                y=y,
                anchor_x="left",
                anchor_y="center",
                color=C["BLACK"],
                group=G(self.m_draw + 2),
                font_name=self.font_name,
            )

        # Border on top of everything
        for name, coords in [("border_top", (x1, y1, x2, y1)),
                              ("border_right", (x2, y1, x2, y2)),
                              ("border_bottom", (x2, y2, x1, y2)),
                              ("border_left", (x1, y2, x1, y1))]:
            self.vertex[name] = Line(
                *coords, color=C["BLACK"], batch=None, group=G(self.m_draw + 3),
            )

    def _rebuild(self) -> None:
        self.hide()
        self.remove_all_vertices()
        self._draw_scale()
        self.show()

    def set_tick_number(self, n: int) -> None:
        if n == self.tick_number:
            return
        self.tick_number = n
        self._rebuild()

    def set_level_min(self, n: int) -> None:
        if n == self.level_min:
            return
        self.level_min = n
        self._rebuild()

    def set_level_max(self, n: int) -> None:
        if n == self.level_max:
            return
        self.level_max = n
        self._rebuild()

    def get_y_of(self, level: int) -> float:
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / self.level_max)

    def set_performance_level(self, level: int) -> None:
        if level == self.get_performance_level():
            return
        self.performance_level = level
        _, _, _, y2 = self.container.get_x1y1x2y2()
        perf_y: float = self.get_y_of(self.performance_level)
        self.vertex["performance"].height = perf_y - y2
        self.logger.record_state(self.name, "level", self.performance_level)

    def get_performance_level(self) -> int:
        return self.performance_level

    def set_performance_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_performance_color():
            return
        self.performance_color = color
        self.vertex["performance"].color = color[:3]
        self.vertex["performance"].opacity = color[3]
        self.logger.record_state(self.name, "color", self.performance_color)

    def get_performance_color(self) -> tuple[int, int, int, int]:
        shape = self.vertex["performance"]
        return (*shape.color[:3], shape.opacity)
