# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from core.container import Container
from core.widgets.abstractwidget import *
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

        # Arrows vertices #
        # Only a change in vertices is needed to show/hide arrows --> (0, 0, 0...) = hide
        for name, _info in self.arrows.items():
            self.add_triangles(name, G(self.m_draw + 2), (0, 0, 0, 0, 0, 0), C['BLACK'] * 3)

        # Feedback vertices #
        # A frame slightly smaller than the radio container
        vertices: tuple[float, ...] = self.vertice_line_border(container.get_reduced(0.6, 0.9))
        self.add_lines('feedback_lines', G(self.m_draw + 3), vertices, C['BACKGROUND'] * 8)
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
        for name, _info in self.arrows.items():
            v: tuple[int, ...] = (0, 0) * 3  # Get an invisible vertice (hide)
            self.on_batch[name].position[:] = v
        self.is_selected = False
        self.logger.record_state(self.name, "selected", False)

    def show_arrows(self) -> None:
        for name, info in self.arrows.items():
            v: list[float] = self.get_triangle_vertice(x_ratio=info["x_ratio"], angle=info["angle"])
            self.on_batch[name].position[:] = v
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
        if color == self.get_vertex_color("feedback_lines"):
            return
        self.on_batch["feedback_lines"].colors[:] = color * 8
        self.logger.record_state(self.name, "feedback_color", color)
