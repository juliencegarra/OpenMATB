# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import math
from pyglet.gl import *
from pyglet.text import Label, HTMLLabel
from core.constants import Group as G, COLORS as C, FONT_SIZES as F
from pyglet import sprite
from core.logger import logger
from core.constants import BFLIM
from core.utils import get_conf_value


class AbstractWidget:
    def __init__(self, name, container, win):
        self.name = name
        self.container = container
        self.win = win
        self.font_name = get_conf_value('Openmatb', 'font_name')
        self.vertex = dict()
        self.on_batch = dict()
        self.visible = False
        self.logger = logger
        self.highlight_aoi = get_conf_value('Openmatb', 'highlight_aoi')
        glLineWidth(2)
        
        self.m_draw = 0
        self.verbose = False

        if self.container is not None:
            if self.container.name == 'fullscreen':
                self.m_draw = BFLIM
            else:
                self.m_draw = 0


    def is_visible(self):
        return self.visible is True


    def show(self):
        if self.is_visible():
            return
        if self.verbose:
            print('Show ', self.name)
        self.show_aoi_highlight()
        self.assign_vertices_to_batch()
        if hasattr(self, 'set_visibility'):
            self.set_visibility(True)
        else:
            self.visible = True


    def hide(self):
        if not self.is_visible():
            return
        if self.verbose:
            print('Hide ', self.name)

        self.empty_batch()
        if hasattr(self, 'set_visibility'):
            self.set_visibility(False)
        else:
            self.visible = False


    def show_aoi_highlight(self):
        """Add some AOI vertices (frame and text)"""
        if self.container is None:
            return

        if self.highlight_aoi is True:
            self.border_vertice = self.vertice_border(self.container)
            self.add_vertex('highlight', 8, GL_LINES, G(self.m_draw+8),
                            ('v2f/static', self.vertice_strip(self.border_vertice)),
                            ('c4B/dynamic', (C['RED'] * 8)))

            self.vertex[self.name] = Label(self.name, x=self.container.x1 + 5,
                                           y=self.container.y1 - 15, color=C['RED'],
                                           group=G(self.m_draw+8))


    def assign_vertices_to_batch(self):
        for name, v_tuple in self.vertex.items():
            if isinstance(v_tuple, Label) or isinstance(v_tuple, HTMLLabel) or isinstance(v_tuple, sprite.Sprite):
                v_tuple.batch = self.win.batch
            else:
                self.on_batch[name] = self.win.batch.add(*v_tuple)


    def empty_batch(self):
        for name in list(self.vertex.keys()):  # TODO: Complete and use show_vertex
            if isinstance(self.vertex[name], Label) or isinstance(self.vertex[name], HTMLLabel):
                self.vertex[name].batch = None
            else:
                self.on_batch[name].delete()
                del self.on_batch[name]


    def add_vertex(self, name, *args):
        self.vertex[name] = args


    def get_vertex_color(self, vertex_name):
        return tuple(self.on_batch[vertex_name].colors[:][0:4])


    def vertice_strip(self, vertice):
        '''Develop a list of vertice points to obtain a list of vertice segments'''
        vertice_strip_list = list()
        if vertice is not None:
            for i in range((len(vertice)//2)-1):
                x1, y1, x2, y2 = (vertice[i*2], vertice[i*2+1],
                                 vertice[i*2+2], vertice[i*2+3])
                [vertice_strip_list.append(c) for c in (x1, y1, x2, y2)]
            x1, y1, x2, y2 = (vertice[-2], vertice[-1],
                              vertice[0], vertice[1])
            [vertice_strip_list.append(c) for c in (x1, y1, x2, y2)]
            return list(vertice_strip_list)
        else:
            return None


    def get_triangle_vertice(self, h_ratio=0.25, x_ratio=0.3, angle=0):
        # Compute triangle coordinates (radio, pumpflow use it)
        cont = self.container
        w_ratio = (h_ratio*cont.h)/cont.w
        tcont = cont.get_reduced(w_ratio, h_ratio)
        tcont = tcont.get_translated(x=x_ratio * cont.w)
        vertice = (tcont.l, tcont.b, tcont.l + tcont.w, tcont.b, tcont.l + tcont.w/2, tcont.b + tcont.h)
        centroid = self.get_triangle_centroid(vertice)
        vertice = self.rotate_vertice_list(centroid, vertice, angle)
        return vertice


    def get_triangle_centroid(self, vertice):
        x = round(sum([v for i, v in enumerate(vertice) if i%2 == 0])/(len(vertice)/2),2)
        y = round(sum([v for i, v in enumerate(vertice) if i%2 == 1])/(len(vertice)/2),2)
        return (x, y)


    def grouped(self, iterable, n):
        return zip(*[iter(iterable)]*n)


    def rotate_vertice_list(self, origin, vertices_list, angle):
        ox, oy = origin
        rotated_vertices = list()
        for px, py in self.grouped(vertices_list, 2):
            qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
            qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
            rotated_vertices.extend([qx, qy])
        return rotated_vertices


    def vertice_circle(self, center, radius, points_n=30):
        v = list()
        for i in range(points_n):
            cosine= radius * math.cos(i*2*math.pi/points_n) + center[0]
            sine  = radius * math.sin(i*2*math.pi/points_n) + center[1]
            v.extend([cosine, sine])
        return list(v)


    def vertice_border(self, container):
        c = container
        return c.x1, c.y1, c.x2, c.y1, c.x2, c.y2, c.x1, c.y2


    def vertice_line_border(self, container):
        c = container
        return c.x1, c.y1, c.x2, c.y1, c.x2, c.y1, c.x2, c.y2, c.x2, c.y2, c.x1, c.y2, c.x1, c.y2, c.x1, c.y1


    def remove_all_vertices(self):
        self.vertex = dict()
