import math
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QHBoxLayout, QPushButton

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(200,200,500,500)
    layout = QHBoxLayout()
    widget.setLayout(layout)

    label = QPushButton("test")
    layout.addWidget(label)

    #refresh rate
    rate = 50
    duration = 1000


    count = 0
    def update_anim():
        global count
        #logarithmic (check with perception of luminosity/brighness)
        #log = math.log(count + 1)
        #linear
        #log = count
        #sinus
        log = math.sin(count*2*math.pi)
        value = log *100 + 155
        label.setStyleSheet(f"background-color:rgba(200,20,20, {value})")
        count = count + rate / duration
        count = count % 1


    timer = QTimer()
    timer.timeout.connect(update_anim)
    #timer.start(rate)


    label.pressed.connect(lambda : timer.start(rate))
    label.released.connect(timer.stop)

    widget.show()
    sys.exit(app.exec_())