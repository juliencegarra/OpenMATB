# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any, Callable

from pyglet.gl import *

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
        button_vertice: tuple[float, ...] = self.vertice_border(self.active_area)

        self.add_vertex(
            "background",
            4,
            GL_QUADS,
            G(self.m_draw + self.m_draw + 1),
            ("v2f/static", button_vertice),
            ("c4B/static", (C["DARKGREY"] * 4)),
        )
        self.add_vertex(
            "border",
            8,
            GL_LINES,
            G(self.m_draw + self.m_draw + 3),
            ("v2f/static", self.vertice_strip(button_vertice)),
            ("c4B/static", (C["BLACK"] * 8)),
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
        HIDDEN: tuple[int, int, int, int] = (255, 255, 255, 0)

        # --- Play triangle (pointing right, 3 vertices) ---
        self.add_vertex(
            "play_tri",
            3,
            GL_TRIANGLES,
            g,
            ("v2f/static", (cx - 0.3 * s, cy + 0.5 * s, cx - 0.3 * s, cy - 0.5 * s, cx + 0.5 * s, cy)),
            ("c4B/dynamic", list(W * 3)),
        )

        # --- Pause bars (2 quads = 8 vertices) ---
        gap: float = 0.1 * s
        bw: float = 0.2 * s
        bh: float = 0.45 * s
        lx1: float = cx - gap - bw
        lx2: float = cx - gap
        rx1: float = cx + gap
        rx2: float = cx + gap + bw
        yt: float = cy + bh
        yb: float = cy - bh
        self.add_vertex(
            "pause_bars",
            8,
            GL_QUADS,
            g,
            ("v2f/static", (lx1, yt, lx2, yt, lx2, yb, lx1, yb, rx1, yt, rx2, yt, rx2, yb, rx1, yb)),
            ("c4B/dynamic", list(HIDDEN * 8)),
        )

        self.show()

    def update_button_sprite(self, is_paused: bool) -> None:
        W: tuple[int, int, int, int] = C["WHITE"]
        HIDDEN: tuple[int, int, int, int] = (255, 255, 255, 0)
        self.on_batch["play_tri"].colors = list(W * 3) if is_paused else list(HIDDEN * 3)
        self.on_batch["pause_bars"].colors = list(HIDDEN * 8) if is_paused else list(W * 8)


class MuteButton(Button):
    """Mute toggle drawn with GL primitives (no image files)."""

    def __init__(self, name: str, container: Container, callback: Callable[[], Any]) -> None:
        super().__init__(name, container, callback)
        self.is_muted: bool = True

        import math

        cx: float = self.container.cx
        cy: float = self.container.cy
        s: float = self.container.h * 0.30
        g: Any = G(self.m_draw + 8)
        W: tuple[int, int, int, int] = C["WHITE"]
        HIDDEN: tuple[int, int, int, int] = (255, 255, 255, 0)

        # --- Speaker body (quad) ---
        bx1: float = cx - 0.8 * s
        bx2: float = cx - 0.3 * s
        byt: float = cy + 0.25 * s
        byb: float = cy - 0.25 * s
        self.add_vertex(
            "spk_body", 4, GL_QUADS, g, ("v2f/static", (bx1, byt, bx2, byt, bx2, byb, bx1, byb)), ("c4B/static", W * 4)
        )

        # --- Speaker cone (quad / trapezoid) ---
        tip_x: float = cx + 0.2 * s
        self.add_vertex(
            "spk_cone",
            4,
            GL_QUADS,
            g,
            ("v2f/static", (bx2, byt, tip_x, cy + 0.55 * s, tip_x, cy - 0.55 * s, bx2, byb)),
            ("c4B/static", W * 4),
        )

        # --- X mark (2 lines = 4 vertices) — visible when muted ---
        xx1: float = cx + 0.35 * s
        xx2: float = cx + 0.85 * s
        xy1: float = cy + 0.45 * s
        xy2: float = cy - 0.45 * s
        self.add_vertex(
            "mute_x",
            4,
            GL_LINES,
            g,
            ("v2f/static", (xx1, xy1, xx2, xy2, xx1, xy2, xx2, xy1)),
            ("c4B/dynamic", list(W * 4)),
        )

        # --- Sound waves (2 arcs) — hidden when muted ---
        arc_cx: float = tip_x
        n_seg: int = 10

        def arc_line_verts(acx: float, acy: float, r: float, start_deg: float, end_deg: float) -> list[float]:
            pts: list[tuple[float, float]] = []
            for i in range(n_seg + 1):
                a: float = math.radians(start_deg + (end_deg - start_deg) * i / n_seg)
                pts.append((acx + r * math.cos(a), acy + r * math.sin(a)))
            verts: list[float] = []
            for i in range(n_seg):
                verts.extend([pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]])
            return verts

        wave1: list[float] = arc_line_verts(arc_cx, cy, 0.45 * s, -45, 45)
        wave2: list[float] = arc_line_verts(arc_cx, cy, 0.70 * s, -45, 45)
        wave_verts: list[float] = wave1 + wave2
        n_wave_pts: int = len(wave_verts) // 2
        self.add_vertex(
            "unmute_waves",
            n_wave_pts,
            GL_LINES,
            g,
            ("v2f/static", wave_verts),
            ("c4B/dynamic", list(HIDDEN * n_wave_pts)),
        )

        self._n_wave_pts: int = n_wave_pts
        self.show()

    def update_mute_state(self, is_muted: bool) -> None:
        self.is_muted = is_muted
        W: tuple[int, int, int, int] = C["WHITE"]
        HIDDEN: tuple[int, int, int, int] = (255, 255, 255, 0)

        self.on_batch["mute_x"].colors = list(W * 4) if is_muted else list(HIDDEN * 4)
        self.on_batch["unmute_waves"].colors = (
            list(HIDDEN * self._n_wave_pts) if is_muted else list(W * self._n_wave_pts)
        )
