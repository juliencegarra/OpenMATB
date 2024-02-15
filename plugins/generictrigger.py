# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from plugins.abstract import AbstractPlugin
from core.constants import PATHS as P
from core.logger import logger
from core.error import errors
import sys
from core import validation

class Generictrigger(AbstractPlugin):
    def __init__(self, taskplacement='invisible', taskupdatetime=5):
        super().__init__(taskplacement, taskupdatetime)

        self.validation_dict =  { 'state': validation.is_string }

        self._last_trigger = ""
        self.parameters.update({
            'state': self._last_trigger,
        })



