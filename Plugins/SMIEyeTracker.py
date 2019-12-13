# -*- coding: utf-8 -*-
from PySide2 import QtCore, QtWidgets
from Helpers import Logger
import socket
import datetime
import ctypes
from Helpers.Translator import translate as _

try:
    from iViewXAPI import *  # iViewX library
except:
    pass


def HandleError(ret):
    if ret == 100:
        return "IViewX error !"
    elif ret == 104:
        return "Could not establish connection. Check if Eye Tracker is running."
    elif ret == 105:
        return "Could not establish connection. Check the communication Ports."
    elif ret == 123:
        return "Could not establish connection. Another Process is blocking the communication Ports."
    elif ret == 201:
        return "Could not establish connection. Check if Eye Tracker is installed and running."
    else:
        return "Return Code is " + str(ret) + ". Refer to the iView X SDK Manual for its meaning."


class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.samples_to_test = []
        self.test_window = 10  # second
        self.sample_threshold = 0.50  # proportion of bad samples allowed

        self.parameters = {
            'taskplacement': 'fullscreen',
            'paintGaze': False,
            'trackertype': None,
            'smiip': "192.168.1.35",
            'smisendport': 4444,
            'smireceiveport': 5555,
            'connectmaxtries': 10,
            'maxcalibrations':  5,
            'mousevisible': True,
            'backgroundcolor': (125, 125, 125, 255),
            'foregroundcolor': (0, 0, 0, 255),
            'getFromSample': ['gazeLX', 'gazeLY', 'positionLX', 'positionLY', 'positionLZ',
                              'diamL', 'gazeRX', 'gazeRY', 'positionRX', 'positionRY', 'positionRZ', 'diamR']
        }

    def onStart(self):
        if not iViewXAPI:
            self.parent().showCriticalMessage(
                _("Unable to load the eyetracker library!"))
            return

        self.parent().onPause()

        try:
            self.adress_iviewx = socket.gethostbyname(self.parameters['smiip'])
            print(self.adress_iviewx)
        except (socket.error, EOFError):
            self.parent().showCriticalMessage(
                _("Unable to find the eyetracker computer in the network!"))
            self.parent().onResume()
            return

        try:
            adress_local = socket.gethostbyname(socket.gethostname())
        except (socket.error, EOFError):
            self.parent().showCriticalMessage(
                _("Unable to find the eyetracker computer in the network!"))
            self.parent().onResume()
            return

        res = 0
        i = 0
        while res != 1 and i < self.parameters['connectmaxtries']:
            # Just in case the previous one did not stop anything
            try:
                iViewXAPI.iV_Disconnect()
            except:
                pass

            res = iViewXAPI.iV_Connect(self.adress_iviewx, self.parameters[
                                       'smisendport'], adress_local, self.parameters['smireceiveport'])
            i += 1

        if res != 1:
            self.parent().showCriticalMessage(
                _("Unable to connect to the eyetracker!"))
            self.parent().onResume()
            return

        res = iViewXAPI.iV_GetSystemInfo(byref(systemData))
        self.taskUpdateTime = float(1000 / systemData.samplerate)

        # Calibration
        calibrationData = CCalibration(5, 1, 0, 0, 1, 30, 230, 1, 10)
        res = iViewXAPI.iV_SetupCalibration(byref(calibrationData))

        # Calibration loop
        calibration_accepted = False
        deviation_threshold = 0.5  # Maximum deviation angle accepted for calibration

        while not calibration_accepted:

            res = iViewXAPI.iV_Calibrate()

            res = iViewXAPI.iV_Validate()

            accuracyData = CAccuracy(0, 0, 0, 0)
            res = iViewXAPI.iV_GetAccuracy(byref(accuracyData), 1)
            meanDeviation = (accuracyData.deviationXLeft + accuracyData.deviationXRight +
                             accuracyData.deviationYLeft + accuracyData.deviationYRight) / 4

            if meanDeviation <= deviation_threshold:
                calibration_accepted = True
            print('Mean deviation -> ' + str(meanDeviation))

        tempDict = {
            'sampleRate (Hz)': str(systemData.samplerate),
            'iViewX_version': str(systemData.iV_MajorVersion) + "." + str(
                systemData.iV_MinorVersion) + "." + str(systemData.iV_Buildnumber),
            'API_version': str(systemData.API_MajorVersion) + "." + str(
                systemData.API_MinorVersion) + "." + str(systemData.API_Buildnumber),
            'deviationXLeft': str(accuracyData.deviationXLeft),
            'deviationXRight': str(accuracyData.deviationXRight),
            'deviationYLeft': str(accuracyData.deviationYLeft),
            'deviationYRight': str(accuracyData.deviationYRight),
            'header':
                '\t'.join(
                    [thisInfo for thisInfo in self.parameters['getFromSample']])
        }

        SMILOG_FILE_PATH = self.parent().LOG_FILE_PATH[:-4] + '_ET.log'
        self.sampleLog = Logger.Logger(self.parent(),SMILOG_FILE_PATH, tempDict)

        iViewXAPI.iV_SetLogger(1, "iViewX_log.txt")

        res = iViewXAPI.iV_SaveCalibration("save_calibration")

        try:
            res = iViewXAPI.iV_StopRecording()
        except:
            pass

        res = iViewXAPI.iV_StartRecording()
        if res != 1:
            self.parent().showCriticalMessage(
                _("Unable to start recording the eyetracker!"))
            return

        self.parent().onResume()

    def UNCHECKED(self, type):
        if (hasattr(type, "_type_") and isinstance(type._type_, str)
                and type._type_ != "P"):
            return type
        else:
            return c_void_p

    def onUpdate(self):
        self.readSample()

    def onEnd(self):
        try:
            iViewXAPI.iV_StopRecording()
            iViewXAPI.iV_Disconnect()
        except:
            pass

    def readSample(self):
        res = iViewXAPI.iV_GetSample(byref(sampleData))

        self.samples_to_test.append(res)
        if len(self.samples_to_test) == self.test_window * systemData.samplerate:
            if (float(self.samples_to_test.count(1)) / len(self.samples_to_test)) < 1 - self.sample_threshold:
                self.parent().showCriticalMessage(
                    _("Too many bad samples during the last %s seconds") % + str(self.test_window))
            self.samples_to_test = []

        self.sampleLog.getSmiStamp(sampleData.timestamp)
        self.fromSample = {
            'gazeLX': sampleData.leftEye.gazeX,
            'gazeLY': sampleData.leftEye.gazeY,
            'positionLX': sampleData.leftEye.eyePositionX,
            'positionLY': sampleData.leftEye.eyePositionY,
            'positionLZ': sampleData.leftEye.eyePositionZ,
            'diamL': sampleData.leftEye.diam,
            'gazeRX': sampleData.rightEye.gazeX,
            'gazeRY': sampleData.rightEye.gazeY,
            'positionRX': sampleData.rightEye.eyePositionX,
            'positionRY': sampleData.rightEye.eyePositionY,
            'positionRZ': sampleData.rightEye.eyePositionZ,
            'diamR': sampleData.rightEye.diam
        }

        sample = [self.fromSample[entry]
                  for entry in self.parameters['getFromSample']]
        self.sampleLog.addLine(sample)

    # def onPause(self):
    #     try:
    #         iViewXAPI.iV_PauseEyetracking()
    #     except:
    #         pass

    # def onResume(self):
    #     try:
    #         iViewXAPI.iV_ContinueEyetracking()
    #     except:
    #         pass
