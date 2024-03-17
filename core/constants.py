# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import sys
from pyglet.graphics import OrderedGroup as Group
from pathlib import Path
import configparser

REPLAY_MODE = len(sys.argv) > 1 and sys.argv[1] == '-r'
REPLAY_STRIP_PROPORTION = 0.08

C = COLORS = dict(WHITE=(255, 255, 255, 255),
                  WHITE_TRANSLUCENT=(255, 255, 255, 235),
                  BLACK=(50, 50, 50, 255),
                  GREEN=(142, 219, 176, 255),
                  RED=(241, 100, 100, 255),
                  BACKGROUND=(240, 240, 240, 255),
                  LIGHTGREY=(220, 220, 220, 255),
                  DARKGREY=(50, 50, 50, 255),
                  GREY=(200, 200, 200, 255),
                  BLUE=(153, 204, 255, 255))

F = FONT_SIZES = dict(SMALL=12,
                      MEDIUM=16,
                      LARGE=20,
                      XLARGE=30)

# Proportion of the plugin title into its container
PLUGIN_TITLE_HEIGHT_PROPORTION = 0.1

# Limit between the background and the foreground in relation with draw order
BFLIM = 15

# Ignore these plugins arguments
DEPRECATED = ['pumpstatus', 'end', 'cutofffrequency', 'equalproportions']

PATHS = {k.upper():Path('.', k) for k in ['plugins', 'sessions']}
PATHS.update({k.upper():Path('.', 'includes', k)
              for k in ['img', 'instructions', 'scenarios', 'sounds', 'questionnaires']})

[path.mkdir(parents=False, exist_ok=True) for p, path in PATHS.items() if path.exists() is False]
PATHS['SCENARIO_ERRORS'] = Path('.', 'last_scenario_errors.log')

# Read the configuration file
CONFIG = configparser.ConfigParser()
CONFIG.read(PATHS['PLUGINS'].parent.joinpath('config.ini'))
