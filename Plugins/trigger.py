from PySide2 import QtWidgets, QtCore
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS

        # The trigger will be send during a specific duration (e.g. 2 msecs) to
        # be correctly detected
        self.timertrigger = QtCore.QTimer()
        self.timertrigger.timeout.connect(self.endTrigger)

        self.parameters = {
            'taskplacement': None,
            'taskupdatetime': None,
            'downvalue': '00000000',
            'upvalue': '00000001',
            'delay': 2,  # 2msecs before going back to nominal state
            'port': 0x378
        }

        self.DEFAULT_EMPTY_TRIGGER = self.parameters[
            'downvalue']  # = no trigger
        self.current_triggervalue = self.DEFAULT_EMPTY_TRIGGER
        self.awaiting_triggers = []

    def onStart(self):
        if not os.path.exists(os.path.join('..', 'inpout32.dll')):
            reply = QtWidgets.QMessageBox.question(
                None, _('Error'), _("The file '%s' was not found in the current directory. It will not be possible to send trigger events. Do you want to continue?") % 'inpout32.dll', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.No:
                self.parent().onEnd()
                return

    def onTrigger(self):
        self.parent().addLog("TRIGGER;" + self.parameters['upvalue'])

        val = int(self.parameters['upvalue'], 2)

        if self.current_triggervalue != self.DEFAULT_EMPTY_TRIGGER:
            # store in queue if already sending a trigger
            self.awaiting_triggers.append(val)
        else:
            self.current_triggervalue = self.parameters['upvalue']
            ctypes.windll.inpout32.Out32(self.parameters['port'], val)
            self.timertrigger.start(self.parameters['delay'])

    def endTrigger(self):
        # Manage awaiting triggers
        self.timertrigger.stop()

        while len(self.awaiting_triggers) > 0:
            nexttrigger = self.awaiting_triggers[0]
            self.awaiting_triggers.removeAt(0)
            ctypes.windll.inpout32.Out32(self.parameters['port'], nexttrigger)

        ctypes.windll.inpout32.Out32(
            self.parameters['port'], self.DEFAULT_EMPTY_TRIGGER)
        self.current_triggervalue = self.DEFAULT_EMPTY_TRIGGER
