from PySide import QtCore, QtGui

# Ignoré par le git


class Task(QtGui.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': 100
        }

    def onStart(self):
        h = 40

        self.screen_width = QtGui.QApplication.desktop().screen().width()
        self.screen_height = QtGui.QApplication.desktop().screen().height()

        self.title = QtGui.QLabel(u"Nombre d'erreurs :", self)
        self.title.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")
        self.title.resize(self.title.sizeHint())
        self.title.move((self.screen_width - self.title.width()) / 2, h)

        self.titleperf = QtGui.QLabel(u"", self)
        self.titleperf.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")

    def taskTimedUpdate(self):

        h = 40
        perf = str(self.parent().perfFailCount) + " / " + str(
            self.parent().perfSuccessCount + self.parent().perfFailCount)
        self.titleperf.setText(perf)
        self.titleperf.resize(self.titleperf.sizeHint())
        self.titleperf.move(
            (self.screen_width - self.titleperf.width()) / 2, h * 2)
        self.titleperf.show()
        self.title.show()
