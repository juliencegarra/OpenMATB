# -*- coding:utf-8 -*-

from PySide2 import QtCore, QtWidgets, QtGui
from Helpers import WTank, WPump
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

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
            'pumpcoloroff': '#AAAAAA',
            'pumpcoloron': '#00FF00',
            'pumpcolorfailure': '#FF0000',
            'tolerancelevel': 500,
            'displaytolerance': True,
            'resetperformance': None,

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
            'total': {},
            'last': {}
        }

        for this_cat in self.performance:
            for this_tank in self.parameters['tank']:
                if self.parameters['tank'][this_tank]['target'] is not None:
                    self.performance[this_cat][this_tank+'_in'] = 0
                    self.performance[this_cat][this_tank+'_out'] = 0

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

    def onStart(self):
        # Define a QLabel object to display mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.),
                                    QtGui.QFont.Bold)
        self.modeLabel = QtWidgets.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(self.width() * 0.42, self.height() * 0.40, self.width() * 0.20, 20))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)
        self.refreshModeLabel()
        self.update()

        # If there is any tank that has a target, log the tolerance value
        if self.parameters['displaytolerance']:
            self.buildLog(["STATE", "TANK", "TOLERANCE",
                           str(self.parameters['tolerancelevel'])])

        # For each defined tank
        for thisTank, tankValues in self.parameters['tank'].items():

            # Log its target value if it is set
            if tankValues['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "TARGET",
                               str(tankValues['target'])])

                # Change tank initial level at the target level
                tankValues['level'] = tankValues['target']

            # Set a WTank Qt object
            tankValues['ui'] = WTank.WTank(self)
            tankValues['ui'].setMaxLevel(tankValues['max'])
            tankValues['ui'].locateAndSize(thisTank, tankValues['target'],
                                           tankValues['depletable'])
            tankValues['ui'].setLetter(thisTank.upper())

            # Display tank current capacity only if it is limited
            if tankValues['depletable']:
                tankValues['ui'].setLabel()

            # Display a target level when appropriate
            if tankValues['target'] is not None:
                tankValues['ui'].setTargetY(tankValues['target'],
                                            tankValues['max'])

            # Show the resulting Qt object
            tankValues['ui'].show()

        # For each defined pump
        for thisPump, pumpValues in self.parameters['pump'].items():

            # Preallocate a variable to signal that a given pump fail has
            # already been logged
            pumpValues['failLogged'] = 0

            # Set a WPump Qt object
            pumpValues['ui'] = WPump.WPump(self, thisPump)
            pumpValues['ui'].locateAndSize()
            pumpValues['ui'].lower()

            # Show the resulting Qt object
            pumpValues['ui'].show()

        # Refresh visual information in case some initial values have been
        # altered in the scenario
        for thisTank, tankValues in self.parameters['tank'].items():
            tankValues['ui'].refreshLevel(tankValues['level'])

        for thisPump, pumpValues in self.parameters['pump'].items():
            pumpValues['ui'].changeState(pumpValues['state'],
                                         pumpValues['hide'])

    def onUpdate(self):
        if self.parameters['displayautomationstate'] is True:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        if self.parameters['resetperformance'] in ['last', 'global']:
            for i in self.performance[self.parameters['resetperformance']]:
                self.performance[self.parameters['resetperformance'][i]] = 0
            self.parameters['resetperformance'] = None
        elif self.parameters['resetperformance'] is not None:
            self.parent().showCriticalMessage(_("%s : wrong argument in resman;resetperformance") % self.parameters['resetperformance'])

        time_resolution = (self.parameters['taskupdatetime'] / 1000) / 60.

        # 0. Compute automatic actions if heuristicsolver activated, three heuristics
        # Browse only woorking pumps (state != -1)

        if self.parameters['heuristicsolver'] or self.parameters['assistedsolver']:
            working_pumps = {p: v for p, v in self.parameters['pump'].items()
                             if v['state'] != -1}

            for thisPump, pumpValue in working_pumps.items():
                fromtank = self.parameters['tank'][
                            pumpValue['ui'].fromTank_label]
                totank = self.parameters['tank'][
                            pumpValue['ui'].toTank_label]

                # 0.1. Systematically activate pumps draining non-depletable tanks
                if not fromtank['depletable'] and pumpValue['state'] == 0:
                    pumpValue['state'] = 1

                # 0.2. Activate/deactivate pump whose target tank is too low/high
                # "Too" means level is out of a tolerance zone around the target level (2500 +/- 150)
                if totank['target'] is not None:
                    if totank['level'] <= totank['target'] - 150:
                        pumpValue['state'] = 1
                    elif totank['level'] >= totank['target'] + 150:
                        pumpValue['state'] = 0

                # 0.3. Equilibrate between the two A/B tanks if sufficient level
                if fromtank['target'] is not None and totank['target'] is not None:
                    if fromtank['level'] >= totank['target'] >= totank['level']:
                        pumpValue['state'] = 1
                    else:
                        pumpValue['state'] = 0


        # 1. Deplete tanks A and B
        for thisTank in ['a', 'b']:
            tankValue = self.parameters['tank'][thisTank]
            volume = int(tankValue['lossperminute'] * time_resolution)
            volume = min(volume, tankValue['level'])  # If level less than volume, deplete only available level
            tankValue['level'] -= volume

        # 2. For each pump
        for pumpNumber, pumpValues in self.parameters['pump'].items():

            # 2.a Transfer flow if pump is ON
            if pumpValues['state'] == 1:

                fromtank = self.parameters['tank'][
                    pumpValues['ui'].fromTank_label]
                totank = self.parameters['tank'][
                    pumpValues['ui'].toTank_label]

                # Compute volume
                volume = int(pumpValues['flow']) * time_resolution

                # Check if this volume is available
                volume = min(volume, fromtank['level'])

                # Drain it from tank (if its capacity is limited)...
                if fromtank['depletable']:
                    fromtank['level'] -= int(volume)

                # ...to tank (if it's not full)
                volume = min(volume, totank['max'] - totank['level'])
                totank['level'] += int(volume)

            # 2.b Modify flows according to pump states (OFF | FAIL => 0)
            elif pumpValues['state'] != 1 or pumpValues['hide']:
                if pumpValues['state'] == -1 and not pumpValues['failLogged']:
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "FAIL"])
                    pumpValues['failLogged'] = True

                if pumpValues['state'] == 0 and pumpValues['failLogged']:
                    pumpValues['failLogged'] = False
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "OFF"])

        # 3. For each tank
        for thisTank, tankValues in self.parameters['tank'].items():
            pumps_to_deactivate = []

            # If it is full, select incoming pumps for deactivation
            if tankValues['level'] >= tankValues['max']:
                pumps_to_deactivate.append(p for p, v in
                                           self.parameters['pump'].items()
                                           if v['ui'].toTank_label == thisTank)

            # Likewise, if it is empty, select outcome pumps for deactivation
            elif self.parameters['tank'][thisTank]['level'] <= 0:
                pumps_to_deactivate.append(p for p, v in
                                           self.parameters['pump'].items()
                                           if v['ui'].fromTank_label ==
                                           thisTank)

            # Deactivate selected pumps if not on failure
            for thesePumps in pumps_to_deactivate:
                for thisPump in thesePumps:
                    if not self.parameters['pump'][thisPump]['state'] == -1:
                        self.parameters['pump'][thisPump]['state'] = 0
                        self.buildLog(["STATE", "PUMP" + thisPump, "OFF"])

        # 4. Refresh visual information
        for thisPump, pumpValue in self.parameters['pump'].items():
            pumpValue['ui'].changeState(pumpValue['state'], pumpValue['hide'])

        for thisTank, tankValue in self.parameters['tank'].items():
            tankValue['ui'].refreshLevel(tankValue['level'])

        # 5. Log tank level if a target is set
            if tankValue['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "LEVEL",
                               str(tankValue['level'])])

                for perf_cat, perf_val in self.performance.items():
                    local_dev = abs(tankValue['level'] - tankValue['target'])
                    if local_dev <= self.parameters['tolerancelevel']:
                        perf_val[thisTank.lower()+'_in'] += 1
                    else:
                        perf_val[thisTank.lower()+'_out'] += 1
        self.update()

    def keyEvent(self, key_pressed):

        if self.parameters['heuristicsolver']:
            return
        else:
            # List accepted keys
            accepted_keys = [v['keys'] for p, v in
                             self.parameters['pump'].items()]
            accepted_keys = [i for s in accepted_keys for i in s]

            if key_pressed in accepted_keys:
                # Select pump(s) that corresponds to the key...
                pumps = {p: v for p, v in self.parameters['pump'].items()
                         if key_pressed in v['keys'] and v['state'] != -1}

                # ...and reverse its state if it is not on failure
                for thisPump, pumpValue in pumps.items():
                    pumpValue['state'] = abs(pumpValue['state'] - 1)
                    # Log any pump state change
                    self.buildLog(["STATE", "PUMP" + thisPump,
                                   'ON' if pumpValue['state'] == 1 else 'OFF'])

                self.repaint()  # Refresh
            else:
                return

    def refreshModeLabel(self):
        if self.parameters['heuristicsolver'] is True:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif self.parameters['assistedsolver'] is True:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def buildLog(self, thisList):
        thisList = ["RESMAN"] + thisList
        self.parent().mainLog.addLine(thisList)
