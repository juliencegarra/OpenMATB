# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *

class Timeline(AbstractWidget):
    def __init__(self, name, container, win, max_time_minute):
        super().__init__(name, container, win)
        self.max_time_minute = int(max_time_minute)
        self.graduation_width = 0.41 * self.container.w
        self.unit_padding = 0.06 * self.container.h
        self.draw_timeline()

    def draw_timeline(self):
        self.vertex = dict()
        interval_n = self.max_time_minute * 2
        x1, y1, x2, y2 = self.container.get_x1y1x2y2()
        v = [x2, y1, x2, y2]
        for i, this_y in enumerate([y1 + i * ((y2-y1)/interval_n) for i in range(interval_n + 1)]):
            size = self.graduation_width/2 if i % 2 != 0 else self.graduation_width
            v.extend([x2 - size, this_y, x2, this_y])

        self.add_vertex('lines', len(v)//2, GL_LINES, G(self.m_draw+1), ('v2f/static', v),
                                 ('c4B/static', (C['BLACK']*(len(v)//2))))

        for i, this_y in enumerate([y1 + i * ((y2-y1)/self.max_time_minute)
                                    for i in range(self.max_time_minute + 1)]):
            self.vertex[f'label_{i}'] = Label(str(i), font_size=F['MEDIUM'], x=x1, font_name=self.font_name,
                                              y=this_y, anchor_x='left', anchor_y='center',
                                              color=C['BLACK'], group=G(1))

        self.vertex['unit'] = Label(_('min.'), font_size=F['SMALL'], x=self.container.l, font_name=self.font_name,
                              y=self.container.y2 - self.unit_padding, anchor_x='center', anchor_y='center',
                              color=C['BLACK'], italic=True, group=G(1))

    def set_max_time(self, max_time_minute):
        if max_time_minute == self.get_max_time():
            return
        self.hide()
        self.remove_all_vertices()
        self.max_time_minute = max_time_minute
        self.draw_timeline()
        self.show()
        self.logger.record_state(self.name, 'max_time_minute', max_time_minute)


    def get_max_time(self):
        return self.max_time_minute
