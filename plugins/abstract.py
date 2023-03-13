from pathlib import Path
from pyglet.window import key as winkey
from core.widgets import Simpletext, SimpleHTML, Frame
from core.constants import *
from core import Container, logger


class AbstractPlugin:
    """Any plugin (or task) depends on this meta-class"""
    def __init__(self, window, taskplacement='fullscreen', taskupdatetime=-1):

        self.alias = self.__class__.__name__.lower()  #   A lower version of the plugin class name
        self.widgets = dict()                         #   To store the widget objects of a plugin
        self.win = window                             #   The window to which the plugin is attached
        self.container = None                         #   The visual area of the plugin (object)
        self.logger = logger

        self.can_receive_keys = False
        self.keys = list()                            #   Handle the keys that are allowed
        self.display_title = taskplacement != 'invisible'
        self.automode_string = str()

        self.next_refresh_time = 0
        self.scenariotime = 0

                                            #  If True
        self.blocking = False               # :blocks all other plugins when alive
        self.alive = False                  # :is started and not yet stopped
        self.paused = True                  # :is not updated and cannot receive inputs
        self.visible = False                # :all the plugins widgets are shown
        self.verbose = False

        self.parameters = dict(title=M[self.alias], taskplacement=taskplacement,
                               taskupdatetime=taskupdatetime,
                               taskfeedback=dict(overdue=dict(active=False, color=C['RED'],
                                                              delayms=2000,
                                                              blinkdurationms=1000)))

        # Private parameters
        self.parameters['taskfeedback']['overdue'].update({'_nexttoggletime':0, '_is_visible':False})

        # Define minimal draw order depending on task placement
        self.m_draw = BFLIM if self.parameters['taskplacement'] == 'fullscreen' else 0

        if not self.win.is_in_replay_mode():
            self.win.push_handlers(self.on_key_press, self.on_key_release)


    # def initialize(self, window):
        # self.win = window

        


    def update(self, scenariotime):
        self.scenariotime = scenariotime
        self.compute_next_plugin_state()
        self.refresh_widgets()


    # State handling
    def show(self):
        """
            Showing means display widgets, but also removing a potential masking foreground.
        """
        if self.is_visible():
            return
        
        if self.verbose:
            print('Show ', self.alias)
        self.visible = True
        self.update_can_receive_key()

        for name, widget in self.widgets.items():
            widget.show()


    def hide(self):
        """
            Hiding means showing a neutral foreground before the plugin for non-blocking plugins
            and destroying the title.
            It can mean, also, hiding (destroy) widgets for a fullscreen (blocking) plugin
        """
        if not self.is_visible():
            return
        if self.verbose:
            print('Hide ', self.alias)
        self.visible = False
        self.update_can_receive_key()


        if self.parameters['taskplacement'] == 'fullscreen':
            for name, widget in self.widgets.items():
                widget.hide()

        elif self.parameters['taskplacement'] != 'invisible':
            self.get_widget('task_title').hide()

            # Resman case (manage status if relevant)
            if self.get_widget('status_title') is not None:
                self.get_widget('status_title').hide()
            
            if self.get_widget('foreground') is not None:
                self.get_widget('foreground').show()

        # if self.win._mouse_visible == True:
        #     self.win.set_mouse_visible(self.win.replay_mode)


    def pause(self):
        if self.verbose:
            print('Pause ', self.alias)
        self.paused = True
        self.update_can_receive_key()


    def resume(self):
        if self.verbose:
            print('Resume ', self.alias)
        self.paused = False
        self.update_can_receive_key()


    def start(self):
        if self.verbose:
            print('Start ', self.alias)
        self.alive = True
        if len(self.keys) == 0:  # Because communications keys are already defined
            self.keys = self.find_response_keys(self.parameters, 'key')
        self.create_widgets()
        self.show()
        self.resume()


    def stop(self):
        if self.verbose:
            print('Stop ', self.alias)
        self.alive = False
        self.pause()
        self.hide()


    def is_a_widget_name(self, name):
        return self.get_widget_fullname(name) in self.widgets


    def is_visible(self):
        return self.visible is True
    
    
    def is_paused(self):
        return self.paused is True


    def get_widget_fullname(self, name):
        return f'{self.alias}_{name}'


    def get_widget(self, name):
        if not self.is_a_widget_name(name):
            return
        return self.widgets[self.get_widget_fullname(name)]


    def get_response_timers(self):
        '''Return the time since which responses are expected (list of int)'''
        pass


    def update_can_receive_key(self):
        if self.paused is True or not self.is_visible():
            self.can_receive_keys = False
        else:
            if 'automaticsolver' in self.parameters:
                self.can_receive_keys = not self.parameters['automaticsolver']
            else:
                self.can_receive_keys = True


    def compute_next_plugin_state(self):
        if not self.scenariotime >= self.next_refresh_time or self.is_paused():
            return 0
        if self.verbose:
            print(self.alias, 'Compute next state')
        
        self.next_refresh_time = self.scenariotime + self.parameters['taskupdatetime']/1000

        # Should an automation state (string) be displayed ?
        if 'displayautomationstate' in self.parameters and self.parameters['displayautomationstate']:
            if 'automaticsolver' in self.parameters:
                self.automode_string = _('MANUAL') if not self.parameters['automaticsolver'] else _('AUTO')
            else:
                self.automode_string = _('MANUAL')
        else:
            self.automode_string = ''
        return 1



    def refresh_widgets(self):
        if not self.is_visible():
            return 0
        
        if self.get_widget('foreground') is not None:
            self.get_widget('foreground').set_visibility(False)

        # Refresh some visual information if need be
        if self.get_widget('automode') is not None:
            self.get_widget('automode').set_text(self.automode_string)

        if self.display_title == True:
            self.get_widget('task_title').set_text(self.parameters['title'].upper())
            
            
        # Update the overdue feedback state if relevant
        # Overdue state computing is here to unmerge its temporal
        # logic from the taskupdatetime parameter (so the alarm
        # does not have to wait for plugin update to blink)
        overdue = self.parameters['taskfeedback']['overdue']
        if overdue['active'] and self.get_response_timers() is not None:
            # Should an alarm be displayed ?
            if any([rt > overdue['delayms'] for rt in self.get_response_timers()]):
                if overdue['blinkdurationms'] == 0: # No blink case
                    #overdue['widget'].set_visibility(True)
                    overdue['_is_visible'] = True
                else:  # Blink case
                    if overdue['_nexttoggletime'] == 0:  # First toggle
                        overdue['_nexttoggletime'] = self.scenariotime
                    
                    if self.scenariotime >= overdue['_nexttoggletime']:
                        overdue['_nexttoggletime'] += overdue['blinkdurationms']/1000
                        overdue['_is_visible'] = not overdue['_is_visible']
            else:
                overdue['_blinktimer'] = 0
                overdue['_is_visible'] = False
        else:
            overdue['_is_visible'] = False
        
        if 'widget' in overdue:
            overdue['widget'].set_visibility(overdue['_is_visible'])
            overdue['widget'].set_border_color(overdue['color'])
        return 1


    def find_response_keys(self, search_dict, field):
        # https://stackoverflow.com/questions/14962485/finding-a-key-recursively-in-a-dictionary
        fields_found = []

        for key, value in search_dict.items():
            if key == field:
                fields_found.append(value)

            elif isinstance(value, dict):
                results = self.find_response_keys(value, field)
                for result in results:
                    fields_found.append(result)

            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        more_results = self.find_response_keys(item, field)
                        for another_result in more_results:
                            fields_found.append(another_result)

        return fields_found


    def filter_key(self, symbol):
        if self.can_receive_keys == True:
            sym_string = winkey.symbol_string(symbol)
            keystr = sym_string if sym_string in self.keys else None
            return keystr
        else:
            return None


    def on_key_press(self, symbol, modifiers):
        key = self.filter_key(symbol)
        self.do_on_key(key, 'press')


    def on_key_release(self, symbol, modifiers):
        key = self.filter_key(symbol)
        self.do_on_key(key, 'release')


    def do_on_key(self, key, state):   # JC: pour le solver, devrait prendre un parametre is_solver_action pour separer de vraies actions du participant
        pass


    def is_key_state(self, key, is_pressed):
        if key in self.win.keyboard:
            return self.win.keyboard[key] == is_pressed
        else:
            return None


    def create_widgets(self):
        pthp = PLUGIN_TITLE_HEIGHT_PROPORTION

        self.container = self.win.get_container(self.parameters['taskplacement'])
        self.title_container = self.container.reduce_and_translate(height=pthp,   y=1)
        self.task_container  = self.container.reduce_and_translate(height=1-pthp, y=0)

        # A fullscreen plugin must have its proper background to override the MATB black middle band
        if self.parameters['taskplacement'] == 'fullscreen':
            self.add_widget('background', Frame, self.container, fill_color=C['BACKGROUND'],
                            draw_order=self.m_draw)

        # Other plugins which are not invisible must have a foreground so they can hide
        # Also : add overdue feedback widget to visible plugins
        elif self.parameters['taskplacement'] != 'invisible':
            self.add_widget('foreground', Frame, self.task_container, fill_color=C['BACKGROUND'],
                            draw_order=self.m_draw+10)
            self.parameters['taskfeedback']['overdue']['widget'] = self.add_widget('overdue', Frame,
                            container=self.task_container, border_thickness=0.025,
                            border_color=C['RED'], fill_color=None)


        if self.display_title == True:
            self.add_widget('task_title', Simpletext, container=self.title_container,
                            text=self.parameters['title'].upper(), color=C['WHITE'],
                            font_size=F['MEDIUM'])

        if 'displayautomationstate' in self.parameters.keys():
            if self.parameters['displayautomationstate'] is True:
                position = self.automode_position if hasattr(self, 'automode_position') else (0.5, 0.5)
                autocont = self.container.reduce_and_translate(width=0.15, height=0.05, x=position[0],
                                                                                       y=position[1])
                self.add_widget('automode', Simpletext, container=autocont,
                               text=self.automode_string, x=0.5, y=0.5)



    def add_widget(self, name, cls, container, **kwargs):
        fullname = self.get_widget_fullname(name)
        self.widgets[fullname] = cls(fullname, container, self.win, **kwargs)

        # Record the area coordinates of the widget if it has a container
        if container is not None:
            self.logger.record_aoi(container, fullname)

        return self.widgets[fullname]


    def set_parameter(self, keys_str, value):
        keys_list = keys_str.split('-')
        dic = self.parameters
        for key in keys_list[:-1]:
            dic = dic.setdefault(key, {})
        dic[keys_list[-1]] = value

        # If a key is changed, renew the self.keys dict
        if 'key' in keys_str:
            self.keys = self.find_response_keys(self.parameters, 'key')
        return dic


    def log_performance(self, name, value):
        if not hasattr(self, 'performance'):
            self.performance = dict()
        if name not in self.performance.keys():
            self.performance[name] = list()
        self.performance[name].append(value)
        self.logger.log_performance(self.alias, name, value)


    def keep_value_between(self, value, down, up):
        return max(min(value, up), down)

    def grouped(self, iterable, n):
        return zip(*[iter(iterable)]*n)


class BlockingPlugin(AbstractPlugin):
    def __init__(self, window, taskplacement='fullscreen', taskupdatetime=15):
        super().__init__(window, taskplacement, taskupdatetime)

        new_par = dict(boldtitle=False)
        self.parameters.update(new_par)

        self.blocking = True
        self.display_title = False

        self.slides = list()
        self.current_slide = None
        self.go_to_next_slide = None
        self.ignore_empty_lines = False

        self.input_path = None
        self.folder = None  # Depends on the nature of blocking plugin (questionnaire, instruction...)
        
        # Should we stop the plugin when the are no more slide available
        # (Useful for the LSL plugin, which has a starting instruction, but
        #  should not be stopped)
        self.stop_on_end = True


    def create_widgets(self):
        super().create_widgets()
        self.go_to_next_slide = True  # So the first slide appears as soon as possible

        # Create an input path if relevant
        
        if self.parameters['filename'] is not None:
            self.input_path = Path('.', self.folder, self.parameters['filename'])

        # Only if this input path exists, retrieve its content into slides (split with <newpage>)
        if self.input_path is not None and self.input_path.exists():
            self.slides.append(str())                      # Create the first slide
            lines = self.input_path.open(encoding='utf8').readlines()
            
            if self.ignore_empty_lines == True:
                lines = [l for l in lines if len(l.strip()) > 0]
                
            for line in lines:
                if '#' not in line:
                    if '<newpage>' in line:
                        self.slides.append(str())   # New slide
                    else:
                        self.slides[-1] += line
        else:
            pass # This should not happen (input_path is checked before the scenario is played)


    def update(self, dt):
        #print(self.paused, self.visible)
        super().update(dt)
        if self.go_to_next_slide == True:
            self.go_to_next_slide = False
            if len(self.slides) > 0:  # Are there remaining slides ?
                self.hide()          # If so retrieve the next slide and show it
                self.current_slide = self.slides[0]; del self.slides[0]
                self.make_slide_graphs()
                self.show()
            else:
                if self.stop_on_end:
                    self.stop()
                else:
                    self.hide()
                    self.blocking = False



    def make_slide_graphs(self):
        # Extract the title from the slide string if relevant
        slide_content = self.current_slide.split('\n')
        title_idx = [i for i,t in enumerate(slide_content) if '<h1>' in t]
        if len(title_idx) > 0:
             # In case multiple title tags, take the last one
            title = slide_content[title_idx[-1]]

            self.add_widget(f'title', SimpleHTML, container=self.container,
                            text=title, wrap_width=1, y=0.9, draw_order=self.m_draw+1)
            del slide_content[title_idx[-1]]

        # Remove a potential previous title
        elif 'instructions_title' in self.widgets:
            del self.widgets['instructions_title']

        # Renew the current slide content
        self.current_slide = '\n'.join(slide_content)

        if self.parameters['allowkeypress'] == True:
            key_name = self.parameters['response']['key'].lower()
            response_text = '<center><p>'+self.parameters['response']['text']+'</p></center>'
            self.add_widget(f'press_{key_name}', SimpleHTML, container=self.container,
                            draw_order=self.m_draw+1, text=response_text, wrap_width=0.5, x=0.5, y=0.1)


    def on_key_press(self, symbol, modifiers):
        if self.parameters['allowkeypress'] == True:
            super().on_key_press(symbol, modifiers)


    def do_on_key(self, key, state):
        super().do_on_key(key, state)
        if key is None:
            return

        # Waiting for the key release to advance one slide at the time
        if key.lower() == 'space' and state == 'release':
            self.go_to_next_slide = True
            


# TODO : Include a Solver class like
# ~ """
# ~ class Solver():
    # ~ def __init__(name: str, block_input: bool, solvermode_string=_('AUTO')):
        # ~ self.name = name
        # ~ self.block_input = block_input
        # ~ self.solvermode_string = display

    # ~ def get_solvermode_string():
        # ~ return self.solvermode_string

    # ~ def on_plugin_update(plugin, *param):
        # ~ if plugin is RESMAN:
            # ~ ...
            # ~ plugin.do_on_key(...)

    # ~ def on_plugin_failure(plugin, *param):
        # ~ if plugin is SYSMON or plugin is communications:
            # ~ ...
            # ~ plugin.do_on_key(...)

# ~ """
