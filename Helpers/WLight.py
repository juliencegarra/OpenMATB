from PySide2 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl
from PyQt5.QtMultimedia import QSoundEffect
import math
count = 0
#sound_file = 'C:/Users/zmdgd/source/repos/OpenMATB-Audio/Sounds/alarms/al6-high.wav'
#sound = QSoundEffect()
#sound.setSource(QUrl.fromLocalFile(sound_file))

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
        #Fonction to realise "blink" function 
        def blink(self):
            global count #,sound
            val = 1 - count
            alpha = round(val *100) + 155
            #amplitude = val * 0.8 + 0.2
            a = str(alpha)
            print( a)
            self.light.setStyleSheet(
                    "QLabel { background-color: rgba(200,100,100,"+a+");color:yellow}")
            #sound.setVolume(amplitude)
            count = count + 20 / 500 #period a modifier
        
            if count >= 1 - 20 / 500:
                count = 0

        #Start function "refreshState"
        if on:
            bg = self.onColor
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
            timerb = QtCore.QTimer()
            #timerb.timeout.connect(test())
            timerb.timeout.connect(blink(self))
            timerb.start(20) #period a modifier
            #sound.play() #How to implement sound.stop() ?
        else:
            bg = ""
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
            self.light.setStyleSheet(
                "QLabel { background-color: " + bg + "; color: gray}")

#        self.light.setBackgroundColor(0,bg)


    # def resizeEvent(self, e):
    #     self.light.setGeometry(0, 0, self.width(), self.height())
