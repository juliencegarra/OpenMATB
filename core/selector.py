# Copyright 2023-2026, by Julien Cegarra & Benoit Valery. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import time as _time
import pyglet
from pyglet.window import key as winkey, mouse
from pyglet.text import Label
from pyglet.gl import GL_POLYGON
from datetime import datetime
from core.constants import PATHS as P, COLORS as C, FONT_SIZES as F, Group as G


class FileSelector:
    """
    A pyglet-based file selection screen displayed before the main MATB task.
    Supports scenario files (.txt) and replay session files (.csv).
    """

    _BG_GROUP = G(30)
    _HIGHLIGHT_GROUP = G(31)
    _LABEL_GROUP = G(32)

    def __init__(self, win, mode='scenario'):
        self.win = win
        self.mode = mode
        self._done = False
        self._selected_path = None

        # Scan files
        self._files = self._scan_files()
        self._display_texts = [self._format_entry(f) for f in self._files]

        # Selection / scroll state
        self._selected_index = 0 if self._files else -1
        self._scroll_offset = 0

        # Layout constants
        self._margin = 40
        self._row_height = 32
        self._title_area = 70
        self._footer_area = 50
        self._list_left = self._margin + 10
        self._list_width = self.win.width - 2 * self._margin

        # Visible rows
        usable_h = self.win.height - 2 * self._margin - self._title_area - self._footer_area
        self._visible_rows = max(1, int(usable_h / self._row_height))
        self._list_top = self.win.height - self._margin - self._title_area

        # Double-click tracking
        self._last_click_time = 0
        self._last_click_index = -1

        # Graphics objects
        self._vertices = []
        self._label_pool = []
        self._build_ui()

    # ---- File scanning ----

    def _scan_files(self):
        if self.mode == 'scenario':
            return sorted(P['SCENARIOS'].glob('**/*.txt'))
        files = list(P['SESSIONS'].glob('**/*.csv'))
        return sorted(files, key=self._session_sort_key)

    @staticmethod
    def _session_sort_key(path):
        try:
            return int(path.stem.split('_')[0])
        except (ValueError, IndexError):
            return 0

    def _format_entry(self, filepath):
        if self.mode == 'scenario':
            return str(filepath.relative_to(P['SCENARIOS']).with_suffix(''))
        # Replay: parse {ID}_{YYMMDD}_{HHMMSS}.csv
        parts = filepath.stem.split('_')
        if len(parts) >= 3:
            try:
                dt = datetime.strptime(parts[1] + parts[2], '%y%m%d%H%M%S')
                return f"#{parts[0]} \u2014 {dt.strftime('%Y-%m-%d %H:%M:%S')}"
            except ValueError:
                pass
        return filepath.stem

    # ---- UI building ----

    def _build_ui(self):
        w, h = self.win.width, self.win.height

        # Full-screen background
        self._vertices.append(
            self.win.batch.add(4, GL_POLYGON, self._BG_GROUP,
                ('v2f/static', (0, h, w, h, w, 0, 0, 0)),
                ('c4B', C['BACKGROUND'] * 4)))

        # Title
        title_text = (_("Select a scenario") if self.mode == 'scenario'
                      else _("Select a session"))
        self._title_label = Label(title_text,
            x=w // 2, y=h - self._margin - self._title_area // 2,
            anchor_x='center', anchor_y='center',
            font_size=F['XLARGE'], color=C['BLACK'],
            group=self._LABEL_GROUP, batch=self.win.batch)
        self._vertices.append(self._title_label)

        # Footer instructions
        footer = (_("UP/DOWN: Navigate") + " \u2014 "
                  + _("Enter: Select") + " \u2014 "
                  + _("Esc: Quit"))
        self._footer_label = Label(footer,
            x=w // 2, y=self._margin + self._footer_area // 2,
            anchor_x='center', anchor_y='center',
            font_size=F['SMALL'], color=(150, 150, 150, 255),
            group=self._LABEL_GROUP, batch=self.win.batch)
        self._vertices.append(self._footer_label)

        # Highlight bar (dynamic vertices)
        self._highlight = self.win.batch.add(4, GL_POLYGON, self._HIGHLIGHT_GROUP,
            ('v2f/dynamic', (0, 0, 0, 0, 0, 0, 0, 0)),
            ('c4B', C['BLUE'] * 4))
        self._vertices.append(self._highlight)

        # Label pool for visible rows
        for i in range(self._visible_rows):
            y = self._list_top - (i + 0.5) * self._row_height
            lbl = Label('',
                x=self._list_left, y=y,
                anchor_x='left', anchor_y='center',
                font_size=F['MEDIUM'], color=C['BLACK'],
                group=self._LABEL_GROUP, batch=self.win.batch)
            self._label_pool.append(lbl)
            self._vertices.append(lbl)

        # "No files found" fallback
        if not self._files:
            lbl = Label(_("No files found"),
                x=w // 2, y=h // 2,
                anchor_x='center', anchor_y='center',
                font_size=F['LARGE'], color=C['BLACK'],
                group=self._LABEL_GROUP, batch=self.win.batch)
            self._vertices.append(lbl)

        self._refresh_display()

    # ---- Display refresh ----

    def _refresh_display(self):
        for i, lbl in enumerate(self._label_pool):
            file_idx = self._scroll_offset + i
            if file_idx < len(self._display_texts):
                lbl.text = self._display_texts[file_idx]
                lbl.color = C['WHITE'] if file_idx == self._selected_index else C['BLACK']
            else:
                lbl.text = ''

        # Highlight bar position
        vis_idx = self._selected_index - self._scroll_offset
        if 0 <= vis_idx < self._visible_rows and 0 <= self._selected_index < len(self._files):
            y = self._list_top - (vis_idx + 1) * self._row_height
            x = self._margin
            w = self._list_width
            self._highlight.vertices = [
                x, y + self._row_height,
                x + w, y + self._row_height,
                x + w, y,
                x, y]
        else:
            self._highlight.vertices = [0, 0, 0, 0, 0, 0, 0, 0]

    def _ensure_visible(self):
        if self._selected_index < self._scroll_offset:
            self._scroll_offset = self._selected_index
        elif self._selected_index >= self._scroll_offset + self._visible_rows:
            self._scroll_offset = self._selected_index - self._visible_rows + 1

    # ---- Event handlers ----

    def _on_key_press(self, symbol, modifiers):
        if symbol == winkey.ESCAPE:
            self._selected_path = None
            self._done = True
        elif symbol in (winkey.RETURN, winkey.NUM_ENTER):
            if self._files:
                self._selected_path = self._files[self._selected_index]
                self._done = True
        elif symbol == winkey.UP:
            if self._selected_index > 0:
                self._selected_index -= 1
                self._ensure_visible()
                self._refresh_display()
        elif symbol == winkey.DOWN:
            if self._selected_index < len(self._files) - 1:
                self._selected_index += 1
                self._ensure_visible()
                self._refresh_display()
        elif symbol == winkey.HOME:
            self._selected_index = 0
            self._ensure_visible()
            self._refresh_display()
        elif symbol == winkey.END:
            if self._files:
                self._selected_index = len(self._files) - 1
                self._ensure_visible()
                self._refresh_display()
        elif symbol == winkey.PAGEUP:
            self._selected_index = max(0, self._selected_index - self._visible_rows)
            self._ensure_visible()
            self._refresh_display()
        elif symbol == winkey.PAGEDOWN:
            if self._files:
                self._selected_index = min(len(self._files) - 1,
                                           self._selected_index + self._visible_rows)
                self._ensure_visible()
                self._refresh_display()
        return True  # consume event

    def _on_key_release(self, symbol, modifiers):
        return True  # consume event

    def _on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if not self._files:
            return True
        max_offset = max(0, len(self._files) - self._visible_rows)
        self._scroll_offset = max(0, min(max_offset,
                                         self._scroll_offset - int(scroll_y)))
        if self._selected_index < self._scroll_offset:
            self._selected_index = self._scroll_offset
        elif self._selected_index >= self._scroll_offset + self._visible_rows:
            self._selected_index = self._scroll_offset + self._visible_rows - 1
        self._refresh_display()
        return True

    def _row_index_at_y(self, y):
        row = int((self._list_top - y) / self._row_height)
        if 0 <= row < self._visible_rows:
            file_idx = self._scroll_offset + row
            if file_idx < len(self._files):
                return file_idx
        return None

    def _on_mouse_press(self, x, y, button, modifiers):
        if button != mouse.LEFT or not self._files:
            return True
        idx = self._row_index_at_y(y)
        if idx is None:
            return True

        now = _time.monotonic()
        # Double-click: second click on same item within 0.4 s → confirm
        if idx == self._last_click_index and (now - self._last_click_time) < 0.4:
            self._selected_path = self._files[idx]
            self._done = True
        else:
            self._selected_index = idx
            self._refresh_display()

        self._last_click_time = now
        self._last_click_index = idx
        return True

    # ---- Main loop ----

    def run(self):
        if not self._files:
            self._cleanup()
            return None

        self.win.push_handlers(
            on_key_press=self._on_key_press,
            on_key_release=self._on_key_release,
            on_mouse_scroll=self._on_mouse_scroll,
            on_mouse_press=self._on_mouse_press)

        while not self._done:
            pyglet.clock.tick()
            self.win.dispatch_events()
            self.win.set_mouse_visible(True)
            self.win.clear()
            self.win.batch.draw()
            self.win.flip()

        self._cleanup()
        self.win.pop_handlers()
        return self._selected_path

    def _cleanup(self):
        for v in self._vertices:
            if v is not None:
                v.delete()
        self._vertices.clear()
        self._label_pool.clear()
