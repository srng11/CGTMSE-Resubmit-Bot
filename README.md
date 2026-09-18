# CGTMSE Resubmit Desk

Windows desk for returned first-instalment claims on https://inter.cgtmse.in

## Start on this PC

Double-click **START_DESK.bat**

That file uses `C:\Python314\python.exe`. Do not use an old `run.bat` that says Python 3.10–3.13 is required.

## First run

1. Unzip to a new folder (Desktop is fine)
2. Double-click `START_DESK.bat`
3. Files tab: credential master + claims workbook
4. Build queue → Start live run

## Output

`output\RESUBCL-dd-mm-yyyy-HH-MM\`

Checker ticks **all** ACCEPT boxes on the list, then clicks the Save **picture** (not the page link). RESULT only says Complete if the portal confirms. If maker already forwarded a claim, checker still tries to certify it. Stop still finishes checker for the current MLI.

## GitHub Actions

Every push to `main` compiles the Python files and uploads **CGTMSE_Resubmit_Bot.zip**.

1. Open the **Actions** tab
2. Open the latest **CI** run
3. Download the **CGTMSE_Resubmit_Bot** artifact

You can also click **Run workflow** on that CI workflow.
