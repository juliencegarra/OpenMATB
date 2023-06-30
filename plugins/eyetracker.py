# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.pygaze_pyglet.pygaze import eyetracker
from plugins import AbstractPlugin
from core.window import Window

class Eyetracker(AbstractPlugin):
    def __init__(self, taskplacement='invisible', taskupdatetime=10):
        super().__init__(taskplacement, taskupdatetime)
        
        new_par = {
                   # ~ 'paintGaze': False,
                   'trackertype': 'dummy',
                   # ~ 'smiip': "192.168.1.35",
                   # ~ 'smisendport': 4444,
                   # ~ 'smireceiveport': 5555,
                   # ~ 'connectmaxtries': 10,
                   # ~ 'maxcalibrations':  5,
                   # ~ 'mousevisible': True,
                   # ~ 'backgroundcolor': (125, 125, 125, 255),
                   # ~ 'foregroundcolor': (0, 0, 0, 255),
                   # ~ 'getFromSample': ['gazeLX', 'gazeLY', 'positionLX', 'positionLY', 'positionLZ',
                                     # ~ 'diamL', 'gazeRX', 'gazeRY', 'positionRX', 'positionRY', 
                                     # ~ 'positionRZ', 'diamR']
                   }
        self.parameters.update(new_par)
        self.tracker = None
    
    def start(self, dt):
        super().start(0)
        self.tracker = eyetracker.EyeTracker(display = self.win._display,
                                             trackertype = self.parameters['trackertype'])
        self.tracker.calibrate()
        self.tracker.start_recording()
