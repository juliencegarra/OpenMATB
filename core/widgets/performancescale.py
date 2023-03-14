# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *
from core import Container

class Performancescale(AbstractWidget):
    def __init__(self, name, container, win, level_min, level_max, tick_number, color):
        super().__init__(name, container, win)

        self.performance_level = level_max
        self.performance_color = color
        self.level_max = level_max
        self.tick_number = tick_number

        tick_inter = int((level_max - level_min)/(self.tick_number-1))
        tick_values = list(reversed(range(level_min, level_max + 1, tick_inter)))

        # Background vertex #
        x1, y1, x2, y2 = self.container.get_x1y1x2y2()
        self.border_vertices = self.vertice_border(self.container)
        self.add_vertex('background', 4, GL_QUADS, G(self.m_draw), ('v2f/static', self.border_vertices),
                        ('c4B/static', (C['WHITE']*4)))

        # Performance vertex #
        performance_vertices = self.get_performance_vertices(self.performance_level)
        self.add_vertex('performance', 4, GL_QUADS, G(self.m_draw+1), ('v2f/stream', performance_vertices),
                        ('c4B/static', (self.performance_color*4)))

        # Borders vertex #
        self.add_vertex('borders', 8, GL_LINES, G(self.m_draw+2), ("v2f/static", self.vertice_strip(self.border_vertices)),
                        ('c4B/static', (C['BLACK']*8)))


        # Ticks vertex #
        self.tick_width = self.container.w * 0.25
        v = list()
        x = self.container.l + self.container.w + self.container.w * 0.1

        self.positions = []

        for i in range(tick_number):
            y = self.container.b + self.container.h - (self.container.h/(self.tick_number-1)) * i
            w = self.tick_width # if i != 5 else self.tick_width + 8
            v.extend([self.container.x2 - w, y, self.container.x2, y])

            self.vertex[f'tick_{tick_values[i]}_label'] = Label(str(tick_values[i]),
                        font_size=F['SMALL'], x=x, y=y, anchor_x='left',
                        anchor_y='center', color=C['BLACK'], group=G(self.m_draw+2), font_name=self.font_name)


        self.add_vertex('ticks' , len(v)//2, GL_LINES, G(self.m_draw+2), ('v2f/static', v),
                        ('c4B/static', (C['BLACK']*(len(v)//2))))


    def get_performance_vertices(self, level):
        v2 = list(self.border_vertices)
        v2[1] = v2[3] = self.get_y_of(level)
        return v2


    def get_y_of(self, level):
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / self.level_max)


    def set_performance_level(self, level):
        if level == self.get_performance_level():
            return
        self.performance_level = level
        v1 = list(self.vertice_border(self.container))
        v1[1] = v1[3] = self.get_y_of(self.performance_level)
        self.on_batch['performance'].vertices = v1
        self.logger.record_state(self.name, 'level', self.performance_level)


    def get_performance_level(self):
        return self.performance_level


    def set_performance_color(self, color):
        if color == self.get_performance_color():
            return
        self.performance_color = color
        self.on_batch['performance'].colors[:] = color * 4
        self.logger.record_state(self.name, 'color', self.performance_color)


    def get_performance_color(self):
        return self.get_vertex_color('performance')
