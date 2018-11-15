# -*- coding: utf-8 -*-
#!/usr/bin/env python
from PySide import QtCore, QtGui
import socket
import platform
import random

# Ignoré dans le git

try:
    import pygame

    from pygaze import settings
    settings.DISPTYPE = 'pygame'
    settings.DUMMYMODE = False

    from pygaze import libscreen
    from pygaze import libtime
    from pygaze import liblog
    from pygaze import libinput
    from pygaze import eyetracker
except:
    pass

# important :
# doit specifier l'eyetracker et la taille de l'ecran dans le scenario

# DUMMYMODE = True # False for gaze contingent display, True for dummy mode (using mouse or joystick)
# LOGFILENAME = 'default' # logfilename, without path
# LOGFILE = LOGFILENAME[:] # .txt; adding path before logfilename is optional; logs responses (NOT eye movements, these are stored in an EDF file!)
# TRIALS = 5


class PyGameImageWidget(QtGui.QWidget):

    def __init__(self, parent=None):
        super(PyGameImageWidget, self).__init__(parent)
        surface = pygame.display.get_surface()
        self.w = surface.get_width()
        self.h = surface.get_height()
        self.data = surface.get_buffer().raw
        self.image = QtGui.QImage(
            self.data, self.w, self.h, QtGui.QImage.Format_RGB32)

# def getData(self):
# surface = pygame.display.get_surface()
# return surface.get_buffer().raw

    def paintEvent(self, event):
        data = pygame.display.get_surface().get_buffer().raw
        self.image = QtGui.QImage(
            self.data, self.w, self.h, QtGui.QImage.Format_RGB32)
        print "update"

        qp = QtGui.QPainter()
        qp.begin(self)
        # self.image.fromData(data)
        qp.drawImage(0, 0, self.image)
        qp.end()


class Task(QtGui.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.taskUpdateTime = None

        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': None,
            'trackertype': None,
            'saccadevelocitythreshold': 35,
            'saccadeaccelerationthreshold': 9500,
            'smiip': "127.0.0.1",
            'smisendport': 4444,
            'smireceiveport': 5555,

            'calibrationinstruction':
                "When you see a cross, look at it and press space. Then make an eye movement to the black circle when it appears.\n\n(press space to start)",

            'screensize': None,
            'mousevisible': True,
            'backgroundcolor': (125, 125, 125, 255),
            'foregroundcolor': (0, 0, 0, 255)


        }
        self.wait_key = False

    def onStart(self):
        # TODO : to remove!
        self.parameters['trackertype'] = 'smi'
        self.parameters['smiip'] = "192.168.1.35"
        self.parameters['screensize'] = (33.8, 27.1)

        self.parent().onPause()

        if self.parameters['trackertype'] is None:
            self.parent().showCriticalMessage(
                "You should define the eye tracker type in the scenario")
            self.parent().onResume()
            return

        if self.parameters['screensize'] is None:
            self.parent().showCriticalMessage(
                "You should define the screen size in the scenario")
            self.parent().onResume()
            return

        screenResolution = (
            self.parent().screen_width, self.parent().screen_height)

        # Prepare the surface for pygame

        # start timing
        libtime.expstart()

        # TODO : gerer le screenr (nombre d'ecran)

        print screenResolution

        # create display object
        try:
            self.disp = libscreen.Display(screenr=0, disptype='pygame',
                                          dispsize=screenResolution,
                                          screensize=self.parameters[
                                              'screensize'],
                                          mousevisible=self.parameters[
                                          'mousevisible'],
                                          bgc=self.parameters[
                                              'backgroundcolor'],
                                          fgc=self.parameters['foregroundcolor'])
        except Exception as e:
            self.parent().showCriticalMessage(e.message)
            self.parent().onResume()
            return

        # create eyetracker object
        try:
            self.tracker = eyetracker.EyeTracker(self.disp,
                                                 trackertype=self.parameters[
                                                 'trackertype'],
                                                 saccade_velocity_threshold=self.parameters[
                                                 'saccadevelocitythreshold'],
                                                 saccade_acceleration_threshold=self.parameters[
                                                 'saccadeaccelerationthreshold'],
                                                 ip=self.parameters['smiip'],
                                                 sendport=int(
                                                 self.parameters[
                                                     'smisendport']),
                                                 receiveport=int(self.parameters['smireceiveport']))
        except Exception as e:
            print "ici"
            self.parent().showCriticalMessage(e.message)
            self.parent().onResume()
            return

        # create keyboard object
        self.keyboard = libinput.Keyboard(keylist=['space'], timeout=None)

        # create logfile object
        self.log = liblog.Logfile()
        self.log.write(
            ["trialnr", "trialtype", "endpos", "latency", "correct"])

        # create screens
        self.inscreen = libscreen.Screen(disptype='pygame')
        self.inscreen.draw_text(
            text=self.parameters['calibrationinstruction'], fontsize=24)

        # show instructions
        self.disp.fill(self.inscreen)
        self.disp.show()

        try:
            self.tracker.calibrate()
        except Exception as e:
            print "ici calibrate"
            self.parent().showCriticalMessage(e.message)
            self.parent().onResume()
            return

        # pygame.display.iconify()
        # self.parent().setCentralWidget(PyGameImageWidget())

        print "fin eye tracking"
        self.parent().onResume()


#
#
# def keyEvent(self, e):
# print "icib"
# if self.wait_key:
# self.tracker.start_recording()
# self.onEnd()
# self.tracker.calibrate()
#
# self.inscreen.draw_fixation(fixtype='cross',pw=3)
# pygame.display.flip()
# self.disp.fill(self.inscreen)
#
# self.parent().setCentralWidget(PyGameImageWidget())
# self.wait_key = False
# print "icic"
# tracker.status_msg("trial %d" % trialnr)
# tracker.log("start_trial %d trialtype %s" % (trialnr, trialtype))
#

    def onEnd(self):
        # end the experiment
        try:
            self.tracker.stop_recording()
            self.log.close()
            self.tracker.close()
            self.disp.close()
            self.libtime.expend()
        except:
            pass
