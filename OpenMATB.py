<<<<<<< HEAD:MATB.py
# -*- coding: utf-8 -*-

VERSION = "1.0"
VERSIONTITLE = 'OpenMATB v' + VERSION

# Default directories
DIRECTORY_NAME_PLUGINS = "Plugins"
DIRECTORY_NAME_LOGS = "Logs"
DIRECTORY_NAME_SCENARIOS = "Scenarios"
DIRECTORY_NAME_SCALES = "Scales"

# The name of variable used to interact with plugins.
# Do not touch or everything will break!
PARAMETERS_VARIABLE = "parameters"

# We wait at least one tenth millisecond to update tasks.This is sufficient!
# Will prevent hammering the main loop at <0.06 milliseconds
MAIN_SCHEDULER_INTERVAL = 0.001

global CONFIG
CONFIG = {}



import ctypes
import time
import datetime
import imp
import ast
import sys
import os
import platform
from Helpers import Logger, Translator
from Helpers.Translator import translate as _
import pdb


def OSCriticalErrorMessage(title, msg):
    if platform.system() == "Windows":
        ctypes.windll.user32.MessageBoxW(None, _(msg), VERSIONTITLE + " - " + _(title), 0)
    else:
        print _(title) + ":" + _(msg)
    exit()


# Ensure that Pyside, pygame and rstr are available
try:
    from PySide import QtCore, QtGui
    import rstr
    import pygame
except:
    OSCriticalErrorMessage(
        _("Error"), _("Please check that all required libraries are installed"))


class Main(QtGui.QMainWindow):

    def __init__(self, scenario_fullpath):
        super(Main, self).__init__(parent=None)
        self.setFixedSize(1024, 768)
        self.registeredTaskTimer = []
        self.parameters = {
            'showlabels': True,
            'allowescape': True
        }

        # Preallocate a dictionary to store plugins information
        self.PLUGINS_TASK = {}

        # Store working directory and scenario names
        self.working_directory = os.path.dirname(os.path.abspath(__file__))
        self.scenario_shortfilename = os.path.split(scenario_fullpath)[1]
        self.scenario_directory = os.path.split(scenario_fullpath)[0]
        self.scales_directory = self.working_directory + os.sep + DIRECTORY_NAME_SCALES

        # Check that the plugins folder exists
        if not os.path.exists(DIRECTORY_NAME_PLUGINS):
            self.showCriticalMessage(
                _("Plugins directory does not exist. Check that its name is correct"))

        # Create a ./Logs folder if it does not exist
        if not os.path.exists(DIRECTORY_NAME_LOGS):
            os.mkdir(DIRECTORY_NAME_LOGS)

        # Create a filename for the log file
        # Corresponds to : scenario name + date + .log
        LOG_FILE_NAME = os.path.join(self.scenario_shortfilename.replace(".txt", "").replace(
            " ", "_") + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".log")
        self.LOG_FILE_PATH = os.path.join(DIRECTORY_NAME_LOGS, LOG_FILE_NAME)

        # Initialize a Logger instance with this log filename (see Helpers/Logger.py)
        self.mainLog = Logger.Logger(self, self.LOG_FILE_PATH)
        self.mainLog.addLine(['MAIN', 'INFO', 'SCENARIO', 'FILENAME', self.scenario_shortfilename])

        # Initialize two timing variables
        self.scenarioTimeStr = None
        self.elapsedTime = 0

        # Compute screen dimensions
        # /!\ Be careful : when multiple monitor are present, screen height and width are computed for the widest screen,
        # but the active screen will be used. Therefore you must ensure that the active screen
        # (just click on it before running application) is also the widest.

        self.screen_width = self.width()
        self.screen_height= self.height()
        #screen_widths = [QtGui.QApplication.desktop().screenGeometry(i).width()
        #                 for i in range(0, QtGui.QApplication.desktop().screenCount())]
        #self.screen_width = max(screen_widths)
        #self.screen_index = screen_widths.index(self.screen_width)
        #self.screen_height = QtGui.QApplication.desktop().screenGeometry(
        #    self.screen_index).height()

        # Get current screen
        #current_screen = QtGui.QApplication.desktop().screenNumber(QtGui.QApplication.desktop().cursor().pos())
        #centerPoint = QtGui.QApplication.desktop().screenGeometry(current_screen).center()
        #self.move(centerPoint)

        # Log the computed screen size values
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'WIDTH', str(self.screen_width)])
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'HEIGHT', str(self.screen_height)])

        #  The following dictionary contains all the information about sizes and placements.
        #  control_top/left is the top/left margin
        #  control_height/width defines the plugin height/width
        self.placements = {
            'fullscreen': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height,
                           'control_width': self.screen_width},

            'topleft': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height / 2,
                        'control_width': self.screen_width * (7.0 / 20.1)},

            'topmid': {'control_top': 0, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                       'control_width': self.screen_width * (10.7 / 20.1)},

            'topright': {'control_top': 0, 'control_left': self.screen_width * (5.9 / 20.1) + self.screen_width * (
                    10.6 / 20.1), 'control_height': self.screen_height / 2,
                         'control_width': self.screen_width * (3.6 / 20.1)},

            'bottomleft': {'control_top': self.screen_height / 2, 'control_left': 0, 'control_height':
                self.screen_height / 2, 'control_width': self.screen_width * (5.9 / 20.1)},

            'bottommid': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                          'control_width': self.screen_width * (10.7 / 20.1)},

            'bottomright': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (5.9 / 20.1) +
                                                                                   self.screen_width * (10.6 / 20.1),
                            'control_height': self.screen_height / 2,
                            'control_width': self.screen_width * (3.6 / 20.1)}
        }

        # Turn off Caps Lock and Num Lock if possible (only Windows until now)
        if platform.system() == "Windows":
            self.turnOffKey(0x14)  # Caps Lock
            self.turnOffKey(0x90)  # Num Lock

        # Preallocate variables to handle experiment pauses
        self.experiment_pause = False
        self.experiment_running = True

        # Initialize plugins
        self.load_plugins()
        self.place_plugins_on_screen()
        self.loadedTasks = []

        # Load scenario file
        self.scenariocontents = self.loadScenario(scenario_fullpath)

        if self.parameters['showlabels']:
            self.showlabels()

    def turnOffKey(self, k):
        '''On Windows, use this method to turn off a key defined by the k variable'''
        KEYEVENTF_EXTENTEDKEY = 0x1
        KEYEVENTF_KEYUP = 0x2

        dll = ctypes.WinDLL('User32.dll')

        if dll.GetKeyState(k):
            dll.keybd_event(k, 0x45, KEYEVENTF_EXTENTEDKEY, 0)
            dll.keybd_event(
                k, 0x45, KEYEVENTF_EXTENTEDKEY | KEYEVENTF_KEYUP, 0)


    def runExperiment(self):
        # Initialize a general timer
        if sys.platform == 'win32':
            self.default_timer = time.clock
        else:
            self.default_timer = time.time

        # Update time once to take first scenario instructions (0:00:00) into account
        self.scenarioUpdateTime()
        self.last_time = self.default_timer()

        # Launch experiment
        while self.experiment_running:
            self.scheduler()
            QtCore.QCoreApplication.processEvents()

        sys.exit()

    def showCriticalMessage(self, msg):
        """Display a critical message (msg) in a QMessageBox Qt object before exiting"""

        flags = QtGui.QMessageBox.Abort
        flags |= QtGui.QMessageBox.StandardButton.Ignore

        result = QtGui.QMessageBox.critical(self, VERSIONTITLE + " "+_("Error"),
                                            msg,
                                            flags)

        if result == QtGui.QMessageBox.Abort:
            self.onEnd()
            sys.exit()


    def getPluginClass(self, plugin):
        """Return the Task instance of the given plugin"""
        if plugin == "__main__":
            return self
        else:
            return self.PLUGINS_TASK[plugin]["class"]

    def load_plugins(self):
        """Inform the Main() class with plugins information"""

        # For each plugin that is present in the ./Plugins directory
        for thisfile in os.listdir(DIRECTORY_NAME_PLUGINS):

            # If it is a python file...
            if thisfile.endswith(".py"):

                # Retrieve the plugin name
                plugin_name = thisfile.replace(".py", "")
                module = imp.load_source(plugin_name, os.path.join(
                    self.working_directory, DIRECTORY_NAME_PLUGINS, thisfile))

                # If the plugin has defined a Task class, log it
                if hasattr(module, "Task"):
                    task = module.Task(self)

                    # Check if a parameters dictionary is present
                    if not hasattr(task, 'parameters'):
                        print _("Plugin '%s' is invalid (no parameters data)") % (plugin_name)
                        continue

                    # Initialize a dictionary to store plugin information
                    plugin_name = plugin_name.lower()
                    self.PLUGINS_TASK[plugin_name] = {}
                    self.PLUGINS_TASK[plugin_name]['class'] = task
                    self.PLUGINS_TASK[plugin_name]['TIME_SINCE_UPDATE'] = 0
                    self.PLUGINS_TASK[plugin_name]['taskRunning'] = False
                    self.PLUGINS_TASK[plugin_name]['taskPaused'] = False

                    # Store potential plugin information
                    if 'taskupdatetime' in task.parameters:
                        self.PLUGINS_TASK[plugin_name][
                            "UPDATE_TIME"] = task.parameters['taskupdatetime']
                    else:
                        self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] = None

                    if hasattr(task, "keyEvent"):
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = True
                    else:
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = False
                    self.PLUGINS_TASK[plugin_name]["NEED_LOG"] = True if hasattr(task, "onLog") else False

                    task.hide()
                else:
                    print _("Plugin '%s' is not recognized") % plugin_name

    def showlabels(self):
        # If loaded plugins have an ui_label, display it
        for plugin_name in self.loadedTasks:
            if plugin_name != "__main__":
                if 'ui_label' in self.PLUGINS_TASK[plugin_name]:
                    self.PLUGINS_TASK[plugin_name]['ui_label'].show()

    def place_plugins_on_screen(self):
        """Compute size and position of each plugin, in a 2 x 3 canvas,
        as a function of the taskplacement variable of each plugin"""

        # Compute some sizes as a function of screen height
        LABEL_HEIGHT = self.screen_height / 27
        font_size_pt = int(LABEL_HEIGHT / (5 / 2))

        # Adapt top margin and height to the presence/absence of plugin labels
        if self.parameters['showlabels']:
            for k in self.placements.keys():
                self.placements[k]['control_top'] += LABEL_HEIGHT
                self.placements[k]['control_height'] -= LABEL_HEIGHT

        # Browse plugins to effectively size and place them
        for plugin_name in self.PLUGINS_TASK:
            plugin = self.getPluginClass(plugin_name)

            # Check if the plugin has a taskplacement parameter
            if 'taskplacement' not in plugin.parameters or not plugin.parameters['taskplacement']:
                print _("Plugin '%s' has no placement data. It will not be displayed") %  plugin_name
                continue

            # If so, retrieve it
            placement = plugin.parameters['taskplacement']

            # Plugin placement must match one value of the self.placement dictionary
            if placement in self.placements.keys():
                self.control_top = self.placements[placement]['control_top']
                self.control_left = self.placements[placement]['control_left']
                self.control_height = self.placements[
                    placement]['control_height']
                self.control_width = self.placements[
                    placement]['control_width']

                # If the plugin is not displayed in fullscreen, log information about its area of interest (AOI)
                if placement != 'fullscreen':
                    thisPlacement = self.placements[placement]
                    AOIx = [int(thisPlacement['control_left']), int(
                        thisPlacement['control_left'] + thisPlacement['control_width'])]
                    AOIy = [int(thisPlacement['control_top']), int(
                        thisPlacement['control_top'] + thisPlacement['control_height'])]

                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_X', AOIx])
                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_Y', AOIy])

                    # For each non-fullscreen plugin, show its label if needed
                    if self.parameters['showlabels']:
                        self.PLUGINS_TASK[plugin_name]['ui_label'] = QtGui.QLabel(plugin.parameters['title'].upper(), self)

                        self.PLUGINS_TASK[plugin_name]['ui_label'].setStyleSheet("font: " + str(font_size_pt) + "pt \"MS Shell Dlg 2\"; background-color: black; color: white;")
                        self.PLUGINS_TASK[plugin_name]['ui_label'].setAlignment(QtCore.Qt.AlignCenter)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].resize(self.control_width, LABEL_HEIGHT)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].move(self.control_left, self.control_top - LABEL_HEIGHT)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].hide()

            else:
                self.showCriticalMessage(
                    _("Placement '%s' is not recognized!") % placement)

            # Resize, place and show the plugin itself
            plugin.resize(self.control_width, self.control_height)
            plugin.move(self.control_left, self.control_top)
            plugin.show()


    def timerRegister(self, timer):
        self.registeredTaskTimer.append(timer)


    def loadScenario(self, scenario_file):
        """Convert the scenario file into a dictionary : dict[time][task][listOfcommand]"""

        # Create a dictionary
        scenario_content = {}

        # Read the scenario text file
        with open(scenario_file, 'r') as f:

            # Browse lines
            for lineNumber, scenario_line in enumerate(f):

                # Remove blank lines
                scenario_line = scenario_line.strip()

                # Only consider lines that do not begin with a #
                if not scenario_line.startswith("#") and scenario_line:

                    # Extract information from line : time, task and command (see getCommand below)
                    time, task, command = self.getCommand(lineNumber, scenario_line)

                    # Add the task to the list of loadedTasks
                    if not task in self.loadedTasks and task is not None:
                        self.loadedTasks.append(task)

                    # If the extracted time is not yet present in the scenario dictionary...
                    if time and time not in scenario_content:
                        # ...add it
                        scenario_content[time] = {}

                    # Likewise, if task not in scenario, add it
                    if task and task not in scenario_content[time]:
                        scenario_content[time][task] = []

                    # Finally, add the command at the correct location in the scenario dictionary
                    if command and time and task:
                        scenario_content[time][task].append(command)

        # If scenario is not valid, exit (see validateScenario below)
        if not self.validateScenario(scenario_content):
            sys.exit()

        return scenario_content

    def validateScenario(self, scenario_content):
        """Check that the scenario follows a set of criteria. Output the corresponding boolean value"""

        # Browse the loaded task, ignoring the __main__ one
        for checktask in self.loadedTasks:
            if checktask == "__main__":
                continue

            else:
                howmanyentries = 0
                entries = []
                for k in scenario_content.keys():
                    if checktask in scenario_content[k]:
                        for t in scenario_content[k][checktask]:
                            howmanyentries += 1
                            entries.append(t)

                # Does the scenario contains one or more commands for the task at hand ?
                if howmanyentries == 0:
                    self.showCriticalMessage(_("No entry has been found for the '%s' plugin. Check the scenario file") % checktask )
                    return False

                # Are the start/stop commands present ?
                for thiscommand in ['start']:
                    if thiscommand not in [thisentry[0] for thisentry in entries]:
                        self.showCriticalMessage(_("The '%s' plugin does not admit a %s command. Please fix that") % (checktask, thiscommand))
                        return False

        # Check that the last command of the scenario is an 'end'
        try:
            lasttime = sorted(scenario_content.keys())[-1]
            lasttask = scenario_content[lasttime].keys()[0]

            # Is there more than one task?
            if (len(scenario_content[lasttime].keys()) > 1):
                raise Exception()

            lastcmd = scenario_content[lasttime][lasttask][0][0]

            if lastcmd != "end":
                raise Exception()
        except:
            self.showCriticalMessage(_("The scenario should terminate with a 'end' command"))
            return False

        # Check there is at least one task in the scenario
        # Do not take into account the special case of the "__main__" task
        if len(self.loadedTasks) <= 1:
            self.showCriticalMessage(_("No task is started!"))
            return False

        return True

    def getCommand(self, lineNumber, lineContent):
        """Parse lineContent to time, task and command variables.

            There are 3 possible syntax:
            0:00:00;end => call onEnd in main script
            0:00:00;track;start => call onStart in the track plugins
            0:00:00;track;variable;value=> modify the parameters in the track plugins
         """

        # Retrieve line content, removing white space and using semi-colon as delimiter
        lineList = lineContent.strip().split(';')

        # Check if the length of lineList is correct
        if not 1 < len(lineList) < 5:
            self.showCriticalMessage(_("Error. Number of value is incorrect. See line")+" " + str(lineNumber) + ' (' + str(lineContent) + ')')
            return None, None, None

        # Manage the special case of main (0:00:00;start)
        elif len(lineList) == 2:
            lineList.insert(1, "__main__")

        # (there is no * to unpack variable sized list in python2.7 (time, task, *command))
        time, task, command = lineList[0], lineList[1], lineList[2:]

        if task == "__main__":
            taskclass = self
        elif task in self.PLUGINS_TASK:
            taskclass = self.getPluginClass(task)
        else:
            self.showCriticalMessage(
                _("'%s' plugin: unknown\n\nLINE: %s") % (task, str(lineNumber)))
            return None, None, None

        # When only one command, concatenate it with the 'on' chain (e.g. start leads to onStart)
        # onCommand functions are called into the plugins
        if len(command) == 1:
            functionname = "on" + command[0].capitalize()

            # If the onCommand does not exist...
            if not hasattr(taskclass, functionname) and functionname not in ["onStart", "onStop", "onPause",
                                                                             "onResume"]:

                # signal it.
                errorcaller = ""
                if task != "__main__":
                    errorcaller = "' in '" + task

                self.showCriticalMessage(
                    _("'%s' not found!\n\nLINE: %s") % (functionname + errorcaller, str(lineNumber)))
                return None, None, None
            else:
                return time, task, command

        # For the other variables, check that there are corrects (available in the plugin)
        else:
            if taskclass == self:
                self.showCriticalMessage(
                    _("The main script parameters should not be called, use a task instead!\n\nLINE: %s") % str(lineNumber))
                return None, None, None

            if not hasattr(taskclass, PARAMETERS_VARIABLE):
                self.showCriticalMessage(
                    _("'%s' should have a parameters dictionary!\n\nLINE: %s") % (task, str(lineNumber)))
                return None, None, None

            if not self.testParameterVariable(task, taskclass, command[0]):
                self.showCriticalMessage(
                    _("Variable '%s' unknown in task '%s'\n\nLINE: %s") % (str(command [0]), task, str(lineNumber)))
                return None, None, None

        return time, task, command


    def testParameterVariable(self, task, taskclass, adress):
        """Check that a given variable is present in the parameters dictionary of the plugin"""

        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        adress = adress.split('-')

        for i in range(0, len(adress)):
            k = str(adress[i])
            if isinstance(current, dict):
                if k in current:
                    current = current.get(k, None)  # getattr(current, k)

                else:
                    self.showCriticalMessage(
                        _("Variable '%s' unknown in task '%s'") % (k, task))
                    return False
            else:
                # Requires a dictionary...
                self.showCriticalMessage(
                    _("Plugin '%s' has a malformed '%s' variable") % (task, PARAMETERS_VARIABLE))
                return False

        return True

    def setParameterVariable(self, task, taskclass, variable, value):
        """Set a variable to its value, after having convert it to the correct type"""
        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        command = variable.split("-")

        for e in range(0, len(command) - 1):  # range(0,0) = []
            current = current.get(command[e], None)

        t = type(current[command[-1]])
        if current[command[-1]] is None:
            print _("Warning: None Value in self.parameters. This should not happen!")

        # Must test booleen first because booleen are also int (e.g., True == 1 is True)
        if isinstance(current[command[-1]], bool):
            if value.lower() == 'true':
                current[command[-1]] = True
            elif value.lower() == 'false':
                current[command[-1]] = False
        elif isinstance(current[command[-1]], int):
            current[command[-1]] = int(value)
        elif isinstance(current[command[-1]], float):
            current[command[-1]] = float(value)
        elif isinstance(current[command[-1]], str) or isinstance(current[command[-1]], unicode) or current[command[-1]] is None:
            current[command[-1]] = value
        else:
            try:
                current[command[-1]] = ast.literal_eval(value)
            except:
                print value
                self.showCriticalMessage(
                    _("Unable to evaluate a value! This should not happen!"))

        # Retrieve changing value that are handled by MATB.py (e.g., title, taskupdatetime)
        if variable == 'title':
            self.PLUGINS_TASK[task]['ui_label'].setText(value)
        elif variable == 'taskupdatetime' and isinstance(current[command[-1]], int):
            self.PLUGINS_TASK[task]['UPDATE_TIME'] = int(value)

    def executeScenario(self, time):
        """Interpret and execute commands for the current time value"""

        # Check if the current time has entry in the scenario
        if time in self.scenariocontents:

            # If so, browse all the task that are involved
            for task in [this_task for this_task in self.scenariocontents[time] if this_task != '__main__']:
                # Store an instance of the Task class of the plugin
                taskclass = self.getPluginClass(task)

                # For each command that is found
                for command in self.scenariocontents[time][task]:

                    # If action command, determine which and execute according actions
                    if len(command) == 1:
                        functionname = "on" + command[0].capitalize()

                        msg = ''
                        if functionname == "onStart":
                            self.PLUGINS_TASK[task]['taskRunning'] = True
                            self.PLUGINS_TASK[task]['taskPaused'] = False
                            taskclass.show()
                            msg = 'START'
                        elif functionname == "onStop":
                            self.PLUGINS_TASK[task]['taskRunning'] = False
                            msg = 'STOP'
                        elif functionname == "onShow":
                            taskclass.show()
                            msg = 'SHOW'
                        elif functionname == "onHide":
                            taskclass.hide()
                            msg = 'HIDE'
                        elif functionname == "onPause":
                            if not self.PLUGINS_TASK[task]['taskPaused']:
                                self.PLUGINS_TASK[task]['taskPaused'] = True
                                msg = 'PAUSE'
                        elif functionname == "onResume":
                            if self.PLUGINS_TASK[task]['taskPaused']:
                                self.PLUGINS_TASK[task]['taskPaused'] = False
                                msg = 'RESUME'

                        if hasattr(taskclass, functionname):
                            getattr(taskclass, functionname)()

                        if len(msg):
                            self.mainLog.addLine(['MAIN', 'STATE', task.upper(), msg])

                        self.waitEndofPause()

                    else:
                        # If longer command, set as a parameter variable (see setParameterVariable above)
                        self.setParameterVariable(task, taskclass, command[0], command[1])
                        self.mainLog.addLine(['MAIN', 'SCENARIO', task.upper(), command[0].upper(), command[1]])

    def waitEndofPause(self):
        # if the task asked for a pause. Wait for the end of the pause
        # this is necessary to prevent racing conditions between tasks
        # started at the same time event
        while self.experiment_pause:
            QtCore.QCoreApplication.processEvents()

        self.last_time = self.default_timer()

    def scenarioUpdateTime(self):
        """Increment time (h,m,s) and get the corresponding string chain (H:MM:SS)"""

        m, s = divmod(self.elapsedTime / 1000.0, 60)
        h, m = divmod(m, 60)

        if h > 9:
            self.showCriticalMessage(_("Timing overflow. This should not happen!"))

        s = "%d:%02d:%02d" % (h, m, s)

        # If scenarioTimeStr need to be updated (1 second passed), update it
        # and try to execute scenario contents again (see the executeScenario fucntion above)
        if s != self.scenarioTimeStr:
            self.scenarioTimeStr = s
            self.executeScenario(self.scenarioTimeStr)

    def scheduler(self):
        """Manage the passage of time. Block time during pauses"""
        current_time = self.default_timer()
        elapsed_time = (current_time - self.last_time) * 1000.0

        if elapsed_time < MAIN_SCHEDULER_INTERVAL:
            return

        self.last_time = current_time

        # The main experiment is in pause, so do not increment time
        if self.experiment_pause or not self.experiment_running:
            return

        # Time increment in case the experiment is running
        self.elapsedTime += elapsed_time

        # If experiment is effectively running, browse plugins and refresh them (execute their onUpdate() method) as a function of their own UPDATE_TIME
        for plugin_name in self.PLUGINS_TASK:
            if plugin_name in self.loadedTasks:
                if self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] is not None and self.PLUGINS_TASK[plugin_name][
                    'taskRunning']:
                    self.PLUGINS_TASK[plugin_name][
                        "TIME_SINCE_UPDATE"] += elapsed_time
                    if self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] >= self.PLUGINS_TASK[plugin_name][
                        "UPDATE_TIME"]:
                        self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] = 0
                        if hasattr(self.PLUGINS_TASK[plugin_name]["class"], "onUpdate"):
                            self.PLUGINS_TASK[plugin_name]["class"].onUpdate()
                        else:
                            self.showCriticalMessage(
                                _("Plugin '%s' requires an onUpdate() function!") % plugin_name)

        self.scenarioUpdateTime()

    def eventFilter(self, source, event):
        """Filter key inputs, and launch task keyEvent methods if not paused"""
        if (event.type() == QtCore.QEvent.KeyRelease):
            key = event.key()

            # End experiment if key=ESC
            if key == QtCore.Qt.Key_Escape:
                self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", "ESC"])
                if self.parameters['allowescape']:
                    self.onEnd()
                return True

            self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", str(key)])

            for task in self.PLUGINS_TASK:
                if self.PLUGINS_TASK[task]["RECEIVE_KEY"] and not self.PLUGINS_TASK[task]['taskPaused']:
                    self.getPluginClass(task).keyEvent(key)

            return True
        else:
            return QtGui.QMainWindow.eventFilter(self, source, event)

    def sendLogToPlugins(self, stringLine):
        if hasattr(self, 'loadedTasks'):
            for plugin_name in self.PLUGINS_TASK:
                if plugin_name in self.loadedTasks:
                    if self.PLUGINS_TASK[plugin_name]["NEED_LOG"] == True:
                        self.PLUGINS_TASK[plugin_name]["class"].onLog(stringLine)

    def closeEvent(self, e):
        """Defines what happens when close button or ALT-F4 is hit"""
        if self.parameters['allowescape']:
            self.hide()
            self.onEnd()
            e.accept()
        else:
            e.ignore()

    def onEnd(self):
        """Defines what happens for the experiment to end"""

        self.experiment_running = False

        # Start the onEnd() method of each loaded plugin
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if hasattr(self.getPluginClass(plugin), "onEnd"):
                    self.getPluginClass(plugin).onEnd()

        self.mainLog.addLine(["MAIN", "STATE", "", "END"])
        self.close()
        sys.exit()

    def onPause(self):
        """Defines what happens when the experiment is paused, for instance when a generic scale is presented"""
        self.mainLog.addLine(["MAIN", "STATE", "", "PAUSE"])
        self.experiment_pause = True

        # The timer is paused
        for timer in self.registeredTaskTimer:
            timer.pause()

        # The onPause() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if not self.PLUGINS_TASK[plugin]['taskPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = True
                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].hide()

                    if hasattr(self.getPluginClass(plugin), "onPause"):
                        self.getPluginClass(plugin).onPause()

                # Also, the plugin in itself is hidden
                classplugin.hide()

    def onResume(self):
        """Defines what happens when resuming from a pause"""
        self.mainLog.addLine(["MAIN", "STATE", "", "RESUME"])
        self.experiment_pause = False

        # The timer is resumed
        for timer in self.registeredTaskTimer:
            timer.resume()

        # And the onResume() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if self.PLUGINS_TASK[plugin]['taskPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = False

                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].show()

                    if hasattr(self.getPluginClass(plugin), "onResume"):
                        self.getPluginClass(plugin).onResume()

                # Finally, the plugin is displayed back
                classplugin.show()

def loadConfig():
    config_filename = 'config.txt'

    if os.path.exists(config_filename):
        with open(config_filename, 'r') as lines:
            for line in lines:
                split = line.split('=')
                if len(split)==2:
                    CONFIG[split[0]]=(split[1])

    if CONFIG.has_key('language'):
        Translator._lang = CONFIG['language']

# return the value from the config file or the default one
def getConfigValue(key, defaultvalue):
    if CONFIG.has_key(key):
        return CONFIG[key]
    return defaultvalue

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    loadConfig()

    scenario_FullPath, none = QtGui.QFileDialog.getOpenFileName(
        None, VERSIONTITLE + _('Select a scenario'), DIRECTORY_NAME_SCENARIOS, "(*.txt)")

    if os.path.exists(scenario_FullPath):
        pygame.init()
        window = Main(scenario_FullPath)
        window.setWindowTitle(VERSIONTITLE)

        window.show()
        app.installEventFilter(window)
        window.runExperiment()

    else:
        OSCriticalErrorMessage(_("Error"), _("No scenario selected!"))

    sys.exit(app.exec_())
=======
# -*- coding: utf-8 -*-

VERSION = "1.0.000"
VERSIONTITLE = 'OpenMATB v' + VERSION

# Default directories
DIRECTORY_NAME_PLUGINS = "Plugins"
DIRECTORY_NAME_LOGS = "Logs"
DIRECTORY_NAME_SCENARIOS = "Scenarios"
DIRECTORY_NAME_SCALES = "Scales"

# The name of variable used to interact with plugins.
# Do not touch or everything will break!
PARAMETERS_VARIABLE = "parameters"

# We wait at least one tenth millisecond to update tasks.This is sufficient!
# Will prevent hammering the main loop at <0.06 milliseconds
MAIN_SCHEDULER_INTERVAL = 0.001

global CONFIG
CONFIG = {}


import ctypes
import time
import datetime
import imp
import ast
import sys
import os
import platform
from Helpers import Logger, Translator
from Helpers.Translator import translate as _

def OSCriticalErrorMessage(title, msg):
    if platform.system() == "Windows":
        ctypes.windll.user32.MessageBoxW(None, _(msg), VERSIONTITLE + " - " + _(title), 0)
    else:
        print _(title) + ":" + _(msg)
    sys.exit()


# Ensure that Pyside, pygame, rstr and wave are available
try:
    from PySide import QtCore, QtGui
    import pygame
    import rstr
    import wave
except:
    OSCriticalErrorMessage(
        _("Error"), _("Please check that all required libraries are installed"))


class Main(QtGui.QMainWindow):

    def __init__(self, scenario_fullpath):
        super(Main, self).__init__(parent=None)
        self.setFixedSize(1900, 1000)
        self.registeredTaskTimer = []
        self.parameters = {
            'showlabels': True,
            'allowescape': True
        }

        # Preallocate a dictionary to store plugins information
        self.PLUGINS_TASK = {}

        # Store working directory and scenario names
        # Use correct directory if running in cxFreeze (frozen)
        if getattr(sys, 'frozen', False):
            self.working_directory = os.getcwd()
        else:
            self.working_directory = os.path.dirname(os.path.abspath(__file__))

        self.scenario_shortfilename = os.path.split(scenario_fullpath)[1]
        self.scenario_directory = os.path.split(scenario_fullpath)[0]
        self.scales_directory = os.path.join(self.working_directory, DIRECTORY_NAME_SCALES)

        # Check that the plugins folder exists
        if not os.path.exists(os.path.join(self.working_directory, DIRECTORY_NAME_PLUGINS)):
            self.showCriticalMessage(
                _("Plugins directory does not exist. Check that its name is correct"))

        # Create a ./Logs folder if it does not exist
        if not os.path.exists(os.path.join(self.working_directory, DIRECTORY_NAME_LOGS)):
            os.mkdir(os.path.join(self.working_directory, DIRECTORY_NAME_LOGS))

        # Create a filename for the log file
        # Corresponds to : scenario name + date + .log
        LOG_FILE_NAME = os.path.join(self.scenario_shortfilename.replace(".txt", "").replace(
            " ", "_") + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".log")
        self.LOG_FILE_PATH = os.path.join(self.working_directory, DIRECTORY_NAME_LOGS, LOG_FILE_NAME)

        # Initialize a Logger instance with this log filename (see Helpers/Logger.py)
        self.mainLog = Logger.Logger(self, self.LOG_FILE_PATH)
        self.mainLog.addLine(['MAIN', 'INFO', 'SCENARIO', 'FILENAME', self.scenario_shortfilename])

        # Initialize two timing variables
        self.scenarioTimeStr = None
        self.elapsedTime = 0

        # Compute screen dimensions
        # /!\ Be careful : when multiple monitor are present, screen height and width are computed for the widest screen,
        # but the active screen will be used. Therefore you must ensure that the active screen
        # (just click on it before running application) is also the widest.

        self.screen_width = self.width()
        self.screen_height= self.height()
        print self.screen_width
        print self.screen_height
        #screen_widths = [QtGui.QApplication.desktop().screenGeometry(i).width()
        #                 for i in range(0, QtGui.QApplication.desktop().screenCount())]
        #self.screen_width = max(screen_widths)
        #self.screen_index = screen_widths.index(self.screen_width)
        #self.screen_height = QtGui.QApplication.desktop().screenGeometry(
        #    self.screen_index).height()

        # Get current screen
        #current_screen = QtGui.QApplication.desktop().screenNumber(QtGui.QApplication.desktop().cursor().pos())
        #centerPoint = QtGui.QApplication.desktop().screenGeometry(current_screen).center()
        #self.move(centerPoint)

        # Log the computed screen size values
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'WIDTH', str(self.screen_width)])
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'HEIGHT', str(self.screen_height)])

        #  The following dictionary contains all the information about sizes and placements.
        #  control_top/left is the top/left margin
        #  control_height/width defines the plugin height/width
        self.placements = {
            'fullscreen': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height,
                           'control_width': self.screen_width},

            'topleft': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height / 2,
                        'control_width': self.screen_width * (7.0 / 20.1)},

            'topmid': {'control_top': 0, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                       'control_width': self.screen_width * (10.7 / 20.1)},

            'topright': {'control_top': 0, 'control_left': self.screen_width * (5.9 / 20.1) + self.screen_width * (
                    10.6 / 20.1), 'control_height': self.screen_height / 2,
                         'control_width': self.screen_width * (3.6 / 20.1)},

            'bottomleft': {'control_top': self.screen_height / 2, 'control_left': 0, 'control_height':
                self.screen_height / 2, 'control_width': self.screen_width * (5.9 / 20.1)},

            'bottommid': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                          'control_width': self.screen_width * (10.7 / 20.1)},

            'bottomright': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (5.9 / 20.1) +
                                                                                   self.screen_width * (10.6 / 20.1),
                            'control_height': self.screen_height / 2,
                            'control_width': self.screen_width * (3.6 / 20.1)}
        }

        # Turn off Caps Lock and Num Lock if possible (only Windows until now)
        if platform.system() == "Windows":
            self.turnOffKey(0x14)  # Caps Lock
            self.turnOffKey(0x90)  # Num Lock

        # Preallocate variables to handle experiment pauses
        self.experiment_pause = False
        self.experiment_running = True

        # Initialize plugins
        self.load_plugins()
        self.place_plugins_on_screen()
        self.loadedTasks = []

        # Load scenario file
        self.scenariocontents = self.loadScenario(scenario_fullpath)

        if self.parameters['showlabels']:
            self.showlabels()

    def turnOffKey(self, k):
        """On Windows, use this method to turn off a key defined by the k variable"""
        KEYEVENTF_EXTENTEDKEY = 0x1
        KEYEVENTF_KEYUP = 0x2

        dll = ctypes.WinDLL('User32.dll')

        if dll.GetKeyState(k):
            dll.keybd_event(k, 0x45, KEYEVENTF_EXTENTEDKEY, 0)
            dll.keybd_event(
                k, 0x45, KEYEVENTF_EXTENTEDKEY | KEYEVENTF_KEYUP, 0)


    def runExperiment(self):
        # Initialize a general timer
        if sys.platform == 'win32':
            self.default_timer = time.clock
        else:
            self.default_timer = time.time

        # Update time once to take first scenario instructions (0:00:00) into account
        self.scenarioUpdateTime()
        self.last_time = self.default_timer()

        # Launch experiment
        while self.experiment_running:
            self.scheduler()
            QtCore.QCoreApplication.processEvents()

        sys.exit()

    def showCriticalMessage(self, msg):
        """Display a critical message (msg) in a QMessageBox Qt object before exiting"""

        flags = QtGui.QMessageBox.Abort
        flags |= QtGui.QMessageBox.StandardButton.Ignore

        result = QtGui.QMessageBox.critical(self, VERSIONTITLE + " "+_("Error"),
                                            msg,
                                            flags)

        if result == QtGui.QMessageBox.Abort:
            self.onEnd()
            sys.exit()


    def getPluginClass(self, plugin):
        """Return the Task instance of the given plugin"""
        if plugin == "__main__":
            return self
        else:
            return self.PLUGINS_TASK[plugin]["class"]

    def load_plugins(self):
        """Inform the Main() class with plugins information"""

        # For each plugin that is present in the ./Plugins directory
        for thisfile in os.listdir(DIRECTORY_NAME_PLUGINS):

            # If it is a python file...
            if thisfile.endswith(".py"):

                # Retrieve the plugin name
                plugin_name = thisfile.replace(".py", "")
                module = imp.load_source(plugin_name, os.path.join(
                    self.working_directory, DIRECTORY_NAME_PLUGINS, thisfile))

                # If the plugin has defined a Task class, log it
                if hasattr(module, "Task"):
                    task = module.Task(self)

                    # Check if a parameters dictionary is present
                    if not hasattr(task, 'parameters'):
                        print _("Plugin '%s' is invalid (no parameters data)") % (plugin_name)
                        continue

                    # Initialize a dictionary to store plugin information
                    plugin_name = plugin_name.lower()
                    self.PLUGINS_TASK[plugin_name] = {}
                    self.PLUGINS_TASK[plugin_name]['class'] = task
                    self.PLUGINS_TASK[plugin_name]['TIME_SINCE_UPDATE'] = 0
                    self.PLUGINS_TASK[plugin_name]['taskRunning'] = False
                    self.PLUGINS_TASK[plugin_name]['taskPaused'] = False

                    # Store potential plugin information
                    if 'taskupdatetime' in task.parameters:
                        self.PLUGINS_TASK[plugin_name][
                            "UPDATE_TIME"] = task.parameters['taskupdatetime']
                    else:
                        self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] = None

                    if hasattr(task, "keyEvent"):
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = True
                    else:
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = False
                    self.PLUGINS_TASK[plugin_name]["NEED_LOG"] = True if hasattr(task, "onLog") else False

                    task.hide()
                else:
                    print _("Plugin '%s' is not recognized") % plugin_name

    def showlabels(self):
        # If loaded plugins have an ui_label, display it
        for plugin_name in self.loadedTasks:
            if plugin_name != "__main__":
                if 'ui_label' in self.PLUGINS_TASK[plugin_name]:
                    self.PLUGINS_TASK[plugin_name]['ui_label'].show()

    def place_plugins_on_screen(self):
        """Compute size and position of each plugin, in a 2 x 3 canvas,
        as a function of the taskplacement variable of each plugin"""

        # Compute some sizes as a function of screen height
        LABEL_HEIGHT = self.screen_height / 27
        font_size_pt = int(LABEL_HEIGHT / (5 / 2))

        # Adapt top margin and height to the presence/absence of plugin labels
        if self.parameters['showlabels']:
            for k in self.placements.keys():
                self.placements[k]['control_top'] += LABEL_HEIGHT
                self.placements[k]['control_height'] -= LABEL_HEIGHT

        # Browse plugins to effectively size and place them
        for plugin_name in self.PLUGINS_TASK:
            plugin = self.getPluginClass(plugin_name)

            # Check if the plugin has a taskplacement parameter
            if 'taskplacement' not in plugin.parameters or not plugin.parameters['taskplacement']:
                print _("Plugin '%s' has no placement data. It will not be displayed") % plugin_name
                continue

            # If so, retrieve it
            placement = plugin.parameters['taskplacement']

            # Plugin placement must match one value of the self.placement dictionary
            if placement in self.placements.keys():
                self.control_top = self.placements[placement]['control_top']
                self.control_left = self.placements[placement]['control_left']
                self.control_height = self.placements[
                    placement]['control_height']
                self.control_width = self.placements[
                    placement]['control_width']

                # If the plugin is not displayed in fullscreen, log information about its area of interest (AOI)
                if placement != 'fullscreen':
                    thisPlacement = self.placements[placement]
                    AOIx = [int(thisPlacement['control_left']), int(
                        thisPlacement['control_left'] + thisPlacement['control_width'])]
                    AOIy = [int(thisPlacement['control_top']), int(
                        thisPlacement['control_top'] + thisPlacement['control_height'])]

                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_X', AOIx])
                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_Y', AOIy])

                    # For each non-fullscreen plugin, show its label if needed
                    if self.parameters['showlabels']:
                        self.PLUGINS_TASK[plugin_name]['ui_label'] = QtGui.QLabel(plugin.parameters['title'].upper(), self)

                        self.PLUGINS_TASK[plugin_name]['ui_label'].setStyleSheet("font: " + str(font_size_pt) + "pt \"MS Shell Dlg 2\"; background-color: black; color: white;")
                        self.PLUGINS_TASK[plugin_name]['ui_label'].setAlignment(QtCore.Qt.AlignCenter)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].resize(self.control_width, LABEL_HEIGHT)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].move(self.control_left, self.control_top - LABEL_HEIGHT)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].hide()

            else:
                self.showCriticalMessage(
                    _("Placement '%s' is not recognized!") % placement)

            # Resize, place and show the plugin itself
            plugin.resize(self.control_width, self.control_height)
            plugin.move(self.control_left, self.control_top)
            plugin.show()


    def timerRegister(self, timer):
        self.registeredTaskTimer.append(timer)


    def loadScenario(self, scenario_file):
        """Convert the scenario file into a dictionary : dict[time][task][listOfcommand]"""

        # Create a dictionary
        scenario_content = {}

        # Read the scenario text file
        with open(scenario_file, 'r') as f:

            # Browse lines
            for lineNumber, scenario_line in enumerate(f):

                # Remove blank lines
                scenario_line = scenario_line.strip()

                # Only consider lines that do not begin with a #
                if not scenario_line.startswith("#") and scenario_line:

                    # Extract information from line : time, task and command (see getCommand below)
                    time, task, command = self.getCommand(lineNumber, scenario_line)

                    # Add the task to the list of loadedTasks
                    if not task in self.loadedTasks and task is not None:
                        self.loadedTasks.append(task)

                    # If the extracted time is not yet present in the scenario dictionary...
                    if time and time not in scenario_content:
                        # ...add it
                        scenario_content[time] = {}

                    # Likewise, if task not in scenario, add it
                    if task and task not in scenario_content[time]:
                        scenario_content[time][task] = []

                    # Finally, add the command at the correct location in the scenario dictionary
                    if command and time and task:
                        scenario_content[time][task].append(command)

        # If scenario is not valid, exit (see validateScenario below)
        if not self.validateScenario(scenario_content):
            sys.exit()

        return scenario_content

    def validateScenario(self, scenario_content):
        """Check that the scenario follows a set of criteria. Output the corresponding boolean value"""

        # Browse the loaded task, ignoring the __main__ one
        for checktask in self.loadedTasks:
            if checktask == "__main__":
                continue

            else:
                howmanyentries = 0
                entries = []
                for k in scenario_content.keys():
                    if checktask in scenario_content[k]:
                        for t in scenario_content[k][checktask]:
                            howmanyentries += 1
                            entries.append(t)

                # Does the scenario contains one or more commands for the task at hand ?
                if howmanyentries == 0:
                    self.showCriticalMessage(_("No entry has been found for the '%s' plugin. Check the scenario file") % checktask )
                    return False

                # Are the start/stop commands present ?
                for thiscommand in ['start']:
                    if thiscommand not in [thisentry[0] for thisentry in entries]:
                        self.showCriticalMessage(_("The '%s' plugin does not admit a %s command. Please fix that") % (checktask, thiscommand))
                        return False

        # Check that the last command of the scenario is an 'end'
        try:
            lasttime = sorted(scenario_content.keys())[-1]
            lasttask = scenario_content[lasttime].keys()[0]

            # Is there more than one task?
            if (len(scenario_content[lasttime].keys()) > 1):
                raise Exception()

            lastcmd = scenario_content[lasttime][lasttask][0][0]

            if lastcmd != "end":
                raise Exception()
        except:
            self.showCriticalMessage(_("The scenario should terminate with a 'end' command"))
            return False

        # Check there is at least one task in the scenario
        # Do not take into account the special case of the "__main__" task
        if len(self.loadedTasks) <= 1:
            self.showCriticalMessage(_("No task is started!"))
            return False

        return True

    def getCommand(self, lineNumber, lineContent):
        """Parse lineContent to time, task and command variables.

            There are 3 possible syntax:
            0:00:00;end => call onEnd in main script
            0:00:00;track;start => call onStart in the track plugins
            0:00:00;track;variable;value=> modify the parameters in the track plugins
         """

        # Retrieve line content, removing white space and using semi-colon as delimiter
        lineList = lineContent.strip().split(';')

        # Check if the length of lineList is correct
        if not 1 < len(lineList) < 5:
            self.showCriticalMessage(_("Error. Number of value is incorrect. See line")+" " + str(lineNumber) + ' (' + str(lineContent) + ')')
            return None, None, None

        # Manage the special case of main (0:00:00;start)
        elif len(lineList) == 2:
            lineList.insert(1, "__main__")

        # (there is no * to unpack variable sized list in python2.7 (time, task, *command))
        time, task, command = lineList[0], lineList[1], lineList[2:]

        if task == "__main__":
            taskclass = self
        elif task in self.PLUGINS_TASK:
            taskclass = self.getPluginClass(task)
        else:
            self.showCriticalMessage(
                _("'%s' plugin: unknown\n\nLINE: %s") % (task, str(lineNumber)))
            return None, None, None

        # When only one command, concatenate it with the 'on' chain (e.g. start leads to onStart)
        # onCommand functions are called into the plugins
        if len(command) == 1:
            functionname = "on" + command[0].capitalize()

            # If the onCommand does not exist...
            if not hasattr(taskclass, functionname) and functionname not in ["onStart", "onStop", "onPause",
                                                                             "onResume"]:

                # signal it.
                errorcaller = ""
                if task != "__main__":
                    errorcaller = "' in '" + task

                self.showCriticalMessage(
                    _("'%s' not found!\n\nLINE: %s") % (functionname + errorcaller, str(lineNumber)))
                return None, None, None
            else:
                return time, task, command

        # For the other variables, check that there are corrects (available in the plugin)
        else:
            if taskclass == self:
                self.showCriticalMessage(
                    _("The main script parameters should not be called, use a task instead!\n\nLINE: %s") % str(lineNumber))
                return None, None, None

            if not hasattr(taskclass, PARAMETERS_VARIABLE):
                self.showCriticalMessage(
                    _("'%s' should have a parameters dictionary!\n\nLINE: %s") % (task, str(lineNumber)))
                return None, None, None

            if not self.testParameterVariable(task, taskclass, command[0]):
                self.showCriticalMessage(
                    _("Variable '%s' unknown in task '%s'\n\nLINE: %s") % (str(command [0]), task, str(lineNumber)))
                return None, None, None

        return time, task, command


    def testParameterVariable(self, task, taskclass, adress):
        """Check that a given variable is present in the parameters dictionary of the plugin"""

        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        adress = adress.split('-')

        for i in range(0, len(adress)):
            k = str(adress[i])
            if isinstance(current, dict):
                if k in current:
                    current = current.get(k, None)  # getattr(current, k)

                else:
                    self.showCriticalMessage(
                        _("Variable '%s' unknown in task '%s'") % (k, task))
                    return False
            else:
                # Requires a dictionary...
                self.showCriticalMessage(
                    _("Plugin '%s' has a malformed '%s' variable") % (task, PARAMETERS_VARIABLE))
                return False

        return True

    def setParameterVariable(self, task, taskclass, variable, value):
        """Set a variable to its value, after having convert it to the correct type"""
        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        command = variable.split("-")

        for e in range(0, len(command) - 1):  # range(0,0) = []
            current = current.get(command[e], None)

        t = type(current[command[-1]])
        if current[command[-1]] is None:
            print _("Warning: None Value in self.parameters. This should not happen!")

        # Must test booleen first because booleen are also int (e.g., True == 1 is True)
        if isinstance(current[command[-1]], bool):
            if value.lower() == 'true':
                current[command[-1]] = True
            elif value.lower() == 'false':
                current[command[-1]] = False
        elif isinstance(current[command[-1]], int):
            current[command[-1]] = int(value)
        elif isinstance(current[command[-1]], float):
            current[command[-1]] = float(value)
        elif isinstance(current[command[-1]], str) or isinstance(current[command[-1]], unicode) or current[command[-1]] is None:
            current[command[-1]] = value
        else:
            try:
                current[command[-1]] = ast.literal_eval(value)
            except:
                print value
                self.showCriticalMessage(
                    _("Unable to evaluate a value! This should not happen!"))

        # Retrieve changing value that are handled by MATB.py (e.g., title, taskupdatetime)
        if variable == 'title':
            self.PLUGINS_TASK[task]['ui_label'].setText(value)
        elif variable == 'taskupdatetime' and isinstance(current[command[-1]], int):
            self.PLUGINS_TASK[task]['UPDATE_TIME'] = int(value)

    def executeScenario(self, time):
        """Interpret and execute commands for the current time value"""

        # Check if the current time has entry in the scenario
        if time in self.scenariocontents:

            # If so, browse all the task that are involved
            for task in [this_task for this_task in self.scenariocontents[time] if this_task != '__main__']:
                # Store an instance of the Task class of the plugin
                taskclass = self.getPluginClass(task)

                # For each command that is found
                for command in self.scenariocontents[time][task]:

                    # If action command, determine which and execute according actions
                    if len(command) == 1:
                        functionname = "on" + command[0].capitalize()

                        msg = ''
                        if functionname == "onStart":
                            self.PLUGINS_TASK[task]['taskRunning'] = True
                            self.PLUGINS_TASK[task]['taskPaused'] = False
                            taskclass.show()
                            msg = 'START'
                        elif functionname == "onStop":
                            self.PLUGINS_TASK[task]['taskRunning'] = False
                            msg = 'STOP'
                        elif functionname == "onShow":
                            taskclass.show()
                            msg = 'SHOW'
                        elif functionname == "onHide":
                            taskclass.hide()
                            msg = 'HIDE'
                        elif functionname == "onPause":
                            if not self.PLUGINS_TASK[task]['taskPaused']:
                                self.PLUGINS_TASK[task]['taskPaused'] = True
                                msg = 'PAUSE'
                        elif functionname == "onResume":
                            if self.PLUGINS_TASK[task]['taskPaused']:
                                self.PLUGINS_TASK[task]['taskPaused'] = False
                                msg = 'RESUME'

                        if hasattr(taskclass, functionname):
                            getattr(taskclass, functionname)()

                        if len(msg):
                            self.mainLog.addLine(['MAIN', 'STATE', task.upper(), msg])

                        self.waitEndofPause()

                    else:
                        # If longer command, set as a parameter variable (see setParameterVariable above)
                        self.setParameterVariable(task, taskclass, command[0], command[1])
                        self.mainLog.addLine(['MAIN', 'SCENARIO', task.upper(), command[0].upper(), command[1]])

    def waitEndofPause(self):
        # if the task asked for a pause. Wait for the end of the pause
        # this is necessary to prevent racing conditions between tasks
        # started at the same time event
        while self.experiment_pause:
            QtCore.QCoreApplication.processEvents()

        self.last_time = self.default_timer()

    def scenarioUpdateTime(self):
        """Increment time (h,m,s) and get the corresponding string chain (H:MM:SS)"""

        m, s = divmod(self.elapsedTime / 1000.0, 60)
        h, m = divmod(m, 60)

        if h > 9:
            self.showCriticalMessage(_("Timing overflow. This should not happen!"))

        s = "%d:%02d:%02d" % (h, m, s)

        # If scenarioTimeStr need to be updated (1 second passed), update it
        # and try to execute scenario contents again (see the executeScenario fucntion above)
        if s != self.scenarioTimeStr:
            self.scenarioTimeStr = s
            self.executeScenario(self.scenarioTimeStr)

    def scheduler(self):
        """Manage the passage of time. Block time during pauses"""
        current_time = self.default_timer()
        elapsed_time = (current_time - self.last_time) * 1000.0

        if elapsed_time < MAIN_SCHEDULER_INTERVAL:
            return

        self.last_time = current_time

        # The main experiment is in pause, so do not increment time
        if self.experiment_pause or not self.experiment_running:
            return

        # Time increment in case the experiment is running
        self.elapsedTime += elapsed_time

        # If experiment is effectively running, browse plugins and refresh them (execute their onUpdate() method) as a function of their own UPDATE_TIME
        for plugin_name in self.PLUGINS_TASK:
            if plugin_name in self.loadedTasks:
                if self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] is not None and self.PLUGINS_TASK[plugin_name][
                    'taskRunning']:
                    self.PLUGINS_TASK[plugin_name][
                        "TIME_SINCE_UPDATE"] += elapsed_time
                    if self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] >= self.PLUGINS_TASK[plugin_name][
                        "UPDATE_TIME"]:
                        self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] = 0
                        if hasattr(self.PLUGINS_TASK[plugin_name]["class"], "onUpdate"):
                            self.PLUGINS_TASK[plugin_name]["class"].onUpdate()
                        else:
                            self.showCriticalMessage(
                                _("Plugin '%s' requires an onUpdate() function!") % plugin_name)

        self.scenarioUpdateTime()

    def eventFilter(self, source, event):
        """Filter key inputs, and launch task keyEvent methods if not paused"""
        if (event.type() == QtCore.QEvent.KeyRelease):
            key = event.key()

            # End experiment if key=ESC
            if key == QtCore.Qt.Key_Escape:
                self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", "ESC"])
                if self.parameters['allowescape']:
                    self.onEnd()
                return True

            self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", str(key)])

            for task in self.PLUGINS_TASK:
                if self.PLUGINS_TASK[task]["RECEIVE_KEY"] and not self.PLUGINS_TASK[task]['taskPaused']:
                    self.getPluginClass(task).keyEvent(key)

            return True
        else:
            return QtGui.QMainWindow.eventFilter(self, source, event)

    def sendLogToPlugins(self, stringLine):
        if hasattr(self, 'loadedTasks'):
            for plugin_name in self.PLUGINS_TASK:
                if plugin_name in self.loadedTasks:
                    if self.PLUGINS_TASK[plugin_name]["NEED_LOG"] == True:
                        self.PLUGINS_TASK[plugin_name]["class"].onLog(stringLine)

    def closeEvent(self, e):
        """Defines what happens when close button or ALT-F4 is hit"""
        if self.parameters['allowescape']:
            self.hide()
            self.onEnd()
            e.accept()
        else:
            e.ignore()

    def onEnd(self):
        """Defines what happens for the experiment to end"""

        self.experiment_running = False

        # Start the onEnd() method of each loaded plugin
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if hasattr(self.getPluginClass(plugin), "onEnd"):
                    self.getPluginClass(plugin).onEnd()

        self.mainLog.addLine(["MAIN", "STATE", "", "END"])
        self.close()
        sys.exit()

    def onPause(self):
        """Defines what happens when the experiment is paused, for instance when a generic scale is presented"""
        self.mainLog.addLine(["MAIN", "STATE", "", "PAUSE"])
        self.experiment_pause = True

        # The timer is paused
        for timer in self.registeredTaskTimer:
            timer.pause()

        # The onPause() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if not self.PLUGINS_TASK[plugin]['taskPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = True
                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].hide()

                    if hasattr(self.getPluginClass(plugin), "onPause"):
                        self.getPluginClass(plugin).onPause()

                # Also, the plugin in itself is hidden
                classplugin.hide()

    def onResume(self):
        """Defines what happens when resuming from a pause"""
        self.mainLog.addLine(["MAIN", "STATE", "", "RESUME"])
        self.experiment_pause = False

        # The timer is resumed
        for timer in self.registeredTaskTimer:
            timer.resume()

        # And the onResume() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if self.PLUGINS_TASK[plugin]['taskPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = False

                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].show()

                    if hasattr(self.getPluginClass(plugin), "onResume"):
                        self.getPluginClass(plugin).onResume()

                # Finally, the plugin is displayed back
                classplugin.show()

def loadConfig():
    config_filename = 'config.txt'

    if os.path.exists(config_filename):
        with open(config_filename, 'r') as lines:
            for line in lines:
                split = line.split('=')
                if len(split)==2:
                    CONFIG[split[0]]=(split[1])

    if CONFIG.has_key('language'):
        Translator._lang = CONFIG['language']

# return the value from the config file or the default one
def getConfigValue(key, defaultvalue):
    if CONFIG.has_key(key):
        return CONFIG[key]
    return defaultvalue

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    loadConfig()

    scenario_FullPath, none = QtGui.QFileDialog.getOpenFileName(
        None, VERSIONTITLE + ' - ' + _('Select a scenario'), DIRECTORY_NAME_SCENARIOS, "(*.txt)")

    if os.path.exists(scenario_FullPath):
        pygame.init()
        window = Main(scenario_FullPath)
        window.setWindowTitle(VERSIONTITLE)

        window.show()
        app.installEventFilter(window)
        window.runExperiment()

    else:
        OSCriticalErrorMessage(_("Error"), _("No scenario selected!"))

    sys.exit(app.exec_())
>>>>>>> fd53522b6c90ad7bbd79c90a3db4616a2e00a04f:OpenMATB.py
