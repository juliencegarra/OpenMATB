# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from datetime import datetime
from os import getpid
from typing import Any, Callable

from core import validation
from core.error import get_errors
from plugins import Instructions

try:
    import pylsl
except (ImportError, RuntimeError):
    pylsl = None


class Labstreaminglayer(Instructions):
    def __init__(self) -> None:
        super().__init__()

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "marker": validation.is_string,
            "streamsession": validation.is_boolean,
            "pauseatstart": validation.is_boolean,
            "state": validation.is_string,
        }

        self.parameters.update({"marker": "", "streamsession": False, "pauseatstart": False})

        self.stream_info: Any | None = None
        self.stream_outlet: Any | None = None
        self.stop_on_end: bool = False
        self._stream_error_reported: bool = False
        self._heartbeat_interval_sec: float = 1.0
        self._next_heartbeat_time: float = 0.0

        self.lsl_wait_msg: str = _("Please enable the OpenMATB stream into your LabRecorder.")

    def start(self) -> None:
        # If we get there it's because the plugin is used.
        # If pylsl is not available this part should fail.
        # Create a LSL marker outlet.
        super().start()
        if pylsl is None:
            get_errors().add_error(
                _("pylsl is unavailable. OpenMATB LSL stream is disabled. Check pylsl/liblsl installation."),
                fatal=False,
            )
            self.stream_info = None
            self.stream_outlet = None
            return

        try:
            source_id: str = f"openmatb-{datetime.now().strftime('%Y%m%d%H%M%S')}-{getpid()}"
            self.stream_info = pylsl.StreamInfo(
                "OpenMATB",
                type="Markers",
                channel_count=1,
                nominal_srate=0,
                channel_format="string",
                source_id=source_id,
            )
            self.stream_outlet = pylsl.StreamOutlet(self.stream_info)
        except Exception as exc:  # noqa: BLE001
            self.stream_info = None
            self.stream_outlet = None
            get_errors().add_error(_(f"Cannot create LSL outlet: {exc}"), fatal=False)
            return

        if self.parameters["streamsession"] is True:
            self.logger.lsl = self

        self._next_heartbeat_time = 0.0
        self.push("OPENMATB_LSL_STREAM_STARTED")

        # The pauseatstart parameter is now ignored to prevent blocking LSL data flow.
        # if self.parameters["pauseatstart"] is True:
        #     self.slides = [self.get_msg_slide_content(self.lsl_wait_msg)]

    def update(self, dt: float) -> None:
        super().update(dt)

        if self.parameters["streamsession"] is True and self.logger.lsl is None:
            if self.stream_outlet is not None:
                self.logger.lsl = self
            elif not self._stream_error_reported:
                get_errors().add_error(
                    _("OpenMATB LSL stream session requested, but no outlet is available."),
                    fatal=False,
                )
                self._stream_error_reported = True
        elif self.parameters["streamsession"] is False and self.logger.lsl is not None:
            self.logger.lsl = None

        if self.parameters["marker"] != "":
            # A marker has been set. Push it to the outlet.
            self.push(self.parameters["marker"])

            # and reset the marker to empty.
            self.parameters["marker"] = ""

        if self.stream_outlet is not None and self.scenario_time >= self._next_heartbeat_time:
            self.push(f"OPENMATB_LSL_HEARTBEAT|t={self.scenario_time:.3f}")
            self._next_heartbeat_time = self.scenario_time + self._heartbeat_interval_sec

    def push(self, message: str) -> None:
        if self.stream_outlet is None:
            return
        self.stream_outlet.push_sample([message])

    #        print(message)

    def stop(self) -> None:
        self.push("OPENMATB_LSL_STREAM_STOPPED")
        if self.logger.lsl is self:
            self.logger.lsl = None
        super().stop()
        self.stream_info = None
        self.stream_outlet = None
        self._next_heartbeat_time = 0.0

    def get_msg_slide_content(self, str_msg: str) -> str:
        return f"<title>Lab streaming layer\n{self.lsl_wait_msg}"
