# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import argparse
import configparser
import sys
from pathlib import Path

from pyglet.graphics import Group  # noqa: F401

from core.platform import IS_WEB, url_params, web_sessions_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="OpenMATB",
        description="Open Multi-Attribute Task Battery",
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        help=_("Path to a scenario file (.txt) to launch directly"),
    )
    parser.add_argument(
        "-r",
        dest="replay",
        nargs="?",
        const=True,
        default=False,
        metavar="SESSION",
        help=_("Launch in replay mode (optional: session path)"),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help=_("Skip dialog boxes (session, non-fatal errors, questionnaires, instructions)"),
    )
    # When running under pytest, ignore test runner arguments. In the browser, there is no command line:
    # the options are given in the page address (see REPLAY_MODE below and core.platform.url_params)
    if IS_WEB or "pytest" in sys.modules or "unittest" in sys.argv[0:1]:
        return parser.parse_args([])
    return parser.parse_args()


ARGS: argparse.Namespace = _parse_args()
if IS_WEB:
    REPLAY_MODE: bool = url_params().get("mode") == "replay"
else:
    REPLAY_MODE = ARGS.replay is not False
HEADLESS_MODE: bool = ARGS.headless
REPLAY_STRIP_PROPORTION: float = 0.08
REPLAY_PERF_STRIP_PROPORTION: float = 0.08

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
    TEXTGREY=(110, 110, 110, 255),  # Secondary text (still readable on the background)
    BLUE=(153, 204, 255, 255),
    CYAN=(0, 190, 255, 255),
    YELLOW=(255, 220, 50, 255),
)
C = COLORS

FONT_SIZES: dict[str, int] = dict(SMALL=12, MEDIUM=16, LARGE=20, XLARGE=30)
F = FONT_SIZES
_BASE_FONT_SIZES: dict[str, int] = dict(FONT_SIZES)  # For a 1920 x 1080 window
_font_scale: float = 1.0


def scale_font_sizes(width: float, height: float, minimum: float = 0.75) -> float:
    """Scale the font sizes as the task areas, from a 1920 x 1080 window: smaller in a smaller window (at least by
    minimum, to stay readable), larger in a larger one, so that the texts keep their place in every window.
    Before any text is created: the widgets read FONT_SIZES when they are created."""
    global _font_scale
    _font_scale = max(minimum, min(width / 1920, height / 1080))
    for name, size in _BASE_FONT_SIZES.items():
        FONT_SIZES[name] = round(size * _font_scale)
    return _font_scale


def scaled(length: float) -> float:
    """A length in pixels in a 1920 x 1080 window, at the scale of the fonts (e.g. a space next to a text)."""
    return length * _font_scale


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
if IS_WEB:
    # Session logs are kept in the browser persistent storage, so they can be replayed later
    PATHS["SESSIONS"] = web_sessions_path()

for path in PATHS.values():
    if not path.exists():
        path.mkdir(parents=False, exist_ok=True)
PATHS["SCENARIO_ERRORS"] = Path(".", "last_scenario_errors.log")

# Read the configuration file
CONFIG: configparser.ConfigParser = configparser.ConfigParser()
CONFIG.read(PATHS["PLUGINS"].parent.joinpath("config.ini"), encoding="utf-8")  # As main.py (not the locale one)
