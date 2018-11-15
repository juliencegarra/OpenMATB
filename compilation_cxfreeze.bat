
@RD /S /q OpenMATB
xcopy Helpers\*.* OpenMATB\Helpers\*.* /e
xcopy Plugins\*.* OpenMATB\Plugins\*.* /e
xcopy Scales\*.* OpenMATB\Scales\*.* /e
xcopy Translations\*.* OpenMATB\Translations\*.* /e
python.exe compilation_cxfreeze.py build

cd openMATB
openMATB.exe