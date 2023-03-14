# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from random import choice, sample
from core import Container, COLORS as C
from core.widgets import Scale, Light
from plugins.abstract import AbstractPlugin

class Sysmon(AbstractPlugin):
    def __init__(self, window, taskplacement='topleft', taskupdatetime=200):
        super().__init__(window, taskplacement, taskupdatetime)

        new_par = dict(alerttimeout=10000, automaticsolver=False, automaticsolverdelay=1000,
                       displayautomationstate=True, allowanykey=False, feedbackduration=1500,

                       feedbacks=dict(positive=dict(active=True, color=C['GREEN']),
                                      negative=dict(active=True, color=C['RED'])),

                       lights=dict([('1', dict(name='F5', failure=False, default='on',
                                     oncolor=C['GREEN'], key='F5', on=True)),
                                    ('2', dict(name='F6', failure=False, default='off',
                                     oncolor=C['RED'], key='F6', on=False))]),

                       scales=dict([('1', dict(name='F1', failure=False, side=0, key='F1')),
                                    ('2', dict(name='F2', failure=False, side=0, key='F2')),
                                    ('3', dict(name='F3', failure=False, side=0, key='F3')),
                                    ('4', dict(name='F4', failure=False, side=0, key='F4'))])
                       )

        self.parameters.update(new_par)

        # Add private parameters
        # to any gauge
        for gauge in self.get_all_gauges():
            gauge.update({'_failuretimer':None, '_onfailure':False, '_milliresponsetime':0,
                          '_freezetimer':None})

        # and to scale only
        for gauge in self.get_scale_gauges():
            gauge.update({'_pos':5, '_zone':0, '_feedbacktimer':None, '_feedbacktype':None})

        self.automode_position = (0.5, 0.05)
        self.scale_zones = {1: list(range(3)), 0: list(range(3, 8)), -1: list(range(8, 11))}


    def get_response_timers(self):
        return [g['_milliresponsetime'] for g in self.get_all_gauges()]


    def create_widgets(self):
        super().create_widgets()
        # Widgets coordinates (the left l coordinate is variable)
        scale_w = self.task_container.w * 0.1
        scale_b = self.task_container.b + self.task_container.h * 0.15
        scale_h = self.task_container.h * 0.5

        light_w = self.task_container.w * 0.4
        light_b = self.task_container.b + self.task_container.h * 0.75
        light_h = self.task_container.h * 0.15

        for scale_n, scale in self.parameters['scales'].items():
            scale_l = self.task_container.l + (self.task_container.w / 4) * (int(scale_n) - 1) + \
                      self.task_container.w/8 - scale_w/2
            scale_container = Container(f'scale_{scale_n}', scale_l, scale_b, scale_w, scale_h)

            scale['widget'] = self.add_widget(f"scale{str(scale_n)}", Scale,
                                             container=scale_container,
                                             label=scale['name'],
                                             arrow_position=scale['_pos'])

        for light_n, light in self.parameters['lights'].items():
            light_l = self.task_container.l + (self.task_container.w/2) * (int(light_n)-1) + \
                      self.task_container.w/4 - light_w/2
            light_container = Container(f'light_{light_n}', light_l, light_b, light_w, light_h)

            light['widget'] = self.add_widget(f'light{str(light_n)}', Light,
                                             container=light_container,
                                             label=light['name'],
                                             color=self.determine_light_color(light))


    def compute_next_plugin_state(self):
        if super().compute_next_plugin_state() == 0:
            return

        # For the gauges that are on failure
        for gauge in self.get_gauges_on_failure():
            # Decrement their failure timer / increment their response time
            gauge['_failuretimer'] -= self.parameters['taskupdatetime']
            gauge['_milliresponsetime'] += self.parameters['taskupdatetime']

            # If the failure timer has ended by itself, stop failure and trigger a negative feedback
            # if possible (scale gauges)
            if gauge['_failuretimer'] <= 0:
                self.stop_failure(gauge, success=False)

        for gauge in self.get_scale_gauges():
            if gauge['_feedbacktimer'] is not None:
                gauge['_feedbacktimer'] -= self.parameters['taskupdatetime']
                if gauge['_feedbacktimer'] <= 0:
                    gauge['_feedbacktimer'] = None
                    gauge['_feedbacktype'] = None


        # Compute arrows next position
        for scale_n, scale in self.parameters['scales'].items():
            if scale['_pos'] not in self.scale_zones[scale['_zone']]:
                scale['_pos'] = sample(self.scale_zones[scale['_zone']], 1)[0]
            else:
                direction = sample([-1, 1], 1)[0]
                if scale['_pos'] + direction in self.scale_zones[scale['_zone']]:
                    scale['_pos'] += direction
                else:
                    scale['_pos'] -= direction

            # If the gauge freeze timer is not null, freeze its arrow (pos = )
            if scale['_freezetimer'] is not None and isinstance(scale['_freezetimer'], int):
                scale['_freezetimer'] -= self.parameters['taskupdatetime']
                if scale['_freezetimer'] > 0:
                    # Here, freeze position
                    scale['_pos'] = 5  # TODO: Check central scale value
                else:
                    scale['_freezetimer'] = None


        # Check for failure
        for gauge in self.get_gauges_key_value('failure', True):
            self.start_failure(gauge)


    def refresh_widgets(self):
        if super().refresh_widgets() == 0:
            return
        for scale_n, scale in self.parameters['scales'].items():
            scale['widget'].set_arrow_position(scale['_pos'])

            if scale['_feedbacktimer'] is not None:
                color = self.parameters['feedbacks'][scale['_feedbacktype']]['color']
                scale['widget'].set_feedback_color(color)
                scale['widget'].set_feedback_visibility(True)

            # Feedback timer is over and the feedback is yet visible
            # Hide the feedback
            else:
                scale['widget'].set_feedback_visibility(False)

        for light_n, light in self.parameters['lights'].items():
            light['widget'].set_color(self.determine_light_color(light))

        for gauge in self.get_all_gauges():
            gauge['widget'].set_label(gauge['name'])


    def determine_light_color(self, light):
        color = light['oncolor'] if light['on'] == True else C['BACKGROUND']
        return color


    def start_failure(self, gauge):
        if gauge['_onfailure'] == True:
            pass  # TODO : warn in case of multiple failure on the same gauge
        else:
            gauge['_onfailure'] = True
            if 'default' in gauge.keys():  # Light case
                gauge['on'] = not gauge['default'] == 'on'
            else:  # Scale case
                if gauge['side'] not in [-1, 1]:
                    gauge['side'] = choice([-1, 1])
                gauge['_zone'] = gauge['side']
        gauge['failure'] = False

        # Schedule failure timing
        delay = self.parameters['automaticsolverdelay'] if self.parameters['automaticsolver'] \
            else self.parameters['alerttimeout']
        gauge['_failuretimer'] = delay


    def stop_failure(self, gauge, success=False):
        # Reset the gauge failure timer
        gauge['_onfailure'] = False
        gauge['_failuretimer'] = None

        # Set the (potential) feedback type (ft)
        ft = 'positive' if self.parameters['automaticsolver'] or success == True else 'negative'

        # Does this feedback type (positive or negative) is currently active ?
        # If so, set the feedback type and duration, if the gauge has got one
        # (the feedback widget is refreshed by the refresh_widget method)
        if self.parameters['feedbacks'][ft]['active'] and '_feedbacktimer' in gauge:
            self.set_scale_feedback(gauge, ft)

        # Feed the freeze timer with feedback duration (1.5 by default) if the response is good
        if success:
            gauge['_freezetimer'] = self.parameters['feedbackduration']

        # IDEA: do we need to distinguish manual detection (hit) from automatic detection ?
        # Evaluate performance in terms of signal detection and response time
        if ft == 'positive':
            sdt_string, rt = 'HIT', gauge['_milliresponsetime']
        else:
            sdt_string, rt = 'MISS', float('nan')
        sdt_string = 'HIT' if ft == 'positive' else 'MISS'

        self.log_performance('name', gauge['name'])
        self.log_performance('signal_detection', sdt_string)
        self.log_performance('response_time', rt)

        # Reset gauge to its nominal (default) state
        if 'default' in gauge.keys():  # Light case
            gauge['on'] = gauge['default'] == 'on'
        else:  # Scale case
            gauge['_zone'] = 0
        gauge['_milliresponsetime'] = 0


    def get_gauges_key_value(self, key, value):
        gauge_list = list()
        for gauge in self.get_all_gauges():
            if gauge[key] == value:
                gauge_list.append(gauge)
        return gauge_list


    def get_gauge_by_key(self, key):
        return self.get_gauges_key_value('key', key)[0]


    def get_gauges_on_failure(self):
        return self.get_gauges_key_value('_onfailure', True)


    def get_scale_gauges(self):
        return [g for _,g in self.parameters['scales'].items()]


    def get_light_gauges(self):
        return [g for _,g in self.parameters['lights'].items()]


    def get_all_gauges(self):
        return [g for g in self.get_scale_gauges() + self.get_light_gauges()]


    def set_scale_feedback(self, gauge, feedback_type):
        # Set the feedback type and duration, if the gauge has got one
        # (the feedback widget is refreshed by the refresh_widget method)
        gauge['_feedbacktype'] = feedback_type
        gauge['_feedbacktimer'] = self.parameters['feedbackduration']


    def do_on_key(self, key, state):
        super().do_on_key(key, state)
        if key is None:
            return

        if state == 'press':
            gauge = self.get_gauge_by_key(key)
            if key in [g['key'] for g in self.get_gauges_on_failure()]:
                self.stop_failure(gauge=gauge, success=True)
            else:
                self.log_performance('name', gauge['name'])
                self.log_performance('signal_detection', 'FA')
                self.log_performance('response_time', float('nan'))

                # Set a negative feedback if relevant
                if self.parameters['feedbacks']['negative']['active']:
                    self.set_scale_feedback(gauge, 'negative')
