# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *

class PumpFlow(AbstractWidget):
    def __init__(self, name, container, win, label, flow):
        super().__init__(name, container, win)

        self.label = label
        self.flow = flow

        # Pump label #
        self.vertex[self.label] = Label(self.pump_string(0), font_size=F['SMALL'], font_name=self.font_name,
                                         x=self.container.l + self.container.w*0.3,
                                         y=self.container.cy, anchor_x='left',
                                         anchor_y='center', color=C['BLACK'], group=G(self.m_draw+1))

        # Pump arrow #
        v = self.get_triangle_vertice(h_ratio=0.25, x_ratio=-0.05, angle=3*math.pi/2)
        self.add_vertex(f'{self.label}_arrow', 3, GL_TRIANGLES, G(self.m_draw+2),
                        ('v2f/static', v),
                        ('c4B/static', (C['BLACK']*3)))


    def pump_string(self, value):
        return f"{self.label}\t\t\t\t\t\t\t\t\t\t\t\t{value}"


    def set_flow(self, flow):
        if self.pump_string(flow) == self.get_flow():
            return
        self.vertex[self.label].text = self.pump_string(flow)
        self.logger.record_state(self.name, self.label, flow)

    
    def get_flow(self):
        return self.vertex[self.label].text
