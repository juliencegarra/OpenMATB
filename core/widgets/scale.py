# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from pyglet.gl import *
from random import sample
from core.constants import COLORS as C, FONT_SIZES as F
from core import Container, Group as G
from core.widgets.abstractwidget import AbstractWidget
from pyglet.text import Label


class Scale(AbstractWidget):
    def __init__(self, name, container, win, label, arrow_position=5):
        super().__init__(name, container, win)

        self.background_color = (255, 255, 255)
        self.feedback_visible = False

        # Compute arrow positions list
        self.positions = [self.container.b + (self.container.h/11) * i +
                          self.container.h/22 for i in range(11)]
        self.position = 5

        # Compute vertices
        self.vertex['label'] = Label(label.upper(), font_size=F['MEDIUM'], x=self.container.cx, font_name=self.font_name,
                                     y=self.container.b-20, anchor_x='center', anchor_y='center',
                                     color=C['BLACK'], batch=None, group=G(self.m_draw+1))

        scale_vertice = self.vertice_border(self.container)
        self.add_vertex('background', 4, GL_QUADS, G(self.m_draw+self.m_draw+1), ('v2f/static', scale_vertice),
                                     ('c3B/static', ((255, 255, 255)*4)))
        self.add_vertex('border', 8, GL_LINES, G(self.m_draw+self.m_draw+3), ("v2f/static", self.vertice_strip(scale_vertice)),
                                  ('c4B/static', (C['BLACK']*8)))

        # Compute widths
        self.tick_width = self.container.w * 0.25
        v = list()
        for i in range(11):
            w = self.tick_width if i != 5 else self.tick_width + 8
            v.extend([self.container.x2 - w, self.positions[i],
                      self.container.x2, self.positions[i]])

        self.arrow_width = 0.15 * self.container.w
        self.arrow_x_offset = 0.22 * self.container.w       # So the arrow does not stick to
                                                            # the right side of the scale
        self.feedback_height = 0.12 * self.container.h

        self.add_vertex('ticks' , len(v)//2, GL_LINES, G(self.m_draw+3), ('v2f/static', v),
                        ('c4B/static', (C['BLACK']*(len(v)//2))))
        self.add_vertex('feedback', 4, GL_QUADS, G(self.m_draw+2), ('v2f/dynamic', (0, 0, 0, 0, 0, 0, 0, 0)),
                        ('c4B/dynamic', (C['GREEN'] * 4)))
        self.add_vertex('arrow', 3, GL_TRIANGLES, G(self.m_draw+2), ('v2f/stream', self.return_arrow_vertice(arrow_position)),
                        ('c4B/static', (C['BLACK']*3)))


    def return_arrow_vertice(self, position):
        xo = self.arrow_x_offset
        aw = self.arrow_width
        return (self.container.x2 - self.tick_width - xo, self.positions[position],
                self.container.x2 - self.tick_width - (xo + aw), self.positions[position] - aw / 2,
                self.container.x2 - self.tick_width - (xo + aw), self.positions[position] + aw / 2)


    def set_feedback_visibility(self, visible):
        if visible == self.feedback_visible:
            return
        self.feedback_visible = visible
        h = self.feedback_height
        v = ((self.container.x1, self.container.y2 + h, self.container.x2, self.container.y2 + h,
             self.container.x2, self.container.y2, self.container.x1, self.container.y2)
             if visible else (0, 0)*4)
        self.on_batch['feedback'].vertices = v
        self.logger.record_state(self.name, 'feedback_visible', visible)


    def is_feedback_visible(self):
        return self.feedback_visible is True


    def set_feedback_color(self, color):
        if color == self.get_feedback_color():
            return
        self.on_batch['feedback'].colors[:] = color * 4
        self.logger.record_state(self.name, 'feedback_color', color)


    def get_feedback_color(self):
        return self.get_vertex_color('feedback')


    def set_arrow_position(self, position):
        if position == self.get_arrow_position():
            return
        self.position = position
        self.on_batch['arrow'].vertices = self.return_arrow_vertice(self.position)
        self.logger.record_state(self.name, 'arrow', self.position)
        
    
    def get_arrow_position(self):
        return self.position
    
    
    def set_label(self, label):
        label_to_upper = label.upper()
        if label == self.get_label():
            return
        self.vertex['label'].text = label_to_upper
        self.logger.record_state(self.name, 'label', label_to_upper)
        
        
    def get_label(self):
        return self.vertex['label'].text
