# -*- coding: utf-8 -*-
#!/usr/bin/env python

# iViewXAPI.py
#
# Demonstrates features of iView X API
# Defines structures
# Loads in iViewXAPI.dll
# This script shows how to set up an experiment with Python 2.7.1 (with ctypes Library)
#
# Author: SMI GmbH
# Feb. 16, 2011

from ctypes import *


#===========================
#		Struct Definition
#===========================

class CSystem(Structure):
    _fields_ = [("samplerate", c_int),
                ("iV_MajorVersion", c_int),
                ("iV_MinorVersion", c_int),
                ("iV_Buildnumber", c_int),
                ("API_MajorVersion", c_int),
                ("API_MinorVersion", c_int),
                ("API_Buildnumber", c_int),
                ("iV_ETDevice", c_int)]


class CCalibration(Structure):
    _fields_ = [("method", c_int),
                ("visualization", c_int),
                ("displayDevice", c_int),
                ("speed", c_int),
                ("autoAccept", c_int),
                ("foregroundBrightness", c_int),
                ("backgroundBrightness", c_int),
                ("targetShape", c_int),
                ("targetSize", c_int),
                ("targetFilename", c_char * 256)]


class CEye(Structure):
    _fields_ = [("gazeX", c_double),
                ("gazeY", c_double),
                ("diam", c_double),
                ("eyePositionX", c_double),
                ("eyePositionY", c_double),
                ("eyePositionZ", c_double)]


class CSample(Structure):
    _fields_ = [("timestamp", c_longlong),
                ("leftEye", CEye),
                ("rightEye", CEye),
                ("planeNumber", c_int)]


class CEvent(Structure):
    _fields_ = [("eventType", c_char),
                ("eye", c_char),
                ("startTime", c_longlong),
                ("endTime", c_longlong),
                ("duration", c_longlong),
                ("positionX", c_double),
                ("positionY", c_double)]


class CAccuracy(Structure):
    _fields_ = [
        ("deviationXLeft", c_double),
        ("deviationYLeft", c_double),
        ("deviationXRight", c_double),
        ("deviationYRight", c_double),
    ]


class CImageStruct(Structure):
    _fields_ = [
        ("imageHeight", c_int),
        ("imageWidth", c_int),
        ("imageSize", c_int),
        ("imageBuffer", c_char),  # Ou  c_ubyte * MAX_IMAGE_SIZE
    ]


class CTimestamp(Structure):
    _fields_ = [("timestamp", c_double)]


class CAOIRectangleStruct(Structure):
    _fields_ = [
        ("x1", c_int),
        ("x2", c_int),
        ("y1", c_int),
        ("y2", c_int)
    ]


class CAOIStruct(Structure):
    _fields_ = [
        ("enabled", c_int),
        ("aoiName", c_char * 256),
        ("aoiGroup", c_char * 256),
        ("AOIRectangleStruct", CAOIRectangleStruct),  # position
        ("fixationHit", c_int),
        ("eye", c_char),
        ("outputValue", c_int),
        ("outputMessage", c_char * 256)
    ]


#===========================
#		Loading iViewX.dll
#===========================
# pdb.set_trace()
try:
    iViewXAPI = windll.LoadLibrary("iViewXAPI.dll")
except:
    iViewXAPI = None


# pydll.LoadLibrary("iViewXAPI.dll")


#===========================
#		Initializing Structs
#===========================

systemData = CSystem(0, 0, 0, 0, 0, 0, 0, 0)
calibrationData = CCalibration(5, 1, 0, 0, 1, 20, 239, 1, 15, b"")
leftEye = CEye(0, 0, 0)
rightEye = CEye(0, 0, 0)
sampleData = CSample(0, leftEye, rightEye, 0)
eventData = CEvent(b'F', b'L', 0, 0, 0, 0, 0)

timestampData = CTimestamp(0)

tmpAOIrectangle = CAOIRectangleStruct(0, 0, 0, 0)
tmpAOI = CAOIStruct(1, b"", b"", tmpAOIrectangle, 0, b'R', 0, b"")
