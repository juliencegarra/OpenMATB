#-*- coding:utf-8 -*-

from PySide import QtCore, QtGui
from Helpers import WTank, WPump
import itertools
from Helpers.Translator import translate as _

class Task(QtGui.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # RESMAN PARAMETERS ###
        self.parameters = {
            'taskplacement': 'bottommid',
            'taskupdatetime': 2000,
            'title': 'Resources management',
            'heuristicsolver': False,
            'assistedsolver': False,
            'displayautomationstate': False,
            'pumpcoloroff' : '#AAAAAA',
            'pumpcoloron' : '#00FF00',
            'pumpcolorfailure' : '#FF0000',
            'tolerancelevel':500,
            'displaytolerance':True,

            'pump': {'1': {'flow': 800, 'state': 0, 'keys': [QtCore.Qt.Key_1], 'hide': 0},
                     '2': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_2, 233], 'hide': 0},
                     '3': {'flow': 800, 'state': 0, 'keys': [QtCore.Qt.Key_3], 'hide': 0},
                     '4': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_4],'hide': 0},
                     '5': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_5], 'hide': 0},
                     '6': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_6], 'hide': 0},
                     '7': {'flow': 400, 'state': 0, 'keys': [QtCore.Qt.Key_7, 232], 'hide': 0},
                     '8': {'flow': 400, 'state': 0, 'keys': [QtCore.Qt.Key_8], 'hide': 0}},

            'tank': {
                'a': {'level': 2500, 'max': 4000, 'target': 2500, 'depletable': 1, 'lossperminute': 800, 'hide': 0},
                'b': {'level': 2500, 'max': 4000, 'target': 2500, 'depletable': 1, 'lossperminute': 800, 'hide': 0},
                'c': {'level': 1000, 'max': 2000, 'target': None, 'depletable': 1, 'lossperminute': 0, 'hide': 0},
                'd': {'level': 1000, 'max': 2000, 'target': None, 'depletable': 1, 'lossperminute': 0, 'hide': 0},
                'e': {'level': 3000, 'max': 4000, 'target': None, 'depletable': 0, 'lossperminute': 0, 'hide': 0},
                'f': {'level': 3000, 'max': 4000, 'target': None, 'depletable': 0, 'lossperminute': 0, 'hide': 0}
            }
        }
        
        self.performance = {
            'total' : {},
            'last'  : {}
        }
        
        for this_cat in self.performance:
            for this_tank in self.parameters['tank']:
                if self.parameters['tank'][this_tank]['target'] is not None:
                    self.performance[this_cat][this_tank+'_in'] = 0
                    self.performance[this_cat][this_tank+'_out'] = 0
        
        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

    def onStart(self):

        if self.parameters['displayautomationstate']:
            # Define a QLabel object to display mode
            self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
            self.modeLabel = QtGui.QLabel(self)
            self.modeLabel.setGeometry(QtCore.QRect(self.width() * 0.42, self.height() * 0.40, self.width() * 0.20, 20))
            self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
            self.modeLabel.setFont(self.modeFont)
            self.refreshModeLabel()
            self.update()

        # If there is any tank that has a target, log the tolerance value
        if self.parameters['displaytolerance']:
            self.buildLog(["STATE", "TANK", "TOLERANCE", str(self.parameters['tolerancelevel'])])

        # For each defined tank
        for thisTank in self.parameters['tank'].keys():

            # Log its target value if it is set
            if self.parameters['tank'][thisTank]['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "TARGET", str(self.parameters['tank'][thisTank]['target'])])
                
                # Change tank initial level at the target level
                self.parameters['tank'][thisTank]['level'] = self.parameters['tank'][thisTank]['target']

             # Set a WTank Qt object
            self.parameters['tank'][thisTank]['ui'] = WTank.WTank(self)
            self.parameters['tank'][thisTank]['ui'].setMaxLevel(
                self.parameters['tank'][thisTank]['max'])
            self.parameters['tank'][thisTank]['ui'].locateAndSize(thisTank, self.parameters[
                                                                  'tank'][thisTank]['target'], self.parameters['tank'][thisTank]['depletable'])
            self.parameters['tank'][thisTank]['ui'].setLetter(thisTank.upper())

            # Display tank current capacity only if it is limited
            if self.parameters['tank'][thisTank]['depletable']:
                self.parameters['tank'][thisTank]['ui'].setLabel()

            # Display a target level when appropriate
            if self.parameters['tank'][thisTank]['target'] is not None:
                self.parameters['tank'][thisTank]['ui'].setTargetY(
                    self.parameters['tank'][thisTank]['target'], self.parameters['tank'][thisTank]['max'])

            # Show the resulting Qt object
            self.parameters['tank'][thisTank]['ui'].show()

        # For each defined pump
        for thisPump in self.parameters['pump'].keys():

            # Preallocate a variable to signal that a given pump fail has
            # already been logged
            self.parameters['pump'][thisPump]['failLogged'] = 0

            # Set a WPump Qt object
            self.parameters['pump'][thisPump]['ui'] = WPump.WPump(self, thisPump)
            self.parameters['pump'][thisPump]['ui'].locateAndSize()
            self.parameters['pump'][thisPump]['ui'].lower()

            # Show the resulting Qt object
            self.parameters['pump'][thisPump]['ui'].show()

        # Refresh visual information in case some initial values have been
        # altered in the scenario
        for thisTank in self.parameters['tank'].keys():
            self.parameters['tank'][thisTank]['ui'].refreshLevel(
                self.parameters['tank'][thisTank]['level'])

        for thisPump in self.parameters['pump'].keys():
            self.parameters['pump'][thisPump]['ui'].changeState(
                self.parameters['pump'][thisPump]['state'], self.parameters['pump'][thisPump]['hide'])


    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()

        time_resolution = (self.parameters['taskupdatetime'] / 1000) / 60.

        # 0. Compute automatic actions if heuristicsolver activated, three heuristics
        # Browse only woorking pumps (state != -1)

        if self.parameters['heuristicsolver'] or self.parameters['assistedsolver']:
            for this_pump in [pump for pump in self.parameters['pump'].keys() if self.parameters['pump'][pump]['state'] != -1]:
                fromtank = self.parameters['pump'][this_pump]['ui'].fromTank_label
                totank = self.parameters['pump'][this_pump]['ui'].toTank_label


                # 0.1. Systematically activate pumps draining non-depletable tanks
                if not self.parameters['tank'][fromtank]['depletable'] and self.parameters['pump'][this_pump]['state'] == 0 :
                    self.parameters['pump'][this_pump]['state'] = 1


                # 0.2. Activate/deactivate pump whose target tank is too low/high
                # "Too" means level is out of a tolerance zone around the target level (2500 +/- 150)
                if self.parameters['tank'][totank]['target'] is not None:
                    if self.parameters['tank'][totank]['level'] <= self.parameters['tank'][totank]['target'] - 150:
                        self.parameters['pump'][this_pump]['state'] = 1
                    elif self.parameters['tank'][totank]['level'] >= self.parameters['tank'][totank]['target'] + 150:
                        self.parameters['pump'][this_pump]['state'] = 0


                # 0.3. Equilibrate between the two A/B tanks if sufficient level
                if self.parameters['tank'][fromtank]['target'] is not None and self.parameters['tank'][totank]['target'] is not None:
                    if self.parameters['tank'][fromtank]['level'] >= self.parameters['tank'][totank]['target'] >= self.parameters['tank'][totank]['level']:
                        self.parameters['pump'][this_pump]['state'] = 1
                    else:
                        self.parameters['pump'][this_pump]['state'] = 0


        # 1. Deplete tanks A and B
        for thisTank in ['a', 'b']:
            volume = int(self.parameters['tank'][
                         thisTank]['lossperminute'] * time_resolution)
            volume = min(volume, self.parameters['tank'][thisTank][
                         'level'])  # If level less than volume, deplete only available level
            self.parameters['tank'][thisTank]['level'] -= volume

        # 2. For each pump
        for pumpNumber in self.parameters['pump'].keys():

            # 2.a Transfer flow if pump is ON
            if self.parameters['pump'][pumpNumber]['state'] == 1:

                fromtank, totank = self.parameters['pump'][pumpNumber]['ui'].fromTank_label, self.parameters['pump'][pumpNumber]['ui'].toTank_label

                # Compute volume
                volume = int(self.parameters['pump'][
                             pumpNumber]['flow']) * time_resolution

                # Check if this volume is available
                volume = min(
                    volume, self.parameters['tank'][fromtank]['level'])

                # Drain it from tank (if its capacity is limited)...
                if self.parameters['tank'][fromtank]['depletable']:
                    self.parameters['tank'][fromtank]['level'] -= int(volume)

                # ...to tank (if it's not full)
                volume = min(volume, self.parameters['tank'][totank][
                             'max'] - self.parameters['tank'][totank]['level'])
                self.parameters['tank'][totank]['level'] += int(volume)

            # 2.b Modify flows according to pump states
            elif self.parameters['pump'][pumpNumber]['state'] != 1 or self.parameters['pump'][pumpNumber]['hide']:  # (OFF | FAIL => 0)
                if self.parameters['pump'][pumpNumber]['state'] == -1 and not self.parameters['pump'][pumpNumber]['failLogged']:
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "FAIL"])
                    self.parameters['pump'][pumpNumber]['failLogged'] = True

                if self.parameters['pump'][pumpNumber]['state'] == 0 and self.parameters['pump'][pumpNumber]['failLogged']:
                    self.parameters['pump'][pumpNumber]['failLogged'] = False
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "OFF"])

        # 3. For each tank
        for thisTank in self.parameters['tank'].keys():
            pumps_to_deactivate = []

            # If it is full, select incoming pumps for deactivation
            if self.parameters['tank'][thisTank]['level'] >= self.parameters['tank'][thisTank]['max']:
                pumps_to_deactivate = [self.parameters['pump'].keys()[i] for i in range(
                    0, len(self.parameters['pump'])) if self.parameters['pump'][self.parameters['pump'].keys()[i]]['ui'].toTank_label == thisTank]

            # Likewise, if it is empty, select outcome pumps for deactivation
            elif self.parameters['tank'][thisTank]['level'] <= 0:
                pumps_to_deactivate = [self.parameters['pump'].keys()[i] for i in range(
                    0, len(self.parameters['pump'])) if self.parameters['pump'][self.parameters['pump'].keys()[i]]['ui'].fromTank_label == thisTank]

            # Deactivate selected pumps if not on failure
            for thisPump in pumps_to_deactivate:
                if not self.parameters['pump'][thisPump]['state'] == -1:  # if not Fail
                    self.parameters['pump'][thisPump]['state'] = 0
                    self.buildLog(["STATE", "PUMP" + thisPump, "OFF"])

        # 4. Refresh visual information
        for thisPump in self.parameters['pump'].keys():
            self.parameters['pump'][thisPump]['ui'].changeState(self.parameters['pump'][thisPump]['state'], self.parameters['pump'][thisPump]['hide'])

        for thisTank in self.parameters['tank'].keys():
            self.parameters['tank'][thisTank]['ui'].refreshLevel(self.parameters['tank'][thisTank]['level'])

        # 5. Log tank level if a target is set           
        for thisTank in self.parameters['tank'].keys():
            if self.parameters['tank'][thisTank]['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "LEVEL", str(self.parameters['tank'][thisTank]['level'])])
                
                for this_cat in self.performance:
                    local_dev = abs(self.parameters['tank'][thisTank]['level'] - self.parameters['tank'][thisTank]['target'])
                    if local_dev <= self.parameters['tolerancelevel']:
                        self.performance[this_cat][thisTank.lower()+'_in']+=1
                    else:
                        self.performance[this_cat][thisTank.lower()+'_out']+=1
        self.update()


    def keyEvent(self, key_pressed):

        if self.parameters['heuristicsolver']:
            return
        else:
            # List accepted keys
            accepted_keys = list(itertools.chain.from_iterable(
                [self.parameters['pump'][thisKey]['keys'] for thisKey in self.parameters['pump'].keys()]))

            if key_pressed in accepted_keys:

                # Select pump that corresponds to the key...
                pump_number = [thisKey for thisKey in self.parameters['pump']
                               .keys() if key_pressed in self.parameters['pump'][thisKey]['keys']][0]

                # ...and reverse its state if it is not on failure
                if not self.parameters['pump'][pump_number]['state'] == -1:
                    self.parameters['pump'][pump_number]['state'] = abs(self.parameters['pump'][pump_number]['state'] - 1)
                    stateStr = 'ON' if self.parameters['pump'][pump_number]['state'] == 1 else 'OFF'

                    # Log any pump state change
                    self.buildLog(["STATE", "PUMP" + pump_number, stateStr])
                    del stateStr

                self.repaint()  # Refresh
            else:
                return

    def refreshModeLabel(self):
        if self.parameters['heuristicsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif self.parameters['assistedsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def buildLog(self, thisList):
        thisList = ["RESMAN"] + thisList
        self.parent().mainLog.addLine(thisList)
