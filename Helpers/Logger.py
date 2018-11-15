from PySide import QtGui
import datetime
import os

class Logger(QtGui.QWidget):
    def __init__(self, parent, logPath, headerDict={}):
        super(Logger, self).__init__(parent)
        self.logPath = logPath
        self.sep = '\t'
        self.endLine = '\n'
        self.additionalDict = headerDict
        self.smiStamp = ''
        # self.begin_time = datetime.datetime.now()

        if not os.path.isfile(self.logPath):
            self.writeHeader()

    def writeHeader(self):
        dateString = '_'.join(
            self.logPath.split(os.sep)[1].replace('.log', '').split('_')[1:])

        with open(self.logPath, 'w') as logFile:
            dictToLog = {
                'date': dateString,
                'screenWidth':
                    str(QtGui.QApplication.desktop().screen().width()),
                'screenHeight':
                    str(QtGui.QApplication.desktop().screen().height())
            }

            dictToLog.update(self.additionalDict)

            for key, value in dictToLog.iteritems():
                logFile.write(
                    "#" + self.sep + key + self.sep + str(value) + self.endLine)
            logFile.write(self.endLine)

    def listToStringLine(self, thisList):
        stringLine = self.sep.join([str(x) for x in thisList])
        return stringLine

    def getSmiStamp(self, timestamp):
        self.smiStamp = timestamp

    def addLine(self, listToLog):
        fullList = [datetime.datetime.now().strftime(
            "%H:%M:%S.%f"), self.smiStamp] + listToLog
        self.smiStamp = ''
        stringLine = self.listToStringLine(fullList)
        
        # Send log information to MATB.py, so it can communicate it to plugins
        self.parent().sendLogToPlugins(stringLine)

        with open(self.logPath, 'a') as logFile:
            logFile.write(stringLine + self.endLine)
#            self.parent()
