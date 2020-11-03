#test_sound.py

sound_file = 'C:/Users/zmdgd/source/repos/OpenMATB-Audio/Sounds/alarms/al6-high.wav'
count = 0




import pyglet
import time
from PySide2 import QtCore





pyglet.options['audio'] = ('openal', 'pulse', 'directsound', 'silent')
source = pyglet.media.StaticSource(pyglet.media.load(sound_file))

player = pyglet.media.Player()
player.queue(source)
player.EOS_LOOP = 'loop'
# Or:
#plauer.loop = True
player.play()

while 1:    
    duration = 500
    val = 1 - count
    player.volume = val * 0.8 + 0.2
    count = count + 20 / duration 
        
    if count > 1 - 20 / duration:
        count = 0


