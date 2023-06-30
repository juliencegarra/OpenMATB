# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import csv, sys
from pathlib import Path
from core.constants import PATHS as P
from core.error import errors
from core.scenario import Event, Scenario
from core.utils import find_the_last_session_number

# Some plugins must not be replayed for now
IGNORE_PLUGINS = ['labstreaminglayer', 'parallelport', 'genericscales', 'instructions']

class LogReader:
    '''
    The log reader takes a session file as input and is able to return its entries depending on
    their onset time. Relevant entries are scenario events and user inputs, which are combined to
    simulate what happened during the session.
    '''
    def __init__(self):
        events, self.inputs, self.states, self.duration_sec,  = [], [], [], 0
        self.start_sec, self.end_sec = 0, 0
        self.line_n = 0

        if len(sys.argv) > 2:
            replay_session_id = int(sys.argv[2])
        else:
            replay_session_id = find_the_last_session_number()
    

        # Check if the desired session file exists. If so, load and parse it.
        session_file_list = [f for f in P['SESSIONS'].glob(f'**/{replay_session_id}_*.csv')]

        if len(session_file_list) == 0:
            errors.add_error(_('The desired session file (ID=%s) does not exist') % replay_session_id,
                             fatal=True)
        elif len(session_file_list) > 1:
            errors.add_error(_('Multiple session files match the desired session ID (%s)') % replay_session_id,
                             fatal=True)

        # Correct case when only one session file is identified
        elif len(session_file_list) == 1:
            session_file_path = session_file_list[0]
            with open(session_file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                first_row = next(reader)
                for row in reader:
                    # Define what type of entry must be retrieved for replaying
                    if not row['module'] in IGNORE_PLUGINS:
                        row['logtime'] = float(row['logtime'])

                        # Event case
                        if row['type'] == 'event':
                            events.append(self.session_event_to_str(row))

                        # Input case
                        elif row['type'] == 'input':
                            self.inputs.append(row)

                        # State case
                        elif row['type'] == 'state':
                            
                            # Record communications radio frequencies
                            # AND track cursor positions
                            if ('radio_frequency' in row['address']
                                    or 'cursor_proportional' in row['address']
                                    or 'slider_' in row['address']):
                                row['value'] = eval(row['value'])
                                self.states.append(row)

                # The last row browsed contains the ending time
                self.end_sec = float(row['scenario_time'])
                self.duration_sec = self.end_sec - self.start_sec

        self.scenario = Scenario(events)


    def session_event_to_str(self, event_row):
        time_sec = int(float(event_row['scenario_time']))
        plugin = event_row['module']
        if event_row['address'] == 'self':
            command = event_row['value']
        else:
            command = ';'.join([event_row['address'], event_row['value']])

        event = Event(self.line_n, time_sec, plugin, command)
        self.line_n += 1
        return event.get_line_str()