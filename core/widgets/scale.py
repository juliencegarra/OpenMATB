# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from pyglet.shapes import Line, Rectangle, Triangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.widgets import AbstractWidget


class Scale(AbstractWidget):
    def __init__(self, name: str, container: Any, label: str, arrow_position: int = 5) -> None:
        super().__init__(name, container)

        self.background_color: tuple[int, int, int] = (255, 255, 255)
        self.feedback_visible: bool = False

        # Compute arrow positions list
        self.positions: list[float] = [
            self.container.b + (self.container.h / 11) * i + self.container.h / 22 for i in range(11)
        ]
        self.position: int = 5

        # Label
        self.vertex["label"] = Label(
            label.upper(),
            font_size=F["MEDIUM"],
            x=self.container.cx,
            font_name=self.font_name,
            y=self.container.b - 20,
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            batch=None,
            group=G(self.m_draw + 1),
        )

        x1, y1, x2, y2 = self.container.get_x1y1x2y2()

        # Background fill
        self.vertex["background"] = Rectangle(
            x=x1, y=y2,
            width=self.container.w,
            height=self.container.h,
            color=(255, 255, 255),
            batch=None,
            group=G(self.m_draw + self.m_draw + 1),
        )

        # Border on top
        for bname, coords in [("border_top", (x1, y1, x2, y1)),
                               ("border_right", (x2, y1, x2, y2)),
                               ("border_bottom", (x2, y2, x1, y2)),
                               ("border_left", (x1, y2, x1, y1))]:
            self.vertex[bname] = Line(
                *coords, color=C["BLACK"], batch=None,
                group=G(self.m_draw + self.m_draw + 3),
            )

        # Ticks
        self.tick_width: float = self.container.w * 0.25
        for i in range(11):
            w: float = self.tick_width if i != 5 else self.tick_width + 8
            self.vertex[f"tick_{i}"] = Line(
                self.container.x2 - w, self.positions[i],
                self.container.x2, self.positions[i],
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 3),
            )

        # Arrow dimensions
        self.arrow_width: float = 0.15 * self.container.w
        self.arrow_x_offset: float = 0.22 * self.container.w
        self.feedback_height: float = 0.12 * self.container.h

        # Feedback rectangle (hidden by default)
        self.vertex["feedback"] = Rectangle(
            x=0, y=0, width=0, height=0,
            color=C["GREEN"],
            batch=None,
            group=G(self.m_draw + 2),
        )
        self.vertex["feedback"].visible = False

        # Arrow triangle
        av = self.return_arrow_vertice(arrow_position)
        self.vertex["arrow"] = Triangle(
            av[0], av[1], av[2], av[3], av[4], av[5],
            color=C["BLACK"],
            batch=None,
            group=G(self.m_draw + 2),
        )

    def return_arrow_vertice(self, position: int) -> tuple[float, ...]:
        xo: float = self.arrow_x_offset
        aw: float = self.arrow_width
        return (
            self.container.x2 - self.tick_width - xo,
            self.positions[position],
            self.container.x2 - self.tick_width - (xo + aw),
            self.positions[position] - aw / 2,
            self.container.x2 - self.tick_width - (xo + aw),
            self.positions[position] + aw / 2,
        )

    def set_feedback_visibility(self, visible: bool) -> None:
        if visible == self.feedback_visible:
            return
        self.feedback_visible = visible
        shape = self.vertex["feedback"]
        if visible:
            h: float = self.feedback_height
            shape.x = self.container.x1
            shape.y = self.container.y2
            shape.width = self.container.w
            shape.height = h
            shape.visible = True
        else:
            shape.visible = False
        self.logger.record_state(self.name, "feedback_visible", visible)

    def is_feedback_visible(self) -> bool:
        return self.feedback_visible is True

    def set_feedback_color(self, color: tuple[int, ...]) -> None:
        if color == self.get_feedback_color():
            return
        self.vertex["feedback"].color = color[:3]
        self.vertex["feedback"].opacity = color[3]
        self.logger.record_state(self.name, "feedback_color", color)

    def get_feedback_color(self) -> tuple[int, ...]:
        shape = self.vertex["feedback"]
        return (*shape.color[:3], shape.opacity)

    def set_arrow_position(self, position: int) -> None:
        if position == self.get_arrow_position():
            return
        self.position = position
        av = self.return_arrow_vertice(self.position)
        old = self.vertex["arrow"]
        self.vertex["arrow"] = Triangle(
            av[0], av[1], av[2], av[3], av[4], av[5],
            color=C["BLACK"],
            batch=old.batch,
            group=old.group,
        )
        old.delete()
        self.logger.record_state(self.name, "arrow", self.position)

    def get_arrow_position(self) -> int:
        return self.position

    def set_label(self, label: str) -> None:
        label_to_upper: str = label.upper()
        if label == self.get_label():
            return
        self.vertex["label"].text = label_to_upper
        self.logger.record_state(self.name, "label", label_to_upper)

    def get_label(self) -> str:
        return self.vertex["label"].text
