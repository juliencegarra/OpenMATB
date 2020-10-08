import math
import sys

from PyQt5.QtCore import QUrl, QTimer, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import QPushButton, QApplication, QWidget, QHBoxLayout


class QAVButton(QPushButton):
    def __init__(self, label):
        """ builds a custom button and displays it"""
        # calls super constuctor
        super(QAVButton, self).__init__(label)
        self.sound = QSoundEffect()
        self.volume = 1.
        self.color = QColor(Qt.gray)

        self.count = 0
        self.duration = 1000
        self.rate = 20

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_anim)

        self.mode = "sin"

        self.pressed.connect(self.start)
        self.released.connect(self.stop)

    def setSound(self, sound_file):
        self.sound.setSource(QUrl.fromLocalFile(sound_file))
        self.sound.setLoopCount(QSoundEffect.Infinite)

    def start(self):
        self.count = 0
        self.sound.play()
        self.timer.start(self.rate)

    def stop(self):
        self.timer.stop()
        self.sound.stop()

    def update_anim(self):

        #logarithmic (check with perception of luminosity/brighness)
        #val = math.log(count + 1)
        #linear
        if self.mode == "sin":
            val = math.sin(self.count* 2 * math.pi) / 2 + 0.5
        elif self.mode == "lin" :
            val = 1 - self.count
        else :
            val = math.log(self.count + 1)

        alpha = val *100 + 155
        red = self.color.red()
        green = self.color.green()
        blue = self.color.blue()
        self.setStyleSheet(f"background-color:rgba({red},{green},{blue}, {alpha})")

        amplitude = val * 0.8 + 0.2
        self.sound.setVolume(amplitude)

        self.count = self.count + self.rate / self.duration
        # print(count)
        if self.count >= 1 - self.rate / self.duration:
            self.count = 0


if __name__ == '__main__':
    #build UI
    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(200,200,500,500)
    layout = QHBoxLayout()
    widget.setLayout(layout)

    relax = QAVButton("relax")
    relax.setSound(sound_file = "../Sounds/alarms/al6-low.wav")
    relax.mode = "sin"
    relax.color = QColor(Qt.blue)
    relax.duration = 2000
    warning = QAVButton("warning")
    warning.setSound(sound_file = "../Sounds/alarms/al6-medium.wav")
    warning.mode = "sin"
    warning.color = QColor(Qt.darkYellow)
    emergency = QAVButton("emergency")
    emergency.setSound(sound_file = "../Sounds/alarms/al6-high.wav")
    emergency.duration = 500
    emergency.mode = "lin"
    emergency.color = QColor(Qt.red)

    layout.addWidget(relax)
    layout.addWidget(warning)
    layout.addWidget(emergency)

    widget.show()
    sys.exit(app.exec_())