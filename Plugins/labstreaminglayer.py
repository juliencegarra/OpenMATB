from PySide2 import QtCore, QtWidgets
import time
from random import random as rand
try:
    # Could fail if pylsl is not available.
    from pylsl import StreamInfo, StreamOutlet
except:
    # Continue in case of failure. If the plugin is not used, that's not a problem.
    pass

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
            'title' : 'Lab Streaming Layer',
            # The onUpdate function should be called approximatively every 10 ms.
            'taskupdatetime' : 10,
            'marker' : '',
        }

        self.stream_info = None
        self.stream_outlet = None

    def onStart(self):
        # If we get there it's because the plugin is used.
        # If pylsl is not available this part should fail.
        # Create a LSL marker outlet.
        self.stream_info = StreamInfo('openMATB', type='Markers', channel_count=1, nominal_srate=0, channel_format='string', source_id='myuidw435368')
        self.stream_outlet = StreamOutlet(self.stream_info)

    def onUpdate(self):
        if self.parameters['marker'] != '':
            # A marker has been set. Push it to the outlet.
            self.pushMarker(self.parameters['marker'])
            # Reset the marker to empty.
            self.parameters['marker'] = ''

    def onStop(self):
        self.stream_info = None
        self.stream_outlet = None

    def pushMarker(self, marker):
        self.stream_outlet.push_sample([marker])
        self.buildLog(['MARKER', marker])

    def buildLog(self, thisList):
        thisList = ["LABSTREAMINGLAYER"] + thisList
        self.parent().mainLog.addLine(thisList)
