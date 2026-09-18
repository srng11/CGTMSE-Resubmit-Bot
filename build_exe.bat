@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ and tick Add to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6.15.0"
if errorlevel 1 (
  echo pyinstaller install failed. Your Python may be too new or too old.
  python --version
  pause
  exit /b 1
)

echo.
echo Building CGTMSE_Resubmit_Desk.exe ...
pyinstaller --noconfirm --clean --windowed --onefile ^
  --name CGTMSE_Resubmit_Desk ^
  --add-data "templates;templates" ^
  --add-data "bot;bot" ^
  --hidden-import openpyxl ^
  --hidden-import openpyxl.cell._writer ^
  --hidden-import playwright ^
  --hidden-import playwright.sync_api ^
  --collect-submodules bot ^
  launcher.py

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Done. EXE is in dist\CGTMSE_Resubmit_Desk.exe
echo Live portal mode still needs Playwright browsers:
echo   .venv\Scripts\python -m playwright install chromium
echo Copy the templates folder next to the EXE if you want the sample sheets.
pause
endlocal
