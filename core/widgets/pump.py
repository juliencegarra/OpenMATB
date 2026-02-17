# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *

class Pump(AbstractWidget):
    def __init__(self, name, container, from_cont, to_cont, pump_n, color, pump_width,
                 y_offset=0):
        super().__init__(name, container)
        width = pump_width

        # If from_container and to_container are aligned (x or y axis)
        if from_cont.cx == to_cont.cx or from_cont.cy == to_cont.cy:
            # Draw a straight line
            self.add_lines('connector_1', G(self.m_draw),
                           (from_cont.cx, from_cont.cy + y_offset, to_cont.cx,
                            to_cont.cy + y_offset), C['BLACK']*2)

            # Draw the pump in the middle of the line
            x1, x2 = min(from_cont.cx, to_cont.cx), max(from_cont.cx, to_cont.cx)
            s = -1 if from_cont.cx > to_cont.cx else 1
            x = x1 + (x2 - x1)/2 + s*width/2
            y = from_cont.cy + y_offset
            w = width if from_cont.cx > to_cont.cx else -width   # Pump width
            h = abs(w)
            self.pump_vertice = (x, y, x + w, y + h/2, x + w, y - h/2)
            self.num_location = (x + w*0.70, y + 2)

        else:  # If not, make an perpendicular node
            y_offset = -y_offset-20
            self.add_lines('connector_1', G(self.m_draw),
                           (from_cont.cx, from_cont.cy, from_cont.cx,
                            to_cont.cy + y_offset), C['BLACK']*2)
            self.add_lines('connector_2', G(self.m_draw),
                           (to_cont.cx, to_cont.cy + y_offset, from_cont.cx,
                            to_cont.cy + y_offset), C['BLACK']*2)

            # And stick the pump to the source tank
            x = from_cont.cx
            y = from_cont.cy + from_cont.h/2 + width*2
            w = width
            self.pump_vertice = (x, y, x - w/2, y - w, x + w/2, y - w)
            self.num_location = (x, y - w/2 - 3)

        self.add_triangles('triangle', G(self.m_draw+1), self.pump_vertice, color*3)

        self.add_lines('border', G(self.m_draw+2),
                       self.vertice_strip(self.pump_vertice), C['BLACK']*6)

        self.vertex['label'] = Label(str(pump_n), font_size=F['SMALL'], font_name=self.font_name,
                                     x=self.num_location[0], y=self.num_location[1],
                                     anchor_x='center', anchor_y='center', color=C['BLACK'],
                                     group=G(self.m_draw+2))

    def set_color(self, color):
        if color == self.get_color():
            return
        self.on_batch['triangle'].colors[:] = color * 3
        self.logger.record_state(self.name, 'triangle', color)

    def get_color(self):
        return self.get_vertex_color('triangle')
