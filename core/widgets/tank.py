# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from pyglet.shapes import Line, Rectangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


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

        x1, y1, x2, y2 = self.container.get_x1y1x2y2()

        # Background fill
        self.vertex["background"] = Rectangle(
            x=x1,
            y=y2,
            width=self.container.w,
            height=self.container.h,
            color=C["WHITE"][:3],
            batch=None,
            group=G(self.m_draw + 1),
        )

        # Border on top of fluid (m_draw + 3)
        for name, coords in [
            ("border_top", (x1, y1, x2, y1)),
            ("border_right", (x2, y1, x2, y2)),
            ("border_bottom", (x2, y2, x1, y2)),
            ("border_left", (x1, y2, x1, y1)),
        ]:
            self.vertex[name] = Line(
                *coords,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 3),
            )

        if target is not None:
            t_left, t_bottom, t_width, t_height = self._get_tolerance_lbwh(self.tolerance_radius, target, level_max)
            self.vertex["tolerance"] = Rectangle(
                x=t_left,
                y=t_bottom,
                width=t_width,
                height=t_height,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 1),
            )

        # Fluid rectangle — bottom-anchored, height varies
        fluid_y = self.get_y_of(self.level, level_max)
        self.vertex["fluid"] = Rectangle(
            x=self.container.x1,
            y=y2,
            width=self.container.w,
            height=fluid_y - y2,
            color=C["GREEN"],
            batch=None,
            group=G(self.m_draw + 2),
        )

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

    def _get_tolerance_lbwh(
        self, radius: float, target_level: float, level_max: float
    ) -> tuple[float, float, float, float]:
        t_width: int = 15
        t_left: float = self.container.l - t_width if self.infoside == "left" else self.container.l + self.container.w
        t_bottom: float = self.get_y_of(target_level - radius, level_max)
        t_height: float = self.get_y_of(radius * 2, level_max) - self.get_y_of(0, level_max)
        self.tolerance_cont = Container("Tolerance", t_left, t_bottom, t_width, t_height)
        return t_left, t_bottom, t_width, t_height

    def get_y_of(self, level: float, level_max: float) -> float:
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / level_max)

    def set_tolerance_radius(self, radius: float, target: float, level_max: float) -> None:
        if radius == self.get_tolerance_radius():
            return
        self.tolerance_radius = radius
        t_left, t_bottom, t_width, t_height = self._get_tolerance_lbwh(radius, target, level_max)
        shape = self.vertex["tolerance"]
        shape.x = t_left
        shape.y = t_bottom
        shape.width = t_width
        shape.height = t_height
        self.logger.record_state(self.name, "tolerance_radius", radius)
        self.logger.record_state(self.name, "target", target)
        self.logger.record_state(self.name, "level_max", level_max)

    def set_tolerance_color(self, color: tuple[int, ...]) -> None:
        if color == self.get_tolerance_color():
            return
        self.vertex["tolerance"].color = color[:3]
        self.vertex["tolerance"].opacity = color[3]
        self.logger.record_state(self.name, "tolerance_color", color)

    def get_tolerance_radius(self) -> float:
        return self.tolerance_radius

    def get_tolerance_color(self) -> tuple[int, ...]:
        shape = self.vertex["tolerance"]
        return (*shape.color[:3], shape.opacity)

    def set_fluid_level(self, level: float, level_max: float) -> None:
        if level == self.get_fluid_level():
            return
        self.level = level
        _, _, _, y2 = self.container.get_x1y1x2y2()
        fluid_y: float = self.get_y_of(level, level_max)
        self.vertex["fluid"].height = fluid_y - y2
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
