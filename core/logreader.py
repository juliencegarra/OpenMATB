# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import ast
import csv
import io
from bisect import bisect_right
from pathlib import Path
from typing import Any

from core.constants import PATHS as P
from core.error import get_errors
from core.event import Event

# Some plugins must not be replayed for now. The lab streaming layer is replayed without its stream: its pause at
# start is a blocking page (dropped, the following events ran at once, and the SPACE that closed it closed the next
# page, e.g. a 120 s resting baseline)
IGNORE_PLUGINS: list[str] = ["parallelport"]

# Minimum logtime span (seconds) for a frozen scenario_time group to be
# considered a blocking segment (filters out simultaneous events).
BLOCKING_THRESHOLD: float = 0.5


class LogReader:
    """
    The log reader takes a session file as input and is able to return its entries depending on
    their onset time. Relevant entries are scenario events and user inputs, which are combined to
    simulate what happened during the session.
    """

    def __init__(self, replay_session_id: int | None = None, session_path: str | None = None) -> None:
        self.session_file_path: Path | None = None
        self.replay_session_id: int | None = replay_session_id

        if session_path is not None:
            # Direct path provided (from file selector)
            self.session_file_path = Path(session_path)
            try:
                self.replay_session_id = int(self.session_file_path.stem.split("_")[0])
            except (ValueError, IndexError):
                pass
        else:
            # Look up by session ID
            session_file_list: list[Path] = [f for f in P["SESSIONS"].glob(f"**/{replay_session_id}_*.csv")]

            if len(session_file_list) == 0:
                msg = _("The desired session file (ID=%s) does not exist") % replay_session_id
                get_errors().add_error(msg, fatal=True)
            elif len(session_file_list) > 1:
                get_errors().add_error(
                    _("Multiple session files match the desired session ID (%s)") % replay_session_id, fatal=True
                )
            elif len(session_file_list) == 1:
                self.session_file_path = session_file_list[0]

        self.contents: list[str] = []
        # The normalized logtime of each event of contents: the replay sends the keys logged before an event before it
        self.event_logtimes: list[float] = []
        # The ends of the communications prompts, as (scenario time, radio name): the replay ends them at these times
        self.prompt_ends: list[tuple[float, str]] = []
        # Whether the lab streaming layer showed its pause at start (not without a stream, e.g. pylsl missing)
        self.lsl_pause_shown: bool = False
        self.inputs: list[dict[str, Any]] = []
        self.states: list[dict[str, Any]] = []
        self.start_sec: float = 0
        self.end_sec: float = 0
        self.duration_sec: float = 0
        self.session_duration: float = 0
        self.line_n: int = 0
        self.keyboard_inputs: list[dict[str, Any]] = []
        self.joystick_inputs: list[dict[str, Any]] = []
        self.mouse_inputs: list[dict[str, Any]] = []
        self.blocking_segments: list[tuple[float, float, float]] = []
        self._bp_replay_times: list[float] = [0.0]
        self._bp_scenario_times: list[float] = [0.0]
        self.perf_rows: list[dict[str, Any]] = []
        self.perf_series: dict[str, list[tuple[float, dict[str, str]]]] = {}
        self.task_hidden_periods: dict[str, list[tuple[float, float]]] = {}
        # Browser sessions only (see _read_page_events)
        self.environment: dict[str, str] = {}
        self.window_size: tuple[float, float] | None = None
        self.hidden_periods: list[tuple[float, float, float]] = []
        self.freezes: list[tuple[float, float]] = []

        self.reload_session()

    def reload_session(self) -> None:
        if self.session_file_path is None:
            return

        self.contents, self.inputs, self.states = [], [], []
        self.start_sec, self.end_sec, self.duration_sec = 0, 0, 0
        self.session_duration = 0
        self.line_n = 0
        self.event_logtimes = []
        self.keyboard_inputs = []
        self.joystick_inputs = []
        self.mouse_inputs = []
        self.blocking_segments = []
        self._bp_replay_times = [0.0]
        self._bp_scenario_times = [0.0]
        self.perf_rows = []
        self.perf_series = {}
        self.task_hidden_periods = {}
        self.lsl_pause_shown = False
        self.environment = {}
        self.hidden_periods = []
        self.freezes = []

        # First pass: read all rows
        all_rows: list[dict[str, Any]] = []
        # utf-8-sig: a session file saved again as "CSV UTF-8" (e.g. by Excel) starts with a BOM
        with open(self.session_file_path, "rb") as csvfile:
            data: bytes = csvfile.read()
        try:
            text: str = data.decode("utf-8-sig")
        except UnicodeDecodeError:  # Sessions before 1.5 were written in the Windows encoding (e.g. "Temps passé")
            text = data.decode("cp1252", errors="replace")
        rows: list[dict[str, Any]] = list(csv.DictReader(io.StringIO(text, newline="")))
        # A session killed while writing (power loss, crash) ends with a row cut anywhere, without its end of line
        cut_last_row: bool = not text.endswith(("\n", "\r"))
        for n, row in enumerate(rows):
            cut: bool = cut_last_row and n == len(rows) - 1
            # A cut row keeps its time (the session lasted until then), but its incomplete content is not read
            # (an invalid scenario event, a mouse click or joystick value raising during the replay...)
            if cut or any(row.get(k) is None for k in ("type", "module", "address", "value")):
                row.update(type="", module=row.get("module") or "", address="", value="")
            # Skip a row without valid times (e.g. the last row of a session that crashed while writing it)
            try:
                row["logtime"] = float(row["logtime"])
                row["scenario_time"] = float(row["scenario_time"])
            except (TypeError, ValueError):
                continue
            # A time cut in its digits is smaller than the real one (120.003 cut to 12): the times never go back
            if cut and all_rows:
                row["logtime"] = max(row["logtime"], all_rows[-1]["logtime"])
                row["scenario_time"] = max(row["scenario_time"], all_rows[-1]["scenario_time"])
            all_rows.append(row)

        if not all_rows:
            return

        # The session ID logged at start (newer sessions), else the one of the file name: the seeds of the replay
        for row in all_rows:
            if row["type"] == "session_id":
                try:
                    self.replay_session_id = int(row["value"])
                except ValueError:
                    pass
                break

        # Capture first logtime for normalization
        first_logtime: float = all_rows[0]["logtime"]
        for row in all_rows:
            row["normalized_logtime"] = row["logtime"] - first_logtime

        # Detect blocking segments and build replay-to-scenario mapping
        self._detect_blocking_segments(all_rows)
        self._build_replay_mapping(all_rows)

        # Session duration based on logtime (includes blocking periods)
        self.session_duration = all_rows[-1]["normalized_logtime"]
        self._read_page_events(all_rows)
        self._read_task_visibility(all_rows)
        # Its page logged the areas of its widgets (title, text, response), not only its background
        self.lsl_pause_shown = any(
            row["type"] == "aoi" and row["module"] == "labstreaminglayer" and row["address"] != "background"
            for row in all_rows
        )
        self.window_size = self._read_window_size(all_rows)
        # The scenario time of the end of the session (its "end" row), None for a session that crashed
        end_time: float | None = next(
            (row["scenario_time"] for row in reversed(all_rows) if row["type"] == "manual" and row["value"] == "end"),
            None,
        )

        # Second pass: process rows (skip first row as before)
        for row in all_rows[1:]:
            if row["module"] in IGNORE_PLUGINS:
                continue

            # Event case
            if row["type"] == "event":
                # Not the stops of the end of the session: logged in its last update (e.g. a session quit, the stops
                # of the running tasks), the window closed then and never showed them. Replayed at their whole second
                # (the scenario times are whole seconds), they hid the tasks up to 1 s too early
                if row["address"] == "self" and row["value"] == "stop" and row["scenario_time"] == end_time:
                    continue
                self.contents.append(self.session_event_to_str(row))
                self.event_logtimes.append(row["normalized_logtime"])

            # The end of a communications prompt ("Target COM_2:127.9", since 2023)
            elif row["type"] == "manual" and str(row["value"]).startswith("Target "):
                radio_name: str = str(row["value"])[len("Target ") :].split(":")[0]
                self.prompt_ends.append((row["scenario_time"], radio_name))

            # Input case
            elif row["type"] == "input":
                self.inputs.append(row)
                # The joystick axes: of the joystick (x, y), or of an agent (address "joystick", value "x,y")
                if row["module"] == "joystick" or "joystick" in row["address"]:
                    self.joystick_inputs.append(row)
                # The keys: keyboard, agent, mouse clicks on a task, joystick buttons (module "Joystick"), and the
                # pages ended by maxdurationsec (module "timeout", address: the plugin), in their order
                elif row["module"] in ("keyboard", "agent", "mouse_key", "Joystick", "timeout"):
                    self.keyboard_inputs.append(row)
                elif row["module"] == "mouse":
                    self.mouse_inputs.append(row)

            # State case
            elif row["type"] == "state":
                # Record communications radio frequencies, track cursor positions, questionnaire sliders
                # AND resman tank levels
                if (
                    "radio_frequency" in row["address"]
                    or "cursor_proportional" in row["address"]
                    or "slider_" in row["address"]
                    or "fluid_level" in row["address"]
                ):
                    try:
                        row["value"] = ast.literal_eval(row["value"])
                    except (ValueError, SyntaxError):  # A last row cut in its value (crash while writing it)
                        continue
                    self.states.append(row)

            # Performance case
            elif row["type"] == "performance":
                self.perf_rows.append(row)

        # The last row browsed contains the ending time
        self.end_sec = all_rows[-1]["scenario_time"]
        self.duration_sec = self.end_sec - self.start_sec
        self._index_performance_data()

    def _index_performance_data(self) -> None:
        """Group performance rows by module and scenario_time into series sorted by replay time (normalized logtime,
        of the first row of each group): the instructions and the questionnaires, which pause the scenario time,
        keep their width on the performance strip, as on the timeline."""
        # Group by (module, scenario_time) → {address: value}. An address already in the group starts another one
        # at the same time: two outcomes of the same step (e.g. two sysmon failures timing out together) made
        # a single marker
        self.perf_series = {}
        group_times: dict[str, float] = {}  # The scenario time of the last group of each module
        for row in self.perf_rows:
            module: str = row["module"]
            series: list[tuple[float, dict[str, str]]] = self.perf_series.setdefault(module, [])
            if series and group_times[module] == row["scenario_time"] and row["address"] not in series[-1][1]:
                series[-1][1][row["address"]] = row["value"]
            else:
                series.append((row["normalized_logtime"], {row["address"]: row["value"]}))
                group_times[module] = row["scenario_time"]

        # Sorted by time (the order of the rows is kept at the same time)
        for series in self.perf_series.values():
            series.sort(key=lambda x: x[0])

    def _detect_blocking_segments(self, all_rows: list[dict[str, Any]]) -> None:
        """Identify periods where scenario_time is frozen while logtime advances."""
        self.blocking_segments = []

        if len(all_rows) < 2:
            return

        # Group consecutive rows with the same scenario_time
        current_st: float = all_rows[0]["scenario_time"]
        current_start_lt: float = all_rows[0]["normalized_logtime"]
        current_end_lt: float = all_rows[0]["normalized_logtime"]

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

    def _build_replay_mapping(self, all_rows: list[dict[str, Any]] | None = None) -> None:
        """Build breakpoints (replay_time, scenario_time) for the replay_time -> scenario_time mapping.

        The breakpoints are the start and end of the blocking segments, and the first row logged at each scenario
        time: the scenario time does not start with the log (the first rows are written before the scenario
        starts, while the tasks are created), and it stops for pauses shorter than BLOCKING_THRESHOLD. Without
        these anchors, the replayed inputs (placed by logtime) were shifted from the events (placed by
        scenario_time), e.g. by the ~0.2 s of the start.
        """
        points: list[tuple[float, float]] = [(0.0, 0.0)]
        for lt_start, lt_end, frozen_st in self.blocking_segments:
            points += [(lt_start, frozen_st), (lt_end, frozen_st)]
        last_st: float | None = None
        for row in all_rows or []:
            if row["scenario_time"] != last_st:
                points.append((row["normalized_logtime"], row["scenario_time"]))
                last_st = row["scenario_time"]
        points.sort()
        self._bp_replay_times = [lt for lt, _st in points]
        self._bp_scenario_times = [st for _lt, st in points]

    def replay_to_scenario_time(self, replay_time: float) -> float:
        """Convert replay_time (normalized logtime) to scenario_time.

        From a breakpoint the scenario time advances with the replay time (slope 1), up to the scenario time of
        the next breakpoint (slope 0 in a blocking segment, whose two ends have the same scenario time).
        Uses an O(log k) bisect lookup, k being the number of breakpoints.
        """
        idx: int = bisect_right(self._bp_replay_times, replay_time) - 1
        if idx < 0:
            return 0.0

        scenario_time: float = self._bp_scenario_times[idx] + (replay_time - self._bp_replay_times[idx])
        if idx + 1 < len(self._bp_replay_times):
            scenario_time = min(scenario_time, self._bp_scenario_times[idx + 1])
        return scenario_time

    @staticmethod
    def _read_window_size(all_rows: list[dict[str, Any]]) -> tuple[float, float] | None:
        """Size (width, height) of the window of the session, where its mouse inputs were: logged ("window": "WxH"),
        or, in older sessions, the extent of the areas of interest of the tasks (each one is (x1, y1, x2, y2))."""
        width: float = 0
        height: float = 0
        for row in all_rows:
            if row["type"] == "window":
                try:
                    w, h = (float(v) for v in str(row["value"]).split("x"))
                    return w, h
                except ValueError:
                    continue
            if row["type"] == "aoi":
                try:
                    x1, y1, x2, y2 = ast.literal_eval(row["value"])
                except (ValueError, SyntaxError, TypeError):
                    continue
                width, height = max(width, x1, x2), max(height, y1, y2)
        return (width, height) if width > 0 and height > 0 else None

    def _read_page_events(self, all_rows: list[dict[str, Any]]) -> None:
        """Browser sessions: the browser and its system, the periods when the page was hidden (the scenario is
        paused), and the pauses of the page (freeze, e.g. garbage collection), in replay time (seconds).

        hidden_periods: (hidden, visible, resumed): the page was hidden from `hidden` to `visible`, and the
        scenario resumed at `resumed` (after the pause dialog). freezes: (start, duration in seconds)."""
        hidden_since: float | None = None
        for row in all_rows:
            kind: str = row["type"]
            if kind in ("browser", "os"):
                self.environment[kind] = row["value"]
            elif kind == "freeze":
                duration: float = float(row["value"]) / 1000  # Logged when the page runs again
                self.freezes.append((max(row["normalized_logtime"] - duration, 0), duration))
            elif kind == "visibility" and row["value"] == "hidden" and hidden_since is None:
                hidden_since = row["normalized_logtime"]
            elif kind == "visibility" and row["value"] == "visible" and hidden_since is not None:
                self.hidden_periods.append(self._hidden_period(hidden_since, row["normalized_logtime"]))
                hidden_since = None
        if hidden_since is not None:  # Still hidden at the end of the session
            self.hidden_periods.append(self._hidden_period(hidden_since, self.session_duration))

    def _read_task_visibility(self, all_rows: list[dict[str, Any]]) -> None:
        """The periods when each task was not visible, in replay time: before its start, hidden, during the
        instructions and the questionnaires, after its stop. Its foreground covers it then (a logged state)."""
        hidden_since: dict[str, float | None] = {}
        for row in all_rows:
            if row["type"] != "state" or row["address"] != "foreground, visibility":
                continue
            since: float | None = hidden_since.setdefault(row["module"], 0.0)  # Not visible before its start
            # True/False, or 1/0 before 1.5
            if row["value"] in ("False", "0", "0.0") and since is not None:
                self.task_hidden_periods.setdefault(row["module"], []).append((since, row["normalized_logtime"]))
                hidden_since[row["module"]] = None
            elif row["value"] in ("True", "1", "1.0") and since is None:
                hidden_since[row["module"]] = row["normalized_logtime"]
        for module, since in hidden_since.items():
            if since is not None:  # Still hidden at the end of the session
                self.task_hidden_periods.setdefault(module, []).append((since, self.session_duration))

    def _hidden_period(self, hidden: float, visible: float) -> tuple[float, float, float]:
        # The scenario time is frozen from when the page is hidden until the pause dialog is closed
        resumed: float = visible
        for lt_start, lt_end, _frozen_st in self.blocking_segments:
            if lt_start - 0.5 <= hidden <= lt_end:
                resumed = max(resumed, lt_end)
        return hidden, visible, resumed

    def is_in_blocking_segment(self, replay_time: float) -> bool:
        """Check if replay_time falls inside a blocking segment."""
        for lt_start, lt_end, _frozen_st in self.blocking_segments:
            if lt_start <= replay_time <= lt_end:
                return True
        return False

    @staticmethod
    def _scenario_value(value: str) -> str:
        """A list value logged as a Python list by previous versions (e.g. "['sysmon', 'track']") is written back
        as in a scenario (sysmon,track): otherwise its validation fails in the replay"""
        if not (value.startswith("[") and value.endswith("]")):
            return value
        try:
            values: Any = ast.literal_eval(value)
        except (ValueError, SyntaxError):  # E.g. a regex such as [A-Z][0-9]
            return value
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            return value
        return ",".join(values)

    def session_event_to_str(self, event_row: dict[str, Any]) -> str:
        time_sec: int = int(float(event_row["scenario_time"]))
        plugin: str = event_row["module"]
        if event_row["address"] == "self":
            command: str = event_row["value"]
        else:
            command = ";".join([event_row["address"], self._scenario_value(event_row["value"])])

        event: Event = Event(self.line_n, time_sec, plugin, command)
        self.line_n += 1
        return event.get_line_str()
