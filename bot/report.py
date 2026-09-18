from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def _reason(item: dict) -> str:
    msg = (item.get("message") or item.get("portal") or "").lower()
    st = item.get("status") or ""
    if st == "queued":
        return "queued"
    if "certified" in msg or "approved claims" in msg or "approvaed claims" in msg:
        return "certified"
    if "not on checker list" in msg:
        return "maker sent — not on checker list"
    if "checker not certified" in msg or "select at least one" in msg or "select atleast one" in msg:
        return "maker sent — checker save rejected"
    if "already sent" in msg or "already exist" in msg or "can not be updated" in msg or "cannot be updated" in msg:
        return "already sent — checker pending"
    if "maker forwarded" in msg or "has been forwarded" in msg:
        return "maker sent — checker pending"
    if "urn" in msg:
        return "URN / UAP"
    if "closed" in msg or "no live account" in msg:
        return "loan closed"
    if "legal" in msg and "attachment" in msg:
        return "legal papers required"
    if "valid amount" in msg or "term loan/composite" in msg:
        return "term loan amount missing"
    if st == "error":
        return "blocked"
    if st == "done":
        return "done"
    return st or "other"


def write_result(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "MLI ID",
                "Claim Ref",
                "Maker",
                "Checker",
                "Status",
                "Reason",
                "Remark",
                "Message",
            ],
        )
        w.writeheader()
        for item in items:
            claim = item.get("claim") or {}
            cred = item.get("credential") or {}
            w.writerow(
                {
                    "MLI ID": claim.get("mliCanonical") or claim.get("mliId") or "",
                    "Claim Ref": claim.get("claimRef") or "",
                    "Maker": cred.get("makerUser") or "",
                    "Checker": cred.get("checkerUser") or "",
                    "Status": item.get("status") or "",
                    "Reason": _reason(item),
                    "Remark": item.get("remark") or "",
                    "Message": item.get("message") or item.get("portal") or "",
                }
            )


def write_summary(path: Path, items: list[dict], folder: str, note: str = "") -> None:
    counts: dict[str, int] = {}
    status = {"done": 0, "error": 0, "queued": 0, "running": 0}
    for item in items:
        st = item.get("status") or "queued"
        status[st] = status.get(st, 0) + 1
        reason = _reason(item)
        counts[reason] = counts.get(reason, 0) + 1
    lines = [
        "CGTMSE Resubmit Desk — RESULT",
        f"Folder: {folder}",
        f"Time:   {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Total    {len(items)}",
        f"Done     {status.get('done', 0)}",
        f"Error    {status.get('error', 0)}",
        f"Queued   {status.get('queued', 0)}",
        f"Running  {status.get('running', 0)}",
        "",
        "By meaning",
    ]
    for key in sorted(counts, key=lambda k: (-counts[k], k)):
        lines.append(f"  {counts[key]:5d}  {key}")
    lines.append("")
    if note:
        lines.append(note)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
