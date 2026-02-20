# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from core.constants import PATHS as P
from core.widgets import SimpleHTML
from plugins.abstractplugin import BlockingPlugin


class Instructions(BlockingPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.folder: str = P["INSTRUCTIONS"]
        new_par: dict[str, Any] = dict(
            filename=None,
            pointsize=0,
            maxdurationsec=0,
            response=dict(text=_("Press SPACE to continue"), key="SPACE"),
            allowkeypress=True,
        )
        self.parameters.update(new_par)

    def make_slide_graphs(self) -> None:
        super().make_slide_graphs()
        self.add_widget(
            "instructions",
            SimpleHTML,
            container=self.container,
            text=self.current_slide,
            wrap_width=0.8,
            draw_order=self.m_draw + 1,
        )
