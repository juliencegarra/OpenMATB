# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.pyglet_compat import ITALIC
from core.widgets.abstractwidget import *


class Simpletext(AbstractWidget):
    def __init__(
        self,
        name: str,
        container: Any,
        text: str,
        draw_order: int = 1,
        font_size: int | None = None,  # F["SMALL"] (not as a default value: it is scaled to the window)
        x: float = 0.5,
        y: float = 0.5,
        wrap_width: float = 1,
        color: tuple[int, ...] = C["BLACK"],
        bold: bool = False,
        italic: bool = False,
        anchor_x: str = "center",
    ) -> None:
        super().__init__(name, container)

        x_pos: float = self.container.l + x * self.container.w
        y_pos: float = self.container.b + y * self.container.h
        wrap_width_px: float = max(self.container.w * wrap_width, 1)  # pyglet needs a positive width

        label_kwargs: dict = dict(
            font_size=F["SMALL"] if font_size is None else font_size,
            x=x_pos,
            y=y_pos,
            align=anchor_x,  # A right (left) anchored text is aligned on it: its box is the wrap width
            anchor_x=anchor_x,
            anchor_y="center",
            color=color,
            group=G(draw_order),
            multiline=True,
            width=wrap_width_px,
            font_name=self.font_name,
        )
        if bold:
            label_kwargs["weight"] = "bold"
        if italic:
            label_kwargs.update(ITALIC)
        self.vertex["text"] = Label(text, **label_kwargs)

    def set_text(self, text: str) -> None:
        if text == self.get_text():
            return
        self.vertex["text"].text = text
        self.logger.record_state(self.name, "text", text)

    def get_text(self) -> str:
        return self.vertex["text"].text
