import math
import sys

from PySide2.QtCore import QUrl, QTimer, Qt
from PySide2.QtGui import QColor
from PySide2.QtMultimedia import QSoundEffect
from PySide2.QtWidgets import QPushButton, QApplication, QWidget, QHBoxLayout

BUTTON_STYLE = "border: 1px solid white; border-radius: 4px;"


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

        self.mode = "toggle"

        self.pressed.connect(self.start)
        self.released.connect(self.stop)

        self.is_accelerating = False
        self.update_style("")

    def setSound(self, sound_file):
        self.sound.setSource(QUrl.fromLocalFile(sound_file))
        #self.sound.setLoopCount(QSoundEffect.Infinite)

    def start(self):
        self.count = 0
        self.sound.play()
        self.timer.start(self.rate)

    def stop(self):
        self.timer.stop()
        self.sound.stop()
        self.update_style("")

    def set_color(self, col):
        self.color = col

    def update_color_with_alha(self, alpha):
        red = self.color.red()
        green = self.color.green()
        blue = self.color.blue()
        bg_style = f"background-color:rgba({red},{green},{blue}, {alpha});"
        self.update_style(bg_style)

    def update_style(self, bg):
        bg_style = "QPushButton {" + bg + BUTTON_STYLE + "}"
        self.setStyleSheet(bg_style)

    def update_anim(self):

        # logarithmic (check with perception of luminosity/brighness)
        # val = math.log(count + 1)
        # linear
        if self.mode == "sin":
            val = math.sin(self.count * 2 * math.pi) / 2 + 0.5
        elif self.mode == "lin":
            val = 1 - self.count
        elif self.mode == "toggle":
            val = 1
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

            if self.is_accelerating:
                self.duration = max(200, self.duration * 0.95)


if __name__ == '__main__':
    # build UI
    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(200, 200, 500, 500)
    layout = QHBoxLayout()
    widget.setLayout(layout)

    audio_visual_congruent_left = QAVButton("  AudioVisual Congruent Left  ")
    #audio_visual_congruent_left.setSound(sound_file="../Sounds/alarms/bip2-left-master.wav")
    audio_visual_congruent_left.setSound(sound_file="C:/Users/zmdgd/source/repos/OpenMATB/Sounds/alarms/bip2-left-master.wav")
    audio_visual_congruent_left.mode = "sin"
    audio_visual_congruent_left.set_color(QColor(Qt.darkYellow))

    visual = QAVButton("  Visual  ")
    visual.mode = "toggle"
    visual.set_color(QColor(Qt.darkYellow))
    visual.duration = 2000
    visual.is_accelerating = False

    audio_visual = QAVButton("  Audio-Visual  ")
    #audio_visual.setSound(sound_file="../Sounds/alarms/bip1-master.wav")
    audio_visual.setSound(sound_file="C:/Users/zmdgd/source/repos/OpenMATB/Sounds/alarms/bip1-master.wav")
    audio_visual.mode = "toggle"
    audio_visual.set_color(QColor(Qt.darkYellow))

    audio_visual_congruent_right = QAVButton("  AudioVisual Congruent Right  ")
    #audio_visual_congruent_right.setSound(sound_file="../Sounds/alarms/bip2-right-master.wav")
    audio_visual_congruent_right.setSound(sound_file="C:/Users/zmdgd/source/repos/OpenMATB/Sounds/alarms/bip2-right-master.wav")
    audio_visual_congruent_right.mode = "sin"
    audio_visual_congruent_right.set_color(QColor(Qt.darkYellow))

    layout.addWidget(audio_visual_congruent_left)
    layout.addWidget(visual)
    layout.addWidget(audio_visual)
    layout.addWidget(audio_visual_congruent_right)

    widget.show()
    sys.exit(app.exec_())
