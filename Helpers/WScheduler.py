from PySide2 import QtWidgets, QtCore, QtGui

class WScheduler (QtWidgets.QWidget):

    def __init__(self, parent, tracking_schedule, communication_schedule, maxTime_sec, label):
        super(WScheduler, self).__init__(parent)

        self.schedule_duration_mn = 8
        self.current_time_sec = 0
        self.schedule_limit_sec = self.schedule_duration_mn * 60
        self.maxTime_sec = maxTime_sec

        # Display options
        fontsize = int(self.parent().height() / 35.)
        self.font = QtGui.QFont("sans-serif", fontsize, QtGui.QFont.Bold)
        self.thinfont = QtGui.QFont("sans-serif", fontsize)
        self.minFont = QtGui.QFont("sans-serif", fontsize - 1, QtGui.QFont.StyleItalic)
        self.trait_width = fontsize / 3.

        self.task_ulx = 0.1 * self.parent().width()
        self.task_width = 0.8 * self.parent().width()
        self.task_uly = 0.05 * self.parent().height()
        self.task_height = 0.75 * self.parent().height()
        self.time_height = 0.15 * self.parent().height()
        self.axeWidth = 0.25 * self.parent().width()

        lowerspace = self.task_uly + 20
        upperspace = self.task_uly + self.task_height - 40
        length =self.schedule_duration_mn * 2 + 1
        self.breaks_list = [lowerspace + x*(upperspace-lowerspace)/length for x in range(length)]

        self.tracking_ulx = self.task_ulx + 0.8 * self.task_width
        self.communication_ulx = self.task_ulx + 0.2 * self.task_width
        self.schedule_up = self.breaks_list[0]
        self.schedule_down = self.breaks_list[-1]

        # Schedules
        self.schedules = dict(track = tracking_schedule, communication = communication_schedule)

        self.green_pen = QtGui.QPen(QtGui.QColor('#009900'), min(1, self.trait_width - 2))
        self.lightblue_pen = QtGui.QPen(QtGui.QColor('#729fcf'), self.trait_width, QtCore.Qt.SolidLine)
        self.red_pen = QtGui.QPen(QtGui.QColor('#ff0000'), self.trait_width - 1, QtCore.Qt.SolidLine)

        self.T_letter = QtWidgets.QLabel(self)
        self.T_letter.setText('T')
        self.T_letter.setFont(self.font)
        self.T_letter.setGeometry(QtCore.QRect(self.tracking_ulx - self.axeWidth / 2, self.breaks_list[-1], self.axeWidth, 55))
        self.T_letter.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)

        self.C_letter = QtWidgets.QLabel(self)
        self.C_letter.setText('C')
        self.C_letter.setFont(self.font)
        self.C_letter.setGeometry(QtCore.QRect(self.communication_ulx - self.axeWidth / 2, self.breaks_list[-1], self.axeWidth, 55))
        self.C_letter.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)

        self.min_label = QtWidgets.QLabel(self)
        self.min_label.setText('min')
        self.min_label.setFont(self.minFont)
        self.min_label.setGeometry(QtCore.QRect(self.task_ulx + self.task_width / 2 - 20, self.breaks_list[-1], 40, 55))
        self.min_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)

        self.time_string_label = QtWidgets.QLabel(self)
        self.time_string_label.setText('0:00:00')
        self.time_string_label.setFont(self.thinfont)
        self.time_string_label.setGeometry(
            QtCore.QRect(self.task_ulx, self.task_uly + self.task_height, self.task_width, self.time_height))
        self.time_string_label.setAlignment(
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)

        self.time_label = QtWidgets.QLabel(self)
        self.time_label.setText(label)
        self.time_label.setFont(self.thinfont)
        self.time_label.setGeometry(
            QtCore.QRect(self.task_ulx, self.task_uly + self.task_height, self.task_width, self.time_height))
        self.time_label.setAlignment(
            QtCore.Qt.AlignTop | QtCore.Qt.AlignCenter)

        self.digits = {}
        for t, this_y in enumerate(self.breaks_list):
            self.digits[str(t)] = QtWidgets.QLabel(self)
            self.digits[str(t)].setText(str(t / 2))
            self.digits[str(t)].setFont(self.font)
            self.digits[str(t)].setGeometry(
                QtCore.QRect(self.task_ulx + self.task_width / 2 - self.axeWidth / 2, this_y - 20, self.axeWidth, 40))
            self.digits[str(t)].setAlignment(
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)

    def getProgression(self, current_time):
        self.time_string_label.setText(current_time)
        self.current = dict(track = [], communication = [])

        self.current_time_sec = self.parent().dateStringToSecondInteger(current_time)
        self.schedule_limit_sec = self.current_time_sec + self.schedule_duration_mn * 60

        for this_task in self.current.keys():
            for i, this_interval in enumerate(self.schedules[this_task]):
                if len(this_interval):
                    self.current[this_task].append([])
                    for t, this_time in enumerate(this_interval):
                        self.current[this_task][i].append(
                            round((float(max(self.current_time_sec, min(self.schedule_limit_sec, this_time)) -
                                  self.current_time_sec) / (self.schedule_duration_mn * 60)) *
                                  (self.breaks_list[-1] - self.breaks_list[0])))

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawAxes(qp)
        qp.end()

    def drawAxes(self, qp):

        # Draw subtask border
        qp.setPen(self.lightblue_pen)
        qp.drawRect(QtCore.QRect(self.task_ulx, self.task_uly, self.task_width, self.task_height))

        # Draw the railroad
        qp.drawLine(self.task_ulx + self.task_width / 2 - 20, self.task_uly,
                    self.task_ulx + self.task_width / 2 - 20, self.task_uly + self.task_height)
        qp.drawLine(self.task_ulx + self.task_width / 2 + 20, self.task_uly,
                    self.task_ulx + self.task_width / 2 + 20, self.task_uly + self.task_height)

        for t, this_y in enumerate(self.breaks_list):

            # Axis digits
            if t % 4 == 0:
                qp.drawLine(self.task_ulx + self.task_width / 2 - self.axeWidth / 2, this_y, self.task_ulx
                            + self.task_width / 2 - 15, this_y)
                qp.drawLine(self.task_ulx + self.task_width / 2 + 15, this_y, self.task_ulx +
                            self.task_width / 2 + self.axeWidth / 2, this_y)
                self.digits[str(t)].show()
            else:

                qp.drawLine(self.task_ulx + self.task_width / 2 - self.axeWidth / 2,
                            this_y, self.task_ulx + self.task_width / 2 + self.axeWidth / 2, this_y)
                self.digits[str(t)].hide()

        # "min" label
        self.min_label.show()

        # Scheduler up/down limits
            # Red squares
        qp.setBrush(QtGui.QColor('#ff0000'))
        qp.setPen(self.red_pen)

        qp.drawRect(QtCore.QRect(self.tracking_ulx - 5, self.schedule_up - 10, 10, 10))
        qp.drawRect(QtCore.QRect(self.communication_ulx - 5, self.schedule_up - 10, 10, 10))
        qp.drawRect(QtCore.QRect(self.tracking_ulx - 5, self.schedule_down, 10, 10))
        qp.drawRect(QtCore.QRect(self.communication_ulx - 5, self.schedule_down, 10, 10))

        # Tracking label
        self.T_letter.show()

        # Communication label
        self.C_letter.show()

        # Red time lines
        remaining_time = abs(self.maxTime_sec - self.current_time_sec)
        limit_y = min([float(remaining_time) / (self.schedule_duration_mn * 60), 1])
        qp.drawLine(self.tracking_ulx, self.breaks_list[0], self.tracking_ulx, self.breaks_list[
                    0] + limit_y * (self.breaks_list[-1] - self.breaks_list[0]))
        qp.drawLine(self.tracking_ulx - 5, self.breaks_list[0] + limit_y * (self.breaks_list[-1] - self.breaks_list[
                    0]), self.tracking_ulx + 5, self.breaks_list[0] + limit_y * (self.breaks_list[-1] - self.breaks_list[0]))

        qp.drawLine(self.communication_ulx, self.breaks_list[0], self.communication_ulx, self.breaks_list[
                    0] + limit_y * (self.breaks_list[-1] - self.breaks_list[0]))
        qp.drawLine(self.communication_ulx - 5, self.breaks_list[0] + limit_y * (self.breaks_list[-1] - self.breaks_list[
                    0]), self.communication_ulx + 5, self.breaks_list[0] + limit_y * (self.breaks_list[-1] - self.breaks_list[0]))

        qp.setBrush(QtGui.QColor('#009900'))
        qp.setPen(self.green_pen)

        # Tracking
        for this_task in self.current.keys():
            for this_interval in self.current[this_task]:
                if this_interval[1] != 0:
                    uly_up = self.breaks_list[0] + this_interval[0]
                    uly_down = self.breaks_list[0] + this_interval[1]
                    this_x = self.tracking_ulx if this_task == 'track' else self.communication_ulx
                    this_rect = QtCore.QRect(this_x - 15, uly_up, 30, uly_down - uly_up)
                    qp.drawRect(this_rect)

        # Elapsed time
        self.time_label.show()
        self.time_string_label.show()
