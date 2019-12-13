from PySide2 import QtCore, QtWidgets, QtGui
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.resman = None

        # PUMPSTATUS PARAMETERS ###
        self.parameters = {
            'taskplacement': 'bottomright',
            'taskupdatetime': 1000,
            'title': 'Pump status'
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

    def onStart(self):

        # Retrieve resman pump values
        dictresman = self.getResmanPumpParameters()
        if not dictresman:
            return

        # Define font sizes
        fontsize = int(self.height() / 30.)
        self.titleFont = QtGui.QFont("sans-serif", fontsize, QtGui.QFont.Bold)
        self.textFont = QtGui.QFont(
            "sans-serif", fontsize - 1, QtGui.QFont.Bold)

        # Arrange the layout
        self.width = self.parent().placements[
            self.parameters['taskplacement']]['control_width']
        layout = QtWidgets.QVBoxLayout()
        hlayout = QtWidgets.QHBoxLayout()
        layout.addLayout(hlayout)

        # For each resman pump
        for k in sorted(dictresman):

            # If it is not hidden
            if not dictresman[k]['hide']:

                # Allocate an horizontal box in the layout, filled with three
                # distinct elements
                hbox = QtWidgets.QHBoxLayout()

                # 1. A QLabel Qt object (pump number)
                dictresman[k]['ui_statuscaption'] = QtWidgets.QLabel(self)
                dictresman[k]['ui_statuscaption'].setFont(self.textFont)
                dictresman[k]['ui_statuscaption'].setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

                # Add QLabel object to the horizontal layout
                hbox.addWidget(dictresman[k]['ui_statuscaption'])

                # 2. An arrow in a QLabel Qt object
                triangle = QtWidgets.QLabel(u'\u25B6', self)
                triangle.setFixedWidth(self.parent().height() / 14.)
                triangle.setAlignment(
                    QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)

                # Add this arrow to the horizontal layout
                hbox.addWidget(triangle)

                # 3. A QLabel Qt object (pump flow value)
                dictresman[k]['ui_statusvalue'] = QtWidgets.QLabel(self)
                dictresman[k]['ui_statusvalue'].setFont(self.textFont)
                dictresman[k]['ui_statusvalue'].setAlignment(
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                # Add QLabel object to the horizontal layout
                hbox.addWidget(dictresman[k]['ui_statusvalue'])

                # Add the resulting horizontal layout to the general layout
                layout.addLayout(hbox)

        # The resulting layout is composed by horizontal layouts : one for each
        # pump
        self.setLayout(layout)
        self.onUpdate()

    def onUpdate(self):

        # Retrieve current resman pump values
        dictresman = self.getResmanPumpParameters()

        if not dictresman:
            return

        # For each resman pump
        for k in dictresman:

            # Set the pump name
            if 'ui_statuscaption' in dictresman[k]:
                dictresman[k]['ui_statuscaption'].setText(
                    "<b>" + str(k) + "</b>")

            # And the pump flow value
            if 'ui_statusvalue' in dictresman[k]:

                # If the pump is not ON
                if dictresman[k]['state'] != 1:

                    # Display a zero
                    dictresman[k]['ui_statusvalue'].setText("<b><i>0</b></i>")

                    # Else, display the flow value
                else:
                    dictresman[k]['ui_statusvalue'].setText(
                        "<b><i>" + str(dictresman[k]['flow']) + "</b></i>")

    def getResmanPumpParameters(self):
        if not self.resman:
            self.resman = self.parent().getPluginClass("resman")
        return self.resman.parameters['pump']
