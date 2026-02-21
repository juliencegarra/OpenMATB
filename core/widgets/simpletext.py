# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.widgets.abstractwidget import *


class Simpletext(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        text: str,
        draw_order: int = 1,
        font_size: int = F["SMALL"],
        x: float = 0.5,
        y: float = 0.5,
        wrap_width: float = 1,
        color: tuple[int, ...] = C["BLACK"],
        bold: bool = False,
    ) -> None:
        super().__init__(name, container)

        x_pos: float = self.container.l + x * self.container.w
        y_pos: float = self.container.b + y * self.container.h
        wrap_width_px: float = self.container.w * wrap_width

        label_kwargs: dict = dict(
            font_size=font_size,
            x=x_pos,
            y=y_pos,
            align="center",
            anchor_x="center",
            anchor_y="center",
            color=color,
            group=G(draw_order),
            multiline=True,
            width=wrap_width_px,
            font_name=self.font_name,
        )
        if bold:
            label_kwargs["weight"] = "bold"
        self.vertex["text"] = Label(text, **label_kwargs)

    def set_text(self, text: str) -> None:
        if text == self.get_text():
            return
        self.vertex["text"].text = text
        self.logger.record_state(self.name, "text", text)

    def get_text(self) -> str:
        return self.vertex["text"].text
