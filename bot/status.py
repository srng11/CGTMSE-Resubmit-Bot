"""Claim outcome words used in RESULT.csv — one meaning each."""

QUEUED = "queued"
RUNNING = "running"
FORWARDED = "forwarded"
CERTIFIED = "certified"
BLOCKED = "blocked"
ERROR = "error"

CHECKER_OK = (
    "has been certified",
    "certified successfully",
    "claim(s) have been approved",
    "successfully certified",
    "d&u has been",
    "d and u has been",
)

CHECKER_NO_TICK = (
    "select atleast one",
    "select at least one",
    "accepet or reject",
    "accept or reject",
)


def classify_login_text(title: str, body: str) -> str:
    blob = f"{title or ''}\n{body or ''}".lower()
    if "invalid password" in blob or (title or "").strip().lower() == "error message":
        return "bad"
    if "log out" in blob:
        return "ok"
    return "other"


def classify_checker_text(text: str) -> str:
    low = (text or "").lower()
    if any(p in low for p in CHECKER_NO_TICK):
        return "no_tick"
    if any(p in low for p in CHECKER_OK):
        return "ok"
    return "other"


def summary_counts(queue: list[dict]) -> dict[str, int]:
    keys = (QUEUED, RUNNING, FORWARDED, CERTIFIED, BLOCKED, ERROR)
    counts = {k: 0 for k in keys}
    counts["other"] = 0
    for item in queue:
        st = str(item.get("status") or "other")
        if st in counts:
            counts[st] += 1
        else:
            counts["other"] += 1
    return counts
