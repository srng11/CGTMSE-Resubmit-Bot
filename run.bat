@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install openpyxl==3.1.5 playwright==1.48.0
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
python -m playwright install chromium
python launcher.py
pause
