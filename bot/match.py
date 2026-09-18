from __future__ import annotations

from collections import defaultdict

from .parse import canonical_mli, merge_password_chain, split_passwords


def build_queue(credentials: list[dict], claims: list[dict], maker_fallback: str = "", checker_fallback: str = "") -> list[dict]:
    by_mli = {c["mliCanonical"]: c for c in credentials if c.get("mliCanonical")}
    maker_fb = split_passwords(maker_fallback)
    checker_fb = split_passwords(checker_fallback)
    items: list[dict] = []
    for claim in claims:
        mli = claim.get("mliCanonical") or canonical_mli(claim.get("mliId", ""))
        cred = dict(by_mli.get(mli) or {})
        if cred:
            cred["makerPasswords"] = merge_password_chain(cred.get("makerPassword", ""), maker_fb)
            cred["checkerPasswords"] = merge_password_chain(cred.get("checkerPassword", ""), checker_fb)
        items.append(
            {
                "claim": claim,
                "credential": cred,
                "status": "queued" if cred else "error",
                "phase": "",
                "message": "" if cred else "No credential for this MLI",
                "remark": "",
            }
        )
    return items


def group_by_mli(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        mli = (item.get("credential") or {}).get("mliCanonical") or item["claim"].get("mliCanonical") or ""
        groups[mli].append(item)
    return dict(groups)
