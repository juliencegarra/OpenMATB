#! .venv/bin/python3.9

#TODO:
# make dialogs (question dialog, file dialog)
# if 'input' in last log line it seems not handled in replay
# check all buttons events (num_1...)
# add joystick movement to log
# add eyetracking position on display

""" Replay OpenMATB (version 1.0)
"""

import gettext, configparser
from pathlib import Path


# Read the configuration file
config = configparser.ConfigParser()
config.read("config.ini")


# Read and install the specified language iso
# The LOCALE_PATH constant can't be set into constants.py because
# the latter must be translated itself
LOCALE_PATH = Path('.', 'locales')
language_iso = config['Openmatb']['language']
language = gettext.translation('openmatb', LOCALE_PATH, [language_iso])
language.install()

# Only after language installation, import core modules (they must be translated)
from core import Window, Scenario, Scheduler, fatalerror, errorchoice
from core.constants import PATHS as P

# Check the specified screen index. If null, set screen_index to 0.
if len(config['Openmatb']['screen_index']) == 0:
    screen_index = 0
else:
    try:
        screen_index = int(config['Openmatb']['screen_index'])
    except ValueError:
        fatalerror(_(f"In config.ini, screen index must be an integer, not {config['Openmatb']['screen_index']}"))



import os, csv, sys
import pyglet.graphics
from pyglet.gl import *
from pyglet.text import Label
from core.constants import COLORS as C, FONT_SIZES as F, Group as G

sys.path.insert(0,'core')

#import core.pyglet_gui as pyglet_gui
#import pyglet_gui.theme as Theme
#"import core.pyglet_gui.Theme
#from core import pyglet_gui
from pyglet_gui.theme import Theme
from pyglet_gui.gui import Label, Frame
from pyglet_gui.manager import Manager
from pyglet_gui.buttons import Button
from pyglet_gui.containers import HorizontalContainer, VerticalContainer, Container, Spacer
from pyglet_gui.sliders import HorizontalSlider
from pyglet_gui.constants import HALIGN_CENTER, HALIGN_LEFT, HALIGN_RIGHT, \
    VALIGN_TOP, VALIGN_CENTER, ANCHOR_CENTER, GetRelativePoint
from pyglet.window import key as winkey
from pyglet import shapes
from pyglet_gui.core import Viewer


# gui theme for pyglet_gui
theme = Theme({
            "font": "Lucida Grande",
            "font_size": 12,
            "text_color": [255, 255, 255, 255],
            "gui_color": [255, 0, 0, 255],
            "frame": {
               "image": {
                   "source": "panel.png",
                   "frame": [8, 8, 16, 16],
                   "padding": [8, 8, 0, 0]
               }
            },
            "button": {
                "down": {
                    "image": {
                        "source": "button-down.png",
                        "frame": [8, 6, 2, 2],
                        "padding": [18, 18, 8, 6]
                    },
                    "text_color": [0, 0, 0, 255]
                },
                "up": {
                    "image": {
                        "source": "button.png",
                        "frame": [6, 5, 6, 3],
                        "padding": [18, 18, 8, 6]
                    }
                }
            },
            "slider": {
               "knob": {
                   "image": {
                       "source": "slider-knob.png"
                   },
                   "offset": [-5, -11]
               },
               "padding": [8, 8, 8, 8],
               "step": {
                   "image": {
                       "source": "slider-step.png"
                   },
                   "offset": [-2, -8]
               },
               "bar": {
                   "image": {
                       "source": "slider-bar.png",
                       "frame": [8, 8, 8, 0],
                       "padding": [8, 8, 8, 8]
                   }
               }
           }
           }, resources_path='core/img/theme/')



# Class to read OpenMATB logfile, get contents at a specific timestamp.
# Also allow to regenerate scenario used in the experiment

class LogReader:
    def __init__(self, filename):
        self.file = None
        self.contents = {}
        self.min = 0.0
        self.max = 0.0
        self.duration = 0.0

        self.scenario = []

        self.loadFile(filename)

    # get first timestamp to align each timestamp on 0
    def getStartingLogTime(self, filename) -> float:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'logtime' in row:
                    return float(row['logtime'])

        return None


    def loadFile(self, filename):
        self.min = float('inf')
        self.max = -float('inf')

        # we will use a key starting at 0
        startingLogTime = self.getStartingLogTime(filename)

        if startingLogTime==None:
            print("Invalid log file")
            return

        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                #TODO: check key exists
                logtime = float(row['logtime'])-startingLogTime

                if logtime in self.contents:
                    # It should never happen... but if it is the case add an epsilon
                    # not to overwrite existing keys
                    print("Logtime "+str(logtime)+" already exists!")
                    logtime += sys.float_info.epsilon

                if logtime < self.min:
                    self.min = logtime
                if logtime > self.max:
                    self.max = logtime


                self.contents[logtime] = {}
                for key in row:
                    self.contents[logtime][key] = row[key]

        self.duration = self.max-self.min

        self.rebuildScenario()


    def rebuildScenario(self):
        contents = self.getContentsTypeAtTime('event', 0, self.duration)
        for c in contents:
            self.scenario.append(self.getContentsAsScenarioLine(c, contents[c]))


    # get log data in a time period (startTime to endTime)
    def getContentsTypeAtTime(self, contentsType: str, startTime: float, endTime: float):
        contents = {}

        for key in self.contents:
            if key>=startTime and key<endTime and (contentsType == None or self.contents[key]['type']==contentsType):
                contents[key] =self.contents[key]

        return contents


    # convert the scenario line as a csv line that can be used by the OpenMATB engine
    def getContentsAsScenarioLine(self, logTime, logEvent):

        h = int(logTime / 3600)
        m = int((logTime - h * 3600) / 60)
        s = int (logTime - m * 60)

        #rebuild scenario line using logTime as scenario time
        line = str(h)+":"+str(m)+":"+str(s) + ";" + logEvent['module'] + ";"

        if logEvent['address'] != "self":
            line += logEvent['address'] + ";"

        if logEvent['address']=='lights-1-failure':
            line += "True"
        else:
            line += logEvent['value']

        return line



class ReplayOpenMATB:
    def __init__(self):
        self.version = 1.1


        # init variables
        self.last_time = -1
        self.user_input_buttons = {}

        self.log = LogReader("includes/logtest.csv")


        # In OpenMATB, scenario and window are linked together, we cannot
        # create window without loading scenario beforehand

        self.input_file = Scenario(self.log.scenario)
        self.window = Window(screen_index=screen_index, fullscreen=False,
                                 replay_mode=True, style=Window.WINDOW_STYLE_BORDERLESS)
        self.window.on_key_press_replay = self.on_key_press

        self.container_media = self.window.get_container('mediastrip')
        self.container_input = self.window.get_container('inputstrip')



        # Fill the media container (bottom row) with widgets

        label_logTime = Label("Log time: ")
        self.label_logtime = Label(self.get_time_hms_str(0))

        label_scenarioTime = Label("Scenario time: ")
        self.label_scenariotime = Label(self.get_time_hms_str(0))

        self.horizontalSlider = HorizontalSlider(steps=10, on_set=self.on_set_slider, width = self.container_media.w * 0.4)
        self.button_play = Button('>', is_pressed=False, on_press=self.on_play_pressed)


        self.horizontalContainer = HorizontalContainer([
                            Spacer(),
                            self.button_play,
                            Spacer(),
                            self.horizontalSlider,

                            Spacer(),
                            label_logTime,
                            Spacer(),
                            self.label_logtime,

                            Spacer(),
                            label_scenarioTime,
                            Spacer(),
                            self.label_scenariotime,

                            ], align = HALIGN_CENTER, padding=5)

        self.horizontalContainer.width = self.container_media.w*0.8
        self.horizontalContainer.height = self.container_media.h


        # add everything to pyglet_gui manager
        Manager(self.horizontalContainer, window=self.window, theme=theme, batch=self.window.batch)

        self.horizontalContainer.expand(self.container_media.w* 0.8, self.container_media.h)
        self.horizontalContainer.set_position(self.container_media.l, self.container_media.b + self.container_media.h * 0.25)


        # Initialize OpenMATB scheduler

        self.scheduler = Scheduler(self.input_file, self.window, 0, 0)
        self.scheduler.scenario_clock.on_time_changed = self.on_scheduler_scenario_time_changed

        self.createInputBar()
        self.startLog()

        # Initialize eye position widget
        self.display_eye_position(None)



    # Create the right bar with the widgets for keyboard and joystick
    def createInputBar(self):
        keys = self.getAcceptedKeys()


        label_userInputs = Label("User input:")

        items =   [Spacer(),
                   label_userInputs,
                   Spacer(),
                   ]

        self.user_input_buttons = {}

        # in the layout each key is a button + spacer
        for key in keys:
            b = Button(key)
            self.user_input_buttons[key] = b
            items.append(b)
            items.append(Spacer())


        label_joystick = Label("Joystick:")
        items.append(Spacer())
        items.append(label_joystick)
        items.append(Spacer())


        # an empty viewer to space widgets. It is later used to contain a shapes.Circle
        self.joystick_viewer = Viewer(height = self.container_input.w * 0.8)
        items.append(self.joystick_viewer)

        self.verticalContainer = Frame(VerticalContainer(items, align = HALIGN_CENTER, padding=5))


        self.verticalContainer.width = self.container_input.w*0.9
        self.verticalContainer.height = self.container_input.h


        Manager(self.verticalContainer, window=self.window, theme=theme, batch=self.window.batch)


        self.verticalContainer.expand(self.container_input.w*0.8, self.container_input.h)
        self.verticalContainer.set_position(self.container_input.l + self.container_input.w / 10, self.container_input.b)



        # Create both joystick circles
        self.user_input_joystick_background = shapes.Circle(self.joystick_viewer.x + self.joystick_viewer.width / 2, self.joystick_viewer.y + self.joystick_viewer.height / 2, self.joystick_viewer.height *0.4, color=(50, 225, 30), batch=self.window.batch)
        self.user_input_joystick = shapes.Circle(self.joystick_viewer.x + self.joystick_viewer.width / 2, self.joystick_viewer.y + self.joystick_viewer.height / 2, self.joystick_viewer.height *0.1, color=(225, 30, 30), batch=self.window.batch)


    # Determine keys that can be used in the scenario file according to loaded plugins
    def getAcceptedKeys(self):
        accepted_keys = []
        for p in self.scheduler.plugins:
            plugin = self.scheduler.plugins[p]
            keys = plugin.find_response_keys(plugin.parameters, 'key')
            for k in keys:
                if k != '':
                    accepted_keys.append(k)

        accepted_keys.sort()
        return accepted_keys


    # Initialize variables when log is first loaded
    def startLog(self):
        self.horizontalSlider._min_value = 0
        self.horizontalSlider._max_value = self.log.duration
        self.scheduler.move_scenario_time_to(0)
        self.last_time = -1

        self.ignore_knob_change = False


    # convert timestamp to string handling msec if needed
    def get_time_hms_str(self, time_msec):
        s = str(time_msec).split('.')

        time_sec = int(s[0])

        if len(s)>1:
            mseconds = int(s[1][:2])  #limit to 2 values after comma
        else:
            mseconds = int(0)


        seconds = int(time_sec)
        hours = seconds // (60*60)
        seconds %= (60*60)
        minutes = seconds // 60
        seconds %= 60

        return str("%01i:%02i:%02i.%02i" % (hours, minutes, seconds, mseconds))


    # Key press event in the Replay (not the user key event in the log)
    def on_key_press(self, symbol, modifier):
        keystr = winkey.symbol_string(symbol)

        if keystr == 'ESCAPE':
            self.window.exit()
        else:
            print ("pressed key: "+keystr)


    # Replay user pressed the toggle play button
    def on_play_pressed(self, is_pressed):
        if is_pressed:
            if self.last_time == self.log.duration:
                self.startLog()
            self.button_play.label = ">"
            self.scheduler.play_scenario(self.log.duration)
        else:
            self.button_play.label = "||"
            self.scheduler.stop_scenario()


    # User modified the slider knob position
    def on_set_slider(self, value):

        if not self.ignore_knob_change:

            #a = self.getNearestLogAtTime(value, self.log.contents)


            self.scheduler.move_scenario_time_to(value)

            if self.button_play.is_pressed:
                self.button_play.change_state()

    def getNearestScenarioTime(self, time, contents):
        best = 0
        diff = float('inf')
        for c in contents:
            if  (abs(time - c)) < diff:
                diff = abs(time-c)
                best = contents[c]['scenariotime']


        return best

    def getNearestLogAtTime(self, time, contents):
        best = None
        diff = float('inf')
        for c in contents:
            if  (abs(time - c)) < diff:
                diff = abs(time-c)
                best = c

        return best


    def display_eye_position(self, position):
        w, h = (1-self.window.replay_margin_w) * self.window.width, (1 - self.window.replay_margin_h)*self.window.height
        b = self.window.height*self.window.replay_margin_h


        pos_x = 50
        pos_y = 100
##        if position == None:
##            pos_x = -1000
##            pos_y = -1000


        rx = pos_x
        ry = h - pos_y
        size = h/40


        self.eye = shapes.Circle(rx, ry, size, color=(225, 30, 30), batch=self.window.batch)


    # Update keyboard action in the input bar
    def display_user_actions(self, contents):
        for c in contents:
            if contents[c]['type']=='input':
                address = contents[c]['address']
                if address in self.user_input_buttons:
                    button = self.user_input_buttons[address]
                    if contents[c]['value'] == "press":
                        if not button.is_pressed:
                            button.change_state()
                    elif contents[c]['value'] == "release":
                        if button.is_pressed:
                            button.change_state()
            elif contents[c]['type']=='joystick':
                #address = contents[c]['address']
                #if address == 'center_deviation':
                    print(contents[c])
            elif contents[c]['type']=='performance':
                #display performance values?
                pass


    # The timer change over scenario time
    def on_scheduler_scenario_time_changed(self, time):
        value = float(max(0, min(self.log.duration, time)))

        if value != self.last_time:

            self.ignore_knob_change = True
            self.horizontalSlider.set_knob_pos(value / self.log.duration)
            self.ignore_knob_change = False

            contents = self.log.getContentsTypeAtTime(None, self.last_time, value)

            if len(contents)>0:

                self.last_time = value

                a = self.getNearestLogAtTime(time, contents)

                line = contents[a]

                self.label_logtime.set_text(self.get_time_hms_str(a))

                #scenarioTime = self.getNearestScenarioTime(value, contents)
                self.label_scenariotime.set_text(self.get_time_hms_str(line['scenariotime']))

                self.display_user_actions(contents)

                #self.label_time._update()
                self.window.batch.invalidate()

            if value == self.log.duration:
                self.on_end_play()


    # event called when the play mode arrived on last timestamp
    def on_end_play(self):
        self.button_play.change_state()

    def run(self):
        self.scheduler.run()

if __name__ == '__main__':
    app = ReplayOpenMATB()
    app.run()