from __future__ import annotations

from .parse import merge_password_chain, split_passwords


def mask_secret(value: str) -> str:
    if not value:
        return "—"
    if len(value) <= 2:
        return "••"
    return "•" * min(10, len(value) - 2) + value[-2:]


def format_passwords(passwords: list[str] | None, show: bool) -> str:
    pwds = [p for p in (passwords or []) if p]
    if not pwds:
        return "—"
    if show:
        return "  →  ".join(pwds) if len(pwds) > 1 else pwds[0]
    hidden = mask_secret(pwds[0])
    extra = len(pwds) - 1
    if extra:
        return f"{hidden}  +{extra} fallback"
    return hidden


def apply_user_fallbacks(creds: list[dict], maker_fallback_text: str, checker_fallback_text: str) -> list[dict]:
    maker_fb = split_passwords(maker_fallback_text)
    checker_fb = split_passwords(checker_fallback_text)
    out = []
    for cred in creds:
        rec = dict(cred)
        rec["makerPasswords"] = merge_password_chain(cred.get("makerPassword", ""), maker_fb)
        rec["checkerPasswords"] = merge_password_chain(cred.get("checkerPassword", ""), checker_fb)
        out.append(rec)
    return out


def build_queue(claims: list[dict], creds: list[dict]) -> list[dict]:
    by_mli = {c["mliCanonical"]: c for c in creds}
    queue: list[dict] = []
    for claim in claims:
        if not claim.get("claimRef"):
            continue
        cred = by_mli.get(claim.get("mliCanonical", ""))
        item = {
            "claim": claim,
            "credential": cred,
            "status": "queued",
            "phase": "idle",
            "remark": "",
            "message": "",
        }
        if not cred:
            item["status"] = "error"
            item["message"] = "No credentials for this MLI ID"
        elif not cred.get("makerUser") or not cred.get("makerPasswords"):
            item["status"] = "error"
            item["message"] = "Maker user or password missing"
        elif not cred.get("checkerUser") or not cred.get("checkerPasswords"):
            item["status"] = "error"
            item["message"] = "Checker user or password missing"
        queue.append(item)
    return queue


def group_by_mli(items: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        key = item["claim"].get("mliCanonical") or "(blank)"
        grouped.setdefault(key, []).append(item)
    return grouped
