from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtCore import QTimer
import os
from Helpers.Translator import translate as _


class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': None,
            'filename': '',
            'pointsize': 0,
            'durationsec': 0
        }

        self.screen_width = self.parent().screen_width
        self.screen_height = self.parent().screen_height

        self.font = QtGui.QFont("Times", round(self.screen_height/54.))
        self.font.setStyleStrategy(QtGui.QFont.PreferAntialias)

    def onStart(self):
        if self.parameters['pointsize'] > 0:
            self.font.setPointSize(self.parameters['pointsize'])

        self.parent().onPause()
        self.LoadText(self.parameters['filename'])
        self.setLayout(self.layout)
        self.show()
        if self.parameters['durationsec'] > 0:
            durationms = self.parameters['durationsec'] * 1000
            QTimer.singleShot(durationms, self.terminate)
            self.parameters['durationsec'] = 0

    def LoadText(self, textfile):
        # Load scales from file
        if len(textfile) == 0:
            self.parent().showCriticalMessage(_("No file to load!"))
            return

        filepath = os.path.join(self.parent().instructions_directory, textfile)

        if not os.path.exists(filepath):
            self.parent().showCriticalMessage(
                _("Unable to find the text file: '%s'") % filepath)
            return

        with open(filepath, 'r') as txt:
            instructions = txt.read()
        instructions_ui = QtWidgets.QLabel(instructions)
        instructions_ui.setFont(self.font)
        instructions_ui.setWordWrap(True)
        instructions_ui.setAlignment(QtCore.Qt.AlignCenter)

        self.layout = QtWidgets.QVBoxLayout(self)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(instructions_ui)
        self.layout.addLayout(hbox)

        self.layout.addStretch(1)

        if self.parameters['durationsec'] == 0:
            self.continue_button = QtWidgets.QPushButton(_('Continue'))
            self.continue_button.setMaximumWidth(0.25 * self.screen_width)
            self.continue_button.clicked.connect(self.terminate)
            hbox = QtWidgets.QHBoxLayout()
            hbox.addWidget(self.continue_button)
            self.layout.addLayout(hbox)

    def onUpdate(self):
        pass

    def terminate(self):
        self.buildLog([self.parameters['filename'], 'END'])
        # Force to reparent and destroy the layout
        QtWidgets.QWidget().setLayout(self.layout)
        self.parent().onResume()

    def buildLog(self, thisList):
        thisList = 'INSTRUCTION' + thisList
        self.parent().mainLog.addLine(thisList)
