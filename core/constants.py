# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import argparse
import configparser
import sys
from pathlib import Path

from pyglet.graphics import Group  # noqa: F401


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="OpenMATB",
        description="Open Multi-Attribute Task Battery",
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        help=_("Chemin vers un fichier scénario (.txt) à lancer directement"),
    )
    parser.add_argument(
        "-r",
        dest="replay",
        nargs="?",
        const=True,
        default=False,
        metavar="SESSION",
        help=_("Lancer en mode replay (optionnel : chemin de session)"),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help=_("Passer les boîtes de dialogue (session, erreurs non fatales, questionnaires, instructions)"),
    )
    # When running under pytest, ignore test runner arguments
    if "pytest" in sys.modules or "unittest" in sys.argv[0:1]:
        return parser.parse_args([])
    return parser.parse_args()


ARGS: argparse.Namespace = _parse_args()
REPLAY_MODE: bool = ARGS.replay is not False
HEADLESS_MODE: bool = ARGS.headless
REPLAY_STRIP_PROPORTION: float = 0.08

COLORS: dict[str, tuple[int, int, int, int]] = dict(
    WHITE=(255, 255, 255, 255),
    WHITE_TRANSLUCENT=(255, 255, 255, 235),
    BLACK=(50, 50, 50, 255),
    GREEN=(142, 219, 176, 255),
    RED=(241, 100, 100, 255),
    BACKGROUND=(240, 240, 240, 255),
    LIGHTGREY=(220, 220, 220, 255),
    DARKGREY=(50, 50, 50, 255),
    GREY=(200, 200, 200, 255),
    BLUE=(153, 204, 255, 255),
    CYAN=(0, 190, 255, 255),
    YELLOW=(255, 220, 50, 255),
)
C = COLORS

FONT_SIZES: dict[str, int] = dict(SMALL=12, MEDIUM=16, LARGE=20, XLARGE=30)
F = FONT_SIZES

# Proportion of the plugin title into its container
PLUGIN_TITLE_HEIGHT_PROPORTION: float = 0.1

# Limit between the background and the foreground in relation with draw order
BFLIM: int = 15

# Ignore these plugins arguments
DEPRECATED: list[str] = ["pumpstatus", "end", "cutofffrequency", "equalproportions"]

SYSTEM_PSEUDO_PLUGIN: str = "system"
SYSTEM_COMMANDS: list[str] = ["pause", "agent", "mousecontrol"]

PATHS: dict[str, Path] = {k.upper(): Path(".", k) for k in ["plugins", "sessions"]}
PATHS.update(
    {k.upper(): Path(".", "includes", k) for k in ["img", "instructions", "scenarios", "sounds", "questionnaires"]}
)

[path.mkdir(parents=False, exist_ok=True) for p, path in PATHS.items() if path.exists() is False]
PATHS["SCENARIO_ERRORS"] = Path(".", "last_scenario_errors.log")

# Read the configuration file
CONFIG: configparser.ConfigParser = configparser.ConfigParser()
CONFIG.read(PATHS["PLUGINS"].parent.joinpath("config.ini"))
