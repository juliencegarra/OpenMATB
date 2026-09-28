# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

from core import get_logger


class AbstractAgent(ABC):
    """Base class for agents that can control plugins when automaticsolver is True."""

    def __init__(self, name: str = "agent", automode_string: str = "AUTO") -> None:
        self.name = name
        self.automode_string = automode_string
        self.allows_human_input: bool = False

    @abstractmethod
    def on_plugin_update(self, plugin: Any, scenario_time: float) -> None:
        """Called each frame for each active plugin with automaticsolver=True.
        Handles periodic actions: resman (pumps), track (compensation),
        comms (tuning), sysmon (failure resolution)."""
        ...

    @abstractmethod
    def on_failure_started(self, plugin: Any, gauge: dict) -> dict:
        """Called when a sysmon failure starts and automaticsolver=True.
        Returns a dict that may contain {"delay": N} to set the safety-net timer
        (the agent resolves failures actively via on_plugin_update)."""
        ...

    def get_automode_string(self) -> str:
        return self.automode_string

    def send_key(self, plugin: Any, keystr: str, state: str = "press") -> None:
        """Inject a key event into the plugin via do_on_key(emulate=True).
        Logs the input for replay compatibility."""
        get_logger().record_input("agent", keystr, state)
        plugin.do_on_key(keystr, state, emulate=True)

    def send_joystick(self, plugin: Any, x: float, y: float) -> None:
        """Inject joystick analog input into the plugin.
        Values should be in [-1, 1] range, like a real joystick."""
        get_logger().record_input("agent", "joystick", f"{x},{y}")
        if hasattr(plugin, "get_joystick_inputs"):
            plugin.get_joystick_inputs(x, y)

    @staticmethod
    def compute_tracking_compensation(
        cx: float,
        cy: float,
        half_w: float,
        half_h: float,
        gain: float = 4.0,
        settle_force: float = 0.3,
        settle_ms: float = 2000,
        last_outside_time: float | None = None,
        current_time: float = 0.0,
    ) -> tuple[float, float]:
        """Proportional joystick compensation with post-target settling.

        Returns (jx, jy) clamped to [-1, 1], ready for send_joystick().
        """
        raw_jx = -cx / half_w * gain
        raw_jy = cy / half_h * gain
        settling = last_outside_time is not None and (current_time - last_outside_time) * 1000 < settle_ms
        if settling:
            if abs(raw_jx) < settle_force and abs(cx) > 1.0:
                raw_jx = math.copysign(settle_force, raw_jx)
            if abs(raw_jy) < settle_force and abs(cy) > 1.0:
                raw_jy = math.copysign(settle_force, raw_jy)
        return max(-1.0, min(1.0, raw_jx)), max(-1.0, min(1.0, raw_jy))

    @staticmethod
    def compute_comms_action(
        active_radio: dict,
        target_radio: dict,
        keys: dict,
    ) -> str:
        """Determine which key to send for communications tuning.

        Returns the mapped key string from *keys* (ready for send_key()).
        """
        if active_radio != target_radio:
            direction = "selectradioup" if target_radio["pos"] < active_radio["pos"] else "selectradiodown"
            return keys[direction]
        elif round(active_radio["targetfreq"], 1) != round(active_radio["currentfreq"], 1):
            direction = (
                "tunefrequencyup" if active_radio["targetfreq"] > active_radio["currentfreq"] else "tunefrequencydown"
            )
            return keys[direction]
        else:
            return keys["validateresponse"]
