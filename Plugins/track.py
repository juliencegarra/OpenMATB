from PySide import QtGui, QtCore
from Helpers import WTrack
from Helpers.Translator import translate as _
import inputs

class Task(QtGui.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.my_joystick = None

        # TRACK PARAMETERS ###
        self.parameters = {
            'taskplacement': 'topmid',
            'taskupdatetime': 5,
            'title': 'Tracking',
            'cursorcolor': '#0000FF',
            'cursorcoloroutside': '#0000FF',
            'automaticsolver': False,
            'displayautomationstate': True,
            'assistedsolver': False,
            'targetradius': 0.1,
            'joystickforce': 0.05,
            'cutofffrequency': 0.06,
            'equalproportions' : True,
        }
        
        self.performance = {
            'total' : {'time_in_ms':0, 'time_out_ms':0, 'points_number':0, 'deviation_mean':0},
            'last'  : {'time_in_ms':0, 'time_out_ms':0, 'points_number':0, 'deviation_mean':0}
        }
        
        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])


    def onStart(self):
        
        # Define a QLabel object to potentially display automation mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
        self.modeLabel = QtGui.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(0.60 * self.width(), 0.60 * self.height(), 0.40 * self.width(), 0.40 * self.height()))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)
        
        self.parameters['displaytitle'] = True

        # Set a WTrack Qt object
        self.widget = WTrack.WTrack(self, self.parameters['equalproportions'])

        # Create a layout for the widget
        layout = QtGui.QGridLayout()

        # Add the WTrack object to the layout
        layout.addWidget(self.widget)
        self.setLayout(layout)
        
        if len(inputs.devices.gamepads) == 0:
            self.parent().showCriticalMessage(
                _("Please plug a joystick for the '%s' task!") % (self.parameters['title']))

        # Log some task information once
        self.buildLog(["STATE", "TARGET", "X", str(0.5)])
        self.buildLog(["STATE", "TARGET", "Y", str(0.5)])
        self.buildLog(["STATE", "TARGET", "RADIUS", str(self.parameters['targetradius'])])
        msg = _('AUTO') if self.parameters['automaticsolver'] else _('MANUAL')
        self.buildLog(["STATE", "", "MODE", msg])

    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        # Preallocate x and y input variables
        x_input, y_input = 0, 0

        # Compute next cursor coordinates (x,y)
        current_X, current_Y = self.widget.moveCursor()

        # If automatic solver : always correct cursor position
        if self.parameters['automaticsolver']:
            x_input, y_input = self.widget.getAutoCompensation()

        # Else allow manual compensatory movements only if cursor is outside
        # the target area
        elif not self.widget.isCursorInTarget():

            # Retrieve potentials joystick inputs (x,y)
            #~ ev_type, code, state = [[event.ev_type, event.code, event.state] for event in inputs.get_gamepad()][0]
            #~ if ev_type == 'Absolute':
                #~ print str(code) + ': ' + str(state)
            
            #~ x_input, y_input = self.joystick_input()

            # If assisted solver : correct cursor position only if joystick
            # inputs something
            if self.parameters['assistedsolver']:
                if any([this_input != 0 for this_input in [x_input, y_input]]):
                    x_input, y_input = self.widget.getAutoCompensation()

        # Modulate cursor position with potentials joystick inputs
        current_X += x_input
        current_Y += y_input

        # Refresh the display
        self.widget.refreshCursorPosition(current_X, current_Y)

        # Constantly log the cursor coordinates
        self.buildLog(["STATE", "CURSOR", "X", str(current_X)])
        self.buildLog(["STATE", "CURSOR", "Y", str(current_Y)])
        
        # Record performance
        for this_cat in self.performance.keys():
            if self.widget.isCursorInTarget():
                self.performance[this_cat]['time_in_ms'] += self.parameters['taskupdatetime']
            else:
                self.performance[this_cat]['time_out_ms'] += self.parameters['taskupdatetime']
            
            current_deviation = self.widget.returnAbsoluteDeviation()
            self.performance[this_cat]['points_number'] += 1
            self.performance[this_cat]['deviation_mean'] = self.performance[this_cat]['deviation_mean'] * ((self.performance[this_cat]['points_number']-1) / float(self.performance[this_cat]['points_number'])) + current_deviation * (float(1) / self.performance[this_cat]['points_number'])

    #~ def joystick_input(self):
        #~ if self.my_joystick:
            #~ pygame.event.pump()
            #~ # Apply a joystickforce factor to joystick input to obtain a
            #~ # smoother movement
            #~ return self.my_joystick.get_axis(0) * self.parameters['joystickforce'], self.my_joystick.get_axis(1) * self.parameters['joystickforce']
        #~ else:
            #~ return 0, 0

    def refreshModeLabel(self):
        if self.parameters['automaticsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif self.parameters['assistedsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def buildLog(self, thisList):
        thisList = ["TRACK"] + thisList
        self.parent().mainLog.addLine(thisList)
