# CGTMSE Resubmit Desk v1.7.0

Windows desk that resubmits returned first-instalment claims on the CGTMSE portal (maker, then checker).

## Run

1. Double-click `run.bat`
2. Files tab: Credential Master + Claims Data
3. Optional maker / checker fallback passwords, comma separated
4. Build queue → Run → Start live run
5. Output: `output\RESUBCL-dd-mm-yyyy-HH-MM`

Stop still finishes checker for claims already sent on that MLI.

## v1.7.0

- RESULT follows the portal page, not the click
- Maker "forwarded" only if the page says forwarded (or already sent)
- Checker "certified" only if Approved Claims is shown
- Already-sent claims still go to checker
- Error screenshot is taken on the red page, before going back to search
- Checker list is photographed before ACCEPT
- No video recording
- Chrome console noise stays out of `log.txt`

## Files

- `run.bat` — create venv, install openpyxl + playwright, start desk
- `launcher.py` / `dashboard.py` — office-colour wizard
- `bot/` — portal, engine, evidence, Excel parse
- `build_exe.bat` — optional PyInstaller (not required)
