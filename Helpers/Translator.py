import os
# This class is a simplified alternative to gettext in unicode

# translations are stored as key=values in a text language file.
# language is set by the config file
# If a translation is not available, the default language is used



_translations = {}

_lang = ""

def translate(s):
    global _translations
    global _lang
    _lang = _lang.strip()
    if len(_translations)==0 and _lang!='':

        translation_filename = os.path.join('Translations', _lang + ".txt")

        if not os.path.exists(translation_filename):
            print("There is no translation in the '"+_lang+"' language!")
            _lang = "" # reset the translation to resume
        else:
            try:
                with open(translation_filename, 'r') as lines:
                    for line in lines:
                        split = line.decode('utf-8').split('=')
                        if len(split)==2:
                            _translations[split[0]]=''.join(split[1].splitlines()) #remove carriage return
            except:
                OSCriticalErrorMessage("Error",
                "Unable to open the translation. Please ensure it is saved as an UTF-8 file!")

    if len(_translations)!=0 and _translations.has_key(str(s)):
        return str(_translations[str(s)])

    return str(s)
