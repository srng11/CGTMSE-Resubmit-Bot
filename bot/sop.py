PORTAL_URL = "https://inter.cgtmse.in/jsp/Home.jsp"

SOP_STEPS = [
    {"id": "open", "role": "maker", "title": "Open portal, close notice", "detail": "https://inter.cgtmse.in — Close the CGS-1 scheme banner."},
    {"id": "login", "role": "maker", "title": "Sign in as Maker", "detail": "Member ID, Maker user ID, password, tick T&Cs, click Sign In."},
    {"id": "caution", "role": "maker", "title": "Acknowledge caution", "detail": "Tick the AGF warning and Close."},
    {"id": "menu", "role": "maker", "title": "Open returned-claim form", "detail": "Claims Processing → Claim For → Update Returned Claim Info."},
    {"id": "lookup", "role": "maker", "title": "Call up the claim", "detail": "Enter Claim Reference No. and press OK."},
    {"id": "remark", "role": "maker", "title": "Read return remark", "detail": "Capture the red help line from CGTMSE."},
    {"id": "correct", "role": "maker", "title": "Apply corrections", "detail": "Optional Excel columns: URN, State, Legal Waiver, Comment."},
    {"id": "submit", "role": "maker", "title": "Submit and Accept D/U", "detail": "Submit the form, Accept the Declaration & Undertaking."},
    {"id": "logout-maker", "role": "handover", "title": "Maker logs out", "detail": "Session closed. Checker signs in with a different user ID."},
    {"id": "login-checker", "role": "checker", "title": "Sign in as Checker", "detail": "Same Member ID, Checker user ID, password, T&Cs, Sign In, caution."},
    {"id": "accept", "role": "checker", "title": "ACCEPT and Save", "detail": "Submission of claim → ACCEPT on that claim → confirm alert → Save picture."},
    {"id": "logout-checker", "role": "checker", "title": "Checker logs out", "detail": "Confirm the claim under Approved Claims, then Log Out."},
]

RETURNED_FORM = "displayClaimDetailsInput.do?method=displayClaimDetailsInput"
CHECKER_LIST = "displayClaimProcessingSubmitDU.do?method=displayClaimProcessingSubmitDU"
