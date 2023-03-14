# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import pyglet.clock

class Clock(pyglet.clock.Clock):
    """
    A special implementation of the pyglet Clock whose speed can be changed.
    """
    _time: float = 0.0
    default_speed: float = 1.0
    speed: float = default_speed
    pause_sources = {}

    def __init__(self, speed: float, name: str):
        self.name = name

        pyglet.clock.Clock.__init__(self, time_function=self.get_time)
        self.default_speed = float(speed)
        self.speed = self.default_speed

        pyglet.clock.schedule(self.advance)
        self.on_time_changed = None


    def advance(self, time: float):
        self.set_time(self._time + (time * self.speed))
        self.tick()


    def get_time(self) -> float:
        return self._time


    # set time in scenario_time for replay
    def set_time(self, time: float):
        self._time = time

        if self.on_time_changed != None:
            self.on_time_changed(self._time)


    def set_speed(self, speed: float):
        self.speed = speed


    def pause(self, key:str):
        self.pause_sources[key] = True
        self.set_speed(0.0)


    def resume(self, key:str):
        # resume if we not longer have a pause in progress
        if not self.is_playing(None):
            self.set_speed(self.default_speed)
        self.pause_sources[key] = False


    def is_playing(self, ignore: str) -> bool:
        # is there any pause still in progress?
        for key in self.pause_sources:
            if self.pause_sources[key] == True and key != ignore:
                return False
        return True
