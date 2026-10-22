# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from typing import Any, Callable

from pyglet.shapes import Arc, Circle, Rectangle
from pyglet.text import Label

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import Group as G
from core.constants import scaled
from core.container import Container
from core.widgets import AbstractWidget
from core.window import Window


class Slider(AbstractWidget):
    mirrored: bool = False  # Minimum on the right, for a right-to-left language

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
        slider_width: float = 0.5,  # Proportion of the container taken by the slide, between its bounds
        mirrored: bool = False,
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
        self.mirrored = mirrored

        self.rank: int = rank
        self.groove_value: float = self.value_default
        self.hover: bool = False
        self.selected: bool = False
        self.on_mouse_focus: Callable[[int], Any] | None = on_mouse_focus

        self.containers: dict[str, Container] = dict()
        self.set_sub_containers(slider_width)
        self.set_slider_thumb_and_groove()
        self.show()

        if interactive:
            Window.MainWindow.push_handlers(self.on_mouse_press, self.on_mouse_drag, self.on_mouse_release)

    track_width: float = 0.9  # Proportion of the slide container, between the bounds
    groove_height: float = 0.2  # Proportion of the slide container (also the groove radius)

    def set_sub_containers(self, slider_width: float = 0.5) -> None:
        l: float = self.container.l
        n_labels: int = 3 if self.showvalue else 2
        label_w: float = self.container.w * (1 - slider_width) / n_labels
        slider_w: float = self.container.w * slider_width

        self.containers = dict()
        names: list[str] = ["min", "slide", "max"] + (["value"] if self.showvalue else [])
        if self.mirrored:  # From the right: min, slide, max, value
            names.reverse()
        left: float = l
        for name in names:
            width: float = slider_w if name == "slide" else label_w
            self.containers[name] = Container(f"container_{name}", left, self.container.b, width, self.container.h)
            left += width
        # The bounds are next to the ends of the track, beyond the groove radius (they were centered in their column):
        # the one on the left is right-aligned, the one on the right left-aligned (the minimum on the right if mirrored)
        slide: Container = self.containers["slide"]
        track_inset: float = slide.w * (1 - self.track_width) / 2
        bound_gap: float = slide.h * self.groove_height + scaled(12)
        left_bound, right_bound = ("max", "min") if self.mirrored else ("min", "max")
        bound_x: dict[str, float] = {
            left_bound: slide.l + track_inset - bound_gap,
            right_bound: slide.l + slide.w - track_inset + bound_gap,
        }
        for name, anchor in [(left_bound, "right"), (right_bound, "left")]:
            self.vertex[name] = Label(
                getattr(self, f"label_{name}"),
                font_name=self.font_name,
                anchor_x=anchor,
                anchor_y="center",
                x=bound_x[name],
                y=slide.cy,
                color=C["TEXTGREY"],
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
        slider_groove_h: float = self.groove_height
        slider_thumb_h: float = 0.05
        slider_thumb_w: float = self.track_width

        self.containers["thumb"] = self.containers["slide"].get_reduced(slider_thumb_w, slider_thumb_h)

        # The groove container comprises the whole groove movements area
        self.containers["allgroove"] = self.containers["slide"].get_reduced(slider_thumb_w, slider_groove_h)

        tc = self.containers["thumb"]
        self.vertex["thumb"] = Rectangle(
            x=tc.x1,
            y=tc.y2,
            width=tc.w,
            height=tc.h,
            color=C["GREY"],
            batch=None,
            group=G(self.draw_order + self.rank),
        )

        self._groove_radius: float = self.containers["allgroove"].h
        gx, gy = self._get_groove_center()
        self.vertex["groove_b"] = Circle(
            x=gx,
            y=gy,
            radius=self._groove_radius,
            segments=30,
            color=C["BLUE"],
            batch=None,
            group=G(self.draw_order + self.rank),
        )
        self.vertex["groove"] = Arc(
            x=gx,
            y=gy,
            radius=self._groove_radius,
            segments=30,
            color=C["BLACK"],
            batch=None,
            group=G(self.draw_order + self.rank),
        )

    def _get_groove_center(self) -> tuple[float, float]:
        center_ratio: float = (self.groove_value - self.value_min) / (self.value_max - self.value_min)
        if self.mirrored:
            center_ratio = 1 - center_ratio
        x: float = self.containers["allgroove"].l + center_ratio * self.containers["allgroove"].w
        y: float = self.containers["allgroove"].cy
        return x, y

    def set_groove_position(self) -> None:
        gx, gy = self._get_groove_center()
        groove_b = self.vertex["groove_b"]
        groove = self.vertex["groove"]
        if math.isclose(groove_b.x, gx) and math.isclose(groove_b.y, gy):
            return
        groove_b.x = gx
        groove_b.y = gy
        groove.x = gx
        groove.y = gy

    def set_value_label(self) -> None:
        if not self.showvalue:
            return
        display_value: str = str(round(self.groove_value))
        if display_value == self.vertex["value"].text:
            return
        self.vertex["value"].text = display_value

    def coordinates_in_groove_container(self, x: float, y: float) -> bool:
        return self.containers["allgroove"].contains_xy(x, y)

    def remove_mouse_handlers(self) -> None:
        """Stop following the mouse (the slider is no longer used: page changed, questionnaire ended)."""
        Window.MainWindow.remove_handlers(self.on_mouse_press, self.on_mouse_drag, self.on_mouse_release)

    def is_active(self) -> bool:
        # Hidden (e.g. the questionnaire has ended) or under the pause dialog: the mouse is not for the slider
        return self.visible and Window.MainWindow.modal_dialog is None

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        if not self.is_active():
            return
        if self.containers["slide"].contains_xy(x, y) and self.hover is False:
            self.hover = True
            self.update_cursor_appearance()
            if self.on_mouse_focus is not None:
                self.on_mouse_focus(self.rank)
            # Jump groove to click position
            self.update_groove_value(self._ratio_at(x))

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self.hover is True:
            self.hover = False
            self.update_cursor_appearance()

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, button: int, modifiers: int) -> None:
        if self.hover is True and self.is_active():
            self.update_groove_value(self._ratio_at(x))

    def _ratio_at(self, x: float) -> float:
        """The position of x in the groove, from the minimum (0) to the maximum (1)."""
        x_min: float = self.containers["allgroove"].l
        x_max: float = self.containers["allgroove"].l + self.containers["allgroove"].w
        x = min(x_max, max(x_min, x))
        ratio: float = (x - x_min) / (x_max - x_min)
        return 1 - ratio if self.mirrored else ratio

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
        if self.visible and "thumb" in self.vertex:
            color = C["BLUE"] if is_selected else C["GREY"]
            self.vertex["thumb"].color = color[:3]
            self.vertex["thumb"].opacity = color[3]
        if self.visible and "groove" in self.vertex:
            outline = C["BLUE"] if is_selected else C["BLACK"]
            self.vertex["groove"].color = outline[:3]
            self.vertex["groove"].opacity = outline[3]

    def adjust_value(self, steps: int) -> None:
        step_size: float = (self.value_max - self.value_min) / 20
        current_step: int = round((self.groove_value - self.value_min) / step_size)
        new_value: float = self.value_min + (current_step + steps) * step_size
        # Between the bounds, whatever their order (a reversed scale, e.g. 100/0/50, stuck at one end)
        low, high = sorted((self.value_min, self.value_max))
        new_value = max(low, min(high, new_value))
        ratio: float = (new_value - self.value_min) / (self.value_max - self.value_min)
        self.update_groove_value(ratio)

    def update(self) -> None:
        if self.visible:
            self.set_groove_position()
            self.set_value_label()

    def hide(self) -> None:
        if self.hover:
            self.hover = False
            self.update_cursor_appearance()
        super().hide()
        Window.MainWindow.slider_visible = False

    def show(self) -> None:
        super().show()
        Window.MainWindow.slider_visible = True
