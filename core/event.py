# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import re
##from pyglet.window import key as winkey
##from core.constants import PATHS as P, REPLAY_MODE
##from core.logger import logger
##from core.error import errors
##from core.utils import get_conf_value

from core.constants import DEPRECATED

class Event:
    sep = ';'

    def __init__(self, line_id, time_sec, plugin, command):
        self.line = int(line_id)
        self.time_sec = time_sec
        self.plugin = plugin
        self.command = [command] if not isinstance(command, list) else command
        self.done = False
        self.line_str = self.get_line_str()


    @classmethod
    def parse_from_string(cls, line_id, line_str):
        time_str, plugin, *command = line_str.strip().split(cls.sep)
        h, m, s = time_str.split(':')
        time_sec = int(h) * 3600 + int(m) * 60 + int(s)
        return cls(line_id, time_sec, plugin, command)


    def __repr__(self):
        return f'Event({self.line}, {self.time_sec}, {self.plugin}, {self.command})'


    def __str__(self):
        return f'l.{self.line} > {self.get_line_str()}'


    def __len__(self):
        return len(self.command)


    def get_line_str(self) -> str:
        return f'{self.get_time_hms_str()}{self.sep}{self.plugin}{self.sep}{self.get_command_str()}'


    def get_time_hms_str(self) -> str:
        seconds = int(self.time_sec)
        hours = seconds // (60*60)
        seconds %= (60*60)
        minutes = seconds // 60
        seconds %= 60
        return "%01i:%02i:%02i" % (hours, minutes, seconds)


    def get_command_str(self) -> str:
        if len(self) == 1:
            return self.command[0]
        elif len(self) == 2:
            return f'{self.command[0]}{self.sep}{self.command[1]}'


    def is_deprecated(self) -> bool:
        return self.plugin in DEPRECATED or (len(self.command) > 0 and self.command[0] in DEPRECATED)
