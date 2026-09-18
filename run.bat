@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo CGTMSE Resubmit Desk
echo.

if exist ".venv\Scripts\python.exe" goto HAVEVENV

set "PYEXE="
if exist "C:\Python314\python.exe" set "PYEXE=C:\Python314\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python314\python.exe"

if not defined PYEXE (
  echo Python not found. Need C:\Python314\python.exe
  pause
  exit /b 1
)

echo Creating .venv with %PYEXE%
"%PYEXE%" -m venv .venv
if errorlevel 1 (
  echo Could not create .venv
  pause
  exit /b 1
)

:HAVEVENV
call ".venv\Scripts\activate.bat"
python -c "import sys; print('Using', sys.version)"
python -c "import openpyxl, playwright" 2>nul
if errorlevel 1 (
  python -m pip install --upgrade pip
  python -m pip install "openpyxl>=3.1.5" "playwright>=1.49.0"
  if errorlevel 1 (
    echo pip install failed
    pause
    exit /b 1
  )
)
python -m playwright install chromium
python launcher.py
if errorlevel 1 pause
endlocal
