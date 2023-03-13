#! .venv/bin/python3
""" OpenMATB
"""

import gettext, configparser
from pathlib import Path
from pyglet import font


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
from core.dialog import fatalerror

# Check if the specified font is available on the system
if len(config['Openmatb']['font_name']) and not font.have_font(config['Openmatb']['font_name']):
    fatalerror(_(f"In config.ini, the specified font (%s) is not available. Correct it or leave it empty to use a default font.") % config['Openmatb']['font_name'])


# Check the specified screen index. If null, set screen_index to 0.
if len(config['Openmatb']['screen_index']) == 0:
    screen_index = 0
else:
    try:
        screen_index = int(config['Openmatb']['screen_index'])
    except ValueError:
        fatalerror(_(f"In config.ini, screen index must be an integer, not %s") % config['Openmatb']['screen_index'])

# Check boolean values
for param in ['fullscreen', 'highlight_aoi', 'hide_on_pause']:
    if config['Openmatb'][param].lower() in ['true', 'false']:
        if config['Openmatb'][param].lower() == 'true':
            globals()[param] = True
        else:
            globals()[param] = False
    else:
        fatalerror(_(f"In config.ini, [%s] parameter must be a boolean (true or false, not %s).") %           (param, config['Openmatb'][param]))


class OpenMATB:
    def __init__(self):
        # The MATB window must be bordeless (in non-fullscreen mode)
        window = Window(screen_index=screen_index, fullscreen=fullscreen,
                        replay_mode=False, style=Window.WINDOW_STYLE_BORDERLESS,
                        highlight_aoi=highlight_aoi, hide_on_pause=hide_on_pause)

        scenario_path = P['SCENARIOS'].joinpath(config['Openmatb']['scenario_path'])
        scenario = Scenario(scenario_path, window)

        self.scheduler = Scheduler(scenario.events, scenario.plugins, window,
                                   config['Openmatb']['clock_speed'],
                                   config['Openmatb']['display_session_number'])
        self.scheduler.run()

if __name__ == '__main__':
    app = OpenMATB()
