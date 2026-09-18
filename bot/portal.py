"""CGTMSE portal steps for returned first-instalment claims."""

from __future__ import annotations

from typing import Callable

from .sop import CHECKER_LIST, PORTAL_URL

LogFn = Callable[[str, str, str], None]


class PortalError(RuntimeError):
    pass


RETURNED_FORM = "displayClaimDetailsInput.do?method=displayClaimDetailsInput"


def _snap(evidence, page, title: str, claim: str, log: LogFn, dom: bool = False) -> None:
    if evidence is None:
        return
    try:
        evidence.capture_page(page, title, claim=claim, dom=dom)
    except Exception as exc:
        log("warn", f"Screenshot failed ({title}): {exc}", claim)


def _iframe(page):
    return page.frame_locator("#contentFrame")


def _bind_content(page) -> None:
    page.evaluate(
        """() => {
            const f = document.getElementById('contentFrame') || document.querySelector('iframe[name="content"]');
            if (f) { try { window.content = f.contentWindow; } catch (e) {} }
        }"""
    )


def restore_named_iframe(page) -> str:
    try:
        return page.evaluate(
            """() => {
                const f = document.getElementById('contentFrame') || document.querySelector('iframe[name="content"]');
                if (!f) return 'no-iframe';
                try { window.content = f.contentWindow; } catch (e) { return String(e); }
                return 'ok';
            }"""
        ) or "ok"
    except Exception as exc:
        return str(exc)


def _goto_iframe(page, url: str) -> None:
    restore_named_iframe(page)
    page.evaluate(
        """(url) => {
            const path = url.startsWith('/') ? url : '/' + url;
            const f = document.getElementById('contentFrame') || document.querySelector('iframe[name="content"]');
            if (!f) return 'no-iframe';
            try { window.content = f.contentWindow; } catch (e) {}
            try { f.contentWindow.location.href = path; return 'ok'; } catch (e) { return String(e); }
        }""",
        url,
    )


def _back_to_search(page) -> None:
    restore_named_iframe(page)
    try:
        if _iframe(page).locator("input[name=clmRefNumberNew]").first.is_visible(timeout=300):
            return
    except Exception:
        pass
    try:
        page.evaluate(
            """(url) => {
                const path = url.startsWith('/') ? url : '/' + url;
                const f = document.getElementById('contentFrame') || document.querySelector('iframe[name="content"]');
                if (!f) return 'no-iframe';
                try { window.content = f.contentWindow; } catch (e) {}
                try { f.contentWindow.location.href = path; return 'ok'; } catch (e) { return String(e); }
            }""",
            RETURNED_FORM,
        )
        _iframe(page).locator("input[name=clmRefNumberNew]").first.wait_for(state="visible", timeout=5000)
    except Exception:
        pass
    restore_named_iframe(page)


def on_login_screen(page) -> bool:
    try:
        loc = page.locator("#memberId1")
        return bool(loc.count() and loc.first.is_visible())
    except Exception:
        return False


def close_scheme_notice(page) -> None:
    try:
        page.evaluate(
            """() => {
                if (typeof closePopup === 'function') closePopup();
                const a = document.getElementById('exampleInfo1');
                if (a) { a.style.display = 'none'; a.classList.remove('show'); }
            }"""
        )
    except Exception:
        pass


def _login_state(page) -> str:
    try:
        if page.locator("#ackCaution").count() and page.locator("#ackCaution").first.is_visible():
            return "ok"
    except Exception:
        pass
    title = ""
    body = ""
    try:
        title = (page.title() or "")
        body = page.locator("body").inner_text()[:2000]
    except Exception:
        pass
    blob = f"{title}\n{body}".lower()
    if "log out" in blob or "claims processing" in blob:
        return "ok"
    if "invalid password" in blob or title.strip().lower() == "error message":
        return "bad"
    if on_login_screen(page):
        return "login"
    return "ok"


def _click_ok(page) -> None:
    for loc in (
        page.get_by_role("link", name="Ok"),
        page.locator("input[value='Ok'], input[value='OK']"),
        page.get_by_text("Ok", exact=True),
    ):
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=3000)
                return
        except Exception:
            continue


def recover_login_form(page, log: LogFn | None = None, claim_ref: str = "") -> None:
    if _login_state(page) == "bad" or not on_login_screen(page):
        if log:
            log("warn", "Invalid password — returning to login", claim_ref)
        _click_ok(page)
        page.wait_for_timeout(200)
        if not on_login_screen(page):
            page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_selector("#memberId1", timeout=20000)
    close_scheme_notice(page)


def login_with_captcha(page, member_id: str, user: str, passwords: list[str], role: str, log: LogFn, claim_ref: str, captcha_fn=None, evidence=None) -> int:
    if not passwords:
        raise PortalError(f"{role} password missing")
    page.wait_for_selector("#memberId1", timeout=20000)
    close_scheme_notice(page)
    last = "login"
    for i, pwd in enumerate(passwords, 1):
        source = "Excel" if i == 1 else f"fallback {i - 1}"
        log("info", f"{role} sign-in · {user} · {source}", claim_ref)
        recover_login_form(page, log, claim_ref)
        page.fill("#memberId1", member_id)
        page.fill("#userId", user)
        page.fill("#passwd", pwd)
        try:
            page.locator("#checkAgree").check(force=True, timeout=4000)
        except Exception:
            page.evaluate("() => { const el = document.getElementById('checkAgree'); if (el && !el.checked) el.click(); }")
        btn = page.locator("button.login-button")
        if btn.count():
            btn.first.click(force=True)
        else:
            page.get_by_role("button", name="Sign In").click(force=True)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(200)
        last = _login_state(page)
        if last == "ok":
            log("ok", f"Signed in as {user}", claim_ref)
            return i
        if last == "bad":
            log("warn", f"{source} rejected", claim_ref)
            if evidence is not None:
                _snap(evidence, page, f"invalid-password-{source}", claim_ref, log)
            recover_login_form(page, log, claim_ref)
            continue
        if on_login_screen(page):
            log("warn", "Still on login. If a captcha is shown, type it in the browser.", claim_ref)
            page.wait_for_timeout(5000)
            if _login_state(page) == "ok":
                log("ok", f"Signed in as {user}", claim_ref)
                return i
    raise PortalError(f"{role} login failed after {len(passwords)} password(s). Last state: {last}")


def ack_caution(page) -> None:
    try:
        box = page.locator("#ackCaution")
        if box.count():
            box.check(force=True)
            page.locator("#closeBtn").click(timeout=5000)
            page.wait_for_timeout(200)
            return
    except Exception:
        pass
    close_scheme_notice(page)


def _select(page, name: str, label: str, log: LogFn, ref: str) -> None:
    sel = page.locator(f"select[name='{name}']").first
    sel.wait_for(state="attached", timeout=8000)
    idx = page.evaluate(
        """({ name, label }) => {
            const s = document.querySelector(`select[name="${name}"]`);
            if (!s) return -1;
            s.disabled = false;
            s.removeAttribute('disabled');
            const want = label.replace(/\\s+/g, ' ').trim().toLowerCase();
            return [...s.options].findIndex(o => (o.text || '').replace(/\\s+/g, ' ').trim().toLowerCase().includes(want));
        }""",
        {"name": name, "label": label},
    )
    if idx is None or int(idx) < 0:
        raise PortalError(f"{name}: '{label}' not found")
    sel.select_option(index=int(idx), timeout=5000)
    page.evaluate(
        """(name) => {
            const s = document.querySelector(`select[name="${name}"]`);
            const f = document.getElementById('contentFrame');
            if (f) { try { window.content = f.contentWindow; } catch (e) {} }
            s.dispatchEvent(new Event('change', { bubbles: true }));
            try {
                if (name === 'MainMenu' && typeof setSubMenuOptions === 'function') setSubMenuOptions(s, '');
                if (name === 'SubMenu' && typeof doActionForSelection === 'function') doActionForSelection(s, '');
            } catch (e) {}
        }""",
        name,
    )
    log("ok", f"{name}: {label}", ref)
    page.wait_for_timeout(250)


def open_claims_menu(page, main_label: str, sub_label: str, log: LogFn, ref: str) -> None:
    _bind_content(page)
    try:
        page.evaluate(
            """() => {
                const f = document.getElementById('contentFrame');
                if (f) { try { window.content = f.contentWindow; } catch (e) {} }
                if (typeof setMenuOptions === 'function') setMenuOptions('CP', '');
            }"""
        )
        log("ok", "Claims Processing", ref)
    except Exception as exc:
        log("warn", f"Claims Processing: {exc}", ref)
        page.locator("div.schemes", has_text="Claims").first.click(timeout=4000)
    try:
        page.wait_for_function(
            "() => { const s = document.querySelector('select[name=MainMenu]'); return s && !s.disabled && s.options.length > 1; }",
            timeout=5000,
        )
    except Exception:
        pass
    _select(page, "MainMenu", main_label, log, ref)
    if sub_label:
        try:
            page.wait_for_function(
                "() => { const s = document.querySelector('select[name=SubMenu]'); return s && s.options.length > 1; }",
                timeout=5000,
            )
        except Exception:
            pass
        _select(page, "SubMenu", sub_label, log, ref)
        if "Returned" in sub_label:
            page.evaluate(
                """(url) => {
                    const path = url.startsWith('/') ? url : '/' + url;
                    const f = document.getElementById('contentFrame');
                    if (!f) return;
                    try { window.content = f.contentWindow; } catch (e) {}
                    f.contentWindow.location.href = path;
                }""",
                RETURNED_FORM,
            )
    else:
        page.evaluate(
            """() => {
                const s = document.querySelector('select[name=MainMenu]');
                const f = document.getElementById('contentFrame');
                if (f) { try { window.content = f.contentWindow; } catch (e) {} }
                try { if (typeof doActionForSelection === 'function') doActionForSelection(s, ''); } catch (e) {}
            }"""
        )


def logout(page) -> None:
    try:
        page.get_by_text("Log Out", exact=False).first.click(timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(300)


def _iframe_text(page) -> str:
    try:
        return _iframe(page).locator("body").inner_text()
    except Exception:
        return ""


def _fill_urn(page, urn: str) -> bool:
    for sel in ("input[name*='urn' i]", "input[id*='urn' i]", "#urnNumber", "input[name=urnNumber]"):
        try:
            loc = _iframe(page).locator(sel)
            if loc.count():
                loc.first.fill(urn)
                return True
        except Exception:
            continue
    return False


def _submit_btn(page):
    frame = _iframe(page)
    try:
        return frame.get_by_role("button", name="Submit").or_(frame.locator("input[type=submit], input[value=Submit]")).first
    except Exception:
        return frame.locator("input[type=submit], input[value=Submit], button:has-text('Submit')").first


def _wait_claim_form(page, claim: dict, log: LogFn, ref: str) -> dict:
    last = ""
    for _ in range(30):
        last = _iframe_text(page)
        low = last.lower()
        if "urn/uap not updated" in low:
            return {"ok": False, "message": "URN/UAP not updated", "text": last[:800]}
        if "no live account" in low or "have been closed" in low:
            return {"ok": False, "message": "No live account / loan closed", "text": last[:800]}
        if "can not be updated" in low or "cannot be updated" in low:
            return {
                "ok": False,
                "checker": True,
                "message": "Already forwarded / locked — checker will verify",
                "text": last[:800],
            }
        try:
            if _iframe(page).locator("#stateCode").first.is_visible(timeout=200):
                return {"ok": True, "text": last[:800]}
        except Exception:
            pass
        if "form for first instalment" in low:
            return {"ok": True, "text": last[:800]}
        page.wait_for_timeout(150)
    return {"ok": False, "message": (last[:240] or "Claim form did not open").strip(), "text": last[:800]}


def _option_labels(select_loc) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        opts = select_loc.locator("option")
        for i in range(opts.count()):
            t = (opts.nth(i).inner_text() or "").strip()
            v = (opts.nth(i).get_attribute("value") or t).strip()
            if v and t.lower() not in {"select", "--branch state--", ""}:
                out.append((v, t))
    except Exception:
        pass
    return out


def _fill_returned_form(page, claim: dict, log: LogFn, ref: str) -> str | None:
    """Fill state + legal. Return a skip reason, or None if ready to submit."""
    st = _iframe(page).locator("#stateCode")
    try:
        if st.count() and not (st.input_value() or "").strip():
            if claim.get("state"):
                st.select_option(label=claim["state"], timeout=2000)
            else:
                st.select_option(index=1, timeout=2000)
            log("ok", "Branch state set", ref)
    except Exception as exc:
        log("warn", f"State: {exc}", ref)

    legal = _iframe(page).locator("#idLegal")
    try:
        if legal.count() and not (legal.input_value() or "").strip():
            labels = _option_labels(legal)
            waiver = next((v for v, t in labels if "legal waiver" in f"{v} {t}".lower()), None)
            wanted = (claim.get("legalForum") or claim.get("legalWaiver") or "").strip()
            if waiver and (not wanted or "waiver" in wanted.lower()):
                legal.select_option(value=waiver, timeout=2000)
                try:
                    legal.dispatch_event("change")
                except Exception:
                    pass
                log("ok", "Legal Waiver selected", ref)
            elif wanted:
                match = next((v for v, t in labels if wanted.lower() in f"{v} {t}".lower()), None)
                attach = (claim.get("attachment") or "").strip()
                if not match:
                    return f"Legal forum '{wanted}' is not in the dropdown"
                if "waiver" not in wanted.lower() and not attach:
                    return "Legal Forum is not Legal Waiver; legal attachment required"
                legal.select_option(value=match, timeout=2000)
                try:
                    legal.dispatch_event("change")
                except Exception:
                    pass
                if attach:
                    from pathlib import Path
                    if Path(attach).is_file():
                        _iframe(page).locator("input[name=legalAttachmentPath]").first.set_input_files(attach)
                        log("ok", f"Legal forum {match} + attachment", ref)
                    else:
                        return f"Legal attachment not found: {attach}"
                else:
                    log("ok", f"Legal forum {match}", ref)
            else:
                attach = (claim.get("attachment") or "").strip()
                if not attach:
                    names = ", ".join(t for _, t in labels) or "(none)"
                    return f"Legal Forum is not Legal Waiver ({names}); legal attachment required"
                from pathlib import Path
                if not Path(attach).is_file():
                    return f"Legal attachment not found: {attach}"
                choice = labels[0][0] if labels else ""
                if not choice:
                    return "Legal Forum has no options"
                legal.select_option(value=choice, timeout=2000)
                try:
                    legal.dispatch_event("change")
                except Exception:
                    pass
                _iframe(page).locator("input[name=legalAttachmentPath]").first.set_input_files(attach)
                log("ok", f"Legal forum {choice} + attachment", ref)
    except Exception as exc:
        return f"Legal forum: {exc}"

    if claim.get("comment"):
        try:
            _iframe(page).locator("[name=mliCommentOnFinPosition]").fill(claim["comment"])
        except Exception:
            pass
    if claim.get("urn"):
        _fill_urn(page, claim["urn"])
    return None


def _click_submit(page) -> None:
    frame = _iframe(page)
    try:
        frame.locator("a[href*='addFirstClaimsPageDetails']").first.click(timeout=5000)
        return
    except Exception:
        pass
    frame.locator("img[alt='Submit']").first.click(timeout=5000)


def maker_process_claim(page, item: dict, mode: str, log: LogFn, evidence=None, full_dom: bool = False) -> dict:
    claim = item["claim"]
    ref = claim["claimRef"]
    try:
        return _maker_process_claim(page, item, mode, log, evidence, full_dom)
    finally:
        try:
            if not on_login_screen(page):
                _back_to_search(page)
        except Exception:
            restore_named_iframe(page)


def _maker_process_claim(page, item: dict, mode: str, log: LogFn, evidence=None, full_dom: bool = False) -> dict:
    claim = item["claim"]
    ref = claim["claimRef"]
    if on_login_screen(page):
        raise PortalError("Returned to the login page")
    search = _iframe(page).locator("input[name=clmRefNumberNew]").first
    try:
        ready = search.is_visible()
    except Exception:
        ready = False
    if not ready:
        open_claims_menu(page, "Claim For", "Update Returned Claim Info", log, ref)
        search = _iframe(page).locator("input[name=clmRefNumberNew]").first
        search.wait_for(state="visible", timeout=8000)
    log("ok", "Update Returned Claim Info", ref)
    _snap(evidence, page, "03-returned-form", ref, log, True)

    search.fill(ref)
    log("ok", f"Claim reference {ref}", ref)
    try:
        _iframe(page).locator("#okId").click(timeout=4000)
    except Exception:
        _iframe(page).locator("input[value='OK'], input[value='Ok']").first.click(timeout=4000)

    opened = _wait_claim_form(page, claim, log, ref)
    _snap(evidence, page, "04-claim-open", ref, log, True)
    if not opened["ok"]:
        log("warn", opened["message"], ref)
        if opened.get("checker"):
            return {
                "status": "done",
                "phase": "checker",
                "remark": opened["message"],
                "message": opened["message"],
            }
        return {"status": "error", "phase": "maker", "remark": opened["message"], "message": opened["message"]}

    log("ok", f"Opened {ref}", ref)
    remark = ""
    try:
        reds = _iframe(page).locator("font[color='red'], span.SubHeading, li")
        for i in range(min(reds.count(), 8)):
            t = reds.nth(i).inner_text().strip()
            if t and "welcome email" not in t.lower():
                remark = t[:400]
                break
    except Exception:
        remark = opened.get("text", "")[:400]
    if remark:
        log("info", f"Return remark: {remark}", ref)

    _fill_skip = _fill_returned_form(page, claim, log, ref)
    if _fill_skip:
        log("warn", _fill_skip, ref)
        return {"status": "error", "phase": "maker", "remark": remark, "message": _fill_skip}

    if mode == "inspect":
        _snap(evidence, page, "06-inspect-stop", ref, log, True)
        return {"status": "done", "phase": "done", "remark": remark, "message": "Inspect — submit skipped"}

    _click_submit(page)
    accept = _iframe(page).locator("input[value='Accept'], button:has-text('Accept'), img[alt='Accept']").first
    try:
        accept.wait_for(state="visible", timeout=10000)
    except Exception as exc:
        body = _iframe_text(page)
        raise PortalError(f"Accept did not appear after Submit. Iframe: {body[:400] or exc}") from exc
    accept.click(timeout=8000)
    page.wait_for_timeout(400)
    restore_named_iframe(page)
    body = _iframe_text(page)
    _snap(evidence, page, "07-maker-accepted", ref, log, True)
    low = (body or "").lower()
    if "already exist" in low:
        log("warn", "Term loan already on file — checker will verify", ref)
        return {
            "status": "done",
            "phase": "checker",
            "remark": remark,
            "message": "Term loan already on file — checker will verify",
        }
    if "please correct" in low and "forwarded" not in low:
        msg = (body or "Maker submit error")[:240].strip()
        log("error", msg, ref)
        return {"status": "error", "phase": "maker", "remark": remark, "message": msg}
    log("ok", "Forwarded to CGTMSE", ref)
    return {"status": "done", "phase": "checker", "remark": remark, "message": "Maker forwarded"}


def _arm_dialogs(page) -> None:
    def _on_dialog(dialog) -> None:
        try:
            dialog.accept()
        except Exception:
            try:
                dialog.dismiss()
            except Exception:
                pass

    try:
        page.on("dialog", _on_dialog)
    except Exception:
        pass


def _open_checker_list(page, log: LogFn, ref: str) -> None:
    restore_named_iframe(page)
    open_claims_menu(page, "Submission of claim", "", log, ref)
    _goto_iframe(page, CHECKER_LIST)
    try:
        _iframe(page).locator("input[name^='duCertifyDecisionYes']").first.wait_for(state="visible", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(800)
    restore_named_iframe(page)


def _tick_accept(page, ref: str) -> bool:
    frame = _iframe(page)
    sels = (
        f"input[name='duCertifyDecisionYes({ref})'][value='Y']",
        f"input[name='duCertifyDecisionYes({ref})']",
        f"input[value='Y'][name*='{ref}']",
    )
    for sel in sels:
        loc = frame.locator(sel)
        try:
            if loc.count():
                loc.first.click(force=True, timeout=5000)
                try:
                    loc.first.check(force=True, timeout=2000)
                except Exception:
                    pass
                return True
        except Exception:
            continue
    try:
        return bool(
            page.evaluate(
                """(ref) => {
                    const f = document.getElementById('contentFrame');
                    const d = f && (f.contentDocument || f.contentWindow.document);
                    if (!d) return false;
                    const nodes = [...d.querySelectorAll('input[type=radio], input[type=checkbox]')];
                    const el = nodes.find(n => (n.name || '').includes(ref) && String(n.value || 'Y') === 'Y')
                             || nodes.find(n => (n.name || '').includes(ref));
                    if (!el) return false;
                    el.disabled = false;
                    el.checked = true;
                    el.click();
                    el.dispatchEvent(new Event('click', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }""",
                ref,
            )
        )
    except Exception:
        return False


def _click_checker_save(page) -> str:
    """Click the Save picture / javascript submit. Never follow the Details.do href."""
    frame = _iframe(page)
    for sel in (
        "img[alt='Save']",
        "img[src*='Submit.gif']",
        "a[href*='javascript'][href*='submitForm']",
    ):
        try:
            loc = frame.locator(sel)
            if loc.count():
                loc.first.click(timeout=4000)
                return sel
        except Exception:
            continue
    try:
        return (
            page.evaluate(
                """() => {
                    const f = document.getElementById('contentFrame');
                    const d = f && (f.contentDocument || f.contentWindow.document);
                    if (!d) return 'no-doc';
                    const img = d.querySelector("img[alt='Save']") || d.querySelector("img[src*='Submit.gif']");
                    if (img) { (img.closest('a') || img).click(); return 'js-img'; }
                    const w = f.contentWindow;
                    if (w && typeof w.submitForm === 'function') {
                        try { w.submitForm('displayClaimProcessingSubmitDUDetails'); return 'submitForm'; }
                        catch (e) { return 'submitForm-fail'; }
                    }
                    return 'no-save';
                }"""
            )
            or "no-save"
        )
    except Exception as exc:
        return f"save-exc:{exc}"


def _checker_error_ok(page) -> None:
    frame = _iframe(page)
    try:
        frame.locator("img[src*='OK.gif'], img[alt='OK']").first.click(timeout=3000)
        page.wait_for_timeout(800)
        return
    except Exception:
        pass
    _goto_iframe(page, CHECKER_LIST)
    page.wait_for_timeout(800)


def _classify_checker_page(text: str) -> str:
    low = (text or "").lower()
    if "select atleast one" in low or "select at least one" in low or "accepet or reject" in low:
        return "no_tick"
    if "approved" in low or "has been certified" in low or "successfully" in low:
        return "ok"
    return "other"


def checker_certify_batch(page, items: list[dict], log: LogFn, evidence=None, full_dom: bool = False) -> dict[str, dict]:
    """Tick every listed claim at once, Save once. Returns claimRef -> result."""
    out: dict[str, dict] = {}
    if not items:
        return out
    refs = [(item["claim"].get("claimRef") or "").strip().upper() for item in items]
    ref0 = refs[0]
    restore_named_iframe(page)
    _arm_dialogs(page)
    _open_checker_list(page, log, ref0)
    _snap(evidence, page, "09-checker-list", ref0, log, True)

    ticked: list[str] = []
    for ref in refs:
        if _tick_accept(page, ref):
            ticked.append(ref)
            log("ok", f"ACCEPT ticked for {ref}", ref)
        else:
            log("warn", f"{ref} not on checker list", ref)
            out[ref] = {
                "status": "done",
                "phase": "checker",
                "message": "Maker forwarded. Not on checker list yet — certify by hand if needed",
            }
    if not ticked:
        return out

    page.wait_for_timeout(800)
    _snap(evidence, page, "09b-checker-ticked", ref0, log, True)
    how = _click_checker_save(page)
    log("info", f"Checker Save control: {how}", ref0)
    page.wait_for_timeout(1500)
    restore_named_iframe(page)
    text = _iframe_text(page)
    kind = _classify_checker_page(text)
    _snap(evidence, page, "10-checker-saved", ref0, log, True)

    if kind == "no_tick":
        log("warn", "Portal: select at least one — retry after OK", ref0)
        _checker_error_ok(page)
        _open_checker_list(page, log, ref0)
        for ref in ticked:
            _tick_accept(page, ref)
        page.wait_for_timeout(800)
        how = _click_checker_save(page)
        log("info", f"Checker Save retry: {how}", ref0)
        page.wait_for_timeout(1500)
        restore_named_iframe(page)
        text = _iframe_text(page)
        kind = _classify_checker_page(text)
        _snap(evidence, page, "10-checker-saved-retry", ref0, log, True)

    if kind == "ok":
        msg = "Complete — maker forwarded and checker certified"
        log("ok", "Checker certified the list", ref0)
        for ref in ticked:
            out[ref] = {"status": "done", "phase": "done", "message": msg}
        return out

    msg = f"Maker forwarded. Checker did not certify: {(text or '(blank page)')[:200].strip()}"
    log("error", msg, ref0)
    for ref in ticked:
        out[ref] = {"status": "done", "phase": "checker", "message": msg}
    return out


def checker_process_claim(page, item: dict, log: LogFn, evidence=None, full_dom: bool = False) -> dict:
    ref = (item["claim"].get("claimRef") or "").strip().upper()
    return checker_certify_batch(page, [item], log, evidence, full_dom).get(
        ref,
        {
            "status": "done",
            "phase": "checker",
            "message": "Maker forwarded. Checker did not return a result",
        },
    )
