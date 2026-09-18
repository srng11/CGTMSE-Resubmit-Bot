@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Run run.bat first to create .venv
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install "pyinstaller>=6.15.0"
if errorlevel 1 (
  echo PyInstaller is optional. Use run.bat to start the desk.
  pause
  exit /b 1
)
pyinstaller --noconfirm --clean --windowed --name CGTMSE_Resubmit_Desk launcher.py
echo Built dist\CGTMSE_Resubmit_Desk
pause
