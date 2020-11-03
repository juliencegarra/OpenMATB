import math

from PySide2.QtCore import QUrl
from PySide2.QtMultimedia import QSoundEffect, QAudioDeviceInfo
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import QTimer
from PySide2.QtGui import QColor


class WLight(QtWidgets.QWidget):

    def __init__(self, parent, off, onColor, name, index, sound_file):
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
        # ~ self.feedback = 0  # Useless yet

        self.light.setGeometry(
            self.ulx, self.uly, self.lightWidth, self.lightHeight)
        self.light.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)

        # audio part
        self.sound_file = sound_file
        self.color = QColor(self.onColor)
        self.count = 0
        self.duration = 1000
        self.rate = 20
        self.sound = QSoundEffect()
        self.setSound(self.sound_file)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_anim)
        self.mode = "sin"

        #print('devices',QAudioDeviceInfo.availableDevices())


    def setSound(self, sound_file):
        self.sound.setSource(QUrl.fromLocalFile(sound_file))
        self.sound.setLoopCount(QSoundEffect.Infinite)

    def start(self):
        #print('starting sound?', self.sound.status())
        if not self.sound.isPlaying():
            self.count = 0
            self.sound.play()
            self.timer.start(self.rate)

    def stop(self):
        self.timer.stop()
        self.sound.stop()

    def update_color_with_alha(self, alpha):
        red = self.color.red()
        green = self.color.green()
        blue = self.color.blue()
        bg_style = f"rgba({red},{green},{blue}, {alpha})"
        self.light.setStyleSheet(
            "QLabel { background-color: " + bg_style + "; color: black}")

    def update_anim(self):

        # logarithmic (check with perception of luminosity/brighness)
        # val = math.log(count + 1)
        # linear
        if self.mode == "sin":
            val = math.sin(self.count * 2 * math.pi) / 2 + 0.5
        elif self.mode == "lin":
            val = 1 - self.count
        else:
            val = math.log(self.count + 1)

        alpha = round(val * 100) + 155
        self.update_color_with_alha(alpha)

        amplitude = val * 0.8 + 0.2
        self.sound.setVolume(amplitude)

        self.count = self.count + self.rate / self.duration
        # print(count)
        if self.count >= 1 - self.rate / self.duration:
            self.count = 0


    def refreshState(self, on):
        if on:
            bg = self.onColor
            self.start()
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        else:
            bg = ""
            self.light.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
            self.stop()
            self.light.setStyleSheet(
             "QLabel { background-color: " + bg + "; color: black}")
