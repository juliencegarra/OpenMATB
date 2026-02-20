# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import pyglet.clock


class Clock(pyglet.clock.Clock):
    """
    A special implementation of the pyglet Clock allowing speed changes.
    """

    _time: float = 0.0
    _speed: int = 1

    def __init__(self, name: str) -> None:
        self.name: str = name

        pyglet.clock.Clock.__init__(self, time_function=self.get_time)
        pyglet.clock.schedule(self.advance)

        # necessary variable as an unschedule then schedule seems to produce unexpected crashes
        self.isFastForward: bool = False

    def advance(self, dt: float) -> None:
        if self.isFastForward:
            return

        for _i in range(0, self._speed):
            self.set_time(self._time + dt)

            self.tick()

    def get_time(self) -> float:
        return self._time

    def increase_speed(self) -> None:
        self._speed += 1
        if self._speed > 10:
            self._speed = 10

    def decrease_speed(self) -> None:
        self._speed -= 1
        if self._speed < 1:
            self._speed = 1

    def reset_speed(self) -> None:
        self._speed = 1

    # set time in scenario_time for replay
    def set_time(self, time: float) -> None:
        self._time = time

    def fastforward_time(self, target_time: float) -> None:
        # loop on advance() like method to tick the replayscheduler/scheduler update()
        self.isFastForward = True

        while target_time > 0:
            dt: float = min(target_time, 0.1)

            self.set_time(self.get_time() + dt)
            self.tick()

            target_time -= dt

        self.isFastForward = False
