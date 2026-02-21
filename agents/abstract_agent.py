# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core import get_logger


class AbstractAgent(ABC):
    """Base class for agents that can control plugins when automaticsolver is True."""

    def __init__(self, name: str = "agent", automode_string: str = "AUTO") -> None:
        self.name = name
        self.automode_string = automode_string

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
        get_logger().record_input("keyboard", keystr, state)
        plugin.do_on_key(keystr, state, emulate=True)

    def send_joystick(self, plugin: Any, x: float, y: float) -> None:
        """Inject joystick analog input into the plugin.
        Values should be in [-1, 1] range, like a real joystick."""
        if hasattr(plugin, "get_joystick_inputs"):
            plugin.get_joystick_inputs(x, y)
