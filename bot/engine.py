from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .envcheck import collect_environment, format_environment
from .evidence import Evidence
from .match import group_by_mli
from .sop import SOP_STEPS

LogFn = Callable[[str, str, str], None]
StopFn = Callable[[], bool]


def _sleep(ms: int, stopped: StopFn) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        if stopped():
            raise RuntimeError("Stopped by operator")
        time.sleep(0.05)


def _wrap_log(log: LogFn, evidence: Evidence | None) -> LogFn:
    def inner(level: str, text: str, claim: str = "") -> None:
        if evidence is not None:
            evidence.event("log", text, level=level, claim=claim)
        log(level, text, claim)

    return inner


def persist(evidence: Evidence | None, items: list[dict], note: str = "") -> None:
    if evidence is None:
        return
    try:
        evidence.finish(items, note or f"Pack: {evidence.root}")
    except Exception:
        pass


def start_session(bot_root: Path, mode: str, live: bool, items: list[dict], screen: str = "", extra: dict | None = None) -> Evidence:
    ev = Evidence(bot_root)
    run = {
        "mode": mode,
        "live": live,
        "claims": len(items),
        **(extra or {}),
    }
    env = collect_environment(bot_root, screen=screen, extra=run)
    ev.write_json("environment.json", env)
    return ev


def describe_env(bot_root: Path, screen: str = "") -> str:
    return format_environment(collect_environment(bot_root, screen=screen))


def run_rehearsal(items, mode, log: LogFn, stopped: StopFn, on_item, evidence: Evidence | None = None) -> None:
    log = _wrap_log(log, evidence)
    runnable = [i for i in items if i.get("status") == "queued"]
    log("info", f"Rehearsal started · {len(runnable)} claim(s) · mode {mode}", "")
    if evidence:
        log("info", f"Output pack: {getattr(evidence, 'root', evidence.dir)}", "")
    groups = group_by_mli(runnable)
    for mli, group in groups.items():
        if stopped():
            break
        cred = group[0].get("credential") or {}
        n_m = len(cred.get("makerPasswords") or [])
        n_c = len(cred.get("checkerPasswords") or [])
        log(
            "info",
            f"MLI {mli} · Maker {cred.get('makerUser','')} ({n_m} password(s)) · Checker {cred.get('checkerUser','')} ({n_c} password(s)) · {len(group)} claim(s)",
            "",
        )
        for item in group:
            if stopped():
                break
            _rehearse_one(item, mode, log, stopped, on_item)
    if stopped():
        log("warn", "Run stopped. Remaining claims stay queued.", "")
    else:
        log("ok", "Rehearsal finished. No portal was called.", "")
    if evidence:
        evidence.finish(items, "Rehearsal complete. No portal screenshots.")


def _rehearse_one(item, mode, log, stopped, on_item) -> None:
    claim = item["claim"]
    cred = item["credential"]
    ref = claim["claimRef"]
    on_item(claim["id"], {"status": "running", "phase": "maker"})
    log("info", f"Maker session for {ref}", ref)
    for step in SOP_STEPS:
        if step["role"] != "maker":
            continue
        _sleep(220, stopped)
        if step["id"] == "login":
            n = len(cred.get("makerPasswords") or [cred.get("makerPassword")])
            log("ok", f"Signed in as {cred['makerUser']} @ {cred['mliCanonical']} · {n} password(s) on file", ref)
        elif step["id"] == "lookup":
            log("ok", f"Opened {ref}", ref)
        elif step["id"] == "remark":
            remark = f"URN supplied in file: {claim['urn']}" if claim.get("urn") else "Return remark would be read from the red help line."
            on_item(claim["id"], {"remark": remark})
            log("info", remark, ref)
        elif step["id"] == "correct":
            bits = [b for b in [
                f"URN={claim['urn']}" if claim.get("urn") else "",
                f"State={claim['state']}" if claim.get("state") else "",
                f"Legal Waiver={claim['legalWaiver']}" if claim.get("legalWaiver") else "",
                f"Comment={claim['comment']}" if claim.get("comment") else "",
            ] if b]
            if bits:
                log("ok", "Corrections from file: " + " · ".join(bits), ref)
            else:
                log("warn", "No correction columns in the claims file.", ref)
        elif step["id"] == "submit":
            if mode == "inspect":
                log("warn", "Inspect mode — submit skipped.", ref)
            else:
                log("ok", "Submit + Accept D/U (rehearsed).", ref)
        else:
            log("info", step["title"], ref)
    _sleep(160, stopped)
    log("info", "Maker logs out", ref)
    if mode == "inspect":
        on_item(claim["id"], {"status": "done", "phase": "done", "message": "Inspect rehearsal complete"})
        return
    on_item(claim["id"], {"phase": "checker"})
    log("info", f"Checker session for {ref} as {cred['checkerUser']}", ref)
    for step in SOP_STEPS:
        if step["role"] != "checker":
            continue
        _sleep(220, stopped)
        log("ok", step["title"], ref)
    on_item(claim["id"], {"status": "done", "phase": "done", "message": "Rehearsal complete — forwarded / Approved Claims (simulated)"})
    log("ok", f"Done {ref}", ref)


def _launch_browser(pw, headless: bool, log: LogFn):
    """Prefer installed Chrome so the login page matches what the operator sees (captcha image)."""
    attempts = [
        {"channel": "chrome", "headless": headless, "args": ["--disable-blink-features=AutomationControlled"]},
        {"channel": "msedge", "headless": headless, "args": ["--disable-blink-features=AutomationControlled"]},
        {"headless": headless, "args": ["--disable-blink-features=AutomationControlled"]},
    ]
    last = None
    for spec in attempts:
        try:
            browser = pw.chromium.launch(**spec)
            name = spec.get("channel") or "playwright-chromium"
            log("info", f"Browser: {name}  headless={headless}", "")
            return browser
        except Exception as exc:
            last = exc
            log("warn", f"Could not launch {spec.get('channel') or 'chromium'}: {exc}", "")
    raise RuntimeError(f"Could not launch Chrome, Edge, or Chromium: {last}")


def _bind_page(page, evidence, consoles: list) -> None:
    def on_console(msg):
        try:
            consoles.append(f"{msg.type}: {msg.text}")
            if evidence:
                evidence.event("console", msg.text, extra={"type": msg.type})
        except Exception:
            pass

    def on_pageerror(err):
        if evidence:
            try:
                evidence.event("pageerror", str(err), level="error")
            except Exception:
                pass

    def on_crash(_page):
        if evidence:
            evidence.event("crash", "Page crashed", level="error")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("crash", on_crash)


def _close_page(page, log: LogFn) -> None:
    if page is None:
        return
    try:
        page.close()
    except Exception as exc:
        log("warn", f"Page close: {exc}", "")


def run_live(
    items,
    mode,
    log: LogFn,
    stopped: StopFn,
    on_item,
    headless: bool,
    evidence: Evidence | None = None,
    full_dom: bool = False,
    captcha_fn=None,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Use run.bat or: pip install playwright && python -m playwright install chromium") from exc

    from .portal import (
        PortalError,
        ack_caution,
        checker_certify_batch,
        close_scheme_notice,
        login_with_captcha,
        logout,
        maker_process_claim,
        restore_named_iframe,
    )
    from .sop import PORTAL_URL

    log = _wrap_log(log, evidence)
    runnable = [i for i in items if i.get("status") == "queued"]
    groups = group_by_mli(runnable)
    log("info", f"LIVE run started · {len(runnable)} claim(s) · {len(groups)} MLI(s) · mode {mode} · headless={headless}", "")
    if evidence:
        log("info", f"Output pack: {getattr(evidence, 'root', evidence.dir)}", "")
    consoles: list[str] = []

    def fatal(msg: str) -> bool:
        text = msg.lower()
        return "has been closed" in text or "target page" in text or "browser has been closed" in text

    with sync_playwright() as pw:
        browser = _launch_browser(pw, headless, log)
        ctx_kwargs = {"viewport": {"width": 1440, "height": 900}, "ignore_https_errors": True}
        context = browser.new_context(**ctx_kwargs)
        tracing = False

        page = context.new_page()
        try:
            context.set_default_timeout(25000)
            page.set_default_timeout(25000)
        except Exception:
            pass
        _bind_page(page, evidence, consoles)
        aborted = False
        try:
            for mli, group in groups.items():
                if stopped() or aborted:
                    break
                cred = group[0].get("credential") or {}
                maker_pw = cred.get("makerPasswords") or ([cred.get("makerPassword")] if cred.get("makerPassword") else [])
                checker_pw = cred.get("checkerPasswords") or ([cred.get("checkerPassword")] if cred.get("checkerPassword") else [])
                log("info", f"MLI {mli} · Maker {cred.get('makerUser')} · {len(group)} claim(s) · one login, then each claim", "")

                try:
                    if page.is_closed():
                        page = context.new_page()
                        _bind_page(page, evidence, consoles)
                    page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=45000)
                    close_scheme_notice(page)
                    log("ok", "Scheme notice closed (#exampleInfo1 / closePopup)", "")
                    if evidence:
                        evidence.capture_page(page, "01-portal-open", claim=mli, dom=full_dom)
                    login_with_captcha(
                        page, cred["mliCanonical"], cred["makerUser"], maker_pw, "Maker",
                        log, group[0]["claim"]["claimRef"], captcha_fn, evidence,
                    )
                    ack_caution(page)
                    if evidence:
                        evidence.capture_page(page, "02-maker-home", claim=mli, dom=full_dom)
                except Exception as exc:
                    msg = str(exc)
                    if evidence:
                        try:
                            evidence.capture_error(page, exc, "maker-login-failure", claim=mli)
                        except Exception:
                            pass
                    log("error", f"Maker login failed for MLI {mli}: {msg}", "")
                    for item in group:
                        on_item(item["claim"]["id"], {"status": "error", "message": f"Maker login failed: {msg}"})
                    if fatal(msg):
                        aborted = True
                        log("error", "Browser closed. Remaining claims stay queued.", "")
                        break
                    continue

                seen_refs: set[str] = set()
                for item in group:
                    if stopped() or aborted:
                        break
                    claim = item["claim"]
                    ref = (claim.get("claimRef") or "").strip().upper()
                    if ref in seen_refs:
                        on_item(claim["id"], {"status": "error", "phase": "maker", "message": "Duplicate claim ref — already processed this run"})
                        log("warn", "Duplicate claim ref — skipped", ref)
                        item["status"] = "error"
                        continue
                    seen_refs.add(ref)
                    on_item(claim["id"], {"status": "running", "phase": "maker"})
                    try:
                        result = maker_process_claim(page, item, mode, log, evidence=evidence, full_dom=full_dom)
                        on_item(claim["id"], result)
                        item["status"] = result.get("status", item.get("status"))
                        item["phase"] = result.get("phase", "")
                        item["message"] = result.get("message", "")
                        item["remark"] = result.get("remark", item.get("remark", ""))
                    except Exception as exc:
                        msg = str(exc)
                        if evidence:
                            try:
                                evidence.capture_error(page, exc, "maker-failure", claim=claim["claimRef"])
                            except Exception:
                                pass
                        on_item(claim["id"], {"status": "error", "message": msg})
                        item["status"] = "error"
                        log("error", msg, claim["claimRef"])
                        try:
                            from .portal import on_login_screen, restore_named_iframe
                            restore_named_iframe(page)
                            if on_login_screen(page):
                                log("error", "Login page again — remaining claims for this MLI are skipped", "")
                                for rest in group:
                                    if rest.get("status") == "queued" or rest["claim"]["id"] == claim["id"]:
                                        if rest["claim"]["id"] != claim["id"]:
                                            on_item(rest["claim"]["id"], {"status": "error", "message": "Session lost (login page)"})
                                            rest["status"] = "error"
                                break
                        except Exception:
                            pass
                        if fatal(msg):
                            aborted = True
                            break
                    else:
                        try:
                            from .portal import restore_named_iframe
                            restore_named_iframe(page)
                        except Exception:
                            pass

                try:
                    logout(page)
                    log("info", "Maker logged out", "")
                except Exception as exc:
                    log("warn", f"Maker logout: {exc}", "")
                if aborted or mode == "inspect":
                    continue
                needs = [it for it in group if it.get("status") == "done"]
                if not needs:
                    persist(evidence, items, f"MLI {mli} maker only")
                    if stopped():
                        break
                    continue
                if stopped():
                    log("warn", "Stop pressed — checker still running for this MLI", "")

                try:
                    if page.is_closed():
                        page = context.new_page()
                        _bind_page(page, evidence, consoles)
                    if page.get_by_text("Log in again").count():
                        page.get_by_text("Log in again").first.click()
                        page.wait_for_timeout(800)
                    else:
                        page.goto(PORTAL_URL, wait_until="domcontentloaded")
                    close_scheme_notice(page)
                    login_with_captcha(
                        page, cred["mliCanonical"], cred["checkerUser"], checker_pw, "Checker",
                        log, group[0]["claim"]["claimRef"], captcha_fn, evidence,
                    )
                    ack_caution(page)
                    restore_named_iframe(page)
                    if evidence:
                        evidence.capture_page(page, "08-checker-home", claim=mli, dom=full_dom)
                except Exception as exc:
                    msg = str(exc)
                    if evidence:
                        try:
                            evidence.capture_error(page, exc, "checker-login-failure", claim=mli)
                        except Exception:
                            pass
                    log("error", f"Checker login failed for MLI {mli}: {msg}", "")
                    for item in needs:
                        on_item(item["claim"]["id"], {"status": "done", "message": f"Maker forwarded. Checker login failed: {msg}"})
                    if fatal(msg):
                        aborted = True
                        break
                    persist(evidence, items, f"MLI {mli} checker login failed")
                    if stopped():
                        break
                    continue

                for item in needs:
                    on_item(item["claim"]["id"], {"phase": "checker"})
                try:
                    restore_named_iframe(page)
                    results = checker_certify_batch(page, needs, log, evidence=evidence, full_dom=full_dom)
                    for item in needs:
                        ref = (item["claim"].get("claimRef") or "").strip().upper()
                        result = results.get(ref) or {
                            "status": "done",
                            "phase": "checker",
                            "message": "Maker forwarded. Checker did not return a result",
                        }
                        on_item(item["claim"]["id"], result)
                        item["status"] = result.get("status", "done")
                        item["phase"] = result.get("phase", "checker")
                        item["message"] = result.get("message", "")
                        if result.get("phase") == "done":
                            log("ok", f"Done {ref}", ref)
                except Exception as exc:
                    msg = str(exc)
                    if evidence:
                        try:
                            evidence.capture_error(page, exc, "checker-failure", claim=mli)
                        except Exception:
                            pass
                    log("error", f"Checker batch: {msg}", "")
                    for item in needs:
                        on_item(item["claim"]["id"], {"status": "done", "phase": "checker", "message": f"Maker forwarded. Checker: {msg}"})
                    if fatal(msg):
                        aborted = True
                try:
                    logout(page)
                except Exception as exc:
                    log("warn", f"Checker logout: {exc}", "")
                persist(evidence, items, f"MLI {mli}")
                if stopped() or aborted:
                    break
        finally:
            if tracing and evidence:
                try:
                    context.tracing.stop(path=str(evidence.dir / "trace.zip"))
                    log("ok", "Trace saved: trace.zip", "")
                except Exception as exc:
                    log("warn", f"Trace stop: {exc}", "")
            try:
                if page is not None and not page.is_closed():
                    _close_page(page, log)
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    if evidence:
        try:
            evidence.write_json("browser-console.json", consoles[-200:])
        except Exception:
            pass
        evidence.finish(items, f"Live run complete. Pack: {evidence.root}")
    if stopped():
        log("warn", "Live run stopped.", "")
    elif aborted:
        log("error", "Live run aborted after a fatal browser error.", "")
    else:
        log("ok", "Live run finished.", "")

