# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from time import strftime, gmtime
from core.widgets import Timeline, Schedule, Simpletext
from plugins.abstract import AbstractPlugin
from core.constants import COLORS as C
from core import Container


class Scheduling(AbstractPlugin):
    def __init__(self, window, taskplacement='topright', taskupdatetime=1000):
        super().__init__(window, taskplacement, taskupdatetime)

        self.parameters.update(dict(minduration=8, displaychronometer=True, reversechronometer=False,
                                    displayedplugins=['sysmon', 'track', 'communications', 'resman']))

        for i, p in enumerate(self.parameters['displayedplugins']):
            self.parameters['displayedplugins'][i] = _(self.parameters['displayedplugins'][i])

        # Planning of events is set by the scheduler [set_planning(events)] because it needs
        # to know events
        self.planning = {p:{'running':list(), 'manual':list()}
                         for p in self.parameters['displayedplugins']}
        self.colors = dict(line=C['GREY'], running=C['RED'], manual=C['GREEN'])
        self.maximum_time_sec = None


    def create_widgets(self):
        super().create_widgets()

        timeline_container = Container('timeline',
                                       self.task_container.l + self.task_container.w * 0.1,
                                       self.task_container.b + self.task_container.h * 0.20,
                                       self.task_container.w * 0.17, self.task_container.h * 0.7)

        self.add_widget('timeline', Timeline, container=timeline_container,
                       max_time_minute=self.parameters['minduration'])

        self.add_widget('elapsed_time', Simpletext, container=self.task_container,
                       text=self.get_chrono_str(), y=0.05)

        for p, name in enumerate(self.planning.keys()):
            planning_container = Container(f'schedule_{name}',
                                           self.task_container.l + self.task_container.w * (0.15 + 0.15 * (p+1)),
                                           self.task_container.b + self.task_container.h * 0.20,
                                           self.task_container.w * 0.17,
                                           self.task_container.h * 0.7)

            self.add_widget(name, Schedule, container=planning_container, label=name)


    def refresh_widgets(self):
        if super().refresh_widgets() == 0:
            return
        # This plugin can not be paused for now.
        # When visible, it is just synchronized with the elapsed time
        self.widgets['scheduling_timeline'].set_max_time(self.parameters['minduration'])
        self.widgets[f'{self.alias}_elapsed_time'].set_text(self.get_chrono_str())
        self.update_relative_plannings()


    def update_relative_plannings(self):
        # For each displayed plugin, and each mode, send the relative time points to the widget
        # Time points are relative to the elapsed time and the maximum displayed duration (minutes)

        self.relative_planning = {p:{'running':list(), 'manual':list()}
                                     for p in self.parameters['displayedplugins']}


        for plugin_name in self.planning.keys():
            wdgt_adress = f'{self.alias}_{plugin_name}'
            if plugin_name in self.parameters['displayedplugins']:

                # See if we should show the plugin timeline
                self.widgets[wdgt_adress].show()

                for time_mode, abs_time_pts in self.planning[plugin_name].items():
                    bound_color = self.colors['line']
                    rel = self.relative_planning[plugin_name][time_mode]
                    # Limit the time interval with relative 0 and displayed duration (minutes)
                    max_sec = self.parameters['minduration'] * 60

                    # For each time pair (start, end)
                    for start, end in self.grouped(abs_time_pts, 2):

                        # Set the color of the top bound for each displayed plugin
                        if start <= self.get_elapsed_time_sec() < end:
                            if time_mode != 'running':
                                self.widgets[wdgt_adress].set_top_bound_color(self.colors[time_mode])

                        # Take elapsed time into account
                        rel.append([start-self.get_elapsed_time_sec(),
                                    end-self.get_elapsed_time_sec()])
                        rel_pair = rel[-1]


                        rel_pair[0] = 0 if rel_pair[0] < 0 else rel_pair[0]                # start
                        rel_pair[1] = max_sec if rel_pair[1] > max_sec else rel_pair[1]    # end

                        # If a segment has expired (end < 0), do not map the segment
                        if rel_pair[1] < 0:
                            del self.relative_planning[plugin_name][time_mode][-1]

                    color = self.colors[time_mode]
                    rel_plan = self.relative_planning[plugin_name][time_mode]
                    self.widgets[wdgt_adress].map_segment(time_mode, rel_plan, max_sec, color)

            # See if we should hide the plugin timeline
            else:
                self.widgets[wdgt_adress].hide()


    def get_chrono_str(self):
        if self.parameters['displaychronometer']:
            if self.parameters['reversechronometer']:
                return self.get_remaining_time_string()
            else:
                return self.get_elapsed_time_string()
        else:
            return ''


    def get_elapsed_time_sec(self):
        return int(self.scenariotime)


    def get_elapsed_time_string(self):
        str_time = strftime('%H:%M:%S', gmtime(self.get_elapsed_time_sec()))
        return _('Elapsed time \t %s') % str_time


    def get_remaining_time_sec(self):
        return int(self.maximum_time_sec) - int(self.scenariotime)


    def get_remaining_time_string(self):
        str_time = strftime('%H:%M:%S', gmtime(self.get_remaining_time_sec()))
        return _('Remaining time \t %s') % str_time


    def set_planning(self, events):  # Executed by the scheduler
        # TODO: Remove redundant events (stop -> stop), keep the earliest.
        start_stop_labels = ['start', 'stop', 'resume', 'pause']
        auto_labels = ['automaticsolver']
        
        # Retrieve last event time_sec for reversed chronometer
        self.maximum_time_sec = events[-1].time_sec

        start_time_sec = [e.time_sec for e in events if e.plugin == 'scheduling'
                         if 'start' in e.command[0]][0]

        # For each task...
        for task in self.planning.keys():
            # 1. ...compute running segments
            start_stop_events = [(e.time_sec, e.command[0]) for e in events if e.plugin == task
                           and e.command[0] in start_stop_labels]
            for event in start_stop_events:
                self.planning[task]['running'].append(event[0])
            if len(self.planning[task]['running']) % 2 == 1:
                del(self.planning[task]['running'][-1])

            # 2. ...compute manual segments
            auto_events = [(e.time_sec, e.command[1]) for e in events if e.plugin == task
                           and e.command[0] in auto_labels]

            # If some automation events are specified, compute manual segments accordingly
            if len(auto_events) > 0:
                while auto_events[0][1] is False:  # Be sure to begin with an (automaticsolver, True)
                    del(auto_events[0])

                stop_time = [e[0] for e in start_stop_events if e[1] == 'stop'][0]
                start_time = [e[0] for e in start_stop_events if e[1] == 'start'][0]

                self.planning[task]['manual'].append(start_time)
                for ae in auto_events:
                    self.planning[task]['manual'].append(ae[0])
                if len(self.planning[task]['manual']) % 2 == 1:
                    self.planning[task]['manual'].append(stop_time)

            # Else, running segments are all manual segments
            else:
                self.planning[task]['manual'] = self.planning[task]['running']
