from PySide2 import QtCore, QtWidgets, QtGui
from Helpers.Translator import translate as _
from Helpers import QTExtensions

class Task(QtWidgets.QWidget):
    # TODO : implement performance computation for the 'communications' Task
    # TODO : Identification of target tanks must be dynamic
    # TODO : record total performance also
    # TODO : implement an online feedback (in onUpdate method)

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime' : None,
            'feedbackduration' : 5
        }

        self.performances = {}

        self.mainFont = QtGui.QFont("Times", round(self.parent().screen_height/60.))
        self.mainFont.setStyleStrategy(QtGui.QFont.PreferAntialias)

        self.feedback_timer = QTExtensions.QTimerWithPause(self)
        self.feedback_timer.timeout.connect(self.onStop)

    def onStart(self):
        # Prepare a dict for each task that records performance
        for this_plugin in self.parent().PLUGINS_TASK:
            if hasattr(self.parent().PLUGINS_TASK[this_plugin]['class'], 'performance'):
                self.performances[this_plugin] = dict()


        # Retrieve performance values since last feedback, store it in a dict
        for this_plugin in self.performances:
            self.performances[this_plugin]['infos'] = self.parent().PLUGINS_TASK[this_plugin]['class'].performance

            # Prepare text object
            what_location = self.parent().PLUGINS_TASK[this_plugin]['class'].parameters['taskplacement']
            placement = self.parent().placements[what_location]
            self.performances[this_plugin]['uis'] = dict()
            self.performances[this_plugin]['uis']['perf_label'] = QtWidgets.QLabel(self)
            self.performances[this_plugin]['uis']['perf_label'].setGeometry(QtCore.QRect(placement['control_left'], placement['control_top'], placement['control_width'], placement['control_height']))
            self.performances[this_plugin]['uis']['perf_label'].setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            self.performances[this_plugin]['uis']['perf_label'].setFont(self.mainFont)

            text = str()
            if this_plugin == 'resman':
                for this_tank in ['a', 'b']:
                    perf = round(self.performances[this_plugin]['infos']['last'][this_tank+'_in'] / (self.performances[this_plugin]['infos']['last'][this_tank+'_in'] + self.performances[this_plugin]['infos']['last'][this_tank+'_out']) * 100,1) if (self.performances[this_plugin]['infos']['last'][this_tank+'_in'] + self.performances[this_plugin]['infos']['last'][this_tank+'_out']) != 0 else 100
                    this_text = _("%s tank: on average, you have maintained this tank at a correct level %s%% of time") % (this_tank.upper(), perf)
                    text += this_text + '\r\n'
                self.performances[this_plugin]['uis']['perf_label'].setWordWrap(1)
                self.performances[this_plugin]['uis']['perf_label'].setText(text)

            elif this_plugin == 'sysmon':
                hit = self.performances[this_plugin]['infos']['last']['hit_number']
                miss = self.performances[this_plugin]['infos']['last']['miss_number']
                rate = self.performances[this_plugin]['infos']['last']['hit_number'] / (self.performances[this_plugin]['infos']['last']['hit_number'] +  self.performances[this_plugin]['infos']['last']['miss_number']) if (self.performances[this_plugin]['infos']['last']['hit_number'] +  self.performances[this_plugin]['infos']['last']['miss_number']) != 0 else 1

                rate = round(rate * 100,1)

                text = _("On average, you corrected %s out of %s of failures (%s%%)") % (hit, hit+miss, rate)
                self.performances[this_plugin]['uis']['perf_label'].setWordWrap(1)
                self.performances[this_plugin]['uis']['perf_label'].setText(text)


            elif this_plugin == 'track':
                time_in_rate = float(self.performances[this_plugin]['infos']['total']['time_in_ms']) / (self.performances[this_plugin]['infos']['total']['time_in_ms'] + self.performances[this_plugin]['infos']['total']['time_out_ms']) if (self.performances[this_plugin]['infos']['total']['time_in_ms'] + self.performances[this_plugin]['infos']['total']['time_out_ms']) != 0 else 1
                perc = round(time_in_rate * 100,1)


                text = _("On average, you spent %s%% of time inside the target") % perc

                self.performances[this_plugin]['uis']['perf_label'].setWordWrap(1)
                self.performances[this_plugin]['uis']['perf_label'].setText(text)


        # Pause all, hide all the running task, but not their ui_label
        self.parent().onPause(hide_ui=False)
        for this_plugin in self.performances:
            self.performances[this_plugin]['uis']['perf_label'].show()
        self.show()

        self.feedback_timer.start(self.parameters['feedbackduration'] * 1000)

    def onStop(self):
        self.feedback_timer.stop()
        for this_plugin in self.performances:
            # Reset local performance indexes
            for this_index in self.parent().PLUGINS_TASK[this_plugin]['class'].performance['last']:
                self.parent().PLUGINS_TASK[this_plugin]['class'].performance['last'][this_index] = 0

            # And hide the corresponding Qt object
            self.performances[this_plugin]['uis']['perf_label'].hide()

        self.hide()
        self.parent().onResume()

    def onUpdate(self):
        pass
