#!/usr/bin/env python3

import configparser
import gettext
import re
from datetime import datetime
from pathlib import Path
from random import randint, shuffle
from time import time
from types import SimpleNamespace

from core.constants import PATHS
from core.event import Event

# ----------------------------------------------------------------------
# Load config for language & install _() for translations
# ----------------------------------------------------------------------
config = configparser.ConfigParser()
# Assuming config.ini is in the parent directory of where the script is run
try:
    config.read(Path(__file__).parent.parent / "config.ini")
    LOCALE_PATH = Path(__file__).parent.parent / "locales"
    language_iso = config["Openmatb"]["language"]
except KeyError:
    # Fallback for different structures
    config.read(Path(__file__).parent.parent.parent / "matb_task" / "config.ini")
    LOCALE_PATH = Path(__file__).parent.parent.parent / "matb_task" / "locales"
    language_iso = config["Openmatb"]["language"]


language = gettext.translation("openmatb", LOCALE_PATH, [language_iso])
language.install()


class BaseGenerator:
    """
    A base class for generating MATB scenarios.
    It includes helper functions and basic structure for creating scenario files.
    """

    EVENTS_REFRACTORY_DURATION = 1
    AVERAGE_AUDITORY_PROMPT_DURATION = 10

    @staticmethod
    def _build_fallback_plugins():
        return {
            "track": SimpleNamespace(parameters={"targetproportion": 0.25}),
            "sysmon": SimpleNamespace(
                parameters={
                    "alerttimeout": 10000,
                    "lights": {
                        "1": {"name": "F5"},
                        "2": {"name": "F6"},
                    },
                    "scales": {
                        "1": {"name": "F1"},
                        "2": {"name": "F2"},
                        "3": {"name": "F3"},
                        "4": {"name": "F4"},
                    },
                }
            ),
            "communications": SimpleNamespace(parameters={"maxresponsedelay": 20000}),
            "resman": SimpleNamespace(
                parameters={
                    "tank": {
                        "a": {"target": 2500},
                        "b": {"target": 2500},
                        "c": {"target": None},
                        "d": {"target": None},
                        "e": {"target": None},
                        "f": {"target": None},
                    },
                    "pump": {
                        "1": {"flow": 800},
                        "2": {"flow": 600},
                        "3": {"flow": 800},
                        "4": {"flow": 600},
                        "5": {"flow": 600},
                        "6": {"flow": 600},
                        "7": {"flow": 400},
                        "8": {"flow": 400},
                    },
                }
            ),
        }

    def __init__(self, silent_track=True):
        try:
            from core.window import Window
            from plugins import Communications, Resman, Sysmon, Track

            win = Window()
            win.set_visible(False)

            self.plugins = {
                "track": Track(win, silent=silent_track),
                "sysmon": Sysmon(win),
                "communications": Communications(win),
                "resman": Resman(win),
            }
        except ModuleNotFoundError:
            self.plugins = self._build_fallback_plugins()

    def format_time(self, sec):
        """Format 'sec' into 'H:MM:SS' (hours always 0)."""
        m = int(sec) // 60
        s = int(sec) % 60
        return f"0:{m:02d}:{s:02d}"

    def parse_time_from_line(self, line_str):
        """
        If line_str starts with HH:MM:SS;, returns total seconds. Otherwise None.
        """
        match = re.match(r"^(\d+):(\d+):(\d+);", line_str.strip())
        if not match:
            return None
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s)

    def get_events_from_scenario(self, scenario_lines):
        """Return only Event objects from the scenario list."""
        return [l for l in scenario_lines if isinstance(l, Event)]

    def get_last_line_num(self, scenario_lines):
        """Find the highest line number used so far (for new Event IDs)."""
        events = self.get_events_from_scenario(scenario_lines)
        return events[-1].line if events else 0

    def reorder_scenario_by_time(self, scenario_lines):
        """
        Sort scenario lines (Event objects + string lines) by time.
        Reassign line numbers for Event objects in ascending order.
        """
        sorted_list = []
        event_counter = 1

        for idx, line in enumerate(scenario_lines):
            if isinstance(line, Event):
                t = line.time_sec
                sorted_list.append((t, idx, line))
            else:
                maybe_time = self.parse_time_from_line(line)
                if maybe_time is None:
                    # Lines without a timestamp (like comments) can go first
                    sorted_list.append((-1, idx, line))
                else:
                    sorted_list.append((maybe_time, idx, line))

        sorted_list.sort(key=lambda x: (x[0], x[1]))

        # Create a new list for the reordered lines
        reordered_lines = []
        for _, _, obj in sorted_list:
            if isinstance(obj, Event):
                obj.line = event_counter
                event_counter += 1
            reordered_lines.append(obj)

        return reordered_lines

    def random_partition(self, duration_sec, parts):
        """Split duration_sec into 'parts' random intervals."""
        duration_sec = int(duration_sec)  # Ensure integer for randint
        if parts <= 1:
            return [duration_sec]
        out = []
        for _ in range(parts - 1):
            val = randint(0, max(0, duration_sec))
            out.append(val)
            duration_sec -= val
            if duration_sec < 0:
                duration_sec = 0
        out.append(duration_sec)
        shuffle(out)
        return out

    def distribute_randomly(
        self,
        scenario_lines,
        start_sec,
        single_duration,
        cmd_list,
        plugin_name,
        time_for_events,
    ):
        total_event_duration = len(cmd_list) * single_duration
        rest_sec = time_for_events - total_event_duration
        if rest_sec < 0:
            rest_sec = 0

        n = len(cmd_list) + 1
        intervals = self.random_partition(rest_sec, n) if n > 1 else [rest_sec]
        if len(intervals) > 1:
            intervals = intervals[:-1]
        else:
            intervals = [0]

        last_line_num = self.get_last_line_num(scenario_lines)
        onset = start_sec

        for delay, cmd in zip(intervals, cmd_list):
            onset += delay
            last_line_num += 1
            scenario_lines.append(Event(last_line_num, onset, plugin_name, cmd))
            onset += single_duration

        return scenario_lines

    def choices(self, items, k, shuffle_it=True):
        """Randomly pick k items (with repetition if needed), and optionally shuffle the result."""
        c = list(items)
        shuffle(c)
        result = []
        while len(result) < k:
            if not c:
                c = list(items)
                shuffle(c)
            result.append(c.pop())
        if shuffle_it:
            shuffle(result)
        return result

    def write_scenario_file(self, scenario_path, scenario_lines, header_lines):
        """Writes the scenario lines to a file with a header."""
        scenario_path.parent.mkdir(parents=True, exist_ok=True)

        with open(str(scenario_path), "w") as f:
            for line in header_lines:
                f.write(line + "\n")
            f.write("\n")

            for line in scenario_lines:
                if isinstance(line, Event):
                    # Re-create the line string from the event object to ensure correctness
                    line_time_int = int(round(line.time_sec))
                    hh = line_time_int // 3600
                    rem = line_time_int % 3600
                    mm = rem // 60
                    ss = rem % 60

                    if isinstance(line.command, list):
                        cmd_str = ";".join(str(x) for x in line.command)
                    else:
                        cmd_str = str(line.command)
                    line_str = f"{hh}:{mm:02d}:{ss:02d};{line.plugin};{cmd_str}"
                    f.write(line_str + "\n")
                else:
                    f.write(str(line) + "\n")
        print(f"Scenario file created: {scenario_path}")

    def schedule_sysmon_failures(
        self, scenario_lines, start_sec, block_sec, difficulty
    ):
        plugin_name = "sysmon"
        plugin = self.plugins[plugin_name]

        fail_duration = (
            plugin.parameters["alerttimeout"] / 1000 + self.EVENTS_REFRACTORY_DURATION
        )
        if block_sec <= 0 or fail_duration <= 0:
            return scenario_lines

        ratio = fail_duration / block_sec
        max_events = int(1 / ratio) if ratio > 0 else 0
        difficulty_events = int(difficulty / ratio) if ratio > 0 else 0
        events_N = min(max_events, difficulty_events)

        # Build commands for lights
        light_keys = list(plugin.parameters["lights"].keys())
        chosen_lights = self.choices(light_keys, events_N)
        cmd_lights = [[f"lights-{lk}-failure", True] for lk in chosen_lights]

        # Build commands for scales
        scale_keys = list(plugin.parameters["scales"].keys())
        chosen_scales = self.choices(scale_keys, events_N)
        cmd_scales = [[f"scales-{sk}-failure", True] for sk in chosen_scales]

        # Distribute them
        scenario_lines = self.distribute_randomly(
            scenario_lines,
            start_sec,
            fail_duration,
            cmd_lights,
            plugin_name,
            time_for_events=block_sec,
        )
        scenario_lines = self.distribute_randomly(
            scenario_lines,
            start_sec,
            fail_duration,
            cmd_scales,
            plugin_name,
            time_for_events=block_sec,
        )
        return scenario_lines

    def schedule_track_events(self, scenario_lines, start_sec, difficulty):
        plugin_name = "track"
        line_id = self.get_last_line_num(scenario_lines) + 1
        cmd = ["targetproportion", 1 - difficulty]
        scenario_lines.append(Event(line_id, start_sec, plugin_name, cmd))
        return scenario_lines

    def schedule_comms_events(self, scenario_lines, start_sec, block_sec, comms_rate):
        plugin_name = "communications"
        if block_sec <= 0:
            return scenario_lines

        total_calls = int(comms_rate * (block_sec / 60))
        if total_calls % 2 != 0:
            total_calls += 1
        half_own = total_calls // 2
        half_other = total_calls // 2
        prompts = (["own"] * half_own) + (["other"] * half_other)
        shuffle(prompts)

        single_dur = (
            self.AVERAGE_AUDITORY_PROMPT_DURATION + self.EVENTS_REFRACTORY_DURATION
        )
        cmd_list = [["radioprompt", p] for p in prompts]

        # Ensure events don't happen in the first 5 or last 10 seconds
        time_for_events = block_sec - 15
        if time_for_events < 0:
            time_for_events = 0
        
        scenario_lines = self.distribute_randomly(
            scenario_lines,
            start_sec + 5,
            single_dur,
            cmd_list,
            plugin_name,
            time_for_events=time_for_events,
        )
        return scenario_lines

    def schedule_resman_events(self, scenario_lines, start_sec, difficulty):
        plugin_name = "resman"
        plugin = self.plugins[plugin_name]
        pumps = plugin.parameters["pump"]
        
        infinite_cap = sum(p["flow"] for k, p in pumps.items() if k in ["2", "4"])
        finite_cap = sum(p["flow"] for k, p in pumps.items() if k in ["5", "6"])
        total_cap = infinite_cap + finite_cap

        if total_cap <= 0:
            return scenario_lines

        max_leak = int(total_cap / 2)
        target_tanks = [
            k for k, v in plugin.parameters["tank"].items() if v["target"] is not None
        ]

        line_id = self.get_last_line_num(scenario_lines)
        for tank in target_tanks:
            line_id += 1
            base_value = int(max_leak * difficulty)
            variation = randint(-25, 25)
            leakage_value = base_value + variation
            if leakage_value < 0:
                leakage_value = 0
            
            cmd = [f"tank-{tank}-lossperminute", leakage_value]
            scenario_lines.append(Event(line_id, start_sec, plugin_name, cmd))

        return scenario_lines
