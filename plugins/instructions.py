from plugins.abstract import BlockingPlugin
from core.widgets import Simpletext
from core.constants import FONT_SIZES as F, PATHS as P

class Instructions(BlockingPlugin):
    def __init__(self):
        super().__init__()

        self.folder = P['INSTRUCTIONS']
        new_par = dict(filename=None, pointsize=0, maxdurationsec=0,
                       response=dict(text=_('Press SPACE to continue'), key='SPACE'),
                       allowkeypress=True)
        self.parameters.update(new_par)

    def make_slide_graphs(self):
        super().make_slide_graphs()
        # ~ instr_str = f'instructions_{self.parameters["filename"]}'
        self.add_widget('instructions', Simpletext, container=self.container, 
                        text=self.current_slide, font_size=F['XLARGE'], wrap_width=0.8, 
                        draw_order=self.m_draw+1)
