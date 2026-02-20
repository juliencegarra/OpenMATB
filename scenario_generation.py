# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Pure scenario generation logic — no Window/plugin initialization at module level.

This module contains dataclasses for scenario configuration and all the pure
functions needed to generate an OpenMATB scenario file.  It is imported by both
the CLI (scenario_generator.py) and the UI (scenario_generator_ui.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from random import randint, shuffle
from time import time
from typing import Any

from core.constants import PATHS
from core.event import Event


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class BlockConfig:
    duration_sec: int = 60
    plugins: dict[str, float] = field(default_factory=dict)
    # Ex: {"track": 0.25, "sysmon": 0.25, "communications": 0.25, "resman": 0.25}
    extra_events: list[tuple[str, str, Any]] = field(default_factory=list)
    # Ex: [("sysmon", "alerttimeout", 5000), ("communications", "voiceidiom", "fr")]


@dataclass
class InterBlockEvent:
    type: str  # "instructions" or "genericscales"
    filename: str  # relative path of the file
    position: int  # index of block AFTER which to insert (0 = before block 1)


@dataclass
class ScenarioConfig:
    scenario_name: str = "three_load_levels"
    events_refractory_duration: int = 1
    communications_target_ratio: float = 0.50
    average_auditory_prompt_duration: int = 13
    blocks: list[BlockConfig] = field(default_factory=list)
    inter_block_events: list[InterBlockEvent] = field(default_factory=list)


# ── Pure helper functions ────────────────────────────────────────────────────


def part_duration_sec(duration_sec: int, part_left: int, duration_list: list[int] | None = None) -> list[int]:
    if duration_list is None:
        duration_list = list()
    MIN_PART_DURATION_SEC: int = 0
    if duration_sec == 0:
        return duration_list

    # part_left is used to prevent taking too huge time at once
    part_left = max(2, part_left)
    allowed_max_duration: int = int(duration_sec / (part_left - 1))

    n: int = randint(MIN_PART_DURATION_SEC, allowed_max_duration)
    return part_duration_sec(duration_sec - n, part_left - 1, duration_list + [n])


def get_part_durations(duration_sec: int, part_number: int) -> list[int]:
    while True:
        parts: list[int] = part_duration_sec(duration_sec, part_number)
        if len(parts) == part_number:
            break
    shuffle(parts)
    return parts


def reduce(p: float, q: float) -> tuple[int, int]:
    if p == q:
        return 1, 1
    x: float = max(p, q)
    y: float = min(p, q)
    while True:
        x %= y
        if x == 0:
            break
        if x < y:
            temp: float = x
            x = y
            y = temp
    return int(p / y), int(q / y)


def choices(l: list[str], k: int, randomize: bool) -> list[str]:
    wl: list[str] = list(l)
    shuffle(wl)
    nl: list[str] = list()
    while len(nl) < k:
        if len(wl) == 0:
            wl = list(l)
            shuffle(wl)
        nl.append(wl.pop())

    if randomize:
        shuffle(nl)
    return nl


def get_events_from_scenario(scenario_lines: list[str | Event]) -> list[Event]:
    return [l for l in scenario_lines if isinstance(l, Event)]


def get_task_current_state(scenario_lines: list[str | Event], plugin: str) -> list[str] | None:
    # Filter the event list to plugin events and check its emptyness
    scenario_events: list[Event] = get_events_from_scenario(scenario_lines)
    task_events: list[Event] = [e for e in scenario_events if e.plugin == plugin]
    if len(task_events) == 0:
        return None

    # If some events are present, keep only start, stop, pause, resume, hide and show events
    cmd_keep_list: list[str] = ["start", "pause", "resume"]
    task_cmd_events: list[Event] = [e for e in task_events if e.command[0] in cmd_keep_list]
    if len(task_cmd_events) > 0:
        return task_cmd_events[-1].command
    else:
        return None


# ── Event distribution ───────────────────────────────────────────────────────


def distribute_events(
    scenario_lines: list[str | Event],
    start_sec: int,
    single_duration: float,
    cmd_list: list[list[Any]],
    plugin_name: str,
    step_duration_sec: int,
) -> list[str | Event]:
    print(f"Distributing {len(cmd_list)} {plugin_name} events in time")
    total_event_duration: float = len(cmd_list) * single_duration
    rest_sec: float = step_duration_sec - total_event_duration

    n: int = len(cmd_list) + 1  # Delay number

    random_delays: list[int] = get_part_durations(rest_sec, n) if n > 1 else [rest_sec]
    random_delays = random_delays[:-1]  # The last delay is useless

    onset_sec: float = start_sec
    lastline: int = int(get_events_from_scenario(scenario_lines)[-1].line)

    for previous_delay, cmd in zip(random_delays, cmd_list):
        lastline += 1
        onset_sec += previous_delay
        scenario_lines.append(Event(lastline, onset_sec, plugin_name, cmd))
        onset_sec += single_duration
    return scenario_lines


# ── Phase generation ─────────────────────────────────────────────────────────


def add_scenario_phase(
    scenario_lines: list[str | Event],
    task_difficulty_tuples: tuple[tuple[str, float], ...],
    start_sec: int,
    plugins: dict[str, Any],
    config: ScenarioConfig,
    block_duration_sec: int,
) -> list[str | Event]:
    # Compute next line number
    scenario_events: list[Event] = get_events_from_scenario(scenario_lines)
    start_line: int = scenario_events[-1].line + 1 if len(scenario_events) != 0 else 1

    # If a plugin is active and not desired, pause and hide it
    for plugin_name in ["sysmon", "tracking", "communications", "resman", "scheduling"]:
        task_state: list[str] | None = get_task_current_state(scenario_lines, plugin_name)
        active = task_state is not None and task_state[0] in ["start", "resume"]
        desired = plugin_name in [p for (p, d) in task_difficulty_tuples]
        if active and not desired:
            scenario_lines.append(Event(start_line, start_sec, plugin_name, "pause"))
            start_line += 1
            scenario_lines.append(Event(start_line, start_sec, plugin_name, "hide"))
            start_line += 1

    # If the desired plugin is not started or inactive, add the relevant commands
    for plugin_name, difficulty in task_difficulty_tuples:
        plugin: Any = plugins.get(plugin_name)
        task_state = get_task_current_state(scenario_lines, plugin_name)
        if task_state is None:
            scenario_lines.append(Event(start_line, start_sec, plugin_name, "start"))
            start_line += 1
        elif task_state is not None and task_state[0] == "pause":
            scenario_lines.append(Event(start_line, start_sec, plugin_name, "show"))
            start_line += 1
            scenario_lines.append(Event(start_line, start_sec, plugin_name, "resume"))
            start_line += 1

        # ── SYSMON ──
        if plugin_name == "sysmon":
            print("System monitoring | computing events")
            failure_duration_sec: float = (
                plugin.parameters["alerttimeout"] / 1000 + config.events_refractory_duration
            )
            single_failure_ratio: float = failure_duration_sec / block_duration_sec
            max_events_N: int = int(1 / single_failure_ratio)
            difficulty_events_N: int = int(difficulty / single_failure_ratio)
            events_N: int = min(max_events_N, difficulty_events_N)

            # Light events
            light_names: list[str] = [k for k, v in plugin.parameters["lights"].items()]
            light_list: list[str] = choices(light_names, events_N, True)
            cmd_list: list[list[Any]] = [[f"lights-{l}-failure", True] for l in light_list]
            scenario_lines = distribute_events(
                scenario_lines, start_sec, failure_duration_sec, cmd_list, plugin_name, block_duration_sec
            )

            # Scale events
            scale_names: list[str] = [k for k, v in plugin.parameters["scales"].items()]
            scale_list: list[str] = choices(scale_names, events_N, True)
            cmd_list = [[f"scales-{s}-failure", True] for s in scale_list]
            scenario_lines = distribute_events(
                scenario_lines, start_sec, failure_duration_sec, cmd_list, plugin_name, block_duration_sec
            )

        # ── TRACKING ──
        elif plugin_name == "track":
            print("Tracking | computing events")
            scenario_lines.append(Event(start_line, start_sec, plugin_name, ["targetproportion", 1 - difficulty]))
            start_line += 1

        # ── COMMUNICATIONS ──
        elif plugin_name == "communications":
            print("Communications | computing events")
            averaged_duration_sec: int = config.average_auditory_prompt_duration
            single_duration_sec: float = averaged_duration_sec + config.events_refractory_duration
            communication_ratio: float = difficulty
            single_event_ratio: float = single_duration_sec / block_duration_sec
            max_event_num: int = int(block_duration_sec / single_duration_sec)
            current_event_num: int = int(communication_ratio / single_event_ratio)
            event_num: int = min(max_event_num, current_event_num)

            n_ratio, d_ratio = reduce(config.communications_target_ratio * 100, 100)
            promptlist: list[str] = ["own"] * n_ratio + ["other"] * (d_ratio - n_ratio)

            if (event_num % d_ratio) == 0 and event_num > 1:
                prompt_list: list[str] = choices(promptlist, event_num, True)
                p: float = prompt_list.count("own") / len(prompt_list)
                while abs(p - n_ratio / d_ratio) > 1e-9:
                    prompt_list = choices(promptlist, event_num, True)
                    p = prompt_list.count("own") / len(prompt_list)
            else:
                prompt_list = choices(promptlist, event_num, True)
            print("Communications | List :" + " - ".join(prompt_list))

            cmd_list = [["radioprompt", p] for p in prompt_list]
            scenario_lines = distribute_events(
                scenario_lines, start_sec, single_duration_sec, cmd_list, plugin_name, block_duration_sec
            )

        # ── RESMAN ──
        elif plugin_name == "resman":
            print("Resources management | computing events")
            pumps: dict[str, dict[str, Any]] = plugin.parameters["pump"]
            infinite_capacity: int = sum([p["flow"] for k, p in pumps.items() if k in ["2", "4"]])
            finite_capacity: int = sum([p["flow"] for k, p in pumps.items() if k in ["5", "6"]])
            total_capacity: int = infinite_capacity + finite_capacity
            maximum_single_leakage: int = int(total_capacity / 2)

            target_tank_letters: list[str] = [
                k for k, t in plugin.parameters["tank"].items() if t["target"] is not None
            ]
            for letter in target_tank_letters:
                cmd: list[Any] = [f"tank-{letter}-lossperminute", int(maximum_single_leakage * difficulty)]
                scenario_lines.append(Event(start_line, start_sec, plugin_name, cmd))
                start_line += 1

        # ── SCHEDULING ──
        elif plugin_name == "scheduling":
            print("Scheduling | computing events")
            # Difficulty controls minduration: lower difficulty = higher minduration (easier)
            min_duration: int = int(5000 * (1 - difficulty) + 500)
            scenario_lines.append(Event(start_line, start_sec, plugin_name,
                                        ["minduration", min_duration]))
            start_line += 1

    return scenario_lines


# ── Orchestration ────────────────────────────────────────────────────────────


def _insert_inter_block_events(
    scenario_lines: list[str | Event],
    config: ScenarioConfig,
    position: int,
    time_sec: int,
) -> tuple[list[str | Event], int]:
    """Insert inter-block events (instructions/genericscales) at the given position.

    Returns updated scenario_lines and the additional time consumed (pause duration).
    """
    extra_time: int = 0
    inter_events: list[InterBlockEvent] = [
        ie for ie in config.inter_block_events if ie.position == position
    ]
    if not inter_events:
        return scenario_lines, 0

    scenario_events: list[Event] = get_events_from_scenario(scenario_lines)
    start_line: int = scenario_events[-1].line + 1 if scenario_events else 1
    current_time: int = time_sec

    for ie in inter_events:
        # Pause all active tasks before inter-block event
        scenario_lines.append(f"Inter-block: {ie.type} ({ie.filename})")

        # Add the inter-block start event
        scenario_lines.append(Event(start_line, current_time, ie.type, [ie.filename]))
        start_line += 1
        scenario_lines.append(Event(start_line, current_time, ie.type, "start"))
        start_line += 1

        # The inter-block event has no fixed duration — OpenMATB handles it
        # We just mark stop right after start (the runtime handles the pause)
        scenario_lines.append(Event(start_line, current_time, ie.type, "stop"))
        start_line += 1

    return scenario_lines, extra_time


def generate_scenario(config: ScenarioConfig, plugins: dict[str, Any]) -> list[str | Event]:
    """Generate a complete scenario from config and plugin instances.

    Returns a list of scenario lines (strings for comments, Event objects for events).
    """
    scenario_lines: list[str | Event] = list()
    cumulative_extra_time: int = 0

    for i, block in enumerate(config.blocks):
        # Insert inter-block events BEFORE this block (position == i means before block i)
        if i == 0 and scenario_lines:
            pass  # No events before block 0 unless explicitly positioned
        start_time_sec: int = sum(b.duration_sec for b in config.blocks[:i]) + cumulative_extra_time

        # Inter-block events at position i (before block i+1, i.e. after block i-1)
        if config.inter_block_events:
            scenario_lines, extra = _insert_inter_block_events(
                scenario_lines, config, i, start_time_sec,
            )
            cumulative_extra_time += extra

        task_difficulty_tuples: tuple[tuple[str, float], ...] = tuple(
            (name, difficulty) for name, difficulty in block.plugins.items()
        )

        # Compute average difficulty for the block label
        avg_difficulty: float = (
            sum(block.plugins.values()) / len(block.plugins) if block.plugins else 0
        )
        ch_str: str = f"Block n\u00b0 {i + 1}. Technical load = {round(avg_difficulty * 100, 1)} %"
        scenario_lines.append(ch_str)
        print("\nAdding " + ch_str)

        # Recalculate start_time after potential inter-block additions
        start_time_sec = sum(b.duration_sec for b in config.blocks[:i]) + cumulative_extra_time

        # Inject extra events (advanced plugin parameters) at block start
        if block.extra_events:
            scenario_events = get_events_from_scenario(scenario_lines)
            line_num: int = scenario_events[-1].line + 1 if scenario_events else 1
            for plugin_name, param_name, param_value in block.extra_events:
                scenario_lines.append(
                    Event(line_num, start_time_sec, plugin_name, [param_name, param_value])
                )
                line_num += 1

        scenario_lines = add_scenario_phase(
            scenario_lines, task_difficulty_tuples, start_time_sec,
            plugins, config, block.duration_sec,
        )

    # Insert inter-block events after the last block
    if config.blocks and config.inter_block_events:
        end_time: int = sum(b.duration_sec for b in config.blocks) + cumulative_extra_time
        scenario_lines, extra = _insert_inter_block_events(
            scenario_lines, config, len(config.blocks), end_time,
        )

    # Stop all tasks at the very end
    if config.blocks:
        start_time_sec = sum(b.duration_sec for b in config.blocks) + cumulative_extra_time
        scenario_events = get_events_from_scenario(scenario_lines)
        start_line: int = scenario_events[-1].line + 1 if len(scenario_events) != 0 else 1
        for task in set([e.plugin for e in scenario_events]):
            scenario_lines.append(Event(start_line, start_time_sec, task, "stop"))
            start_line += 1

    return scenario_lines


def format_scenario_lines(scenario_lines: list[str | Event], config: ScenarioConfig) -> list[str]:
    """Format scenario lines into a list of strings (same format as the output file)."""
    date_str: str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    result: list[str] = [
        "# OpenMATB scenario generator",
        "",
        f"# Name: {config.scenario_name}",
        f"# Date: {date_str}",
        "",
    ]
    for evt in scenario_lines:
        if isinstance(evt, Event):
            result.append(evt.line_str)
        elif isinstance(evt, str):
            result.append("")
            result.append("# " + evt)
    return result


def write_scenario_file(scenario_lines: list[str | Event], config: ScenarioConfig) -> Path:
    """Write scenario lines to a timestamped file. Returns the output path."""
    timestamp: float = time()
    date_time: datetime = datetime.fromtimestamp(timestamp)
    date_str_1: str = date_time.strftime("%d%m%Y_%H%M%S")
    date_str_2: str = date_time.strftime("%d/%m/%Y %H:%M:%S")

    scenario_path: Path = PATHS["SCENARIOS"].joinpath("generated", f"{config.scenario_name}_{date_str_1}.txt")
    scenario_path.parent.mkdir(parents=True, exist_ok=True)

    with open(str(scenario_path), "w", encoding="utf-8") as scenario_f:
        scenario_f.write("# OpenMATB scenario generator\n\n")
        scenario_f.write(f"# Name: {config.scenario_name}\n")
        scenario_f.write(f"# Date: {date_str_2}\n\n")

        # Append the generated lines
        for evt in scenario_lines:
            if isinstance(evt, Event):
                scenario_f.write(evt.line_str + "\n")
            elif isinstance(evt, str):
                scenario_f.write("\n# " + evt + "\n")

    print(f"\nScenario generated: {scenario_path!s}")
    return scenario_path
