# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.widgets.abstractwidget import *


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

        # Compute vertices of X and Y axis
        # First, set one axis and one corner
        cx, cy = self.container.get_center()
        _x1, _y1, x2, y2 = self.container.get_x1y1x2y2()
        v1: list[float] = [cx, cy, x2, cy, x2, y2, x2 - self.corner_width, y2, x2, y2, x2, y2 + self.corner_width]
        # On this axis, define five graduations
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

        # Then copy and rotate this axis three times
        v2: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi / 2)
        v3: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi)
        v4: list[float] = self.rotate_vertice_list([cx, cy], v1, math.pi + math.pi / 2)
        v: list[float] = v1 + v2 + v3 + v4

        self.add_lines("axis", G(self.m_draw + 1), v, C["BLACK"] * (len(v) // 2))

        # Target area
        self.target_proportion: float = target_proportion
        self.target_radius: float = self.container.w / 2 * self.target_proportion
        v = self.vertice_circle([self.container.cx, self.container.cy], self.target_radius, 50)

        self.add_polygon("target_area", G(self.m_draw), v, (255, 255, 255, 255) * (len(v) // 2))

        self.add_lines("target_border", G(self.m_draw + 1), v, C["BLACK"] * (len(v) // 2))

        # Cursor definition
        v = self.get_cursor_vertice()
        self.add_lines("cursor", G(self.m_draw + 2), v, cursorcolor * (len(v) // 2))

    def set_target_proportion(self, proportion: float) -> None:
        if proportion == self.get_target_proportion():
            return
        self.target_proportion = proportion
        self.target_radius = self.container.w / 2 * proportion
        v: list[float] = self.vertice_circle([self.container.cx, self.container.cy], self.target_radius, 50)
        self.on_batch["target_area"].position[:] = v
        self.on_batch["target_border"].position[:] = v
        self.logger.record_state(self.name, "target_proportion", proportion)

    def get_target_proportion(self) -> float:
        return self.target_proportion

    def get_cursor_vertice(self) -> list[float]:
        v: list[float] = self.vertice_strip(self.vertice_circle(self.cursor_absolute, self.cursor_radius, 20))
        v.extend(
            [
                self.cursor_absolute[0] - self.cursor_radius,
                self.cursor_absolute[1],
                self.cursor_absolute[0] + self.cursor_radius,
                self.cursor_absolute[1],
            ]
        )
        v.extend(
            [
                self.cursor_absolute[0],
                self.cursor_absolute[1] - self.cursor_radius,
                self.cursor_absolute[0],
                self.cursor_absolute[1] + self.cursor_radius,
            ]
        )
        return v

    def is_cursor_in_target(self) -> bool | float:
        if self.target_radius > 0:
            return self.is_cursor_in_radius(self.target_radius)
        else:
            return float("nan")

    def return_deviation(self) -> float:
        return math.sqrt(self.cursor_relative[0] ** 2 + self.cursor_relative[1] ** 2)

    def is_cursor_in_radius(self, radius: float) -> bool:
        return radius >= math.sqrt(
            (self.container.cx - self.cursor_absolute[0]) ** 2 + (self.container.cy - self.cursor_absolute[1]) ** 2
        )

    def set_cursor_position(self, x: float, y: float) -> None:
        self.cursor_relative = [x, y]
        if self.get_cursor_absolute_position() == self.relative_to_absolute():
            return
        self.cursor_absolute = self.relative_to_absolute()
        v: list[float] = self.get_cursor_vertice()
        self.on_batch["cursor"].position[:] = v
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
        length: int = len(self.get_cursor_vertice()) // 2
        self.on_batch["cursor"].colors[:] = color * length
        self.logger.record_state(self.name, "cursor_color", color)

    def get_cursor_color(self) -> tuple[int, ...]:
        return self.get_vertex_color("cursor")
