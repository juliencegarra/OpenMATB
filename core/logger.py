# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from collections import namedtuple
from csv import DictWriter
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import IO, Any

from core.constants import PATHS, REPLAY_MODE
from core.utils import find_the_first_available_session_number

_logger: Logger | None = None


def get_logger() -> Logger:
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger


def set_logger(lg: Logger | None) -> None:
    global _logger
    _logger = lg


class Logger:
    def __init__(self) -> None:
        self.datetime: datetime = datetime.now()
        self.fields_list: list[str] = ["logtime", "scenario_time", "type", "module", "address", "value"]
        self.slot: type = namedtuple("Row", self.fields_list)
        self.maxfloats: int = 6  # Time logged at microsecond precision
        self.session_id: int | None = None
        self.lsl: Any = None

        self.session_id = find_the_first_available_session_number()
        self.mode: str = "w"

        self.scenario_time: float = 0  # Updated by the scheduler class

        self.file: IO[str] | None = None
        self.writer: DictWriter | None = None
        self.queue: list[Any] = list()

        if not REPLAY_MODE:
            self.path: Path = PATHS["SESSIONS"].joinpath(
                self.datetime.strftime("%Y-%m-%d"), f"{self.session_id}_{self.datetime.strftime('%y%m%d_%H%M%S')}.csv"
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.open()

    # TODO: see if we can/should merge record_* methods into one
    def record_event(self, event: Any) -> None:
        if len(event.command) == 1:
            adress: str = "self"
            value: str = event.command[0]
        elif len(event.command) == 2:
            adress = event.command[0]
            value = event.command[1]
        slot: list[Any] = [perf_counter(), self.scenario_time, "event", event.plugin, adress, value]
        self.write_single_slot(slot)

    def record_input(self, module: str, key: str, state: str) -> None:
        slot: list[Any] = [perf_counter(), self.scenario_time, "input", module, key, state]
        self.write_single_slot(slot)

    def record_aoi(self, container: Any, name: str) -> None:
        plugin: str = name.split("_")[0]
        widget: str = "_".join(name.split("_")[1:])
        slot: list[Any] = [perf_counter(), self.scenario_time, "aoi", plugin, widget, container.get_x1y1x2y2()]
        self.write_single_slot(slot)

    def record_state(self, graph_name: str, attribute: str, value: Any) -> None:
        module: str = graph_name.split("_")[0]
        graph_name = "_".join(graph_name.split("_")[1:])
        address: str = f"{graph_name}, {attribute}"
        slot: list[Any] = [perf_counter(), self.scenario_time, "state", module, address, value]
        self.write_single_slot(slot)

    def record_parameter(self, plugin: str, address: str, value: Any) -> None:
        slot: list[Any] = [perf_counter(), self.scenario_time, "parameter", plugin, address, value]
        self.write_single_slot(slot)

    def log_performance(self, module: str, metric: str, value: Any) -> None:
        slot: list[Any] = [perf_counter(), self.scenario_time, "performance", module, metric, value]
        self.write_single_slot(slot)

    def record_a_pseudorandom_value(self, module: str, seed: int, output: Any) -> None:
        slot: list[Any] = [perf_counter(), self.scenario_time, "seed_value", module, "", seed]
        self.write_single_slot(slot)
        slot = [perf_counter(), self.scenario_time, "seed_output", module, "", output]
        self.write_single_slot(slot)

    def log_manual_entry(self, entry: str, key: str = "manual") -> None:
        slot: list[Any] = [perf_counter(), self.scenario_time, key, "", "", entry]
        self.write_single_slot(slot)

    def __enter__(self) -> Logger:
        self.open()
        return self

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        self.file.close()

    def open(self) -> None:
        create_header: bool = not (self.path.exists() and self.mode == "a")
        self.file = open(str(self.path), self.mode, newline="")
        self.writer = DictWriter(self.file, fieldnames=self.fields_list)
        if create_header:
            self.writer.writeheader()

    def close(self) -> None:
        self.file.close()

    def add_row_to_queue(self, row: Any) -> None:
        self.queue.append(row)

    def empty_queue(self) -> None:
        self.queue = list()

    def round_row(self, row: Any) -> Any:
        new_list: list[Any] = list()
        for col in row:
            new_value: Any = round(col, self.maxfloats) if isinstance(col, (float, int)) else col
            new_list.append(new_value)
        return self.slot(*new_list)

    def write_row_queue(self, change_dict: dict[str, Any] | None = None) -> None:
        if not REPLAY_MODE:
            if len(self.queue) == 0:
                print(_("Warning, queue is empty"))
            else:
                for this_row in self.queue:
                    row_dict: dict[str, Any] = self.round_row(this_row)._asdict()
                    if change_dict is not None:
                        for k, v in change_dict.items():
                            row_dict[k] = v
                    self.writer.writerow(row_dict)
                    if self.lsl is not None:
                        self.lsl.push(";".join([str(r) for r in row_dict.values()]))
                self.empty_queue()

    def write_single_slot(self, values: list[Any]) -> None:
        row: Any = self.slot(*values)
        self.add_row_to_queue(row)
        self.write_row_queue()

    def set_totaltime(self, totaltime: float) -> None:
        self.totaltime: float = totaltime

    def set_scenario_time(self, scenario_time: float) -> None:
        self.scenario_time = scenario_time

