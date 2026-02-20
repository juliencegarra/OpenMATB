# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import csv
from bisect import bisect_right
from pathlib import Path

from core.constants import PATHS as P
from core.error import errors
from core.event import Event

# Some plugins must not be replayed for now
IGNORE_PLUGINS = ["labstreaminglayer", "parallelport"]

# Minimum logtime span (seconds) for a frozen scenario_time group to be
# considered a blocking segment (filters out simultaneous events).
BLOCKING_THRESHOLD = 0.5


class LogReader:
    """
    The log reader takes a session file as input and is able to return its entries depending on
    their onset time. Relevant entries are scenario events and user inputs, which are combined to
    simulate what happened during the session.
    """

    def __init__(self, replay_session_id=None, session_path=None):
        self.session_file_path = None
        self.replay_session_id = replay_session_id

        if session_path is not None:
            # Direct path provided (from file selector)
            self.session_file_path = Path(session_path)
            try:
                self.replay_session_id = int(self.session_file_path.stem.split("_")[0])
            except (ValueError, IndexError):
                pass
        else:
            # Look up by session ID
            session_file_list = [f for f in P["SESSIONS"].glob(f"**/{replay_session_id}_*.csv")]

            if len(session_file_list) == 0:
                errors.add_error(_("The desired session file (ID=%s) does not exist") % replay_session_id, fatal=True)
            elif len(session_file_list) > 1:
                errors.add_error(
                    _("Multiple session files match the desired session ID (%s)") % replay_session_id, fatal=True
                )
            elif len(session_file_list) == 1:
                self.session_file_path = session_file_list[0]

        self.reload_session()

    def reload_session(self):
        if self.session_file_path is None:
            return

        self.contents, self.inputs, self.states = [], [], []
        self.start_sec, self.end_sec, self.duration_sec = 0, 0, 0
        self.session_duration = 0
        self.line_n = 0
        self.keyboard_inputs = []
        self.joystick_inputs = []
        self.blocking_segments = []
        self._bp_replay_times = [0.0]
        self._bp_scenario_times = [0.0]

        # First pass: read all rows
        all_rows = []
        with open(self.session_file_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row["logtime"] = float(row["logtime"])
                row["scenario_time"] = float(row["scenario_time"])
                all_rows.append(row)

        if not all_rows:
            return

        # Capture first logtime for normalization
        first_logtime = all_rows[0]["logtime"]
        for row in all_rows:
            row["normalized_logtime"] = row["logtime"] - first_logtime

        # Detect blocking segments and build replay-to-scenario mapping
        self._detect_blocking_segments(all_rows)
        self._build_replay_mapping()

        # Session duration based on logtime (includes blocking periods)
        self.session_duration = all_rows[-1]["normalized_logtime"]

        # Second pass: process rows (skip first row as before)
        for row in all_rows[1:]:
            if row["module"] in IGNORE_PLUGINS:
                continue

            # Event case
            if row["type"] == "event":
                self.contents.append(self.session_event_to_str(row))

            # Input case
            elif row["type"] == "input":
                self.inputs.append(row)
                if row["module"] == "keyboard":
                    self.keyboard_inputs.append(row)
                elif "joystick" in row["address"]:
                    self.joystick_inputs.append(row)

            # State case
            elif row["type"] == "state":
                # Record communications radio frequencies
                # AND track cursor positions
                if (
                    "radio_frequency" in row["address"]
                    or "cursor_proportional" in row["address"]
                    or "slider_" in row["address"]
                ):
                    row["value"] = eval(row["value"])
                    self.states.append(row)

        # The last row browsed contains the ending time
        self.end_sec = all_rows[-1]["scenario_time"]
        self.duration_sec = self.end_sec - self.start_sec

    def _detect_blocking_segments(self, all_rows):
        """Identify periods where scenario_time is frozen while logtime advances."""
        self.blocking_segments = []

        if len(all_rows) < 2:
            return

        # Group consecutive rows with the same scenario_time
        current_st = all_rows[0]["scenario_time"]
        current_start_lt = all_rows[0]["normalized_logtime"]
        current_end_lt = all_rows[0]["normalized_logtime"]

        for row in all_rows[1:]:
            if abs(row["scenario_time"] - current_st) < 0.01:
                current_end_lt = row["normalized_logtime"]
            else:
                if current_end_lt - current_start_lt > BLOCKING_THRESHOLD:
                    self.blocking_segments.append((current_start_lt, current_end_lt, current_st))
                current_st = row["scenario_time"]
                current_start_lt = row["normalized_logtime"]
                current_end_lt = row["normalized_logtime"]

        # Handle the last group
        if current_end_lt - current_start_lt > BLOCKING_THRESHOLD:
            self.blocking_segments.append((current_start_lt, current_end_lt, current_st))

    def _build_replay_mapping(self):
        """Build breakpoints for replay_time -> scenario_time mapping.

        Between consecutive breakpoints the slope is either 1 (normal) or
        0 (blocking segment).
        """
        self._bp_replay_times = [0.0]
        self._bp_scenario_times = [0.0]

        for lt_start, lt_end, frozen_st in self.blocking_segments:
            self._bp_replay_times.append(lt_start)
            self._bp_scenario_times.append(frozen_st)
            self._bp_replay_times.append(lt_end)
            self._bp_scenario_times.append(frozen_st)

    def replay_to_scenario_time(self, replay_time):
        """Convert replay_time (normalized logtime) to scenario_time.

        Uses O(log k) bisect lookup where k = number of blocking segments.
        """
        idx = bisect_right(self._bp_replay_times, replay_time) - 1
        if idx < 0:
            return 0.0

        rt_base = self._bp_replay_times[idx]
        st_base = self._bp_scenario_times[idx]

        # Check if we are inside a blocking segment (next breakpoint has
        # the same scenario_time, meaning slope = 0).
        if idx + 1 < len(self._bp_replay_times):
            st_next = self._bp_scenario_times[idx + 1]
            if abs(st_base - st_next) < 0.001:
                return st_base

        # Normal segment: slope = 1
        return st_base + (replay_time - rt_base)

    def session_event_to_str(self, event_row):
        time_sec = int(float(event_row["scenario_time"]))
        plugin = event_row["module"]
        if event_row["address"] == "self":
            command = event_row["value"]
        else:
            command = ";".join([event_row["address"], event_row["value"]])

        event = Event(self.line_n, time_sec, plugin, command)
        self.line_n += 1
        return event.get_line_str()
