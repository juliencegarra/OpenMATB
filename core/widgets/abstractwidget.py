# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any

from pyglet import sprite
from pyglet.gl import (  # noqa: F401
    GL_BLEND,
    GL_LINES,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TRIANGLES,
    glBlendFunc,
    glEnable,
    glLineWidth,
)
from pyglet.shapes import ShapeBase
from pyglet.text import HTMLLabel, Label

from core.constants import BFLIM
from core.constants import COLORS as C
from core.constants import FONT_SIZES as F  # noqa: F401
from core.constants import Group as G
from core.container import Container
from core.logger import Logger, get_logger
from core.rendering import get_group, get_program, quad_indices
from core.utils import get_conf_value
from core.window import Window


class AbstractWidget:
    def __init__(self, name: str, container: Container | None) -> None:
        self.name: str = name
        self.container: Container | None = container
        self.font_name: str = get_conf_value("Openmatb", "font_name")
        self.vertex: dict[str, Any] = dict()
        self.on_batch: dict[str, Any] = dict()
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
        """Re-show: set .visible=True on shapes/labels, rebuild legacy on_batch entries."""
        batch = Window.MainWindow.batch
        for name, v_def in self.vertex.items():
            if isinstance(v_def, ShapeBase):
                if v_def.batch is None:
                    v_def.batch = batch
                v_def.visible = True
            elif isinstance(v_def, (Label, HTMLLabel, sprite.Sprite)):
                if v_def.batch is None:
                    v_def.batch = batch
            elif name not in self.on_batch:
                self._assign_single_legacy(name, v_def)

    def _hide_all_vertices(self) -> None:
        """Hide: set .visible=False on shapes/labels, delete legacy on_batch entries."""
        for name in list(self.vertex.keys()):
            if isinstance(self.vertex[name], ShapeBase):
                self.vertex[name].visible = False
            elif isinstance(self.vertex[name], (Label, HTMLLabel)):
                self.vertex[name].batch = None
            elif name in self.on_batch:
                self.on_batch[name].delete()
                del self.on_batch[name]

    def add_quad(self, name: str, group: Any, positions: tuple | list, colors: tuple | list) -> None:
        """Register a quad (4 vertices, 2 triangles via indexing)."""
        self.vertex[name] = ("quad", group, positions, colors)

    def add_lines(self, name: str, group: Any, positions: tuple | list, colors: tuple | list) -> None:
        """Register GL_LINES segments."""
        self.vertex[name] = ("lines", group, positions, colors)

    def show_aoi_highlight(self) -> None:
        """Add some AOI vertices (frame and text)"""
        if self.container is None:
            return

        if self.highlight_aoi is True:
            self.border_vertice: tuple[float, ...] = self.vertice_border(self.container)
            self.add_lines("highlight", G(self.m_draw + 8), self.vertice_strip(self.border_vertice), C["RED"] * 8)

            self.vertex[self.name] = Label(
                self.name, x=self.container.x1 + 5, y=self.container.y1 - 15, color=C["RED"], group=G(self.m_draw + 8)
            )

    def assign_vertices_to_batch(self) -> None:
        batch = Window.MainWindow.batch
        for name, v_def in self.vertex.items():
            if isinstance(v_def, ShapeBase):
                v_def.batch = batch
            elif isinstance(v_def, (Label, HTMLLabel, sprite.Sprite)):
                v_def.batch = batch
            else:
                self._assign_single_legacy(name, v_def)

    def _assign_single_legacy(self, name: str, v_def: tuple) -> None:
        """Create a legacy on_batch vertex list for a tuple-based vertex definition."""
        program = get_program()
        batch = Window.MainWindow.batch
        kind, group, positions, colors = v_def
        sg = get_group(order=group.order, parent=group.parent)
        count = len(positions) // 2

        if kind == "quad":
            indices = quad_indices(count)
            self.on_batch[name] = program.vertex_list_indexed(
                count, GL_TRIANGLES, indices,
                batch=batch, group=sg,
                position=("f", positions), colors=("Bn", colors),
            )
        elif kind == "lines":
            self.on_batch[name] = program.vertex_list(
                count, GL_LINES, batch=batch, group=sg,
                position=("f", positions), colors=("Bn", colors),
            )

    def empty_batch(self) -> None:
        self._hide_all_vertices()
        self.on_batch = dict()
        self._batch_assigned = False

    def resize_quad(self, name: str, new_count: int) -> None:
        """Resize an indexed quad vertex list, recalculating indices."""
        vlist = self.on_batch[name]
        new_indices = quad_indices(new_count)
        vlist.resize(new_count, len(new_indices))
        vlist.indices[:] = new_indices

    def get_vertex_color(self, vertex_name: str) -> tuple[int, int, int, int]:
        return tuple(self.on_batch[vertex_name].colors[:][0:4])

    def vertice_strip(self, vertice: tuple[float, ...] | list[float]) -> list[float] | None:
        """Develop a list of vertice points to obtain a list of vertice segments"""
        vertice_strip_list: list[float] = list()
        if vertice is not None:
            for i in range((len(vertice) // 2) - 1):
                x1: float = vertice[i * 2]
                y1: float = vertice[i * 2 + 1]
                x2: float = vertice[i * 2 + 2]
                y2: float = vertice[i * 2 + 3]
                [vertice_strip_list.append(c) for c in (x1, y1, x2, y2)]
            x1, y1, x2, y2 = (vertice[-2], vertice[-1], vertice[0], vertice[1])
            [vertice_strip_list.append(c) for c in (x1, y1, x2, y2)]
            return list(vertice_strip_list)
        else:
            return None

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

    def vertice_border(self, container: Container) -> tuple[float, float, float, float, float, float, float, float]:
        c: Container = container
        return c.x1, c.y1, c.x2, c.y1, c.x2, c.y2, c.x1, c.y2

    def remove_all_vertices(self) -> None:
        self.vertex = dict()
