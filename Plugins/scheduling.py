from PySide2 import QtWidgets
from Helpers import WScheduler
import datetime
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # SCHEDULING PARAMETERS ###
        self.parameters = {
            'title': 'Scheduling',
            'taskplacement': "topright",
            'taskupdatetime': 1000
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

    def onStart(self):

        # Retrieve scenario events for the tracking and the communication tasks
        self.tracking_schedule, self.communication_schedule = self.getSchedule()

        # Get the time of the last event
        maxTime_sec = max([self.dateStringToSecondInteger(this_time)
                          for this_time, value in self.parent().scenariocontents.items()])

        # Set a Qt layout
        layout = QtWidgets.QGridLayout()

        # Set a WScheduler Qt object
        self.widget = WScheduler.WScheduler(self, self.tracking_schedule, self.communication_schedule, maxTime_sec, _('Elapsed Time'))
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # Compute tasks progression as a function of current scenario time
        self.widget.getProgression(self.parent().scenarioTimeStr)

    def onUpdate(self):
        # Compute tasks progression as a function of current scenario time
        self.widget.getProgression(self.parent().scenarioTimeStr)

        # And refresh visual display
        self.update()

    def getSchedule(self):
        """Read self.parent().scenariocontents. Schedules show manual mode phases"""

        schedules = dict(track = [], communications = [])

        for this_task in schedules.keys():
            this_dict = {key: value for key, value in self.parent().scenariocontents.items() if this_task in value}

            if any([['start'] in value[this_task] for key, value in this_dict.items()]):
                starttime = [key for key, value in this_dict.items() if ['start'] in value[this_task]][0]
                this_start = [key for key, value in this_dict.items() if ['start'] in value[this_task]][0]
                try:
                    endtime = [key for key, value in this_dict.items() if 'stop' in value[this_task][0]][0]
                except:
                    self.parent().showCriticalMessage(_("Can't compute schedule. No 'stop' signal found in scenario for the %s task") % (this_task))

                # Browse scenario content in sorted order
                # While automaticsolver is OFF : manual/assisted mode is ON
                for this_time in sorted(this_dict):
                    if ['automaticsolver', 'True'] in this_dict[this_time][this_task] or ['automaticsolver', 'False'] in this_dict[this_time][this_task]:
                        if ['automaticsolver', 'True'] in this_dict[this_time][this_task]:
                            this_end = this_time
                        elif ['automaticsolver', 'False'] in this_dict[this_time][this_task]:
                            this_start = this_time

                        if 'this_start' in locals() and 'this_end' in locals() and this_start < this_end:
                            schedules[this_task].append([self.dateStringToSecondInteger(this_start), self.dateStringToSecondInteger(this_end)])
                if this_start < endtime and this_start != starttime:
                    schedules[this_task].append([self.dateStringToSecondInteger(this_start), self.dateStringToSecondInteger(endtime)])

                if len(schedules[this_task]) == 0:
                    schedules[this_task].append([self.dateStringToSecondInteger(starttime), self.dateStringToSecondInteger(endtime)])
        return schedules['track'], schedules['communications']

    def dateStringToSecondInteger(self, date_string, format_string="%H:%M:%S"):
        '''Convert a date string into seconds (int)'''
        date_object = datetime.datetime.strptime(date_string, format_string)
        insecond = date_object.second + \
            date_object.minute * 60 + date_object.hour * 60 ** 2
        return insecond
