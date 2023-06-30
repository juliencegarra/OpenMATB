# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets import AbstractWidget
from core.constants import COLORS as C, FONT_SIZES as F, PATHS as P
from core.constants import Group as G
from pyglet.text import Label
from pyglet import image, sprite
from pyglet.gl import *

class Button(AbstractWidget):
    def __init__(self, name, container, win, callback):
        super().__init__(name, container, win)

        self.padding = 0.1
        self.hover = False
        self.callback = callback

        # Draw the button
        self.active_area = self.container.get_reduced(1-self.padding, 1-self.padding)
        button_vertice = self.vertice_border(self.active_area)

        self.add_vertex('background', 4, GL_QUADS, G(self.m_draw+self.m_draw+1), 
                        ('v2f/static', button_vertice), ('c4B/static', (C['DARKGREY']*4)))
        self.add_vertex('border', 8, GL_LINES, G(self.m_draw+self.m_draw+3), 
                        ("v2f/static", self.vertice_strip(button_vertice)), 
                        ('c4B/static', (C['BLACK']*8)))

        self.win.push_handlers(self.on_mouse_press, self.on_mouse_release)


    def on_mouse_press(self, x, y, button, modifiers):
        if self.mouse_is_in_active_area(x, y) and self.hover == False:
            self.hover = True


    def on_mouse_release(self, x, y, button, modifiers):
        if self.hover == True:
            self.on_mouse_click()
            self.hover = False


    def mouse_is_in_active_area(self, x, y):
        return self.active_area.contains_xy(x, y)


    def on_mouse_click(self):
        if self.verbose:
            print(self.name, 'Click')
        return self.callback()



class PlayPause(Button):
    def __init__(self, name, container, win, callback):
        super().__init__(name, container, win, callback)
        self.current_image = None

        img_path = P['IMG']
        self.pause_img = image.load(img_path.joinpath('pause.png'))
        self.play_img = image.load(img_path.joinpath('play.png'))

        for pic_img in [self.play_img, self.pause_img]:
            pic_img.anchor_x = pic_img.width // 2
            pic_img.anchor_y = pic_img.height // 2

        self.sprites = {0: sprite.Sprite(img=self.play_img),
                        1: sprite.Sprite(img=self.pause_img)}

        for pause, sp in self.sprites.items():
            sp.batch = self.win.batch if pause == 1 else None
            sp.x=self.container.cx
            sp.y=self.container.cy
            sp.group=G(self.m_draw+8)
            sp.scale = (self.container.h / sp.height) - self.padding/2

        self.show()


    def update_button_sprite(self, is_paused):
        self.sprites[int(is_paused)].batch = None
        self.sprites[int(not is_paused)].batch = self.win.batch
