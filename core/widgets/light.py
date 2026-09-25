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


class Light(AbstractWidget):
    def __init__(self, name: str, container: Container, label: str, color: tuple[int, int, int, int]) -> None:
        super().__init__(name, container)

        x1, y1, x2, y2 = self.container.get_x1y1x2y2()

        self.vertex["background"] = Rectangle(
            x=x1,
            y=y2,
            width=self.container.w,
            height=self.container.h,
            color=color[:3],
            batch=None,
            group=G(self.m_draw),
        )
        self.vertex["background"].opacity = color[3]

        # Border on top
        for bname, coords in [
            ("border_top", (x1, y1, x2, y1)),
            ("border_right", (x2, y1, x2, y2)),
            ("border_bottom", (x2, y2, x1, y2)),
            ("border_left", (x1, y2, x1, y1)),
        ]:
            self.vertex[bname] = Line(
                *coords,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 1),
            )

        self.vertex["label"] = Label(
            label.upper(),
            font_size=F["MEDIUM"],
            x=self.container.cx,
            y=self.container.cy,
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            batch=None,
            group=G(self.m_draw + 2),
            font_name=self.font_name,
        )

    def set_label(self, label: str) -> None:
        label_to_upper: str = label.upper()
        if label_to_upper == self.get_label():
            return
        self.vertex["label"].text = label_to_upper
        self.logger.record_state(self.name, "label", label_to_upper)

    def get_label(self) -> str:
        return self.vertex["label"].text

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_color():
            return
        self.vertex["background"].color = color[:3]
        self.vertex["background"].opacity = color[3]

        self.logger.record_state(self.name, "background", color)
        self.logger.record_state(self.name, "border", C["BLACK"])

    def get_color(self) -> tuple[int, int, int, int]:
        shape = self.vertex["background"]
        return (*shape.color[:3], shape.opacity)
