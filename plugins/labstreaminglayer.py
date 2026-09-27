# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from core import validation
from core.error import get_errors
from core.platform import IS_WEB, web_lsl_outlet
from plugins import Instructions

try:
    import pylsl
except (ImportError, RuntimeError):
    pylsl = None


class Labstreaminglayer(Instructions):
    def __init__(self) -> None:
        super().__init__()

        self.validation_dict.update(
            {
                "marker": validation.is_string,
                "streamsession": validation.is_boolean,
                "pauseatstart": validation.is_boolean,
                "state": validation.is_string,
            }
        )

        self.parameters.update({"marker": "", "streamsession": False, "pauseatstart": False})

        self.stream_info: Any | None = None
        self.stream_outlet: Any | None = None
        self.stop_on_end: bool = False
        self.needs_input_file = False  # No filename command needed before start
        self._logged_offset: float | None = None  # Browser: clock offset of the LSL bridge last logged

        self.lsl_wait_msg: str = _("Please enable the OpenMATB stream into your LabRecorder.")

    def start(self) -> None:
        # If we get there it's because the plugin is used.
        # If pylsl is not available this part should fail.
        # Create a LSL marker outlet.
        super().start()
        if IS_WEB:
            # The markers go to web/lsl_bridge.py (web_lsl_bridge in config.ini), which creates the same stream
            self.stream_outlet = web_lsl_outlet()
            if self.stream_outlet is None:
                get_errors().add_error(
                    _(
                        "Lab streaming layer is not available in the browser without the LSL bridge "
                        "(web_lsl_bridge in config.ini). No marker will be sent"
                    )
                )
                return
        elif pylsl is None:
            get_errors().add_error(_("Python pylsl module is missing. No marker will be sent"))
            return
        else:
            self.stream_info = pylsl.StreamInfo(
                "OpenMATB",
                type="Markers",
                channel_count=1,
                nominal_srate=0,
                channel_format="string",
                source_id="myuidw435368",
            )
            self.stream_outlet = pylsl.StreamOutlet(self.stream_info)

        if self.parameters["pauseatstart"] is True:
            self.slides = [self.get_msg_slide_content(self.lsl_wait_msg)]

    def update(self, dt: float) -> None:
        super().update(dt)
        self.log_clock_offset()

        if self.parameters["streamsession"] is True and self.logger.lsl is None:
            self.logger.lsl = self
        elif self.parameters["streamsession"] is False and self.logger.lsl is not None:
            self.logger.lsl = None

        if self.parameters["marker"] != "":
            # A marker has been set. Push it to the outlet.
            self.push(self.parameters["marker"])

            # and reset the marker to empty.
            self.parameters["marker"] = ""

    def log_clock_offset(self) -> None:
        """Browser: log the offset between the browser clock (logtime) and the LSL clock when the bridge measures
        a better one, so that every row of the session file can be put in LSL time: logtime - lsl_offset."""
        if not IS_WEB or self.stream_outlet is None:
            return
        offset: float | None = self.stream_outlet.clock_offset()
        if offset is not None and (self._logged_offset is None or abs(offset - self._logged_offset) >= 1e-4):
            self.logger.log_manual_entry(f"{offset:.6f}", key="lsl_offset")
            self._logged_offset = offset

    def push(self, message: str) -> None:
        if self.stream_outlet is None:
            return
        self.stream_outlet.push_sample([message])

    #        print(message)

    def stop(self) -> None:
        super().stop()
        self.stream_info = None
        self.stream_outlet = None

    def get_msg_slide_content(self, str_msg: str) -> str:
        return f"<title>Lab streaming layer\n{self.lsl_wait_msg}"
