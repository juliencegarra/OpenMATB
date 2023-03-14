# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from plugins.abstract import AbstractPlugin
from core.constants import PATHS as P
from core.dialog import fatalerror
from core import logger

class Parallelport(AbstractPlugin):
    def __init__(self, window, taskplacement='invisible', taskupdatetime=5):
        super().__init__(window, taskplacement, taskupdatetime)

        try:
            import parallel
        except:
             #TODO: use a global alerterror() method
            print(_('Python Parallel module is missing. Skipping parallel plugin'))
            return

        try:
            self._port = parallel.Parallel()

        except:  # Exception under Linux platforms : FileNotFoundError (/dev/parport0)
            fatalerror(_('The physical parallel port was not found.'))

        else:

            self._downvalue = 0
            self.parameters.update({
                'trigger': self._downvalue,
                'delayms': 5
            })

            self._triggertimerms = 0
            self._last_trigger = self._downvalue
            self._awaiting_triggers = []


    def is_trigger_being_sent(self):
        '''Return if the last trigger value is not the down value (trigger being sent)'''
        return self._last_trigger != self._downvalue


    def set_trigger_value(self, value):
        self._port.setData(value)
        self._triggertimerms = 0
        logger.record_state(f'{self.alias}_trigger', 'value', value)
        self._last_trigger = value


    def compute_next_plugin_state(self):
        '''Send the trigger value defined in upvalue, lasting for delayms'''
        if super().compute_next_plugin_state() == 0:
            return

        # If the trigger value is not null...
        if self.parameters['trigger'] != self._downvalue:

            # ... and no trigger being sent: send it
            if self.is_trigger_being_sent() == False:
                self.set_trigger_value(self.parameters['trigger'])

            # but if a trigger is already being sent, store it
            else:
                self._awaiting_triggers.append(self.parameters['trigger'])

            # Finally, reset the input trigger
            self.parameters['trigger'] = self._downvalue

        # If it is null and some triggers are awaiting and no trigger is being sent
        elif len(self._awaiting_triggers) > 0 and not self.is_trigger_being_sent():
            self.set_trigger_value(self._awaiting_triggers[0])  # Make it current
            del self._awaiting_triggers[0]  # And delete it

        # If a trigger is currently defined...
        if self.is_trigger_being_sent() and self._triggertimerms >= self.parameters['delayms']:
            #... and the delayms has been reached: sent default value to parallel port
            self.set_trigger_value(self._downvalue)

        # Grow timer of not-null trigger
        if self.is_trigger_being_sent() == True:
            self._triggertimerms += self.parameters['taskupdatetime']
