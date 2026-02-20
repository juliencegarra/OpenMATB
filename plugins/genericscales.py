# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from plugins.abstractplugin import BlockingPlugin
from core.widgets import Simpletext, Slider, Frame
from core.constants import FONT_SIZES as F, PATHS as P, COLORS as C, REPLAY_MODE
from re import match as regex_match
from pyglet.text import Label as PygletLabel
from core.container import Container
from core.utils import get_conf_value

class Genericscales(BlockingPlugin):
    def __init__(self):
        super().__init__()

        self.folder = P['QUESTIONNAIRES']
        new_par = dict(filename=None, pointsize=0, maxdurationsec=0,
                       response=dict(text=_('Press SPACE to validate'), key='SPACE'),
                       allowkeypress=True, showvalue=False)
        self.sliders = dict()
        self.parameters.update(new_par)

        self.ignore_empty_lines = True

        self.regex_scale_pattern = r'(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)'
        self.question_height_ratio = 0.1  # question + response slider
        self.question_interspace = 0.05  # Space to leave between two questions
        self.top_to_top = self.question_interspace + self.question_height_ratio


    def _measure_text_height(self, text, font_size, wrap_width_px, bold=False):
        font_name = get_conf_value('Openmatb', 'font_name')
        tmp = PygletLabel(text, font_size=font_size, multiline=True,
                          width=wrap_width_px, bold=bold, font_name=font_name)
        return tmp.content_height

    def make_slide_graphs(self):
        # Remove old slider/label widgets from previous slide
        for key in list(self.sliders):
            fullname = self.get_widget_fullname(key)
            self.widgets.pop(fullname, None)
            label_fullname = self.get_widget_fullname(key.replace('slider_', 'label_'))
            self.widgets.pop(label_fullname, None)
            title_fullname = self.get_widget_fullname(key.replace('slider_', 'title_'))
            self.widgets.pop(title_fullname, None)
        self.sliders.clear()

        super().make_slide_graphs()

        scales = self.current_slide.split('\n')
        scale_list = [s.strip() for s in scales if len(s.strip()) > 0]
        if len(scale_list) == 0:
            return

        all_scales_container = self.container.get_reduced(1, self.top_to_top*(len(scale_list)))

        height_in_prop = (self.question_height_ratio * self.container.h)/all_scales_container.h
        for l, scale in enumerate(scale_list):

            # Define the scale main container (question + response slider)
            scale_container = all_scales_container.reduce_and_translate(
                height=height_in_prop, y=1-(1/(len(scale_list)))*l)

            if regex_match(self.regex_scale_pattern, scale):
                title, label, limit_labels, values = scale.strip().split(';')
                label_min, label_max = limit_labels.split('/')
                value_min, value_max, value_default = [int(v) for v in values.split('/')]

                show_title = (title != label)

                if show_title:
                    wrap_px = scale_container.w * 0.8
                    padding = 4

                    title_h = self._measure_text_height(title, F['MEDIUM'], wrap_px, bold=True) + padding
                    question_h = self._measure_text_height(label, F['MEDIUM'], wrap_px) + padding

                    min_slider_h = scale_container.h * 0.40
                    slider_h = max(min_slider_h, scale_container.h - title_h - question_h)

                    text_budget = scale_container.h - slider_h
                    if title_h + question_h > text_budget and text_budget > 0:
                        ratio = text_budget / (title_h + question_h)
                        title_h *= ratio
                        question_h *= ratio

                    L, B, W, H = scale_container.l, scale_container.b, scale_container.w, scale_container.h
                    title_container = Container('title', L, B + H - title_h, W, title_h)
                    question_container = Container('question', L, B + H - title_h - question_h, W, question_h)
                    slider_container = Container('slider', L, B, W, slider_h)

                    self.add_widget(f'title_{l+1}', Simpletext,
                                    container=title_container,
                                    text=title, wrap_width=0.8,
                                    font_size=F['MEDIUM'], bold=True,
                                    draw_order=self.m_draw)
                else:
                    question_container = scale_container.reduce_and_translate(1, 0.4, 0, 1)
                    slider_container = scale_container.reduce_and_translate(1, 0.6, 0, 0)

                self.add_widget(f'label_{l+1}', Simpletext,
                                container=question_container,
                                text=label, wrap_width=0.8, font_size=F['MEDIUM'],
                                draw_order=self.m_draw)

                self.sliders[f'slider_{l+1}'] = self.add_widget(f'slider_{l+1}', Slider,
                                container=slider_container,
                                title=title, label_min=label_min, label_max=label_max,
                                value_min=value_min, value_max=value_max,
                                value_default=value_default, rank=l, draw_order=self.m_draw+3,
                                interactive=not REPLAY_MODE,
                                showvalue=self.parameters['showvalue'])


    def refresh_widgets(self):
        # Useful for replay mode (refresh groove positions)
        if not super().refresh_widgets():
            return

        for slider_name, slider in self.sliders.items():
            slider.update()



    def stop(self):
        for slider_name, slider_widget in self.sliders.items():
            self.log_performance(slider_widget.get_title(), slider_widget.get_value())
        super().stop()


