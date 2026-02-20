# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any

from core.pygaze_pyglet.pygaze import eyetracker
from core.window import Window
from plugins.abstractplugin import AbstractPlugin


class Eyetracker(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 10) -> None:
        super().__init__(_("Eye tracker"), taskplacement, taskupdatetime)

        new_par: dict[str, str] = {
            # ~ 'paintGaze': False,
            "trackertype": "dummy",
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
        self.tracker: Any | None = None

    def start(self, dt: float) -> None:
        super().start()
        self.tracker = eyetracker.EyeTracker(
            display=Window.MainWindow._display, trackertype=self.parameters["trackertype"]
        )
        self.tracker.calibrate()
        self.tracker.start_recording()
