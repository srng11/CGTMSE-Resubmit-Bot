@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo CGTMSE Resubmit Desk
echo Looking for Python 3.12 / 3.13 / 3.11  (Playwright does not like a broken 3.14 launcher)
echo.

set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 -c "import sys" >nul 2>&1 && set "PYEXE=py -3.12"
  if not defined PYEXE py -3.13 -c "import sys" >nul 2>&1 && set "PYEXE=py -3.13"
  if not defined PYEXE py -3.11 -c "import sys" >nul 2>&1 && set "PYEXE=py -3.11"
  if not defined PYEXE py -3.10 -c "import sys" >nul 2>&1 && set "PYEXE=py -3.10"
)

if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python311\python.exe" set "PYEXE=C:\Python311\python.exe"

if not defined PYEXE (
  where python >nul 2>&1
  if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
  echo No Python found. Install Python 3.12 from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH". Then run this file again.
  pause
  exit /b 1
)

echo Using: %PYEXE%
%PYEXE% -c "import sys; print('  ', sys.version)"

if exist .venv\Scripts\python.exe goto HAVEVENV

echo Creating virtual environment...
%PYEXE% -m venv .venv
if errorlevel 1 (
  echo.
  echo Could not create .venv with that Python.
  echo Install Python 3.12 from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

:HAVEVENV
if not exist .venv\Scripts\python.exe (
  echo .venv is broken. Delete the .venv folder and run this file again.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install "openpyxl==3.1.5" "playwright>=1.48.0"
if errorlevel 1 (
  echo.
  echo pip install failed.
  echo This desk needs Python 3.10 to 3.13. Python 3.14 often fails here.
  echo Install 3.12 from python.org, then delete the .venv folder and run this file again.
  pause
  exit /b 1
)
python -m playwright install chromium
python launcher.py
pause
