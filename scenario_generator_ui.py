#! .venv/bin/python3.9
# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Pyglet 2.x UI for the OpenMATB Scenario Generator.

Launch:  python scenario_generator_ui.py
"""

from __future__ import annotations

import configparser
import gettext
import json
import time as _time
from pathlib import Path
from typing import Any, Callable

import pyglet
from pyglet import shapes
from pyglet.gl import GL_SCISSOR_TEST, glClearColor, glDisable, glEnable, glScissor
from pyglet.text import Label
from pyglet.window import key as winkey, mouse

# ── i18n bootstrap (same as scenario_generator.py) ──────────────────────────

_cfg = configparser.ConfigParser()
_cfg.read("config.ini")
_locale_path = Path(".", "locales")
_lang = gettext.translation("openmatb", _locale_path, [_cfg["Openmatb"]["language"]])
_lang.install()

from scenario_generation import (
    BlockConfig, InterBlockEvent, ScenarioConfig,
    format_scenario_lines, generate_scenario, write_scenario_file,
)

# ── Colour palette ───────────────────────────────────────────────────────────

COL_BG = (240, 240, 240)
COL_PANEL = (255, 255, 255)
COL_ACCENT = (50, 120, 215)
COL_ACCENT_HOVER = (30, 100, 195)
COL_SLIDER_TRACK = (200, 200, 200)
COL_SLIDER_THUMB = (50, 120, 215)
COL_TOGGLE_ON = (80, 180, 120)
COL_TOGGLE_OFF = (180, 180, 180)
COL_TEXT = (50, 50, 50, 255)
COL_TEXT_LIGHT = (130, 130, 130, 255)
COL_INPUT_BG = (245, 245, 245)
COL_INPUT_BORDER = (180, 180, 180)
COL_WHITE = (255, 255, 255, 255)
COL_GREEN_BTN = (46, 139, 87)
COL_GREEN_HOVER = (36, 119, 77)
COL_RED_BTN = (200, 60, 60)
COL_RED_HOVER = (170, 40, 40)
COL_BLOCK_BG = (248, 248, 252)
COL_BLOCK_BORDER = (210, 210, 220)
COL_OVERLAY_DIM = (0, 0, 0, 120)
COL_OVERLAY_BG = (255, 255, 255)
COL_WARN = (220, 160, 0, 255)
COL_INTERBLOCK_BG = (230, 240, 255)
COL_INTERBLOCK_BORDER = (170, 190, 220)

FONT = "Segoe UI"
FONT_FALLBACK = ""  # pyglet default


# ══════════════════════════════════════════════════════════════════════════════
#  Custom lightweight widgets — built with pyglet.shapes + pyglet.text.Label
# ══════════════════════════════════════════════════════════════════════════════


class UISlider:
    """Horizontal slider with track, thumb, and value label."""

    def __init__(self, x: int, y: int, width: int, label_text: str,
                 min_val: float, max_val: float, step: float, value: float,
                 batch: pyglet.graphics.Batch, fmt: str = "{:.0f}",
                 suffix: str = "", on_change: Callable | None = None):
        self.x, self.y, self.width = x, y, width
        self.min_val, self.max_val, self.step = min_val, max_val, step
        self._value = self._snap(value)
        self.fmt, self.suffix = fmt, suffix
        self.on_change = on_change
        self._dragging = False

        track_y = y + 8
        self.label = Label(label_text, x=x, y=y + 28, font_name=FONT,
                           font_size=11, color=COL_TEXT, batch=batch)
        self.track = shapes.Rectangle(x, track_y, width, 4,
                                      color=COL_SLIDER_TRACK, batch=batch)
        self.thumb = shapes.Circle(self._thumb_x(), track_y + 2, 8,
                                   color=COL_SLIDER_THUMB, batch=batch)
        self.val_label = Label(self._format(), x=x + width + 8, y=y + 6,
                               font_name=FONT, font_size=11, color=COL_TEXT,
                               batch=batch)
        self._shapes = [self.label, self.track, self.thumb, self.val_label]

    def _snap(self, v: float) -> float:
        v = max(self.min_val, min(self.max_val, v))
        return round(round((v - self.min_val) / self.step) * self.step + self.min_val, 6)

    def _thumb_x(self) -> float:
        ratio = (self._value - self.min_val) / (self.max_val - self.min_val) if self.max_val != self.min_val else 0
        return self.x + ratio * self.width

    def _format(self) -> str:
        return self.fmt.format(self._value) + self.suffix

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = self._snap(v)
        self.thumb.x = self._thumb_x()
        self.val_label.text = self._format()

    def _update(self) -> None:
        self.thumb.x = self._thumb_x()
        self.val_label.text = self._format()
        if self.on_change:
            self.on_change(self._value)

    def _hit(self, mx: int, my: int) -> bool:
        return (self.x - 5 <= mx <= self.x + self.width + 5
                and self.y - 5 <= my <= self.y + 40)

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if button == mouse.LEFT and self._hit(mx, my):
            self._dragging = True
            self._set_from_x(mx)
            return True
        return False

    def on_mouse_drag(self, mx: int, my: int, dx: int, dy: int, buttons: int, mod: int) -> bool:
        if self._dragging:
            self._set_from_x(mx)
            return True
        return False

    def on_mouse_release(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self._dragging:
            self._dragging = False
            return True
        return False

    def _set_from_x(self, mx: int) -> None:
        ratio = max(0, min(1, (mx - self.x) / self.width)) if self.width else 0
        self._value = self._snap(self.min_val + ratio * (self.max_val - self.min_val))
        self._update()

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.label.y += dy
        self.track.y += dy
        self.thumb.y += dy
        self.val_label.y += dy

    @property
    def visible(self) -> bool:
        return self.track.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        for s in self._shapes:
            s.visible = v

    def delete(self) -> None:
        for s in self._shapes:
            s.delete()


class UIToggle:
    """On/off toggle with coloured background and label."""

    def __init__(self, x: int, y: int, label_text: str, value: bool,
                 batch: pyglet.graphics.Batch, on_change: Callable | None = None):
        self.x, self.y = x, y
        self._value = value
        self.on_change = on_change
        self.bg = shapes.Rectangle(x, y, 20, 20,
                                   color=COL_TOGGLE_ON if value else COL_TOGGLE_OFF,
                                   batch=batch)
        self.check_label = Label("\u2713" if value else "", x=x + 4, y=y + 2,
                                 font_name=FONT, font_size=12, color=COL_WHITE,
                                 batch=batch)
        self.text_label = Label(label_text, x=x + 28, y=y + 2, font_name=FONT,
                                font_size=11, color=COL_TEXT, batch=batch)
        self._shapes = [self.bg, self.check_label, self.text_label]

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, v: bool) -> None:
        self._value = v
        self.bg.color = COL_TOGGLE_ON if v else COL_TOGGLE_OFF
        self.check_label.text = "\u2713" if v else ""

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if button == mouse.LEFT and self.x <= mx <= self.x + 120 and self.y <= my <= self.y + 20:
            self._value = not self._value
            self.bg.color = COL_TOGGLE_ON if self._value else COL_TOGGLE_OFF
            self.check_label.text = "\u2713" if self._value else ""
            if self.on_change:
                self.on_change(self._value)
            return True
        return False

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.bg.y += dy
        self.check_label.y += dy
        self.text_label.y += dy

    @property
    def visible(self) -> bool:
        return self.bg.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        for s in self._shapes:
            s.visible = v

    def delete(self) -> None:
        for s in self._shapes:
            s.delete()


class UIButton:
    """Clickable button with hover effect."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 batch: pyglet.graphics.Batch, color: tuple = COL_ACCENT,
                 hover_color: tuple = COL_ACCENT_HOVER,
                 text_color: tuple = COL_WHITE, on_click: Callable | None = None):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.color, self.hover_color = color, hover_color
        self.on_click = on_click
        self.bg = shapes.Rectangle(x, y, width, height, color=color, batch=batch)
        self.lbl = Label(text, x=x + width // 2, y=y + height // 2,
                         anchor_x="center", anchor_y="center",
                         font_name=FONT, font_size=12, color=text_color,
                         batch=batch)
        self._shapes = [self.bg, self.lbl]

    def _hit(self, mx: int, my: int) -> bool:
        return self.x <= mx <= self.x + self.width and self.y <= my <= self.y + self.height

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if button == mouse.LEFT and self._hit(mx, my):
            if self.on_click:
                self.on_click()
            return True
        return False

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.bg.color = self.hover_color if self._hit(mx, my) else self.color

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.bg.y += dy
        self.lbl.y += dy

    @property
    def visible(self) -> bool:
        return self.bg.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        for s in self._shapes:
            s.visible = v

    def delete(self) -> None:
        for s in self._shapes:
            s.delete()


class UITextInput:
    """Single-line text input with focus handling."""

    _BLINK_INTERVAL = 0.53  # seconds

    def __init__(self, x: int, y: int, width: int, label_text: str, value: str,
                 batch: pyglet.graphics.Batch):
        self.x, self.y, self.width = x, y, width
        self._value = value
        self._focused = False
        self._cursor_visible = True

        self.label = Label(label_text, x=x, y=y + 30, font_name=FONT,
                           font_size=11, color=COL_TEXT, batch=batch)
        self.bg = shapes.Rectangle(x, y, width, 26, color=COL_INPUT_BG, batch=batch)
        self.border = shapes.Box(x, y, width, 26, color=COL_INPUT_BORDER, batch=batch)
        self.text_label = Label(value, x=x + 6, y=y + 5, font_name=FONT,
                                font_size=11, color=COL_TEXT, batch=batch,
                                width=width - 12)
        # Caret (thin vertical line after text)
        self._caret = shapes.Line(0, y + 4, 0, y + 22, thickness=1,
                                  color=COL_TEXT[:3], batch=batch)
        self._caret.visible = False
        self._shapes = [self.label, self.bg, self.border, self.text_label,
                        self._caret]
        self._update_caret_x()
        pyglet.clock.schedule_interval(self._blink, self._BLINK_INTERVAL)

    def _update_caret_x(self) -> None:
        cx = self.x + 6 + self.text_label.content_width
        self._caret.x = cx
        self._caret.x2 = cx

    def _blink(self, dt: float) -> None:
        if not self._focused:
            return
        self._cursor_visible = not self._cursor_visible
        self._caret.visible = self._cursor_visible

    def _show_caret(self) -> None:
        self._cursor_visible = True
        self._caret.visible = True

    def _hide_caret(self) -> None:
        self._cursor_visible = False
        self._caret.visible = False

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        self._value = v
        self.text_label.text = v
        self._update_caret_x()

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        hit = self.x <= mx <= self.x + self.width and self.y <= my <= self.y + 26
        self._focused = hit
        self.border.color = COL_ACCENT if hit else COL_INPUT_BORDER
        if hit:
            self._show_caret()
        else:
            self._hide_caret()
        return hit

    def on_text(self, text: str) -> bool:
        if not self._focused:
            return False
        if text in ("\r", "\n"):
            self._focused = False
            self.border.color = COL_INPUT_BORDER
            self._hide_caret()
            return True
        self._value += text
        self.text_label.text = self._value
        self._update_caret_x()
        self._show_caret()
        return True

    def on_key_press(self, symbol: int, mod: int) -> bool:
        if not self._focused:
            return False
        if symbol == winkey.BACKSPACE:
            self._value = self._value[:-1]
            self.text_label.text = self._value
            self._update_caret_x()
            self._show_caret()
            return True
        return False

    @property
    def visible(self) -> bool:
        return self.bg.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        for s in self._shapes:
            s.visible = v

    def delete(self) -> None:
        pyglet.clock.unschedule(self._blink)
        for s in self._shapes:
            s.delete()


# ══════════════════════════════════════════════════════════════════════════════
#  BlockWidgetGroup — one card per block in the right panel
# ══════════════════════════════════════════════════════════════════════════════


class BlockWidgetGroup:
    """A group of widgets representing one scenario block."""

    CARD_H = 238
    PLUGIN_NAMES = ["track", "sysmon", "communications", "resman", "scheduling"]
    PLUGIN_LABELS = {"track": "Track", "sysmon": "Sysmon",
                     "communications": "Comms", "resman": "Resman",
                     "scheduling": "Sched."}

    def __init__(self, index: int, x: int, y: int, width: int,
                 batch: pyglet.graphics.Batch, difficulty: float = 0.50,
                 on_remove: Callable | None = None,
                 on_duplicate: Callable | None = None,
                 on_move_up: Callable | None = None,
                 on_move_down: Callable | None = None,
                 on_advanced: Callable | None = None):
        self.index = index
        self.x, self.y, self.width = x, y, width
        self.batch = batch
        self.on_remove = on_remove
        self.on_duplicate = on_duplicate
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.on_advanced = on_advanced
        self.advanced_params: dict[str, dict] = {}

        # Card background
        self.bg = shapes.Rectangle(x, y, width, self.CARD_H,
                                   color=COL_BLOCK_BG, batch=batch)
        self.border = shapes.Box(x, y, width, self.CARD_H,
                                 color=COL_BLOCK_BORDER, batch=batch)
        self.title = Label(f"Block {index + 1}", x=x + 10, y=y + self.CARD_H - 22,
                           font_name=FONT, font_size=12, weight='bold',
                           color=COL_TEXT, batch=batch)

        # Top-right buttons row
        btn_right = x + width - 10
        self.remove_btn = UIButton(
            btn_right - 90, y + self.CARD_H - 30, 90, 26, "\u2715 Remove", batch,
            color=COL_RED_BTN, hover_color=COL_RED_HOVER,
            text_color=COL_WHITE, on_click=self._do_remove,
        )
        self.dup_btn = UIButton(
            btn_right - 165, y + self.CARD_H - 30, 70, 26, "\u2295 Clone", batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            text_color=COL_WHITE, on_click=self._do_duplicate,
        )
        self.move_up_btn = UIButton(
            btn_right - 205, y + self.CARD_H - 30, 32, 26, "\u25b2", batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            text_color=COL_WHITE, on_click=self._do_move_up,
        )
        self.move_down_btn = UIButton(
            btn_right - 242, y + self.CARD_H - 30, 32, 26, "\u25bc", batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            text_color=COL_WHITE, on_click=self._do_move_down,
        )

        # Duration slider
        self.duration_slider = UISlider(
            x + 10, y + self.CARD_H - 72, width - 120,
            "Duration", 30, 300, 5, 60, batch,
            fmt="{:.0f}", suffix=" s",
        )

        # Plugin toggles + difficulty sliders + gear buttons
        self.toggles: dict[str, UIToggle] = {}
        self.sliders: dict[str, UISlider] = {}
        self.gear_btns: dict[str, UIButton] = {}
        row_y = y + self.CARD_H - 110
        for name in self.PLUGIN_NAMES:
            self.toggles[name] = UIToggle(x + 10, row_y,
                                          self.PLUGIN_LABELS[name], True, batch)
            self.sliders[name] = UISlider(
                x + 135, row_y - 8, width - 240,
                "", 0, 100, 1, difficulty * 100, batch,
                fmt="{:.0f}", suffix=" %",
            )
            self.gear_btns[name] = UIButton(
                x + width - 40, row_y - 3, 26, 22, "\u2699", batch,
                color=(160, 160, 170), hover_color=(120, 120, 140),
                text_color=COL_WHITE,
                on_click=lambda n=name: self._do_advanced(n),
            )
            row_y -= 28

        self._all_shapes = [self.bg, self.border, self.title]

    def _do_remove(self) -> None:
        if self.on_remove:
            self.on_remove(self.index)

    def _do_duplicate(self) -> None:
        if self.on_duplicate:
            self.on_duplicate(self.index)

    def _do_move_up(self) -> None:
        if self.on_move_up:
            self.on_move_up(self.index)

    def _do_move_down(self) -> None:
        if self.on_move_down:
            self.on_move_down(self.index)

    def _do_advanced(self, plugin_name: str) -> None:
        if self.on_advanced:
            self.on_advanced(self.index, plugin_name)

    def get_block_config(self) -> BlockConfig:
        plugins = {}
        for name in self.PLUGIN_NAMES:
            if self.toggles[name].value:
                plugins[name] = self.sliders[name].value / 100.0
        extra_events: list[tuple[str, str, Any]] = []
        for plugin_name, params in self.advanced_params.items():
            for param_name, param_value in params.items():
                extra_events.append((plugin_name, param_name, param_value))
        return BlockConfig(
            duration_sec=int(self.duration_slider.value),
            plugins=plugins,
            extra_events=extra_events,
        )

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.bg.y += dy
        self.border.y += dy
        self.title.y += dy
        for btn in (self.remove_btn, self.dup_btn, self.move_up_btn, self.move_down_btn):
            btn.set_y(btn.y + dy)
        self.duration_slider.set_y(self.duration_slider.y + dy)
        for name in self.PLUGIN_NAMES:
            self.toggles[name].set_y(self.toggles[name].y + dy)
            self.sliders[name].set_y(self.sliders[name].y + dy)
            if name in self.gear_btns:
                self.gear_btns[name].set_y(self.gear_btns[name].y + dy)

    @property
    def visible(self) -> bool:
        return self.bg.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        self.bg.visible = v
        self.border.visible = v
        self.title.visible = v
        for btn in (self.remove_btn, self.dup_btn, self.move_up_btn, self.move_down_btn):
            btn.visible = v
        self.duration_slider.visible = v
        for name in self.PLUGIN_NAMES:
            self.toggles[name].visible = v
            self.sliders[name].visible = v
            if name in self.gear_btns:
                self.gear_btns[name].visible = v

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        for btn in (self.remove_btn, self.dup_btn, self.move_up_btn, self.move_down_btn):
            if btn.on_mouse_press(mx, my, button, mod):
                return True
        if self.duration_slider.on_mouse_press(mx, my, button, mod):
            return True
        for name in self.PLUGIN_NAMES:
            if self.toggles[name].on_mouse_press(mx, my, button, mod):
                return True
            if self.sliders[name].on_mouse_press(mx, my, button, mod):
                return True
            if name in self.gear_btns and self.gear_btns[name].on_mouse_press(mx, my, button, mod):
                return True
        return False

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        for btn in (self.remove_btn, self.dup_btn, self.move_up_btn, self.move_down_btn):
            btn.on_mouse_motion(mx, my, dx, dy)
        for name in self.PLUGIN_NAMES:
            if name in self.gear_btns:
                self.gear_btns[name].on_mouse_motion(mx, my, dx, dy)

    def on_mouse_drag(self, mx: int, my: int, dx: int, dy: int, buttons: int, mod: int) -> bool:
        if self.duration_slider.on_mouse_drag(mx, my, dx, dy, buttons, mod):
            return True
        for name in self.PLUGIN_NAMES:
            if self.sliders[name].on_mouse_drag(mx, my, dx, dy, buttons, mod):
                return True
        return False

    def on_mouse_release(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self.duration_slider.on_mouse_release(mx, my, button, mod):
            return True
        for name in self.PLUGIN_NAMES:
            if self.sliders[name].on_mouse_release(mx, my, button, mod):
                return True
        return False

    def delete(self) -> None:
        for s in self._all_shapes:
            s.delete()
        for btn in (self.remove_btn, self.dup_btn, self.move_up_btn, self.move_down_btn):
            btn.delete()
        self.duration_slider.delete()
        for name in self.PLUGIN_NAMES:
            self.toggles[name].delete()
            self.sliders[name].delete()
            if name in self.gear_btns:
                self.gear_btns[name].delete()


# ══════════════════════════════════════════════════════════════════════════════
#  InterBlockWidget — mini-card between blocks for instructions/questionnaires
# ══════════════════════════════════════════════════════════════════════════════


class InterBlockWidget:
    """A small card displayed between blocks representing an inter-block event."""

    CARD_H = 40

    TYPE_LABELS = {"instructions": "\u2709 Instructions", "genericscales": "\u2611 NASA-TLX"}

    def __init__(self, position: int, event_type: str, filename: str,
                 x: int, y: int, width: int, batch: pyglet.graphics.Batch,
                 on_remove: Callable | None = None):
        self.position = position
        self.event_type = event_type
        self.filename = filename
        self.x, self.y, self.width = x, y, width
        self.batch = batch
        self.on_remove_cb = on_remove

        self.bg = shapes.Rectangle(x, y, width, self.CARD_H,
                                   color=COL_INTERBLOCK_BG, batch=batch)
        self.border = shapes.Box(x, y, width, self.CARD_H,
                                 color=COL_INTERBLOCK_BORDER, batch=batch)
        type_str = self.TYPE_LABELS.get(event_type, event_type)
        self.label = Label(f"{type_str} : {Path(filename).stem}",
                           x=x + 10, y=y + 12, font_name=FONT, font_size=10,
                           color=COL_TEXT, batch=batch)
        self.remove_btn = UIButton(
            x + width - 35, y + 8, 26, 24, "\u2715", batch,
            color=COL_RED_BTN, hover_color=COL_RED_HOVER,
            text_color=COL_WHITE, on_click=self._do_remove,
        )
        self._shapes = [self.bg, self.border, self.label]

    def _do_remove(self) -> None:
        if self.on_remove_cb:
            self.on_remove_cb(self)

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.bg.y += dy
        self.border.y += dy
        self.label.y += dy
        self.remove_btn.set_y(self.remove_btn.y + dy)

    @property
    def visible(self) -> bool:
        return self.bg.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        for s in self._shapes:
            s.visible = v
        self.remove_btn.visible = v

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        return self.remove_btn.on_mouse_press(mx, my, button, mod)

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.remove_btn.on_mouse_motion(mx, my, dx, dy)

    def delete(self) -> None:
        for s in self._shapes:
            s.delete()
        self.remove_btn.delete()

    def to_inter_block_event(self) -> InterBlockEvent:
        return InterBlockEvent(type=self.event_type, filename=self.filename,
                               position=self.position)


# ══════════════════════════════════════════════════════════════════════════════
#  InsertZone — clickable zone between blocks to add instructions/questionnaires
# ══════════════════════════════════════════════════════════════════════════════


class InsertZone:
    """Two small buttons displayed between blocks for inserting inter-block events."""

    ZONE_H = 24

    def __init__(self, position: int, x: int, y: int, width: int,
                 batch: pyglet.graphics.Batch,
                 on_instructions: Callable, on_questionnaire: Callable) -> None:
        self.position = position
        self.x, self.y, self.width = x, y, width
        self.instr_btn = UIButton(
            x, y, width // 2 - 5, self.ZONE_H,
            "+ Instructions", batch,
            color=(200, 215, 240), hover_color=(170, 195, 230),
            text_color=COL_TEXT, on_click=lambda: on_instructions(position),
        )
        self.quest_btn = UIButton(
            x + width // 2 + 5, y, width // 2 - 5, self.ZONE_H,
            "+ Questionnaire", batch,
            color=(200, 215, 240), hover_color=(170, 195, 230),
            text_color=COL_TEXT, on_click=lambda: on_questionnaire(position),
        )

    def set_y(self, new_y: int) -> None:
        dy = new_y - self.y
        self.y = new_y
        self.instr_btn.set_y(self.instr_btn.y + dy)
        self.quest_btn.set_y(self.quest_btn.y + dy)

    @property
    def visible(self) -> bool:
        return self.instr_btn.visible

    @visible.setter
    def visible(self, v: bool) -> None:
        self.instr_btn.visible = v
        self.quest_btn.visible = v

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self.instr_btn.on_mouse_press(mx, my, button, mod):
            return True
        if self.quest_btn.on_mouse_press(mx, my, button, mod):
            return True
        return False

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.instr_btn.on_mouse_motion(mx, my, dx, dy)
        self.quest_btn.on_mouse_motion(mx, my, dx, dy)

    def delete(self) -> None:
        self.instr_btn.delete()
        self.quest_btn.delete()


# ══════════════════════════════════════════════════════════════════════════════
#  Overlay widgets — modal panels drawn on top of the main UI
# ══════════════════════════════════════════════════════════════════════════════


class UIPreviewOverlay:
    """Modal overlay showing the generated scenario content."""

    def __init__(self, win_w: int, win_h: int, batch: pyglet.graphics.Batch,
                 lines: list[str], file_path: Path | None, on_close: Callable) -> None:
        self.batch = batch
        self.on_close = on_close
        self.file_path = file_path
        self._scroll_offset = 0
        self._lines = lines

        # Dim background
        self.dim_bg = shapes.Rectangle(0, 0, win_w, win_h, color=(0, 0, 0),
                                       batch=batch)
        self.dim_bg.opacity = 120

        # White panel
        pw, ph = 820, 560
        px, py = (win_w - pw) // 2, (win_h - ph) // 2
        self.panel_x, self.panel_y, self.panel_w, self.panel_h = px, py, pw, ph
        self.panel = shapes.Rectangle(px, py, pw, ph, color=COL_OVERLAY_BG, batch=batch)
        self.panel_border = shapes.Box(px, py, pw, ph, color=COL_BLOCK_BORDER, batch=batch)

        # Title
        self.title = Label("Preview", x=px + 15, y=py + ph - 25,
                           font_name=FONT, font_size=13, weight='bold',
                           color=COL_TEXT, batch=batch)

        # Path label
        self.path_label = Label(str(file_path) if file_path else "Preview",
                                x=px + 15, y=py + ph - 48,
                                font_name=FONT, font_size=9, color=COL_TEXT_LIGHT,
                                batch=batch)

        # Close button (× cross)
        self.close_btn = UIButton(px + pw - 35, py + ph - 33, 24, 24, "\u00d7", batch,
                                  color=(180, 180, 180), hover_color=(120, 120, 120),
                                  on_click=self._do_close)

        # Scrollable text area — label pool
        self._sb_w = 14
        self._text_top = py + ph - 65
        self._text_left = px + 15
        self._text_bottom = py + 15
        self._row_height = 16
        self._visible_rows = (self._text_top - self._text_bottom) // self._row_height
        self._label_pool: list[Label] = []
        for i in range(self._visible_rows):
            lbl = Label("", x=self._text_left, y=self._text_top - i * self._row_height,
                        font_name="Consolas", font_size=9, color=COL_TEXT, batch=batch)
            self._label_pool.append(lbl)

        # Scrollbar with ▲/▼ buttons
        sb_x = px + pw - self._sb_w - 8
        self._sb_btn_h = 20
        sb_full_top = self._text_top + self._row_height
        sb_full_bottom = self._text_bottom
        self._sb_up_btn = UIButton(sb_x, sb_full_top - self._sb_btn_h,
                                   self._sb_w, self._sb_btn_h, "\u25b2", batch,
                                   on_click=self._scroll_up)
        self._sb_down_btn = UIButton(sb_x, sb_full_bottom,
                                     self._sb_w, self._sb_btn_h, "\u25bc", batch,
                                     on_click=self._scroll_down)
        sb_track_bottom = sb_full_bottom + self._sb_btn_h
        sb_track_h = sb_full_top - self._sb_btn_h - sb_track_bottom
        self._sb_track = shapes.Rectangle(sb_x, sb_track_bottom,
                                          self._sb_w, sb_track_h,
                                          color=(230, 230, 230), batch=batch)
        self._sb_thumb = shapes.Rectangle(sb_x, sb_track_bottom + sb_track_h - 40,
                                          self._sb_w, 40,
                                          color=(170, 170, 180), batch=batch)
        self._sb_x = sb_x
        self._sb_track_bottom = sb_track_bottom
        self._sb_track_h = sb_track_h
        self._sb_dragging = False

        self._all_shapes = [self.dim_bg, self.panel, self.panel_border,
                            self.title, self.path_label,
                            self._sb_track, self._sb_thumb] + self._label_pool
        self._refresh()

    def _refresh(self) -> None:
        for i, lbl in enumerate(self._label_pool):
            line_idx = self._scroll_offset + i
            if line_idx < len(self._lines):
                lbl.text = self._lines[line_idx][:120]
            else:
                lbl.text = ""
        # Update scrollbar thumb
        max_off = max(0, len(self._lines) - self._visible_rows)
        if max_off <= 0:
            self._sb_thumb.visible = False
        else:
            self._sb_thumb.visible = True
            thumb_h = max(20, int(self._sb_track_h * self._visible_rows / len(self._lines)))
            ratio = self._scroll_offset / max_off
            thumb_y = self._sb_track_bottom + self._sb_track_h - thumb_h - int(ratio * (self._sb_track_h - thumb_h))
            self._sb_thumb.y = thumb_y
            self._sb_thumb.height = thumb_h

    def _scroll_up(self) -> None:
        if self._scroll_offset > 0:
            self._scroll_offset -= 1
            self._refresh()

    def _scroll_down(self) -> None:
        max_off = max(0, len(self._lines) - self._visible_rows)
        if self._scroll_offset < max_off:
            self._scroll_offset += 1
            self._refresh()

    def _sb_click_to_scroll(self, my: int) -> None:
        max_off = max(0, len(self._lines) - self._visible_rows)
        if max_off <= 0:
            return
        clamped_y = max(self._sb_track_bottom, min(my, self._sb_track_bottom + self._sb_track_h))
        ratio = 1.0 - (clamped_y - self._sb_track_bottom) / self._sb_track_h
        self._scroll_offset = max(0, min(max_off, int(ratio * max_off + 0.5)))
        self._refresh()

    def _do_close(self) -> None:
        self.on_close()

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        self.close_btn.on_mouse_press(mx, my, button, mod)
        self._sb_up_btn.on_mouse_press(mx, my, button, mod)
        self._sb_down_btn.on_mouse_press(mx, my, button, mod)
        # Scrollbar track click
        if (self._sb_thumb.visible
                and self._sb_x <= mx <= self._sb_x + self._sb_w
                and self._sb_track_bottom <= my <= self._sb_track_bottom + self._sb_track_h):
            self._sb_dragging = True
            self._sb_click_to_scroll(my)
        return True  # consume all clicks when overlay is open

    def on_mouse_drag(self, mx: int, my: int, dx: int, dy: int, buttons: int, mod: int) -> bool:
        if self._sb_dragging:
            self._sb_click_to_scroll(my)
        return True

    def on_mouse_release(self, mx: int, my: int, button: int, mod: int) -> bool:
        self._sb_dragging = False
        return True

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.close_btn.on_mouse_motion(mx, my, dx, dy)
        self._sb_up_btn.on_mouse_motion(mx, my, dx, dy)
        self._sb_down_btn.on_mouse_motion(mx, my, dx, dy)

    def on_mouse_scroll(self, mx: int, my: int, scroll_x: float, scroll_y: float) -> bool:
        max_offset = max(0, len(self._lines) - self._visible_rows)
        self._scroll_offset = max(0, min(max_offset,
                                         self._scroll_offset - int(scroll_y)))
        self._refresh()
        return True

    def on_key_press(self, symbol: int, mod: int) -> bool:
        if symbol == winkey.ESCAPE:
            self._do_close()
        return True

    def delete(self) -> None:
        for s in self._all_shapes:
            s.delete()
        self.close_btn.delete()
        self._sb_up_btn.delete()
        self._sb_down_btn.delete()


class UIFileSelector:
    """Modal overlay for selecting a file from a directory."""

    def __init__(self, win_w: int, win_h: int, batch: pyglet.graphics.Batch,
                 files: list[Path], title: str, on_select: Callable,
                 on_cancel: Callable) -> None:
        self.batch = batch
        self.on_select = on_select
        self.on_cancel = on_cancel
        self._files = files
        self._display_texts = [str(f.name) for f in files]
        self._selected_index = 0 if files else -1
        self._scroll_offset = 0
        self._last_click_time = 0.0
        self._last_click_index = -1

        # Dim background
        self.dim_bg = shapes.Rectangle(0, 0, win_w, win_h, color=(0, 0, 0), batch=batch)
        self.dim_bg.opacity = 120

        # White panel
        pw, ph = 600, 450
        px, py = (win_w - pw) // 2, (win_h - ph) // 2
        self.panel_x, self.panel_y, self.panel_w, self.panel_h = px, py, pw, ph
        self.panel = shapes.Rectangle(px, py, pw, ph, color=COL_OVERLAY_BG, batch=batch)
        self.panel_border = shapes.Box(px, py, pw, ph, color=COL_BLOCK_BORDER, batch=batch)

        self.title_lbl = Label(title, x=px + 15, y=py + ph - 25,
                               font_name=FONT, font_size=13, weight='bold',
                               color=COL_TEXT, batch=batch)

        # Close button (× cross)
        self.cancel_btn = UIButton(px + pw - 35, py + ph - 33, 24, 24, "\u00d7", batch,
                                   color=(180, 180, 180), hover_color=(120, 120, 120),
                                   on_click=self._do_cancel)

        # Select button
        self.select_btn = UIButton(px + pw - 90, py + ph - 35, 75, 26,
                                   "Select", batch,
                                   color=COL_GREEN_BTN, hover_color=COL_GREEN_HOVER,
                                   on_click=self._do_select)

        # File list — label pool
        self._list_top = py + ph - 55
        self._row_height = 24
        self._visible_rows = (ph - 80) // self._row_height
        self._label_pool: list[Label] = []
        for i in range(self._visible_rows):
            lbl = Label("", x=px + 20,
                        y=self._list_top - i * self._row_height,
                        font_name=FONT, font_size=10, color=COL_TEXT, batch=batch)
            self._label_pool.append(lbl)

        # Highlight bar
        self._highlight = shapes.Rectangle(px + 5, 0, pw - 10, self._row_height,
                                           color=COL_ACCENT, batch=batch)
        self._highlight.opacity = 60

        self._all_shapes = [self.dim_bg, self.panel, self.panel_border,
                            self.title_lbl, self._highlight] + self._label_pool
        self._refresh()

    def _refresh(self) -> None:
        for i, lbl in enumerate(self._label_pool):
            file_idx = self._scroll_offset + i
            if file_idx < len(self._display_texts):
                lbl.text = self._display_texts[file_idx]
                lbl.color = COL_WHITE if file_idx == self._selected_index else COL_TEXT
            else:
                lbl.text = ""

        vis_idx = self._selected_index - self._scroll_offset
        if 0 <= vis_idx < self._visible_rows and 0 <= self._selected_index < len(self._files):
            y = self._list_top - vis_idx * self._row_height - 5
            self._highlight.y = y
            self._highlight.visible = True
        else:
            self._highlight.visible = False

    def _do_cancel(self) -> None:
        self.on_cancel()

    def _do_select(self) -> None:
        if 0 <= self._selected_index < len(self._files):
            self.on_select(self._files[self._selected_index])

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self.cancel_btn.on_mouse_press(mx, my, button, mod):
            return True
        if self.select_btn.on_mouse_press(mx, my, button, mod):
            return True
        # Click on list item
        if button == mouse.LEFT and self._files:
            row = int((self._list_top - my + 5) / self._row_height)
            if 0 <= row < self._visible_rows:
                idx = self._scroll_offset + row
                if idx < len(self._files):
                    now = _time.monotonic()
                    if idx == self._last_click_index and (now - self._last_click_time) < 0.4:
                        self.on_select(self._files[idx])
                    else:
                        self._selected_index = idx
                        self._refresh()
                    self._last_click_time = now
                    self._last_click_index = idx
        return True

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.cancel_btn.on_mouse_motion(mx, my, dx, dy)
        self.select_btn.on_mouse_motion(mx, my, dx, dy)

    def on_mouse_scroll(self, mx: int, my: int, scroll_x: float, scroll_y: float) -> bool:
        if not self._files:
            return True
        max_offset = max(0, len(self._files) - self._visible_rows)
        self._scroll_offset = max(0, min(max_offset,
                                         self._scroll_offset - int(scroll_y)))
        self._refresh()
        return True

    def on_key_press(self, symbol: int, mod: int) -> bool:
        if symbol == winkey.ESCAPE:
            self._do_cancel()
        elif symbol == winkey.RETURN:
            self._do_select()
        elif symbol == winkey.UP and self._selected_index > 0:
            self._selected_index -= 1
            if self._selected_index < self._scroll_offset:
                self._scroll_offset = self._selected_index
            self._refresh()
        elif symbol == winkey.DOWN and self._selected_index < len(self._files) - 1:
            self._selected_index += 1
            if self._selected_index >= self._scroll_offset + self._visible_rows:
                self._scroll_offset = self._selected_index - self._visible_rows + 1
            self._refresh()
        return True

    def delete(self) -> None:
        for s in self._all_shapes:
            s.delete()
        self.cancel_btn.delete()
        self.select_btn.delete()


class UIAdvancedPanel:
    """Modal overlay for advanced plugin parameters."""

    PLUGIN_PARAMS: dict[str, list[tuple[str, str, str, dict]]] = {
        "sysmon": [
            ("alerttimeout", "Alert timeout (ms)", "slider",
             {"min_val": 1000, "max_val": 30000, "step": 500, "default": 10000,
              "fmt": "{:.0f}", "suffix": " ms"}),
            ("allowanykey", "Allow any key", "toggle", {"default": False}),
        ],
        "communications": [
            ("voiceidiom", "Voice language", "radio",
             {"options": ["fr", "en"], "labels": ["French", "English"],
              "default": "fr"}),
            ("voicegender", "Voice gender", "radio",
             {"options": ["female", "male"], "labels": ["Female", "Male"],
              "default": "female"}),
        ],
        "resman": [
            ("toleranceradius", "Tolerance radius", "slider",
             {"min_val": 50, "max_val": 500, "step": 10, "default": 250,
              "fmt": "{:.0f}", "suffix": ""}),
        ],
        "track": [
            ("joystickforce", "Joystick force", "slider",
             {"min_val": 1, "max_val": 10, "step": 1, "default": 5,
              "fmt": "{:.0f}", "suffix": ""}),
            ("cursorcolor", "Cursor color", "radio",
             {"options": ["#ff0000", "#00ff00", "#0000ff", "#ffff00"],
              "labels": ["Red", "Green", "Blue", "Yellow"],
              "default": "#ff0000"}),
        ],
        "scheduling": [
            ("minduration", "Min duration (ms)", "slider",
             {"min_val": 500, "max_val": 10000, "step": 500, "default": 2000,
              "fmt": "{:.0f}", "suffix": " ms"}),
        ],
    }

    def __init__(self, win_w: int, win_h: int, batch: pyglet.graphics.Batch,
                 plugin_name: str, current_params: dict,
                 on_save: Callable, on_cancel: Callable) -> None:
        self.batch = batch
        self.plugin_name = plugin_name
        self.on_save_cb = on_save
        self.on_cancel_cb = on_cancel
        self._widgets: list[Any] = []
        self._param_widgets: dict[str, Any] = {}

        # Dim background
        self.dim_bg = shapes.Rectangle(0, 0, win_w, win_h, color=(0, 0, 0), batch=batch)
        self.dim_bg.opacity = 120

        # Panel
        pw, ph = 500, 400
        px, py = (win_w - pw) // 2, (win_h - ph) // 2
        self.panel = shapes.Rectangle(px, py, pw, ph, color=COL_OVERLAY_BG, batch=batch)
        self.panel_border = shapes.Box(px, py, pw, ph, color=COL_BLOCK_BORDER, batch=batch)

        plugin_label = BlockWidgetGroup.PLUGIN_LABELS.get(plugin_name, plugin_name.capitalize())
        self.title = Label(f"Advanced settings \u2014 {plugin_label}",
                           x=px + 15, y=py + ph - 25,
                           font_name=FONT, font_size=13, weight='bold',
                           color=COL_TEXT, batch=batch)

        self.save_btn = UIButton(px + pw - 85, py + 10, 70, 28, "Apply", batch,
                                 color=COL_GREEN_BTN, hover_color=COL_GREEN_HOVER,
                                 on_click=self._do_save)
        self.cancel_btn = UIButton(px + pw - 35, py + ph - 33, 24, 24, "\u00d7", batch,
                                   color=(180, 180, 180), hover_color=(120, 120, 120),
                                   on_click=self._do_cancel)

        self._all_shapes = [self.dim_bg, self.panel, self.panel_border, self.title]

        # Build parameter widgets
        params_def = self.PLUGIN_PARAMS.get(plugin_name, [])
        row_y = py + ph - 90
        for param_name, label_text, widget_type, opts in params_def:
            current_val = current_params.get(param_name, opts.get("default"))
            if widget_type == "slider":
                slider = UISlider(px + 20, row_y, pw - 120, label_text,
                                  opts["min_val"], opts["max_val"], opts["step"],
                                  current_val if current_val is not None else opts["default"],
                                  batch, fmt=opts.get("fmt", "{:.0f}"),
                                  suffix=opts.get("suffix", ""))
                self._param_widgets[param_name] = ("slider", slider)
                self._widgets.append(slider)
                row_y -= 60
            elif widget_type == "toggle":
                toggle = UIToggle(px + 20, row_y, label_text,
                                  current_val if current_val is not None else opts["default"],
                                  batch)
                self._param_widgets[param_name] = ("toggle", toggle)
                self._widgets.append(toggle)
                row_y -= 35
            elif widget_type == "radio":
                lbl = Label(label_text, x=px + 20, y=row_y,
                            font_name=FONT, font_size=11, color=COL_TEXT, batch=batch)
                self._all_shapes.append(lbl)
                row_y -= 28
                buttons: list[UIButton] = []
                selected = current_val if current_val is not None else opts["default"]
                for j, (opt, opt_label) in enumerate(zip(opts["options"], opts["labels"])):
                    is_sel = (opt == selected)
                    btn = UIButton(
                        px + 20 + j * 110, row_y, 100, 26, opt_label, batch,
                        color=COL_ACCENT if is_sel else COL_TOGGLE_OFF,
                        hover_color=COL_ACCENT_HOVER if is_sel else (160, 160, 160),
                        text_color=COL_WHITE,
                    )
                    buttons.append(btn)
                    self._widgets.append(btn)
                self._param_widgets[param_name] = ("radio", buttons, opts["options"])
                row_y -= 40

    def _get_params(self) -> dict:
        result = {}
        for param_name, widget_info in self._param_widgets.items():
            wtype = widget_info[0]
            if wtype == "slider":
                result[param_name] = widget_info[1].value
            elif wtype == "toggle":
                result[param_name] = widget_info[1].value
            elif wtype == "radio":
                buttons = widget_info[1]
                options = widget_info[2]
                for btn, opt in zip(buttons, options):
                    if btn.color == COL_ACCENT:
                        result[param_name] = opt
                        break
        return result

    def _do_save(self) -> None:
        self.on_save_cb(self._get_params())

    def _do_cancel(self) -> None:
        self.on_cancel_cb()

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self.save_btn.on_mouse_press(mx, my, button, mod):
            return True
        if self.cancel_btn.on_mouse_press(mx, my, button, mod):
            return True
        # Handle radio button clicks
        for param_name, widget_info in self._param_widgets.items():
            wtype = widget_info[0]
            if wtype == "slider":
                if widget_info[1].on_mouse_press(mx, my, button, mod):
                    return True
            elif wtype == "toggle":
                if widget_info[1].on_mouse_press(mx, my, button, mod):
                    return True
            elif wtype == "radio":
                buttons = widget_info[1]
                options = widget_info[2]
                for i, btn in enumerate(buttons):
                    if btn._hit(mx, my) and button == mouse.LEFT:
                        # Deselect all, select this one
                        for b in buttons:
                            b.color = COL_TOGGLE_OFF
                            b.hover_color = (160, 160, 160)
                            b.bg.color = COL_TOGGLE_OFF
                        btn.color = COL_ACCENT
                        btn.hover_color = COL_ACCENT_HOVER
                        btn.bg.color = COL_ACCENT
                        return True
        return True

    def on_mouse_drag(self, mx: int, my: int, dx: int, dy: int, buttons: int, mod: int) -> bool:
        for param_name, widget_info in self._param_widgets.items():
            if widget_info[0] == "slider":
                if widget_info[1].on_mouse_drag(mx, my, dx, dy, buttons, mod):
                    return True
        return True

    def on_mouse_release(self, mx: int, my: int, button: int, mod: int) -> bool:
        for param_name, widget_info in self._param_widgets.items():
            if widget_info[0] == "slider":
                if widget_info[1].on_mouse_release(mx, my, button, mod):
                    return True
        return True

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        self.save_btn.on_mouse_motion(mx, my, dx, dy)
        self.cancel_btn.on_mouse_motion(mx, my, dx, dy)

    def on_key_press(self, symbol: int, mod: int) -> bool:
        if symbol == winkey.ESCAPE:
            self._do_cancel()
        return True

    def delete(self) -> None:
        for s in self._all_shapes:
            s.delete()
        self.save_btn.delete()
        self.cancel_btn.delete()
        for w in self._widgets:
            w.delete()


# ══════════════════════════════════════════════════════════════════════════════
#  Main UI class
# ══════════════════════════════════════════════════════════════════════════════


class ScenarioGeneratorUI:
    WIN_W, WIN_H = 1000, 700
    LEFT_W = 280
    SB_W = 20  # scrollbar column width
    MAX_BLOCKS = 10
    BLOCK_GAP = 10

    def __init__(self) -> None:
        self.window = pyglet.window.Window(
            self.WIN_W, self.WIN_H,
            caption="OpenMATB \u2014 Scenario Generator",
            resizable=False,
        )
        self.batch = pyglet.graphics.Batch()
        self._blocks_batch = pyglet.graphics.Batch()
        self._overlay_batch = pyglet.graphics.Batch()
        self.blocks: list[BlockWidgetGroup] = []
        self.scroll_offset = 0
        self._all_widgets: list[Any] = []

        # Overlay state — only one overlay open at a time
        self._overlay: UIPreviewOverlay | UIFileSelector | UIAdvancedPanel | None = None
        # Inter-block widgets
        self._inter_block_widgets: list[InterBlockWidget] = []
        # Preview cache: reuse previewed lines when generating if config unchanged
        self._preview_lines: list | None = None
        self._preview_config: ScenarioConfig | None = None

        # Pre-create insert zones (one per possible gap: 0..MAX_BLOCKS)
        bx = self.LEFT_W + 15
        bw = self.WIN_W - self.LEFT_W - self.SB_W - 20
        self._insert_zones: list[InsertZone] = []
        for pos in range(self.MAX_BLOCKS + 1):
            zone = InsertZone(pos, bx, 0, bw, self._blocks_batch,
                              on_instructions=self._insert_instructions_at,
                              on_questionnaire=self._insert_questionnaire_at)
            zone.visible = False
            self._insert_zones.append(zone)

        self._build_ui()
        self.window.push_handlers(self)

        # Default: 3 blocks with progressive difficulty
        for diff in (0.25, 0.55, 0.85):
            self._add_block(diff)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        W, H = self.WIN_W, self.WIN_H

        # Title bar
        self.title_bg = shapes.Rectangle(0, H - 45, W, 45, color=COL_ACCENT, batch=self.batch)
        self.title_label = Label(
            "OpenMATB \u2014 Scenario Generator",
            x=15, y=H - 30, font_name=FONT, font_size=14,
            color=COL_WHITE, batch=self.batch,
        )

        # Left panel background
        self.left_bg = shapes.Rectangle(0, 50, self.LEFT_W, H - 95,
                                        color=COL_PANEL, batch=self.batch)

        # Section label
        self.left_title = Label(
            "GLOBAL SETTINGS", x=15, y=H - 70,
            font_name=FONT, font_size=11, weight='bold', color=COL_TEXT,
            batch=self.batch,
        )

        # Scenario name
        self.name_input = UITextInput(15, H - 130, self.LEFT_W - 30,
                                      "Scenario name:", "three_load_levels",
                                      self.batch)
        self._all_widgets.append(self.name_input)

        # Comm ratio slider
        self.comm_slider = UISlider(
            15, H - 200, self.LEFT_W - 80,
            "Communications ratio:", 0, 100, 1, 50,
            self.batch, fmt="{:.0f}", suffix=" %",
        )
        self._all_widgets.append(self.comm_slider)

        # Refractory duration slider
        self.refract_slider = UISlider(
            15, H - 260, self.LEFT_W - 80,
            "Refractory duration:", 0, 5, 0.5, 1,
            self.batch, fmt="{:.1f}", suffix=" s",
        )
        self._all_widgets.append(self.refract_slider)

        # Prompt duration slider
        self.prompt_slider = UISlider(
            15, H - 320, self.LEFT_W - 80,
            "Audio prompt duration:", 5, 30, 1, 13,
            self.batch, fmt="{:.0f}", suffix=" s",
        )
        self._all_widgets.append(self.prompt_slider)

        # Right panel title
        self.right_title = Label(
            "BLOCK CONFIGURATION", x=self.LEFT_W + 15, y=H - 70,
            font_name=FONT, font_size=11, weight='bold', color=COL_TEXT,
            batch=self.batch,
        )

        # Block management buttons — below the title, above the blocks area
        btn_y = H - 105
        self.add_btn = UIButton(
            self.LEFT_W + 15, btn_y, 100, 28, "+ Add", self.batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            on_click=lambda: self._add_block(0.50),
        )
        # Preset buttons — same row, right-aligned
        right_edge = self.WIN_W - 15
        self.load_preset_btn = UIButton(
            right_edge - 130, btn_y, 130, 28, "\U0001f4c2 Load config", self.batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            on_click=self._open_preset_selector,
        )
        self.save_preset_btn = UIButton(
            right_edge - 270, btn_y, 130, 28, "\U0001f4be Save config", self.batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            on_click=self._save_preset,
        )

        # Scrollbar (right edge of blocks area) with ▲/▼ buttons
        self._sb_width = self.SB_W
        self._sb_btn_h = 24
        sb_x = self.WIN_W - self._sb_width - 2
        self.scroll_up_btn = UIButton(
            sb_x, self._blocks_area_top - self._sb_btn_h, self._sb_width,
            self._sb_btn_h, "\u25b2", self.batch, on_click=self._scroll_up,
        )
        self.scroll_down_btn = UIButton(
            sb_x, self._blocks_area_bottom, self._sb_width,
            self._sb_btn_h, "\u25bc", self.batch, on_click=self._scroll_down,
        )
        sb_track_bottom = self._blocks_area_bottom + self._sb_btn_h
        sb_track_h = self._blocks_area_height - 2 * self._sb_btn_h
        self._sb_track = shapes.Rectangle(
            sb_x, sb_track_bottom, self._sb_width,
            sb_track_h, color=(220, 220, 220), batch=self.batch,
        )
        self._sb_thumb = shapes.Rectangle(
            sb_x, sb_track_bottom + sb_track_h - 40, self._sb_width, 40,
            color=(160, 160, 170), batch=self.batch,
        )
        self._sb_track_bottom = sb_track_bottom
        self._sb_track_h = sb_track_h
        self._sb_thumb.visible = False
        self._sb_dragging = False

        # Bottom bar (full width)
        self.bottom_bg = shapes.Rectangle(0, 0, self.WIN_W, 50, color=COL_PANEL, batch=self.batch)
        self.preview_btn = UIButton(
            15, 10, 110, 32, "PREVIEW", self.batch,
            color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
            on_click=self._on_preview,
        )
        self.generate_btn = UIButton(
            135, 10, 80, 32, "SAVE", self.batch,
            color=COL_GREEN_BTN, hover_color=COL_GREEN_HOVER,
            on_click=self._on_generate,
        )
        self.status_label = Label(
            "Status: Ready", x=230, y=20, font_name=FONT,
            font_size=11, color=COL_TEXT_LIGHT, batch=self.batch,
        )

    # ── Block management ─────────────────────────────────────────────────

    @property
    def _blocks_area_top(self) -> int:
        return self.WIN_H - 140

    @property
    def _blocks_area_bottom(self) -> int:
        return 55

    @property
    def _blocks_area_height(self) -> int:
        return self._blocks_area_top - self._blocks_area_bottom

    def _add_block(self, difficulty: float = 0.50, insert_at: int | None = None,
                   config: BlockConfig | None = None) -> None:
        if len(self.blocks) >= self.MAX_BLOCKS:
            return
        idx = len(self.blocks) if insert_at is None else insert_at
        bx = self.LEFT_W + 15
        bw = self.WIN_W - self.LEFT_W - self.SB_W - 20
        block = BlockWidgetGroup(
            idx, bx, 0, bw, self._blocks_batch, difficulty,
            on_remove=self._remove_block_at,
            on_duplicate=self._duplicate_block_at,
            on_move_up=lambda i: self._move_block(i, -1),
            on_move_down=lambda i: self._move_block(i, 1),
            on_advanced=self._open_advanced_panel,
        )
        if config is not None:
            block.duration_slider.value = config.duration_sec
            for name in block.PLUGIN_NAMES:
                if name in config.plugins:
                    block.toggles[name].value = True
                    block.sliders[name].value = config.plugins[name] * 100
                else:
                    block.toggles[name].value = False
        if insert_at is not None:
            self.blocks.insert(insert_at, block)
        else:
            self.blocks.append(block)
        self._update_scroll()

    def _duplicate_block_at(self, index: int) -> None:
        if len(self.blocks) >= self.MAX_BLOCKS:
            return
        source = self.blocks[index]
        cfg = source.get_block_config()
        self._add_block(insert_at=index + 1, config=cfg)

    def _move_block(self, index: int, direction: int) -> None:
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.blocks):
            return
        self.blocks[index], self.blocks[new_index] = self.blocks[new_index], self.blocks[index]
        self._update_scroll()

    def _remove_block_at(self, index: int) -> None:
        if len(self.blocks) <= 1:
            return
        block = self.blocks.pop(index)
        block.delete()
        if self.scroll_offset > 0:
            self.scroll_offset = max(0, self.scroll_offset - 1)
        self._update_scroll()

    def _scroll_up(self) -> None:
        if self.scroll_offset > 0:
            self.scroll_offset -= 1
            self._update_scroll()

    def _scroll_down(self) -> None:
        max_offset = self._max_scroll_offset()
        if self.scroll_offset < max_offset:
            self.scroll_offset += 1
            self._update_scroll()

    def _max_scroll_offset(self) -> int:
        n = len(self.blocks)
        card_step = BlockWidgetGroup.CARD_H + self.BLOCK_GAP
        iz_total = (n + 1) * (InsertZone.ZONE_H + self.BLOCK_GAP)
        ib_total = len(self._inter_block_widgets) * (InterBlockWidget.CARD_H + self.BLOCK_GAP * 2)
        total = n * card_step + iz_total + ib_total
        if total <= self._blocks_area_height:
            return 0
        overflow = total - self._blocks_area_height
        return max(0, -(-overflow // card_step))  # ceil division

    def _update_scroll(self) -> None:
        card_h = BlockWidgetGroup.CARD_H + self.BLOCK_GAP
        ib_h = InterBlockWidget.CARD_H + self.BLOCK_GAP * 2
        iz_h = InsertZone.ZONE_H + self.BLOCK_GAP
        area_top = self._blocks_area_top
        n_blocks = len(self.blocks)

        # Apply scroll offset: shift starting cursor up so scrolled blocks
        # are above the visible area
        cursor_y = area_top + self.scroll_offset * card_h + self.BLOCK_GAP

        for i, block in enumerate(self.blocks):
            # Insert zone BEFORE this block (position i)
            if i < len(self._insert_zones):
                zone = self._insert_zones[i]
                zone.position = i
                cursor_y -= iz_h
                zone.set_y(cursor_y)
                in_view = (cursor_y + iz_h > self._blocks_area_bottom
                           and cursor_y < area_top)
                zone.visible = in_view

            # Inter-block widgets at this position
            for iw in self._inter_block_widgets:
                if iw.position == i:
                    cursor_y -= ib_h
                    iw.set_y(cursor_y)
                    in_view = (cursor_y + ib_h > self._blocks_area_bottom
                               and cursor_y < area_top)
                    iw.visible = in_view

            # The block card itself
            card_y = cursor_y - BlockWidgetGroup.CARD_H
            block.set_y(card_y)
            cursor_y = card_y - self.BLOCK_GAP

            in_view = (card_y + BlockWidgetGroup.CARD_H > self._blocks_area_bottom
                       and card_y < area_top)
            block.visible = in_view
            block.index = i
            block.title.text = f"Block {i + 1}"

        # Insert zone AFTER the last block
        if n_blocks < len(self._insert_zones):
            zone = self._insert_zones[n_blocks]
            zone.position = n_blocks
            cursor_y -= iz_h
            zone.set_y(cursor_y)
            in_view = (cursor_y + iz_h > self._blocks_area_bottom
                       and cursor_y < area_top)
            zone.visible = in_view

        # Inter-block widgets after the last block
        for iw in self._inter_block_widgets:
            if iw.position == n_blocks:
                cursor_y -= ib_h
                iw.set_y(cursor_y)
                in_view = (cursor_y + ib_h > self._blocks_area_bottom
                           and cursor_y < area_top)
                iw.visible = in_view

        # Hide unused insert zones
        for j in range(n_blocks + 1, len(self._insert_zones)):
            self._insert_zones[j].visible = False

        # Update scrollbar thumb
        max_off = self._max_scroll_offset()
        if max_off <= 0:
            self._sb_thumb.visible = False
        else:
            self._sb_thumb.visible = True
            track_h = self._sb_track_h
            thumb_h = max(20, int(track_h * track_h /
                          (track_h + max_off * card_h)))
            ratio = self.scroll_offset / max_off
            thumb_y = self._sb_track_bottom + track_h - thumb_h - int(
                ratio * (track_h - thumb_h))
            self._sb_thumb.y = thumb_y
            self._sb_thumb.height = thumb_h

    # ── Config building & generation ─────────────────────────────────────

    def _build_config(self) -> ScenarioConfig:
        inter_block_events = [
            w.to_inter_block_event() for w in self._inter_block_widgets
        ]
        return ScenarioConfig(
            scenario_name=self.name_input.value,
            events_refractory_duration=int(self.refract_slider.value)
                if self.refract_slider.value == int(self.refract_slider.value)
                else self.refract_slider.value,
            communications_target_ratio=self.comm_slider.value / 100.0,
            average_auditory_prompt_duration=int(self.prompt_slider.value),
            blocks=[b.get_block_config() for b in self.blocks],
            inter_block_events=inter_block_events,
        )

    # ── Validation ─────────────────────────────────────────────────────

    def _validate(self) -> tuple[list[str], list[str]]:
        """Validate current config. Returns (errors, warnings)."""
        errors: list[str] = []
        warnings: list[str] = []

        if not self.name_input.value.strip():
            errors.append("Scenario name is empty")

        for i, block in enumerate(self.blocks):
            cfg = block.get_block_config()
            if cfg.duration_sec <= 0:
                errors.append(f"Block {i+1}: zero duration")
            if not cfg.plugins:
                warnings.append(f"Block {i+1}: no active plugin")
            # Check if communications events fit in duration
            if "communications" in cfg.plugins:
                comm_diff = cfg.plugins["communications"]
                avg_dur = self.prompt_slider.value + self.refract_slider.value
                est_events = int(comm_diff / (avg_dur / cfg.duration_sec)) if cfg.duration_sec > 0 else 0
                if est_events > 0 and est_events * avg_dur > cfg.duration_sec:
                    warnings.append(f"Block {i+1}: duration too short for comms")

        return errors, warnings

    def _update_validation_status(self) -> None:
        """Update the status bar with validation results."""
        errors, warnings = self._validate()
        if errors:
            self.status_label.text = f"Error: {errors[0]}"
            self.status_label.color = (200, 50, 50, 255)
        elif warnings:
            self.status_label.text = f"Warning: {warnings[0]}"
            self.status_label.color = COL_WARN
        else:
            self.status_label.text = "Status: Ready"
            self.status_label.color = COL_TEXT_LIGHT

    # ── Custom file selector ─────────────────────────────────────────

    # ── Preset save/load ─────────────────────────────────────────────

    def _save_preset(self) -> None:
        config = self._build_config()
        data = {
            "scenario_name": config.scenario_name,
            "events_refractory_duration": config.events_refractory_duration,
            "communications_target_ratio": config.communications_target_ratio,
            "average_auditory_prompt_duration": config.average_auditory_prompt_duration,
            "blocks": [
                {
                    "duration_sec": b.duration_sec,
                    "plugins": b.plugins,
                    "extra_events": [
                        {"plugin": p, "param": n, "value": v}
                        for p, n, v in b.extra_events
                    ],
                }
                for b in config.blocks
            ],
            "inter_block_events": [
                {"type": ie.type, "filename": ie.filename, "position": ie.position}
                for ie in config.inter_block_events
            ],
        }
        preset_dir = Path("includes", "scenarios", "presets")
        preset_dir.mkdir(parents=True, exist_ok=True)
        preset_path = preset_dir / f"{config.scenario_name}.json"
        with open(str(preset_path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.status_label.text = f"Config saved: {preset_path.name}"
        self.status_label.color = (0, 120, 60, 255)

    def _open_preset_selector(self) -> None:
        preset_dir = Path("includes", "scenarios", "presets")
        preset_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(preset_dir.glob("*.json"))
        self._overlay = UIFileSelector(
            self.WIN_W, self.WIN_H, self._overlay_batch, files,
            "Load a config",
            on_select=self._on_preset_selected,
            on_cancel=self._close_overlay,
        )

    def _on_preset_selected(self, path: Path) -> None:
        self._close_overlay()
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_preset(data)
            self.status_label.text = f"Config loaded: {path.name}"
            self.status_label.color = (0, 120, 60, 255)
        except Exception as e:
            self.status_label.text = f"Config error: {e}"
            self.status_label.color = (200, 50, 50, 255)

    def _apply_preset(self, data: dict) -> None:
        """Apply a loaded preset to all UI widgets."""
        self.name_input.value = data.get("scenario_name", "preset")
        self.comm_slider.value = data.get("communications_target_ratio", 0.5) * 100
        self.refract_slider.value = data.get("events_refractory_duration", 1)
        self.prompt_slider.value = data.get("average_auditory_prompt_duration", 13)

        # Remove existing blocks
        for b in self.blocks[:]:
            b.delete()
        self.blocks.clear()
        self.scroll_offset = 0

        # Rebuild blocks from preset
        for block_data in data.get("blocks", []):
            cfg = BlockConfig(
                duration_sec=block_data.get("duration_sec", 60),
                plugins=block_data.get("plugins", {}),
                extra_events=[
                    (ev["plugin"], ev["param"], ev["value"])
                    for ev in block_data.get("extra_events", [])
                ],
            )
            self._add_block(config=cfg)

        # Rebuild inter-block widgets
        for w in self._inter_block_widgets[:]:
            w.delete()
        self._inter_block_widgets.clear()
        for ie_data in data.get("inter_block_events", []):
            self._add_inter_block_widget(
                ie_data["position"], ie_data["type"], ie_data["filename"]
            )

    # ── Advanced parameters panel ────────────────────────────────────

    def _open_advanced_panel(self, block_index: int, plugin_name: str) -> None:
        block = self.blocks[block_index]
        current_params = block.advanced_params.get(plugin_name, {})
        self._adv_block_index = block_index
        self._adv_plugin_name = plugin_name
        self._overlay = UIAdvancedPanel(
            self.WIN_W, self.WIN_H, self._overlay_batch, plugin_name, current_params,
            on_save=self._on_advanced_save,
            on_cancel=self._close_overlay,
        )

    def _on_advanced_save(self, params: dict) -> None:
        block = self.blocks[self._adv_block_index]
        block.advanced_params[self._adv_plugin_name] = params
        self._close_overlay()

    # ── Inter-block events ───────────────────────────────────────────

    def _add_inter_block_widget(self, position: int, event_type: str,
                                filename: str) -> None:
        bx = self.LEFT_W + 15
        bw = self.WIN_W - self.LEFT_W - self.SB_W - 20
        widget = InterBlockWidget(
            position, event_type, filename, bx, 0, bw, self._blocks_batch,
            on_remove=self._remove_inter_block_widget,
        )
        self._inter_block_widgets.append(widget)
        self._update_scroll()

    def _remove_inter_block_widget(self, widget: InterBlockWidget) -> None:
        if widget in self._inter_block_widgets:
            self._inter_block_widgets.remove(widget)
            widget.delete()
            self._update_scroll()

    def _open_insert_menu(self, position: int) -> None:
        """Open a file selector to pick an instructions/questionnaire file."""
        # For now, we offer a type choice via a simple overlay
        # We'll use two separate methods triggered by the insert buttons
        pass

    def _insert_instructions_at(self, position: int) -> None:
        """Open file selector for instructions file at given position."""
        from core.constants import PATHS
        include_dir = Path("includes")
        files = sorted(include_dir.glob("**/*.txt")) + sorted(include_dir.glob("**/*.html"))
        self._pending_insert_position = position
        self._pending_insert_type = "instructions"
        self._overlay = UIFileSelector(
            self.WIN_W, self.WIN_H, self._overlay_batch, files,
            "Select an instructions file",
            on_select=self._on_interblock_file_selected,
            on_cancel=self._close_overlay,
        )

    def _insert_questionnaire_at(self, position: int) -> None:
        """Open file selector for genericscales file at given position."""
        include_dir = Path("includes")
        files = sorted(include_dir.glob("**/*.txt")) + sorted(include_dir.glob("**/*.html"))
        self._pending_insert_position = position
        self._pending_insert_type = "genericscales"
        self._overlay = UIFileSelector(
            self.WIN_W, self.WIN_H, self._overlay_batch, files,
            "Select a questionnaire",
            on_select=self._on_interblock_file_selected,
            on_cancel=self._close_overlay,
        )

    def _on_interblock_file_selected(self, path: Path) -> None:
        self._add_inter_block_widget(
            self._pending_insert_position,
            self._pending_insert_type,
            str(path),
        )
        self._close_overlay()

    # ── Overlay management ───────────────────────────────────────────

    def _close_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.delete()
            self._overlay = None

    # ── Preview & Generation ────────────────────────────────────────

    def _on_preview(self) -> None:
        errors, warnings = self._validate()
        if errors:
            self.status_label.text = f"Error: {errors[0]}"
            self.status_label.color = (200, 50, 50, 255)
            return

        self.status_label.text = "Status: Generating preview..."
        self.status_label.color = COL_TEXT
        self.on_draw()
        self.window.flip()

        try:
            config = self._build_config()
            from core.window import Window
            from plugins import Communications, Resman, Scheduling, Sysmon, Track

            win = Window()
            win.set_visible(False)
            plugins: dict[str, Any] = {
                "track": Track(win, silent=True),
                "sysmon": Sysmon(win),
                "communications": Communications(win),
                "resman": Resman(win),
                "scheduling": Scheduling(win),
            }

            lines = generate_scenario(config, plugins)
            win.close()
            self.window.switch_to()

            # Cache for reuse by _on_generate
            self._preview_lines = lines
            self._preview_config = config

            preview_lines = format_scenario_lines(lines, config)
            self._overlay = UIPreviewOverlay(
                self.WIN_W, self.WIN_H, self._overlay_batch,
                preview_lines, None, self._close_overlay,
            )
            self.status_label.text = "Status: Ready"
            self.status_label.color = COL_TEXT_LIGHT

        except Exception as e:
            self.status_label.text = f"Error: {e}"
            self.status_label.color = (200, 50, 50, 255)

    def _on_generate(self) -> None:
        # Validate first
        errors, warnings = self._validate()
        if errors:
            self.status_label.text = f"Error: {errors[0]}"
            self.status_label.color = (200, 50, 50, 255)
            return

        self.status_label.text = "Status: Saving..."
        self.status_label.color = COL_TEXT
        # Force a draw so the user sees the status update
        self.on_draw()
        self.window.flip()

        try:
            config = self._build_config()

            # Reuse preview if config unchanged
            if (self._preview_lines is not None
                    and self._preview_config is not None
                    and self._preview_config == config):
                lines = self._preview_lines
            else:
                from core.window import Window
                from plugins import Communications, Resman, Scheduling, Sysmon, Track

                win = Window()
                win.set_visible(False)
                plugins: dict[str, Any] = {
                    "track": Track(win, silent=True),
                    "sysmon": Sysmon(win),
                    "communications": Communications(win),
                    "resman": Resman(win),
                    "scheduling": Scheduling(win),
                }
                lines = generate_scenario(config, plugins)
                win.close()
                self.window.switch_to()

            path = write_scenario_file(lines, config)
            self._preview_lines = None
            self._preview_config = None
            self.status_label.text = f"Saved: {path.name}"
            self.status_label.color = (0, 120, 60, 255)

        except Exception as e:
            self.status_label.text = f"Error: {e}"
            self.status_label.color = (200, 50, 50, 255)

    # ── Event handlers ───────────────────────────────────────────────────

    def on_draw(self) -> None:
        glClearColor(0.94, 0.94, 0.94, 1.0)
        self.window.clear()
        self.batch.draw()
        # Draw scrollable blocks area with scissor clipping
        glEnable(GL_SCISSOR_TEST)
        glScissor(self.LEFT_W, self._blocks_area_bottom,
                  self.WIN_W - self.LEFT_W, self._blocks_area_height)
        self._blocks_batch.draw()
        glDisable(GL_SCISSOR_TEST)
        if self._overlay is not None:
            self._overlay_batch.draw()

    def on_mouse_press(self, mx: int, my: int, button: int, mod: int) -> bool:
        # Overlay takes priority
        if self._overlay is not None:
            return self._overlay.on_mouse_press(mx, my, button, mod)

        # Text input
        if self.name_input.on_mouse_press(mx, my, button, mod):
            return True
        # Left panel buttons
        for btn in (self.preview_btn, self.generate_btn, self.add_btn,
                    self.scroll_up_btn, self.scroll_down_btn,
                    self.save_preset_btn, self.load_preset_btn):
            if btn.on_mouse_press(mx, my, button, mod):
                return True
        # Scrollbar track click
        if (self._sb_thumb.visible
                and self.WIN_W - self._sb_width - 4 <= mx <= self.WIN_W
                and self._sb_track_bottom <= my <= self._sb_track_bottom + self._sb_track_h):
            self._sb_dragging = True
            self._sb_click_to_scroll(my)
            return True
        # Global sliders
        for slider in (self.comm_slider, self.refract_slider, self.prompt_slider):
            if slider.on_mouse_press(mx, my, button, mod):
                return True
        # Insert zones
        for zone in self._insert_zones:
            if zone.visible and zone.on_mouse_press(mx, my, button, mod):
                return True
        # Inter-block widgets
        for iw in self._inter_block_widgets:
            if iw.visible and iw.on_mouse_press(mx, my, button, mod):
                return True
        # Block widgets
        for block in self.blocks:
            if block.visible and block.on_mouse_press(mx, my, button, mod):
                return True
        return False

    def _sb_click_to_scroll(self, my: int) -> None:
        """Set scroll offset based on mouse Y position on the scrollbar track."""
        max_off = self._max_scroll_offset()
        if max_off <= 0:
            return
        track_h = self._sb_track_h
        clamped_y = max(self._sb_track_bottom, min(my, self._sb_track_bottom + track_h))
        ratio = 1.0 - (clamped_y - self._sb_track_bottom) / track_h
        self.scroll_offset = max(0, min(max_off, int(ratio * max_off + 0.5)))
        self._update_scroll()

    def on_mouse_drag(self, mx: int, my: int, dx: int, dy: int, buttons: int, mod: int) -> bool:
        if self._overlay is not None:
            if hasattr(self._overlay, 'on_mouse_drag'):
                return self._overlay.on_mouse_drag(mx, my, dx, dy, buttons, mod)
            return True
        if self._sb_dragging:
            self._sb_click_to_scroll(my)
            return True
        for slider in (self.comm_slider, self.refract_slider, self.prompt_slider):
            if slider.on_mouse_drag(mx, my, dx, dy, buttons, mod):
                return True
        for block in self.blocks:
            if block.visible and block.on_mouse_drag(mx, my, dx, dy, buttons, mod):
                return True
        return False

    def on_mouse_release(self, mx: int, my: int, button: int, mod: int) -> bool:
        if self._overlay is not None:
            if hasattr(self._overlay, 'on_mouse_release'):
                return self._overlay.on_mouse_release(mx, my, button, mod)
            return True
        if self._sb_dragging:
            self._sb_dragging = False
            return True
        for slider in (self.comm_slider, self.refract_slider, self.prompt_slider):
            if slider.on_mouse_release(mx, my, button, mod):
                return True
        for block in self.blocks:
            if block.visible and block.on_mouse_release(mx, my, button, mod):
                return True
        return False

    def on_mouse_motion(self, mx: int, my: int, dx: int, dy: int) -> None:
        if self._overlay is not None:
            self._overlay.on_mouse_motion(mx, my, dx, dy)
            return
        for btn in (self.preview_btn, self.generate_btn, self.add_btn,
                    self.scroll_up_btn, self.scroll_down_btn,
                    self.save_preset_btn, self.load_preset_btn):
            btn.on_mouse_motion(mx, my, dx, dy)
        for zone in self._insert_zones:
            if zone.visible:
                zone.on_mouse_motion(mx, my, dx, dy)
        for iw in self._inter_block_widgets:
            if iw.visible:
                iw.on_mouse_motion(mx, my, dx, dy)
        for block in self.blocks:
            if block.visible:
                block.on_mouse_motion(mx, my, dx, dy)

    def on_mouse_scroll(self, mx: int, my: int, scroll_x: float, scroll_y: float) -> bool:
        if self._overlay is not None:
            return self._overlay.on_mouse_scroll(mx, my, scroll_x, scroll_y)
        # Scroll blocks panel if mouse is in the right area
        if mx > self.LEFT_W:
            if scroll_y > 0:
                self._scroll_up()
            elif scroll_y < 0:
                self._scroll_down()
            return True
        return False

    def on_text(self, text: str) -> bool:
        if self._overlay is not None:
            return True
        return self.name_input.on_text(text)

    def on_key_press(self, symbol: int, mod: int) -> bool:
        if self._overlay is not None:
            return self._overlay.on_key_press(symbol, mod)
        if symbol == winkey.ESCAPE:
            self.window.close()
            return True
        return self.name_input.on_key_press(symbol, mod)

    def on_close(self) -> None:
        pyglet.app.exit()

    def run(self) -> None:
        pyglet.app.run()


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ui = ScenarioGeneratorUI()
    ui.run()
