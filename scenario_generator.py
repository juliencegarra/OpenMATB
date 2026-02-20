#! .venv/bin/python3.9
# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

import configparser
import gettext
from pathlib import Path
from sys import exit
from typing import Any

# Read the configuration file
config: configparser.ConfigParser = configparser.ConfigParser()
config.read("config.ini")

# Read and install the specified language iso
# The LOCALE_PATH constant can't be set into constants.py because
# the latter must be translated itself
LOCALE_PATH: Path = Path(".", "locales")
language_iso: str = config["Openmatb"]["language"]
language: gettext.GNUTranslations = gettext.translation("openmatb", LOCALE_PATH, [language_iso])
language.install()


# Imports #
from core.constants import PATHS
from core.window import Window
from plugins import Communications, Resman, Sysmon, Track
from scenario_generation import BlockConfig, ScenarioConfig, generate_scenario, write_scenario_file

# Constants #
EVENTS_REFRACTORY_DURATION: int = 1  # Delay before the next event is allowed (in seconds)
DIFFICULTY_MIN: float = 0.25
DIFFICULTY_MAX: float = 0.85
DIFFICULTY_STEP_NUMBER: int = 3
DIFFICULTY_STEP: float = (DIFFICULTY_MAX - DIFFICULTY_MIN) / (DIFFICULTY_STEP_NUMBER - 1)
STEP_DURATION_SEC: int = 60
COMMUNICATIONS_TARGET_RATIO: float = 0.50  # Proportion of target communications
AVERAGE_AUDITORY_PROMPT_DURATION: int = 13
SCENARIO_NAME: str = "three_load_levels"

# Specify a scenario that should be added at the beginning
ADD_SCENARIO_PATH: Path = PATHS["SCENARIOS"].joinpath("custom_generator.txt")

win: Window = Window()
win.set_visible(False)

# Plugin instances #
# Useful to manipulate parameters #
plugins: dict[str, Any] = {
    "track": Track(win, silent=True),
    "sysmon": Sysmon(win),
    "communications": Communications(win),
    "resman": Resman(win),
}


def main() -> None:
    print("OpenMATB - Scenario generator")
    print("_____________________________")

    blocks: list[BlockConfig] = [
        BlockConfig(
            duration_sec=STEP_DURATION_SEC,
            plugins={"track": d, "sysmon": d, "communications": d, "resman": d},
        )
        for d in (DIFFICULTY_MIN + DIFFICULTY_STEP * i for i in range(DIFFICULTY_STEP_NUMBER))
    ]

    scenario_config: ScenarioConfig = ScenarioConfig(
        scenario_name=SCENARIO_NAME,
        events_refractory_duration=EVENTS_REFRACTORY_DURATION,
        communications_target_ratio=COMMUNICATIONS_TARGET_RATIO,
        average_auditory_prompt_duration=AVERAGE_AUDITORY_PROMPT_DURATION,
        custom_scenario_path=ADD_SCENARIO_PATH if ADD_SCENARIO_PATH.exists() else None,
        blocks=blocks,
    )

    lines = generate_scenario(scenario_config, plugins)
    path = write_scenario_file(lines, scenario_config)
    print(f"\nScenario generated: {path}")


if __name__ == "__main__":
    main()
    exit()
