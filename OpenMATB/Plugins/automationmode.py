from PySide import QtCore, QtGui

# ignoré par le git


class Task(QtGui.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': 5000,
            'automationmode': -1,
            'automationmodenames': [
                u"Sans assistance", u"Avertissement", u"Contrôle partagé", u"Délégation"],
        }

        self.automatisationtitre = QtGui.QLabel(u"", self)
        self.automatisationtitre.setStyleSheet(
            "font: 18pt \"MS Shell Dlg 2\"; ")

        self.automatisationtitre.hide()
        self.track = None
        self.resman = None
        self.sysmon = None

    def onStart(self):
        self.taskRunning = True
        self.track = self.parent().getPluginClass("track")
        self.resman = self.parent().getPluginClass("resman")
        self.sysmon = self.parent().getPluginClass("sysmon")

#
#
# elif scenariodata[0] == "selectmode":
# self.taskRunning = True
# self.runTask()
# elif scenariodata[0] == "changemode":
# self.taskRunning = True
# self.onChangeAutomatisation(int(scenariodata[1]), "SCRIPT")
#
# def runTask(self):
        # if self.taskRunning == False:
        #    return

        self.parent().onPause()

        self.screen_width = QtGui.QApplication.desktop().screen().width()
        self.screen_height = QtGui.QApplication.desktop().screen().height()

        h = 20

        self.automatisationscreen_titre = QtGui.QLabel(
            u"Quel mode voulez-vous choisir ?", self)
        self.automatisationscreen_titre.setStyleSheet(
            "font: 14pt \"MS Shell Dlg 2\"; ")
        self.automatisationscreen_titre.resize(
            self.automatisationscreen_titre.sizeHint())
        self.automatisationscreen_titre.move(
            (self.screen_width - self.automatisationscreen_titre.width()) / 2, h)

        self.btnmode0 = QtGui.QPushButton(u'Sans assistance', self)
        self.btnmode0.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")
        self.btnmode0.clicked.connect(self.lancemode0)
        self.btnmode0.resize(self.btnmode0.sizeHint())
        self.btnmode0.move(
            (self.screen_width - self.btnmode0.width()) / 2, h + 40)

        self.btnmode1 = QtGui.QPushButton(u'Avertissement', self)
        self.btnmode1.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")
        self.btnmode1.clicked.connect(self.lancemode1)
        self.btnmode1.resize(self.btnmode1.sizeHint())
        self.btnmode1.move(
            (self.screen_width - self.btnmode1.width()) / 2, h + 80)

        self.btnmode2 = QtGui.QPushButton(u'Contrôle partagé', self)
        self.btnmode2.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")
        self.btnmode2.clicked.connect(self.lancemode2)
        self.btnmode2.resize(self.btnmode2.sizeHint())
        self.btnmode2.move(
            (self.screen_width - self.btnmode2.width()) / 2, h + 120)

        self.btnmode3 = QtGui.QPushButton(u'Délégation', self)
        self.btnmode3.setStyleSheet("font: 14pt \"MS Shell Dlg 2\"; ")
        self.btnmode3.clicked.connect(self.lancemode3)
        self.btnmode3.resize(self.btnmode3.sizeHint())
        self.btnmode3.move(
            (self.screen_width - self.btnmode3.width()) / 2, h + 160)

        self.automatisationscreen_titre.show()
        self.btnmode0.show()
        self.btnmode1.show()
        self.btnmode2.show()
        self.btnmode3.show()
        self.show()

    def lancemode0(self):
        self.lancemode(0)

    def lancemode1(self):
        self.lancemode(1)

    def lancemode2(self):
        self.lancemode(2)

    def lancemode3(self):
        self.lancemode(3)

    def lancemode(self, id):
        # self.parent().allshow()
        self.parent().onResume()

        # self.automatisationtitre.show()
        self.automatisationscreen_titre.hide()
        self.btnmode0.hide()
        self.btnmode1.hide()
        self.btnmode2.hide()
        self.btnmode3.hide()

        self.onChangeAutomatisation(id, "MENU")

    def onChangeAutomatisation(self, mode, source):
        self.parent().addLog("AUTOMATISATION_CHANGE;" + str(source) + ";" + str(mode) +
                             ";" + str(self.self.parameters['automationmode']))  # +";"+self.parameters['automationmodenames'][mode])

        if mode != self.self.parameters['automationmode']:
            self.automatisationtitre.setText(
                self.parameters['automationmodenames'][mode])
            self.automatisationtitre.resize(
                self.automatisationtitre.sizeHint())
            self.automatisationtitre.move(
                (self.screen_width - self.automatisationtitre.width()) / 2, 2)
            self.self.parameters['automationmode'] = mode

            if mode == 0:
                # MANUEL

                # tracking
                if self.track:
                    self.track.change_color = False
                    self.track.automatic_solver = False
                    self.track.assisted_solver = False

                # symon
                if self.sysmon:
                    self.sysmon.change_color = False
                    self.sysmon.allow_any_key = False
                    self.sysmon.automatic_solver = False

                # resman
                if self.resman:
                    self.resman.change_color_fail = False
                    self.resman.change_color_suggest = False
                    self.resman.automatic_solver = False

            elif mode == 1:
                # AVERTISSEMENT
                if self.track:
                    self.track.change_color = True
                    self.track.automatic_solver = False
                    self.track.assisted_solver = False

                if self.sysmon:
                    self.sysmon.change_color = True
                    self.sysmon.allow_any_key = False
                    self.sysmon.automatic_solver = False

                if self.resman:
                    self.resman.change_color_fail = True
                    self.resman.change_color_suggest = False
                    self.resman.automatic_solver = False

            elif mode == 2:
                # CONTROLE PARTAGE
                if self.track:
                    self.track.change_color = False
                    self.track.automatic_solver = False
                    self.track.assisted_solver = True

                if self.sysmon:
                    self.sysmon.change_color = False
                    self.sysmon.allow_any_key = True
                    self.sysmon.automatic_solver = False

                if self.resman:
                    self.resman.change_color_fail = False
                    self.resman.change_color_suggest = True
                    self.resman.automatic_solver = False

            elif mode == 3:
                # DELEGATION
                if self.track:
                    self.track.change_color = False
                    self.track.automatic_solver = True
                    self.track.assisted_solver = False

                if self.sysmon:
                    self.sysmon.change_color = False
                    self.sysmon.allow_any_key = False
                    self.sysmon.automatic_solver = True

                if self.resman:
                    self.resman.change_color_fail = False
                    self.resman.change_color_suggest = False
                    self.resman.automatic_solver = True
