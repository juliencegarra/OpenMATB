# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from string import ascii_uppercase, digits, ascii_lowercase
from random import randint, uniform, choice
from math import copysign
from rstr import xeger
from pathlib import Path
from pyglet.media import Player, SourceGroup, load
from plugins.abstract import AbstractPlugin
from core.widgets import Radio, Simpletext
from core import Container
from core.constants import PATHS as P, COLORS as C


class Communications(AbstractPlugin):
    def __init__(self, window, taskplacement='bottomleft', taskupdatetime=80):
        super().__init__(window, taskplacement, taskupdatetime)
        
        self.keys.extend(['UP', 'DOWN', 'RIGHT', 'LEFT', 'ENTER'])
        
        self.change_radio = dict(UP=-1, DOWN=1)   
        self.letters, self.digits = ascii_uppercase, digits
        
        # Callsign regex must be defined first because it is needed by self.get_callsign()
        self.parameters['callsignregex']='[A-Z][A-Z][A-Z]\d\d\d'
        self.old_regex = str(self.parameters['callsignregex'])
        new_par = dict(owncallsign=str(), othercallsign=list(), othercallsignnumber=5, 
                       airbandminMhz=108.0, airbandmaxMhz=137.0, airbandminvariationMhz=5, 
                       airbandmaxvariationMhz=6, voicegender='female', voiceidiom='french',
                       radioprompt=str(), maxresponsedelay=20000, 
                       promptlist=['NAV_1', 'NAV_2', 'COM_1', 'COM_2'], automaticsolver=False, 
                       displayautomationstate=True, feedbackduration=1500,
                       feedbacks=dict(positive=dict(active=False, color=C['GREEN']),
                                      negative=dict(active=False, color=C['RED'])))
                                      
        self.parameters.update(new_par)
        self.regenerate_callsigns()


        
        # Handle OWN radios information       
        self.parameters['radios'] = dict()
        for r, this_radio in enumerate(self.parameters['promptlist']):
            self.parameters['radios'][r] = {'name': this_radio, 'currentfreq': self.get_rand_frequency(),
                                            'targetfreq': None, 'pos': r, 'response_time': 0,
                                            'is_active': False, 'is_prompting':False,
                                            '_feedbacktimer': None, '_feedbacktype':None}
        self.lastradioselected = None
        self.frequency_modulation = 0.1

        self.sound_path = P['SOUNDS'].joinpath(self.parameters['voiceidiom'],
                                               self.parameters['voicegender'])
        self.samples_path = [self.sound_path.joinpath(f'{i}.wav') 
                             for i in [s for s in digits + ascii_lowercase] + 
                             [this_radio.lower() for this_radio in self.parameters['promptlist']] + 
                             ['radio', 'point', 'frequency']]
        
        for sample_needed in self.samples_path:
            if not sample_needed.exists():
                print(sample_needed, _(' does not exist'))
        
        self.player = Player()
        self.automode_position = (0.5, 0.2)
    

    def regenerate_callsigns(self):
        self.parameters['owncallsign'] = self.get_callsign()
        for i in range(self.parameters['othercallsignnumber']):
            this_callsign = self.get_callsign()
            while this_callsign in [self.parameters['owncallsign']] + \
                                    self.parameters['othercallsign']:
                this_callsign = self.get_callsign()
            self.parameters['othercallsign'].append(this_callsign)

    
    def create_widgets(self):
        super().create_widgets()
        self.add_widget('callsign', Simpletext, container=self.task_container,
                       text=_('Callsign \t\t %s') % self.parameters['owncallsign'], y=0.9)
        
        active_index = randint(0, len(self.parameters['radios'])-1)
        for pos, radio in self.parameters['radios'].items():
            radio['is_active'] = pos==active_index
            # Compute radio container            
            radio_container = Container(radio['name'], self.task_container.l, 
                                       self.task_container.b + self.task_container.h * (0.7 - 0.13 * pos),
                                       self.task_container.w, self.task_container.h * 0.1)
            
            radio['widget'] = self.add_widget(f"radio_{radio['name']}", Radio, 
                                             container=radio_container, label=radio['name'],
                                             frequency=radio['currentfreq'], on=radio['is_active'])
    
    
    def get_averaged_prompt_duration(self, n=1000):
        durations = list()
        for i in range(n):
            # Alternate between the various radio possible names
            radio_name = self.parameters['promptlist'][i%len(self.parameters['promptlist'])]
            callsign = self.get_callsign()  # Generate randoms callsigns based on the regex
            random_frequency = self.get_rand_frequency()
            sound_group = self.group_audio_files(callsign, radio_name, random_frequency)
            durations.append(sound_group.duration)
        return sum(durations)/n
            
                           
    def get_callsign(self):
        call_rgx = self.parameters['callsignregex']
        duplicateChar, notInList= True, True

        self.letters = ascii_uppercase if len(self.letters) < 3 else self.letters
        self.digits = digits if len(self.digits) < 3 else self.digits
            
        while duplicateChar or notInList:
            callsign = xeger(call_rgx)
            duplicateChar = False if len(callsign) == len(set(callsign)) else True
            notInList = any([s not in self.letters + self.digits for s in callsign])

        for s in callsign:
            for li in [self.letters, self.digits]:
                if s in li:
                    li = li.replace(s, '')
        return callsign
        
    
    def group_audio_files(self, callsign, radio_name, freq):
        list_of_sounds = ['empty']*20 + [c.lower() for c in callsign] + [c.lower() for c in callsign] + ['radio'] \
                          + [radio_name.lower()] + ['frequency'] + [c.lower().replace('.', 'point')
                                                                    for c in str(freq)] + ['empty']
        
        group = SourceGroup()
        for f in list_of_sounds:
            source = load(str(self.sound_path.joinpath(f'{f}.wav')), streaming=False)
            group.add(source)
        return group
    
    
    def prompt_for_a_new_target(self, destination, radio_name):
        self.parameters['radioprompt'] = ''
        radio = [r for i, r in self.parameters['radios'].items() if r['name'] == radio_name][0]
        
        callsign = self.parameters[f'{destination}callsign']
        callsign = choice(callsign) if isinstance(callsign, list) else callsign
        
        random_frequency = self.get_rand_frequency()
        while not (self.parameters['airbandminvariationMhz'] < 
                   abs(random_frequency - radio['currentfreq']) <
                   self.parameters['airbandmaxvariationMhz']):
            random_frequency = self.get_rand_frequency()
        
        if destination == 'own':
            radio['targetfreq'] = random_frequency
            radio['is_prompting'] = True
        
        sound_group = self.group_audio_files(callsign, radio_name, random_frequency)
        self.player.queue(sound_group)

        # Play immediately the sound_group, even if the player is already playing
        if self.player.playing:
            self.player.next_source()
        else:
            self.player.play()
    
    
    def get_rand_frequency(self):
        return round(uniform(float(self.parameters['airbandminMhz']),
                             float(self.parameters['airbandmaxMhz'])), 1)
    
    
    def get_target_radios_list(self):
        # Multiple radios can have a target frequency at the same time
        # because of a potential delay in reactions
        return [r for _, r in self.parameters['radios'].items() if r['targetfreq'] is not None]
    
    
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
            
    
    def get_response_timers(self):
        return [r['response_time'] for _, r in self.parameters['radios'].items() 
                if r['response_time'] > 0]
                
                
    def get_waiting_response_radios(self):
        '''A radio is waiting a response when it specifies a target and its prompting message
           is over'''
        
        return [r for _, r in self.parameters['radios'].items() 
                if r in self.get_target_radios_list()
                and r['is_prompting'] == False]
    
        
    def get_max_pos(self):
        return max([r['pos'] for k, r in self.parameters['radios'].items()])
    
    
    def get_min_pos(self):
        return min([r['pos'] for k, r in self.parameters['radios'].items()])
        
        
    def modulate_frequency(self):
        if self.is_key_state('LEFT', True):
            self.get_active_radio_dict()['currentfreq'] -= self.frequency_modulation
        elif self.is_key_state('RIGHT', True):
            self.get_active_radio_dict()['currentfreq'] += self.frequency_modulation
    
    
    def compute_next_plugin_state(self):
        if super().compute_next_plugin_state() == 0:
            return

        if self.parameters['callsignregex'] != self.old_regex:
            self.regenerate_callsigns()
            self.old_regex = str(self.parameters['callsignregex'])
        
        if self.parameters['radioprompt'].lower() in ['own', 'other']:
            while True:
                selected_radio = choice(self.parameters['promptlist'])
                if selected_radio != self.lastradioselected:
                    break
            
            self.lastradioselected = str(selected_radio)
            self.prompt_for_a_new_target(self.parameters['radioprompt'].lower(), selected_radio)
        
        if self.can_receive_keys == True:
            self.modulate_frequency()
        
        # If a target is defined + auditory prompt has ended
        # response can occur, so increment response_time
        target_radios =  self.get_target_radios_list()
        active = self.get_active_radio_dict()
        
        # Browse targeted radios
        for radio in target_radios:
            # Increment response time as soon as auditory prompting has ended
            if radio['is_prompting'] == False:
                radio['response_time'] += self.parameters['taskupdatetime']
                
                # Record potential target miss
                if radio['response_time'] >= self.parameters['maxresponsedelay']:
                    self.record_target_missing(radio)
                    
            elif self.player.source is None:  # If the radio prompt has just ended
                radio['is_prompting'] = False
                
            
        # If multiple radios must be modified
        # The automatic solver sticks to the first one (until it is tuned)
        if self.parameters['automaticsolver'] is True:
            waiting_radios = self.get_waiting_response_radios()
            
            # Only if a radio is waiting autosolving, do it
            if len(waiting_radios) > 0:
                autoradio = waiting_radios[0]
                
                if active != autoradio:  # Automatic radio switch if needed
                    active['is_active'] = False
                    current_index, target_index = (active['pos'], autoradio['pos'])
                    new_index = current_index + copysign(1, target_index - current_index)
                    self.get_radio_dict_by_pos(new_index)['is_active'] = True

                # Automatic radio tune
                elif active['targetfreq'] != active['currentfreq']:
                    active['currentfreq'] = round(active['currentfreq'] + 
                                                  copysign(0.1, active['targetfreq'] 
                                                           - active['currentfreq']), 1)
                else:
                    self.confirm_response()  # Emulate a response confirmation
        
        active['currentfreq'] = self.keep_value_between(active['currentfreq'],
                                                        up=self.parameters['airbandmaxMhz'],
                                                        down=self.parameters['airbandminMhz'])
        
        # Feedback handling
        for r, radio in self.parameters['radios'].items():
            if radio['_feedbacktimer'] is not None:
                radio['_feedbacktimer'] -= self.parameters['taskupdatetime']
                if radio['_feedbacktimer'] <= 0:
                    radio['_feedbacktimer'] = None
                    radio['_feedbacktype'] = None
    
    
    def refresh_widgets(self):
        if super().refresh_widgets() == 0:
            return

        self.widgets['communications_callsign'].set_text(self.parameters['owncallsign'])
        
        # Move arrow to active radio
        for _, radio in self.parameters['radios'].items():
            if not radio['is_active'] and radio['widget'].is_selected:
                radio['widget'].hide_arrows()
            elif radio['is_active'] and not radio['widget'].is_selected:
                radio['widget'].show_arrows()
        
        # Propagate current frequency value to the widgets
        active = self.get_active_radio_dict()
        active['widget'].set_frequency_text(active['currentfreq'])
        
        # Check a need for feedback refreshing
        for r, radio in self.parameters['radios'].items():
            if radio['_feedbacktimer'] is not None:
                color = self.parameters['feedbacks'][radio['_feedbacktype']]['color']                
            else:
                color = C['BACKGROUND']
            radio['widget'].set_feedback_color(color)
        
                            
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
        
        self.disable_radio_target(target_radio)
        
        self.set_feedback(target_radio, ft='negative')
    
    
    def confirm_response(self):
        '''Evaluate response performance and log it'''
        
        # Retrieve the responded radio and the target radios
        responded_radio = self.get_active_radio_dict()
        waiting_radios = self.get_waiting_response_radios()
        
        # Check if there was a target to be responded to
        response_needed = True if len(waiting_radios) > 0 else False
        
        # Check if the responded radio was prompting (good radio)
        good_radio = responded_radio in waiting_radios if len(waiting_radios) else float('nan')
        
        # If a target radio is responded, get it to compute response deviation and time
        # If not, get the target radio only if it is single
        # (if there were two target radios simultaneously, we can't decide which to select
        #  to compute deviation and response time with the uncorrect responded radio)
        if responded_radio in waiting_radios:
            measure_radio = responded_radio
        elif len(waiting_radios) == 1:
            measure_radio = waiting_radios[0]
        else:
            measure_radio = None
        
        # Now compute
        if measure_radio is not None:
            target_frequency = measure_radio['targetfreq']
            target_radio_name = measure_radio['name']
            deviation = responded_radio['currentfreq'] - target_frequency
            rt = measure_radio['response_time']
        else:
            deviation = rt = target_frequency = target_radio_name = float('nan')
        
        if good_radio == True:
            self.disable_radio_target(responded_radio)
        
        self.log_performance('response_was_needed', response_needed)
        self.log_performance('target_radio', target_radio_name)
        self.log_performance('responded_radio', responded_radio['name'])
        self.log_performance('target_frequency', target_frequency)
        self.log_performance('responded_frequency', responded_radio['currentfreq'])
        self.log_performance('correct_radio', good_radio)
        self.log_performance('response_deviation', round(deviation, 1))
        self.log_performance('response_time', rt)
        
        # Response is good if both radio and frequency are correct
        if not response_needed:
            self.set_feedback(responded_radio, ft='negative')
        else:
            if good_radio == True and round(deviation, 1) == 0:                
                self.set_feedback(responded_radio, ft='positive')
            else:
                self.set_feedback(responded_radio, ft='negative')
                
    
    def set_feedback(self, radio, ft):
        # Set the feedback type and duration, if the gauge has got one
        # (the feedback widget is refreshed by the refresh_widget method)
        if self.parameters['feedbacks'][ft]['active']:
            radio['_feedbacktype'] = ft
            radio['_feedbacktimer'] = self.parameters['feedbackduration']
        
    
    def do_on_key(self, key, state):
        '''Check for radio change and frequency validation'''
        
        super().do_on_key(key, state)
        if key is None:
            return
            
        if state == 'press':
            if key in self.change_radio.keys():  # Change radio
                next_active_n = self.keep_value_between(self.get_active_radio_dict()['pos']  
                                                        + self.change_radio[key], 
                                                        down=self.get_min_pos(), up=self.get_max_pos())
                
                self.get_active_radio_dict()['is_active'] = False
                self.get_radio_dict_by_pos(next_active_n)['is_active'] = True
                
            elif key == 'ENTER':
                self.confirm_response()            
