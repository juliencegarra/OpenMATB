# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.constants import COLORS as C
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget


class Frame(AbstractWidget):
    """
    This widget is a simple frame that surrounds the task. It has a given color and thickness,
    and can be shown or hidden to generate various feedback effects (blinking alarm, colorful feedback).
    """

    def __init__(
        self,
        name: str,
        container: Container,
        fill_color: tuple[int, int, int, int] | None = C["BACKGROUND"],
        border_color: tuple[int, int, int, int] = C["BACKGROUND"],
        border_thickness: float = 0,
        draw_order: int = 1,
    ) -> None:
        super().__init__(name, container)

        self.border_thickness: float = border_thickness

        if fill_color is not None:
            self.add_quad("fillarea", G(draw_order), (0,) * 8, fill_color * 4)

        self.add_quad("border", G(draw_order + 1), (0,) * 32, border_color * 16)

    def get_border_vertices(self) -> tuple[float, ...]:
        # Left and right rectangles inherit top and bottom thickness
        t_b_th: float = self.border_thickness
        top_container: Container = self.container.reduce_and_translate(1, t_b_th, 0, 1)

        # So top height is left/right width. Thickness is just this width expressed as
        # the main container width ratio
        _: float
        left_right_w: float
        _, _, _, left_right_w = top_container.get_lbwh()
        l_r_th: float = left_right_w / self.container.w

        top_vertices: tuple[float, ...] = self.vertice_border(top_container)
        bot_vertices: tuple[float, ...] = self.vertice_border(self.container.reduce_and_translate(1, t_b_th, 0, 0))
        lef_vertices: tuple[float, ...] = self.vertice_border(self.container.reduce_and_translate(l_r_th, 1, 0, 0))
        rig_vertices: tuple[float, ...] = self.vertice_border(self.container.reduce_and_translate(l_r_th, 1, 1, 0))
        return top_vertices + bot_vertices + lef_vertices + rig_vertices

    def set_border_thickness(self, thickness: float) -> None:
        if thickness == self.get_border_thickness():
            return
        self.border_thickness = thickness
        self.logger.record_state(self.name, "border_thickness", thickness)

        if self.is_visible():
            self.on_batch["border"].position[:] = self.get_border_vertices()

    def get_border_thickness(self) -> float:
        return self.border_thickness

    def set_border_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_border_color():
            return
        self.on_batch["border"].colors[:] = color * 16
        self.logger.record_state(self.name, "color", color)

    def get_border_color(self) -> tuple[int, int, int, int]:
        return self.get_vertex_color("border")

    def set_visibility(self, visible: bool) -> None:
        if visible == self.is_visible():
            return
        self.visible = visible

        if "border" in self.on_batch:
            v: tuple[float, ...] | tuple[int, ...] = self.get_border_vertices() if self.is_visible() else (0,) * 32
            self.on_batch["border"].position[:] = v

        if "fillarea" in self.on_batch:
            v = self.vertice_border(self.container) if self.is_visible() else (0,) * 8
            self.on_batch["fillarea"].position[:] = v

        self.logger.record_state(self.name, "visibility", visible)
