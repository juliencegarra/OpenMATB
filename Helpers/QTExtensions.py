from PySide2 import QtCore, QtGui
import time


class QTimerWithPause (QtCore.QTimer):

    """ A modifier QTimer which allow to pause and resume the timer"""

    def __init__(self, parent):
        QtCore.QTimer.__init__(self)
        self.startTime = 0
        self.interval = 0
        self.needToBeResumed = False
        parent.parent().timerRegister(self)

    def start(self, interval):
        self.interval = interval
        self.startTime = time.time()
        self.needToBeResumed = True
        QtCore.QTimer.start(self, interval)  # one-shot

    def stop(self):
        self.needToBeResumed = False
        QtCore.QTimer.stop(self)

    def pause(self):
        if self.isActive() and self.needToBeResumed:
            self.stop()

            # time() returns float secs, interval is int msec
            elapsedTime = time.time() - self.startTime
            oldi = self.interval
            self.interval -= int(elapsedTime * 1000)

            if self.interval < 0:
                self.interval = 0

    def resume(self):
        if not self.isActive() and self.needToBeResumed:
            self.start(self.interval)
