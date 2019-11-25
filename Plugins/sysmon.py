from PySide2 import QtCore, QtWidgets, QtGui
from Helpers import QTExtensions, WScale, WLight
from numpy import median
import random
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # SYSMON PARAMETERS ###
        self.parameters = {
            'title': 'System monitoring',
            'taskplacement': 'topleft',
            'taskupdatetime': 200,
            'alerttimeout': 10000,
            'automaticsolver': False,
            'automaticsolverdelay': 1 * 1000,
            'displayautomationstate': False,
            'allowanykey': False,
            'scalesnumofboxes': 11,
            'safezonelength': 3,
            'feedback': True,
            'feedbackcolor': '#ffff00',  # Yellow
            'feedbackduration': 1.5 * 1000,
            'launchfeedback': 0,
            'scalestyle': 1,  # could be defined at the scale level
            'resetperformance': None,

            'lights': {
                '1': {'name': 'F5', 'failure': False, 'on': True, 'default': 'on', 'oncolor': "#009900", 'keys': [QtCore.Qt.Key_F5]},
                '2': {'name': 'F6', 'failure': False, 'on': False, 'default': 'off', 'oncolor': "#FF0000", 'keys': [QtCore.Qt.Key_F6]}
            },

            'scales': {
                '1': {'name': 'F1', 'failure': 'no', 'keys': [QtCore.Qt.Key_F1]},
                '2': {'name': 'F2', 'failure': 'no', 'keys': [QtCore.Qt.Key_F2]},
                '3': {'name': 'F3', 'failure': 'no', 'keys': [QtCore.Qt.Key_F3]},
                '4': {'name': 'F4', 'failure': 'no', 'keys': [QtCore.Qt.Key_F4]}
            }
            }

        self.performance = {
            'total' : {'hit_number': 0, 'miss_number':0, 'fa_number':0},
            'last'  : {'hit_number': 0, 'miss_number':0, 'fa_number':0}
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Set the initial position of the cursor (middle)
        for this_scale in self.parameters['scales'].keys():
            self.parameters['scales'][this_scale][
                'position'] = self.parameters['scalesnumofboxes'] / 2

        # Define two failures zones (up, down)
        totalRange = range(1, self.parameters['scalesnumofboxes'] - 1)
        centerPosition = totalRange[int(median(totalRange))]
        self.zones = {
            'up': [k for k in totalRange if k < (centerPosition - (self.parameters['safezonelength'] - 1) / 2)],
            'down': [k for k in totalRange if k > (centerPosition + (self.parameters['safezonelength'] - 1) / 2)]
        }

        # Define the "safe" zone (no)
        self.zones['no'] = [k for k in totalRange if k not in self.zones['up'] if k not in self.zones['down']]

        # Set a list of accepted keys depending on lights and scales parameters
        scales_keys = [self.parameters['scales'][id]["keys"][0]
                       for id in self.parameters['scales'].keys()]
        lights_keys = [self.parameters['lights'][id]["keys"][0]
                       for id in self.parameters['lights'].keys()]
        self.accepted_keys = scales_keys + lights_keys

    def onStart(self):

        # Define a QLabel object to potentially display automation mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
        self.modeLabel = QtWidgets.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(0, 0.2 * self.height(), self.width(), 0.08 * self.height()))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)

        # For each light button
        for index, k in enumerate(self.parameters['lights'].keys()):

            # Set a WLight Qt object
            self.parameters['lights'][k]['ui'] = WLight.WLight(self, self.parameters['lights'][k][
                                                               'on'], self.parameters['lights'][k]['oncolor'], self.parameters['lights'][k]['name'], index)

            # Show the WLight Qt object
            self.parameters['lights'][k]['ui'].show()

        # For each scale gauge
        for k in sorted(self.parameters['scales'].keys()):

            # Set a WScale Qt object
            self.parameters['scales'][k]['ui'] = WScale.WScale(
                self, self.parameters['scales'][k]['name'], self.parameters['scalesnumofboxes'], k, self.parameters['scalestyle'])

            # Show the WScale Qt object
            self.parameters['scales'][k]['ui'].show()

        # Define two timers to handle failure and feedback durations
        self.failuretimeoutTimer = QTExtensions.QTimerWithPause(self)
        self.failuretimeoutTimer.timeout.connect(self.endFailure)
        self.feedbackTimer = QTExtensions.QTimerWithPause(self)
        self.feedbackTimer.timeout.connect(self.endFeedBackTimer)

        # Preallocate a variable handling information about a potential current failure
        self.currentFailure = {}

    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        if self.parameters['resetperformance'] is not None:
            if self.parameters['resetperformance'] in ['last', 'global']:
                for this_index in self.performance[self.parameters['resetperformance']]:
                    self.performance[self.parameters['resetperformance']][this_index] = 0
            else:
                self.parent().showCriticalMessage(_("%s : wrong argument in sysmon;resetperformance") % self.parameters['resetperformance'])
            self.parameters['resetperformance'] = None

        # For each light button, refresh name
        for index, k in enumerate(self.parameters['lights'].keys()):
            self.parameters['lights'][k]['ui'].light.setText(self.parameters['lights'][k]['name'])

        # For each scale gauge, refresh name
        for k in sorted(self.parameters['scales'].keys()):
            self.parameters['scales'][k]['ui'].label.setText(self.parameters['scales'][k]['name'])


        # 1. Check failures only if no failure is already occuring
        # (currently prevents double-failure !)
        if len(self.currentFailure) == 0:
            for lights_or_scales in ['lights', 'scales']:
                for thisGauge in self.parameters[lights_or_scales].keys():

                    # If a failure is to be initiated
                    if (lights_or_scales == 'scales' and self.parameters[lights_or_scales][thisGauge]['failure'] in ['up', 'down']) or (lights_or_scales == 'lights' and self.parameters[lights_or_scales][thisGauge]['failure']):

                        # Start it...
                        self.startFailure(lights_or_scales, thisGauge)
                        # ...and leave the loop
                        break

        # 2. Vary position of each scale, depending on its state (up, down, no)
        for thisScale in self.parameters['scales'].keys():
            self.parameters['scales'][thisScale][
                'position'] = self.computeNextPosition(thisScale)

        # 3. Refresh visual display
        for thisScale in self.parameters['scales'].keys():
            if 'ui' in self.parameters['scales'][thisScale]:
                self.parameters['scales'][thisScale][
                    'ui'].style = self.parameters['scalestyle']
                self.parameters['scales'][thisScale][
                    'ui'].position = self.parameters['scales'][thisScale]['position']

        for thisLight in self.parameters['lights'].keys():
            if 'ui' in self.parameters['lights'][thisLight]:
                self.parameters['lights'][thisLight]['ui'].refreshState(
                    self.parameters['lights'][thisLight]['on'])

        # 4. Check for arbitrary feedbacks
        if self.parameters['launchfeedback'] != 0:
            ui_idx = str(self.parameters['launchfeedback'])
            if any([ui_idx == idx for idx, val
                    in self.parameters['scales'].items()]):
                trigger_ui = self.parameters['scales'][ui_idx]['ui']
                self.trigger_feedback(trigger_ui)
                self.parameters['launchfeedback'] = 0

    def keyEvent(self, key_pressed):

        # If automaticsolver on, do not listen for keyboard inputs
        if self.parameters['automaticsolver'] or not key_pressed in self.accepted_keys:
            return

        # If no failure is occuring, any keypress is a false alarm
        if len(self.currentFailure) == 0:
            self.record_performance('NA','fa')
            return

        # If a failure is occuring, key press is evaluated further
        else:
            for lights_or_scales in ['lights', 'scales']:
                for thisGauge in self.parameters[lights_or_scales].keys():
                    if self.parameters[lights_or_scales][thisGauge]['failure'] in ['up', 'down'] or self.parameters[lights_or_scales][thisGauge]['failure'] == True:

                        # If correct key pressed -> end failure
                        if key_pressed in self.parameters[lights_or_scales][thisGauge]['keys']:
                            self.endFailure(True)

                        # If uncorrect key pressed -> failure continues (false
                        # alarm)
                        else:
                            self.record_performance('NA','fa')

    def endFeedBackTimer(self):
        self.feedbackTimer.stop()

        for thisScale in self.parameters['scales'].keys():
            self.parameters['scales'][thisScale]['ui'].set_feedback(0)
        # for thisLight in self.parameters['lights'].keys():
        #     self.parameters['lights'][thisLight]['ui'].set_feedback(0)

    def startFailure(self, lights_or_scales, number):
        if len(self.currentFailure) > 0:
            print("Failure already occuring for this gauge!")
            return

        self.currentFailure = {'type': lights_or_scales, 'number': number}

        if lights_or_scales == 'lights':
            self.parameters[lights_or_scales][number]['on'] = False if self.parameters[
                lights_or_scales][number]['default'] == 'on' else True

        self.buildLog(
            ["STATE", self.parameters[lights_or_scales][number]["name"], "FAILURE"])

        # If automatic solver on, start a timer that will automatically stop
        # failure after an automaticsolverdelay duration
        if self.parameters['automaticsolver']:
            self.failuretimeoutTimer.start(self.parameters['automaticsolverdelay'])

        # If automatic solver off, start a timer the will stop failure after an
        # alerttimeout duration
        else:
            self.failuretimeoutTimer.start(self.parameters['alerttimeout'])

    def endFailure(self, success=False):

        lights_or_scales = self.currentFailure['type']
        number = self.currentFailure['number']
        feedback_ui = self.parameters[lights_or_scales][number]['ui']
        self.failuretimeoutTimer.stop()

        # If automatic solver on and failure occuring, send the good key
        # response
        if self.parameters['automaticsolver']:

            self.buildLog(["STATE", self.parameters[lights_or_scales][number]["name"], "AUTOMATIC-SOLVER"])

            if self.parameters['feedback']:
                self.trigger_feedback(feedback_ui)

        # If automatic solver off and good key pressed (success), log a HIT,
        # send a positive feedback, start the corresponding timer
        elif success:
            self.record_performance(self.parameters[lights_or_scales][number]['name'], 'hit')

            if self.parameters['feedback']:
                self.trigger_feedback(feedback_ui)

        # If failure ends with neither automatic solver nor good key pressed,
        # log a MISS
        else:
            self.record_performance(self.parameters[lights_or_scales][number]["name"], 'miss')

        # In any case, reset all the 'failure' variables
        for thisScale in self.parameters['scales'].keys():
            self.parameters['scales'][thisScale]['failure'] = 'no'
        for thisLight in self.parameters['lights'].keys():
            self.parameters['lights'][thisLight]['failure'] = False
            self.parameters['lights'][thisLight]['on'] = True if self.parameters[
                'lights'][thisLight]['default'] == 'on' else False

        # Log the end of the failure
        self.buildLog(["STATE", self.parameters[lights_or_scales][number]["name"], "SAFE"])

        # Empty the current failure variable
        self.currentFailure = {}

    def computeNextPosition(self, whatScale):

        # Retrieve the current cursor position for a specific scale gauge
        actualPosition = self.parameters['scales'][whatScale]['position']

        # Retrieve the current scale state (up, down, no)
        whatZone = self.parameters['scales'][whatScale]['failure']

        # If current position does not match the current scale state, move the
        # cursor in the propoer zone
        if actualPosition not in self.zones[whatZone]:
            actualPosition = random.sample(self.zones[whatZone], 1)[0]

        # If it does match...
        else:
            # ...choose up/down direction randomly
            direction = random.sample([-1, 1], 1)[0]

            # Once a new direction is computed, if the pointer remains in the
            # correct zone...
            if actualPosition + direction in self.zones[whatZone]:
                # ...apply movement
                actualPosition += direction

            # If not...
            else:
                # ...move in the opposite direction
                actualPosition -= direction

        # Finally, return the new computed cursor position
        return actualPosition

    def refreshModeLabel(self):

        if 'automaticsolver' in self.parameters and self.parameters['automaticsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif 'assistedsolver' in self.parameters and self.parameters['assistedsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def trigger_feedback(self, trigger_ui):
        trigger_ui.set_feedback(1, self.parameters['feedbackcolor'])
        self.feedbackTimer.start(self.parameters['feedbackduration'])
        pass

    def record_performance(self, light_scale_name, event):
        for this_cat in self.performance.keys():
            self.performance[this_cat][event+'_number'] += 1
        self.buildLog(["ACTION", light_scale_name, event.upper()])

    def buildLog(self, thisList):
        thisList = ["SYSMON"] + thisList
        self.parent().mainLog.addLine(thisList)
