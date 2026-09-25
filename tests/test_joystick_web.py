"""Tests for core.joystick.WebGamepadDevice (joysticks read with the browser Gamepad API)."""

from types import SimpleNamespace
from unittest.mock import patch

import core.joystick as joystick_module
from core.joystick import WEB_MAX_BUTTONS, Joystick, WebGamepadDevice


def _gamepad(axes, pressed, mapping="", name="Logitech Extreme 3D pro (Vendor: 046d Product: c215)"):
    return SimpleNamespace(
        id=name,
        connected=True,
        mapping=mapping,
        axes=list(axes),
        buttons=[SimpleNamespace(pressed=p) for p in pressed],
    )


def _device(gamepads):
    state = {"gamepads": gamepads}
    return WebGamepadDevice(get_gamepads=lambda: state["gamepads"]), state


class TestFlightJoystick:
    def test_stick_axes_are_x_and_y(self):
        """Axes 0 and 1 are the stick; rudder, throttle and hat axes are ignored."""
        device, _ = _device([_gamepad([0.25, -0.5, 0.9, -1.0], [False] * 12)])
        with patch.object(joystick_module, "get_logger"):
            device.poll()
        assert (device.x, device.y) == (0.25, -0.5)

    def test_buttons_are_padded_to_a_fixed_count(self):
        device, _ = _device([_gamepad([0, 0], [True, False, True])])
        with patch.object(joystick_module, "get_logger"):
            device.poll()
        assert len(device.buttons) == WEB_MAX_BUTTONS
        assert device.buttons[:4] == [True, False, True, False]

    def test_non_standard_joystick_has_no_hat(self):
        device, _ = _device([_gamepad([0, 0], [True] * 16)])
        with patch.object(joystick_module, "get_logger"):
            device.poll()
        assert (device.hat_x, device.hat_y) == (0, 0)


class TestConnection:
    def test_neutral_until_a_joystick_is_revealed(self):
        """The browser reveals a joystick only after a button press: stay neutral until then."""
        device, state = _device([None, None])
        with patch.object(joystick_module, "get_logger") as get_logger:
            device.poll()
            assert device.name is None
            assert (device.x, device.y) == (0, 0)

            state["gamepads"] = [None, _gamepad([0.5, 0.5], [False] * 12)]
            device.poll()
            device.poll()
        assert device.name.startswith("Logitech")
        assert (device.x, device.y) == (0.5, 0.5)
        get_logger.return_value.log_manual_entry.assert_called_once_with(device.name, key="joystick")

    def test_back_to_neutral_when_disconnected(self):
        device, state = _device([_gamepad([0.5, 0.5], [True] * 12)])
        with patch.object(joystick_module, "get_logger"):
            device.poll()
            state["gamepads"] = [None]
            device.poll()
        assert device.name is None
        assert (device.x, device.y) == (0, 0)
        assert not any(device.buttons)


class TestStandardGamepad:
    def test_dpad_is_used_as_hat(self):
        pressed = [False] * 17
        pressed[12] = True  # up
        pressed[15] = True  # right
        device, _ = _device([_gamepad([0, 0, 0, 0], pressed, mapping="standard")])
        with patch.object(joystick_module, "get_logger"):
            device.poll()
        assert (device.hat_x, device.hat_y) == (1, 1)


class TestJoystickWithWebDevice:
    def test_joystick_reads_the_device_and_detects_button_presses(self):
        """The desktop Joystick class works unchanged on top of the browser device."""
        device, state = _device([None])
        with patch.object(joystick_module, "get_logger"):
            joystick = Joystick(device)
            joystick.update()
            assert (joystick.x, joystick.y) == (0, 0)

            pressed = [False] * 12
            pressed[0] = True
            state["gamepads"] = [_gamepad([-0.3, 0.7], pressed)]
            joystick.update()
        assert (joystick.x, joystick.y) == (-0.3, 0.7)
        assert joystick.keys["JOY_BTN_1"] is True
        assert joystick.key_change["JOY_BTN_1"] == "press"
