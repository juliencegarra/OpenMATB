# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)


#TODO:
#- eyetracker (from lsl?)
#- joystick display

#- To handle blocking plugins in replay we need to:
#  - use logtime and not scenariotime
#  - load logtime from logreader
#  - manage replay pause with logtime
#  - synchronize logtime and scenariotime (to manage all events)
#  - handle update() of scheduler (not replayscheduler) accordingly



from pyglet.window import key
from core.scheduler import Scheduler
from core.error import errors
from core.widgets import PlayPause, Simpletext, Slider, Frame, Reticle, SimpleHTML
from core.constants import COLORS as C, FONT_SIZES as F
from time import strftime, gmtime, sleep
from core.logreader import LogReader
from core.container import Container
from core.utils import get_conf_value, get_replay_session_id, clamp
from random import uniform
from core.window import Window

CLOCK_STEP = 0.1

class ReplayScheduler(Scheduler):
    """
    This class manages events execution in the context of the OpenMATB replay.
    """
    def __init__(self):
        self.logreader = None
        self.target_time = 0

        self.set_media_buttons()

        self.set_inputs_buttons()

        Window.MainWindow.on_key_press = self.on_key_press_replay

        # Init is done after UX is set
        super().__init__()

        self.is_paused = True
        square = shapes.Rectangle(x=200, y=200, width=200, height=200, color=(55, 55, 255))


    def set_scenario(self):
        replay_session_id = get_replay_session_id()

        if self.logreader is None or replay_session_id != self.logreader.replay_session_id:
            self.logreader = LogReader(replay_session_id)

##            self.inputs_queue = list(self.logreader.inputs)  # Copy inputs
##            self.keyboard_inputs = [i for i in self.inputs_queue if i['module'] == 'keyboard']
##            self.joystick_inputs = [i for i in self.inputs_queue if 'joystick' in i['address']]
##            self.states_queue = list(self.logreader.states)  # Copy states, //


        super().set_scenario(self.logreader.contents)

        self.sliding = False

        self.slider.value_max = self.logreader.duration_sec

        self.pause_scenario()


    def set_inputs_buttons(self):
        # Plot the keyboard keys that are available in the present plugins
        input_container = Window.MainWindow.get_container('inputstrip')
        key_container = input_container.reduce_and_translate(width=0.9,
                                                             height=0.8,
                                                             y=0, x=0.5)
        self.key_widget = SimpleHTML('replay_keys', key_container, '<strong>Keyboard history:\n</strong>')
        self.key_widget.show()


    def set_media_buttons(self):

        # Media strip
        media_container = Window.MainWindow.get_container('mediastrip')
        self.media_back = Frame('media_background', media_container,
                                fill_color=C['DARKGREY'], draw_order=1)
        self.media_back.show()
        pp_container = media_container.reduce_and_translate(width=0.06, height=1, x=0)
        time_container = media_container.reduce_and_translate(width=0.03, height=1, x=0.78)

        self.playpause = PlayPause('Play_pause_button', pp_container,
                                   self.toggle_playpause)
        self.time = Simpletext('elapsed_time', time_container,
                               text='', font_size=F['LARGE'], color=C['WHITE'])


        self.slider = Slider('timeline', media_container, None, '', '', 0, 1, 0, 1)
        self.time.show()

        # Inputs strip
        input_container = Window.MainWindow.get_container('inputstrip')
        self.inputs_back = Frame('inputs_background', input_container,
                                fill_color=C['LIGHTGREY'], draw_order=1)
        self.inputs_back.show()

        # Manually compute the joystick container to ensure it is a square
        w = h = input_container.w * 0.8
        l = input_container.l + 0.1*input_container.w
        b = input_container.b + 0.85*input_container.h
        joy_container = Container('replay_reticle', l,b,w,h)
        self.replay_reticle = Reticle('replay_reticle', joy_container, C['BLACK'],
                                      target_proportion = 0, m_draw=5)
        self.replay_reticle.show()


    def on_key_press_replay(self, symbol, modifier):
        if symbol==key.ESCAPE:
            Window.MainWindow.exit_prompt()
        elif symbol==key.SPACE:
            self.toggle_playpause()
        elif symbol==key.HOME:
            self.set_target_time(0)
        elif symbol==key.END:
            self.set_target_time(self.logreader.duration_sec)
        elif symbol==key.LEFT:
            self.set_target_time(self.scenario_time - 0.1)
        elif symbol==key.RIGHT:
            self.set_target_time(self.scenario_time + 0.1)
        elif symbol==key.UP:
            self.clock.increase_speed()
        elif symbol==key.DOWN:
            self.clock.decrease_speed()

    def update(self, dt):
        self.pause_if_end_reached()
        self.update_time_string()
        self.slider_control_update()

        if not self.is_paused:
            dt = min(dt, self.target_time - self.scenario_time)

            if dt > 0:
                super().update(dt) # updates the scenario_time
        else:
            # HACK: required as update is not called in pause
            # it would be better to update modaldialog to use a callback
            self.check_if_must_exit()

        # as update manage a queue we need to empty that queue first before
        # processing inputs and states
        if len(self.events_queue)>0:
            return

        self.emulate_keyboard_inputs()
        self.display_joystick_inputs()
        self.process_states()


        #self.pause_if_clock_target_reached()






    def check_plugins_alive(self):
        return all([p.alive for _, p in self.plugins.items()])


    def check_if_must_exit(self):
        # In replay mode, exit conditions are differents. Exit only if the Window is killed.
        if not Window.MainWindow.alive:
            self.exit()



    def update_time_string(self):
        time_str = self.get_time_hms_str()
        self.time.set_text(time_str)


    def get_time_hms_str(self):
        # round to prevent displaying time as 0.099 instead of 0.1
        timesec = round(self.scenario_time, 2)

        t = strftime('%H:%M:%S', gmtime(timesec))
        ms = timesec %1 * 1000

        return '%s.%03d' % (t, ms)


    def pause_if_end_reached(self):
        if self.scenario_time >= self.logreader.end_sec and not self.is_scenario_time_paused():
            self.pause_scenario()


    def pause_scenario(self):
        self.toggle_pause_to(True)


    def resume_scenario(self):
        self.toggle_pause_to(False)


    def toggle_playpause(self):
        self.toggle_pause_to(not self.is_paused)

        if not self.is_paused:
            self.target_time = self.logreader.end_sec
        else:
            self.target_time = self.scenario_time


    def toggle_pause_to(self, status):
        self.is_paused = status
        self.playpause.update_button_sprite(self.is_paused)

    def slider_control_update(self):
        # Update the position of the slider if scenario time changed
        if self.slider.groove_value != self.scenario_time and not self.sliding:
            self.slider.groove_value = self.scenario_time
            self.slider.set_groove_position()


        # At THE FIRST slider mouse press, pause scenario if not already paused
        if self.slider.hover == True and self.sliding == False:
            self.sliding = True
            self.toggle_pause_to(True)

        # At THE FIRST slider mouse release, get back the scenario in its previous state (play/pause)
        # Record the target value (given by the groove position)
        if self.slider.hover == False and self.sliding == True:
            self.sliding = False
            self.set_target_time(self.slider.groove_value)


    def pause_if_clock_target_reached(self):
        # Soon as the clock target is reached, control if the scenario must switch back to pause
        if self.clock.is_target_time_reached():
            self.clock.remove_target_time()
            self.pause_scenario()



    def set_target_time(self, target_time):
        # We are already changing time, do not reenter this method
        if self.clock.isFastForward:
            return

        # clamp desired time
        self.target_time = clamp(target_time, 0, self.logreader.duration_sec)

        # already on the right time
        if self.target_time == self.scenario_time:
            self.pause_scenario()
            return


        # backward in time, we reload everything, reset, and move forward
        if self.target_time < self.scenario_time:
            self.restart_scenario()
            self.scenario_time = 0

        forward_time = self.target_time - self.scenario_time

        # Resuming is required as we want the clock to update the scheduler
        if forward_time > 0:
            self.resume_scenario()
            self.clock.fastforward_time(forward_time)

        self.slider.set_groove_position()
        self.pause_scenario()


    def restart_scenario(self):
        # we need to suspend the clock as it schedules old events
        self.clock.unschedule(self.update)


        self.clock.set_time(0)
        self.clock.tick()
        self.scenario_time = 0
        self.slider.groove_value = 0
        self.slider.set_groove_position()
        self.scenario.reload_plugins()
        self.set_scenario()

        self.clock.schedule(self.update)


    def emulate_keyboard_inputs(self):
        self.keys_history = []

        for input in self.logreader.keyboard_inputs:
            # display actions from 0.5 secs before that time
            if float(input['scenario_time']) > self.scenario_time - (0.5) and float(input['scenario_time']) <= self.scenario_time:

                # execute actions if on time
                if float(input['scenario_time']) == self.scenario_time:
                    for plugin_name, plugin in self.plugins.items():
                        plugin.do_on_key(input['address'], input['value'], True)

                cmd = f"{input['address']} ({input['value']})"
                if len(self.keys_history) > 0 and cmd != self.keys_history[-1]:
                    self.keys_history.append(cmd)
                elif len(self.keys_history) == 0:
                    self.keys_history.append(cmd)

                if len(self.keys_history) > 30:
                    del self.keys_history[0]


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
        past_sta = [(i,s) for i,s in enumerate(self.logreader.states)
                    if float(s['scenario_time']) > self.scenario_time - CLOCK_STEP and float(s['scenario_time']) <= self.scenario_time]

        if len(past_sta) == 0:
            return

        for item in past_sta:
            state = item[1]

            # 1. Cursor position
            if 'cursor_proportional' in state['address'] and 'track' in self.plugins:
                cursor_relative = self.plugins['track'].reticle.proportional_to_relative(state['value'])
                self.plugins['track'].cursor_position = cursor_relative

            # 2. Radio frequencies
            elif 'radio_frequency' in state['address'] and 'communications' in self.plugins:
                radio_name = state['address'].replace(', radio_frequency', '').replace('radio_', '')
                radio = self.plugins['communications'].get_radios_by_key_value('name', radio_name)[0]
                radio['currentfreq'] = state['value']

            # 3. Genericscales slider values
            elif 'slider_' in state['address'] and 'genericscales' in self.plugins:
                slider_name = state['address'].replace(', value', '')
                slider = self.plugins['genericscales'].sliders[slider_name]
                slider.groove_value = state['value']


    def display_joystick_inputs(self):
        x, y = None, None
        past_joy = [(i,s) for i,s in enumerate(self.logreader.joystick_inputs)
                    if float(s['scenario_time']) > self.scenario_time - CLOCK_STEP and float(s['scenario_time']) <= self.scenario_time]


        for s in past_joy:
            joy_input = s[1]

            # X case
            if '_x' in joy_input['address']:
                x = float(joy_input['value'])
            elif '_y' in joy_input['address']:
                y = float(joy_input['value'])

        if x is not None and y is not None:
            rel_x, rel_y = self.replay_reticle.proportional_to_relative((x,y))
            self.replay_reticle.set_cursor_position(rel_x, rel_y)


