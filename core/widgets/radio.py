# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any

from pyglet.shapes import Line, Triangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget
from core.window import Window


class Radio(AbstractWidget):
    def __init__(self, name: str, container: Container, label: str, frequency: float, on: bool) -> None:
        super().__init__(name, container)

        self.arrows: dict[str, dict[str, float]] = dict(
            arrow_up=dict(x_ratio=-0.23, angle=0),
            arrow_down=dict(x_ratio=-0.2, angle=math.pi),
            arrow_left=dict(x_ratio=0.2, angle=math.pi / 2),
            arrow_right=dict(x_ratio=0.23, angle=3 * math.pi / 2),
        )
        self.frequency: float = frequency
        self.label: str = label
        self.is_selected: bool = on

        # Radio label #
        self.vertex["radio_frequency"] = Label(
            self.get_frequency_string(frequency),
            font_size=F["SMALL"],
            x=self.container.cx,
            y=self.container.cy,
            font_name=self.font_name,
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            batch=Window.MainWindow.batch,
            group=G(self.m_draw + 1),
        )

        # Arrow shapes — created with actual positions, hidden by default
        for arrow_name, info in self.arrows.items():
            v: list[float] = self.get_triangle_vertice(x_ratio=info["x_ratio"], angle=info["angle"])
            self.vertex[arrow_name] = Triangle(
                v[0], v[1], v[2], v[3], v[4], v[5],
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 2),
            )
            self.vertex[arrow_name].visible = False

        # Feedback lines — a frame slightly smaller than the radio container
        reduced: Container = container.get_reduced(0.6, 0.9)
        segments: list[tuple[float, float, float, float]] = [
            (reduced.x1, reduced.y1, reduced.x2, reduced.y1),
            (reduced.x2, reduced.y1, reduced.x2, reduced.y2),
            (reduced.x2, reduced.y2, reduced.x1, reduced.y2),
            (reduced.x1, reduced.y2, reduced.x1, reduced.y1),
        ]
        for i, (lx1, ly1, lx2, ly2) in enumerate(segments):
            self.vertex[f"feedback_line_{i}"] = Line(
                lx1, ly1, lx2, ly2,
                color=C["BACKGROUND"],
                batch=None,
                group=G(self.m_draw + 3),
            )

        self.show()

    def show(self) -> None:
        super().show()
        if self.is_selected:
            self.show_arrows()

    def get_frequency_string(self, frequency: float) -> str:
        return f"{self.label.replace('_', ' ')}\t\t\t\t\t\t\t{round(frequency, 1)}"

    def get_position(self) -> Any:
        return self.pos

    def hide_arrows(self) -> None:
        for arrow_name in self.arrows:
            self.vertex[arrow_name].visible = False
        self.is_selected = False
        self.logger.record_state(self.name, "selected", False)

    def show_arrows(self) -> None:
        for arrow_name in self.arrows:
            self.vertex[arrow_name].visible = True
        self.is_selected = True
        self.logger.record_state(self.name, "selected", True)

    def is_new_frequency(self, frequency: float) -> bool:
        return self.get_frequency_string(frequency) != self.vertex["radio_frequency"].text

    def set_frequency_text(self, frequency: float) -> None:
        if not self.is_new_frequency(frequency):
            return
        self.vertex["radio_frequency"].text = self.get_frequency_string(frequency)
        self.logger.record_state(self.name, "radio_frequency", frequency)

    def set_feedback_color(self, color: tuple[int, int, int, int]) -> None:
        current = self._get_feedback_color()
        if color == current:
            return
        for i in range(4):
            self.vertex[f"feedback_line_{i}"].color = color[:3]
            self.vertex[f"feedback_line_{i}"].opacity = color[3]
        self.logger.record_state(self.name, "feedback_color", color)

    def _get_feedback_color(self) -> tuple[int, int, int, int]:
        shape = self.vertex["feedback_line_0"]
        return (*shape.color[:3], shape.opacity)
