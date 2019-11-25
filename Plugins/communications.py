from PySide2 import QtWidgets, QtCore, QtGui
from Helpers import WCom, QTExtensions
from copy import copy
import os
import string
import wave
from rstr import xeger
from random import randrange, choice
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
                self.parameters['radios'][this_destination][r + 1] = {
                    'name': this_radio,
                    'currentfreq': None,
                    'targetfreq': None,
                    'lasttarget': None,
                    'index': r
                }

        self.parameters['frequencyresolutionKhz'] = 100

        # Use list to learn about already created callsign/radio... to minimize repetitions
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
        self.sound_path = self.parent().working_directory + os.sep + 'Sounds' + os.sep + self.parameters[
            'voiceidiom'] + os.sep + self.parameters['voicegender'] + os.sep
        self.noise_path = self.parent().working_directory + \
            os.sep + 'Sounds' + os.sep + 'noise.wav'
        self.sample_list = [i + '.wav' for i in [s for s in string.digits] + [
            s for s in string.ascii_lowercase] + [this_radio.lower() for this_radio in self.parameters['promptlist']] + ['radio', 'point', 'frequency']]
        self.generated_sound_path = self.parent().working_directory + \
            os.sep + 'Sounds' + os.sep + 'output' + os.sep

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
        self.buildLog(["STATE", "OWNCALLSIGN", "", self.parameters['owncallsign']])

        # If no othercallsign specified, generate it, according to the desired
        # num_of_othercallsign. Avoid generating identical callsign (especially
        # compared to the owncallsign)
        for i in range(0, self.parameters['othercallsignnumber']):
            new_callsign = False
            while not new_callsign:
                this_callsign = self.generateCallsign()
                new_callsign = False if this_callsign in self.parameters[
                    'othercallsign'] + [self.parameters['owncallsign']] else True
            self.parameters['othercallsign'].append(this_callsign)

        # Log the list of distractor callsigns
        self.buildLog(["STATE", "OTHERCALLSIGN", "", self.parameters['othercallsign']])

        # If no initial frequencies, choose random frequencies between
        # airband_min and airband_max
        for radio_type in ['own', 'other']:
            for this_radio in self.parameters['radios'][radio_type].keys():
                if self.parameters['radios'][radio_type][this_radio]['currentfreq'] is None:
                    self.parameters['radios'][radio_type][this_radio][
                        'currentfreq'] = self.generateFrequency()

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

        # ...with each radio
        for this_radio in self.parameters['radios']['own']:

            # ...being displayed as a WCom Qt object
            self.parameters['radios']['own'][this_radio][
                'ui'] = WCom.WCom(self, this_radio)
            self.parameters['radios']['own'][this_radio]['ui'].show()
            self.parameters['radios']['own'][this_radio]['ui'].refreshValues()

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

            current_index = [index for index, radio_place in enumerate(self.parameters['radios']['own'].keys()) if
                          self.parameters['radios']['own'][radio_place]['ui'].is_selected][0] + 1

            target_index = [index for index, radio_place in enumerate(self.parameters['radios']['own'].keys()) if
                          self.parameters['radios']['own'][radio_place]['name'] == self.temp_radio][0] + 1

            # Automatic switch between radios
            if current_index != target_index:

                self.parameters['radios']['own'][current_index]['ui'].is_selected = 0
                self.parameters['radios']['own'][current_index]['ui'].refreshValues()

                if current_index < target_index:
                    current_index += 1
                elif current_index > target_index:
                    current_index -= 1

                self.parameters['radios']['own'][current_index]['ui'].is_selected = 1
                self.parameters['radios']['own'][current_index]['ui'].refreshValues()

                self.buildLog(["STATE", 'OWN', self.parameters['promptlist'][current_index - 1], "SELECTED"])

            # Automatic radio tune
            elif abs(self.parameters['radios']['own'][current_index]['currentfreq'] - self.parameters['radios']['own'][current_index]['targetfreq']) > self.parameters['radiostepMhz']:

                if self.parameters['radios']['own'][current_index]['currentfreq'] < self.parameters['radios']['own'][current_index]['targetfreq']:
                    self.parameters['radios']['own'][current_index]['currentfreq'] += self.parameters['radiostepMhz']

                elif self.parameters['radios']['own'][current_index]['currentfreq'] > self.parameters['radios']['own'][current_index]['targetfreq']:
                    self.parameters['radios']['own'][current_index]['currentfreq'] -= self.parameters['radiostepMhz']

                self.parameters['radios']['own'][current_index]['ui'].refreshValues()
                self.buildLog(["STATE", 'OWN', self.parameters['promptlist'][current_index - 1], str(self.parameters['radios']['own'][current_index]['currentfreq'])])

            else:
                self.automaticsolving = False
                self.buildLog(["INPUT", 'AUTO_KEY_RELEASE', 'RETURN', "RESPONSE_END"])

        # Check for a radio prompt query...
        if self.parameters['radioprompt'].lower() in ['own', 'other']:
            # Set a target frequency for a randomly chosen radio in either own or other radios

            # Select a radio among available radios in list (avoid repetition)
            while True:
                selected_radio = choice(self.parameters['promptlist'])
                if selected_radio != self.lastradioselected:
                    break

            self.lastradioselected = copy(selected_radio)
            self.setTargetFrequency(self.parameters['radioprompt'].lower(), selected_radio)
            self.parameters['radioprompt'] = ''

        # Is a prompt needed and possible (mixer not busy) ?
        # (i.e. incoming sound must wait the end of the previous sound to start)
        if not mixer.get_busy():

            # Particular case : if the mixer is not busy and a sound has been
            # started, it means the prompt has ended. So log it.
            if self.sound_started:
                self.buildLog(["STATE", self.temp_destination, self.temp_radio, "END_PROMPT"])
                self.sound_started = False
                if self.parameters['automaticsolver'] and self.temp_destination.lower() == 'own':
                    self.automaticsolving = True


            # Browse all the radios
            for this_destination in self.parameters['radios'].keys():
                for this_radio in self.parameters['radios'][this_destination].keys():
                    this_radio_name = self.parameters['radios'][this_destination][this_radio]['name']

                    # Check if there is a target, and if it is new
                    if self.parameters['radios'][this_destination][this_radio]['targetfreq'] != self.parameters['radios'][this_destination][this_radio]['currentfreq'] and self.parameters['radios'][this_destination][this_radio]['targetfreq'] != self.parameters['radios'][this_destination][this_radio]['lasttarget']:

                        # If so, log the radio name and the corresponding target frequency
                        self.buildLog(["STATE", this_destination.upper(), this_radio_name, "TARGET", str(self.parameters['radios'][this_destination][this_radio]['targetfreq'])])

                        # Retrieve callsign and prompt information
                        callsign = self.parameters['owncallsign'] if this_destination == 'own' else choice(self.parameters['othercallsign'])
                        prompt = '_'.join([this_destination.upper(), callsign.upper(), this_radio_name.upper(), str(self.parameters['radios'][this_destination][this_radio]['targetfreq'])])

                        # Generate audiofile on the fly
                        audiofile_path = self.create_audio_file(prompt)

                        # Play the file and the log a prompt start
                        mixer.Sound(audiofile_path).play()
                        self.buildLog(["STATE", this_destination.upper(), this_radio_name, "START_PROMPT"])
                        self.temp_destination = this_destination.upper()
                        self.temp_radio = this_radio_name
                        self.sound_started = True

                        # Mark this_target as lasttarget to avoid sound repetition
                        self.parameters['radios'][this_destination][this_radio]['lasttarget'] = copy(self.parameters['radios'][this_destination][this_radio]['targetfreq'])

        # If the mixer is busy and a prompt is needed, warn the experimenter
        elif mixer.get_busy():
            # Browse all the radios
            for this_destination in self.parameters['radios'].keys():
                for this_radio in self.parameters['radios'][this_destination].keys():

                    this_radio_name = self.parameters['radios'][this_destination][this_radio]['name']

                    # Check if there is a target, and if it is new
                    if self.parameters['radios'][this_destination][this_radio]['targetfreq'] != self.parameters['radios'][this_destination][this_radio]['currentfreq'] and self.parameters['radios'][this_destination][this_radio]['targetfreq'] != self.parameters['radios'][this_destination][this_radio]['lasttarget']:
                        print('! ' + self.parent().scenarioTimeStr + " : " +"prompt required but mixer already busy! Check that your prompts are spaced with a sufficient duration")

    def keyEvent(self, key_pressed):

        if self.automaticsolving:
            return

        # If the key pressed is not an arrow key, ignore it
        if key_pressed not in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down, QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Return]:
            return
        elif key_pressed == QtCore.Qt.Key_Return:
            self.buildLog(["INPUT", 'KEY_RELEASE', 'RETURN', "RESPONSE_END"])
        else:
            # Retrieve information about the radio that is currently selected
            radio_name = [radio for index, radio in enumerate(self.parameters['radios']['own'].keys()) if self.parameters['radios']['own'][radio]['ui'].is_selected][0]
            index = self.parameters['radios']['own'][radio_name]['index']
            next_radio = None

            # Up and down keys are for radio selection
            if key_pressed == QtCore.Qt.Key_Up and index > 0:
                next_radio = [radio for radio in self.parameters['radios'][
                    'own'].keys() if self.parameters['radios']['own'][radio]['index'] == index - 1][0]
            elif key_pressed == QtCore.Qt.Key_Down and index < len(self.parameters['radios']['own']) - 1:
                next_radio = [radio for radio in self.parameters['radios'][
                    'own'].keys() if self.parameters['radios']['own'][radio]['index'] == index + 1][0]

            # Potential radio switch
            if next_radio is not None:
                self.parameters['radios']['own'][radio_name]['ui'].is_selected = 0
                self.parameters['radios']['own'][radio_name]['ui'].refreshValues()
                self.parameters['radios']['own'][next_radio]['ui'].is_selected = 1
                self.parameters['radios']['own'][next_radio]['ui'].refreshValues()

                self.buildLog(["STATE", 'OWN', next_radio, "SELECTED"])

            # Frequency selection input (check that the desired frequency change is possible)
            lastfreq = None
            if key_pressed == QtCore.Qt.Key_Right and self.parameters['radios']['own'][radio_name]['currentfreq'] + self.parameters['radiostepMhz'] < self.parameters['airbandmaxMhz']:
                lastfreq = copy(self.parameters['radios']['own'][radio_name]['currentfreq'])
                self.parameters['radios']['own'][radio_name]['currentfreq'] += self.parameters['radiostepMhz']
                self.parameters['radios']['own'][radio_name]['currentfreq'] = self.roundFrequency(self.parameters['radios']['own'][radio_name]['currentfreq'])


            elif key_pressed == QtCore.Qt.Key_Left and self.parameters['radios']['own'][radio_name]['currentfreq'] - self.parameters['radiostepMhz'] > self.parameters['airbandminMhz']:
                lastfreq = copy(
                    self.parameters['radios']['own'][radio_name]['currentfreq'])
                self.parameters['radios']['own'][radio_name][
                    'currentfreq'] -= self.parameters['radiostepMhz']
                self.parameters['radios']['own'][radio_name]['currentfreq'] = self.roundFrequency(self.parameters['radios']['own'][radio_name]['currentfreq'])

            # Refresh new value only if it represents a change
            if lastfreq != self.parameters['radios']['own'][radio_name]['currentfreq']:
                self.parameters['radios']['own'][
                    radio_name]['ui'].refreshValues()
                self.buildLog(
                    ["STATE", 'OWN', radio_name, str(self.parameters['radios']['own'][radio_name]['currentfreq'])])

    def roundFrequency(self, raw_frequency):
        return round((raw_frequency * 1000 /
                     float(self.parameters['frequencyresolutionKhz']))) / (
                     1000 / float(self.parameters['frequencyresolutionKhz']))

    def generateCallsign(self):
        '''Generate a callsign with no duplicate character. Pick characters in a list to maximize chance to avoid callsign duplicates'''
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
            if all([count[this_letter]==1 for this_letter in count.keys()]):
                duplicateChar = False
            else:
                duplicateChar = True

            # Test if the letters/digits used are available in (potentially refreshed) lists
            for this_sign in callsign:
                if this_sign in self.letters + self.digits:
                    notInList = False
                else:
                    notInList = True
                    break

        for this_sign in callsign:
            if this_sign in self.letters:
                self.letters = self.letters.replace(this_sign,'')
            elif this_sign in self.digits:
                self.digits = self.digits.replace(this_sign,'')

        return callsign

    def generateFrequency(self):
        '''Return a random frequency, chosen between airbandminMhz and airbandmaxMhz, at the correct frequencyresolutionKhz'''
        temp = randrange(
            self.parameters['airbandminMhz'] * 10 ** 3, self.parameters['airbandmaxMhz'] * 10 ** 3) / 1000.

        return self.roundFrequency(temp)

    def setTargetFrequency(self, prompt_destination, radio_name):
        radio = [idx for idx in self.parameters['radios'][prompt_destination].keys() if self.parameters['radios'][prompt_destination][idx]['name'] == radio_name][0]
        good_frequency = False
        while not good_frequency:
            random_frequency = self.generateFrequency()
            if self.parameters['airbandminvariationMhz'] < abs(random_frequency - self.parameters['radios'][prompt_destination][radio]['currentfreq']) < self.parameters['airbandmaxvariationMhz']:
                good_frequency = True

        self.parameters['radios'][prompt_destination][
            radio]['targetfreq'] = random_frequency

    def create_audio_file(self, output_name):
        '''Build an audiofile on the fly, as a function of callsign, radio and frequency'''

        outfile_path = self.generated_sound_path + output_name + ".wav"

        callsign = output_name.split('_')[1]
        radio = '_'.join(output_name.split('_')[2:4])
        freq = output_name.split('_')[4]

        list_of_sounds = ['empty'] + [str(char).lower() for char in callsign] + [str(char).lower() for char in callsign] + ['radio'] + [radio.lower()] + ['frequency'] +  [str(char).lower().replace('.', 'point') for char in freq]
        files_to_concat = [self.sound_path + sound + '.wav' for sound in list_of_sounds]

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
