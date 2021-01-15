import math
import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QHBoxLayout, QPushButton

import pygame

if __name__ == '__main__':

    #used to play audio
    pygame.init()
    pygame.mixer.init()

    #refresh rate
    rate = 20
    duration = 1000


    def set_panning(pan=0):
        '''input is between -1 left and 1 (right)'''
        # norm between 0 and 1
        x = pan / 2 + 0.5
        global right_amp, left_amp
        right_amp = math.sin(x * math.pi / 2)
        left_amp = math.sin((1 - x) * math.pi / 2)
        global channel
        #print(left_amp, right_amp)
        channel.set_volume(left_amp, right_amp)

    #audio
    channel = None
    sound_file = "C:/Users/zmdgd/source/repos/OpenMATB/Sounds/alarms/al1.wav"
    sound = pygame.mixer.Sound(os.path.abspath(sound_file))

    #build UI
    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(200,200,500,500)
    layout = QHBoxLayout()
    widget.setLayout(layout)
    button = QPushButton("test")
    layout.addWidget(button)


    #animate label background and sound
    count = 0
    def update_anim():
        global count
        global channel, sound

        #logarithmic (check with perception of luminosity/brighness)
        #log = 1 - math.log(count + 1)
        #linear
        log = 1 - count
        #sinus
        #log = (1+ math.sin(count*2*math.pi)) /2
        #print(log)

        #visual mapping
        value = log * 100 + 155
        button.setStyleSheet(f"background-color:rgba(200,20,20, {value})")

        #audio mapping
        amplitude = log
        # print('amplitude', amplitude)
        sound.set_volume(amplitude)


        count = count + rate / duration
        #print(count)
        if count >= 1-rate/duration:
            count = 0




    timer = QTimer()
    timer.timeout.connect(update_anim)
    #timer.start(rate)

    def start_animation():
        global count
        count = 0
        global channel
        channel = pygame.mixer.find_channel()
        set_panning(1)
        channel.play(sound, -1)
        timer.start(rate)

    def stop_animation():
        timer.stop()
        channel.stop()

    button.pressed.connect(start_animation)
    button.released.connect(stop_animation)

    widget.show()
    sys.exit(app.exec_())