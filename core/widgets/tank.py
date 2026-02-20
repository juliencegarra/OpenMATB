# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.container import Container
from core.widgets.abstractwidget import *


class Tank(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        letter: str,
        level: float,
        fluid_label: str,
        level_max: float,
        target: float | None,
        toleranceradius: float,
        infoside: str,
    ) -> None:
        super().__init__(name, container)

        self.tolerance_cont: Container | None = None
        self.infoside: str = infoside
        self.tolerance_radius: float = toleranceradius
        self.level: float = level
        # self.tolerance_color = C['BLACK']

        # Background vertex #
        x1, y1, x2, y2 = self.container.get_x1y1x2y2()
        self.border_vertices: tuple[float, ...] = self.vertice_border(self.container)
        self.add_quad("background", G(self.m_draw + 1), self.border_vertices, C["WHITE"] * 4)

        if target is not None:
            vt: list[float] = self.get_tolerance_vertices(self.tolerance_radius, target, level_max)
            self.add_quad("tolerance", G(self.m_draw + 1), vt, C["BLACK"] * 4)

        fluid_vertices: list[float] = self.get_fluid_vertices(self.level, level_max)
        self.add_quad("fluid", G(self.m_draw + 2), fluid_vertices, C["GREEN"] * 4)

        self.add_lines("borders", G(self.m_draw + 3), self.vertice_strip(self.border_vertices), C["BLACK"] * 8)

        x, _y = self.container.get_center()
        self.vertex["fluid_label"] = Label(
            fluid_label,
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=x,
            y=y2 - 15,
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            group=G(1),
        )

        l_x: float = x1 - 15 if infoside == "left" else x2 + 15
        self.vertex["tank_label"] = Label(
            letter,
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=l_x,
            y=y1 - 10,
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            group=G(1),
        )

    def get_fluid_vertices(self, level: float, level_max: float) -> list[float]:
        v2: list[float] = list(self.border_vertices)
        v2[1] = v2[3] = self.get_y_of(level, level_max)
        return v2

    def get_y_of(self, level: float, level_max: float) -> float:
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / level_max)

    def get_tolerance_vertices(self, radius: float, target_level: float, level_max: float) -> list[float]:
        t_width: int = 15
        t_left: float = self.container.l - t_width if self.infoside == "left" else self.container.l + self.container.w
        t_bottom: float = self.get_y_of(target_level - radius, level_max)
        t_height: float = self.get_y_of(radius * 2, level_max) - self.get_y_of(0, level_max)

        self.tolerance_cont = Container("Tolerance", t_left, t_bottom, t_width, t_height)
        return self.vertice_border(self.tolerance_cont)

    def set_tolerance_radius(self, radius: float, target: float, level_max: float) -> None:
        if radius == self.get_tolerance_radius():
            return
        self.tolerance_radius = radius
        self.on_batch["tolerance"].position[:] = self.get_tolerance_vertices(radius, target, level_max)
        self.logger.record_state(self.name, "tolerance_radius", radius)
        self.logger.record_state(self.name, "target", target)
        self.logger.record_state(self.name, "level_max", level_max)

    def set_tolerance_color(self, color: tuple[int, ...]) -> None:
        if color == self.get_tolerance_color():
            return
        self.on_batch["tolerance"].colors[:] = color * 4
        self.logger.record_state(self.name, "tolerance_color", color)

    def get_tolerance_radius(self) -> float:
        return self.tolerance_radius

    def get_tolerance_color(self) -> tuple[int, ...]:
        return self.get_vertex_color("tolerance")

    def set_fluid_level(self, level: float, level_max: float) -> None:
        if level == self.get_fluid_level():
            return
        self.level = level
        v1: list[float] = list(self.vertice_border(self.container))
        v1[1] = v1[3] = self.get_y_of(level, level_max)
        self.on_batch["fluid"].position[:] = v1
        self.logger.record_state(self.name, "fluid_level", level)

    def get_fluid_level(self) -> float:
        return self.level

    def set_fluid_label(self, label: str) -> None:
        if label == self.get_fluid_label():
            return
        self.vertex["fluid_label"].text = label
        self.logger.record_state(self.name, "fluid_label", label)

    def get_fluid_label(self) -> str:
        return self.vertex["fluid_label"].text
