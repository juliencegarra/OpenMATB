# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from re import fullmatch as regex_fullmatch
from typing import Any

from pyglet.text import Label as PygletLabel

from core import validation
from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.constants import PATHS as P
from core.constants import REPLAY_MODE, scaled
from core.container import Container
from core.utils import get_conf_value
from core.widgets import Simpletext, Slider
from plugins.abstractplugin import BlockingPlugin

# [Short title;]Question;minimumName/maximumName;minimumValue/maximumValue/defaultValue. A line that does not
# match it (e.g. a ; in the question, a missing value) is not a scale, instead of raising during the session
SCALE_PATTERN: str = r"(?:([^;]*);)?([^;]*);([^;/]*)/([^;/]*);(-?\d+)/(-?\d+)/(-?\d+)"


class Genericscales(BlockingPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.folder: str = P["QUESTIONNAIRES"]
        # Its file is read in its folder: checked there (not in the folder of the other blocking plugin)
        self.validation_dict["filename"] = (validation.is_available_text_file, self.folder)
        self.validation_dict["showvalue"] = validation.is_boolean  # Without it, the scenario refused the parameter
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

        self._presentation_count: int = 0
        # Answers of the previous pages of the current presentation, as (title, value)
        self._answers: list[tuple[str, Any]] = list()
        self._first_page: bool = True
        self.ignore_empty_lines: bool = True

        self.regex_scale_pattern: str = SCALE_PATTERN
        # Vertical layout, in proportion of the window height. The scales are stacked with their real height,
        # separated by more space than their own parts (title, question, slider), so that each one reads as a block.
        # A full page first brings its scales closer and thins their sliders (down to the minimum values)
        self.slider_height: tuple[float, float] = (0.05, 0.03)  # (Default, minimum)
        self.scale_gap: tuple[float, float] = (0.05, 0.012)  # Between two scales
        self.title_question_gap: float = 0.006
        # ... then uses smaller titles, then longer lines: (scale title size, question size, maximum text width), the
        # first that fits. Lines of about 100 characters at most (in pixels, as the font sizes) are easier to follow,
        # and the texts never take more than 80% of the window width
        self.text_layouts: list[tuple[int, int, float | None]] = [
            (F["LARGE"], F["MEDIUM"], scaled(1000)),
            (F["MEDIUM"], F["MEDIUM"], scaled(1000)),
            (F["MEDIUM"], F["MEDIUM"], None),
        ]
        # The scales stay between these limits, so as not to cover the page title or the response text
        self.top_limit: dict[bool, float] = {True: 0.84, False: 0.96}  # With / without a page title
        self.bottom_limit: dict[bool, float] = {True: 0.14, False: 0.04}  # With / without a response text

    def start(self) -> None:
        self._presentation_count += 1
        self._answers = list()
        self._first_page = True
        super().start()

    def _measure_text_height(self, text: str, font_size: int, wrap_width_px: float, bold: bool = False) -> int:
        font_name: str = get_conf_value("Openmatb", "font_name")
        kwargs: dict[str, Any] = dict(font_size=font_size, multiline=True, width=wrap_width_px, font_name=font_name)
        if bold:
            kwargs["weight"] = "bold"
        tmp: Any = PygletLabel(text, **kwargs)
        return tmp.content_height

    def make_slide_graphs(self) -> None:
        # Keep the answers of the previous page (its sliders are replaced by the new page ones).
        # The sliders present at the first page come from a previous presentation: already logged
        if not self._first_page:
            self._answers += [(slider.get_title(), slider.get_value()) for slider in self.sliders.values()]
        self._first_page = False

        # Remove old slider/label widgets from previous slide
        for key in list(self.sliders):
            self.sliders[key].remove_mouse_handlers()
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

        # The scales of the page. Their widget names keep their line number
        items: list[dict[str, Any]] = list()
        for l, scale in enumerate(scale_list):
            scale_match = regex_fullmatch(self.regex_scale_pattern, scale)
            if scale_match is None:
                continue
            title: str | None
            title, label, label_min, label_max, *values = scale_match.groups()
            title = label if title is None else title  # Without short title, the question is the title
            value_min, value_max, value_default = [int(v) for v in values]
            if value_min == value_max:  # Not a scale either: the slider divided by zero when the page showed
                continue
            items.append(
                dict(
                    number=l + 1,
                    title=title if title != label else None,
                    label=label,
                    label_min=label_min,
                    label_max=label_max,
                    values=(value_min, value_max, value_default),
                )
            )
        if len(items) == 0:
            return

        # Free area of the page, between its title and its response text (if any)
        H: float = self.container.h
        has_page_title: bool = self.is_a_widget_name("title")
        top: float = self.container.b + H * self.top_limit[has_page_title]
        bottom: float = self.container.b + H * self.bottom_limit[bool(self.parameters.get("allowkeypress"))]
        n: int = len(items)

        # The largest texts whose scales fit in it, with their minimum spacing
        padding: int = 4
        for title_size, question_size, max_width in self.text_layouts:
            wrap_px: float = self.container.w * 0.8 if max_width is None else min(self.container.w * 0.8, max_width)
            for item in items:
                item["title_h"] = (
                    self._measure_text_height(item["title"], title_size, wrap_px, bold=True) + padding
                    if item["title"] is not None
                    else 0
                )
                item["title_gap"] = self.title_question_gap * H if item["title"] is not None else 0
                item["question_h"] = self._measure_text_height(item["label"], question_size, wrap_px) + padding
            text_h: float = sum(item["title_h"] + item["title_gap"] + item["question_h"] for item in items)
            spacing_min: float = (n * self.slider_height[1] + (n - 1) * self.scale_gap[1]) * H
            if text_h + spacing_min <= top - bottom:
                break

        # Then the sliders and the gaps between scales get the remaining space, up to their default size
        spacing_max: float = (n * self.slider_height[0] + (n - 1) * self.scale_gap[0]) * H
        free_ratio: float = (top - bottom - text_h - spacing_min) / (spacing_max - spacing_min)
        free_ratio = max(0.0, min(1.0, free_ratio))
        slider_h: float = H * (self.slider_height[1] + free_ratio * (self.slider_height[0] - self.slider_height[1]))
        gap: float = H * (self.scale_gap[1] + free_ratio * (self.scale_gap[0] - self.scale_gap[1]))
        total_h: float = text_h + n * slider_h + (n - 1) * gap
        # Under a page title, the scales start below it. Otherwise they are centered (from the top if too many)
        y: float = top if has_page_title else min(top, (top + bottom + total_h) / 2)

        L: float = self.container.l
        W: float = self.container.w
        text_l: float = self.container.cx - wrap_px / 2
        for item in items:
            number: int = item["number"]
            title = item["title"] if item["title"] is not None else item["label"]
            if item["title"] is not None:
                y -= item["title_h"]
                self.add_widget(
                    f"title_{number}",
                    Simpletext,
                    container=Container("title", text_l, y, wrap_px, item["title_h"]),
                    text=title,
                    font_size=title_size,
                    bold=True,
                    draw_order=self.m_draw,
                )
                y -= item["title_gap"]

            y -= item["question_h"]
            self.add_widget(
                f"label_{number}",
                Simpletext,
                container=Container("question", text_l, y, wrap_px, item["question_h"]),
                text=item["label"],
                font_size=question_size,
                draw_order=self.m_draw,
            )

            y -= slider_h
            value_min, value_max, value_default = item["values"]
            self.sliders[f"slider_{number}"] = self.add_widget(
                f"slider_{number}",
                Slider,
                container=Container("slider", L, y, W, slider_h),
                title=title,
                label_min=item["label_min"],
                label_max=item["label_max"],
                value_min=value_min,
                value_max=value_max,
                value_default=value_default,
                rank=len(self.sliders),  # Position among the sliders (not among the lines of the page)
                draw_order=self.m_draw + 3,
                interactive=not REPLAY_MODE,
                showvalue=self.parameters["showvalue"],
                on_mouse_focus=self._on_slider_mouse_focus,
            )
            y -= gap

        if self.sliders:
            self.selected_slider_index = 0
            self._update_slider_selection()

    def make_response_widget(self, name: str) -> None:
        # A secondary text: smaller and lighter than the questions
        self.add_widget(
            name,
            Simpletext,
            container=self.container,
            text=self.parameters["response"]["text"],
            wrap_width=0.5,
            y=0.07,  # Lower than in the instructions: more space for the scales, and a clear margin above it
            font_size=F["MEDIUM"],
            color=C["TEXTGREY"],
            italic=True,
            draw_order=self.m_draw + 1,
        )

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
        if not self.alive:  # e.g. the genericscales;stop of a scenario, once the questionnaire is over: logged
            super().stop()
            return
        self.log_performance("presentation_number", self._presentation_count)
        # No page shown yet in this presentation: the sliders (if any) are those of a previous one
        current: list[tuple[str, Any]] = (
            [] if self._first_page else [(slider.get_title(), slider.get_value()) for slider in self.sliders.values()]
        )
        answers: list[tuple[str, Any]] = self._answers + current
        for title, value in answers:
            self.log_performance(title, value)
        for slider in self.sliders.values():  # The questionnaire has ended: its sliders no longer follow the mouse
            slider.remove_mouse_handlers()
        super().stop()
