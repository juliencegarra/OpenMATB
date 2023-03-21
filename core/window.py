# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from pyglet import font
from pyglet.canvas import get_display
from pyglet.window import Window, key as winkey
from pyglet.graphics import Batch
from pyglet.gl import GL_POLYGON
from pyglet.text import Label
from core.container import Container
from core.constants import COLORS as C, FONT_SIZES as F, Group as G, PLUGIN_TITLE_HEIGHT_PROPORTION
from core.modaldialog import ModalDialog
from core.logger import logger
from core.error import errors
import os



class Window(Window):
    def __init__(self, screen_index, font_name, fullscreen, replay_mode, highlight_aoi, hide_on_pause,
                 *args, **kwargs):

        errors.win = self

        # Screen definition #
        try:
            screen_index = int(screen_index)
        except:
            screen_index = 0

        screens = get_display().get_screens()
        if screen_index + 1 > len(screens):
            screen = screens[-1]
            errors.add_error(_(f"In config.ini, the specified screen index exceeds the number of available screens (%s). Last screen selected.") % len(get_display().get_screens()))
        else:
            screen = screens[screen_index]


        # Font definition
        # Font check
        if len(font_name) == 0:
            self.font_name = None
        elif not font.have_font(font_name):
            errors.add_error(_(f"In config.ini, the specified font is not available. A default font will be used."))
            self.font_name = None
        else:
            self.font_name = font_name


        if replay_mode:
            self._width=int(screen.width / 1.2)
            self._height=int(screen.height / 1.2)
        else:
            self._width=screen.width
            self._height=screen.height

        self._fullscreen=fullscreen

        super().__init__(fullscreen=self._fullscreen, width=self._width, height=self._height, vsync=True, *args, **kwargs)

        self.set_size_and_location() # Postpone multiple monitor support
        self.set_mouse_visible(replay_mode)

        self.batch = Batch()
        self.keyboard = dict() # Reproduce a simple KeyStateHandler

        self.replay_mode = replay_mode
        self.create_MATB_background()
        self.alive = True
        self.modal_dialog = None
        self.slider_visible = False

        self.on_key_press_replay = None # used by the replay
        self.highlight_aoi = highlight_aoi
        self.hide_on_pause = hide_on_pause


    def is_in_replay_mode(self):
        return self.replay_mode is True


    def set_size_and_location(self):
        self.switch_to()        # The Window must be active before setting the location
        target_x = (self.screen.x + self.screen.width / 2) - self.screen.width / 2
        target_y = (self.screen.y + self.screen.height / 2) - self.screen.height / 2
        self.set_location(int(target_x), int(target_y))


    def create_MATB_background(self):
        self.replay_margin_h, self.replay_margin_w = (0.07, 0.1) if self.replay_mode else (0, 0)

        MATB_container = self.get_container('fullscreen')
        l, b, w, h = MATB_container.get_lbwh()
        container_title_h = PLUGIN_TITLE_HEIGHT_PROPORTION/2

        # Main background
        self.batch.add(4, GL_POLYGON, G(-1), ('v2f/static', (l, b+h, l+w, b+h, l+w, b, l, b)),
                                            ('c4B', C['BACKGROUND'] * 4))

        # Upper band
        self.batch.add(4, GL_POLYGON, G(-1),
                  ('v2f/static', (l, b+h, l+w, b+h,
                                  l+w, b+h*(1-container_title_h), l, b+h*(1-container_title_h))),
                  ('c4B/static', C['BLACK'] * 4))

        # Middle band
        self.batch.add(4, GL_POLYGON, G(0),
                  ('v2f/static', (l,   b + h/2,   l+w, b + h/2,
                                  l+w, b + h*(0.5-container_title_h),
                                  0,   b + h*(0.5-container_title_h))),
                  ('c4B/static', C['BLACK'] * 4))


    def on_draw(self):
        self.set_mouse_visible(self.is_mouse_necessary())
        self.clear()
        self.batch.draw()


    def is_mouse_necessary(self):
        return self.modal_dialog == True or self.slider_visible == True


    def is_modal_dialog_on(self):
        return self.modal_dialogs > 0


    # Log any keyboard input, either plugins accept it or not
    def on_key_press(self, symbol, modifiers):
        if self.modal_dialog is not None:
            return

        keystr = winkey.symbol_string(symbol)
        self.keyboard[keystr] = True  # KeyStateHandler

        if keystr == 'ESCAPE':
            self.exit_prompt()
        elif keystr == 'P':
            self.pause_prompt()

        if self.replay_mode:
            if self.on_key_press_replay != None:
                self.on_key_press_replay(symbol, modifiers)
            return

        logger.record_input('keyboard', keystr, 'press')


    def on_key_release(self, symbol, modifiers):
        if self.modal_dialog is not None:
            self.modal_dialog.on_key_release(symbol, modifiers)
            return

        keystr = winkey.symbol_string(symbol)
        self.keyboard[keystr] = False  # KeyStateHandler
        logger.record_input('keyboard', keystr, 'release')


    def exit_prompt(self):
        self.modal_dialog = ModalDialog(self, _('You hit the Escape key'), title=_('Exit OpenMATB?'), exit_key='q')


    def pause_prompt(self):
        self.modal_dialog = ModalDialog(self, _('Pause'))


    def exit(self):
        self.alive = False


    def on_joyaxis_motion(self, joystick, axis, value):
        logger.record_input('joystick', axis, value)


    def get_container_list(self):
        w, h = (1-self.replay_margin_w) * self.width, (1 - self.replay_margin_h)*self.height
        b = self.height*self.replay_margin_h

        # Vertical bounds
        x1, x2 = (int(w * bound) for bound in [0.35, 0.85])  # Top row
        x3, x4 = (int(w * bound) for bound in [0.30, 0.85])  # Bottom row

        # Horizontal bound
        y1 = b + h/2

        return [Container('invisible', 0, 0, 0, 0),
                Container('fullscreen', 0, b, w, h),
                Container('topleft', 0, y1, x1, h/2),
                Container('topmid', x1, y1, x2 - x1, h/2),
                Container('topright', x2, y1, w-x2, h/2),
                Container('bottomleft', 0, b, x3, h/2),
                Container('bottommid', x3, b, x4 - x3, h/2),
                Container('bottomright', x4, b, w - x4, h/2),
                Container('mediastrip', 0, 0, self._width, b),
                Container('inputstrip', w, b, self._width*self.replay_margin_w, h)]


    def get_container(self, placement_name):
        container = [c for c in self.get_container_list() if c.name == placement_name]
        if len(container) > 0:
            return container[0]
        else:
            print(_('Error. No placement found for the [%s] alias') % placement_name)
