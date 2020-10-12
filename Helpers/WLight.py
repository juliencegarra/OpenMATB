from PySide2 import QtWidgets, QtCore, QtGui


class WLight(QtWidgets.QWidget):

    def __init__(self, parent, off, onColor, name, index):
        super(WLight, self).__init__(parent)

        ulx_list = [0.11, 0.56, 1.01]
        ulx = ulx_list[index]

        width_proportion = 1 / 3.
        wh_ratio = 3  # width = 2 * height
        
        

        self.lightWidth = width_proportion * self.parent().width()
        self.lightHeight = self.lightWidth / wh_ratio

        font = QtGui.QFont(
            "sans-serif", self.lightWidth / 13., QtGui.QFont.Bold)
        self.light = QtWidgets.QLabel(self)
        self.light.setLineWidth(self.lightWidth / 37.)
        self.off = off
        self.light.setText("<b>%s</b>" % name)
        self.light.setFont(font)
        self.onColor = onColor
        self.ulx = ulx * self.parent().width()
        self.uly = 0.05 * self.parent().height()
        #~ self.feedback = 0  # Useless yet

        self.light.setGeometry(
            self.ulx, self.uly, self.lightWidth, self.lightHeight)
        self.light.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)


    def refreshState(self, on):
        count = 0
        def blink():
            global count
            val = 1 - count
            alpha = val *100 + 155
            self.light.setStyleSheet(
                    "QLabel { background-color: rgba(200,100,100, {alpha});color:yellow}")
            count = count + 20 / 1000
        
            if count >= 1 - 20 / 1000:
                count = 0
        if on:
            bg = self.onColor
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
            timerb = QtCore.QTimer()
            timerb.timeout.connect(blink)
            timerb.start(20)
        else:
            bg = ""
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
            self.light.setStyleSheet(
                "QLabel { background-color: " + bg + "; color: gray}")

#        self.light.setBackgroundColor(0,bg)


    # def resizeEvent(self, e):
    #     self.light.setGeometry(0, 0, self.width(), self.height())
