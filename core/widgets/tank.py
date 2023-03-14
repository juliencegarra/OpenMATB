# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *
from core import Container

class Tank(AbstractWidget):
    def __init__(self, name, container, win, letter, level, fluid_label, level_max, target,
                 toleranceradius, infoside):
        super().__init__(name, container, win)

        self.tolerance_cont = None
        self.infoside = infoside
        self.tolerance_radius = toleranceradius
        self.level = level
        # self.tolerance_color = C['BLACK']

        # Background vertex #
        x1, y1, x2, y2 = self.container.get_x1y1x2y2()
        self.border_vertices = self.vertice_border(self.container)
        self.add_vertex('background', 4, GL_QUADS, G(self.m_draw+1), ('v2f/static', self.border_vertices),
                        ('c4B/static', (C['WHITE']*4)))

        if target is not None:
            vt = self.get_tolerance_vertices(self.tolerance_radius, target, level_max)
            self.add_vertex('tolerance', 4, GL_QUADS, G(self.m_draw+1), ('v2f/static', vt),
                            ('c4B/static', (C['BLACK']*4)))

        fluid_vertices = self.get_fluid_vertices(self.level, level_max)
        self.add_vertex('fluid', 4, GL_QUADS, G(self.m_draw+2), ('v2f/stream', fluid_vertices),
                        ('c4B/static', (C['GREEN']*4)))


        self.add_vertex('borders', 8, GL_LINES, G(self.m_draw+3), ("v2f/static", self.vertice_strip(self.border_vertices)),
                        ('c4B/static', (C['BLACK']*8)))

        x, y = self.container.get_center()
        self.vertex['fluid_label'] = Label(fluid_label, font_size=F['SMALL'], font_name=self.font_name,
                                           x=x, y=y2 - 15, anchor_x='center',
                                           anchor_y='center', color=C['BLACK'], group=G(1))

        l_x = x1 - 15 if infoside == 'left' else x2 + 15
        self.vertex['tank_label'] = Label(letter, font_size=F['SMALL'], font_name=self.font_name,
                                          x=l_x, y=y1 - 10, anchor_x='center',
                                          anchor_y='center', color=C['BLACK'], group=G(1))


    def get_fluid_vertices(self, level, level_max):
        v2 = list(self.border_vertices)
        v2[1] = v2[3] = self.get_y_of(level, level_max)
        return v2


    def get_y_of(self, level, level_max):
        _, y1, _, y2 = self.container.get_x1y1x2y2()
        return y2 + (y1 - y2) * (level / level_max)


    def get_tolerance_vertices(self, radius, target_level, level_max):
        t_width = 15
        t_left = (self.container.l - t_width if self.infoside == 'left'
                  else self.container.l + self.container.w)
        t_bottom = self.get_y_of(target_level - radius, level_max)
        t_height = self.get_y_of(radius*2, level_max) - self.get_y_of(0, level_max)

        self.tolerance_cont = Container('Tolerance', t_left, t_bottom, t_width, t_height)
        return self.vertice_border(self.tolerance_cont)


    def set_tolerance_radius(self, radius, target, level_max):
        if radius == self.get_tolerance_radius():
            return
        self.tolerance_radius = radius
        self.on_batch['tolerance'].vertices = self.get_tolerance_vertices(radius, target, level_max)
        self.logger.record_state(self.name, 'tolerance_radius', radius)
        self.logger.record_state(self.name, 'target', target)
        self.logger.record_state(self.name, 'level_max', level_max)


    def set_tolerance_color(self, color):
        if color == self.get_tolerance_color():
            return
        self.on_batch['tolerance'].colors[:] = color * 4
        self.logger.record_state(self.name, 'tolerance_color', color)


    def get_tolerance_radius(self):
        return self.tolerance_radius


    def get_tolerance_color(self):
        return self.get_vertex_color('tolerance')


    def set_fluid_level(self, level, level_max):
        if level == self.get_fluid_level():
            return
        self.level = level
        v1 = list(self.vertice_border(self.container))
        v1[1] = v1[3] = self.get_y_of(level, level_max)
        self.on_batch['fluid'].vertices = v1
        self.logger.record_state(self.name, 'fluid_level', level)
        
    
    def get_fluid_level(self):
        return self.level


    def set_fluid_label(self, label):
        if label == self.get_fluid_label():
            return
        self.vertex['fluid_label'].text = label
        self.logger.record_state(self.name, 'fluid_label', label)
    
    
    def get_fluid_label(self):
        return self.vertex['fluid_label'].text
