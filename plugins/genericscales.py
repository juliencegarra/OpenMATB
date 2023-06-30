# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from plugins.abstract import BlockingPlugin
from core.widgets import Simpletext, Slider, Frame
from core.constants import FONT_SIZES as F, PATHS as P, COLORS as C
from re import match as regex_match

class Genericscales(BlockingPlugin):
    def __init__(self):
        super().__init__()

        self.folder = P['QUESTIONNAIRES']
        new_par = dict(filename=None, pointsize=0, maxdurationsec=0, 
                       response=dict(text=_('Press SPACE to validate'), key='SPACE'),
                       allowkeypress=True)
        self.sliders = dict()
        self.parameters.update(new_par)
        
        self.ignore_empty_lines = True
        
        self.regex_scale_pattern = r'(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)'
        self.question_height_ratio = 0.1  # question + response slider
        self.question_interspace = 0.05  # Space to leave between two questions
        self.top_to_top = self.question_interspace + self.question_height_ratio
    
    
    def make_slide_graphs(self):
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
            
            text_container = scale_container.reduce_and_translate(1, 0.4, 0, 1)
            slider_container = scale_container.reduce_and_translate(1, 0.6, 0, 0)
            
            if regex_match(self.regex_scale_pattern, scale):
                title, label, limit_labels, values = scale.strip().split(';')
                label_min, label_max = limit_labels.split('/')
                value_min, value_max, value_default = [int(v) for v in values.split('/')]
                
                self.add_widget(f'label_{l+1}', Simpletext, container=text_container,
                                text=label, wrap_width=0.8, font_size=F['MEDIUM'], 
                                draw_order=self.m_draw)
            
                self.sliders[f'slider_{l+1}'] = self.add_widget(f'slider_{l+1}', Slider, 
                                container=slider_container,
                                title=title, label_min=label_min, label_max=label_max,
                                value_min=value_min, value_max=value_max, 
                                value_default=value_default, rank=l, draw_order=self.m_draw+3)


    def refresh_widgets(self):
        # Useful for replay mode (refresh groove positions)
        if super().refresh_widgets() == 0:
            return

        for slider_name, slider in self.sliders.items():
            slider.update()
        

    
    def stop(self):
        for slider_name, slider_widget in self.sliders.items():
            self.log_performance(slider_widget.get_title(), slider_widget.get_value())
        super().stop()
        

