# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *

class Reticle(AbstractWidget):
    def __init__(self, name, container, win, cursorcolor, target_proportion=0.1):
        super().__init__(name, container, win)

        # Set cursor variables
        self.cursor_relative = [0, 0]
        self.cursor_radius = self.container.w/2 * 0.08
        self.cursor_absolute = self.relative_to_absolute()

        # Set widths
        self.corner_width = 0.07 * self.container.w
        self.graduation_width = 0.023 * self.container.w


        # Compute vertices of X and Y axis
        # First, set one axis and one corner
        cx, cy = self.container.get_center()
        x1, y1, x2, y2 = self.container.get_x1y1x2y2()
        v1 = [cx, cy, x2, cy, x2, y2, x2 - self.corner_width, y2,
              x2, y2, x2, y2 + self.corner_width]
        # On this axis, define five graduations
        gw = self.graduation_width
        for i in range(5):
            v1.extend([cx + ((x2 - cx)/4)*i, cy - (gw + gw*((i+1) % 2)),
                       cx + ((x2 - cx)/4)*i, cy + (gw + gw*((i+1) % 2))])

        # Then copy and rotate this axis three times
        v2 = self.rotate_vertice_list([cx, cy], v1, math.pi/2)
        v3 = self.rotate_vertice_list([cx, cy], v1, math.pi)
        v4 = self.rotate_vertice_list([cx, cy], v1, math.pi + math.pi/2)
        v = v1 + v2 + v3 + v4

        self.add_vertex('axis', len(v)//2, GL_LINES, G(self.m_draw+1), ("v2f/static", v),
                        ('c4B/static', (C['BLACK']*(len(v)//2))))

        # Target area
        self.target_proportion = target_proportion
        self.target_radius = self.container.w/2 * self.target_proportion
        v = self.vertice_circle([self.container.cx, self.container.cy], self.target_radius, 50)

        self.add_vertex('target_area', len(v)//2, GL_POLYGON, G(self.m_draw), ("v2f/static", v),
                        ('c3B/static', ((255, 255, 255)*(len(v)//2))))

        self.add_vertex('target_border', len(v)//2, GL_LINES, G(self.m_draw+1), ("v2f/static", v),
                        ('c4B/static', (C['BLACK']*(len(v)//2))))

        # Cursor definition
        v = self.get_cursor_vertice()
        self.add_vertex('cursor', len(v)//2, GL_LINES, G(self.m_draw+2), ("v2f/stream", v),
                        ('c4B/dynamic', (cursorcolor*(len(v)//2))))


    def set_target_proportion(self, proportion):
        if proportion == self.get_target_proportion():
            return
        self.target_proportion = proportion
        self.target_radius = self.container.w/2 * proportion
        v = self.vertice_circle([self.container.cx, self.container.cy], self.target_radius, 50)
        self.on_batch['target_area'].vertices = self.on_batch['target_border'].vertices = v
        self.logger.record_state(self.name, 'target_proportion', proportion)


    def get_target_proportion(self):
        return self.target_proportion


    def get_cursor_vertice(self):
        v = self.vertice_strip(self.vertice_circle(self.cursor_absolute,
                                                   self.cursor_radius, 20))
        v.extend([self.cursor_absolute[0] - self.cursor_radius, self.cursor_absolute[1],
                  self.cursor_absolute[0] + self.cursor_radius, self.cursor_absolute[1]])
        v.extend([self.cursor_absolute[0], self.cursor_absolute[1] - self.cursor_radius,
                  self.cursor_absolute[0], self.cursor_absolute[1] + self.cursor_radius])
        return v
    

    def is_cursor_in_target(self):
        if self.target_radius > 0:
            return self.is_cursor_in_radius(self.target_radius)
        else:
            return float('nan')
        

    def return_deviation(self):
        return math.sqrt(self.cursor_relative[0]**2 + self.cursor_relative[1]**2)


    def is_cursor_in_radius(self, radius):
        return radius >= math.sqrt((self.container.cx - self.cursor_absolute[0]) ** 2 +
                                   (self.container.cy - self.cursor_absolute[1]) ** 2)


    def set_cursor_position(self, x, y):
        self.cursor_relative = [x, y]
        if self.get_cursor_absolute_position() == self.relative_to_absolute():
            return
        self.cursor_absolute = self.relative_to_absolute()
        v = self.get_cursor_vertice()
        self.on_batch['cursor'].vertices = v
        self.logger.record_state(self.name, 'cursor_relative', (x, y))
        
    
    def get_cursor_absolute_position(self):
        return self.cursor_absolute
    

    def relative_to_absolute(self):
        return [self.cursor_relative[i] + c
                for i, c in zip((0, 1), (self.container.cx, self.container.cy))]


    def set_cursor_color(self, color):
        if color == self.get_cursor_color():
            return
        length = len(self.get_cursor_vertice())//2
        self.on_batch['cursor'].colors[:] = color * length
        self.logger.record_state(self.name, 'cursor_color', color)


    def get_cursor_color(self):
        return self.get_vertex_color('cursor')
