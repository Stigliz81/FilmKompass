@echo off
setlocal
cd /d "%~dp0"
echo FilmKompass - Browserexport einmalig einrichten
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.11 oder neuer fehlt. Bitte zuerst Python installieren.
    pause
    exit /b 1
  )
  python -m venv .venv
)
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-export.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto error
echo.
echo Fertig. Browseradapter ist in der Python-Version verfuegbar. Siehe README.
pause
exit /b 0
:error
echo.
echo Einrichtung nicht abgeschlossen. Bitte die Meldungen oben pruefen.
pause
exit /b 1
