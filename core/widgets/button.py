# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any, Callable

from pyglet.shapes import Line, Rectangle, Triangle

from core.constants import COLORS as C
from core.constants import Group as G
from core.container import Container
from core.widgets import AbstractWidget
from core.window import Window


class Button(AbstractWidget):
    def __init__(self, name: str, container: Container, callback: Callable[[], Any]) -> None:
        super().__init__(name, container)

        self.padding: float = 0.1
        self.hover: bool = False
        self.callback: Callable[[], Any] = callback

        # Draw the button
        self.active_area: Container = self.container.get_reduced(1 - self.padding, 1 - self.padding)

        aa = self.active_area
        ax1, ay1, ax2, ay2 = aa.get_x1y1x2y2()

        self.vertex["background"] = Rectangle(
            x=ax1,
            y=ay2,
            width=aa.w,
            height=aa.h,
            color=C["DARKGREY"][:3],
            batch=None,
            group=G(self.m_draw + self.m_draw + 1),
        )

        for bname, coords in [
            ("border_top", (ax1, ay1, ax2, ay1)),
            ("border_right", (ax2, ay1, ax2, ay2)),
            ("border_bottom", (ax2, ay2, ax1, ay2)),
            ("border_left", (ax1, ay2, ax1, ay1)),
        ]:
            self.vertex[bname] = Line(
                *coords,
                color=C["BLACK"],
                batch=None,
                group=G(self.m_draw + self.m_draw + 2),
            )

        Window.MainWindow.push_handlers(self.on_mouse_press, self.on_mouse_release)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self.mouse_is_in_active_area(x, y) and not self.hover:
            self.hover = True

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if self.hover:
            self.on_mouse_click()
            self.hover = False

    def mouse_is_in_active_area(self, x: int, y: int) -> bool:
        return self.active_area.contains_xy(x, y)

    def on_mouse_click(self) -> Any:
        if self.verbose:
            print(self.name, "Click")
        return self.callback()


class PlayPause(Button):
    """Play/Pause toggle drawn with GL primitives (no image files)."""

    def __init__(self, name: str, container: Container, callback: Callable[[], Any]) -> None:
        super().__init__(name, container, callback)

        cx: float = self.container.cx
        cy: float = self.container.cy
        s: float = self.container.h * 0.35
        g: Any = G(self.m_draw + 8)
        W: tuple[int, int, int, int] = C["WHITE"]

        # --- Play triangle (pointing right) ---
        self.vertex["play_tri"] = Triangle(
            cx - 0.3 * s,
            cy + 0.5 * s,
            cx - 0.3 * s,
            cy - 0.5 * s,
            cx + 0.5 * s,
            cy,
            color=W,
            batch=None,
            group=g,
        )

        # --- Pause bars (2 rectangles) ---
        gap: float = 0.1 * s
        bw: float = 0.2 * s
        bh: float = 0.45 * s
        self.vertex["pause_left"] = Rectangle(
            x=cx - gap - bw,
            y=cy - bh,
            width=bw,
            height=2 * bh,
            color=W,
            batch=None,
            group=g,
        )
        self.vertex["pause_left"].visible = False

        self.vertex["pause_right"] = Rectangle(
            x=cx + gap,
            y=cy - bh,
            width=bw,
            height=2 * bh,
            color=W,
            batch=None,
            group=g,
        )
        self.vertex["pause_right"].visible = False

        self.show()

    def update_button_sprite(self, is_paused: bool) -> None:
        self.vertex["play_tri"].visible = is_paused
        self.vertex["pause_left"].visible = not is_paused
        self.vertex["pause_right"].visible = not is_paused


class MuteButton(Button):
    """Mute toggle drawn with GL primitives (no image files)."""

    def __init__(self, name: str, container: Container, callback: Callable[[], Any]) -> None:
        super().__init__(name, container, callback)
        self.is_muted: bool = True

        cx: float = self.container.cx
        cy: float = self.container.cy
        s: float = self.container.h * 0.30
        g: Any = G(self.m_draw + 8)
        W: tuple[int, int, int, int] = C["WHITE"]

        # --- Speaker body (rectangle) ---
        bx1: float = cx - 0.8 * s
        bx2: float = cx - 0.3 * s
        byt: float = cy + 0.25 * s
        byb: float = cy - 0.25 * s
        self.vertex["spk_body"] = Rectangle(
            x=bx1,
            y=byb,
            width=bx2 - bx1,
            height=byt - byb,
            color=W,
            batch=None,
            group=g,
        )

        # --- Speaker cone (triangle / trapezoid approximation) ---
        tip_x: float = cx + 0.2 * s
        self.vertex["spk_cone"] = Triangle(
            bx2,
            byt,
            tip_x,
            cy + 0.55 * s,
            tip_x,
            cy - 0.55 * s,
            color=W,
            batch=None,
            group=g,
        )
        # Second triangle to fill the quad shape
        self.vertex["spk_cone2"] = Triangle(
            bx2,
            byt,
            tip_x,
            cy - 0.55 * s,
            bx2,
            byb,
            color=W,
            batch=None,
            group=g,
        )

        # --- X mark (2 lines) — visible when muted ---
        xx1: float = cx + 0.35 * s
        xx2: float = cx + 0.85 * s
        xy1: float = cy + 0.45 * s
        xy2: float = cy - 0.45 * s
        self.vertex["mute_x1"] = Line(
            xx1,
            xy1,
            xx2,
            xy2,
            color=W,
            batch=None,
            group=g,
        )
        self.vertex["mute_x2"] = Line(
            xx1,
            xy2,
            xx2,
            xy1,
            color=W,
            batch=None,
            group=g,
        )

        # --- Sound waves (2 arcs) — hidden when muted ---
        from pyglet.shapes import Arc

        arc_cx: float = tip_x
        self.vertex["wave1"] = Arc(
            x=arc_cx,
            y=cy,
            radius=0.45 * s,
            segments=10,
            angle=90.0,
            start_angle=-45.0,
            color=W,
            batch=None,
            group=g,
        )
        self.vertex["wave1"].visible = False

        self.vertex["wave2"] = Arc(
            x=arc_cx,
            y=cy,
            radius=0.70 * s,
            segments=10,
            angle=90.0,
            start_angle=-45.0,
            color=W,
            batch=None,
            group=g,
        )
        self.vertex["wave2"].visible = False

        self.show()

    def update_mute_state(self, is_muted: bool) -> None:
        self.is_muted = is_muted
        # X mark visible when muted
        self.vertex["mute_x1"].visible = is_muted
        self.vertex["mute_x2"].visible = is_muted
        # Waves visible when unmuted
        self.vertex["wave1"].visible = not is_muted
        self.vertex["wave2"].visible = not is_muted
