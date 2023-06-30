#! .venv/bin/python3

# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import gettext, sys
from pathlib import Path

# Read and install the specified language iso
# The LOCALE_PATH constant can't be set into constants.py because
# the latter must be translated itself
LOCALE_PATH = Path('.', 'locales')

# Only language is accessed manually from the config.ini to avoid circular imports
# (i.e., utils needing translation needing utils and so on)
language_iso = [l for l in open('config.ini', 'r').readlines()
                if 'language=' in l][0].split('=')[-1].strip()
language = gettext.translation('openmatb', LOCALE_PATH, [language_iso])
language.install()

# Only after language installation, import core modules (they must be translated)
from core.error import errors
from core import LogReader, Window, Scenario, Scheduler, ReplayScheduler
from core.constants import PATHS as P, REPLAY_MODE
from core.logger import logger
from core.utils import get_conf_value, find_the_first_available_session_number, find_the_last_session_number

class OpenMATB:
    def __init__(self):
        # The MATB window must be bordeless (for non-fullscreen mode)
        window = Window(style=Window.WINDOW_STYLE_BORDERLESS)

        if not REPLAY_MODE:
            content = Scenario()
            cls = Scheduler
        else:
            content = LogReader()
            cls = ReplayScheduler

        self.scheduler = cls(window, content)
        self.scheduler.run()

if __name__ == '__main__':
    app = OpenMATB()


    # window.on_key_press_replay = self.on_key_press

            # self.container_media = window.get_container('mediastrip')
            # self.container_input = window.get_container('inputstrip')

