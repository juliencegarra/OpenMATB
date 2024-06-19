# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import sys
from pyglet import font, image
from pyglet.canvas import get_display
from pyglet.window import Window, key as winkey
from pyglet.graphics import Batch
from pyglet.gl import GL_POLYGON, glLineWidth
from pyglet.text import Label
from pyglet import image, sprite
from core.container import Container
from core.constants import COLORS as C, FONT_SIZES as F, Group as G, PLUGIN_TITLE_HEIGHT_PROPORTION
from core.constants import PATHS as P
from core.constants import REPLAY_MODE, REPLAY_STRIP_PROPORTION
from core.modaldialog import ModalDialog
from core.logger import logger
import core.error
from core.utils import get_conf_value

class Window(Window):

    # Static variable
    MainWindow = None

    def __init__(self, *args, **kwargs):

        Window.MainWindow = self # correct way to set it as a static

        screen = self.get_screen()

        self._width=int(screen.width)
        self._height=int(screen.height)
        self._fullscreen=get_conf_value('Openmatb', 'fullscreen')

        super().__init__(fullscreen=self._fullscreen, width=self._width, height=self._height,
                            vsync=True, *args, **kwargs)

        img_path = P['IMG']
        logo16 = image.load(img_path.joinpath('logo16.png'))
        logo32 = image.load(img_path.joinpath('logo32.png'))
        self.set_icon(logo16, logo32)

        self.set_size_and_location(screen) # Postpone multiple monitor support
        self.set_mouse_visible(REPLAY_MODE)

        self.batch = Batch()
        self.keyboard = dict() # Reproduce a simple KeyStateHandler

        self.create_MATB_background()
        self.alive = True
        self.modal_dialog = None
        self.slider_visible = False

        self.on_key_press_replay = None # used by the replay

        self.display_session_id()


    def display_session_id(self):
        # Display the session ID if needed at window instanciation
        if not REPLAY_MODE and get_conf_value('Openmatb', 'display_session_number'):
            msg = _('Session ID: %s') % logger.session_id
            title='OpenMATB'

            self.modal_dialog = ModalDialog(self, msg, title)


    def get_screen(self):
        # Screen definition
        try:
            screen_index = get_conf_value('Openmatb', 'screen_index')
        except:
            screen_index = 0

        screens = get_display().get_screens()
        if screen_index + 1 > len(screens):
            screen = screens[-1]
            errors.add_error(_(f"In config.ini, the specified screen index exceeds the number of available screens (%s). Last screen selected.") % len(get_display().get_screens()))
        else:
            screen = screens[screen_index]

        return screen

    def set_size_and_location(self, screen):
        self.switch_to()        # The Window must be active before setting the location
        target_x = (screen.x + screen.width / 2) - screen.width / 2
        target_y = (screen.y + screen.height / 2) - screen.height / 2
        self.set_location(int(target_x), int(target_y))


    def create_MATB_background(self):
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
        return self.slider_visible or REPLAY_MODE


    # Log any keyboard input, either plugins accept it or not
    # is subclassed in replay mode
    def on_key_press(self, symbol, modifiers):
        if REPLAY_MODE:
            return

        if self.modal_dialog is None:
            keystr = winkey.symbol_string(symbol)
            self.keyboard[keystr] = True  # KeyStateHandler

            if keystr == 'ESCAPE':
                self.exit_prompt()
            elif keystr == 'P':
                self.pause_prompt()

            logger.record_input('keyboard', keystr, 'press')


    def on_key_release(self, symbol, modifiers):
        if self.modal_dialog is not None:
            self.modal_dialog.on_key_release(symbol, modifiers)
            return

        if REPLAY_MODE:
            return

        keystr = winkey.symbol_string(symbol)
        self.keyboard[keystr] = False  # KeyStateHandler
        logger.record_input('keyboard', keystr, 'release')


    def exit_prompt(self):
        self.modal_dialog = ModalDialog(self, _('You hit the Escape key'), 
                                        title=_('Exit OpenMATB?'), exit_key='q')


    def pause_prompt(self):
        self.modal_dialog = ModalDialog(self, _('Pause'))


    def exit(self):
        self.alive = False


    def get_container_list(self):
        mar = REPLAY_STRIP_PROPORTION if REPLAY_MODE else 0
        w, h = (1-mar) * self.width, (1-mar)*self.height
        b = self.height*mar

        # Vertical bounds
        x1, x2 = (int(w * bound) for bound in get_conf_value('Openmatb', 'top_bounds'))  # Top row
        x3, x4 = (int(w * bound) for bound in get_conf_value('Openmatb', 'bottom_bounds'))  # Bottom row

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
                Container('mediastrip', 0, 0, self._width*(1+mar), b),
                Container('inputstrip', w, b, self._width*mar, h)]


    def get_container(self, placement_name):
        container = [c for c in self.get_container_list() if c.name == placement_name]
        if len(container) > 0:
            return container[0]
        else:
            print(_('Error. No placement found for the [%s] alias') % placement_name)


    def open_modal_window(self, pass_list, title, continue_key, exit_key):
        #TODO: would be better to use callbacks than to detect the alive variable
        # for example to close
        self.modal_dialog = ModalDialog(self, pass_list, title=title,
                                                      continue_key=continue_key, exit_key='Q')
