# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *

class Light(AbstractWidget):
    def __init__(self, name, container, win, label, color):
        super().__init__(name, container, win)

        # Compute vertices
        self.border_vertice = self.vertice_border(self.container)
        self.border_color = C['BLACK']

        self.add_vertex('background', 4, GL_QUADS, G(self.m_draw), ('v2f/dynamic', self.border_vertice),
                        ('c4B/dynamic', color*4))

        self.add_vertex('border', 8, GL_LINES, G(self.m_draw+1), ('v2f/static',
                        self.vertice_strip(self.border_vertice)), ('c4B/static', self.border_color*8))

        self.vertex['label'] = Label(label.upper(), font_size=F['MEDIUM'], x=self.container.cx,
                                              y=self.container.cy, anchor_x='center', anchor_y='center',
                                              color=C['BLACK'], batch=None, group=G(self.m_draw+1),
                                              font_name=self.font_name)

    def set_label(self, label):
        label_to_upper = label.upper()
        if label_to_upper == self.get_label():
            return
        self.vertex['label'].text = label_to_upper
        self.logger.record_state(self.name, 'label', label_to_upper)
    
    
    def get_label(self):
        return self.vertex['label'].text


    def set_color(self, color):
        if color == self.get_color():
            return
        self.on_batch['background'].colors[:] = color*4
        self.on_batch['border'].colors[:] = self.border_color*8

        self.logger.record_state(self.name, 'background', color)
        self.logger.record_state(self.name, 'border', self.border_color)


    def get_color(self):
        return self.get_vertex_color('background')
