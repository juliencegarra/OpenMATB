# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.scheduler import Scheduler
from core.error import errors
from core.widgets import PlayPause, Simpletext, Slider, Frame, Reticle, SimpleHTML
from core.constants import COLORS as C, FONT_SIZES as F
from time import strftime, gmtime, sleep
from core.logreader import LogReader
from core.container import Container
from core.utils import get_conf_value
from random import uniform


class ReplayScheduler(Scheduler):
    """
    This class manages events execution in the context of the OpenMATB replay.
    """
    def __init__(self, window, logreader):
        self.scenario = logreader.scenario
        self.logreader = logreader
        self.inputs_queue = list(logreader.inputs)  # Copy inputs, and empty progressively
        self.keyboard_inputs = [i for i in self.inputs_queue if i['module'] == 'keyboard']
        self.joystick_inputs = [i for i in self.inputs_queue if 'joystick' in i['address']]
        self.states_queue = list(logreader.states)  # Copy states, //
        super().__init__(window, self.scenario)
        self.set_media_buttons() 
        self.set_inputs_buttons()
        self.keys_history = list()
        self.sliding = False    # The scheduler must know if the time is currently sliding
                                # to prevent update repetitions
        self.was_the_scenario_paused = False


    def set_inputs_buttons(self):
        # Plot the keyboard keys that are available in the present plugins
        input_container = self.win.get_container('inputstrip')
        key_container = input_container.reduce_and_translate(width=0.9, 
                                                             height=0.8,
                                                             y=0, x=0.5)
        self.key_widget = SimpleHTML('replay_keys', key_container, self.win, '<strong>Keyboard history:\n</strong>')
        self.key_widget.show()


    def set_media_buttons(self):

        # Media strip
        media_container = self.win.get_container('mediastrip')
        self.media_back = Frame('media_background', media_container, self.win,
                                fill_color=C['DARKGREY'], draw_order=1)
        self.media_back.show()
        pp_container = media_container.reduce_and_translate(width=0.06, height=1, x=0)
        time_container = media_container.reduce_and_translate(width=0.03, height=1, x=0.8)

        self.playpause = PlayPause('Play_pause_button', pp_container, self.win,
                                   self.toogle_scenario)
        self.time = Simpletext('elapsed_time', time_container, self.win,
                               text=self.get_time_hms_str(), font_size=F['LARGE'], color=C['WHITE'])

        end_sec = self.logreader.duration_sec
        self.slider = Slider('timeline', media_container, self.win, None, '', '', 0, end_sec, 0, 1)
        self.time.show()

        # Inputs strip
        input_container = self.win.get_container('inputstrip')
        self.inputs_back = Frame('inputs_background', input_container, self.win,
                                fill_color=C['LIGHTGREY'], draw_order=1)
        self.inputs_back.show()

        # Manually compute the joystick container to ensure it is a square
        w = h = input_container.w * 0.8
        l = input_container.l + 0.1*input_container.w
        b = input_container.b + 0.85*input_container.h
        joy_container = Container('replay_reticle', l,b,w,h)
        self.replay_reticle = Reticle('replay_reticle', joy_container, self.win, C['BLACK'],
                                      target_proportion = 0, m_draw=5)
        self.replay_reticle.show()


    def update(self, dt):
        super().update(dt)
        self.emulate_keyboard_inputs()
        self.display_joystick_inputs()
        self.process_states()
        self.update_replay_timing()


    def check_plugins_alive(self):
        return all([p.alive for _, p in self.plugins.items()])


    def check_if_must_exit(self):
        # In replay mode, exit conditions are differents. Exit only if the Window is killed.
        if self.win.alive == False:
            self.exit()


    def update_replay_timing(self):
        self.pause_if_end_reached()
        self.update_time_string()
        self.slider_control_update()
        

    def update_time_string(self):
        time_str = self.get_time_hms_str()
        self.time.set_text(time_str)


    def get_time_hms_str(self):
        return strftime('%H:%M:%S', gmtime(self.scenario_time))


    def pause_if_end_reached(self):
        if self.scenario_time >= self.logreader.end_sec and not self.is_scenario_time_paused():
            self.pause_scenario()


    def pause_scenario(self):
        is_paused = super().pause_scenario()
        self.playpause.update_button_sprite(is_paused)


    def resume_scenario(self):
        is_paused = super().resume_scenario()
        self.playpause.update_button_sprite(is_paused)


    def toogle_scenario(self):
        is_paused = super().toogle_scenario()
        self.playpause.update_button_sprite(is_paused)


    def slider_control_update(self):
        # Update the natural position of the slider when the scenario is running
        if not self.is_scenario_time_paused():
            self.slider.groove_value = self.scenario_time
            self.slider.set_groove_position()

        # At THE FIRST slider mouse press, pause scenario if not already paused
        if self.slider.hover == True and self.sliding == False:
            self.sliding = True
            self.was_the_scenario_paused = self.is_scenario_time_paused()
            if not self.is_scenario_time_paused():
                self.pause_scenario()
            
        # At THE FIRST slider mouse release, get back the scenario in its previous state (play/pause)
        # Record the target value (given by the groove position)
        if self.slider.hover == False and self.sliding == True:
            self.sliding = False
            desired_time_sec = self.slider.groove_value

            ################ TODO: BACKWARD HERE (NOT WORKING)
            if desired_time_sec < self.scenario_time:
                # Handle the case where the desired time position is backward
                # No need to reset the clock anymore since we provide it a relative target
                # (i.e., the clock is always moving forward)

                # 1. Reset the scenario time
                self.scenario_time = 0

                # 2. Stop the current active plugins
                self.plugins = dict()
                # for plugin in self.get_active_plugins():
                #     del self.plugins

                # # 3. Re-initialize plugins
                logreader = LogReader(get_conf_value('Replay', 'replay_session_id'))
                self.plugins = logreader.scenario.plugins
                for p, plugin in self.plugins.items():
                    plugin.win = self.win

                self.events = self.logreader.scenario.events   
                self.inputs_queue = list(self.logreader.inputs)  # Copy inputs, and empty progressively
                self.keyboard_inputs = [i for i in self.inputs_queue if i['module'] == 'keyboard']
                self.states_queue = list(self.logreader.states)  # Copy states, //
            ##########################################################################@

            if self.is_scenario_time_paused():
                self.resume_scenario()

            # Target time sent to the clock must be relative because the clock never pauses
            advance_time = self.slider.groove_value - self.scenario_time
            target_time = self.clock.get_time() + advance_time

            self.clock.set_target_time(target_time)


        # Soon as the clock target is reached, control if the scenario must switch back to pause
        if self.clock.is_target_reached():
            if self.was_the_scenario_paused:
                self.was_the_scenario_paused = False
                self.pause_scenario()


    def emulate_keyboard_inputs(self):
        if len(self.keyboard_inputs) > 0:
            next_input = self.keyboard_inputs[0]
            if float(next_input['scenario_time']) <= self.scenario_time:
                for plugin_name, plugin in self.plugins.items():
                    plugin.do_on_key(next_input['address'], next_input['value'], True)
                    
                cmd = f"{next_input['address']} ({next_input['value']})"
                if len(self.keys_history) > 0 and cmd != self.keys_history[-1]:
                    self.keys_history.append(cmd)
                elif len(self.keys_history) == 0:
                    self.keys_history.append(cmd)

                if len(self.keys_history) > 30:
                    del self.keys_history[0]
                del self.keyboard_inputs[0]

        # Parse key history
        history_str = f"<strong>Keyboard history:\n</strong>" + '<br>'.join([kh for kh in self.keys_history])
        self.key_widget.set_text(history_str)


    def process_states(self):
        # States are displayed as a function of scenario time (not logtime which may vary)
        # It does not matter to display each and every states. Better is to catch
        # the most current one. The following states are manually handled:
        #   – 1. The cursor position in the tracking task
        #   – 2. The frequency of each communications radio
        #   – 3. The value of each slider, in genericscales

        # Get candidates states (and their index) for being displayed, 
        # retrieve the most recent for each state category
        past_sta = [(i,s) for i,s in enumerate(self.states_queue)
                    if float(s['scenario_time']) <= self.scenario_time]

        if len(past_sta) > 0 :
            states_idx_to_del = [s[0] for s in past_sta]    # All past states will be removed from 
            display_idx = list()                            # the list
            for adr in set([s[1]['address'] for s in past_sta]):  # Browse each category
                cat_sta = [s for s in past_sta if s[1]['address'] == adr]
                display_idx.append(max([s[0] for s in cat_sta]))

        
            for this_disp_idx in display_idx:
                state = past_sta[this_disp_idx][1]

                # 1. Cursor position
                if 'cursor_proportional' in state['address']:
                    cursor_relative = self.plugins['track'].reticle.proportional_to_relative(state['value'])
                    self.plugins['track'].cursor_position = cursor_relative

                # 2. Radio frequencies
                elif 'radio_frequency' in state['address']:
                    radio_name = state['address'].replace(', radio_frequency', '').replace('radio_', '')
                    radio = self.plugins['communications'].get_radios_by_key_value('name', radio_name)[0]
                    radio['currentfreq'] = state['value']

                # 3. Genericscales slider values
                elif 'slider_' in state['address']:
                    slider_name = state['address'].replace(', value', '')
                    slider = self.plugins['genericscales'].sliders[slider_name]
                    slider.groove_value = state['value']


            # Delete states that have been just played from the queue
            # NOTE: delete in reverse order to avoid changing indexes while iterating
            for del_idx in sorted(states_idx_to_del, reverse=True):
                del self.states_queue[del_idx]


    def display_joystick_inputs(self):
        x, y = None, None
        past_joy = [(i,s) for i,s in enumerate(self.joystick_inputs)
                    if float(s['scenario_time']) <= self.scenario_time]

        if len(past_joy) > 0 :
            states_idx_to_del = [s[0] for s in past_joy]    # All past states will be removed from 
            display_idx = list()
            for adr in set([s[1]['address'] for s in past_joy]):  # Browse each category
                cat_joy = [s for s in past_joy if s[1]['address'] == adr]
                display_idx.append(max([s[0] for s in cat_joy]))

            for this_disp_idx in display_idx:
                joy_input = past_joy[this_disp_idx][1]

                # X case
                if '_x' in joy_input['address']:
                    x = joy_input['value']
                elif '_y' in joy_input['address']:
                    y = joy_input['value']
            
                if x is not None and y is not None:
                    rel_x, rel_y = self.replay_reticle.proportional_to_relative((x,y))
                    self.replay_reticle.set_cursor_position(rel_x, rel_y)



    # def get_event_at_scenario_time(self, scenario_time: float):
    #     if self.replay_mode and scenario_time > self.target_time:
    #            self.scenario_clock.pause('replay')
    #            return self.unqueue_event()
    # +++
    # In replay filter events that are under the target time limit
        # events_time = [event for event in events_time
        #                if not self.replay_mode or event.time_sec <= self.target_time]

    # def move_scenario_time_to(self, time: float):
    #     if time < self.scenario_clock.get_time():
    #         # moving backward, we need to reset plugins, done events and restart from zero
    #         for plugin in self.plugins:
    #             self.plugins[plugin].stop(0)

    #         for event in self.events:
    #             event.done = False

    #         self.initialize_plugins()

    #         self.scenario_clock.set_time(0)


    #     # moving forward
    #     replay_acceleration_factor = 100

    #     self.target_time = time
    #     self.scenario_clock.set_speed(10.1)
    #     self.scenario_clock.resume('replay')
    #     self.clock.set_speed(replay_acceleration_factor)


    # def play_scenario(self, target_time):
    #     self.clock.set_speed(5)
    #     self.scenario_clock.set_speed(5)
    #     self.scenario_clock.resume('replay')
    #     self.target_time = target_time


    # def stop_scenario(self):
    #     # TODO: check if remaining events
    #     self.scenario_clock.pause('replay')
