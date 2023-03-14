# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from collections import namedtuple
from time import perf_counter
from datetime import datetime
from csv import DictWriter
from core.constants import PATHS

class Logger:
    def __init__(self):
        self.datetime = datetime.now()
        self.fields_list = ['logtime', 'scenariotime', 'type', 'module', 'address', 'value']
        self.slot = namedtuple('Row', self.fields_list)
        self.maxfloats = 6  # Time logged at microsecond precision
        self.session_id = None
        self.lsl = None

        # At instanciation, the logger should automatically compute the session number
        # The current session number is the lowest integer available in the whole session directory
        try:
            session_numbers = [int(s.name.split('_')[0]) 
                               for s in PATHS['SESSIONS'].glob('**/*.csv')]
        except:
            session_numbers = [0]
        # Take max session number + 1, and find the minimum available number into [1, max+1]
        # If no session has been manually removed, it will be max+1
        if len(session_numbers) == 0:
            session_numbers = [0]

        for n in range(1, max(session_numbers)+2):
            if self.session_id is None and n not in session_numbers:
                self.session_id = n

        self.path = PATHS['SESSIONS'].joinpath(self.datetime.strftime("%d-%m-%Y"),
                                f'{self.session_id}_{self.datetime.strftime("%y%m%d_%H%M%S")}.csv')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.mode = 'w'

        self.scenariotime = 0  # Updated by the scheduler class

        self.file = None
        self.writer = None
        self.queue = list()
        self.open()


    # TODO: see if we can/should merge record_* methods into one
    def record_event(self, event):
        if len(event.command) == 1:
            adress = 'self'
            value = event.command[0]
        elif len(event.command) == 2:
            adress = event.command[0]
            value = event.command[1]
        slot = [perf_counter(), self.scenariotime, 'event', event.plugin, adress, value]
        self.write_single_slot(slot)


    def record_input(self, module, key, state):
        slot = [perf_counter(), self.scenariotime, 'input', module, key, state]
        self.write_single_slot(slot)


    def record_aoi(self, container, name):
        plugin = name.split('_')[0]
        widget = '_'.join(name.split('_')[1:])
        slot = [perf_counter(), self.scenariotime, 'aoi', plugin, widget, container.get_x1y1x2y2()]
        self.write_single_slot(slot)


    def record_state(self, graph_name, attribute, value):
        module = graph_name.split('_')[0]
        graph_name = '_'.join(graph_name.split('_')[1:])
        address = f'{graph_name}, {attribute}'
        slot = [perf_counter(), self.scenariotime, 'state', module, address, value]
        self.write_single_slot(slot)


    def log_performance(self, module, metric, value):
        slot = [perf_counter(), self.scenariotime, 'performance', module, metric, value]
        self.write_single_slot(slot)


    def log_manual_entry(self, entry, key='manual'):
        slot = [perf_counter(), self.scenariotime, key, '', '', entry]
        self.write_single_slot(slot)


    def __enter__(self):
        self.open()
        return self


    def __exit__(self, type, value, traceback):
        self.file.close()


    def open(self):
        create_header = False if self.path.exists() and self.mode == 'a' else True
        self.file = open(str(self.path), self.mode, newline = '')
        self.writer = DictWriter(self.file, fieldnames=self.fields_list)
        if create_header:
            self.writer.writeheader()


    def close(self):
        self.file.close()


    def add_row_to_queue(self, row):
        self.queue.append(row)


    def empty_queue(self):
        self.queue = list()


    def round_row(self, row):
        new_list = list()
        for col in row:
            new_value = round(col, self.maxfloats) if isinstance(col, float) or isinstance(col, int) else col
            new_list.append(new_value)
        return self.slot(*new_list)


    def write_row_queue(self, change_dict=None):
        if len(self.queue) == 0:
            print(_('Warning, queue is empty'))
        else:
            for this_row in self.queue:
                row_dict = self.round_row(this_row)._asdict()
                if change_dict is not None:
                    for k,v in change_dict.items():
                        row_dict[k] = v
                self.writer.writerow(row_dict)
                if self.lsl is not None:
                    self.lsl.push(';'.join([str(r) for r in row_dict.values()]))
            self.empty_queue()


    def write_single_slot(self, values):
        row = self.slot(*values)
        self.add_row_to_queue(row)
        self.write_row_queue()


    def set_totaltime(self, totaltime):
        self.totaltime = totaltime


    def set_scenariotime(self, scenariotime):
        self.scenariotime = scenariotime
        

logger = Logger()
