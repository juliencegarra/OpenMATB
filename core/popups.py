from pyglet_gui.theme import Theme
from pyglet_gui.gui import Label
from pyglet_gui.manager import Manager
from pyglet_gui.buttons import Button, OneTimeButton, Checkbox, GroupButton
from pyglet_gui.containers import VerticalContainer

from pyglet.canvas import get_display
from pyglet.graphics import Batch
from pyglet.gl import GL_POLYGON
from pyglet.window import Window

from core.constants import COLORS as C, FONT_SIZES as F, Group as G

class PopupWindow(Window):
    def __init__(self, screen_index, *args, **kwargs):
        screen = get_display().get_screens()[screen_index]
        super(PopupWindow, self).__init__(screen = screen, *args, **kwargs)
        self.batch = Batch()
        self.batch.add(4, GL_POLYGON, G(1),
            ('v2f/static', (0, 0, 0, self.height, self.width, self.height, self.width, 0)),
            ('c4B', C['BACKGROUND'] * 4))

    def on_draw(self):
        self.clear()
        self.batch.draw()


POPUP_THEME = Theme({"font": "Lucida Grande",
                     "font_size": F['SMALL'],
                     "text_color": [255, 0, 0, 255],
                     "gui_color": [255, 0, 0, 255],
                     "button": {
                         "down": {
                             "image": {
                                 "source": "button-down.png",
                                 "frame": [6, 6, 3, 3],
                                 "padding": [12, 12, 4, 2]
                             },
                             "text_color": [0, 0, 0, 255]
                         },
                         "up": {
                             "image": {
                                 "source": "button.png",
                                 "frame": [6, 6, 3, 3],
                                 "padding": [12, 12, 4, 2]
                             }
                        }
                     }},
                     resources_path='./core/theme/')


class PopupMessage:
    def __init__(self, message):
        window = PopupWindow(0)
        label = Label(message)
        
        Manager(VerticalContainer
        ([label,  OneTimeButton(label="One time button")]),
                window=window, theme=POPUP_THEME, batch=window.batch)
