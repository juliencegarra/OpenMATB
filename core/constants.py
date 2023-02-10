from pyglet.graphics import OrderedGroup as Group
from pathlib import Path


C = COLORS = dict(WHITE=(255, 255, 255, 255),
                  BLACK=(50, 50, 50, 255),
                  GREEN=(142, 219, 176, 255),
                  RED=(241, 100, 100, 255),
                  BACKGROUND=(240, 240, 240, 255),
                  LIGHTGREY=(220, 220, 220, 255),
                  GREY=(200, 200, 200, 255),
                  BLUE=(153, 204, 255, 255))

F = FONT_SIZES = dict(SMALL=12,
                      MEDIUM=15,
                      LARGE=20,
                      XLARGE=30)

# Proportion of the plugin title into its container
PLUGIN_TITLE_HEIGHT_PROPORTION = 0.1

# Limit between the background and the foreground in relation with draw order
BFLIM = 15

PATHS = {k.upper():Path('.', k) for k in ['plugins', 'sessions']}
PATHS.update({k.upper():Path('.', 'includes', k)
              for k in ['instructions', 'scenarios', 'sounds', 'questionnaires']})

[path.mkdir(parents=False, exist_ok=True) for p, path in PATHS.items() if path.exists() is False]
PATHS['SCENARIO_ERRORS'] = Path('.', 'last_scenario_errors.log')

MATCHING_ALIAS = M =dict(sysmon=_('System monitoring'),
                         track=_('Tracking'),
                         scheduling=_('Scheduling'),
                         communications=_('Communications'),
                         resman=_('Resources management'),
                         parallelport=_('Parallel port'),
                         labstreaminglayer=_('Lab streaming layer'),
                         instructions=_('Instructions'),
                         genericscales=_('Generic scales'),
                         eyetracker=_('Eye tracker'),
                         performance=_('Performance'))
