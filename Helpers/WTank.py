from PySide import QtCore, QtGui


class WTank(QtGui.QWidget):

    def __init__(self, parent):
        '''Draw a tank, based on its upper left coordinates, and on its nature (target, source, limited or not) which define its size ratio'''
        super(WTank, self).__init__(parent)

        self.tank = QtGui.QProgressBar(self)
        self.tank.setOrientation(QtCore.Qt.Vertical)
        self.tank.setTextVisible(False)
        self.tolerance = self.parent().parameters['tolerancelevel']  # below or above the target level
        self.toleranceColor = QtGui.QColor(230, 247, 255)
        self.letterFont = QtGui.QFont(
            "sans-serif", int(self.parent().height() / 30.), QtGui.QFont.Bold)

        # Define style
        style = """
            QProgressBar::chunk {
                background-color: green;
            }
        """
        self.setStyleSheet(style)
        
        
            
    
    

    def setLabel(self, level=0):
        self.tankLevel = QtGui.QLabel(self)
        self.tankLevel.setGeometry(
            QtCore.QRect(self.ulx, self.uly + self.tankHeight, self.tankWidth, 20))
        self.tankLevel.setAlignment(QtCore.Qt.AlignCenter)

    def setLetter(self, letter):
        self.tankLetter = QtGui.QLabel(self)
        self.tankLetter.setFont(self.letterFont)
        self.tankLetter.setText(letter)
        self.tankLetter.setGeometry(
            QtCore.QRect(self.ulx - 30, self.uly, 30, 30))
        self.tankLetter.setAlignment(
            QtCore.Qt.AlignCenter | QtCore.Qt.AlignCenter)

    def setMaxLevel(self, level):
        self.tank.setRange(0, level)

    def refreshLevel(self, level):
        self.tank.setValue(level)
        try:  # Tank does not necessary have a level label
            self.tankLevel.setFont(self.letterFont)
            self.tankLevel.setText("<b>%s</b>" % str(level))
        except:
            pass

    def locateAndSize(self, tankletter, target, limited):
        self.tanklet = tankletter

        ulxy = {'a': {'ulx': 0.17, 'uly': 0.05},
                'b': {'ulx': 0.66, 'uly': 0.05},
                'c': {'ulx': 0.10, 'uly': 0.52},
                'd': {'ulx': 0.59, 'uly': 0.52},
                'e': {'ulx': 0.33, 'uly': 0.52},
                'f': {'ulx': 0.81, 'uly': 0.52}}

        # Define real x,y coordinates, based on real width/height
        ulx = ulxy[tankletter]['ulx']
        uly = ulxy[tankletter]['uly']

        self.ulx, self.uly = ulx * \
            self.parent().width(), uly * self.parent().height()
        self.target = target

        # Define the tank nature, which will determine its width, and its
        # width/height ratio
        if self.target is not None:  # if tank a target (A or B)
            tankWidth_proportion = 0.18  # relative to total layout width
            wh_ratio = 1
        else:  # not a target
            if limited:  # source is limited
                tankWidth_proportion = 0.1
                wh_ratio = 1 / 1.9  # width = 1/1.9 * height
            else:
                tankWidth_proportion = 0.15
                wh_ratio = 1.5 / 1.9  # width = 1.5/1.9 * height

        self.tankWidth = tankWidth_proportion * self.parent().width()
        self.tankHeight = self.tankWidth / wh_ratio

        self.tank.setGeometry(
            self.ulx, self.uly, self.tankWidth, self.tankHeight)

    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawLines(qp)
        qp.end()

    def setTargetY(self, targetLevel, levelMax):
        self.targetY = self.uly + (1 - targetLevel / float(levelMax)) * self.tankHeight
        self.levelMax = levelMax

    def drawLines(self, qp):
        lineLength = int(self.parent().height() / 35.)
        pen = QtGui.QPen(QtGui.QColor('#000000'), 2, QtCore.Qt.SolidLine)
        if self.target and self.parent().parameters['displaytolerance']:
            qp.setBrush(self.toleranceColor)
            qp.setPen(None)
            qp.drawRect(self.ulx - lineLength, self.targetY - (float(self.tolerance) / self.levelMax)
                        * self.tankHeight, lineLength + 2, (float(self.tolerance) / self.levelMax) * self.tankHeight * 2)
            qp.drawRect(self.ulx + self.tankWidth - 3, self.targetY - (float(self.tolerance) / self.levelMax) * self.tankHeight, lineLength + 2, (float(self.tolerance) / self.levelMax) * self.tankHeight * 2)

            qp.setPen(pen)
            qp.drawLine(self.ulx - lineLength + 2,
                        self.targetY, self.ulx, self.targetY)
            qp.drawLine(self.ulx + self.tankWidth - 2, self.targetY,
                        self.ulx + self.tankWidth + lineLength - 2, self.targetY)
