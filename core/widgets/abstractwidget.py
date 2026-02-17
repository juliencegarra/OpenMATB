# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

import math
from pyglet.gl import (GL_LINES, GL_TRIANGLES,
                        GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                        GL_BLEND, glLineWidth, glBlendFunc, glEnable)
from pyglet.text import Label, HTMLLabel
from core.constants import Group as G, COLORS as C, FONT_SIZES as F
from pyglet import sprite
from core.logger import logger
from core.constants import BFLIM
from core.utils import get_conf_value
from core.window import Window
from core.rendering import (get_program, get_group, quad_indices, polygon_indices,
                             line_loop_to_lines, expand_colors_for_line_loop)


class AbstractWidget:
    def __init__(self, name, container):
        self.name = name
        self.container = container
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


    def add_quad(self, name, group, positions, colors):
        """Register a quad (4 vertices, 2 triangles via indexing)."""
        self.vertex[name] = ('quad', group, positions, colors)

    def add_polygon(self, name, group, positions, colors):
        """Register a convex polygon (fan triangulation via indexing)."""
        self.vertex[name] = ('polygon', group, positions, colors)

    def add_lines(self, name, group, positions, colors):
        """Register GL_LINES segments."""
        self.vertex[name] = ('lines', group, positions, colors)

    def add_triangles(self, name, group, positions, colors):
        """Register GL_TRIANGLES."""
        self.vertex[name] = ('triangles', group, positions, colors)

    def add_line_loop(self, name, group, positions, colors):
        """Register a line loop (converted to GL_LINES on batch assignment)."""
        self.vertex[name] = ('line_loop', group, positions, colors)


    def show_aoi_highlight(self):
        """Add some AOI vertices (frame and text)"""
        if self.container is None:
            return

        if self.highlight_aoi is True:
            self.border_vertice = self.vertice_border(self.container)
            self.add_lines('highlight', G(self.m_draw+8),
                           self.vertice_strip(self.border_vertice), C['RED'] * 8)

            self.vertex[self.name] = Label(self.name, x=self.container.x1 + 5,
                                           y=self.container.y1 - 15, color=C['RED'],
                                           group=G(self.m_draw+8))


    def assign_vertices_to_batch(self):
        program = get_program()
        batch = Window.MainWindow.batch
        for name, v_def in self.vertex.items():
            if isinstance(v_def, (Label, HTMLLabel, sprite.Sprite)):
                v_def.batch = batch
            else:
                kind, group, positions, colors = v_def
                sg = get_group(order=group.order, parent=group.parent)
                count = len(positions) // 2

                if kind == 'quad':
                    indices = quad_indices(count)
                    self.on_batch[name] = program.vertex_list_indexed(
                        count, GL_TRIANGLES, indices, batch=batch, group=sg,
                        position=('f', positions), colors=('Bn', colors))
                elif kind == 'polygon':
                    indices = polygon_indices(count)
                    self.on_batch[name] = program.vertex_list_indexed(
                        count, GL_TRIANGLES, indices, batch=batch, group=sg,
                        position=('f', positions), colors=('Bn', colors))
                elif kind == 'line_loop':
                    new_pos, new_count = line_loop_to_lines(positions)
                    new_colors = expand_colors_for_line_loop(colors, count)
                    self.on_batch[name] = program.vertex_list(
                        new_count, GL_LINES, batch=batch, group=sg,
                        position=('f', new_pos), colors=('Bn', new_colors))
                elif kind in ('lines', 'triangles'):
                    gl_mode = GL_TRIANGLES if kind == 'triangles' else GL_LINES
                    self.on_batch[name] = program.vertex_list(
                        count, gl_mode, batch=batch, group=sg,
                        position=('f', positions), colors=('Bn', colors))


    def empty_batch(self):
        for name in list(self.vertex.keys()):
            if isinstance(self.vertex[name], (Label, HTMLLabel)):
                self.vertex[name].batch = None
            else:
                self.on_batch[name].delete()
                del self.on_batch[name]

        self.on_batch = dict()


    def resize_quad(self, name, new_count):
        """Resize an indexed quad vertex list, recalculating indices."""
        vlist = self.on_batch[name]
        new_indices = quad_indices(new_count)
        vlist.resize(new_count, len(new_indices))
        vlist.indices[:] = new_indices


    def get_positions(self, name):
        """Read vertex positions back as a list."""
        return list(self.on_batch[name].position[:])


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
