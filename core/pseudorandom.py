# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import random
from typing import Any, Sequence, TypeVar

from rstr import xeger as rstrxeger

from core.constants import REPLAY_MODE
from core.logger import logger
from core.utils import find_the_last_session_number

T = TypeVar("T")

SESSION_ID: int = logger.session_id if not REPLAY_MODE else find_the_last_session_number()
plugins_using_seed: list[str] = ["communications", "sysmon"]  # Used to convert a plugin alias into
# a unique integer


def plugin_alias_to_int(plugin_alias: str) -> int:
    return plugins_using_seed.index(plugin_alias)


def set_seed(plugin_alias: str, scenario_time_sec: float, add: int = 0) -> int:
    # `add` is used in case multiple seeds must be generated at the same time (second precision)
    unique_plugin_int: int = plugin_alias_to_int(plugin_alias)
    seed: int = int(SESSION_ID) + unique_plugin_int + int(scenario_time_sec) + add
    random.seed(seed)
    return seed


def choice(arg: Sequence[T], plugin_name: str, scenario_time: float, add: int = 1) -> T:
    seed: int = set_seed(plugin_name, scenario_time, add)
    output: T = random.choice(arg)
    logger.record_a_pseudorandom_value(plugin_name, seed, output)
    return output


def sample(arg: Sequence[T], plugin_name: str, scenario_time: float, add: int) -> T:
    seed: int = set_seed(plugin_name, scenario_time, add)
    output: T = random.sample(arg, 1)[0]
    logger.record_a_pseudorandom_value(plugin_name, seed, output)
    return output


def randint(arg1: int, arg2: int, plugin_name: str, scenario_time: float) -> int:
    seed: int = set_seed(plugin_name, scenario_time)
    output: int = random.randint(arg1, arg2)
    logger.record_a_pseudorandom_value(plugin_name, seed, output)
    return output


def uniform(arg1: float, arg2: float, plugin_name: str, scenario_time: float, add: int) -> float:
    seed: int = set_seed(plugin_name, scenario_time, add)
    output: float = random.uniform(arg1, arg2)
    logger.record_a_pseudorandom_value(plugin_name, seed, output)
    return output


def xeger(call_rgx: str, plugin_name: str, scenario_time: float, add: int) -> str:
    seed: int = set_seed(plugin_name, scenario_time, add)
    output: str = rstrxeger(call_rgx)
    logger.record_a_pseudorandom_value(plugin_name, seed, output)
    return output
