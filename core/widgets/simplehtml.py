# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from pyglet.resource import FileLocation

from core.constants import FONT_SIZES as F
from core.utils import get_conf_value
from core.widgets.abstractwidget import *


class SimpleHTML(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        text: str,
        draw_order: int = 1,
        x: float = 0.5,
        y: float = 0.5,
        wrap_width: float = 1,
    ) -> None:
        super().__init__(name, container)
        self.font_name: str = get_conf_value("Openmatb", "font_name")
        text = self.preparse(text)

        x_pos: int = int(self.container.l + x * self.container.w)
        y_pos: int = int(self.container.b + y * self.container.h)
        wrap_width_px: int = int(self.container.w * wrap_width)

        self.vertex["text"] = HTMLLabel(
            text,
            x=x_pos,
            y=y_pos,
            anchor_x="center",
            anchor_y="center",
            group=G(draw_order),
            multiline=True,
            width=wrap_width_px,
            location=FileLocation("includes/img"),
        )

    def preparse(self, text: str) -> str:
        pars_dict: dict[str, str] = {
            "<h1>": f"<center><strong><font real_size={F['XLARGE']} face={self.font_name}>",
            "</h1>": "</font></strong></center><br>",
            "<h2>": f"<center><font real_size={F['XLARGE']} face={self.font_name}><em>",
            "</h2>": "</em></font></center><br>",
            "<p>": f"<p><font real_size={F['LARGE']} face={self.font_name}>",
            "</p>": "</font></p>",
        }

        for b in ["<h1>", "<h2>", "<p>"]:
            for bb in [b, b.replace("<", "</")]:
                text = text.replace(bb, pars_dict[bb])
        return text

    def set_text(self, text: str) -> None:
        if text == self.get_text():
            return
        self.vertex["text"].text = self.preparse(text)
        self.logger.record_state(self.name, "text", text)

    def get_text(self) -> str:
        return self.vertex["text"].text
