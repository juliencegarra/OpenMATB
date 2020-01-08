from PySide2 import QtWidgets, QtCore, QtGui


class WLight(QtWidgets.QWidget):

    def __init__(self, parent, off, onColor, name, index):
        super(WLight, self).__init__(parent)

        ulx_list = [0.11, 0.56]
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
        if on:
            bg = self.onColor
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        else:
            bg = ""
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)

#        self.light.setBackgroundColor(0,bg)
        self.light.setStyleSheet(
            "QLabel { background-color: " + bg + "; color: black}")

    # def resizeEvent(self, e):
    #     self.light.setGeometry(0, 0, self.width(), self.height())
