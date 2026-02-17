#! .venv/bin/python3

# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
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
with open('config.ini', 'r') as f:
    language_iso = [l for l in f.readlines()
                    if 'language=' in l][0].split('=')[-1].strip()
language = gettext.translation('openmatb', LOCALE_PATH, [language_iso])
language.install()


# Only after language installation, import core modules (they must be translated)
from core import Scheduler, ReplayScheduler
from core.constants import REPLAY_MODE
from core.window import Window
from core.selector import FileSelector


class OpenMATB:
    def __init__(self):
        # The MATB window must be borderless (for non-fullscreen mode)
        Window(style=Window.WINDOW_STYLE_DIALOG, resizable=True)

        # Skip the selector when a replay session ID is given via command line
        show_selector = not (REPLAY_MODE and len(sys.argv) > 2)

        if show_selector:
            mode = 'replay' if REPLAY_MODE else 'scenario'
            selected = FileSelector(Window.MainWindow, mode).run()
            if selected is None:
                sys.exit(0)
        else:
            selected = None

        if REPLAY_MODE:
            ReplayScheduler(session_path=selected)
        else:
            Scheduler(scenario_path=selected)

if __name__ == '__main__':
    app = OpenMATB()
