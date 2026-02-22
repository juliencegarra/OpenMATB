# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import sys
from typing import Any, Callable

from core import validation
from core.error import get_errors
from core.logger import get_logger
from plugins.abstractplugin import AbstractPlugin


class Parallelport(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 5) -> None:
        super().__init__(_("Parallel port"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "trigger": validation.is_positive_integer,
            "delayms": validation.is_positive_integer,
        }

        self._port: Any = None
        self._downvalue: int = 0
        self.parameters.update({"trigger": self._downvalue, "delayms": 5})
        self._triggertimerms: int = 0
        self._last_trigger: int = self._downvalue
        self._awaiting_triggers: list[int] = []

        platform = sys.platform

        # 1. Check platform
        if platform == "darwin":
            get_errors().add_error(
                _("Parallel port is not supported on macOS. Skipping parallel plugin."))
            return

        # 2. Try importing pyparallel
        try:
            import parallel
        except ImportError:
            if platform == "win32":
                get_errors().add_error(_(
                    "Python Parallel module is missing. "
                    "On Windows, install pyparallel (pip install pyparallel) "
                    "and the InpOut32 driver (provides simpleio.dll)."))
            else:
                get_errors().add_error(_(
                    "Python Parallel module is missing. "
                    "On Linux, install pyparallel (pip install pyparallel) "
                    "and ensure the ppdev kernel module is loaded."))
            return

        # 3. Try opening the port
        try:
            self._port = parallel.Parallel()
        except FileNotFoundError:
            if platform == "win32":
                get_errors().add_error(_(
                    "Parallel port not found. "
                    "Ensure the InpOut32 driver is installed (provides simpleio.dll) "
                    "and that a physical parallel port is available."))
            else:
                get_errors().add_error(_(
                    "Parallel port not found. "
                    "Ensure /dev/parport0 exists and you have read/write permissions "
                    "(try: sudo chmod 666 /dev/parport0)."))
            return
        except OSError as exc:
            get_errors().add_error(
                _("Parallel port error: {error}").format(error=str(exc)))
            return

    def is_trigger_being_sent(self) -> bool:
        """Return if the last trigger value is not the down value (trigger being sent)"""
        return self._last_trigger != self._downvalue

    def set_trigger_value(self, value: int) -> None:
        self._port.setData(value)
        self._triggertimerms = 0
        get_logger().record_state(f"{self.alias}_trigger", "value", value)
        self._last_trigger = value

    def compute_next_plugin_state(self) -> None:
        """Send the trigger value defined in upvalue, lasting for delayms"""
        if self._port is None:
            return
        if not super().compute_next_plugin_state():
            return

        # If the trigger value is not null...
        if self.parameters["trigger"] != self._downvalue:
            # ... and no trigger being sent: send it
            if not self.is_trigger_being_sent():
                self.set_trigger_value(self.parameters["trigger"])

            # but if a trigger is already being sent, store it
            else:
                self._awaiting_triggers.append(self.parameters["trigger"])

            # Finally, reset the input trigger
            self.parameters["trigger"] = self._downvalue

        # If it is null and some triggers are awaiting and no trigger is being sent
        elif len(self._awaiting_triggers) > 0 and not self.is_trigger_being_sent():
            self.set_trigger_value(self._awaiting_triggers[0])  # Make it current
            del self._awaiting_triggers[0]  # And delete it

        # If a trigger is currently defined...
        if self.is_trigger_being_sent() and self._triggertimerms >= self.parameters["delayms"]:
            # ... and the delayms has been reached: sent default value to parallel port
            self.set_trigger_value(self._downvalue)

        # Grow timer of not-null trigger
        if self.is_trigger_being_sent():
            self._triggertimerms += self.parameters["taskupdatetime"]
