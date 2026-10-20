@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Einrichtung abgeschlossen. starten_windows.bat oeffnet die Python-Version.
pause
exit /b 0
:error
echo Einrichtung fehlgeschlagen. Python 3.11 oder neuer mit Tkinter erforderlich.
pause
exit /b 1
