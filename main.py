#! .venv/bin/python3

# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import gettext, configparser
from pathlib import Path

# Read the configuration file
config = configparser.ConfigParser()
config.read("config.ini")


# Read and install the specified language iso
# The LOCALE_PATH constant can't be set into constants.py because
# the latter must be translated itself
LOCALE_PATH = Path('.', 'locales')
language_iso = config['Openmatb']['language']
language = gettext.translation('openmatb', LOCALE_PATH, [language_iso])
language.install()

# Only after language installation, import core modules (they must be translated)
from core import Window, Scenario, Scheduler
from core.constants import PATHS as P
from core.error import errors

# Check boolean values
for param in ['fullscreen', 'highlight_aoi', 'hide_on_pause', 'display_session_number']:
    if config['Openmatb'][param].lower() in ['true', 'false']:
        if config['Openmatb'][param].lower() == 'true':
            globals()[param] = True
        else:
            globals()[param] = False
    else:
        globals()[param] = False
        errors.add_error(_(f"In config.ini, [%s] parameter must be a boolean (true or false, not %s). Defaulting to False") % (param, config['Openmatb'][param]))


class OpenMATB:
    def __init__(self):
        # The MATB window must be bordeless (in non-fullscreen mode)
        window = Window(screen_index=config['Openmatb']['screen_index'], font_name=config['Openmatb']['font_name'],
                        fullscreen=fullscreen, replay_mode=False, 
                        style=Window.WINDOW_STYLE_BORDERLESS, highlight_aoi=highlight_aoi, hide_on_pause=hide_on_pause)

        scenario_path = P['SCENARIOS'].joinpath(config['Openmatb']['scenario_path'])
        scenario = Scenario(scenario_path, window)

        errors.show_errors()

        self.scheduler = Scheduler(scenario.events, scenario.plugins, window,
                                   config['Openmatb']['clock_speed'],
                                   display_session_number)
        self.scheduler.run()

if __name__ == '__main__':
    app = OpenMATB()
