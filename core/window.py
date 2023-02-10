from pyglet.canvas import get_display
from pyglet.window import Window, key as winkey
from pyglet.graphics import Batch
from pyglet.gl import GL_POLYGON
from pyglet.text import Label
from pymsgbox import confirm, alert
from core import Container
from core.constants import COLORS as C, FONT_SIZES as F, Group as G, PLUGIN_TITLE_HEIGHT_PROPORTION
from core import logger
import os

class Window(Window):
    def __init__(self, screen_index, fullscreen, replay_mode, highlight_aoi, *args, **kwargs):

        screens = get_display().get_screens()
        if screen_index + 1 > len(screens):
            from core.error import fatalerror
            fatalerror(_(f"In config.ini, the specified screen index (%s) exceed the number of available screens (%s). Note that in Python, the first index is 0.") % (screen_index, len(get_display().get_screens())))
        else:
            screen = screens[screen_index]

        if replay_mode:
            self._width=int(screen.width / 1.2)
            self._height=int(screen.height / 1.2)
        else:
            self._width=screen.width
            self._height=screen.height

        #In Windows, setting fullscreen will make pyglet freeze
        if os.name=='nt':
            fullscreen=False

        self._fullscreen=fullscreen

        super().__init__(fullscreen=self._fullscreen, width=self._width, height=self._height, *args, **kwargs)

        self.set_size_and_location() # Postpone multiple monitor support
        self.set_mouse_visible(replay_mode)

        self.batch = Batch()
        self.keyboard = dict() # Reproduce a simple KeyStateHandler

        self.replay_mode = replay_mode
        self.create_MATB_background()
        self.alive = True
        self.was_prompting = False

        self.on_key_press_replay = None # used by the replay
        self.highlight_aoi = highlight_aoi


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
        self.clear()
        self.batch.draw()


    # Log any keyboard input, either plugins accept it or not
    def on_key_press(self, symbol, modifiers):
        keystr = winkey.symbol_string(symbol)
        self.keyboard[keystr] = True  # KeyStateHandler

        if self.replay_mode:
            if self.on_key_press_replay != None:
                self.on_key_press_replay(symbol, modifiers)
            return

        logger.record_input('keyboard', keystr, 'press')


    def on_key_release(self, symbol, modifiers):
        keystr = winkey.symbol_string(symbol)        
        self.keyboard[keystr] = False  # KeyStateHandler
        
        # For now, these events are waiting key release because waiting key press
        # leads to miss the releasing of the key (pymsgbox blocking)
        if keystr == 'ESCAPE':
            if self.user_wants_to_quit():
                self.exit()
            else:
                pass
        
        elif keystr == 'P':           
            self.pause()
        
        logger.record_input('keyboard', keystr, 'release')


    def user_wants_to_quit(self):
        self.was_prompting = True
        if self._fullscreen:
            self.set_visible(False)

        response = confirm(text=_('You pressed the Escape key.\nDo you want to quit?'), title=_('Exit OpenMATB?'), buttons=[_('Continue'), _('Quit')])

        if self._fullscreen:
            self.set_visible(True)

        if response == _('Quit'):
            return True
        elif response == _('Continue'):
            return False
    
    
    def pause(self):
        self.was_prompting = True
        if self._fullscreen:
            self.set_visible(False)

        response = alert(text=_('Pause'), title=_('OpenMATB'), button=_('Continue'))

        if self._fullscreen:
            self.set_visible(True)
            

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
