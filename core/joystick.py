from __future__ import annotations

from typing import Any, Callable

import pyglet.input

from core.constants import REPLAY_MODE
from core.error import get_errors
from core.logger import get_logger
from core.platform import IS_WEB

hat_sides: list[str] = ["LEFT", "UP", "RIGHT", "DOWN"]

# Browser joysticks: the number of buttons is only known once the joystick is connected
WEB_MAX_BUTTONS: int = 32
# Gamepad API "standard" layout: D-pad buttons, used as hat
STANDARD_DPAD: dict[str, int] = {"UP": 12, "DOWN": 13, "LEFT": 14, "RIGHT": 15}


def _browser_gamepads() -> list[Any]:
    import js

    gamepads = js.navigator.getGamepads()
    return [gamepads[i] for i in range(gamepads.length)]


class WebGamepadDevice:
    """A joystick read with the browser Gamepad API, with the attributes of a pyglet joystick device.

    pyglet does not support joysticks in the browser. Any USB joystick is exposed by the Gamepad API
    (once a button has been pressed while the page has the focus): for flight joysticks, axes 0 and 1
    are the stick (roll and pitch); other axes (rudder, throttle, hat) are ignored.
    """

    def __init__(self, get_gamepads: Callable[[], list[Any]] = _browser_gamepads) -> None:
        self._get_gamepads: Callable[[], list[Any]] = get_gamepads
        self.name: str | None = None  # Set once a joystick is connected
        self.x: float = 0
        self.y: float = 0
        self.buttons: list[bool] = [False] * WEB_MAX_BUTTONS
        self.hat_x: int = 0
        self.hat_y: int = 0

    def open(self) -> None:
        pass

    def poll(self) -> None:
        gamepad: Any = next((g for g in self._get_gamepads() if g is not None and g.connected), None)
        if gamepad is None:
            self.name = None
            self.x = self.y = 0
            self.buttons = [False] * WEB_MAX_BUTTONS
            self.hat_x = self.hat_y = 0
            return

        if self.name != gamepad.id:
            self.name = str(gamepad.id)
            get_logger().log_manual_entry(self.name, key="joystick")

        axes: list[float] = [float(a) for a in gamepad.axes]
        self.x = axes[0] if len(axes) > 0 else 0
        self.y = axes[1] if len(axes) > 1 else 0

        pressed: list[bool] = [bool(b.pressed) for b in gamepad.buttons][:WEB_MAX_BUTTONS]
        self.buttons = pressed + [False] * (WEB_MAX_BUTTONS - len(pressed))

        if gamepad.mapping == "standard":
            self.hat_x = int(pressed[STANDARD_DPAD["RIGHT"]]) - int(pressed[STANDARD_DPAD["LEFT"]])
            self.hat_y = int(pressed[STANDARD_DPAD["UP"]]) - int(pressed[STANDARD_DPAD["DOWN"]])


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
        if hasattr(self.device, "poll"):  # Browser joystick: read the Gamepad API
            self.device.poll()

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

if IS_WEB:
    # The browser reveals a joystick only after one of its buttons is pressed: wait for it
    if not REPLAY_MODE:
        joystick = Joystick(WebGamepadDevice())
        joykey = joystick.keys
elif not REPLAY_MODE:
    # Search and find a joystick
    joysticks: list[Any] = pyglet.input.get_joysticks()
    if len(joysticks) > 0:
        joystick_device: Any = joysticks[0]
        joystick = Joystick(joystick_device)
        joykey = joystick.keys
    else:
        get_errors().add_error(_("No joystick found"))
