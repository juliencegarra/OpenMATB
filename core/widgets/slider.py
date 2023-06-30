# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from pyglet.gl import *
from core.container import Container
from core.constants import COLORS as C, Group as G, FONT_SIZES as F, REPLAY_MODE
from core.widgets import AbstractWidget
from core.widgets import AbstractWidget
from pyglet.text import Label


class Slider(AbstractWidget):
    def __init__(self, name, container, win, title, label_min, label_max,
                 value_min, value_max, value_default, rank, draw_order=1):
        super().__init__(name, container, win)

        self.title = title
        self.label_min = label_min
        self.label_max = label_max
        self.value_min = value_min
        self.value_max = value_max
        self.value_default = value_default
        self.draw_order = draw_order

        self.rank = rank
        self.groove_value = self.value_default
        self.hover = False

        # Enhance smoothing mode
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_DONT_CARE)
        glLineWidth(3)


        self.set_sub_containers()
        self.set_slider_thumb_and_groove()
        self.show()

        self.win.push_handlers(self.on_mouse_press, self.on_mouse_drag,
                               self.on_mouse_release)


    def set_sub_containers(self, slider_width=0.6):
        l = self.container.l
        label_w = self.container.w * (1 - slider_width) / 3
        slider_w = self.container.w * slider_width
        bounds = [l, l+label_w, l+label_w+slider_w, l+label_w+slider_w+label_w,
                  l+label_w+slider_w+label_w*2]

        self.containers = dict()
        for c, name in enumerate(['min', 'slide', 'max', 'value']):
            left, right = bounds[c], bounds[c+1]
            self.containers[name] = Container(f'container_{name}', left,
                        self.container.b, right-left, self.container.h)
        for name in ['min', 'max']:
            x, y = self.containers[name].cx, self.containers[name].cy
            self.vertex[name] = Label(getattr(self, f'label_{name}'), font_name=self.font_name,
                                      align='center', anchor_x='center',
                                      anchor_y='center', x=x, y=y, color=C['BLACK'],
                                      group=G(self.draw_order), font_size=F['MEDIUM'])
        x, y = self.containers['value'].cx, self.containers['value'].cy
        self.vertex['value'] = Label(str(self.groove_value), align='center', anchor_x='center',
                                      anchor_y='center', x=x, y=y, color=C['BLACK'],
                                      group=G(self.draw_order), font_size=F['MEDIUM'], 
                                      font_name=self.font_name)


    def set_slider_thumb_and_groove(self):
        slider_groove_h = 0.2
        slider_thumb_h = 0.05
        slider_thumb_w = 0.9

        self.containers['thumb'] = self.containers['slide'].get_reduced(slider_thumb_w,
                                                                        slider_thumb_h)

        # The groove container comprises the whole groove movements area
        self.containers['allgroove'] = self.containers['slide'].get_reduced(slider_thumb_w,
                                                                            slider_groove_h)

        v1 = self.vertice_border(self.containers['thumb'])
        self.add_vertex('thumb', 4, GL_QUADS, G(self.draw_order+self.rank), ('v2f/static', v1),
                        ('c4B/static', (C['GREY']*4)))

        v2 = self.get_groove_vertices()
        self.add_vertex('groove_b', len(v2)//2, GL_POLYGON, G(self.draw_order+self.rank), 
                        ('v2f/stream', v2), ('c4B/stream', (C['BLUE']*(len(v2)//2))))
        self.add_vertex('groove', len(v2)//2, GL_LINE_LOOP, G(self.draw_order+self.rank), 
                        ('v2f/stream', v2), ('c4B/stream', (C['BLACK']*(len(v2)//2))))


    def get_groove_vertices(self):
        groove_radius = self.containers['allgroove'].h
        center_ratio = ((self.groove_value - self.value_min) /
                        (self.value_max - self.value_min))
        x = self.containers['allgroove'].l + center_ratio * self.containers['allgroove'].w
        y = self.containers['allgroove'].cy
        return self.vertice_circle([x, y], groove_radius)


    def set_groove_position(self):
        if self.get_groove_vertices() == self.on_batch['groove'].vertices:
            return

        self.on_batch['groove'].vertices = self.get_groove_vertices()
        self.on_batch['groove_b'].vertices = self.get_groove_vertices()


    def set_value_label(self):
        if str(self.groove_value) == self.vertex['value'].text:
            return
        self.vertex['value'].text = str(self.groove_value)


    #TODO: hide cursor when finished
    def coordinates_in_groove_container(self, x, y):
        return self.containers['allgroove'].contains_xy(x, y)


    def on_mouse_press(self, x, y, button, modifiers):
        if self.coordinates_in_groove_container(x, y) and self.hover is False:
            self.hover = True
            self.update_cursor_appearance()


    def on_mouse_release(self, x, y, button, modifiers):
        if self.hover is True:
            self.hover = False
            self.update_cursor_appearance()


    def on_mouse_drag(self, x, y, dx, dy, button, modifiers):
        if self.hover is True:
            x_min = self.containers['allgroove'].l
            x_max = self.containers['allgroove'].l + self.containers['allgroove'].w
            x = min(x_max, max(x_min, x))
            ratio = (x-x_min)/(x_max-x_min)
            self.update_groove_value(ratio)


    def update_groove_value(self, ratio):
        new_value = int(round(ratio * (self.value_max - self.value_min) + self.value_min))
        if new_value == self.groove_value:
            return
        self.groove_value = new_value
        self.logger.record_state(self.name, 'value', str(self.groove_value))
        self.update()


    def get_title(self):
        return self.title


    def get_value(self):
        return self.groove_value


    def update_cursor_appearance(self):
        if self.hover is True:
            cursor = self.win.get_system_mouse_cursor(self.win.CURSOR_SIZE_LEFT_RIGHT)
        else:
            cursor = self.win.get_system_mouse_cursor(self.win.CURSOR_DEFAULT)
        self.win.set_mouse_cursor(cursor)


    def update(self):
        if self.visible:
            self.set_groove_position()
            self.set_value_label()


    def hide(self):
        super().hide()
        self.win.slider_visible = False


    def show(self):
        super().show()
        self.win.slider_visible = True
