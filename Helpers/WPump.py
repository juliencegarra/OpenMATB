from PySide2 import QtCore, QtWidgets, QtGui

tankdict = {'1': {'fromtank': 'c', 'totank': 'a' },
            '2': {'fromtank': 'e', 'totank': 'a' },
            '3': {'fromtank': 'd', 'totank': 'b' },
            '4': {'fromtank': 'f', 'totank': 'b' },
            '5': {'fromtank': 'e', 'totank': 'c' },
            '6': {'fromtank': 'f', 'totank': 'd' },
            '7': {'fromtank': 'a', 'totank': 'b' },
            '8': {'fromtank': 'b', 'totank': 'a' }}

class WPump(QtWidgets.QWidget):

    def __init__(self, parent, pumpNumber):
        '''Draw a tank, based on its upper left coordinates, and on its nature (target, source, limited or not) which define its size ratio'''
        super(WPump, self).__init__(parent)

        self.toTank_label = tankdict[pumpNumber]['totank']
        self.fromTank_label = tankdict[pumpNumber]['fromtank']

        self.pumpLabel = QtWidgets.QLabel(self)
        self.pumpLabel.setText("<b>%s</b>" % pumpNumber)

        self.pumpWidth = self.parent().height() / 16.

        self.connector = None
        self.changeState(0, 0)

    def locateAndSize(self):

        if self.fromTank_label == 'a' and self.toTank_label == 'b':
            halign = 0.45
        elif self.fromTank_label == 'b' and self.toTank_label == 'a':
            halign = 0.65
        else:
            halign = 0.5

        # Retrieve Tank object
        self.fromTank = self.parent().parameters['tank'][self.fromTank_label]
        self.toTank = self.parent().parameters['tank'][self.toTank_label]

        if self.fromTank['target'] is None and self.toTank['target'] is not None:
            self.connector = 'vertical'
            self.centerX = (
                self.fromTank['ui'].ulx + self.fromTank['ui'].tankWidth / 2)
            self.ulx = self.centerX - self.pumpWidth / 2

            interHeight = self.fromTank['ui'].uly - (
                self.toTank['ui'].uly + self.toTank['ui'].tankHeight)
            self.centerY = self.fromTank['ui'].uly - interHeight / 2
            self.uly = self.centerY - self.pumpWidth / 2

        elif self.fromTank['target'] is not None and self.toTank['target'] is not None:
            self.connector = 'horizontal'

            if self.fromTank['ui'].ulx - self.toTank['ui'].ulx > 0:  # fromTank is to the right
                interWidth = abs(self.toTank['ui'].ulx + self.toTank[
                                 'ui'].tankWidth - self.fromTank['ui'].ulx)
                self.centerX = self.toTank['ui'].ulx + self.toTank[
                    'ui'].tankWidth + interWidth / 2
                self.ulx = self.centerX - self.pumpWidth / 2

            else:
                interWidth = abs(self.fromTank['ui'].ulx + self.fromTank[
                                 'ui'].tankWidth - self.toTank['ui'].ulx)
                self.centerX = self.fromTank['ui'].ulx + self.fromTank[
                    'ui'].tankWidth + interWidth / 2
                self.ulx = self.centerX - self.pumpWidth / 2

            self.centerY = self.fromTank[
                'ui'].uly + self.fromTank['ui'].tankHeight * halign
            self.uly = self.centerY - self.pumpWidth / 2

        elif self.fromTank['target'] is None and self.toTank['target'] is None:
            self.connector = 'horizontal'

            interWidth = abs(self.toTank['ui'].ulx + self.toTank[
                             'ui'].tankWidth - self.fromTank['ui'].ulx)
            self.centerX = self.toTank['ui'].ulx + self.toTank[
                'ui'].tankWidth + interWidth / 2
            self.ulx = self.centerX - self.pumpWidth / 2

            interHeight = self.fromTank['ui'].uly - (
                self.toTank['ui'].uly + self.toTank['ui'].tankHeight)
            self.centerY = self.fromTank['ui'].uly - interHeight * halign
            self.uly = self.centerY - self.pumpWidth / 2

        self.pumpLabel.setGeometry(
            QtCore.QRect(self.ulx, self.uly, self.pumpWidth, self.pumpWidth))
        self.pumpLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.pumpLabel.setFont(
            QtGui.QFont("sans-serif", self.parent().height() / 42.))

    def refreshLevel(self, level):
        if self.limitedCapacity:
            self.tankLevel.setText("<b>%s</b>" % str(level))

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        if not self.hide:
            self.drawPump(qp)
        qp.end()

    def drawPump(self, qp):
        pen = QtGui.QPen(QtGui.QColor('#000000'), 2, QtCore.Qt.SolidLine)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)
        qp.setPen(pen)
        qp.setBrush(self.background)
        correct = 5

        if self.connector == 'vertical':

            qp.drawLine(self.centerX, self.fromTank['ui'].uly, self.centerX, self.toTank['ui'].uly + 0.75 * self.toTank['ui'].tankHeight)

            temp_x = self.toTank['ui'].ulx if self.toTank['ui'].ulx - (self.centerX + self.pumpWidth / 2) > 0 else self.toTank['ui'].ulx + self.toTank['ui'].tankWidth

            qp.drawLine(self.centerX, self.toTank['ui'].uly + 0.75 * self.toTank['ui'].tankHeight, temp_x, self.toTank['ui'].uly + 0.75 * self.toTank['ui'].tankHeight)

            triangleList = [QtCore.QPoint(self.ulx, self.uly + self.pumpWidth - correct), QtCore.QPoint(self.ulx + self.pumpWidth / 2, self.uly - correct), QtCore.QPoint(self.ulx + self.pumpWidth, self.uly + self.pumpWidth - correct)]

        elif self.connector == 'horizontal':

            if self.fromTank['ui'].ulx - self.toTank['ui'].ulx > 0:  # fromTank is to the right
                x_left, x_right = self.toTank['ui'].ulx + self.toTank['ui'].tankWidth, self.fromTank['ui'].ulx
                triangleList = [QtCore.QPoint(self.ulx - correct, self.uly + self.pumpWidth / 2), QtCore.QPoint(self.ulx + self.pumpWidth - correct, self.uly), QtCore.QPoint(self.ulx + self.pumpWidth - correct, self.uly + self.pumpWidth)]
            else:
                x_left, x_right = self.fromTank['ui'].ulx + self.fromTank['ui'].tankWidth, self.toTank['ui'].ulx
                triangleList = [QtCore.QPoint(self.ulx + correct, self.uly), QtCore.QPoint(self.ulx + correct, self.uly + self.pumpWidth), QtCore.QPoint(self.ulx + correct + self.pumpWidth, self.uly + self.pumpWidth / 2)]
            qp.drawLine(x_left, self.centerY, x_right, self.centerY)

        qp.drawPolygon(triangleList)

    def changeState(self, state, hide):
        self.hide = hide
        if state == -1:  # fail
            self.background = QtGui.QColor(self.parent().parameters['pumpcolorfailure'])
            self.textcolor = self.findBlackOrWhite(self.parent().parameters['pumpcolorfailure'])
            # self.pumpShape.setFrameShadow(QtGui.QFrame.Plain)
        elif state == 1:  # on
            self.background = QtGui.QColor(self.parent().parameters['pumpcoloron'])
            self.textcolor = self.findBlackOrWhite(self.parent().parameters['pumpcoloron'])
            # self.pumpShape.setFrameShadow(QtGui.QFrame.Sunken)
        elif state == 0:  # off
            self.background = QtGui.QColor(self.parent().parameters['pumpcoloroff'])
            self.textcolor = self.findBlackOrWhite(self.parent().parameters['pumpcoloroff'])
            # self.pumpShape.setFrameShadow(QtGui.QFrame.Raised)
        self.pumpLabel.setStyleSheet("QLabel { ; color: " + self.textcolor + "}")

    def findBlackOrWhite(self, my_hex):
        my_hex = my_hex.replace('#','')
        rgb = [int(a, 16) for a in [my_hex[0:2], my_hex[2:4], my_hex[4:6]]]
        mycolor = 'black' if (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) > 123 else 'white'

        return mycolor
