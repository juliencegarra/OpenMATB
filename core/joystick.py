from __future__ import annotations

from typing import Any

import pyglet.input

from core.constants import REPLAY_MODE
from core.error import get_errors
from core.logger import get_logger

hat_sides: list[str] = ["LEFT", "UP", "RIGHT", "DOWN"]


class Joystick:
    def __init__(self, device: Any) -> None:
        self.device: Any = device
        self.keys: dict[str, bool] = dict()
        self.x: float = 0
        self.y: float = 0
        try:  # Just in case Joystick is opened twice (?)
            self.open()
        except OSError:
            pass

        # Define joystick keys (BTN, HAT)
        # 1. Add buttons (the number of which can vary)
        self.keys.update({f"JOY_BTN_{numb + 1}": False for numb in range(len(self.device.buttons))})

        # 2. Add HAT directions as buttons
        self.keys.update({f"JOY_HAT_{side}": False for side in hat_sides})

        # Create a parallel dict of keys for tracking key changes
        self.key_change: dict[str, str | None] = {key: None for key in self.keys}

    def open(self) -> None:
        self.device.open()

    def is_key_pressed(self, key: str) -> bool:
        return self.keys[key] is True

    def has_any_key_changed(self) -> bool:
        return any([v is not None for k, v in self.key_change.items()])

    def reset_key_change(self, keystr: str) -> None:
        self.key_change[keystr] = None

    def update(self) -> None:
        # Update x & y joystick values
        if self.device.x != self.x:
            self.x = self.device.x
            get_logger().record_input("joystick", "x", self.x)
        if self.device.y != self.y:
            self.y = self.device.y
            get_logger().record_input("joystick", "y", self.y)

        # Update button values
        # (Keep a copy of previous state to check for state changes)
        previous_state: dict[str, bool] = dict(self.keys)
        for numb, button_state in enumerate(self.device.buttons):
            self.keys[f"JOY_BTN_{numb + 1}"] = button_state

        # Update hat values as buttons (left, top, right, down)
        # Check hat x & y, and convert to bolleans (pressed, released)
        # Process x axis
        if self.device.hat_x == -1:
            self.keys["JOY_HAT_LEFT"], self.keys["JOY_HAT_RIGHT"] = True, False
        elif self.device.hat_x == 1:
            self.keys["JOY_HAT_LEFT"], self.keys["JOY_HAT_RIGHT"] = False, True
        elif self.device.hat_x == 0:
            self.keys["JOY_HAT_LEFT"] = self.keys["JOY_HAT_RIGHT"] = False

        # Process y axis
        if self.device.hat_y == -1:
            self.keys["JOY_HAT_DOWN"], self.keys["JOY_HAT_UP"] = True, False
        elif self.device.hat_y == 1:
            self.keys["JOY_HAT_DOWN"], self.keys["JOY_HAT_UP"] = False, True
        elif self.device.hat_y == 0:
            self.keys["JOY_HAT_DOWN"] = self.keys["JOY_HAT_UP"] = False

        # Maintain a dict that tracks only buttons state changes (press, release)
        for key in self.keys:
            if previous_state[key] is False and self.keys[key] is True:  # Press
                self.key_change[key] = "press"
                get_logger().record_input("Joystick", key, "press")
            elif previous_state[key] is True and self.keys[key] is False:  # Released
                self.key_change[key] = "released"
                get_logger().record_input("Joystick", key, "release")


joykey: dict[str, bool] | None = None
joystick: Joystick | None = None
# Search and find a joystick
joysticks: list[Any] = pyglet.input.get_joysticks()

if not REPLAY_MODE:
    if len(joysticks) > 0:
        joystick_device: Any = joysticks[0]
        joystick = Joystick(joystick_device)
        joykey = joystick.keys
    else:
        get_errors().add_error(_("No joystick found"))
