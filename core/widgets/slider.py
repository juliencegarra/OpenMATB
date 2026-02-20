# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any, Callable

from pyglet.gl import GL_BLEND, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, glBlendFunc, glEnable, glLineWidth
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.container import Container
from core.rendering import line_loop_to_lines
from core.widgets import AbstractWidget
from core.window import Window


class Slider(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        title: str,
        label_min: str,
        label_max: str,
        value_min: float,
        value_max: float,
        value_default: float,
        rank: int,
        draw_order: int = 1,
        interactive: bool = True,
        showvalue: bool = True,
        on_mouse_focus: Callable[[int], Any] | None = None,
    ) -> None:
        super().__init__(name, container)

        self.title: str = title
        self.label_min: str = label_min
        self.label_max: str = label_max
        self.showvalue: bool = showvalue
        self.value_min: float = value_min
        self.value_max: float = value_max
        self.value_default: float = value_default
        self.draw_order: int = draw_order

        self.rank: int = rank
        self.groove_value: float = self.value_default
        self.hover: bool = False
        self.selected: bool = False
        self.on_mouse_focus: Callable[[int], Any] | None = on_mouse_focus

        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        glLineWidth(3)

        self.containers: dict[str, Container] = dict()
        self.set_sub_containers()
        self.set_slider_thumb_and_groove()
        self.show()

        if interactive:
            Window.MainWindow.push_handlers(self.on_mouse_press, self.on_mouse_drag, self.on_mouse_release)

    def set_sub_containers(self, slider_width: float = 0.6) -> None:
        l: float = self.container.l
        n_labels: int = 3 if self.showvalue else 2
        label_w: float = self.container.w * (1 - slider_width) / n_labels
        slider_w: float = self.container.w * slider_width

        self.containers = dict()
        names: list[str] = ["min", "slide", "max"]
        bounds: list[float] = [l, l + label_w, l + label_w + slider_w, l + label_w + slider_w + label_w]
        for c, name in enumerate(names):
            left: float = bounds[c]
            right: float = bounds[c + 1]
            self.containers[name] = Container(
                f"container_{name}", left, self.container.b, right - left, self.container.h
            )
        if self.showvalue:
            self.containers["value"] = Container(
                "container_value", bounds[3], self.container.b, label_w, self.container.h
            )
        for name in ["min", "max"]:
            x: float = self.containers[name].cx
            y: float = self.containers[name].cy
            self.vertex[name] = Label(
                getattr(self, f"label_{name}"),
                font_name=self.font_name,
                align="center",
                anchor_x="center",
                anchor_y="center",
                x=x,
                y=y,
                color=C["BLACK"],
                group=G(self.draw_order),
                font_size=F["MEDIUM"],
            )
        if self.showvalue:
            x = self.containers["value"].cx
            y = self.containers["value"].cy
            self.vertex["value"] = Label(
                str(self.groove_value),
                align="center",
                anchor_x="center",
                anchor_y="center",
                x=x,
                y=y,
                color=C["BLACK"],
                group=G(self.draw_order),
                font_size=F["MEDIUM"],
                font_name=self.font_name,
            )

    def set_slider_thumb_and_groove(self) -> None:
        slider_groove_h: float = 0.2
        slider_thumb_h: float = 0.05
        slider_thumb_w: float = 0.9

        self.containers["thumb"] = self.containers["slide"].get_reduced(slider_thumb_w, slider_thumb_h)

        # The groove container comprises the whole groove movements area
        self.containers["allgroove"] = self.containers["slide"].get_reduced(slider_thumb_w, slider_groove_h)

        v1: tuple[float, ...] = self.vertice_border(self.containers["thumb"])
        self.add_quad("thumb", G(self.draw_order + self.rank), v1, C["GREY"] * 4)

        v2: list[float] = self.get_groove_vertices()
        self.add_polygon("groove_b", G(self.draw_order + self.rank), v2, C["BLUE"] * (len(v2) // 2))
        self.add_line_loop("groove", G(self.draw_order + self.rank), v2, C["BLACK"] * (len(v2) // 2))

    def get_groove_vertices(self) -> list[float]:
        groove_radius: float = self.containers["allgroove"].h
        center_ratio: float = (self.groove_value - self.value_min) / (self.value_max - self.value_min)
        x: float = self.containers["allgroove"].l + center_ratio * self.containers["allgroove"].w
        y: float = self.containers["allgroove"].cy
        return self.vertice_circle([x, y], groove_radius)

    def set_groove_position(self) -> None:
        new_verts: list[float] = self.get_groove_vertices()
        if new_verts == self.get_positions("groove_b"):
            return
        self.on_batch["groove_b"].position[:] = new_verts
        new_line_pos, _ = line_loop_to_lines(new_verts)
        self.on_batch["groove"].position[:] = new_line_pos

    def set_value_label(self) -> None:
        if not self.showvalue:
            return
        display_value: str = str(round(self.groove_value))
        if display_value == self.vertex["value"].text:
            return
        self.vertex["value"].text = display_value

    # TODO: hide cursor when finished
    def coordinates_in_groove_container(self, x: float, y: float) -> bool:
        return self.containers["allgroove"].contains_xy(x, y)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self.containers["slide"].contains_xy(x, y) and self.hover is False:
            self.hover = True
            self.update_cursor_appearance()
            if self.on_mouse_focus is not None:
                self.on_mouse_focus(self.rank)
            # Jump groove to click position
            x_min: float = self.containers["allgroove"].l
            x_max: float = self.containers["allgroove"].l + self.containers["allgroove"].w
            clamped_x: float = min(x_max, max(x_min, x))
            ratio: float = (clamped_x - x_min) / (x_max - x_min)
            self.update_groove_value(ratio)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self.hover is True:
            self.hover = False
            self.update_cursor_appearance()

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, button: int, modifiers: int) -> None:
        if self.hover is True:
            x_min: float = self.containers["allgroove"].l
            x_max: float = self.containers["allgroove"].l + self.containers["allgroove"].w
            x = min(x_max, max(x_min, x))
            ratio: float = (x - x_min) / (x_max - x_min)
            self.update_groove_value(ratio)

    def update_groove_value(self, ratio: float) -> None:
        val: float = float(ratio * (self.value_max - self.value_min) + self.value_min)
        if math.isclose(val, self.groove_value):
            return
        self.groove_value = val
        self.logger.record_state(self.name, "value", str(val))
        self.update()

    def get_title(self) -> str:
        return self.title

    def get_value(self) -> float:
        return self.groove_value

    def update_cursor_appearance(self) -> None:
        if self.hover is True:
            cursor: Any = Window.MainWindow.get_system_mouse_cursor(Window.MainWindow.CURSOR_SIZE_LEFT_RIGHT)
        else:
            cursor = Window.MainWindow.get_system_mouse_cursor(Window.MainWindow.CURSOR_DEFAULT)
        Window.MainWindow.set_mouse_cursor(cursor)

    def set_selected(self, is_selected: bool) -> None:
        self.selected = is_selected
        if self.visible and "thumb" in self.on_batch:
            color = C["BLUE"] if is_selected else C["GREY"]
            self.on_batch["thumb"].colors = color * 4
        if self.visible and "groove" in self.on_batch:
            outline = C["BLUE"] if is_selected else C["BLACK"]
            n_verts = len(self.on_batch["groove"].colors) // 4
            self.on_batch["groove"].colors = outline * n_verts

    def adjust_value(self, steps: int) -> None:
        step_size: float = (self.value_max - self.value_min) / 20
        current_step: int = round((self.groove_value - self.value_min) / step_size)
        new_value: float = self.value_min + (current_step + steps) * step_size
        new_value = max(self.value_min, min(self.value_max, new_value))
        ratio: float = (new_value - self.value_min) / (self.value_max - self.value_min)
        self.update_groove_value(ratio)

    def update(self) -> None:
        if self.visible:
            self.set_groove_position()
            self.set_value_label()

    def hide(self) -> None:
        super().hide()
        Window.MainWindow.slider_visible = False

    def show(self) -> None:
        super().show()
        Window.MainWindow.slider_visible = True
