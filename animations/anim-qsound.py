import math
import sys

from multiprocessing import Process

from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import QWidget, QApplication, QHBoxLayout, QPushButton


if __name__ == '__main__':

    #used to play audio

    #refresh rate
    rate = 20
    duration = 1000


    #build UI
    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(200,200,500,500)
    layout = QHBoxLayout()
    widget.setLayout(layout)
    button = QPushButton("test")
    layout.addWidget(button)

    # audio
    sound_file = "../Sounds/alarms/al1.wav"
    sound_file = "../Sounds/alarms/al6-low.wav"
    #sound_file = "../Sounds/alarms/al6-medium.wav"
    #sound_file = "../Sounds/alarms/al6-high.wav"
    sound = QSoundEffect()
    sound.setSource(QUrl.fromLocalFile(sound_file))
    sound.setLoopCount(QSoundEffect.Infinite)

    #animate label background and sound
    count = 0
    def update_anim():
        global count

        #logarithmic (check with perception of luminosity/brighness)
        #val = math.log(count + 1)
        #linear
        val = 1 - count
        #sinus
        #val = math.sin(count*2*math.pi) / 2 + 0.5
        #print(val)
        alpha = val *100 + 155
        button.setStyleSheet(f"background-color:rgba(200,100,100, {alpha})")

        amplitude = val * 0.8 + 0.2
        sound.setVolume(amplitude)

        count = count + rate / duration
        # print(count)
        if count >= 1 - rate / duration:
            count = 0


    timer = QTimer()
    timer.timeout.connect(update_anim)

    def start_animation():
        global count
        count = 0
        sound.play()
        timer.start(rate)

    def stop_animation():
        timer.stop()
        sound.stop()

    button.pressed.connect(start_animation)
    button.released.connect(stop_animation)

    widget.show()
    sys.exit(app.exec_())