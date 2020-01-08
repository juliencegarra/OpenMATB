from PySide2 import QtCore, QtWidgets
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': None
        }

    def onStart(self):
        self.parent().onPause()

        self.participant = QtWidgets.QLineEdit(self)

        self.participantlabel = QtWidgets.QLabel(_("Participant ID:"), self)
        self.participantlabel.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")

        self.participantbtn = QtWidgets.QPushButton(_('Start'), self)
        self.participantbtn.resize(self.participantbtn.sizeHint())

        h = (self.parent().screen_height - (self.participantlabel.height()
             + self.participant.height() + self.participantbtn.height()) + 50) / 2

        self.participantlabel.move(
            (self.parent().screen_width - self.participantlabel.width()) / 2, h)

        self.participant.move(
            (self.parent().screen_width - self.participant.width()) / 2, h + self.participantlabel.height() + 25)
        self.participantbtn.move((self.parent().screen_width - self.participant.width())
                                 / 2, h + self.participantlabel.height() + self.participant.height() + 25)

        self.participantbtn.clicked.connect(self.onClose)
        self.participant.show()
        self.participant.setFocus()
        self.participantlabel.show()
        self.participantbtn.show()
        self.show()


    def onClose(self):
        # self.hide()
        self.participant.hide()
        self.participantlabel.hide()
        self.participantbtn.hide()

        self.parent().mainLog.addLine(
            ["PARTICIPANTINFO", "INPUT", "PARTID", str(self.participant.text())])

        self.parent().onResume()
