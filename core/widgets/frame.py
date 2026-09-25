# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from pyglet.shapes import Rectangle

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
        self._border_color: tuple[int, int, int, int] = border_color

        if fill_color is not None:
            self.vertex["fillarea"] = Rectangle(
                x=self.container.x1,
                y=self.container.y2,
                width=self.container.w,
                height=self.container.h,
                color=fill_color[:3],
                batch=None,
                group=G(draw_order),
            )
            self.vertex["fillarea"].opacity = fill_color[3]

        # Four border rectangles (top, bottom, left, right)
        for part in ("top", "bottom", "left", "right"):
            self.vertex[f"border_{part}"] = Rectangle(
                x=0,
                y=0,
                width=0,
                height=0,
                color=border_color[:3],
                batch=None,
                group=G(draw_order + 1),
            )
            self.vertex[f"border_{part}"].opacity = border_color[3]

        self._update_border_rects()

    def _update_border_rects(self) -> None:
        """Recompute border rectangle positions from border_thickness."""
        c = self.container
        if c.w <= 0 or c.h <= 0:
            return
        t = self.border_thickness

        # Top: full width, sits at top of container
        top_cont = c.reduce_and_translate(1, t, 0, 1)
        # Bottom: full width, sits at bottom
        bot_cont = c.reduce_and_translate(1, t, 0, 0)
        # The left/right width is the same pixel size as top height
        lr_w_ratio = top_cont.h / c.w if c.w > 0 else 0
        # Left: full height, sits at left
        lef_cont = c.reduce_and_translate(lr_w_ratio, 1, 0, 0)
        # Right: full height, sits at right
        rig_cont = c.reduce_and_translate(lr_w_ratio, 1, 1, 0)

        for part, cont in [("top", top_cont), ("bottom", bot_cont), ("left", lef_cont), ("right", rig_cont)]:
            shape = self.vertex[f"border_{part}"]
            shape.x = cont.x1
            shape.y = cont.y2
            shape.width = cont.w
            shape.height = cont.h

    def set_border_thickness(self, thickness: float) -> None:
        if thickness == self.get_border_thickness():
            return
        self.border_thickness = thickness
        self.logger.record_state(self.name, "border_thickness", thickness)

        self._update_border_rects()

    def get_border_thickness(self) -> float:
        return self.border_thickness

    def set_border_color(self, color: tuple[int, int, int, int]) -> None:
        if color == self.get_border_color():
            return
        self._border_color = color
        for part in ("top", "bottom", "left", "right"):
            self.vertex[f"border_{part}"].color = color[:3]
            self.vertex[f"border_{part}"].opacity = color[3]
        self.logger.record_state(self.name, "color", color)

    def get_border_color(self) -> tuple[int, int, int, int]:
        return self._border_color

    def set_visibility(self, visible: bool) -> None:
        if visible == self.is_visible():
            return
        self.visible = visible

        for part in ("top", "bottom", "left", "right"):
            self.vertex[f"border_{part}"].visible = visible

        if "fillarea" in self.vertex:
            self.vertex["fillarea"].visible = visible

        self.logger.record_state(self.name, "visibility", visible)
