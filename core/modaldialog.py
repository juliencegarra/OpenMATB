# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from pyglet.font import load as load_font
from pyglet.window import key as winkey
import gettext
from pyglet.text import HTMLLabel, Label
from core.container import Container
from core.logger import logger
from pyglet.gl import *
from core.constants import FONT_SIZES as F, PATHS as P, Group as G, COLORS as C

class ModalDialog:
    def __init__(self, window, msg, title='OpenMATB', continue_key='SPACE', exit_key=None):

        # Allow for drawing of transparent vertices
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self.name = title
        self.win = window
        self.win.modal_dialog = self
        self.continue_key = continue_key
        self.exit_key = exit_key

        # Hide background ?
        if self.win.hide_on_pause:
            MATB_container = self.win.get_container('fullscreen')
            l, b, w, h = MATB_container.get_lbwh()
            self.back_vertice = self.win.batch.add(4, GL_POLYGON, G(20), 
                                            ('v2f/static', (l, b+h, l+w, b+h, l+w, b, l, b)),
                                            ('c4B', C['BACKGROUND'] * 4))
        else:
            self.back_vertice = None

        
        # HTML list definition #
        if isinstance(msg, str):
            msg = [msg]

        html = '<center><p><strong><font face=%s>' % self.win.font_name
        html += '%s</font></strong></p></center>' % title
        for m in msg:
            html += '<center><p><font face=%s>' % self.win.font_name
            html += '%s</font></p></center>' % m
        html += '<center><p><em><font face=%s>' % self.win.font_name
        if exit_key is not None:
            html += '[%s]' % _(exit_key.capitalize())
            html += ' %s' % _('Exit')

        if continue_key is not None and exit_key is not None:
            html += '  –  '

        if continue_key is not None:
            html += '[%s]' % _(continue_key.capitalize())
            html += ' %s' % _('Continue')
        html += '</font></em></p></center>'

        self.html_label = HTMLLabel(html, x=0, y=0, anchor_x='center', anchor_y='center', 
                                    group=G(22), batch=self.win.batch, multiline=True, 
                                    width=self.win.width)
        # # # # # # # # # # # #


        # Container definition #
        left_right_margin_px = 20
        top_bottom_margin_px = 10
        # The first, compute the desired container height and width #
        # - Width is the max html width + 2 * left_right_margin
        w = self.html_label.content_width + 2*left_right_margin_px
        # - Line to line computation
        # - Height is number of line * line to line height + 2 margins
        h = self.html_label.content_height + 2*top_bottom_margin_px
        l = self.win.width/2 - w/2
        b = self.win.height/2 - h/2
        self.container = Container('ModalDialog', l, b, w, h)
        l, b, w, h = self.container.get_lbwh()

        # Container background
        import pyglet
        
        self.back_dialog = self.win.batch.add(4, GL_POLYGON, G(21), 
                                              ('v2f/static', (l, b+h, l+w, b+h, l+w, b, l, b)),
                                              ('c4B', C['WHITE_TRANSLUCENT'] * 4))

        # Container border
        glLineWidth(2);
        self.border_dialog = self.win.batch.add(8, GL_LINES, G(21), 
                                               ('v2f/static', (l, b+h, l+w, b+h, 
                                                               l+w, b+h, l+w, b,
                                                               l+w, b, l, b,
                                                               l, b, l, b+h)),
                                               ('c4B', C['GREY'] * 8))

        

        # HTMLLabel placement #
        self.html_label.x = self.container.cx
        self.html_label.y = self.container.cy

        self.vertices = [self.html_label, self.back_dialog, self.border_dialog, self.back_vertice]


    def on_delete(self):
        """The user wants to continue. So only delete the modal dialog"""
        for v in self.vertices:
            if v is not None:
                v.delete()
        logger.log_manual_entry(f"{self.name} end", key='dialog')
        self.win.modal_dialog = None


    def on_exit(self):
        """The user requested to exit OpenMATB"""
        self.on_delete()
        self.win.alive = False


    def on_key_release(self, symbol, modifiers):
        keystr = winkey.symbol_string(symbol)

        if keystr == self.continue_key:
            self.on_delete()

        if self.exit_key is not None and keystr == self.exit_key.upper():
            self.on_exit()