# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.container import Container
from core.constants import COLORS as C, Group as G
from core.widgets import AbstractWidget
from pyglet.gl import GL_QUADS

class Frame(AbstractWidget):
    '''
    This widget is a simple frame that surrounds the task. It has a given color and thickness,
    and can be shown or hidden to generate various feedback effects (blinking alarm, colorful feedback).
    '''
    def __init__(self, name, container, win, fill_color=C['BACKGROUND'],
                 border_color=C['BACKGROUND'], border_thickness=0, draw_order=1):
        super().__init__(name, container, win)

        self.border_thickness = border_thickness

        if fill_color is not None:
            self.add_vertex('fillarea', 4, GL_QUADS, G(draw_order),
                            ('v2f/static', (0,)*8),
                            ('c4B/static', (fill_color*4)))

        self.add_vertex('border', 16, GL_QUADS, G(draw_order+1), ('v2f/dynamic', (0,)*32),
                        ('c4B/dynamic', (border_color * 16)))


    def get_border_vertices(self):
        # Left and right rectangles inherit top and bottom thickness
        t_b_th = self.border_thickness
        top_container = self.container.reduce_and_translate(1, t_b_th, 0, 1)

        # So top height is left/right width. Thickness is just this width expressed as
        # the main container width ratio
        _, _, _, left_right_w = top_container.get_lbwh()
        l_r_th = left_right_w / self.container.w

        top_vertices = self.vertice_border(top_container)
        bot_vertices = self.vertice_border(self.container.reduce_and_translate(1, t_b_th, 0, 0))
        lef_vertices = self.vertice_border(self.container.reduce_and_translate(l_r_th, 1, 0, 0))
        rig_vertices = self.vertice_border(self.container.reduce_and_translate(l_r_th, 1, 1, 0))
        return top_vertices + bot_vertices + lef_vertices + rig_vertices


    def set_border_thickness(self, thickness):
        if thickness == self.get_border_thickness():
            return
        self.border_thickness = thickness
        self.logger.record_state(self.name, 'border_thickness', thickness)

        if self.is_visible():
            self.on_batch['border'].vertices = self.get_border_vertices()


    def get_border_thickness(self):
        return self.border_thickness


    def set_border_color(self, color):
        if color == self.get_border_color():
            return
        self.on_batch['border'].colors[:] = color * 16
        self.logger.record_state(self.name, 'color', color)


    def get_border_color(self):
        return self.get_vertex_color('border')


    def set_visibility(self, visible):
        if visible == self.is_visible():
            return
        self.visible = visible

        if 'border' in self.on_batch:
            v =  self.get_border_vertices() if self.is_visible() else (0,)*32
            self.on_batch['border'].vertices = v

        if 'fillarea' in self.on_batch:
            v = self.vertice_border(self.container) if self.is_visible() else (0,)*8
            self.on_batch['fillarea'].vertices = v

        self.logger.record_state(self.name, 'visibility', visible)

