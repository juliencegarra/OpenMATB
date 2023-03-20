# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from math import sin, pi, ceil
from pyglet.input import get_joysticks
from plugins.abstract import AbstractPlugin
from core.widgets import Reticle
from core.error import errors
from core.container import Container
from core.constants import Group as G, COLORS as C, FONT_SIZES as F


class Track(AbstractPlugin):
    def __init__(self, window, taskplacement='topmid', taskupdatetime=20, silent=False):
        super().__init__(window, taskplacement, taskupdatetime)

        new_par = dict(cursorcolor=C['BLACK'], cursorcoloroutside=C['RED'], automaticsolver=False,
                       displayautomationstate=True, targetproportion=0.25, joystickforce=1,
                       inverseaxis=False)
        self.parameters.update(new_par)


        self.automode_position = (0.35, 0.1)
        self.cursor_path_gen = iter(self.compute_next_cursor_position())
        self.cursor_position = None
        self.cursor_color_key = 'cursorcolor'
        self.gain_ratio = 0.8  # The proportion of the reticle area the cursor should cover
        self.response_time = 0
        self.joystick = None
        self.silent = silent

        if not self.win.replay_mode:
            joysticks = get_joysticks()
            if len(joysticks) > 0:
                self.joystick = joysticks[0]
                self.joystick.open()
            else:
                self.joystick = None
                if self.silent == False:
                    errors.add_error(_('No joystick found'))

        if self.joystick is not None:
            self.joystick.push_handlers(self.win)

    def get_response_timers(self):
        return [self.response_time]


    def create_widgets(self):
        super().create_widgets()

        # Compute the reticle widget coordinates (left, bottom, width, height)
        b = self.task_container.b + self.task_container.h * 0.1
        h = w = self.task_container.h*0.8
        l = self.task_container.l + self.task_container.w/2 - w/2

        self.add_widget('reticle', Reticle, container=Container('reticle', l, b, w, h),
                       target_proportion=self.parameters['targetproportion'],
                       cursorcolor=self.parameters['cursorcolor'])
        self.reticle = self.widgets['track_reticle']

        # Compute cursor movement constraints as soon as the reticle is created
        self.reticle_container = self.reticle.container
        self.xgain = (self.reticle_container.w * self.gain_ratio)/2
        self.ygain = (self.reticle_container.h * self.gain_ratio)/2
        self.cursor_position = next(self.cursor_path_gen)


    def compute_next_plugin_state(self):
        if super().compute_next_plugin_state() == 0:
            return
        self.cursor_position = next(self.cursor_path_gen)
        self.cursor_color_key = 'cursorcolor' if self.reticle.is_cursor_in_target() \
                    else 'cursorcoloroutside'
        self.log_performance('cursor_in_target', self.reticle.is_cursor_in_target())
        self.log_performance('center_deviation', self.reticle.return_deviation())

        if not self.reticle.is_cursor_in_target():  # A response is needed
            self.response_time += self.parameters['taskupdatetime']
        else:
            if self.response_time > 0:  # The cursor drift has been recovered
                self.log_performance('response_time', self.response_time)
                self.response_time = 0


    def refresh_widgets(self):
        if super().refresh_widgets() == 0:
            return
        self.reticle.set_cursor_position(*self.cursor_position)
        self.reticle.set_cursor_color(self.parameters[self.cursor_color_key])
        self.reticle.set_target_proportion(self.parameters['targetproportion'])


    def compute_next_cursor_position(self):
        # Adapted from Comstock et al., (1992) : the first MATB documentation
        xsin, ysin = 0, 0
        xincr, yincr = 0.005, 0.006  # Cursor (x, y) asynchroneous speeds

        cursorx, cursory = 0, 0
        moffx, moffy = 0, 0

        while True:
            # Must wait the drawing of the reticle to evaluate x & y gain
            if f'{self.alias}_reticle' in self.widgets.keys():
                xsin = xsin + xincr if xsin < 2*pi else 0
                ysin = ysin + yincr if ysin < 2*pi else 0

                cursorx = sin(xsin) * self.xgain
                cursory = sin(ysin) * self.ygain

                compx, compy = 0, 0
                # Potential compensations of cursor movement
                # If the automode is enabled, apply automatic compensation to the cursor drift
                if self.parameters['automaticsolver'] == True:
                    compx = 1 if -self.reticle.cursor_relative[0] >= 0 else -1
                    compy = 1 if -self.reticle.cursor_relative[1] >= 0 else -1

                # Else if a manual input (joystick) is recorded, apply its offset to the cursor,
                # as a function of its gain
                elif self.joystick is not None:
                    if self.parameters['inverseaxis'] == False:
                        compx, compy = self.joystick.x, -self.joystick.y
                    else:
                        compx, compy = -self.joystick.x, self.joystick.y

                compx = compx * self.parameters['joystickforce']
                compy = compy * self.parameters['joystickforce']

                moffx = moffx + compx
                moffy = moffy + compy

                cursorx = cursorx + moffx
                cursory = cursory + moffy

                limitx = min(max(cursorx, -self.reticle.container.w/2), self.reticle.container.w/2)
                limity = min(max(cursory, -self.reticle.container.h/2), self.reticle.container.h/2)

                # If outside reticle limits, compensate cursor position
                # Neutralize the joystick only if it does not go toward the center
                if limitx != cursorx:
                    diff = cursorx-limitx
                    cursorx -= diff
                    if compx !=0 and diff/compx > 0:  # Same sign
                        moffx -= (diff + compx * self.parameters['joystickforce'])

                if limity != cursory:
                    diff = cursory-limity
                    cursory -= diff
                    if compy !=0 and diff/compy > 0:  # Same sign
                        moffy -= (diff + compy * self.parameters['joystickforce'])
                yield (cursorx, cursory)
            else:
                yield (0, 0)
