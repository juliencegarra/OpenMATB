# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *
from core.constants import M

class Schedule(AbstractWidget):
    def __init__(self, name, container, win, label):
        super().__init__(name, container, win)
        self.label = M[label]  # Get full and translated label version into constants

        self.line_radius = int(self.container.h / 200)
        self.bound_radius = int(self.container.h / 70)
        self.box_radius = self.bound_radius * 1.5
        
        self.vertex['letter'] = Label(self.label[0].upper(), font_size=F['MEDIUM'], font_name=self.font_name,
                                      x=self.container.cx, y=self.container.y2 - 15,
                                      anchor_x='center', anchor_y='top', color=C['BLACK'], group=G(1))

        v = [self.container.cx, self.container.y1, self.container.cx, self.container.y2]
        self.add_vertex('line', 2, GL_LINES, G(self.m_draw+1), ('v2f/static', v),
                        ('c4B/static', (C['GREY']*2)))

        self.add_vertex('top_bound', 4, GL_QUADS, G(self.m_draw+3),
                        ('v2f/static', (self.container.cx - self.bound_radius,
                                            self.container.y1+self.bound_radius*2,
                                        self.container.cx + self.bound_radius,
                                            self.container.y1+self.bound_radius*2,
                                        self.container.cx + self.bound_radius, self.container.y1,
                                        self.container.cx - self.bound_radius, self.container.y1)),
                        ('c4B/static', (C['GREY'] * 4)))

        self.add_vertex('bottom_bound', 4, GL_QUADS, G(self.m_draw+3),
                        ('v2f/static', (self.container.cx - self.bound_radius,
                                            self.container.y2 - self.bound_radius * 2,
                                        self.container.cx + self.bound_radius,
                                            self.container.y2 - self.bound_radius * 2,
                                        self.container.cx + self.bound_radius, self.container.y2,
                                        self.container.cx - self.bound_radius, self.container.y2)),
                        ('c4B/static', (C['GREY'] * 4)))

        for g, t in enumerate(['running', 'manual']):
            self.add_vertex(t, 4, GL_QUADS, G(self.m_draw+g+2),
                            ('v2f/dynamic', (0, 0)*4), ('c4B/dynamic', (C['GREY'] * 4)))


    def set_top_bound_color(self, bound_color):
        if bound_color == self.get_vertex_color('top_bound'):
            return
        self.on_batch['top_bound'].colors[:] = bound_color * 4
        self.logger.record_state(self.name, 'top_bound_color', bound_color)


    def sec_to_y(self, sec, max_sec):
        return (self.container.y1 - (sec / max_sec* (self.container.y1 - self.container.y2)))


    def map_segment(self, time_mode, rel_plan, max_sec, color):
        v = list()
        for segment_sec in rel_plan:
            x_radius = self.line_radius if time_mode == 'running' else self.box_radius
            start, end = segment_sec
            y1, y2 = self.sec_to_y(start, max_sec), self.sec_to_y(end, max_sec)
            v.extend([self.container.cx - x_radius, y1, self.container.cx + x_radius, y1,
                      self.container.cx + x_radius, y2, self.container.cx - x_radius, y2])
            self.on_batch[time_mode].resize(len(v)//2)    # Resize the vertex
            self.on_batch[time_mode].vertices = v         # Inform new vertices
            self.on_batch[time_mode].colors[:] = list(color) * (len(v)//2)


    def update(self):
        if self.visible:
            self.change_top_bound_color()
