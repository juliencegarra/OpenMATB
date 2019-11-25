from PySide2 import QtWidgets
import datetime
import os

class Logger(QtWidgets.QWidget):
    def __init__(self, parent, logPath, headerDict={}):
        super(Logger, self).__init__(parent)
        self.logPath = logPath
        self.sep = '\t'
        self.endLine = '\n'
        self.additionalDict = headerDict
        self.smiStamp = ''

        if not os.path.isfile(self.logPath):
            self.writeHeader()

    def writeHeader(self):
        dateString = '_'.join(
            self.logPath.split(os.sep)[1].replace('.log', '').split('_')[1:])

        with open(self.logPath, 'w') as logFile:
            # import pdb; pdb.set_trace()
            dictToLog = {
                'date': dateString,
                # 'screenWidth':
                #     str(QtWidgets.QApplication.desktop().screen().width()),
                # 'screenHeight':
                #     str(QtWidgets.QApplication.desktop().screen().height())
            }

            dictToLog.update(self.additionalDict)

            for key, value in dictToLog.items():
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
