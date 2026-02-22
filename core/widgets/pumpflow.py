# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math

from pyglet.shapes import Triangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


class PumpFlow(AbstractWidget):
    def __init__(self, name: str, container: Container, label: str, flow: int) -> None:
        super().__init__(name, container)

        self.label: str = label
        self.flow: int = flow

        # Pump number label (left-aligned)
        self.vertex[self.label] = Label(
            self.label,
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=self.container.l + self.container.w * 0.3,
            y=self.container.cy,
            anchor_x="left",
            anchor_y="center",
            color=C["BLACK"],
            group=G(self.m_draw + 1),
        )

        # Flow value label (same gap as label-to-triangle, on the right side)
        self.vertex["flow_label"] = Label(
            str(0),
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=self.container.l + self.container.w * 0.7,
            y=self.container.cy,
            anchor_x="right",
            anchor_y="center",
            color=C["BLACK"],
            group=G(self.m_draw + 1),
        )

        # Pump arrow — compute triangle vertices using the parent helper
        v: list[float] = self.get_triangle_vertice(h_ratio=0.25, x_ratio=-0.05, angle=3 * math.pi / 2)
        self.vertex[f"{self.label}_arrow"] = Triangle(
            v[0], v[1], v[2], v[3], v[4], v[5],
            color=C["BLACK"],
            batch=None,
            group=G(self.m_draw + 2),
        )

    def set_flow(self, flow: int) -> None:
        flow_str = str(flow)
        if flow_str == self.vertex["flow_label"].text:
            return
        self.vertex["flow_label"].text = flow_str
        self.logger.record_state(self.name, self.label, flow)

    def get_flow(self) -> str:
        return self.vertex["flow_label"].text
