import time
import wave
import pyglet
import os
import random
import threading
from string import ascii_uppercase, digits, ascii_lowercase
from math import copysign
from pathlib import Path
from pyglet.media import Player, SourceGroup, load
from plugins.abstractplugin import AbstractPlugin
from core.widgets import Radio, Simpletext
from core.container import Container
from core.constants import PATHS as P, COLORS as C, REPLAY_MODE
from core.pseudorandom import randint, uniform, choice, xeger
from core.utils import get_conf_value
from core import validation
import csv
from datetime import datetime

try:
    import pyaudio
except ImportError:
    pyaudio = None

class JoystickRecordingTest:
    """
    Handles joystick button press/release to start/stop recording audio via PyAudio.
    Uses a callback-based stream so that audio is captured asynchronously even when joystick events are processed.
    Plays rogerthat.wav upon release.
    """

    def __init__(self):
        self.enabled = pyaudio is not None
        self.is_recording = False
        self.audio_stream = None
        self.audio_frames = []
        self.record_button_index = 0  # Joystick button to trigger recording

        if not self.enabled:
            self.joystick = None
            self.p = None
            self.ack_sound = None
            return

        # Try to get the first joystick
        joysticks = pyglet.input.get_joysticks()
        if joysticks:
            self.joystick = joysticks[0]
            self.joystick.open()
            self.joystick.push_handlers(self)
        self.p = pyaudio.PyAudio()

        # Attempt to load rogerthat.wav once
        self.ack_sound = None
        try:
            sound_path = P['SOUNDS'].joinpath('english', 'male', 'rogerthat.wav')
            self.ack_sound = load(str(sound_path), streaming=False)
        except Exception as e:
            pass

    def on_joybutton_press(self, joystick, button):
        if button == self.record_button_index:
            self.start_recording()

    def on_joybutton_release(self, joystick, button):
        if button == self.record_button_index:
            self.stop_recording()

    def start_recording(self):
        if not self.enabled:
            return

        if self.is_recording:
            return

        device_info = self.p.get_default_input_device_info()
        self.recorded_sample_rate = int(device_info['defaultSampleRate'])
        self.audio_frames = []  # Reset the frame buffer
        self.is_recording = True

        def callback(in_data, frame_count, time_info, status_flags):
            if self.is_recording:
                self.audio_frames.append(in_data)
            return (None, pyaudio.paContinue)

        self.audio_stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.recorded_sample_rate,
            input=True,
            frames_per_buffer=1024,
            stream_callback=callback
        )
        self.audio_stream.start_stream()

    def stop_recording(self):
        if not self.enabled:
            return

        if not self.is_recording:
            return

        self.is_recording = False
        if self.audio_stream is not None:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        date_str = time.strftime("%Y-%m-%d")
        session_letter = "A"
        session_folder_name = date_str + session_letter

        session_folder = os.path.join('recordings', session_folder_name)
        filename = f"comm_{timestamp}.wav"
        file_path = os.path.join(session_folder, filename)

        os.makedirs(session_folder, exist_ok=True)

        try:
            self.write_wav_file(file_path, sample_rate=self.recorded_sample_rate, sample_width=2)
        except Exception as e:
            pass

        if self.ack_sound:
            self.ack_sound.play()

    def write_wav_file(self, filename, sample_rate=44100, sample_width=2):
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

    def update(self, dt):
        pass


class Communications(AbstractPlugin):
    def __init__(self, label='', taskplacement='bottomleft', taskupdatetime=100):
        super().__init__(_('Communications'), taskplacement, taskupdatetime)
        self.joystick_recorder = JoystickRecordingTest()
        self.validation_dict = {
            'owncallsign': validation.is_callsign,
            'othercallsign': validation.is_callsign_or_list_of,
            'voiceidiom': (validation.is_in_list, [p.name.lower() for p in P['SOUNDS'].iterdir()]),
            'voicegender': (validation.is_in_list, ['male', 'female']),
            'othercallsignnumber': validation.is_positive_integer,
            'airbandminMhz': validation.is_positive_float,
            'airbandmaxMhz': validation.is_positive_float,
            'airbandminvariationMhz': validation.is_positive_integer,
            'airbandmaxvariationMhz': validation.is_positive_integer,
            'radioprompt': (validation.is_in_list, ['own', 'other']),
            'promptlist': (validation.is_in_list, ['NAV_1', 'NAV_2', 'COM_1', 'COM_2']),
            'maxresponsedelay': validation.is_positive_integer,
            'callsignregex': validation.is_a_regex,
            'keys-selectradioup': validation.is_key,
            'keys-selectradiodown': validation.is_key,
            'keys-tunefrequencyup': validation.is_key,
            'keys-tunefrequencydown': validation.is_key,
            'keys-validateresponse': validation.is_key
        }
        self.log_filename = "comms_log.csv"
        self.keys = {'UP', 'DOWN', 'RIGHT', 'LEFT', 'ENTER', 'SPACE'}
        self.callsign_seed = 1
        self.letters, self.digits = ascii_uppercase, digits

        self.parameters['callsignregex'] = '[A-Z][A-Z][A-Z]\\d\\d\\d'
        self.old_regex = str(self.parameters['callsignregex'])
        new_par = dict(
            owncallsign=str(),
            othercallsign=[],
            othercallsignnumber=5,
            airbandminMhz=108.0,
            airbandmaxMhz=137.0,
            airbandminvariationMhz=5,
            airbandmaxvariationMhz=6,
            voicegender='male',
            voiceidiom='english',
            radioprompt=str(),
            maxresponsedelay=20000,
            promptlist=['NAV_1', 'NAV_2', 'COM_1', 'COM_2'],
            automaticsolver=False,
            displayautomationstate=True,
            feedbackduration=1500,
            feedbacks=dict(
                positive=dict(active=False, color=C['GREEN']),
                negative=dict(active=False, color=C['RED'])
            ),
            keys=dict(
                selectradioup='UP',
                selectradiodown='DOWN',
                tunefrequencyup='RIGHT',
                tunefrequencydown='LEFT',
                validateresponse='ENTER'
            )
        )
        self.parameters.update(new_par)
        self.regenerate_callsigns()

        self.parameters['radios'] = dict()
        for r, this_radio in enumerate(self.parameters['promptlist']):
            self.parameters['radios'][r] = {
                'name': this_radio,
                'currentfreq': self.get_rand_frequency(r),
                'targetfreq': None,
                'pos': r,
                'response_time': 0,
                'is_active': False,
                'is_prompting': False,
                '_feedbacktimer': None,
                '_feedbacktype': None
            }
        self.lastradioselected = None
        self.frequency_modulation = 0.1
        self.sound_path = None
        self.set_sample_sounds()
        self.automode_position = (0.5, 0.2)

    def get_sounds_path(self):
        return P['SOUNDS'].joinpath(self.parameters['voiceidiom'], self.parameters['voicegender'])

    def set_sample_sounds(self):
        new_path = self.get_sounds_path()
        if new_path == self.sound_path:
            return
        self.sound_path = new_path
        self.samples_path = [
            self.sound_path.joinpath(f'{i}.wav')
            for i in [s for s in digits + ascii_lowercase]
                     + [this_radio.lower() for this_radio in self.parameters['promptlist']]
                     + ['radio', 'point', 'frequency']
        ]
        for sample_needed in self.samples_path:
            if not sample_needed.exists():
                pass

    def regenerate_callsigns(self):
        self.parameters['owncallsign'] = self.get_callsign()
        self.parameters['othercallsign'] = []
        for i in range(self.parameters['othercallsignnumber']):
            this_callsign = self.get_callsign()
            while this_callsign in [self.parameters['owncallsign']] + self.parameters['othercallsign']:
                this_callsign = self.get_callsign()
            self.parameters['othercallsign'].append(this_callsign)

    def create_widgets(self):
        super().create_widgets()
        self.add_widget('callsign', Simpletext, container=self.task_container,
                        text=_('Callsign \t\t %s') % self.parameters['owncallsign'], y=0.9)
        active_index = randint(0, len(self.parameters['radios']) - 1, self.alias, self.scenario_time)
        for pos, radio in self.parameters['radios'].items():
            radio['is_active'] = (pos == active_index)
            radio_container = Container(
                radio['name'],
                self.task_container.l,
                self.task_container.b + self.task_container.h * (0.7 - 0.13 * pos),
                self.task_container.w,
                self.task_container.h * 0.1
            )
            radio['widget'] = self.add_widget(
                f"radio_{radio['name']}", Radio,
                container=radio_container,
                label=radio['name'],
                frequency=radio['currentfreq'],
                on=radio['is_active']
            )

    def get_callsign(self):
        self.callsign_seed += 1
        call_rgx = self.parameters['callsignregex']
        duplicateChar, notInList = True, True
        self.letters = ascii_uppercase if len(self.letters) < 3 else self.letters
        self.digits = digits if len(self.digits) < 3 else self.digits
        while duplicateChar or notInList:
            callsign = xeger(call_rgx, self.alias, self.scenario_time, self.callsign_seed)
            duplicateChar = (len(callsign) != len(set(callsign)))
            notInList = any([s not in self.letters + self.digits for s in callsign])
            self.callsign_seed += 1
        for s in callsign:
            for li in [self.letters, self.digits]:
                if s in li:
                    li = li.replace(s, '')
        return callsign

    def group_audio_files(self, callsign, radio_name, freq):
        list_of_sounds = (
            ['empty'] * 20 +
            [c.lower() for c in callsign] +
            ['radio'] +
            [radio_name.lower()] +
            ['frequency'] +
            ['empty']
        )
        group = SourceGroup()
        for f in list_of_sounds:
            source = load(str(self.sound_path.joinpath(f'{f}.wav')), streaming=False)
            group.add(source)
        return group

    def prompt_for_a_new_target(self, destination, radio_name):
        radio = self.get_radios_by_key_value('name', radio_name)[0]
        radio_n = self.get_radios_number_by_key_value('name', radio_name)[0]

        callsign = self.parameters[f'{destination}callsign']
        if isinstance(callsign, list):
            callsign = choice(callsign, self.alias, self.scenario_time, radio_n)
        if destination == 'own':
            radio['targetfreq'] = self.get_rand_frequency(radio_n)
            radio['is_prompting'] = True

        participant_raw = str(get_conf_value("Openmatb", "participant_id")).strip()
        participant_label = f"participant_{participant_raw}" if participant_raw else "participant_unknown"
        scenario_rel_path = str(get_conf_value("Openmatb", "scenario_path")).strip()
        block_stem = Path(scenario_rel_path).stem if scenario_rel_path else "unknown_block"

        log_dir = Path("sessions").joinpath(participant_label)
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_filename = str(log_dir.joinpath(f"{participant_raw}_{block_stem}_comms_log.csv"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([now, destination, radio_name, callsign, radio['currentfreq']])
        print("DEBUG: CSV logging completed for prompt")

        sound_group = self.group_audio_files(callsign, radio_name, radio['targetfreq'])
        self.player = Player()
        self.player.queue(sound_group)
        self.player.play()
        prompt_timeout = 5  # seconds, adjust as needed
        pyglet.clock.schedule_once(lambda dt: self.check_and_reset_prompt(radio), prompt_timeout)

    def get_rand_frequency(self, radio_n):
        freq = round(
            uniform(
                float(self.parameters['airbandminMhz']),
                float(self.parameters['airbandmaxMhz']),
                self.alias,
                self.scenario_time,
                radio_n
            ),
            1
        )
        return freq

    def get_target_radios_list(self):
        return [r for _, r in self.parameters['radios'].items() if r['targetfreq'] is not None]

    def get_non_target_radios_list(self):
        return [r for _, r in self.parameters['radios'].items() if r['targetfreq'] is None]

    def get_active_radio_dict(self):
        radio = self.get_radios_by_key_value('is_active', True)
        if radio is not None:
            return radio[0]

    def get_radio_dict_by_pos(self, pos):
        radio = self.get_radios_by_key_value('pos', pos)
        if radio is not None:
            return radio[0]

    def get_radios_by_key_value(self, k, v):
        radio_list = [r for _, r in self.parameters['radios'].items() if r[k] == v]
        if len(radio_list) > 0:
            return radio_list

    def get_radios_number_by_key_value(self, k, v):
        num_list = [i for i, r in self.parameters['radios'].items() if r[k] == v]
        if len(num_list) > 0:
            return num_list

    def get_response_timers(self):
        return [r['response_time'] for _, r in self.parameters['radios'].items() if r['response_time'] > 0]

    def get_waiting_response_radios(self):
        return [r for _, r in self.parameters['radios'].items()
                if r in self.get_target_radios_list() and r['is_prompting'] == False]

    def get_max_pos(self):
        return max(r['pos'] for r in self.parameters['radios'].values())

    def get_min_pos(self):
        return min(r['pos'] for r in self.parameters['radios'].values())

    def modulate_frequency(self):
        pass

    def compute_next_plugin_state(self):
        if self.parameters['callsignregex'] != self.old_regex:
            self.regenerate_callsigns()
            self.old_regex = str(self.parameters['callsignregex'])
        self.set_sample_sounds()
        if self.parameters['radioprompt'].lower() in ['own', 'other']:
            next_destination = self.parameters['radioprompt'].lower()
            self.parameters['radioprompt'] = ''
            prompting_radio_list = self.get_radios_by_key_value('is_prompting', True)
            if prompting_radio_list and hasattr(self, 'player'):
                self.player.pause()
                del self.player
                prompting_radio = prompting_radio_list[0]
                prompting_radio['is_prompting'] = False
            pyglet.clock.schedule_once(self.schedule_prompt_with_randomize, 2, next_destination)
        if self.parameters['automaticsolver'] is True and REPLAY_MODE == False:
            waiting_radios = self.get_waiting_response_radios()
            if len(waiting_radios) > 0:
                autoradio = waiting_radios[0]
                active = self.get_active_radio_dict()
                if active != autoradio:
                    active['is_active'] = False
                    current_index, target_index = (active['pos'], autoradio['pos'])
                    new_index = current_index + copysign(1, target_index - current_index)
                    self.get_radio_dict_by_pos(new_index)['is_active'] = True
                elif active['targetfreq'] != active['currentfreq']:
                    active['currentfreq'] = round(
                        active['currentfreq'] + copysign(0.1, active['targetfreq'] - active['currentfreq']),
                        1
                    )
                else:
                    self.confirm_response()
        if self.get_active_radio_dict():
            active = self.get_active_radio_dict()
            active['currentfreq'] = self.keep_value_between(
                active['currentfreq'],
                up=self.parameters['airbandmaxMhz'],
                down=self.parameters['airbandminMhz']
            )

    def disable_radio_target(self, radio):
        radio['response_time'] = 0
        radio['targetfreq'] = None

    def record_target_missing(self, target_radio):
        self.log_performance('target_radio', target_radio['name'])
        self.log_performance('target_frequency', target_radio['targetfreq'])
        self.log_performance('response_was_needed', True)
        self.log_performance('responded_radio', float('nan'))
        self.log_performance('responded_frequency', float('nan'))
        self.log_performance('correct_radio', False)
        self.log_performance('response_deviation', float('nan'))
        self.log_performance('response_time', float('nan'))
        self.log_performance('sdt_value', 'MISS')
        self.disable_radio_target(target_radio)
        self.set_feedback(target_radio, ft='negative')

    def get_sdt_value(self, response_needed, was_a_radio_responded, correct_radio, response_deviation):
        if not response_needed:
            return 'FA'
        elif was_a_radio_responded is False:
            return 'MISS'
        elif correct_radio and response_deviation == 0:
            return 'HIT'
        elif correct_radio is False and response_deviation == 0:
            return 'BAD_RADIO'
        elif response_deviation != 0 and correct_radio:
            return 'BAD_FREQ'
        elif correct_radio is False and response_deviation != 0:
            return 'BAD_RADIO_FREQ'

    def confirm_response(self):
        responded_radio = self.get_active_radio_dict()
        waiting_radios = self.get_waiting_response_radios()
        response_needed = (len(waiting_radios) > 0)
        good_radio = responded_radio in waiting_radios if waiting_radios else float('nan')
        if responded_radio in waiting_radios:
            measure_radio = responded_radio
        elif len(waiting_radios) == 1:
            measure_radio = waiting_radios[0]
        else:
            measure_radio = None
        if measure_radio is not None:
            target_frequency = measure_radio['targetfreq']
            target_radio_name = measure_radio['name']
            deviation = round(responded_radio['currentfreq'] - target_frequency, 1)
            rt = measure_radio['response_time']
        else:
            deviation = rt = target_frequency = target_radio_name = float('nan')
        sdt = self.get_sdt_value(response_needed, True, good_radio, deviation)
        self.log_performance('response_was_needed', response_needed)
        self.log_performance('target_radio', target_radio_name)
        self.log_performance('responded_radio', responded_radio['name'])
        self.log_performance('target_frequency', target_frequency)
        self.log_performance('responded_frequency', responded_radio['currentfreq'])
        self.log_performance('correct_radio', good_radio)
        self.log_performance('response_deviation', deviation)
        self.log_performance('response_time', rt)
        self.log_performance('sdt_value', sdt)
        if not response_needed:
            self.set_feedback(responded_radio, ft='negative')
        else:
            if good_radio == True and deviation == 0:
                self.disable_radio_target(responded_radio)
                self.set_feedback(responded_radio, ft='positive')
            else:
                self.set_feedback(responded_radio, ft='negative')

    def set_feedback(self, radio, ft):
        if self.parameters['feedbacks'][ft]['active']:
            radio['_feedbacktype'] = ft
            radio['_feedbacktimer'] = self.parameters['feedbackduration']

    def do_on_key(self, key, state, emulate):
        key = super().do_on_key(key, state, emulate)
        if key is None:
            return
        if str(key).upper() == 'SPACE':
            if state == 'press':
                self.joystick_recorder.start_recording()
            elif state == 'release':
                self.joystick_recorder.stop_recording()
            return key
        if state == 'press':
            if key in self.change_radio.keys():
                next_active_n = self.keep_value_between(
                    self.get_active_radio_dict()['pos'] + self.change_radio[key],
                    down=self.get_min_pos(),
                    up=self.get_max_pos()
                )
                self.get_active_radio_dict()['is_active'] = False
                self.get_radio_dict_by_pos(next_active_n)['is_active'] = True
            elif key == 'ENTER':
                self.confirm_response()
        return key

    def schedule_prompt_with_randomize(self, dt, destination):
        if hasattr(self, 'prompt_scheduled') and self.prompt_scheduled:
            return
        self.prompt_scheduled = True
        used_frequencies = set()
        for _, radio in self.parameters['radios'].items():
            freq = round(random.uniform(108.0, 138.0), 1)
            while freq in used_frequencies:
                freq = round(random.uniform(108.0, 138.0), 1)
            used_frequencies.add(freq)
            radio['currentfreq'] = freq
        if destination == 'own':
            non_target_radios = self.get_non_target_radios_list()
            if len(non_target_radios) == 0:
                for _, radio in self.parameters['radios'].items():
                    self.reset_radio_state(radio, reason="stale prompt")
                non_target_radios = self.get_non_target_radios_list()
            if non_target_radios:
                radio_choice = choice(non_target_radios, self.alias, self.scenario_time)
                radio_name_to_prompt = radio_choice['name']
            else:
                radio_name_to_prompt = None
        else:
            radio_name_to_prompt = choice(self.parameters['promptlist'], self.alias, self.scenario_time)
        if radio_name_to_prompt is not None:
            self.prompt_for_a_new_target(destination, radio_name_to_prompt)
        self.prompt_scheduled = False

    def refresh_widgets(self):
        if not super().refresh_widgets():
            return
        self.widgets['communications_callsign'].set_text(self.parameters['owncallsign'])
        for _, radio in self.parameters['radios'].items():
            radio['widget'].set_frequency_text(radio['currentfreq'])
            if radio['_feedbacktimer'] is not None:
                color = self.parameters['feedbacks'][radio['_feedbacktype']]['color']
            else:
                color = C['BACKGROUND']
            radio['widget'].set_feedback_color(color)

    def reset_radio_state(self, radio, reason="timeout"):
        radio['targetfreq'] = None
        radio['is_prompting'] = False
        radio['response_time'] = 0

    def check_and_reset_prompt(self, radio):
        if radio['is_prompting']:
            self.reset_radio_state(radio, reason="no response timeout")
