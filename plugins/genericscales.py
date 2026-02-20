# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from re import match as regex_match
from typing import Any

from pyglet.text import Label as PygletLabel

from core.constants import FONT_SIZES as F
from core.constants import PATHS as P
from core.constants import REPLAY_MODE
from core.container import Container
from core.utils import get_conf_value
from core.widgets import Simpletext, Slider
from plugins.abstractplugin import BlockingPlugin


class Genericscales(BlockingPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.folder: str = P["QUESTIONNAIRES"]
        new_par: dict[str, Any] = dict(
            filename=None,
            pointsize=0,
            maxdurationsec=0,
            response=dict(text=_("Press SPACE to validate"), key="SPACE"),
            allowkeypress=True,
            showvalue=False,
        )
        self.sliders: dict[str, Any] = dict()
        self.selected_slider_index: int = 0
        self.keys.update({"UP", "DOWN", "LEFT", "RIGHT"})
        self.parameters.update(new_par)

        self.ignore_empty_lines: bool = True

        self.regex_scale_pattern: str = r"(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)"
        self.question_height_ratio: float = 0.1  # question + response slider
        self.question_interspace: float = 0.05  # Space to leave between two questions
        self.top_to_top: float = self.question_interspace + self.question_height_ratio

    def _measure_text_height(self, text: str, font_size: int, wrap_width_px: float, bold: bool = False) -> int:
        font_name: str = get_conf_value("Openmatb", "font_name")
        tmp: Any = PygletLabel(
            text, font_size=font_size, multiline=True, width=wrap_width_px, bold=bold, font_name=font_name
        )
        return tmp.content_height

    def make_slide_graphs(self) -> None:
        # Remove old slider/label widgets from previous slide
        for key in list(self.sliders):
            fullname: str = self.get_widget_fullname(key)
            self.widgets.pop(fullname, None)
            label_fullname: str = self.get_widget_fullname(key.replace("slider_", "label_"))
            self.widgets.pop(label_fullname, None)
            title_fullname: str = self.get_widget_fullname(key.replace("slider_", "title_"))
            self.widgets.pop(title_fullname, None)
        self.sliders.clear()

        super().make_slide_graphs()

        scales: list[str] = self.current_slide.split("\n")
        scale_list: list[str] = [s.strip() for s in scales if len(s.strip()) > 0]
        if len(scale_list) == 0:
            return

        all_scales_container: Container = self.container.get_reduced(1, self.top_to_top * (len(scale_list)))

        height_in_prop: float = (self.question_height_ratio * self.container.h) / all_scales_container.h
        for l, scale in enumerate(scale_list):
            # Define the scale main container (question + response slider)
            scale_container: Container = all_scales_container.reduce_and_translate(
                height=height_in_prop, y=1 - (1 / (len(scale_list))) * l
            )

            if regex_match(self.regex_scale_pattern, scale):
                title: str
                label: str
                limit_labels: str
                values: str
                title, label, limit_labels, values = scale.strip().split(";")
                label_min: str
                label_max: str
                label_min, label_max = limit_labels.split("/")
                value_min: int
                value_max: int
                value_default: int
                value_min, value_max, value_default = [int(v) for v in values.split("/")]

                show_title: bool = title != label

                if show_title:
                    wrap_px: float = scale_container.w * 0.8
                    padding: int = 4

                    title_h: float = self._measure_text_height(title, F["MEDIUM"], wrap_px, bold=True) + padding
                    question_h: float = self._measure_text_height(label, F["MEDIUM"], wrap_px) + padding

                    min_slider_h: float = scale_container.h * 0.40
                    slider_h: float = max(min_slider_h, scale_container.h - title_h - question_h)

                    text_budget: float = scale_container.h - slider_h
                    if title_h + question_h > text_budget and text_budget > 0:
                        ratio: float = text_budget / (title_h + question_h)
                        title_h *= ratio
                        question_h *= ratio

                    L: float = scale_container.l
                    B: float = scale_container.b
                    W: float = scale_container.w
                    H: float = scale_container.h
                    title_container: Container = Container("title", L, B + H - title_h, W, title_h)
                    question_container: Container = Container(
                        "question", L, B + H - title_h - question_h, W, question_h
                    )
                    slider_container: Container = Container("slider", L, B, W, slider_h)

                    self.add_widget(
                        f"title_{l + 1}",
                        Simpletext,
                        container=title_container,
                        text=title,
                        wrap_width=0.8,
                        font_size=F["MEDIUM"],
                        bold=True,
                        draw_order=self.m_draw,
                    )
                else:
                    question_container = scale_container.reduce_and_translate(1, 0.4, 0, 1)
                    slider_container = scale_container.reduce_and_translate(1, 0.6, 0, 0)

                self.add_widget(
                    f"label_{l + 1}",
                    Simpletext,
                    container=question_container,
                    text=label,
                    wrap_width=0.8,
                    font_size=F["MEDIUM"],
                    draw_order=self.m_draw,
                )

                self.sliders[f"slider_{l + 1}"] = self.add_widget(
                    f"slider_{l + 1}",
                    Slider,
                    container=slider_container,
                    title=title,
                    label_min=label_min,
                    label_max=label_max,
                    value_min=value_min,
                    value_max=value_max,
                    value_default=value_default,
                    rank=l,
                    draw_order=self.m_draw + 3,
                    interactive=not REPLAY_MODE,
                    showvalue=self.parameters["showvalue"],
                    on_mouse_focus=self._on_slider_mouse_focus,
                )

        if self.sliders:
            self.selected_slider_index = 0
            self._update_slider_selection()

    def _on_slider_mouse_focus(self, rank: int) -> None:
        self.selected_slider_index = rank
        self._update_slider_selection()

    def _update_slider_selection(self) -> None:
        slider_list = list(self.sliders.values())
        for i, slider in enumerate(slider_list):
            slider.set_selected(i == self.selected_slider_index)

    def do_on_key(self, keystr: str, state: str, emulate: bool = False) -> str | None:
        keystr = super().do_on_key(keystr, state, emulate)
        if keystr is None:
            return

        if state != "press":
            return keystr

        slider_list = list(self.sliders.values())
        if not slider_list:
            return keystr

        if keystr.lower() == "up":
            self.selected_slider_index = (self.selected_slider_index - 1) % len(slider_list)
            self._update_slider_selection()
        elif keystr.lower() == "down":
            self.selected_slider_index = (self.selected_slider_index + 1) % len(slider_list)
            self._update_slider_selection()
        elif keystr.lower() == "left":
            slider_list[self.selected_slider_index].adjust_value(-1)
        elif keystr.lower() == "right":
            slider_list[self.selected_slider_index].adjust_value(1)

        return keystr

    def refresh_widgets(self) -> None:
        # Useful for replay mode (refresh groove positions)
        if not super().refresh_widgets():
            return

        for _slider_name, slider in self.sliders.items():
            slider.update()

    def stop(self) -> None:
        for _slider_name, slider_widget in self.sliders.items():
            self.log_performance(slider_widget.get_title(), slider_widget.get_value())
        super().stop()
