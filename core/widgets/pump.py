# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from pyglet.shapes import Line, Triangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


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
            self.vertex["connector_1"] = Line(
                from_cont.cx, from_cont.cy + y_offset,
                to_cont.cx, to_cont.cy + y_offset,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw),
            )

            # Draw the pump in the middle of the line
            x1: float = min(from_cont.cx, to_cont.cx)
            x2: float = max(from_cont.cx, to_cont.cx)
            s: int = -1 if from_cont.cx > to_cont.cx else 1
            x: float = x1 + (x2 - x1) / 2 + s * width / 2
            y: float = from_cont.cy + y_offset
            w: float = width if from_cont.cx > to_cont.cx else -width  # Pump width
            h: float = abs(w)
            pump_verts = (x, y, x + w, y + h / 2, x + w, y - h / 2)
            num_location: tuple[float, float] = (x + w * 0.70, y + 2)

        else:  # If not, make a perpendicular node
            y_offset = -y_offset - 20
            self.vertex["connector_1"] = Line(
                from_cont.cx, from_cont.cy,
                from_cont.cx, to_cont.cy + y_offset,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw),
            )
            self.vertex["connector_2"] = Line(
                to_cont.cx, to_cont.cy + y_offset,
                from_cont.cx, to_cont.cy + y_offset,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw),
            )

            # And stick the pump to the source tank
            x = from_cont.cx
            y = from_cont.cy + from_cont.h / 2 + width * 2
            w = width
            pump_verts = (x, y, x - w / 2, y - w, x + w / 2, y - w)
            num_location = (x, y - w / 2 - 3)

        # Triangle shape
        self.vertex["triangle"] = Triangle(
            pump_verts[0], pump_verts[1],
            pump_verts[2], pump_verts[3],
            pump_verts[4], pump_verts[5],
            color=color,
            batch=None,
            group=G(self.m_draw + 1),
        )

        # Border lines around the triangle
        pv = pump_verts
        for i, (lx1, ly1, lx2, ly2) in enumerate([
            (pv[0], pv[1], pv[2], pv[3]),
            (pv[2], pv[3], pv[4], pv[5]),
            (pv[4], pv[5], pv[0], pv[1]),
        ]):
            self.vertex[f"border_{i}"] = Line(
                lx1, ly1, lx2, ly2,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + 2),
            )

        self.vertex["label"] = Label(
            str(pump_n),
            font_size=F["SMALL"],
            font_name=self.font_name,
            x=num_location[0],
            y=num_location[1],
            anchor_x="center",
            anchor_y="center",
            color=C["BLACK"],
            group=G(self.m_draw + 2),
        )

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_color():
            return
        self.vertex["triangle"].color = color[:3]
        self.vertex["triangle"].opacity = color[3]
        self.logger.record_state(self.name, "triangle", color)

    def get_color(self) -> tuple[int, int, int, int]:
        shape = self.vertex["triangle"]
        return (*shape.color[:3], shape.opacity)
