# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from pyglet.text.formats.html import HTMLDecoder
from pyglet.resource import FileLocation
from core.widgets.abstractwidget import *
from core.constants import FONT_SIZES as F
from core.constants import COLORS as C


class SimpleHTML(AbstractWidget):
    def __init__(self, name, container, win, text, draw_order=1, x=0.5, y=0.5, wrap_width=1):
        super().__init__(name, container, win)
        self.win = win
        text = self.preparse(text)

        x = int(self.container.l + x * self.container.w)
        y = int(self.container.b + y * self.container.h)
        wrap_width = int(self.container.w * wrap_width)

        self.vertex['text'] = HTMLLabel(text, x=x, y=y, anchor_x='center',
                                        anchor_y='center', group=G(draw_order), multiline=True, 
                                        width=wrap_width, location=FileLocation('includes/img'))

    def preparse(self, text):
        def get_nearest_size_of_pt(pt):
            # See https://github.com/pyglet/pyglet/blob/master/pyglet/text/formats/html.py
            # Where pyglet HTML sizes are defined
            # TODO: Migrating to pyglet 2 -> real_size font attribute will be usable

            font_sizes = {8: 1, 10: 2, 12: 3, 14: 4, 18: 5, 24: 6, 48: 7}
            diffs = [abs(pt-k) for k, v in font_sizes.items()]
            nearest_key = [k for k,v in zip(list(font_sizes.keys()), diffs) if v == min(diffs)][0]
            # if len(nearest_key) > 1:    # If equality, take greatest
                # nearest_key = nearest_key[0]
            return font_sizes[nearest_key]


        hs = html_sizes = {k:get_nearest_size_of_pt(v) for k,v in F.items()}

        pars_dict = {
        '<h1>':f"<center><strong><font size={hs['XLARGE']} face={self.win.font_name}>",
        '</h1>':f"</font></strong></center><br>",
        '<h2>':f"<center><font size={hs['XLARGE']} face={self.win.font_name}><em>",
        '</h2>':f"</em></font></center><br>",
        '<p>':f"<p><font size={hs['LARGE']} face={self.win.font_name}>",
        '</p>':f"</font></p>"
        }
        
        for b in ['<h1>', '<h2>', '<p>']:
            for bb in [b, b.replace('<', '</')]:
                text = text.replace(bb, pars_dict[bb])
        return text


    def set_text(self, text):
        if text == self.get_text():
            return
        self.vertex['text'].text = self.preparse(text)
        self.logger.record_state(self.name, 'text', text)


    def get_text(self):
        return self.vertex['text'].text