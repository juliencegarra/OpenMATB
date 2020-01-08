from PySide2 import QtWidgets, QtCore, QtGui
from Helpers import WCom
from copy import copy
import os
import string
import wave
from rstr import xeger
from random import randrange, choice
from math import copysign
from pygame import mixer
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # COMMUNICATIONS PARAMETERS ###
        self.parameters = {
            'title': 'Communications',
            'taskplacement': "bottomleft",
            'taskupdatetime': 50,
            'callsignregex': '[A-Z][A-Z][A-Z]\d\d\d',
            'owncallsign': '',
            'othercallsign': [],
            'othercallsignnumber': 5,
            'airbandminMhz': 108,
            'airbandmaxMhz': 137,
            'airbandminvariationMhz': 5,
            'airbandmaxvariationMhz': 6,
            'radiostepMhz': 0.1,
            'voicegender': 'male',
            'voiceidiom': 'french',
            'radioprompt': '',
            'promptlist': ['NAV_1', 'NAV_2', 'COM_1', 'COM_2'],
            'automaticsolver': False,
            'displayautomationstate': False,
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Preallocate a dictionary to handle radios information
        self.parameters['radios'] = {}
        for this_destination in ['own', 'other']:
            self.parameters['radios'][this_destination] = {}
            for r, this_radio in enumerate(self.parameters['promptlist']):
                self.parameters['radios'][this_destination][r] = {
                    'name': this_radio,
                    'currentfreq': None,
                    'targetfreq': None,
                    'lasttarget': None,
                    'index': r
                }

        self.parameters['frequencyresolutionKhz'] = 100

        # Use list to learn about already created callsign/radio... to minimize
        # repetitions
        self.letters = string.ascii_uppercase
        self.digits = string.digits
        self.lastradioselected = ''

        # Set a boolean to handle automatic solving
        self.automaticsolving = False

    def onStart(self):

        self.font = QtGui.QFont(
            "sans-serif", self.height() / 30, QtGui.QFont.Bold)
        self.upper_margin = self.height() / 12

        if self.parameters['displayautomationstate']:
            # Define a QLabel object to display mode
            self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
            self.modeLabel = QtWidgets.QLabel(self)
            self.modeLabel.setGeometry(QtCore.QRect(self.width() * 0.5, self.height() * 0.10, self.width() * 0.20, 20))
            self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
            self.modeLabel.setFont(self.modeFont)
            self.refreshModeLabel()
            self.update()

        self.sound_started = False

        # Check that the regular expression for callsign only contains letters
        # and digits
        if len(self.parameters['callsignregex'].replace('[A-Z]', '').replace('\d', '')) > 0:
            self.parent().showCriticalMessage(_("'%s' is problematic in the regular expression for callsign. It should only contains letters ([A-Z]) and/or digits (\d)") % (self.parameters['callsignregex'].replace('[A-Z]', '').replace(
                '\d', '')))

        # Generate sound paths...
        wd = self.parent().working_directory
        self.sound_path = os.sep.join([wd, 'Sounds',
                                       self.parameters['voiceidiom'],
                                       self.parameters['voicegender']])

        self.noise_path = os.sep.join([wd, 'Sounds', 'noise.wav'])
        samples = [s for s in string.digits + string.ascii_lowercase] \
            + [this_radio.lower() for this_radio in
               self.parameters['promptlist']] + ['radio', 'point', 'frequency']
        self.sample_list = ['{}.wav'.format(i) for i in samples]
        self.generated_sound_path = os.sep.join([wd, 'Sounds', 'output'])

        # ...and check if there are all available
        for sample_needed in self.sample_list:
            if sample_needed not in os.listdir(self.sound_path):
                self.parent().showCriticalMessage(_("The '%s' file is missing from the '%s' directory") % (sample_needed, self.sound_path))

        # Check if the output folder exists, if not create it
        if not os.path.exists(self.generated_sound_path):
            os.makedirs(self.generated_sound_path)

        # If yes and the folder not empty, empty it
        elif len(os.listdir(self.generated_sound_path)) > 0:
            for this_file in os.listdir(self.generated_sound_path):
                os.remove(self.generated_sound_path + os.sep + this_file)

        # If no subject_callsign defined in scenario, generate one
        if self.parameters['owncallsign'] == '':
            self.parameters['owncallsign'] = self.generateCallsign()

        # Log the participant callsign
        self.buildLog(["STATE", "OWNCALLSIGN", "",
                       self.parameters['owncallsign']])

        # If no othercallsign specified, generate it, according to the desired
        # num_of_othercallsign. Avoid generating identical callsign (especially
        # compared to the owncallsign)
        for i in range(self.parameters['othercallsignnumber']):
            new_callsign = False
            while not new_callsign:
                this_callsign = self.generateCallsign()
                new_callsign = (this_callsign not in
                                self.parameters['othercallsign'] +
                                [self.parameters['owncallsign']])
            self.parameters['othercallsign'].append(this_callsign)

        # Log the list of distractor callsigns
        self.buildLog(["STATE", "OTHERCALLSIGN", "",
                      self.parameters['othercallsign']])

        # If no initial frequencies, choose random frequencies between
        # airband_min and airband_max
        for radio_type in ['own', 'other']:
            for this_radio, radios_values in \
                    self.parameters['radios'][radio_type].items():
                if radios_values['currentfreq'] is None:
                    radios_values['currentfreq'] = self.generateFrequency()

        # Display (own) environment...
        self.callsign = QtWidgets.QLabel(self)
        self.callsign.setText(
            u'Identifiant    \u27A1    ' + self.parameters['owncallsign'])
        self.callsign.setFont(self.font)
        self.callsign.setAlignment(
            QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.callsign.setGeometry(
            0, self.upper_margin, self.width(), self.parent().height() / 5.)
        self.callsign.show()

        # ...with each radio...
        for r, radio_values in self.parameters['radios']['own'].items():

            # ...being displayed as a WCom Qt object
            # Upper radio will be selected by default
            radio_values['ui'] = WCom.WCom(self, radio_values['index'])
            radio_values['ui'].show()
            radio_values['ui'].refreshValues()

        # Initialize pygame.mixer() for sound playing
        mixer.init()

    def onEnd(self):
        mixer.quit()

    def onPause(self):
        mixer.pause()

    def onResume(self):
        mixer.unpause()

    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()

        # Check for required automated actions (one step per update)
        if self.automaticsolving:
            own_radios = self.parameters['radios']['own']

            current_index = [r['index'] for i, r in own_radios.items() if
                             r['ui'].is_selected][0]

            target_index = [r['index'] for i, r in own_radios.items() if
                            r['name'] == self.temp_radio][0]

            abs_diff = abs(own_radios[current_index]['currentfreq'] -
                           own_radios[current_index]['targetfreq'])
            # Automatic switch between radios
            if current_index != target_index:
                own_radios[current_index]['ui'].is_selected = 0
                own_radios[current_index]['ui'].refreshValues()

                current_index += copysign(1, target_index - current_index)

                own_radios[current_index]['ui'].is_selected = 1
                own_radios[current_index]['ui'].refreshValues()

                self.buildLog(["STATE", 'OWN',
                              self.parameters['promptlist'][current_index - 1],
                              "SELECTED"])

            # Automatic radio tune
            elif abs_diff > self.parameters['radiostepMhz']:
                own_radios[current_index]['currentfreq'] += copysign(
                        self.parameters['radiostepMhz'], abs_diff)
                own_radios[current_index]['ui'].refreshValues()
                self.buildLog(["STATE", 'OWN',
                              self.parameters['promptlist'][current_index - 1],
                              str(own_radios[current_index]['currentfreq'])])

            else:
                self.automaticsolving = False
                self.buildLog(["INPUT", 'AUTO_KEY_RELEASE', 'RETURN',
                              "RESPONSE_END"])

        # Check for a radio prompt query...
        if self.parameters['radioprompt'].lower() in ['own', 'other']:
            # Set a target frequency for a randomly chosen radio in
            # either own or other radios

            # Select a radio among available radios in list (avoid repetition)
            while True:
                selected_radio = choice(self.parameters['promptlist'])
                if selected_radio != self.lastradioselected:
                    break

            self.lastradioselected = copy(selected_radio)
            self.setTargetFrequency(self.parameters['radioprompt'].lower(),
                                    selected_radio)
            self.parameters['radioprompt'] = ''

        # Is a prompt needed and possible (mixer not busy) ?
        # (i.e. incoming sound must wait the end of the previous sound to start)
        if not mixer.get_busy():

            # Particular case : if the mixer is not busy and a sound has been
            # started, it means the prompt has ended. So log it.
            if self.sound_started:
                self.buildLog(["STATE", self.temp_destination, self.temp_radio,
                              "END_PROMPT"])
                self.sound_started = False
                if (self.parameters['automaticsolver'] and
                        self.temp_destination.lower() == 'own'):
                    self.automaticsolving = True

            # Browse all the radios
            for this_destination in self.parameters['radios']:
                for this_radio, radio_values in \
                        self.parameters['radios'][this_destination].items():
                    this_radio_name = radio_values['name']

                    # Check if there is a target, and if it is new
                    if (radio_values['targetfreq'] !=
                        radio_values['currentfreq']
                        and radio_values['targetfreq'] !=
                            radio_values['lasttarget']):

                        # If so, log the radio name and the corresponding
                        # target frequency
                        self.buildLog(["STATE", this_destination.upper(),
                                      this_radio_name, "TARGET",
                                      str(radio_values['targetfreq'])])

                        # Retrieve callsign and prompt information
                        callsign = self.parameters['owncallsign'] if \
                            this_destination == 'own' else \
                            choice(self.parameters['othercallsign'])

                        prompt = '_'.join([this_destination.upper(),
                                          callsign.upper(),
                                          this_radio_name.upper(),
                                          str(radio_values['targetfreq'])])

                        # Generate audiofile on the fly
                        audiofile_path = self.create_audio_file(prompt)

                        # Play the file and the log a prompt start
                        mixer.Sound(audiofile_path).play()
                        self.buildLog(["STATE", this_destination.upper(),
                                      this_radio_name, "START_PROMPT"])
                        self.temp_destination = this_destination.upper()
                        self.temp_radio = this_radio_name
                        self.sound_started = True

                        # Mark this_target as lasttarget to avoid repetition
                        radio_values['lasttarget'] = \
                            copy(radio_values['targetfreq'])

        # If the mixer is busy and a prompt is needed, warn the experimenter
        elif mixer.get_busy():
            # Browse all the radios
            for this_destination in self.parameters['radios']:
                for this_radio, radio_values in \
                        self.parameters['radios'][this_destination].items():

                    this_radio_name = radio_values['name']

                    # Check if there is a target, and if it is new
                    if (radio_values['targetfreq'] !=
                        radio_values['currentfreq']
                        and radio_values['targetfreq'] !=
                            radio_values['lasttarget']):
                        print('! ' + self.parent().scenarioTimeStr + " : " +"prompt required but mixer already busy! Check that your prompts are spaced with a sufficient duration")

    def keyEvent(self, key_pressed):
        own_radios = self.parameters['radios']['own']
        if self.automaticsolving:
            return

        # If the key pressed is not an arrow key, ignore it
        if key_pressed not in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down,
                               QtCore.Qt.Key_Left, QtCore.Qt.Key_Right,
                               QtCore.Qt.Key_Return]:
            return
        elif key_pressed == QtCore.Qt.Key_Return:
            self.buildLog(["INPUT", 'KEY_RELEASE', 'RETURN', "RESPONSE_END"])
        else:
            # Retrieve information about the radio that is currently selected
            selected_radio = [r for i, r in own_radios.items() if
                              r['ui'].is_selected][0]

            # index = self.parameters['radios']['own'][radio_name]['index']
            next_radio = None

            # Up and down keys are for radio selection
            if key_pressed == QtCore.Qt.Key_Up and selected_radio['index'] > 0:
                next_radio = [r for i, r in own_radios.items() if
                              r['index'] == selected_radio['index'] - 1][0]
            elif key_pressed == QtCore.Qt.Key_Down and \
                    selected_radio['index'] < len(own_radios) - 1:
                next_radio = [r for i, r in own_radios.items() if
                              r['index'] == selected_radio['index'] + 1][0]

            # Potential radio switch
            if next_radio is not None:
                selected_radio['ui'].is_selected = 0
                selected_radio['ui'].refreshValues()
                next_radio['ui'].is_selected = 1
                next_radio['ui'].refreshValues()

                self.buildLog(["STATE", 'OWN', next_radio, "SELECTED"])

            # Frequency selection input (check that the desired frequency
            # change is possible)
            lastfreq = None
            if (key_pressed == QtCore.Qt.Key_Right and
                    selected_radio['currentfreq'] +
                    self.parameters['radiostepMhz']
                    < self.parameters['airbandmaxMhz']):
                lastfreq = copy(selected_radio['currentfreq'])
                selected_radio['currentfreq'] += self.parameters['radiostepMhz']
                selected_radio['currentfreq'] = self.roundFrequency(
                    selected_radio['currentfreq'])

            elif (key_pressed == QtCore.Qt.Key_Left and
                  selected_radio['currentfreq'] -
                  self.parameters['radiostepMhz'] >
                  self.parameters['airbandminMhz']):
                lastfreq = copy(selected_radio['currentfreq'])
                selected_radio['currentfreq'] -= self.parameters['radiostepMhz']
                selected_radio['currentfreq'] = self.roundFrequency(
                    selected_radio['currentfreq'])

            # Refresh new value only if it represents a change
            if lastfreq != selected_radio['currentfreq']:
                selected_radio['ui'].refreshValues()
                self.buildLog(["STATE", 'OWN', selected_radio['name'],
                              str(selected_radio['currentfreq'])])

    def roundFrequency(self, raw_frequency):
        return round((raw_frequency * 1000 /
                     float(self.parameters['frequencyresolutionKhz']))) / (
                     1000 / float(self.parameters['frequencyresolutionKhz']))

    def generateCallsign(self):
        '''Generate a callsign with no duplicate character. Pick characters in
        a list to maximize chance to avoid callsign duplicates'''
        duplicateChar = True
        notInList = True
        count = {}

        # Refresh letters/digits list if their length is not sufficient
        if len(self.letters) < self.parameters['callsignregex'].count('[A-Z]'):
            self.letters = string.ascii_uppercase

        if len(self.digits) < self.parameters['callsignregex'].count('\d'):
            self.digits = string.digits

        while duplicateChar or notInList:
            callsign = xeger(self.parameters['callsignregex'])

            # Test duplicate in the callsign itself
            for this_sign in callsign:
                count[this_sign] = callsign.count(this_sign)
            if all([count[this_letter] == 1 for this_letter in count]):
                duplicateChar = False
            else:
                duplicateChar = True

            # Test if the letters/digits used are available in (potentially
            # refreshed) lists
            for this_sign in callsign:
                notInList = this_sign not in self.letters + self.digits
                if notInList:
                    break

        for this_sign in callsign:
            if this_sign in self.letters:
                self.letters = self.letters.replace(this_sign, '')
            elif this_sign in self.digits:
                self.digits = self.digits.replace(this_sign, '')

        return callsign

    def generateFrequency(self):
        '''Return a random frequency, chosen between airbandminMhz and
        airbandmaxMhz, at the correct frequencyresolutionKhz'''
        temp = randrange(
            self.parameters['airbandminMhz'] * 10 ** 3,
            self.parameters['airbandmaxMhz'] * 10 ** 3) / 1000.

        return self.roundFrequency(temp)

    def setTargetFrequency(self, prompt_destination, radio_name):
        radio = [r for i, r in
                 self.parameters['radios'][prompt_destination].items() if
                 r['name'] == radio_name][0]
        good_frequency = False
        while not good_frequency:
            random_frequency = self.generateFrequency()
            if (self.parameters['airbandminvariationMhz'] <
                    abs(random_frequency - radio['currentfreq']) <
                    self.parameters['airbandmaxvariationMhz']):
                good_frequency = True

        radio['targetfreq'] = random_frequency

    def create_audio_file(self, output_name):
        '''Build an audiofile on the fly, as a function of callsign, radio and
        frequency'''

        outfile_path = os.sep.join([self.generated_sound_path,
                                    '{}.wav'.format(output_name)])

        callsign = output_name.split('_')[1]
        radio = '_'.join(output_name.split('_')[2:4])
        freq = output_name.split('_')[4]

        list_of_sounds = ['empty'] + [str(char).lower() for char in callsign] + [str(char).lower() for char in callsign] + ['radio'] + [radio.lower()] + ['frequency'] +  [str(char).lower().replace('.', 'point') for char in freq]
        files_to_concat = [os.sep.join([self.sound_path,
                           '{}.wav'.format(sound)]) for sound in list_of_sounds]

        data = []
        for infile in files_to_concat:
            w = wave.open(infile, 'rb')
            w = wave.open(infile, 'rb')
            data.append([w.getparams(), w.readframes(w.getnframes())])
            w.close()

        output = wave.open(outfile_path, 'wb')
        output.setparams(data[0][0])
        output.setframerate(41000)
        for d, this_data in enumerate(data):
            output.writeframes(data[d][1])
        output.close()

        return outfile_path

    def refreshModeLabel(self):
        if self.parameters['automaticsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def buildLog(self, thisList):
        thisList = ["COMMUN"] + thisList
        self.parent().mainLog.addLine(thisList)
