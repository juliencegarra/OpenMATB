#! .venv/bin/python3

# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import gettext
import sys
from pathlib import Path

import pyglet

# Read and install the specified language iso
# The LOCALE_PATH constant can't be set into constants.py because
# the latter must be translated itself
LOCALE_PATH: Path = Path(".", "locales")

# Only language is accessed manually from the config.ini to avoid circular imports
# (i.e., utils needing translation needing utils and so on)
# In the browser, the page can override it with ?lang=xx_XX
with open("config.ini", "r") as f:
    language_iso: str = [l for l in f.readlines() if "language=" in l][0].split("=")[-1].strip()
if sys.platform == "emscripten":  # core.platform can't be imported before translation
    from urllib.parse import parse_qs

    import js

    language_iso = parse_qs(str(js.window.location.search).lstrip("?")).get("lang", [language_iso])[-1]
language: gettext.NullTranslations = gettext.translation("openmatb", LOCALE_PATH, [language_iso], fallback=True)
language.install()


# Only after language installation, import core modules (they must be translated)
from core import ReplayScheduler, Scheduler
from core.constants import ARGS, PATHS, REPLAY_MODE
from core.platform import notify_page, setup_web, url_params
from core.selector import FileSelector
from core.utils import get_conf_value
from core.window import Window


class OpenMATB:
    def __init__(self) -> None:
        setup_web()
        # The MATB window must be borderless (for non-fullscreen mode)
        Window(style=Window.WINDOW_STYLE_DIALOG, resizable=True)
        # Keep references: pyglet only holds weak references to event handlers
        self.selector: FileSelector | None = None
        self.scheduler: Scheduler | None = None

        if REPLAY_MODE:
            # Skip the selector when a replay session is given (-r <session> or ?session=)
            if isinstance(ARGS.replay, str) or "session" in url_params():
                self.start(None)
            else:
                self.selector = FileSelector(Window.MainWindow, "replay")
                self.selector.open(self.on_selected)
        else:
            # Priority: 1) command-line scenario, 2) ?scenario= or config.ini, 3) selector UI
            ini_scenario: str = url_params().get("scenario") or get_conf_value("Openmatb", "scenario_path").strip()
            if ARGS.scenario:
                scenario_path: Path = Path(ARGS.scenario)
                self.start(scenario_path if scenario_path.is_absolute() else PATHS["SCENARIOS"] / scenario_path)
            elif ini_scenario:
                self.start(PATHS["SCENARIOS"].joinpath(ini_scenario))
            else:
                self.selector = FileSelector(Window.MainWindow, "scenario")
                self.selector.open(self.on_selected)

    def on_selected(self, selected: Path | None) -> None:
        self.selector = None
        if selected is None:  # Selection cancelled
            Window.MainWindow.close()
            pyglet.app.exit()
            notify_page("openmatb-exit")
        else:
            self.start(selected)

    def start(self, selected: Path | None) -> None:
        if REPLAY_MODE:
            self.scheduler = ReplayScheduler(session_path=selected)
        else:
            self.scheduler = Scheduler(scenario_path=selected)


if __name__ == "__main__":
    app: OpenMATB = OpenMATB()
    pyglet.app.run()  # Blocks on desktop, returns immediately in the browser
