# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import sys
from pyglet.app import EventLoop
from core.event import Event
from core.clock import Clock
from core.modaldialog import ModalDialog
from core.logger import logger
from core.utils import get_conf_value
from core.constants import REPLAY_MODE
from core.error import errors
from core.window import Window
from core.scenario import Scenario
from core.joystick import joystick

class Scheduler:
    """
    This class manages events execution.
    """

    def __init__(self):
        logger.log_manual_entry(open('VERSION', 'r').read().strip(), key='version')

        self.clock = Clock('main')
        self.scenario_time = 0

        # Create the event loop
        self.clock.schedule(self.update)
        self.event_loop = EventLoop()

        self.joystick = joystick
        self.set_scenario()

        self.event_loop.run()

    def set_scenario(self, events = None):
        self.scenario = Scenario(events)

        self.events = self.scenario.events
        self.plugins = self.scenario.plugins

        # Attribute window to plugins in use, and push their handles to window
        for p in self.plugins:
            self.plugins[p].win = Window.MainWindow
            self.plugins[p].joystick = self.joystick
            if not REPLAY_MODE:
                Window.MainWindow.push_handlers(self.plugins[p].on_key_press,
                                       self.plugins[p].on_key_release)

            self.plugins[p].on_scenario_loaded(self.scenario)

        self.pause_scenario_time = False
        self.scenario_time = 0

        # We store events in a list in case their execution is delayed by a blocking event
        self.events_queue = list()
        self.blocking_plugin = None

        # Store the plugins that could be paused by a *blocking* event
        self.paused_plugins = list()


    def update(self, dt):
        if Window.MainWindow.modal_dialog is not None:
            return
        elif errors.is_empty() == False:
            errors.show_errors()

        self.update_timers(dt)
        self.update_joystick()
        self.update_active_plugins()
        self.execute_events()
        self.check_if_must_exit()


    def update_timers(self, dt):
        # Update timers with dt
        if not self.is_scenario_time_paused():
            self.scenario_time += dt
            logger.set_scenario_time(self.scenario_time)


    def update_active_plugins(self):
        # Check if there are active plugins...
        if len(self.get_active_plugins()) > 0:
            # ... if so, update them
            [p.update(self.scenario_time) for p in self.get_active_plugins()]


    def update_joystick(self):
        # Execute the update method of the joystick
        if self.joystick is None:
            return

        self.joystick.update()
        # Check if there are active plugins...
        if len(self.get_active_plugins()) > 0:
            for p in self.get_active_plugins():
                # Send joystick inputs to appropriate plugin (tracking)
                if hasattr(p, 'get_joystick_inputs'):
                    p.get_joystick_inputs(self.joystick.x, self.joystick.y)

                # ... if a joystick button has been just pressed/released
                # ... execute the according on_key_press method in active plugins
            if self.joystick.has_any_key_changed():
                for k,v in self.joystick.key_change.items():
                    if v == 'press':
                        [p.on_joy_key_press(k) for p in self.get_active_plugins()]
                    elif v == 'release':
                        [p.on_joy_key_release(k) for p in self.get_active_plugins()]

                    self.joystick.reset_key_change(k)



    def check_if_must_exit(self):
        # If no active plugin, and no remaining events, close the OpenMATB
        if len(self.get_active_plugins()) == 0 and len(self.events_queue) == 0:
            self.exit()

        # If the windows has been killed, exit the program
        if Window.MainWindow.alive == False:
            # Be careful to stop all the plugins in case they’re not
            # (so we have a stop time for each plugin, in case we must compute this somewhere)
            for p_name, plugin in self.plugins.items():
                if plugin.alive == True:
                    stop_event = Event(0, int(self.scenario_time), p_name, 'stop')
                    self.execute_one_event(stop_event)
            self.exit()


    def execute_events(self):
        # Detect a potential blocking plugin
        active_blocking_plugin = self.get_active_blocking_plugin()

        # Execute scenario events in case the scenario timer is running
        if not self.is_scenario_time_paused():
            if active_blocking_plugin is None:
                event = self.get_event_at_scenario_time(self.scenario_time)
                if event is not None:
                    self.execute_one_event(event)

            # Check if a blocking plugin has started so to pause concurrent plugins
            elif active_blocking_plugin.alive:
                # Toggle scenario_time pause only once
                if not self.is_scenario_time_paused():
                    self.pause_scenario()
                    self.paused_plugins = self.get_active_non_blocking_plugins()
                    self.execute_plugins_methods(self.paused_plugins, methods=['pause', 'hide'])

        # In Replay mode: IT IS the play/pause button that manages the scenario resuming
        elif active_blocking_plugin is None and REPLAY_MODE == False:
            if len(self.paused_plugins) > 0:
                self.execute_plugins_methods(self.paused_plugins, methods=['show', 'resume'])
                self.paused_plugins = list()
            self.resume_scenario()


    def is_scenario_time_paused(self):
        return self.pause_scenario_time == True


    def pause_scenario(self):
        self.pause_scenario_time = True
        return self.is_scenario_time_paused()


    def resume_scenario(self):
        self.pause_scenario_time = False
        return self.is_scenario_time_paused()


    def toggle_scenario(self):
        self.pause_scenario_time = not self.pause_scenario_time
        return self.is_scenario_time_paused()


    def get_active_blocking_plugin(self):
        p = self.get_plugins_by_states([('blocking', True), ('paused', False)])
        if len(p) > 0:
            return p[0]


    def get_active_non_blocking_plugins(self):
        return self.get_plugins_by_states([('blocking', False), ('paused', False)])


    def get_active_plugins(self):
        return self.get_plugins_by_states([('alive', True)])


    def execute_one_event(self, event):
        # Set the plugin corresponding to the event
        plugin = self.plugins[event.plugin]

        # If one argument, assume it is a plugin method to execute
        if len(event.command) == 1:
            getattr(plugin, event.command[0])()

        # If two arguments in the 'command' field, suppose a (parameter, value) to update
        elif len(event.command) == 2:
            getattr(plugin, 'set_parameter')(event.command[0], event.command[1])

        event.done = 1

        # The event can be logged whenever inside the method, since self.durations remain
        # constant all along it
        logger.record_event(event)


    def execute_plugins_methods(self, plugins, methods):
        if len(plugins) == 0:
            return

        if isinstance(methods, str):
            methods = [methods]

        for m in methods:
            for p in plugins:
                # self.execute_one_event(Event(0, 0, p.alias, m)) DO NOT create new events
                getattr(p, m)()


    def get_plugins_by_states(self, attribute_state_list):
        plugins = {k:p for k,p in self.plugins.items()}
        for (attribute, state) in attribute_state_list:
            plugins = {k:p for k,p in plugins.items() if getattr(p, attribute) == state}
        return [p for _,p in plugins.items()]


    def get_event_at_scenario_time(self, scenario_time: float):
        # Retrieve (simultaneous) events matching scenario_duration_sec
        # We look to the most precise point in the near future that might matches a set of event time(s)
        events_time = [event for event in self.events
                       if event.time_sec <= scenario_time]

        # Filter events that are either done or already in the queue
        events_time = [event for event in events_time
                       if event.done != 1]

        # Sort them according to their line number (ascending order)
        # and append the listed events in the correct order
        for event in sorted(events_time, key=lambda x: x.line):
            if event not in self.events_queue:
                self.events_queue.append(event)

        return self.unqueue_event()


    def unqueue_event(self):
        # If some events must be executed, unstack the next event
        if len(self.events_queue) > 0:
            event = self.events_queue[0]
            del self.events_queue[0]
            return event

        return None


    def exit(self):
        logger.log_manual_entry('end')
        self.event_loop.exit()
        Window.MainWindow.close() # needed for windows clean exit
        sys.exit(0)
