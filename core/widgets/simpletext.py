# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.widgets.abstractwidget import *
from core.constants import FONT_SIZES as F
from core.constants import COLORS as C


class Simpletext(AbstractWidget):
    def __init__(self, name, container, win, text, draw_order=1, font_size=F['SMALL'], x=0.5, y=0.5, wrap_width=1,
                 color=C['BLACK'], bold=False):
        super().__init__(name, container, win)

        x = self.container.l + x * self.container.w
        y = self.container.b + y * self.container.h
        wrap_width = self.container.w * wrap_width

        self.vertex['text'] = Label(text, font_size=font_size, x=x, y=y, align='center',
                                    anchor_x='center', anchor_y='center', color=color,
                                    group=G(draw_order), multiline=True, width=wrap_width, bold=bold,
                                    font_name=self.font_name)
        
        #TODO   Is this first log needed ?
        #self.logger.record_state(self.name, 'text', text)


    def set_text(self, text):
        if text == self.get_text():
            return
        self.vertex['text'].text = text
        self.logger.record_state(self.name, 'text', text)


    def get_text(self):
        return self.vertex['text'].text
