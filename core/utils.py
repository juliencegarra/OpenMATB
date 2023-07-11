# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from core.constants import PATHS as P
import configparser

def get_session_numbers():
    try:
        session_numbers = [int(s.name.split('_')[0]) 
                           for s in P['SESSIONS'].glob('**/*.csv')]
    except:
        session_numbers = [0]

    return session_numbers


def find_the_first_available_session_number():
    session_numbers = get_session_numbers()
    first_avail = None
    
    # Take max session number + 1, and find the minimum available number into [1, max+1]
    # If no session has been manually removed, it will be max+1
    if len(session_numbers) == 0:
        first_avail = 1
    else:
        for n in range(1, max(session_numbers)+1):
            if n not in session_numbers and first_avail is None:
                first_avail = n

    if first_avail is None:
        first_avail = max(session_numbers) + 1

    return first_avail


def find_the_last_session_number():
    session_numbers = get_session_numbers()
    return max(session_numbers)


def get_conf_value(section, key, val_type=None):

    # Read the configuration file
    config_path = P['PLUGINS'].parent.joinpath('config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)

    value = config[section][key]

    # Boolean boolean values
    if key in ['fullscreen', 'highlight_aoi', 'hide_on_pause', 'display_session_number']:
        if value.strip().lower() == 'true':
            return True
        elif value.strip().lower() == 'false':
            return False
        else:
            raise TypeError(_(f"In config.ini, [%s] parameter must be a boolean (true or false, not %s). Defaulting to False") % (key, value))


    # Integer values
    elif key in ['screen_index']:
        try:
            value = int(value)
        except:
            raise TypeError(_(f"In config.ini, [%s] parameter must be an integer (not %s)") % (key, value))
        else:
            return value

    # Float values
    elif key in ['clock_speed']:
        try:
            value = float(value)
        except:
            raise TypeError(_(f"In config.ini, [%s] parameter must be a float (not %s)") % (key, value))
        else:
            return value

    # String value
    else:
        # Font definition & check
        if key == 'font_name':
            if len(value) == 0:
                return
            elif not font.have_font(value):
                raise TypeError(_(f"In config.ini, the specified font is not available. A default font will be used."))
            else:
                return font_name

        return value