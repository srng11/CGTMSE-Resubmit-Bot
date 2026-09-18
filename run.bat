@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo CGTMSE Resubmit Desk
echo.

rem --- Reuse a venv that already worked ---
if exist ".venv\Scripts\python.exe" goto HAVEVENV

for %%D in (
  "%USERPROFILE%\Downloads\CGTMSE-Resubmit-Bot-main\CGTMSE-Resubmit-Bot-main\.venv"
  "%USERPROFILE%\Downloads\CGTMSE-Resubmit-Bot-main\.venv"
  "%~dp0..\CGTMSE-Resubmit-Bot-main\.venv"
  "%~dp0..\CGTMSE-Resubmit-Bot-main\CGTMSE-Resubmit-Bot-main\.venv"
) do (
  if exist "%%~D\Scripts\python.exe" (
    echo Using the working .venv from:
    echo   %%~D
    mklink /J ".venv" "%%~D" >nul 2>&1
    if not exist ".venv\Scripts\python.exe" xcopy /E /I /Y "%%~D" ".venv" >nul
    if exist ".venv\Scripts\python.exe" goto HAVEVENV
  )
)

rem --- Find a real python.exe. Never use py -3 (broken pythoncore path). ---
set "PYEXE="
if exist "C:\Python314\python.exe" set "PYEXE=C:\Python314\python.exe"
if not defined PYEXE if exist "C:\Python313\python.exe" set "PYEXE=C:\Python313\python.exe"
if not defined PYEXE if exist "C:\Python312\python.exe" set "PYEXE=C:\Python312\python.exe"
if not defined PYEXE if exist "C:\Python311\python.exe" set "PYEXE=C:\Python311\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"

if not defined PYEXE (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "pythoncore" >nul
    if errorlevel 1 (
      if not defined PYEXE set "PYEXE=%%P"
    )
  )
)

if not defined PYEXE (
  echo Python was not found.
  echo Install from https://www.python.org/downloads/ and tick Add python.exe to PATH.
  pause
  exit /b 1
)

echo Creating virtual environment with:
echo   %PYEXE%
"%PYEXE%" -c "import sys; print(' ', sys.version)"
"%PYEXE%" -m venv .venv
if errorlevel 1 (
  echo Could not create .venv
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
echo Using:
python -c "import sys; print(' ', sys.version)"

python -c "import openpyxl, playwright" >nul 2>&1
if not errorlevel 1 goto READY

echo Installing packages (current Playwright, works on Python 3.14)...
python -m pip install --upgrade pip
python -m pip install "openpyxl>=3.1.5" "playwright>=1.49.0"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

:READY
python -m playwright install chromium
python launcher.py
if errorlevel 1 pause
endlocal
