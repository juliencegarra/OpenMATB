from PySide2 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl
from PyQt5.QtMultimedia import QSoundEffect
import pyglet,math,time


count = 0

sound_file = 'C:/Users/zmdgd/source/repos/OpenMATB/Sounds/alarms/al6-high.wav'
sound_file = QUrl.fromLocalFile("Sounds/alarms/al6-high.wav").path()
pyglet.options['audio'] = ('openal', 'pulse', 'directsound', 'silent')
source = pyglet.media.StaticSource(pyglet.media.load(sound_file))

player = pyglet.media.Player()
player.queue(source)
player.loop = True
#player.EOS_LOOP = 'loop'

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
        self.id = index
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
            duration = 500
            val = 1 - count
            alpha = round(val *155) + 100
            player.volume = val * 0.8 + 0.2
            a = str(alpha)
            self.light.setStyleSheet(
                    "QLabel { background-color: rgba(255,80,80,"+a+");color:yellow}")
            count = count + 20 / duration 
        
            if count > 1 - 20 / duration:
                count = 0

        #Start function "refreshState"
        if self.id == 0 :
            if on:
                self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
                timerb = QtCore.QTimer()
                timerb.timeout.connect(blink(self))
                timerb.start(1) 
                QtCore.QTimer.singleShot(5000,  player.pause)
                player.play()
#                keyboard.add_hotkey('f1', player.pause())
            else:
                bg = ""
                self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
                self.light.setStyleSheet(
                    "QLabel { background-color: " + bg + "; color: gray}")
        else:
            if self.id == 1 :
                if on:
                    bg = "#FF0000"
                    self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
                
                else:
                    bg = ""
                    self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
            
                self.light.setStyleSheet("QLabel { background-color: " + bg + "; color: gray}")
            #else:
                #Alarm Non-congruent


#        self.light.setBackgroundColor(0,bg)


    # def resizeEvent(self, e):
    #     self.light.setGeometry(0, 0, self.width(), self.height())