CGTMSE Resubmit Desk  v1.7.0

1. Double-click run.bat
2. Files tab: choose Credential Master and Claims Data
3. Optional: maker / checker fallback passwords, comma separated
4. Build queue → Run → Start live run
5. Stop still finishes checker for claims already sent on that MLI
6. Output folder: output\RESUBCL-dd-mm-yyyy-HH-MM

What changed in 1.7.0
- RESULT follows the portal page, not the click
- Maker "forwarded" only if the page says forwarded (or already sent)
- Checker "certified" only if Approved Claims is shown
- Already-sent claims still go to checker
- Error screenshot is taken on the red page, before going back to search
- Checker list is photographed before ACCEPT
- No video recording
- Chrome console noise stays out of log.txt
