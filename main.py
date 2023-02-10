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
from core import Window, Scenario, Scheduler, fatalerror, errorchoice
from core.constants import PATHS as P


# Check if the specified font is available on the system
if len(config['Openmatb']['font_name']) and not font.have_font(config['Openmatb']['font_name']):
    errorchoice(_(f"In config.ini, the specified font (%s) is not available. If you continue, a default font will be used.") % config['Openmatb']['font_name'])


# Check the specified screen index. If null, set screen_index to 0.
if len(config['Openmatb']['screen_index']) == 0:
    screen_index = 0
else:
    try:
        screen_index = int(config['Openmatb']['screen_index'])
    except ValueError:
        fatalerror(_(f"In config.ini, screen index must be an integer, not %s") % config['Openmatb']['screen_index'])


# Check the specified fullscreen value. If null, set to True
if config['Openmatb']['fullscreen'].lower() in ['true', 'false']:
    fullscreen = True if config['Openmatb']['fullscreen'].lower() == 'true' else False
else:
    errorchoice(_(f"In config.ini, the specified fullscreen mode must be a boolean (not %s). If you continue, fullscreen will be set to its default value (True)") % config['Openmatb']['fullscreen'])
    fullscreen = True


# Check the specified highlight_aoi value. If null, set to False
if config['Openmatb']['highlight_aoi'].lower() in ['true', 'false']:
    highlight_aoi = True if config['Openmatb']['highlight_aoi'].lower() == 'true' else False
else:
    errorchoice(_(f"In config.ini, the specified highlight_aoi value must be a boolean (not %s). If you continue, highlight_aoi will be set to its default value (False)") % config['Openmatb']['highlight_aoi'])
    highlight_aoi = False


class OpenMATB:
    def __init__(self):
        scenario_path = P['SCENARIOS'].joinpath(config['Openmatb']['scenario_path'])
        self.input_file = Scenario(scenario_path)

        # The MATB window must is bordeless (in non-fullscreen mode)
        self.window = Window(screen_index=screen_index, fullscreen=fullscreen,
                             replay_mode=False, style=Window.WINDOW_STYLE_BORDERLESS,
                             highlight_aoi=highlight_aoi)
        self.scheduler = Scheduler(self.input_file, self.window,
                                   config['Openmatb']['clock_speed'],
                                   config['Openmatb']['display_session_number'])

    def run(self):
        self.scheduler.run()

if __name__ == '__main__':
    app = OpenMATB()
    app.run()
