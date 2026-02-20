# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.container import Container
from core.widgets.abstractwidget import *


class Pump(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Container,
        from_cont: Container,
        to_cont: Container,
        pump_n: int,
        color: tuple[int, int, int, int],
        pump_width: float,
        y_offset: float = 0,
    ) -> None:
        super().__init__(name, container)
        width: float = pump_width

        # If from_container and to_container are aligned (x or y axis)
        if from_cont.cx == to_cont.cx or from_cont.cy == to_cont.cy:
            # Draw a straight line
            self.add_vertex(
                "connector_1",
                2,
                GL_LINES,
                G(self.m_draw),
                ("v2f/static", (from_cont.cx, from_cont.cy + y_offset, to_cont.cx, to_cont.cy + y_offset)),
                ("c4B/static", (C["BLACK"] * 2)),
            )

            # Draw the pump in the middle of the line
            x1: float = min(from_cont.cx, to_cont.cx)
            x2: float = max(from_cont.cx, to_cont.cx)
            s: int = -1 if from_cont.cx > to_cont.cx else 1
            x: float = x1 + (x2 - x1) / 2 + s * width / 2
            y: float = from_cont.cy + y_offset
            w: float = width if from_cont.cx > to_cont.cx else -width  # Pump width
            h: float = abs(w)
            self.pump_vertice: tuple[float, ...] = (x, y, x + w, y + h / 2, x + w, y - h / 2)
            self.num_location: tuple[float, float] = (x + w * 0.70, y + 2)

        else:  # If not, make an perpendicular node
            y_offset = -y_offset - 20
            self.add_vertex(
                "connector_1",
                2,
                GL_LINES,
                G(self.m_draw),
                ("v2f/static", (from_cont.cx, from_cont.cy, from_cont.cx, to_cont.cy + y_offset)),
                ("c4B/static", (C["BLACK"] * 2)),
            )
            self.add_vertex(
                "connector_2",
                2,
                GL_LINES,
                G(self.m_draw),
                ("v2f/static", (to_cont.cx, to_cont.cy + y_offset, from_cont.cx, to_cont.cy + y_offset)),
                ("c4B/static", (C["BLACK"] * 2)),
            )

            # And stick the pump to the source tank
            x = from_cont.cx
            y = from_cont.cy + from_cont.h / 2 + width * 2
            w = width
            self.pump_vertice = (x, y, x - w / 2, y - w, x + w / 2, y - w)
            self.num_location = (x, y - w / 2 - 3)

        self.add_vertex(
            "triangle",
            3,
            GL_TRIANGLES,
            G(self.m_draw + 1),
            ("v2f/static", self.pump_vertice),
            ("c4B/dynamic", (color * 3)),
        )

        self.add_vertex(
            "border",
            6,
            GL_LINES,
            G(self.m_draw + 2),
            ("v2f/static", self.vertice_strip(self.pump_vertice)),
            ("c4B/static", (C["BLACK"] * 6)),
        )

        self.vertex["label"] = Label(
            str(pump_n),
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=self.num_location[0],
            y=self.num_location[1],
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            group=G(self.m_draw + 2),
        )

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_color():
            return
        self.on_batch["triangle"].colors[:] = color * 3
        self.logger.record_state(self.name, "triangle", color)

    def get_color(self) -> tuple[int, int, int, int]:
        return self.get_vertex_color("triangle")
