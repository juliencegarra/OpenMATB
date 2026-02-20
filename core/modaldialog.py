# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from pyglet.gl import GL_BLEND, GL_LINES, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, GL_TRIANGLES, glBlendFunc, glEnable
from pyglet.text import HTMLLabel
from pyglet.window import key as winkey

from core.constants import COLORS as C
from core.constants import Group as G
from core.container import Container
from core.logger import get_logger
from core.rendering import get_group, get_program, polygon_indices
from core.utils import get_conf_value


class ModalDialog:
    def __init__(
        self,
        win: Any,
        msg: str | list[str],
        title: str = "OpenMATB",
        continue_key: str | None = "SPACE",
        exit_key: str | None = None,
    ) -> None:
        # Allow for drawing of transparent vertices
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self.win: Any = win
        self.name: str = title
        self.continue_key: str | None = continue_key
        self.exit_key: str | None = exit_key
        self.hide_on_pause: bool = get_conf_value("Openmatb", "hide_on_pause")

        # Hide background ?
        if self.hide_on_pause:
            MATB_container: Container = self.win.get_container("fullscreen")
            l, b, w, h = MATB_container.get_lbwh()
            program = get_program()
            self.back_vertice: Any | None = program.vertex_list_indexed(
                4,
                GL_TRIANGLES,
                polygon_indices(4),
                batch=self.win.batch,
                group=get_group(order=20),
                position=("f", (l, b + h, l + w, b + h, l + w, b, l, b)),
                colors=("Bn", C["BACKGROUND"] * 4),
            )
        else:
            self.back_vertice = None

        # HTML list definition #
        if isinstance(msg, str):
            msg = [msg]

        html: str = "<center><p><strong><font face=%s>" % "sans"
        html += "%s</font></strong></p></center>" % title
        for m in msg:
            html += "<center><p><font face=%s>" % "sans"
            html += "%s</font></p></center>" % m
        html += "<center><p><em><font face=%s>" % "sans"
        if exit_key is not None:
            html += "[%s]" % _(exit_key.capitalize())
            html += " %s" % _("Exit")

        if continue_key is not None and exit_key is not None:
            html += "  –  "

        if continue_key is not None:
            html += "[%s]" % _(continue_key.capitalize())
            html += " %s" % _("Continue")
        html += "</font></em></p></center>"

        self.html_label: HTMLLabel = HTMLLabel(
            html,
            x=0,
            y=0,
            anchor_x="center",
            anchor_y="center",
            group=G(22),
            batch=self.win.batch,
            multiline=True,
            width=self.win.width,
        )
        # # # # # # # # # # # #

        # Container definition #
        left_right_margin_px: int = 20
        top_bottom_margin_px: int = 10
        # The first, compute the desired container height and width #
        # - Width is the max html width + 2 * left_right_margin
        w: float = self.html_label.content_width + 2 * left_right_margin_px
        # - Line to line computation
        # - Height is number of line * line to line height + 2 margins
        h: float = self.html_label.content_height + 2 * top_bottom_margin_px
        l: float = self.win.width / 2 - w / 2
        b: float = self.win.height / 2 - h / 2
        self.container: Container = Container("ModalDialog", l, b, w, h)
        l, b, w, h = self.container.get_lbwh()

        # Container background
        program = get_program()
        self.back_dialog: Any = program.vertex_list_indexed(
            4,
            GL_TRIANGLES,
            polygon_indices(4),
            batch=self.win.batch,
            group=get_group(order=21),
            position=("f", (l, b + h, l + w, b + h, l + w, b, l, b)),
            colors=("Bn", C["WHITE_TRANSLUCENT"] * 4),
        )

        # Container border
        self.border_dialog: Any = program.vertex_list(
            8,
            GL_LINES,
            batch=self.win.batch,
            group=get_group(order=21),
            position=("f", (l, b + h, l + w, b + h, l + w, b + h, l + w, b, l + w, b, l, b, l, b, l, b + h)),
            colors=("Bn", C["GREY"] * 8),
        )

        # HTMLLabel placement #
        self.html_label.x = self.container.cx
        self.html_label.y = self.container.cy

        self.vertices: list[Any | None] = [self.html_label, self.back_dialog, self.border_dialog, self.back_vertice]

    def on_delete(self) -> None:
        """The user wants to continue. So only delete the modal dialog"""
        for v in self.vertices:
            if v is not None:
                v.delete()
        get_logger().log_manual_entry(f"{self.name} end", key="dialog")
        self.win.modal_dialog = None

    def on_exit(self) -> None:
        """The user requested to exit OpenMATB"""
        self.on_delete()
        self.win.alive = False

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        keystr: str = winkey.symbol_string(symbol)

        if keystr == self.continue_key:
            self.on_delete()

        if self.exit_key is not None and keystr == self.exit_key.upper():
            self.on_exit()
