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
                             line_loop_to_lines, colors_3to4,
                             expand_colors_for_line_loop,
                             GL_POLYGON, GL_QUADS, GL_LINE_LOOP)


class VertexListCompat:
    """Wrapper so that .vertices and .colors work like pyglet 1.5."""
    def __init__(self, vlist):
        self._vlist = vlist

    @property
    def vertices(self):
        return list(self._vlist.position[:])

    @vertices.setter
    def vertices(self, value):
        self._vlist.position[:] = value

    @property
    def colors(self):
        return list(self._vlist.colors[:])

    @colors.setter
    def colors(self, value):
        self._vlist.colors[:] = value

    def delete(self):
        self._vlist.delete()

    def resize(self, count):
        self._vlist.resize(count)


def _parse_format(fmt_string):
    """Parse a pyglet 1.5 vertex format string like 'v2f/static' or 'c4B/dynamic'.

    Returns (prefix, count, type_char, usage) e.g. ('v', 2, 'f', 'static').
    """
    parts = fmt_string.split('/')
    fmt = parts[0]
    usage = parts[1] if len(parts) > 1 else 'static'

    # Parse prefix (v, c), count (2, 3, 4), type (f, B, etc.)
    prefix = fmt[0]
    count = int(fmt[1])
    type_char = fmt[2] if len(fmt) > 2 else 'f'
    return prefix, count, type_char, usage


def _build_vertex_list(batch, count, mode, group, data_pairs, program):
    """Translate a legacy batch.add() call to pyglet 2.x API.

    Args:
        batch: pyglet.graphics.Batch
        count: number of vertices
        mode: GL primitive mode (GL_LINES, GL_TRIANGLES, or sentinel string)
        group: pyglet Group
        data_pairs: list of (format_string, data) tuples
        program: ShaderProgram

    Returns:
        VertexListCompat wrapping the created vertex list
    """
    # Extract vertex and color data from the legacy format tuples
    positions = None
    colors = None
    for fmt_str, data in data_pairs:
        prefix, components, type_char, usage = _parse_format(fmt_str)
        if prefix == 'v':
            positions = data
        elif prefix == 'c':
            if components == 3:
                colors = colors_3to4(data, count)
            else:
                colors = data

    # Determine if we need indexed rendering and what the real GL mode is
    need_indexed = False
    indices = None
    real_mode = mode

    if mode == GL_POLYGON:
        indices = polygon_indices(count)
        real_mode = GL_TRIANGLES
        need_indexed = True
    elif mode == GL_QUADS:
        indices = quad_indices(count)
        real_mode = GL_TRIANGLES
        need_indexed = True
    elif mode == GL_LINE_LOOP:
        # Convert LINE_LOOP to GL_LINES by duplicating vertices
        new_positions, new_count = line_loop_to_lines(positions)
        new_colors = expand_colors_for_line_loop(colors, count)
        positions = new_positions
        colors = new_colors
        count = new_count
        real_mode = GL_LINES
        need_indexed = False

    # Wrap the plain Group in a ShaderGroup for proper shader binding
    shader_group = get_group(order=group.order, parent=group.parent)

    # Build the vertex list
    if need_indexed:
        vlist = program.vertex_list_indexed(
            count, real_mode, indices, batch=batch, group=shader_group,
            position=('f', positions),
            colors=('Bn', colors)
        )
    else:
        vlist = program.vertex_list(
            count, real_mode, batch=batch, group=shader_group,
            position=('f', positions),
            colors=('Bn', colors)
        )

    return VertexListCompat(vlist)


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
        program = get_program()
        for name, v_tuple in self.vertex.items():
            if isinstance(v_tuple, Label) or isinstance(v_tuple, HTMLLabel) or isinstance(v_tuple, sprite.Sprite):
                v_tuple.batch = Window.MainWindow.batch
            else:
                # v_tuple is (count, mode, group, ('v2f/...', data), ('c4B/...', data), ...)
                count = v_tuple[0]
                mode = v_tuple[1]
                group = v_tuple[2]
                data_pairs = v_tuple[3:]
                self.on_batch[name] = _build_vertex_list(
                    Window.MainWindow.batch, count, mode, group, data_pairs, program
                )


    def empty_batch(self):
        for name in list(self.vertex.keys()):
            if isinstance(self.vertex[name], Label) or isinstance(self.vertex[name], HTMLLabel):
                self.vertex[name].batch = None
            else:
                self.on_batch[name].delete()
                del self.on_batch[name]

        self.on_batch = dict()


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
