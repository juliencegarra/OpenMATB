from PySide2 import QtCore, QtWidgets, QtGui
from math import sin, pi
import random
import numpy


class WTrack (QtWidgets.QWidget):

    """ Tracking widget """

    def __init__(self, parent, equalproportions):
        super(WTrack, self).__init__(parent)

        # Define task area (width, height)
        self.targetArea = None
        self.equalproportions = equalproportions
        self.occupiedSpace = 0.9

        if not self.equalproportions:
            self.task_width = self.occupiedSpace * self.parent().width()
            self.task_height = self.occupiedSpace * self.parent().height()
        else:
            self.task_width = self.task_height = min(self.parent().width(), self.parent().height())*self.occupiedSpace

        # Define various sizes (lines, cursor, reticulum, ticks)
        self.penSize = self.task_height / 150.
        self.cursor_diam = 0.1  # 10%
        self.cursor_widthPx = self.cursor_heightPx = self.task_height * \
            self.cursor_diam + self.penSize * 2
        self.reticulum_length = self.cursor_diam / 5.
        self.reticulum_lengthPx = self.reticulum_length * self.task_height
        self.tickLength = 0.1 * self.task_height
        self.target_radius = self.parent().parameters['targetradius']

        # Create Qt objects
        self.pen_cursor = QtGui.QPen(QtGui.QColor(self.parent().parameters['cursorcolor']), self.penSize * 2, QtCore.Qt.SolidLine)
        self.pen_cursor_outside = QtGui.QPen(QtGui.QColor(self.parent().parameters['cursorcoloroutside']), self.penSize * 2, QtCore.Qt.SolidLine)
        self.letterFont = QtGui.QFont("sans-serif", self.task_height / 30., QtGui.QFont.Bold)
        self.plainPen = QtGui.QPen(QtGui.QColor('#0000FF'), self.penSize, QtCore.Qt.SolidLine)
        self.dashedPen = QtGui.QPen(QtGui.QColor('#0000FF'), self.penSize, QtCore.Qt.DashDotLine)

        # Movements parameters
        self.howManySinusoide = 3
        self.cutoffFrequency = self.parent().parameters['cutofffrequency']
        self.cursorSpeedFactor = 0.5 # At which speed should the sinusoides values be browsed ?

        # Range of movements amplitude around the center. e.g., [0,0] = fixed target, [0,1] = wide range, [1,1] = maximum amplitude
        self.amplitudeRange = [0.2, 0.6]

        self.phase = {'x': self.linspace(0, 2 * pi, self.howManySinusoide), 'y': self.linspace(
            pi / 5, pi / 5 + 2 * pi, self.howManySinusoide)}

        self.amplitude = {'x': self.linspace(max(self.amplitudeRange), min(self.amplitudeRange), self.howManySinusoide), 'y': self.linspace(
            max(self.amplitudeRange), min(self.amplitudeRange), self.howManySinusoide)}

        self.frequencies = {'x': self.linspace(0.01, self.cutoffFrequency, self.howManySinusoide), 'y': self.linspace(
            self.cutoffFrequency, 0.02, self.howManySinusoide)}

        self.cursorPos = {'x': 0, 'y': 0}
        self.previousPos = {'x': 0, 'y': 0}

        self.auto_radius = self.target_radius + 0.05
        self.compensationForce = 0.5  # Amplitude of the automated compensatory movement

        random.seed(None)
        self.refreshCursorPosition(self.cursorPos['x'], self.cursorPos['y'])

    def linspace(self, lower, upper, length):
        return [lower + x*(upper-lower)/(length-1) for x in range(length)]

    def returnAbsoluteDeviation(self):
        this_x, this_y = self.getXY()
        return numpy.sqrt(this_x**2 + this_y**2)

    def getXY(self):
        return self.cursorPos['x'], self.cursorPos['y']

    def isCursorInTarget(self):
        return self.isRelativePosInTarget(self.cursorPos['x'], self.cursorPos['y'])

    def isRelativePosInTarget(self, x, y):
        if not self.targetArea:
            return False

        xpos, ypos = self.getPositionFromRelative(x, y)

        return self.targetArea.contains(xpos, ypos)

    def moveCursor(self):
        current_time_ms = int(self.parent().parent().totalElapsedTime_ms)

        # Avoid absolute positioning (t-1 -> t)
        for thisCoord in ['x', 'y']:
            currentSinus = []
            for thisPhase in range(0, self.howManySinusoide):
                phase_value = (2 * pi * self.frequencies[thisCoord][thisPhase] * (
                    (current_time_ms * self.cursorSpeedFactor)/ 1000.) + self.phase[thisCoord][thisPhase]) % 2 * pi
                currentSinus.append(sin(phase_value))

            currentPos = numpy.mean([self.amplitude[thisCoord][thisPhase] * currentSinus[thisPhase]
                                 for thisPhase in range(0, self.howManySinusoide)])

            translation = currentPos - self.previousPos[thisCoord]
            self.cursorPos[thisCoord] += translation
            self.previousPos[thisCoord] = currentPos

        return self.cursorPos["x"], self.cursorPos["y"]

    def getAutoCompensation(self):
        auto_x, auto_y = 0, 0
        current_force = self.parent().parameters['taskupdatetime'] * (float(self.compensationForce)/1000)
        if abs(self.cursorPos['x']) > 0.02:
            auto_x = numpy.sign(-self.cursorPos['x']) * current_force
        if abs(self.cursorPos['y']) > 0.02:
            auto_y = numpy.sign(-self.cursorPos['y']) * current_force
        return auto_x, auto_y

    def refreshCursorPosition(self, x, y):
        # Cursor should not leave the widget area
        self.cursorPos['x'] = max(min(x, 0.99), -0.99)
        self.cursorPos['y'] = max(min(y, 0.99), -0.99)
        self.update()

    def getPositionFromRelative(self, x, y):
        posX = (0.5 + x / 2) * self.task_width - self.penSize / 2
        posY = (0.5 + y / 2) * self.task_height - self.penSize / 2
        return posX, posY

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def drawWidget(self, qp):
        # Define the pen to use

        qp.setPen(self.plainPen)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)

        # Centering
        qp.translate(abs(self.parent().width() - self.task_width) / 2, (self.parent().height() - self.task_height) / 3)

        # Draw the tracking environment (crosses)

        # X axis
        qp.drawLine(0, self.task_height / 2,
                    self.task_width, self.task_height / 2)

        # Y axis
        qp.drawLine(self.task_width / 2, 0,
                    self.task_width / 2, self.task_height)

        # X and Y tickz
        howManyTicks = 7
        coordinates_prop = self.linspace(0, 1, howManyTicks + 2)

        for t, thisTick in enumerate(coordinates_prop):
            tickLength = self.tickLength if t % 2 == 0 else self.tickLength / 2

            # X tikz
            qp.drawLine(
                thisTick * self.task_width, self.task_height /
                    2 - tickLength / 2,
                        thisTick * self.task_width, self.task_height / 2 + tickLength / 2)

            # Y tikz
            qp.drawLine(
                self.task_width / 2 - tickLength /
                    2, thisTick * self.task_height,
                        self.task_width / 2 + tickLength / 2, thisTick * self.task_height)

        # Frame for the track zone (4 corners)
        qp.drawLine(0, 0, self.tickLength, 0)
        qp.drawLine(0, 0, 0, self.tickLength)
        qp.drawLine(self.task_width, 0, self.task_width - self.tickLength, 0)
        qp.drawLine(self.task_width, 0, self.task_width, self.tickLength)
        qp.drawLine(0, self.task_height, self.tickLength, self.task_height)
        qp.drawLine(0, self.task_height, 0, self.task_height - self.tickLength)
        qp.drawLine(self.task_width, self.task_height,
                    self.task_width, self.task_height - self.tickLength)
        qp.drawLine(self.task_width, self.task_height,
                    self.task_width - self.tickLength, self.task_height)

        # Target zone
        # Create a target area to test cursor position
        if self.target_radius > 0:
            self.targetArea = QtCore.QRect(self.task_width / 2 - (self.target_radius / 2) * self.task_width, self.task_height / 2 - (
                self.target_radius / 2) * self.task_height, self.target_radius * self.task_width, self.target_radius * self.task_height)

            # Draw target border
            qp.setPen(self.dashedPen)
            qp.drawRect(self.targetArea)
        else:
            self.targetArea = None

        # Draw cursor in pixels positions
        if self.isRelativePosInTarget(self.cursorPos['x'], self.cursorPos['y']):
            qp.setPen(self.pen_cursor)
        else:
            qp.setPen(self.pen_cursor_outside)

        posX, posY = self.getPositionFromRelative(
            self.cursorPos['x'], self.cursorPos['y'])

        # ellipses
        # inner
        qp.drawEllipse(posX - self.penSize / 2, posY -
                       self.penSize / 2, self.penSize, self.penSize)

        # outer
        qp.drawEllipse(posX - (self.cursor_widthPx / 2), posY - (
            self.cursor_heightPx / 2), self.cursor_widthPx, self.cursor_heightPx)

        # Reticulum (4 lines)
        qp.drawLine(posX + (self.cursor_widthPx / 2 - self.reticulum_lengthPx), posY, posX +
                    (self.cursor_widthPx / 2 - self.reticulum_lengthPx) + self.reticulum_lengthPx, posY)

        qp.drawLine(
            posX, posY +
                (self.cursor_heightPx / 2 - self.reticulum_lengthPx), posX,
                    posY + (self.cursor_heightPx / 2 - self.reticulum_lengthPx) + self.reticulum_lengthPx)

        qp.drawLine(posX - (self.cursor_widthPx / 2 - self.reticulum_lengthPx), posY, posX -
                    (self.cursor_widthPx / 2 - self.reticulum_lengthPx) - self.reticulum_lengthPx, posY)

        qp.drawLine(
            posX, posY -
                (self.cursor_heightPx / 2 - self.reticulum_lengthPx), posX,
                    posY - (self.cursor_heightPx / 2 - self.reticulum_lengthPx) - self.reticulum_lengthPx)
