# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import random
from core.constants import REPLAY_MODE
from core.utils import find_the_last_session_number
from core.logger import logger
from rstr import xeger as rstrxeger


SESSION_ID = logger.session_id if REPLAY_MODE == False else find_the_last_session_number()
plugins_using_seed = ['communications', 'sysmon'] 		# Used to convert a plugin alias into 
														# a unique integer

def plugin_alias_to_int(plugin_alias):
	return plugins_using_seed.index(plugin_alias)


def set_seed(plugin_alias, scenario_time_sec, add=0):
	# `add` is used in case multiple seeds must be generated at the same time (second precision)
	unique_plugin_int = plugin_alias_to_int(plugin_alias)
	seed = int(SESSION_ID) + unique_plugin_int + int(scenario_time_sec) + add
	random.seed(seed)


def choice(arg, plugin_name, scenario_time, add=1):
	seed = set_seed(plugin_name, scenario_time, add)
	output = random.choice(arg)
	logger.record_a_pseudorandom_value(plugin_name, seed, output)
	return output


def sample(arg, plugin_name, scenario_time, add):
	seed = set_seed(plugin_name, scenario_time, add)
	output = random.sample(arg, 1)[0]
	logger.record_a_pseudorandom_value(plugin_name, seed, output)
	return output


def randint(arg1, arg2, plugin_name, scenario_time):
	seed = set_seed(plugin_name, scenario_time)
	output = random.randint(arg1, arg2)
	logger.record_a_pseudorandom_value(plugin_name, seed, output)
	return output	


def uniform(arg1, arg2, plugin_name, scenario_time, add):
	seed = set_seed(plugin_name, scenario_time, add)
	output = random.uniform(arg1, arg2)
	logger.record_a_pseudorandom_value(plugin_name, seed, output)
	return output


def xeger(call_rgx, plugin_name, scenario_time, add):
	seed = set_seed(plugin_name, scenario_time, add)
	output = rstrxeger(call_rgx)
	logger.record_a_pseudorandom_value(plugin_name, seed, output)
	return output
