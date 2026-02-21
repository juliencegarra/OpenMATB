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
from core.logger import Logger, get_logger
from core.utils import get_conf_value
from core.widgets.abstractwidget import AbstractWidget
from core.window import Window


class Schedule(AbstractWidget):
    def __init__(self, name: str, container: Any, label: str) -> None:
        super().__init__(name, container)

        self.line_radius: int = int(self.container.h / 200)
        self.bound_radius: int = int(self.container.h / 70)
        self.box_radius: float = self.bound_radius * 1.5

        self.vertex["letter"] = Label(
            label[0].upper(),
            font_size=F["MEDIUM"],
            font_name=self.font_name,
            x=self.container.cx,
            y=self.container.y2 - 15,
            anchor_x="center",
            anchor_y="top",
            color=C["BLACK"],
            group=G(1),
        )

        # Vertical line
        self.vertex["line"] = Line(
            self.container.cx, self.container.y1,
            self.container.cx, self.container.y2,
            color=C["GREY"][:3], group=G(self.m_draw + 1),
        )

        # Top bound marker
        r: int = self.bound_radius
        self.vertex["top_bound"] = Rectangle(
            x=self.container.cx - r,
            y=self.container.y1,
            width=2 * r,
            height=2 * r,
            color=C["GREY"][:3], group=G(self.m_draw + 3),
        )
        self.vertex["top_bound"].opacity = C["GREY"][3]

        # Bottom bound marker
        self.vertex["bottom_bound"] = Rectangle(
            x=self.container.cx - r,
            y=self.container.y2 - 2 * r,
            width=2 * r,
            height=2 * r,
            color=C["GREY"][:3], group=G(self.m_draw + 3),
        )
        self.vertex["bottom_bound"].opacity = C["GREY"][3]

    def set_top_bound_color(self, bound_color: tuple[int, ...]) -> None:
        shape = self.vertex["top_bound"]
        current: tuple[int, ...] = (*shape.color[:3], shape.opacity)
        if bound_color == current:
            return
        shape.color = bound_color[:3]
        shape.opacity = bound_color[3]
        self.logger.record_state(self.name, "top_bound_color", bound_color)

    def sec_to_y(self, sec: float, max_sec: float) -> float:
        return self.container.y1 - (sec / max_sec * (self.container.y1 - self.container.y2))

    def map_segment(
        self, time_mode: str, rel_plan: list[tuple[float, float]], max_sec: float, color: tuple[int, ...]
    ) -> None:
        # Delete any previous segments for this time_mode
        for key in list(self.vertex):
            if key.startswith(f"seg_{time_mode}_"):
                self.vertex[key].delete()
                del self.vertex[key]

        # Create a Rectangle per segment
        batch = Window.MainWindow.batch if self.visible else None
        for i, segment_sec in enumerate(rel_plan):
            x_radius: float | int = self.line_radius if time_mode == "running" else self.box_radius
            start, end = segment_sec
            y1: float = self.sec_to_y(start, max_sec)
            y2: float = self.sec_to_y(end, max_sec)
            seg = Rectangle(
                x=self.container.cx - x_radius,
                y=min(y1, y2),
                width=2 * x_radius,
                height=abs(y1 - y2),
                color=color[:3],
                batch=batch,
                group=G(self.m_draw + (2 if time_mode == "running" else 3)),
            )
            seg.opacity = color[3]
            self.vertex[f"seg_{time_mode}_{i}"] = seg

    def update(self) -> None:
        if self.visible:
            self.change_top_bound_color()
