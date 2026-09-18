@echo off
cd /d "%~dp0"
echo CGTMSE Resubmit Desk
echo Using C:\Python314\python.exe
if not exist "C:\Python314\python.exe" (
  echo C:\Python314\python.exe not found.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  "C:\Python314\python.exe" -m venv .venv
  if errorlevel 1 (
    echo venv failed
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -c "import openpyxl, playwright" 2>nul
if errorlevel 1 (
  python -m pip install --upgrade pip
  python -m pip install openpyxl playwright
)
python -m playwright install chromium
python launcher.py
pause
