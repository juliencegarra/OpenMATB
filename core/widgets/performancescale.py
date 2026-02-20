# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.container import Container
from core.widgets.abstractwidget import *


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

        # Background vertex #
        _x1: float
        _y1: float
        _x2: float
        _y2: float
        _x1, _y1, _x2, _y2 = self.container.get_x1y1x2y2()
        self.border_vertices: tuple[float, ...] = self.vertice_border(self.container)
        self.add_vertex(
            "background",
            4,
            GL_QUADS,
            G(self.m_draw),
            ("v2f/static", self.border_vertices),
            ("c4B/static", (C["WHITE"] * 4)),
        )

        # Performance vertex #
        performance_vertices: list[float] = self.get_performance_vertices(self.performance_level)
        self.add_vertex(
            "performance",
            4,
            GL_QUADS,
            G(self.m_draw + 1),
            ("v2f/stream", performance_vertices),
            ("c4B/static", (self.performance_color * 4)),
        )

        # Borders vertex #
        self.add_vertex(
            "borders",
            8,
            GL_LINES,
            G(self.m_draw + 2),
            ("v2f/static", self.vertice_strip(self.border_vertices)),
            ("c4B/static", (C["BLACK"] * 8)),
        )

        # Ticks vertex #
        self.tick_width: float = self.container.w * 0.25
        v: list[float] = list()
        x: float = self.container.l + self.container.w + self.container.w * 0.1

        self.positions: list[float] = []

        for i in range(self.tick_number):
            y: float = self.container.b + self.container.h - (self.container.h / (self.tick_number - 1)) * i
            w: float = self.tick_width
            v.extend([self.container.x2 - w, y, self.container.x2, y])

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

        self.add_vertex(
            "ticks",
            len(v) // 2,
            GL_LINES,
            G(self.m_draw + 2),
            ("v2f/static", v),
            ("c4B/static", (C["BLACK"] * (len(v) // 2))),
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

    def get_performance_vertices(self, level: int) -> list[float]:
        v2: list[float] = list(self.border_vertices)
        v2[1] = v2[3] = self.get_y_of(level)
        return v2

    def get_y_of(self, level: int) -> float:
        _: float
        y1: float
        y2: float
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / self.level_max)

    def set_performance_level(self, level: int) -> None:
        if level == self.get_performance_level():
            return
        self.performance_level = level
        v1: list[float] = list(self.vertice_border(self.container))
        v1[1] = v1[3] = self.get_y_of(self.performance_level)
        self.on_batch["performance"].vertices = v1
        self.logger.record_state(self.name, "level", self.performance_level)

    def get_performance_level(self) -> int:
        return self.performance_level

    def set_performance_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_performance_color():
            return
        self.performance_color = color
        self.on_batch["performance"].colors[:] = color * 4
        self.logger.record_state(self.name, "color", self.performance_color)

    def get_performance_color(self) -> tuple[int, int, int, int]:
        return self.get_vertex_color("performance")
