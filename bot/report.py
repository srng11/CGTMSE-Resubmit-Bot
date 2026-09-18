from __future__ import annotations

import csv
from pathlib import Path


def export_csv(path: str | Path, queue: list[dict]) -> Path:
    p = Path(path)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["MLI ID", "Claim Ref", "Maker", "Checker", "Status", "Remark", "Message"])
        for item in queue:
            claim = item["claim"]
            cred = item.get("credential") or {}
            w.writerow(
                [
                    claim.get("mliCanonical", ""),
                    claim.get("claimRef", ""),
                    cred.get("makerUser", ""),
                    cred.get("checkerUser", ""),
                    item.get("status", ""),
                    item.get("remark", ""),
                    item.get("message", ""),
                ]
            )
    return p
