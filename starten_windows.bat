@echo off
setlocal
cd /d "%~dp0"
rem Python source launcher; portable users start FilmKompass.exe.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" moviepilot_manager.py
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 moviepilot_manager.py
  ) else (
    python moviepilot_manager.py
  )
)
if errorlevel 1 (
  echo Start fehlgeschlagen. Python 3.11+ und requirements.txt erforderlich.
  pause
)
