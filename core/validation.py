# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

# Validation methods
# The following methods, associated with the valid_type dictionary, allows to check that
# each scenario parameter value is accepted.

from core.constants import COLORS as C, PATHS as P
from core.joystick import joykey
from pyglet.window import key as winkey

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
    elif x in ['1', '0']:
        return bool(int(x)), None
    else:
        return None, _('should be a boolean (not %s).') % x


def is_color(x):  # Can be an hexadecimal value, a constant name, or an RGBa value
    m = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', x)
    if m is not None:
        x = x.lstrip('#')
        rgba = tuple(list(int(x[i:i + 2], 16) for i in (0, 2, 4)) + [255])
        return rgba, None
    elif x in list(C.keys()):
        return C[x], None
    else:
        try:
            x = eval(x)
        except:
            return None, _('must be (R,G,B,a) or hexadecimal (e.g., #00ff00) values (not %s)') % x
        else:
            if ((isinstance(x, tuple) or isinstance(x, list))
                    and len(x) == 4 and all([0 <= v <= 255 for v in x])):
                return tuple(x), None
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


def is_joystick_key(x):
    if joykey is not None: # Means that the joystick is plugged
        if x in joykey.keys():
            return x, None
        else:
            return None, _('should be an acceptable joystick key value (not %s). See documentation.') % x
    return None, None


def is_key(x):
    kk, kmsg = is_keyboard_key(x)
    if kmsg is None:
        return is_keyboard_key(x)

    jk, jmsg = is_joystick_key(x)
    if jmsg is None:
        return is_joystick_key(x)

    return None, _('should be an acceptable (keyboard or joystick) key value (not %s). See documentation.') % x


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
