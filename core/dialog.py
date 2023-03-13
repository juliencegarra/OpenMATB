from pyglet.gl import GL_POLYGON
from pyglet_gui.theme import Theme
from pyglet_gui.gui import Label, Frame, SectionHeader
from pyglet_gui.manager import Manager
from pyglet_gui.buttons import Button
from pyglet_gui.containers import VerticalContainer, HorizontalContainer

from pyglet.window import Window
from pyglet.graphics import Batch
import pyglet.text
import pyglet.app

from core import logger
from core.constants import COLORS as C, FONT_SIZES as F, Group as G


class Dialog(Manager):
	def __init__(self, win, name, msg, buttons=['OK'], exit_button=None, hide_background=True, title=None):
		self.name = name
		self.hide_background = hide_background
		self.win = win
		self.win.modal_dialog = True
		
		if hide_background:
			MATB_container = win.get_container('fullscreen')
			l, b, w, h = MATB_container.get_lbwh()
			self.backv = win.batch.add(4, GL_POLYGON, G(20), ('v2f/static', (l, b+h, l+w, b+h, l+w, b, l, b)),
													('c4B', C['BACKGROUND'] * 4))

		button_strip = list()
		for b in buttons:
			met = self.on_exit if b == exit_button else self.on_delete
			button_strip.append(None)
			button_strip.append(Button(b, on_press=met))
		button_strip.append(None)
		
		vert_strip = [SectionHeader('Titre')] if title is not None and len(title) > 0 else list()
		vert_strip.extend([Label(msg), HorizontalContainer(button_strip)])

		super().__init__(content=Frame(VerticalContainer(vert_strip)),
						 window=win, batch=win.batch, group=G(21), theme=DIALOG_THEME)
		logger.log_manual_entry(f"{name} start", key='Dialog')

	def on_delete(self, dt):
		if self.hide_background:
			self.backv.delete()
		self.delete()
		self.win.modal_dialog = False
		logger.log_manual_entry(f"{self.name} end", key='dialog')

	def on_exit(self, dt):
		self.on_delete(0)
		self.win.alive = False



def fatalerror(msg):
	batch = Batch()
	fatalwin = Window(style=Window.WINDOW_STYLE_BORDERLESS, width=400, height=250)
	pyglet.gl.glClearColor(*C['BACKGROUND'])  # background definition
	
	m = 40  # margin
	title = pyglet.text.Label('OpenMATB – fatal error !', font_name='sans', font_size=F['MEDIUM'], color=C['BACKGROUND'],
                              x=fatalwin.width//2, y=fatalwin.height-18,
                              anchor_x='center', anchor_y='center')

	rectangle = pyglet.shapes.Rectangle(0, fatalwin.height-m, fatalwin.width, m, color=C['BLACK'][0:3], batch=batch)	

	label = pyglet.text.Label(msg, font_name='serif',
    	x=fatalwin.width//2, y=fatalwin.height//2, multiline=True, color=C['BLACK'],
    	anchor_x='center', anchor_y='center', width=fatalwin.width-m*2)

	presskeystr = _('Press any key to exit')
	presskeylabel = pyglet.text.Label(presskeystr, font_name='serif',
    	x=fatalwin.width//2, y=25, color=C['BLACK'],
    	anchor_x='center', anchor_y='center', bold=True)

	@fatalwin.event
	def on_draw():
	    fatalwin.clear()
	    for v in [rectangle, title, label, presskeylabel]:
	    	v.draw()


	@fatalwin.event
	def on_key_press(symbol, modifiers):
		exit(0)

	pyglet.app.run()



DIALOG_THEME = Theme({"font":'serif',
					"font_size": F["MEDIUM"],
				    "font_size_small": F["SMALL"],

				    "gui_color": C["WHITE"],
				    "text_color": C["BLACK"],
				    "highlight_color": C["LIGHTGREY"],
				    "focus_color": C["LIGHTGREY"],

				    "button": {
				        "down": {
				            "focus": {
				                "image": {
				                    "source": "button-highlight.png",
				                    "frame": [8, 6, 2, 2],
				                    "padding": [18, 18, 8, 6]
				                }
				            },
				            "image": {
				                "source": "button-down.png",
				                "frame": [6, 6, 3, 3],
				                "padding": [12, 12, 4, 2]
				            },
				            "text_color": C["WHITE"],
				        },
				        "up": {
				            "focus": {
				                "image": {
				                    "source": "button-highlight.png",
				                    "frame": [8, 6, 2, 2],
				                    "padding": [18, 18, 8, 6]
				                }
				            },
				            "image": {
				                "source": "custom_button.png",
				                "frame": [6, 6, 3, 3],
				                "padding": [12, 12, 4, 2]
				            }
				        },
				    },
				    "frame": {
				        "image": {
				            "source": "custom_panel.png",
				            "frame": [8, 8, 16, 16],
				            "padding": [16, 16, 8, 8]
				            }
				        },
				        "section": {
        "right": {
            "image": {
                "source": "custom_line.png",
                "region": [2, 0, 6, 4],
                "frame": [0, 4, 4, 0],
                "padding": [0, 0, 0, 6]
            }
        },
        "font_size": 14,
        "opened": {
            "image": {
                "source": "book-open.png"
            }
        },
        "closed": {
            "image": {
                "source": "book.png"
            }
        },
        "left": {
            "image": {
                "source": "custom_line.png",
                "region": [0, 0, 6, 4],
                "frame": [2, 4, 4, 0],
                "padding": [0, 0, 0, 6]
            }
        },
        "center": {
            "image": {
                "source": "custom_line.png",
                "region": [2, 0, 4, 4],
                "frame": [0, 4, 4, 0],
                "padding": [0, 0, 0, 6]
            }
        }
    }},
					  resources_path='./includes/img/theme')