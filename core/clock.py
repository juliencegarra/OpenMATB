# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import pyglet.clock

class Clock(pyglet.clock.Clock):
    """
    A special implementation of the pyglet Clock whose speed can be changed.
    """
    _time: float = 0.0

    def __init__(self, name: str):
        self.name = name

        pyglet.clock.Clock.__init__(self, time_function=self.get_time)
        pyglet.clock.schedule(self.advance)
        self.target_time = None


    def advance(self, time: float):
        self.set_time(self._time + time)
        self.tick()
        if self.target_time is not None:
            if self.target_time >= self.get_time():
                self.advance(0.1)   # Recursion
            else:
                self.target_time = None


    def get_time(self) -> float:
        return self._time


    # set time in scenario_time for replay
    def set_time(self, time: float):
        self._time = time


    def set_target_time(self, target_time):
        if target_time < self.get_time():
            print('Warning. The clock was sent a bad target time (back in time)')
        self.target_time = target_time
        return self.target_time


    def is_target_defined(self):
        return self.target_time is not None


    def get_target_time(self):
        if self.is_target_defined():
            return self.target_time
        return


    def is_target_reached(self):
        if self.target_time is not None:
            if self.target_time <= self.get_time():
                return True
            else:
                return False
        else:
            return False