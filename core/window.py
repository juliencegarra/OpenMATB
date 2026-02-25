# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pyglet import gl, image
from pyglet.display import get_display
from pyglet.gl import glClearColor
from pyglet.graphics import Batch
from pyglet.shapes import Rectangle
from pyglet.window import Window
from pyglet.window import key as winkey

from core.constants import COLORS as C
from core.constants import HEADLESS_MODE
from core.constants import PATHS as P
from core.constants import PLUGIN_TITLE_HEIGHT_PROPORTION, REPLAY_MODE, REPLAY_PERF_STRIP_PROPORTION, REPLAY_STRIP_PROPORTION
from core.constants import Group as G
from core.container import Container
from core.logger import get_logger
from core.modaldialog import ModalDialog
from core.utils import get_conf_value


class Window(Window):
    # Static variable
    MainWindow: Window | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Window.MainWindow = self  # correct way to set it as a static

        screen: Any = self.get_screen()

        self._width: int = int(screen.width)
        self._height: int = int(screen.height)
        self._fullscreen: bool = False if HEADLESS_MODE else get_conf_value("Openmatb", "fullscreen")

        # Enable 4x multisampling antialiasing (MSAA) for smooth edges
        config: Any = screen.get_best_config(gl.Config(
            sample_buffers=1, samples=4,
            double_buffer=True,
        ))

        super().__init__(
            fullscreen=self._fullscreen, width=self._width, height=self._height,
            vsync=True, config=config, *args, **kwargs
        )

        img_path: Any = P["IMG"]
        logo16: Any = image.load(img_path.joinpath("logo16.png"))
        logo32: Any = image.load(img_path.joinpath("logo32.png"))
        self.set_icon(logo16, logo32)

        self.set_size_and_location(screen)  # Postpone multiple monitor support
        self.set_mouse_visible(REPLAY_MODE)

        if HEADLESS_MODE:
            self.set_visible(False)

        self.batch: Batch = Batch()
        self.keyboard: dict[str, bool] = dict()  # Reproduce a simple KeyStateHandler

        self.create_MATB_background()
        self.alive: bool = True
        self.modal_dialog: ModalDialog | None = None
        self.slider_visible: bool = False
        self.mouse_control_active: bool = False
        self.on_key_press_replay: Any | None = None  # used by the replay

    def display_session_id(self) -> None:
        # Display the session ID if needed at window instanciation
        if HEADLESS_MODE:
            return
        if not REPLAY_MODE and get_conf_value("Openmatb", "display_session_number"):
            msg: str = _("Session ID: %s") % get_logger().session_id
            title: str = "OpenMATB"

            self.modal_dialog = ModalDialog(self, msg, title)

    def get_screen(self) -> Any:
        # Screen definition
        try:
            screen_index: int = get_conf_value("Openmatb", "screen_index")
        except (KeyError, TypeError):
            screen_index = 0

        screens: list[Any] = get_display().get_screens()
        if screen_index + 1 > len(screens):
            screen: Any = screens[-1]
            from core.error import get_errors

            get_errors().add_error(
                _(
                    "In config.ini, the specified screen index exceeds the number of"
                    " available screens (%s). Last screen selected."
                )
                % len(get_display().get_screens())
            )
        else:
            screen = screens[screen_index]

        return screen

    def set_size_and_location(self, screen: Any) -> None:
        self.switch_to()  # The Window must be active before setting the location
        target_x: float = (screen.x + screen.width / 2) - screen.width / 2
        target_y: float = (screen.y + screen.height / 2) - screen.height / 2
        self.set_location(int(target_x), int(target_y))

    def create_MATB_background(self) -> None:
        MATB_container: Container = self.get_container("fullscreen")
        l, b, w, h = MATB_container.get_lbwh()
        container_title_h: float = PLUGIN_TITLE_HEIGHT_PROPORTION / 2

        # Main background
        bg = Rectangle(x=l, y=b, width=w, height=h,
                        color=C["BACKGROUND"][:3], batch=self.batch, group=G(-1))
        bg.opacity = C["BACKGROUND"][3]

        # Upper band
        upper_h: float = h * container_title_h
        upper_y: float = b + h - upper_h
        upper = Rectangle(x=l, y=upper_y, width=w, height=upper_h,
                           color=C["BLACK"][:3], batch=self.batch, group=G(-1))
        upper.opacity = C["BLACK"][3]

        # Middle band
        mid_h: float = h * container_title_h
        mid_y: float = b + h * (0.5 - container_title_h)
        mid = Rectangle(x=l, y=mid_y, width=w, height=mid_h,
                         color=C["BLACK"][:3], batch=self.batch, group=G(0))
        mid.opacity = C["BLACK"][3]

        self.bg_shapes: list[Rectangle] = [bg, upper, mid]

    def set_bg_bands_visible(self, visible: bool) -> None:
        for band in self.bg_shapes[1:]:
            band.visible = visible

    def take_screenshot(self) -> None:
        """Capture the OpenGL framebuffer directly (bypasses DWM cache issues)."""
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(f"screenshot_{timestamp}.png")
        color_buffer = image.get_buffer_manager().get_color_buffer()
        color_buffer.save(str(filepath))
        get_logger().log_manual_entry(str(filepath), key="screenshot")

    def on_draw(self) -> None:
        self.set_mouse_visible(self.is_mouse_necessary())
        glClearColor(0, 0, 0, 1)
        self.clear()
        self.batch.draw()

    def is_mouse_necessary(self) -> bool:
        return self.slider_visible or REPLAY_MODE or self.mouse_control_active

    # Log any keyboard input, either plugins accept it or not
    # is subclassed in replay mode
    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == winkey.F12:
            self.take_screenshot()
            return

        if REPLAY_MODE:
            return

        if self.modal_dialog is None:
            keystr: str = winkey.symbol_string(symbol)
            self.keyboard[keystr] = True  # KeyStateHandler

            if keystr == "ESCAPE":
                self.exit_prompt()
            elif keystr == "P":
                self.pause_prompt()

            get_logger().record_input("keyboard", keystr, "press")

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        if self.modal_dialog is not None:
            self.modal_dialog.on_key_release(symbol, modifiers)
            return

        if REPLAY_MODE:
            return

        keystr: str = winkey.symbol_string(symbol)
        self.keyboard[keystr] = False  # KeyStateHandler
        get_logger().record_input("keyboard", keystr, "release")

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        if REPLAY_MODE:
            return
        get_logger().record_input("mouse", "x", x)
        get_logger().record_input("mouse", "y", y)

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int) -> None:
        if REPLAY_MODE:
            return
        get_logger().record_input("mouse", "x", x)
        get_logger().record_input("mouse", "y", y)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        if REPLAY_MODE:
            return
        get_logger().record_input("mouse", "click", f"press;{x};{y};{button}")

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        if REPLAY_MODE:
            return
        get_logger().record_input("mouse", "click", f"release;{x};{y};{button}")

    def exit_prompt(self) -> None:
        if HEADLESS_MODE:
            return
        self.modal_dialog = ModalDialog(self, _("You hit the Escape key"), title=_("Exit OpenMATB?"), exit_key="q")

    def pause_prompt(self) -> None:
        if HEADLESS_MODE:
            return
        self.modal_dialog = ModalDialog(self, _("Pause"))

    def exit(self) -> None:
        self.alive = False

    def get_container_list(self) -> list[Container]:
        mar: float = REPLAY_STRIP_PROPORTION if REPLAY_MODE else 0
        perf_mar: float = REPLAY_PERF_STRIP_PROPORTION if REPLAY_MODE else 0
        w: float = (1 - mar) * self.width
        h: float = (1 - mar - perf_mar) * self.height
        b: float = self.height * mar

        # Vertical bounds
        x1, x2 = (int(w * bound) for bound in get_conf_value("Openmatb", "top_bounds"))  # Top row
        x3, x4 = (int(w * bound) for bound in get_conf_value("Openmatb", "bottom_bounds"))  # Bottom row

        # Horizontal bound
        y1: float = b + h / 2

        return [
            Container("invisible", 0, 0, 0, 0),
            Container("fullscreen", 0, b, w, h),
            Container("topleft", 0, y1, x1, h / 2),
            Container("topmid", x1, y1, x2 - x1, h / 2),
            Container("topright", x2, y1, w - x2, h / 2),
            Container("bottomleft", 0, b, x3, h / 2),
            Container("bottommid", x3, b, x4 - x3, h / 2),
            Container("bottomright", x4, b, w - x4, h / 2),
            Container("mediastrip", 0, 0, self._width * (1 + mar), b),
            Container("inputstrip", w, b, self._width * mar, h),
            Container("perfstrip", 0, b + h, self._width * (1 + mar), self.height * perf_mar),
        ]

    def get_container(self, placement_name: str) -> Container | None:
        container: list[Container] = [c for c in self.get_container_list() if c.name == placement_name]
        if len(container) > 0:
            return container[0]
        else:
            print(_("Error. No placement found for the [%s] alias") % placement_name)

    def open_modal_window(self, pass_list: list[str], title: str, continue_key: str | None, exit_key: str) -> None:
        self.modal_dialog = ModalDialog(self, pass_list, title=title, continue_key=continue_key, exit_key="Q")
