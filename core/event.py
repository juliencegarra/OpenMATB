# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from core.constants import DEPRECATED


class Event:
    sep: str = ";"

    def __init__(self, line_id: int, time_sec: int, plugin: str, command: str | list[str]) -> None:
        self.line: int = int(line_id)
        self.time_sec: int = time_sec
        self.plugin: str = plugin
        self.command: list[str] = [command] if not isinstance(command, list) else command
        self.done: bool = False
        self.line_str: str = self.get_line_str()

    @classmethod
    def parse_from_string(cls, line_id: int, line_str: str) -> Event:
        time_str, plugin, *command = line_str.strip().split(cls.sep)
        h, m, s = time_str.split(":")
        time_sec: int = int(h) * 3600 + int(m) * 60 + int(s)
        return cls(line_id, time_sec, plugin, command)

    def __repr__(self) -> str:
        return f"Event({self.line}, {self.time_sec}, {self.plugin}, {self.command})"

    def __str__(self) -> str:
        return f"l.{self.line} > {self.get_line_str()}"

    def __len__(self) -> int:
        return len(self.command)

    def get_line_str(self) -> str:
        return f"{self.get_time_hms_str()}{self.sep}{self.plugin}{self.sep}{self.get_command_str()}"

    def get_time_hms_str(self) -> str:
        seconds: int = int(self.time_sec)
        hours: int = seconds // (60 * 60)
        seconds %= 60 * 60
        minutes: int = seconds // 60
        seconds %= 60
        return "%01i:%02i:%02i" % (hours, minutes, seconds)

    def get_command_str(self) -> str | None:
        if len(self) == 1:
            return self.command[0]
        elif len(self) == 2:
            return f"{self.command[0]}{self.sep}{self.command[1]}"

    def is_deprecated(self) -> bool:
        return self.plugin in DEPRECATED or (len(self.command) > 0 and self.command[0] in DEPRECATED)
