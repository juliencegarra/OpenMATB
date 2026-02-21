# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any

from pyglet import sprite
from pyglet.gl import glLineWidth  # noqa: F401
from pyglet.shapes import Line, ShapeBase
from pyglet.text import HTMLLabel, Label

from core.constants import BFLIM
from core.constants import COLORS as C
from core.constants import FONT_SIZES as F  # noqa: F401
from core.constants import Group as G
from core.container import Container
from core.logger import Logger, get_logger
from core.utils import get_conf_value
from core.window import Window


class AbstractWidget:
    def __init__(self, name: str, container: Container | None) -> None:
        self.name: str = name
        self.container: Container | None = container
        self.font_name: str = get_conf_value("Openmatb", "font_name")
        self.vertex: dict[str, Any] = dict()
        self.visible: bool = False
        self._batch_assigned: bool = False  # True after first show assigns batch
        self.logger: Logger = get_logger()
        self.highlight_aoi: str = get_conf_value("Openmatb", "highlight_aoi")
        glLineWidth(2)

        self.m_draw: int = 0
        self.verbose: bool = False

        if self.container is not None:
            if self.container.name == "fullscreen":
                self.m_draw = BFLIM
            else:
                self.m_draw = 0

    def is_visible(self) -> bool:
        return self.visible is True

    def show(self) -> None:
        if self.is_visible():
            return
        if self.verbose:
            print("Show ", self.name)
        self.show_aoi_highlight()
        if self._batch_assigned:
            self._show_all_vertices()
        else:
            self.assign_vertices_to_batch()
            self._batch_assigned = True
        if hasattr(self, "set_visibility"):
            self.set_visibility(True)
        else:
            self.visible = True

    def hide(self) -> None:
        if not self.is_visible():
            return
        if self.verbose:
            print("Hide ", self.name)

        self._hide_all_vertices()
        if hasattr(self, "set_visibility"):
            self.set_visibility(False)
        else:
            self.visible = False

    def _show_all_vertices(self) -> None:
        """Re-show: set .visible=True on shapes, restore batch on labels/sprites."""
        batch = Window.MainWindow.batch
        for v_def in self.vertex.values():
            if isinstance(v_def, ShapeBase):
                if v_def.batch is None:
                    v_def.batch = batch
                v_def.visible = True
            elif isinstance(v_def, (Label, HTMLLabel, sprite.Sprite)):
                if v_def.batch is None:
                    v_def.batch = batch

    def _hide_all_vertices(self) -> None:
        """Hide: set .visible=False on shapes, remove batch on labels."""
        for v_def in self.vertex.values():
            if isinstance(v_def, ShapeBase):
                v_def.visible = False
            elif isinstance(v_def, (Label, HTMLLabel)):
                v_def.batch = None

    def show_aoi_highlight(self) -> None:
        """Add some AOI vertices (frame and text)"""
        if self.container is None:
            return

        if self.highlight_aoi is True:
            x1, y1, x2, y2 = self.container.get_x1y1x2y2()
            g = G(self.m_draw + 8)
            red = C["RED"][:3]
            for lname, coords in [("highlight_top", (x1, y1, x2, y1)),
                                   ("highlight_right", (x2, y1, x2, y2)),
                                   ("highlight_bottom", (x2, y2, x1, y2)),
                                   ("highlight_left", (x1, y2, x1, y1))]:
                self.vertex[lname] = Line(*coords, color=red, group=g)

            self.vertex[self.name] = Label(
                self.name, x=x1 + 5, y=y1 - 15, color=C["RED"], group=G(self.m_draw + 8)
            )

    def assign_vertices_to_batch(self) -> None:
        batch = Window.MainWindow.batch
        for v_def in self.vertex.values():
            if isinstance(v_def, (ShapeBase, Label, HTMLLabel, sprite.Sprite)):
                v_def.batch = batch

    def empty_batch(self) -> None:
        self._hide_all_vertices()
        self._batch_assigned = False

    def get_triangle_vertice(self, h_ratio: float = 0.25, x_ratio: float = 0.3, angle: float = 0) -> list[float]:
        # Compute triangle coordinates (radio, pumpflow use it)
        cont: Container = self.container
        w_ratio: float = (h_ratio * cont.h) / cont.w
        tcont: Container = cont.get_reduced(w_ratio, h_ratio)
        tcont = tcont.get_translated(x=x_ratio * cont.w)
        vertice: tuple[float, ...] = (
            tcont.l,
            tcont.b,
            tcont.l + tcont.w,
            tcont.b,
            tcont.l + tcont.w / 2,
            tcont.b + tcont.h,
        )
        centroid: tuple[float, float] = self.get_triangle_centroid(vertice)
        vertice = self.rotate_vertice_list(centroid, vertice, angle)
        return vertice

    def get_triangle_centroid(self, vertice: tuple[float, ...] | list[float]) -> tuple[float, float]:
        x: float = round(sum([v for i, v in enumerate(vertice) if i % 2 == 0]) / (len(vertice) / 2), 2)
        y: float = round(sum([v for i, v in enumerate(vertice) if i % 2 == 1]) / (len(vertice) / 2), 2)
        return (x, y)

    def grouped(self, iterable: tuple[float, ...] | list[float], n: int) -> zip:
        return zip(*[iter(iterable)] * n)

    def rotate_vertice_list(
        self, origin: tuple[float, float], vertices_list: tuple[float, ...] | list[float], angle: float
    ) -> list[float]:
        ox: float
        oy: float
        ox, oy = origin
        rotated_vertices: list[float] = list()
        for px, py in self.grouped(vertices_list, 2):
            qx: float = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
            qy: float = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
            rotated_vertices.extend([qx, qy])
        return rotated_vertices

    def remove_all_vertices(self) -> None:
        self.vertex = dict()
