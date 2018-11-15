#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, os, zipfile


# get version number
_version = "unkwnon version"

for lineBuf in open('OpenMATB.py', 'r'):
    s = lineBuf.replace(' ','').upper()
    pos = s.find('VERSION="')
    if pos>-1:
        _version = s[9:len(s)-2]
        break



def includedirectory(d):
    for file in os.listdir(d):
        if file.endswith(".py"):
            includes.extend([os.path.join(d, file)])

#############################################################################
includes = ['PySide', 'pygame', 'wave', 'numpy']
excludes = ['collections.abc', 'tcl']
packages = []
path = []



from cx_Freeze import setup, Executable
GUI2Exe_Target_1 = Executable(
       # what to build
       script = "OpenMATB.py",
       initScript = None,
       base = 'Win32GUI',  # Hide the console
       targetName = "OpenMATB.exe"
       )

setup(
    name = "OpenMATB",
    version = _version,
    description = "OpenMATB",
    author = "Julien Cegarra & Benoit Valery",

    options = {"build_exe": {"includes": includes,
                             "excludes": excludes,
                              "packages": packages,
                              "path": path,
                              "build_exe" : "OpenMATB"
                              #"create_shared_zip": False,

                              }
                },

     executables = [GUI2Exe_Target_1]
     )


# CREATE A ZIP FILE

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


zipf = zipfile.ZipFile('OpenMATB_v'+_version+'.zip', 'w', zipfile.ZIP_DEFLATED)
zipdir('OpenMATB/', zipf)
zipf.close()

