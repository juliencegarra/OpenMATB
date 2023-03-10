import re
from pyglet.window import key as winkey
from core.constants import COLORS as C, PATHS as P
from core import logger
from core.dialog import fatalerror
import plugins

DEPRECATED = ['pumpstatus', 'end', 'cutofffrequency', 'equalproportions'] # Ignore these arguments

class Event:
    sep = ';'


    def __init__(self, line_id, time_sec, plugin, command):
        self.line = int(line_id)
        self.time_sec = time_sec
        self.plugin = plugin
        self.command = [command] if not isinstance(command, list) else command
        self.done = False
        self.line_str = self.get_line_str()


    @classmethod
    def parse_from_string(cls, line_id, line_str):
        time_str, plugin, *command = line_str.strip().split(cls.sep)
        h, m, s = time_str.split(':')
        time_sec = int(h) * 3600 + int(m) * 60 + int(s)
        return cls(line_id, time_sec, plugin, command)


    def __repr__(self):
        return f'Event({self.line}, {self.time_sec}, {self.plugin}, {self.command})'

    def __str__(self):
        return f'l.{self.line} > {self.get_line_str()}'

    def __len__(self):
        return len(self.command)


    def get_line_str(self):
        return f'{self.get_time_hms_str()}{self.sep}{self.plugin}{self.sep}{self.get_command_str()}'


    def get_time_hms_str(self):
        seconds = int(self.time_sec)
        hours = seconds // (60*60)
        seconds %= (60*60)
        minutes = seconds // 60
        seconds %= 60
        return "%01i:%02i:%02i" % (hours, minutes, seconds)


    def get_command_str(self):
        if len(self) == 1:
            return self.command[0]
        elif len(self) == 2:
            return f'{self.command[0]}{self.sep}{self.command[1]}'


    def is_deprecated(self) -> bool:
        return self.plugin in DEPRECATED or (len(self.command) > 0 and self.command[0] in DEPRECATED)


class Scenario:
    '''
    This object converts scenario to Events, loads the corresponding plugins,
    and checks that some criteria are met (e.g., acceptable values)
    '''

    def __init__(self, scenario_path, window):
        if scenario_path.exists():
            contents = open(scenario_path, 'r').readlines()
        else:
            fatalerror(_('%s was not found') % str(scenario_path))

        self.path = scenario_path
        logger.log_manual_entry(self.path, key='scenario_path')

        # Convert the scenario file into a list of events #
        # (Squeeze empty and commented [#] lines)
        self.events = [Event.parse_from_string(line_n, line_str) for line_n, line_str
                       in enumerate(contents)
                       if len(line_str.strip()) > 0 and not line_str.startswith("#")]

        # Next load the scheduled plugins into the class, so we can check potential errors
        # But first, check that only available plugins are mentioned
        for event in self.events:
            if not hasattr(globals()['plugins'], event.plugin.capitalize()):
                fatalerror(_('Scenario error: %s is not a valid plugin name (l. %s)') % (event.plugin, event.line))

        self.plugins = {name: getattr(globals()['plugins'], name.capitalize())(window)
                        for name in self.get_plugins_name_list()}


        self.events = self.events_retrocompatibility() # Apply retrocompatiblity to events
        errors = self.check_events()   # Check that events are properly expressed

        errorf = open(P['SCENARIO_ERRORS'],'w')
        if len(errors) > 0:
            for this_error in errors:
                print(this_error, file=errorf)
        else:
            print(_('No error'), file=errorf)
        errorf.close()

        if len(errors) > 0:
            fatalerror(_(f"There were some errors in the scenario. See the %s file.") % P['SCENARIO_ERRORS'].name)


    def events_retrocompatibility(self):
        new_list = list()
        for n, e in enumerate(self.events):

            # If plugin or command is DEPRECATED, ignore the event
            if e.is_deprecated():
                pass    # TODO: Raise a deprecation warning

            # For parameters
            # SYSMON now manages failures with two separated variables
            elif len(e) == 2 and 'scales' in e.command[0] and 'failure' in e.command[0] \
                    and e.command[1] in ['up', 'down']:
                sysmon_dict = dict(up='1', down='-1')
                command_1 = [e.command[0], 'True']
                command_2 = [e.command[0].replace('failure', 'side'), sysmon_dict[e.command[1]]]
                new_list.append(Event(e.line, e.time_sec, e.plugin, command_1))
                new_list.append(Event(e.line, e.time_sec, e.plugin, command_2))

            # If no retrocompatibility to apply, just append the event
            else:
                new_list.append(e)
        return new_list


    def get_parameters_value(self, plugin, command):
        current_level = self.plugins[plugin].parameters
        parameter_address = command[0].split('-')

        for entry in parameter_address:  # Is this parameter existing ?
            if current_level is not None and entry in current_level:
                if isinstance(current_level[entry], dict):
                    current_level = current_level[entry]
            else:  # Not entry found, try to resolve retrocompatiblity issue
                current_level = None

        if current_level is None:
            return None, False
        else:
            return current_level[parameter_address[-1]], True


    def try_retrocompatibility(self, plugin, command):
        try:
            command[0] = retro[command[0]]
        except KeyError:
            return None, None
        else:
            return self.get_parameters_value(plugin, command)


    def get_plugin_methods(self, plugin):
        return [f for f in dir(self.plugins[plugin]) if callable(getattr(self.plugins[plugin], f))]


    def get_plugin_events(self, plugin_name):
        return [e for e in self.events if e.plugin == plugin_name]


    def check_events(self):
        errors = list()

        # Rule 1 - all the mentioned plugins should have a start and a stop commands
        # Only non-blocking plugins must have a stop command
        for plug_name in self.get_plugins_name_list():
            if not any(['start' in e.command for e in self.get_plugin_events(plug_name)]):
                errors.append(_('The (%s) plugin does not have a start command.') % plug_name)

            if self.plugins[plug_name].blocking is False:
                if not any(['stop' in e.command for e in self.get_plugin_events(plug_name)]):
                    errors.append(_('The (%s) plugin does not have a stop command.') % plug_name)

        # Rule 1 bis - As for the blocking plugins, they should have their input file
        # defined before they start (check that each start command is preceeded by filename information)
        ## TODO

        for e in self.events:
            # Rule 2 - all events should trigger a command to a plugin
            if len(e) == 0:
                errors.append(_('Error on line %s. This event does not trigger any command.') % e.line)

            # Rule 2 bis - maximum length of a command is 2 (parameter;value)
            elif len(e) > 2:
                errors.append(_('Error on line %s. Maximum length of an event is 2'
                                ' (parameter;value).') % e.line)

            # Rule 3 - when present, a command should match either a plugin method or
            # a parameter, the value of the latter being acceptable
            elif len(e) == 1:  # Method expected
                if e.command[0] not in self.get_plugin_methods(e.plugin):
                    errors.append(_('Error on line %s. Method (%s) is not available for the plugin'
                                    ' (%s)') % (e.line, e.command[0], e.plugin))

            elif len(e) == 2:  # Parameter expected
                new_value = None
                current_value, exists = self.get_parameters_value(e.plugin, e.command)

                # If the current parameter exists in the plugin
                if exists == True:
                    method_args = None

                    # Check that the parameter has a verification method
                    # Else trigger a warning (should not happen)
                    if e.command[0] in validation_dict:
                        eval_method = validation_dict[e.command[0]]
                    else:
                        eval_method = None
                        errors.append(_('Warning on line %s. Parameter (%s) has no verification'
                                        ' method') % (e.line, e.command[0]))

                    if eval_method is not None:
                        if isinstance(eval_method, tuple):
                            # Method-args will receive extra arguments
                            eval_method, *method_args = eval_method

                        # Remove potential blank spaces in the command argument
                        # (except is the eval_method is waiting for a string, like title)
                        if eval_method.__name__ != 'is_string':
                            e.command[1] = e.command[1].replace(' ', '')

                        # ...extra arguments are unpacked here if present
                        method_args = (e.command[1], *method_args) if method_args is not None else (e.command[1],)
                        eval_value, error = eval_method(*method_args)

                        if error is not None:
                            preamble = _('Error on line %s. %s ') % (e.line, e.command[0])
                            error_msg = preamble + error
                            errors.append(error_msg)
                        else:
                            # If no error, replace the event value by its evaluated version
                            e.command[1] = eval_value
                else:
                    errors.append(_('Error on line %s. The %s plugin does not have a %s parameter')
                                    % (e.line, e.plugin, e.command[-2]))
        return errors

    def get_plugins_name_list(self):
        return set([e.plugin for e in self.events if e.plugin not in DEPRECATED])


#JC : tout ce qui suit à déplacer dans un helper à part   ou alors creer un fichier event.py avec toute la partie vérification également

# VERIFICATION METHODS
# The following methods, associated with the valid_type dictionary, allows to check that
# each scenario parameter value is accepted.

def is_string(x):
    # Should always be True as we are reading parameters from a text file
    # If a simple string is accepted, hence any input should be correct
    if isinstance(x, str):
        return x, None
    else:
        return None, _('should be a string (not %s).') % x


def is_natural_integer(x):
    msg = _('should be a natural (0 included) integer (not %s).') % x
    try:
        x = eval(x)
        x = int(x)
    except:
        return None, msg
    else:
        if x >= 0:
            return x, None
        else:
            return None, msg


def is_positive_integer(x):
    if is_natural_integer(x)[0] is not None and int(eval(x)) > 0:
        return eval(x), None
    else:
        return None, _('should be a positive (0 excluded) integer (not %s).') % x


def is_boolean(x):
    if x.capitalize() in ['True', 'False']:
        return eval(x.capitalize()), None
    else:
        return None, _('should be a boolean (not %s).') % x


def is_color(x):  # Can be an hexadecimal value, a constant name, or an RGBa value
    m = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', x)
    if m is not None:
        x = x.lstrip('#')
        rgba = list(int(x[i:i + 2], 16) for i in (0, 2, 4))
        rgba.append(255)
        return rgba, None
    elif x in list(C.keys()):
        return C[x], None
    else:
        try:
            x = eval(x)
        except:
            return None, _('must be (R,G,B,a) or hexadecimal (e.g., #00ff00) values (not %s)') % x
        else:
            if isinstance(x, tuple) and len(x) == 4 and all([0 <= v <= 255 for v in x]):
                return x, None
            else:
                x = str(x)
                return None, _('should be (R,G,B,a) values each comprised between 0 and 255 (not %s)') % x


def is_positive_float(x):
    # Remove a potential floating point and test the other char
    msg = _('should be a positive float (not %s)') % x
    is_float = x.replace('.','',1).isdigit() and '.' in x
    if is_float:
        x = eval(x)
        if x > 0:
            return x, None
        else:
            return None, msg
    else:
        return None, msg


def is_in_list(x, li):
    # Turn x into a list
    x = [str(el) for el in x.split(',')] if ',' in x else [x]

    # Check that all elements of x is in the target (li) list
    result = True if all([el in li for el in x]) else False

    # Retrieve erroneous elements
    errors = [el for el in x if el not in li] if result == False else list()

    if result == True:  # If all elements of x are in target (li) list
    # Try to get an evaluated version of the (x) input
        try:
            x = [eval(el) for el in x]
        except NameError:
            if len(x) == 1:
                x = x[0]
            return x, None
        else:
            if len(x) == 1:
                x = x[0]
            return x, None
    else:
        return None, _('should be comprised in %s (not %s)') % (li, *errors,)


def is_a_regex(x):
    try:
        re.compile(x)
    except re.error:
        return None, _('should be a valid regex expression (not %s)') % (x)
    else:
        return x, None


def is_keyboard_key(x):
    keys_list = list(winkey._key_names.values())
    if x in keys_list:
        return x, None
    else:
        return None, _('should be an acceptable keyboard key value (not %s). See documentation.') % x


def is_task_location(x):
    location_list = ['fullscreen', 'topmid', 'topright', 'topleft', 'bottomleft', 'bottommid', 'bottomright']
    return is_in_list(x, location_list)


# In callsign, only letters and digits are allowed
allowed_char_list = list('abcdefghijklmnopqrstuvwxyz0123456789')
def is_callsign(x):
    if all([el.lower() in allowed_char_list for el in x]):
        return x, None
    else:
        # Get unallowed char
        errors = [el for el in x if el.lower() not in allowed_char_list]
        return None, _('should be composed of letters [a-z] or digits [0-9] (not %s in %s)') % (*errors, x)


def is_callsign_or_list_of(x):
    # Turn x into a list
    x = [str(el) for el in x.split(',')] if ',' in x else [x]

    # Check that all elements are valid callsigns
    result = all([is_callsign(el)[0] is not None for el in x])

    if result == True:
        return x, None
    else:
        # Retrieve unallowed callsigns
        err_cs = ','.join([cs for cs in x if is_callsign(cs)[0] is None])
        return None, _('should be composed of valid callsigns (not %s)') % err_cs


def is_in_unit_interval(x):
    msg = _('should be a float between 0 and 1 (included) (not %s)') % x
    try:
        x = eval(x)
        x = float(x)
    except NameError:
        return None, msg
    else:
        if 0 <= x <= 1:
            return x, None
        else:
            return None, msg


def is_available_text_file(x):
    # The filename of a blocking plugin is to be found either
    # in the scenario or the questionnaire folder
    if any([p.joinpath(x).exists() for p in [P['QUESTIONNAIRES'], P['INSTRUCTIONS']]]):
        return x, None
    else:
        return None, _('should be available either in the Instruction or Questionnaire folder (not %s)') % x


# This dictionary associates to each parameter name a checking method
validation_dict = {

    # If the key points to a tuple, the first argument is the method
    # the other arguments are extra-method arguments


    # General values #
    'title': is_string,
    'taskplacement': is_task_location,
    'taskupdatetime': is_positive_integer,


    # Shared values #
    'automaticsolver': is_boolean,
    'displayautomationstate': is_boolean,
    'taskfeedback-overdue-active': is_boolean,
    'taskfeedback-overdue-color': is_color,
    'taskfeedback-overdue-delayms': is_natural_integer,
    'taskfeedback-overdue-blinkdurationms': is_natural_integer,
    # (sysmon & communications)
    'feedbackduration': is_positive_integer,
    'feedbacks-positive-active': is_boolean,
    'feedbacks-positive-color': is_color,
    'feedbacks-negative-active': is_boolean,
    'feedbacks-negative-color': is_color,


    # Lab streaming layer #
    'marker': is_string,
    'streamsession': is_boolean,
    'pauseatstart': is_boolean,


    # System monitoring #
    'alerttimeout': is_positive_integer,
    'automaticsolverdelay': is_positive_integer,
    'allowanykey': is_boolean,
    'lights-1-name': is_string,
    'lights-1-failure': is_boolean,
    'lights-1-on': is_boolean,
    'lights-1-default': (is_in_list, ['on', 'off']),
    'lights-1-oncolor': is_color,
    'lights-1-key': is_keyboard_key,
    'lights-1-onfailure': is_boolean,
    'lights-2-name': is_string,
    'lights-2-failure': is_boolean,
    'lights-2-on': is_boolean,
    'lights-2-default': (is_in_list, ['on', 'off']),
    'lights-2-oncolor': is_color,
    'lights-2-key': is_keyboard_key,
    'lights-2-onfailure': is_boolean,
    'scales-1-name': is_string,
    'scales-1-failure': is_boolean,
    'scales-1-side': (is_in_list, ['-1', '0', '1']),
    'scales-1-key': is_keyboard_key,
    'scales-1-onfailure': is_boolean,
    'scales-2-name': is_string,
    'scales-2-failure': is_boolean,
    'scales-2-side': (is_in_list, ['-1', '0', '1']),
    'scales-2-key': is_keyboard_key,
    'scales-2-onfailure': is_boolean,
    'scales-3-name': is_string,
    'scales-3-failure': is_boolean,
    'scales-3-side': (is_in_list, ['-1', '0', '1']),
    'scales-3-key': is_keyboard_key,
    'scales-3-onfailure': is_boolean,
    'scales-4-name': is_string,
    'scales-4-failure': is_boolean,
    'scales-4-side': (is_in_list, ['-1', '0', '1']),
    'scales-4-key': is_keyboard_key,
    'scales-4-onfailure': is_boolean,


    # Tracking #
    'cursorcolor': is_color,
    'cursorcoloroutside': is_color,
    'targetproportion': is_in_unit_interval,
    'joystickforce': is_natural_integer,
    'inverseaxis': is_boolean,


    # Scheduling #
    'minduration': is_positive_integer,
    'displayedplugins': (is_in_list, ['sysmon', 'track', 'resman', 'communications']),


    # Communications #
    'owncallsign' : is_callsign,
    'othercallsign' : is_callsign_or_list_of,  # othercallsign can be a list of callsigns
    'voiceidiom': (is_in_list, [p.name.lower() for p in P['SOUNDS'].iterdir()]),
    'voicegender': (is_in_list, ['male', 'female']),
    'othercallsignnumber': is_positive_integer,
    'airbandminMhz': is_positive_float,
    'airbandmaxMhz': is_positive_float,
    'airbandminvariationMhz': is_positive_integer,
    'airbandmaxvariationMhz': is_positive_integer,
    'radioprompt' : (is_in_list, ['own', 'other']),
    'promptlist': (is_in_list, ['NAV_1', 'NAV_2', 'COM_1', 'COM_2']),
    'maxresponsedelay': is_positive_integer,
    'callsignregex': is_a_regex,


    # Resources management
    'pumpcoloroff': is_color,
    'pumpcoloron': is_color,
    'pumpcolorfailure': is_color,
    'toleranceradius': is_positive_integer,
    'statuslocation': is_task_location,
    'displaystatus': is_boolean,
    'tolerancecolor': is_color,
    'tolerancecoloroutside': is_color,

    'pump-1-flow': is_positive_integer,
    'pump-1-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-1-key': is_keyboard_key,
    'pump-2-flow': is_positive_integer,
    'pump-2-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-2-key': is_keyboard_key,
    'pump-3-flow': is_positive_integer,
    'pump-3-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-3-key': is_keyboard_key,
    'pump-4-flow': is_positive_integer,
    'pump-4-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-4-key': is_keyboard_key,
    'pump-5-flow': is_positive_integer,
    'pump-5-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-5-key': is_keyboard_key,
    'pump-6-flow': is_positive_integer,
    'pump-6-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-6-key': is_keyboard_key,
    'pump-7-flow': is_positive_integer,
    'pump-7-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-7-key': is_keyboard_key,
    'pump-8-flow': is_positive_integer,
    'pump-8-state': (is_in_list, ['off', 'on', 'failure']),
    'pump-8-key': is_keyboard_key,

    'tank-a-level': is_natural_integer,
    'tank-a-max': is_positive_integer,
    'tank-a-target': is_positive_integer,
    'tank-a-depletable': is_boolean,
    'tank-a-lossperminute': is_natural_integer,
    'tank-b-level': is_natural_integer,
    'tank-b-max': is_positive_integer,
    'tank-b-target': is_positive_integer,
    'tank-b-depletable': is_boolean,
    'tank-b-lossperminute': is_natural_integer,
    'tank-c-level': is_natural_integer,
    'tank-c-max': is_positive_integer,
    'tank-c-target': is_positive_integer,
    'tank-c-depletable': is_boolean,
    'tank-c-lossperminute': is_natural_integer,
    'tank-d-level': is_natural_integer,
    'tank-d-max': is_positive_integer,
    'tank-d-target': is_positive_integer,
    'tank-d-depletable': is_boolean,
    'tank-d-lossperminute': is_natural_integer,
    'tank-e-level': is_natural_integer,
    'tank-e-max': is_positive_integer,
    'tank-e-target': is_positive_integer,
    'tank-e-depletable': is_boolean,
    'tank-e-lossperminute': is_natural_integer,
    'tank-f-level': is_natural_integer,
    'tank-f-max': is_positive_integer,
    'tank-f-target': is_positive_integer,
    'tank-f-depletable': is_boolean,
    'tank-f-lossperminute': is_natural_integer,


    # Eye tracking
    # Coming soon

    # Parallel port
    'trigger': is_positive_integer,
    'delayms':is_positive_integer,


    # Performance
    'levelmin':is_positive_integer,
    'levelmax':is_positive_integer,
    'ticknumber':is_positive_integer,
    'criticallevel':is_positive_integer,
    'shadowundercritical':is_boolean,
    'defaultcolor':is_color,
    'criticalcolor':is_color,


    # Blocking plugins (genericscales, instructions)
    'boldtitle': is_boolean,
    'filename': is_available_text_file,
    'pointsize': is_natural_integer,
    'maxdurationsec': is_natural_integer,
    'response-text': is_string,
    'response-key': is_keyboard_key,
    'allowkeypress': is_boolean
    }
