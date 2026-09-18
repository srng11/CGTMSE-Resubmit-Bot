@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo CGTMSE Resubmit Desk
echo.

rem --- 1. Reuse a venv that already worked today ---
if exist ".venv\Scripts\python.exe" goto HAVEVENV

for %%D in (
  "%USERPROFILE%\Downloads\CGTMSE-Resubmit-Bot-main\CGTMSE-Resubmit-Bot-main\.venv"
  "%USERPROFILE%\Downloads\CGTMSE-Resubmit-Bot-main\.venv"
  "%~dp0..\CGTMSE-Resubmit-Bot-main\.venv"
  "%~dp0..\CGTMSE-Resubmit-Bot-main\CGTMSE-Resubmit-Bot-main\.venv"
) do (
  if exist "%%~D\Scripts\python.exe" (
    echo Linking the working .venv from:
    echo   %%~D
    mklink /J ".venv" "%%~D" >nul 2>&1
    if exist ".venv\Scripts\python.exe" goto HAVEVENV
  )
)

rem --- 2. Build a new venv with 3.10-3.13 only. Never use py -3 (that hits broken 3.14). ---
set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
  call :TRYPY -3.12
  if not defined PYEXE call :TRYPY -3.13
  if not defined PYEXE call :TRYPY -3.11
  if not defined PYEXE call :TRYPY -3.10
)

if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python311\python.exe" set "PYEXE=C:\Python311\python.exe"
if not defined PYEXE if exist "C:\Python310\python.exe" set "PYEXE=C:\Python310\python.exe"

if not defined PYEXE (
  echo No Python 3.10-3.13 found.
  echo This PC's default is Python 3.14, which cannot install the old Playwright.
  echo.
  echo Do one of these:
  echo   A. Copy the .venv folder from the desk that ran this morning into this folder
  echo   B. Install Python 3.12 from https://www.python.org/downloads/  ^(tick Add to PATH^)
  echo.
  pause
  exit /b 1
)

echo Creating virtual environment with %PYEXE%
%PYEXE% -c "import sys; print(' ', sys.version)"
%PYEXE% -m venv .venv
if errorlevel 1 (
  echo Could not create .venv.
  pause
  exit /b 1
)

:HAVEVENV
if not exist ".venv\Scripts\python.exe" (
  echo .venv is broken. Delete the .venv folder and run this file again.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
echo Using venv:
python -c "import sys; print(' ', sys.version)"

python -c "import openpyxl,playwright" >nul 2>&1
if not errorlevel 1 goto READY

echo Installing packages into the venv...
python -m pip install --upgrade pip
python -m pip install "openpyxl==3.1.5" "playwright>=1.48.0,<2"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

:READY
python -c "from playwright.sync_api import sync_playwright" >nul 2>&1
if errorlevel 1 (
  echo Playwright is not usable in this venv.
  pause
  exit /b 1
)
python -m playwright install chromium
python launcher.py
pause
exit /b 0

:TRYPY
py %1 -c "import sys; raise SystemExit(0 if sys.version_info < (3,14) else 1)" >nul 2>&1
if not errorlevel 1 set "PYEXE=py %1"
exit /b 0
