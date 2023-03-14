#! .venv/bin/python3.9

# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import gettext, configparser, pdb
from pathlib import Path
from sys import exit
from random import random, shuffle, randint
from time import time
from datetime import datetime

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


# Imports #
from core.scenario import Event
from core.constants import PATHS
from plugins import *


# Constants #
EVENTS_REFRACTORY_DURATION = 1  # Delay before the next event is allowed (in seconds)
DIFFICULTY_MIN = 0
DIFFICULTY_MAX = 1
DIFFICULTY_STEP_NUMBER = 20
DIFFICULTY_STEP = (DIFFICULTY_MAX - DIFFICULTY_MIN) / (DIFFICULTY_STEP_NUMBER - 1)
STEP_DURATION_SEC = 60
COMMUNICATIONS_TARGET_RATIO = 0.50  # Proportion of target communications
SCENARIO_NAME = 'incapacitation'

# Specify a scenario that should be added at the beginning
ADD_SCENARIO_PATH = PATHS['SCENARIOS'].joinpath('custom_incapacitation.txt')


# Plugin instances #
# Useful to manipulate parameters #
plugins = {'track':Track(silent=True), 
           'sysmon':Sysmon(),
           'communications':Communications(),
           'resman':Resman()}
           

def part_duration_sec(duration_sec, part_left, duration_list=list()):
    MIN_PART_DURATION_SEC = 0
    if duration_sec == 0:
        return duration_list
        
    # part_left is used to prevent taking too huge time at once
    part_left = max(2, part_left)
    allowed_max_duration = int(duration_sec/(part_left-1))
    
    # ~ print(duration_sec, part_left, allowed_max_duration, duration_list)
    # ~ print(MIN_PART_DURATION_SEC, duration_sec, part_left)
    n = randint(MIN_PART_DURATION_SEC, allowed_max_duration)
    return part_duration_sec(duration_sec - n, part_left-1, duration_list + [n])
           

def get_part_durations(duration_sec, part_number):
    while True:
        parts = part_duration_sec(duration_sec, part_number)
        if len(parts) == part_number:
            break
    shuffle(parts)
    return parts
    

def reduce(p, q):
    if p == q: return 1, 1
    x = max(p, q); y = min(p, q);
    while True:
        x %= y
        if x == 0: break
        if x < y: temp = x; x = y; y = temp;
    return int(p/y), int(q/y)
    

def choices(l, k, randomize):
    wl = list(l)
    shuffle(wl)
    nl = list()
    while len(nl) < k:
        if len(wl) == 0:
            wl = list(l)
            shuffle(wl)
        nl.append(wl.pop())
    
    if randomize == True:
        shuffle(nl)
    return nl
    

def get_events_from_scenario(scenario_lines):
    return [l for l in scenario_lines if isinstance(l, Event)]


def get_task_current_state(scenario_lines, plugin):
    # Filter the event list to plugin events and check its emptyness
    scenario_events = get_events_from_scenario(scenario_lines)
    task_events = [e for e in scenario_events if e.plugin==plugin]
    if len(task_events) == 0:
        return None
    
    # If some events are present, keep only start, stop, pause, resume, hide and show events
    cmd_keep_list = ['start', 'pause', 'resume']
    task_cmd_events = [e for e in task_events if e.command[0] in cmd_keep_list]
    if len(task_cmd_events) > 0:
        return task_cmd_events[-1].command
    else:
        return None


def distribute_events(scenario_lines, start_sec, single_duration, cmd_list, plugin_name):
    total_event_duration = len(cmd_list) * single_duration
    rest_sec = STEP_DURATION_SEC - total_event_duration
    n = len(cmd_list) + 1  # Delay number
    
    random_delays = get_part_durations(rest_sec, n) if n > 1 else [rest_sec]
    random_delays = random_delays[:-1]  # The last delay is useless
               
    onset_sec = start_sec
    lastline = int(scenario_lines[-1].line)

    for previous_delay, cmd in zip(random_delays, cmd_list):
        lastline += 1
        onset_sec += previous_delay
        scenario_lines.append(Event(lastline, onset_sec, plugin_name, cmd))
        onset_sec += single_duration
    return scenario_lines
    

def add_scenario_phase(scenario_lines, task_difficulty_tuples, start_sec):
    # Compute next time (in seconds) and line number
    scenario_events = get_events_from_scenario(scenario_lines)
    start_line = scenario_events[-1].line + 1 if len(scenario_events) != 0 else 1
    end_sec = start_sec + STEP_DURATION_SEC
    
    # If a plugin is active and not desired, pause and hide it
    for plugin_name in ['sysmon', 'tracking', 'communications', 'resman']:
        task_state = get_task_current_state(scenario_lines, plugin_name)
        if (task_state in ['start', 'resume'] 
                and plugin_name not in [p for (p, d) in task_difficulty_tuples]):
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 'pause'))
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 'hide'))
    
    # If the desired plugin is not started or inactive, add the relevant commands
    for (plugin_name, difficulty) in task_difficulty_tuples:
        plugin = plugins[plugin_name]
        task_state = get_task_current_state(scenario_lines, plugin_name)
        if task_state is None:
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 'start'))
        elif task_state == 'pause':
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 'show'))
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 'resume'))
    
        # Handle difficulty of each plugin separately
        # Maximum difficulty cannot simple be the maximum rate of events. For instance, in the
        # system monitoring task, permanent failures would just put the subject to hit any key
        # at any time, which is not the philosophy of a monitoring task.
        
        # SYSMON.           A failure has a given duration (alerttimeout), and multiple gauges can
        # fail simultaneously. Lights and scales should have the same amount of failure events
        # to prevent biased resources allocation.
        # Minimum difficulty = no failure at all
        # Maximum difficulty = ratio failure such that there is always a failure in either lights
        # or scales (taking EVENTS_REFRACTORY_DURATION into account)
        if plugin_name == 'sysmon':
            gauge_failure_ratio = difficulty * 2 # WARNING : the real failure ratio is twice larger
                                                 # (because applied to light and scale separately)
            
            # Failure duration sec takes into account the event refractory duration
            failure_duration_sec = plugin.parameters['alerttimeout'] / 1000 + EVENTS_REFRACTORY_DURATION
            
            # What is the failure ratio ? (i.e., one failure lasts for [failure_ratio %] of the
            # phase duration)
            single_failure_ratio = failure_duration_sec / (STEP_DURATION_SEC)
            
            # Compute the maximum number of events (to be spread between lights and scales)
            absolute_max_events = int(2/single_failure_ratio)
            max_events = min(absolute_max_events, round(gauge_failure_ratio / single_failure_ratio))
            light_events_n = scale_events_n = int(max_events/2)
            # Handle odd/even number of events
            if max_events % 2 != 0: # Is there any event to add somewhere ?
                if max_events > light_events_n + scale_events_n:
                    if random() > 0.5:
                        light_events_n += 1
                    else:
                        scale_events_n += 1
                    
            # Locate light events
            # Retrieve light names
            light_names = [k for k,v in plugin.parameters['lights'].items()]
            light_list = choices(light_names, light_events_n, True)
            cmd_list = [[f'lights-{l}-failure', True] for l in light_list]
            
            scenario_lines = distribute_events(scenario_lines, start_sec, failure_duration_sec,
                                               cmd_list, plugin_name)
            
            # Locate scale events
            # Retrieve scale names
            scale_names = [k for k,v in plugin.parameters['scales'].items()]
            scale_list = choices(scale_names, scale_events_n, True)
            cmd_list = [[f'scales-{s}-failure', True] for s in scale_list]
            
            scenario_lines = distribute_events(scenario_lines, start_sec, failure_duration_sec,
                                               cmd_list, plugin_name)
                

        # TRACKING.         The tracking difficulty is here defined has conversely proportional to
        # the zone of tolerance.
        # Minimum difficulty = maximum tolerance radius
        # Maximum difficulty = null tolerance radius
        elif plugin_name == 'track':
            scenario_lines.append(Event(start_line, start_sec, plugin_name, 
                                         ['targetproportion', 1 - difficulty]))
        
        # COMMUNICATIONS.   Here, difficulty is composed of both the number of communications,
        # and the signal to noise ratio (target versus distracting communications).
        # Minimum difficulty = no communications
        # Maximum difficulty = quasi-permanent communications
        elif plugin_name == 'communications':
            averaged_duration_sec = round(plugin.get_averaged_prompt_duration())
            single_duration_sec = averaged_duration_sec + EVENTS_REFRACTORY_DURATION
            communication_ratio = difficulty
            single_event_ratio = single_duration_sec/STEP_DURATION_SEC
            max_event_num = int(STEP_DURATION_SEC / single_duration_sec)
            current_event_num = round(communication_ratio/single_event_ratio)
            event_num = min(max_event_num, current_event_num)
            
            n,d = reduce(COMMUNICATIONS_TARGET_RATIO*100,100)
            promptlist = ['own']*n+['other']*(d-n)
            
            # If there are a sufficient number of event to garantuee a perfect
            # target ratio, control it
            # ~ print(event_num, d, event_num % d)
            
            if event_num % d==0 and event_num>1:  # The number of events is a multiple of the denominator
                prompt_list = choices(promptlist, event_num, True)
                p = prompt_list.count('own') / len(prompt_list)
                while p != n/d:
                    prompt_list = choices(promptlist, event_num, True)
            else:
                prompt_list = choices(promptlist, event_num, True)
                
            cmd_list = [['radioprompt', p] for p in prompt_list]
            scenario_lines = distribute_events(scenario_lines, start_sec, single_duration_sec,
                                               cmd_list, plugin_name)
        
        # RESMAN.           The task difficulty is proportional to a combination of
        # target tanks leakage and the number of pumps that are unavailable (failure)
        # at a given moment
        # Minimum difficulty = No leak
        # Maximum difficulty = Maximum possible (given the resources that are available)
        
        elif plugin_name == 'resman':
            pumps = plugin.parameters['pump']
            # First, compute the maximum leak level tolerated
            # It depends on both infinite and finite capacities
            # Infinite : sum of flows from undepletable tanks
            infinite_capacity = sum([p['flow'] for k,p in pumps.items() if k in ['2', '4']])
            
            # "Finite" = infinite refilling capacity of depletable tanks (6 & 5)
            finite_capacity = sum([p['flow'] for k,p in pumps.items() if k in ['5', '6']])
            total_capacity = infinite_capacity + finite_capacity
            
            maximum_single_leakage = int(total_capacity / 2)
            
            target_tank_letters = [k for k,t in plugin.parameters['tank'].items()
                                   if t['target'] is not None]
            for letter in target_tank_letters:
                cmd = [f'tank-{letter}-lossperminute', int(maximum_single_leakage * difficulty)]
                scenario_lines.append(Event(start_line, start_sec, plugin_name, cmd))
        
    return scenario_lines
    
    

def main():
    # If a custom scenario entry is specified, then modify plugin parameters because
    # some are important in the scenario generation (e.g., a failure duration).
    if ADD_SCENARIO_PATH.exists():
        # Parse each line to an Event
        # and apply each event to its corresponding plugin (code snippets from Core/scenario.py)
        events = [Event.parse_from_string(0, line_str) for line_n, line_str
                  in enumerate(open(str(ADD_SCENARIO_PATH), 'r').readlines())
                  if len(line_str.strip()) > 0 and not line_str.startswith("#")]
        for event in events:
            if len(event.command) == 1:
                getattr(plugins[event.plugin], event.command[0])(0)
            elif len(event.command) == 2:
                getattr(plugins[event.plugin], 'set_parameter')(event.command[0], event.command[1])
    
    scenario_lines = list()    # Preallocate a list for scenario lines
    
    for i in range(DIFFICULTY_STEP_NUMBER):
        current_difficulty = DIFFICULTY_MIN + DIFFICULTY_STEP * i
        scenario_lines.append(f'Block n° {i+1}. Technical load = {round(current_difficulty*100, 1)} %')
        start_time_sec = i * STEP_DURATION_SEC
        phase_tuples = (('track', current_difficulty),('sysmon', current_difficulty),
                        ('communications', current_difficulty),('resman', current_difficulty))
        scenario_lines = add_scenario_phase(scenario_lines, phase_tuples, start_time_sec)
        
    # Stop all tasks at the very end
    start_time_sec += STEP_DURATION_SEC
    for task in set([e.plugin for e in get_events_from_scenario(scenario_lines)]):
        start_line = scenario_lines[-1].line + 1 if len(scenario_lines) != 0 else 1
        scenario_lines.append(Event(start_line, start_time_sec, task, 'stop'))
        
    timestamp = time()
    date_time = datetime.fromtimestamp(timestamp)
    date_str_1 = date_time.strftime("%d%m%Y_%H%M%S")
    date_str_2 = date_time.strftime("%d/%m/%Y %H:%M:%S")
    
    scenario_path = PATHS['SCENARIOS'].joinpath('generated', f'{SCENARIO_NAME}_{date_str_1}.txt')
    
    with open(str(scenario_path), 'w') as scenario_f:
        
        # Write a header to the file
        scenario_f.write("# OpenMATB scenario generator\n\n")
                
        scenario_f.write(f"# Name: {SCENARIO_NAME}\n")
        scenario_f.write(f"# Date: {date_str_2}\n\n")
        
        # First, write a potential custom scenario file
        if ADD_SCENARIO_PATH.exists():
            scenario_f.write("# Custom scenario commands\n")
            scenario_f.write(f"# Source: {str(ADD_SCENARIO_PATH)}\n")
            with open(str(ADD_SCENARIO_PATH), 'r') as custom_f:
                for line in custom_f:
                    scenario_f.write(line)
            scenario_f.write("# End of custom commands #\n")
        
        # Then, append the generated lines
        for evt in scenario_lines:
            if isinstance(evt, Event):
                scenario_f.write(evt.line_str + '\n')
            elif isinstance(evt, str):
                scenario_f.write('\n# ' + evt + '\n')
        
        print(f"Scenario generated: {str(scenario_path)}")

if __name__ == '__main__':
    main()
    exit()
