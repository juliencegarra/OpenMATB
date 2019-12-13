from PySide2 import QtCore, QtWidgets
import time
from random import random as rand
try:
    from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream
except:
    pass

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
        'taskupdatetime' : 10,
        }

        self.info = None
        self.outlet = None

    def onStart(self):
        try:
            log_info = StreamInfo('LogStream', 'Markers', 1, 0, 'string', 'myuidw43536')
            self.info_outlet = StreamOutlet(log_info)
        except:
            pass

    def onUpdate(self):
        pass

    def onStop(self):
        pass

    def onLog(self, chain):
#        print chain
        if hasattr(self, 'info_outlet'):
            self.info_outlet.push_sample([chain])
