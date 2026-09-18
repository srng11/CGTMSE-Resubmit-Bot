"""Run evidence pack for debugging and troubleshooting."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import export_csv


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:80] or "step"


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k).lower()
            if "pass" in key or "secret" in key or "pwd" in key:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


class Evidence:
    def __init__(self, bot_root: Path) -> None:
        now = datetime.now()
        # Windows cannot use ':' in a folder name — hh-mm stands in for hh:mm.
        stamp = now.strftime("RESUBCL-%d-%m-%Y-%H-%M")
        root = Path(bot_root) / "output" / stamp
        n = 2
        while root.exists():
            root = Path(bot_root) / "output" / f"{stamp}-{n}"
            n += 1
        self.root = root
        self.dir = root / "evidence"
        self.result_dir = root / "result"
        self.reports_dir = root / "reports"
        (self.dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (self.dir / "dom").mkdir(exist_ok=True)
        (self.dir / "page").mkdir(exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.seq = 0
        self.events_path = self.reports_dir / "events.jsonl"
        self.log_path = self.reports_dir / "log.txt"
        self.event("session", "start", extra={"folder": str(self.root)})

    def event(self, kind: str, title: str, level: str = "info", claim: str = "", extra: dict | None = None) -> None:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "seq": self.seq,
            "kind": kind,
            "level": level,
            "title": title,
            "claim": claim,
            "extra": _redact(extra or {}),
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        line = f"{rec['ts']}  {level.upper():5}  {('['+claim+'] ') if claim else ''}{title}\n"
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def write_json(self, name: str, data: Any) -> Path:
        path = self.reports_dir / name
        path.write_text(json.dumps(_redact(data), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def inspect_page(self, page) -> dict:
        info: dict[str, Any] = {"url": "", "title": "", "frames": [], "iframe_text": "", "inputs": [], "buttons": []}
        try:
            info["url"] = page.url
            info["title"] = page.title()
        except Exception as exc:
            info["page_error"] = str(exc)
        try:
            for fr in page.frames:
                rec = {"name": fr.name, "url": fr.url}
                try:
                    rec["title"] = fr.title()
                except Exception:
                    rec["title"] = ""
                info["frames"].append(rec)
        except Exception as exc:
            info["frames_error"] = str(exc)
        frame = None
        try:
            frame = page.frame(name="content")
        except Exception:
            frame = None
        if frame is None:
            try:
                for fr in page.frames:
                    if fr != page.main_frame:
                        frame = fr
                        break
            except Exception:
                frame = None
        if frame is not None:
            try:
                info["iframe_text"] = (frame.locator("body").inner_text(timeout=1500) or "")[:4000]
            except Exception as exc:
                info["iframe_text_error"] = str(exc)
            try:
                info["inputs"] = frame.evaluate(
                    """() => [...document.querySelectorAll('input,select,textarea')].slice(0, 80).map(el => ({
                        tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || '',
                        value: (el.type === 'password') ? '[REDACTED]' : String(el.value || '').slice(0, 80),
                        visible: !!(el.offsetWidth || el.offsetHeight)
                    }))"""
                )
            except Exception as exc:
                info["inputs_error"] = str(exc)
            try:
                info["buttons"] = frame.evaluate(
                    """() => [...document.querySelectorAll('input[type=submit],input[type=button],button')].slice(0, 40).map(el => ({
                        tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || '',
                        value: String(el.value || el.innerText || '').slice(0, 80),
                        visible: !!(el.offsetWidth || el.offsetHeight)
                    }))"""
                )
            except Exception as exc:
                info["buttons_error"] = str(exc)
        return info

    def capture_page(self, page, title: str, claim: str = "", dom: bool = False, full_page: bool = False) -> None:
        self.seq += 1
        slug = f"{self.seq:03d}_{_safe(title)}"
        extra: dict[str, Any] = {"url": "", "page": ""}
        try:
            extra["url"] = page.url
            extra["page"] = page.title()
        except Exception as exc:
            extra["page_error"] = str(exc)
        try:
            shot = self.dir / "screenshots" / f"{slug}.png"
            page.screenshot(path=str(shot), full_page=full_page)
            extra["screenshot"] = shot.name
        except Exception as exc:
            extra["screenshot_error"] = str(exc)
        try:
            loc = page.locator("#contentFrame")
            if loc.count() > 0:
                iframe_shot = self.dir / "screenshots" / f"{slug}.iframe.png"
                loc.first.screenshot(path=str(iframe_shot), timeout=1500)
                extra["iframe_screenshot"] = iframe_shot.name
        except Exception:
            pass
        errorish = "ERROR" in title.upper() or dom
        if errorish:
            try:
                (self.dir / "dom" / f"{slug}.html").write_text(page.content(), encoding="utf-8")
                extra["dom"] = f"{slug}.html"
            except Exception as exc:
                extra["dom_error"] = str(exc)
        try:
            for i, fr in enumerate(page.frames):
                if fr == page.main_frame:
                    continue
                name = _safe(fr.name or f"frame{i}")
                try:
                    (self.dir / "dom" / f"{slug}.{name}.html").write_text(fr.content(), encoding="utf-8")
                    extra.setdefault("frame_dom", []).append(f"{slug}.{name}.html")
                except Exception as exc:
                    extra.setdefault("frame_dom_error", []).append(str(exc))
                try:
                    text = fr.locator("body").inner_text(timeout=1500)
                    (self.dir / "page" / f"{slug}.{name}.txt").write_text(text, encoding="utf-8")
                    extra.setdefault("frame_text", []).append(f"{slug}.{name}.txt")
                except Exception:
                    pass
        except Exception as exc:
            extra["frames_error"] = str(exc)
        try:
            state = self.inspect_page(page)
            (self.dir / "page" / f"{slug}.json").write_text(
                json.dumps(_redact(state), indent=2, ensure_ascii=False), encoding="utf-8"
            )
            extra["page_json"] = f"{slug}.json"
            extra["iframe_text"] = (state.get("iframe_text") or "")[:800]
            extra["frame_urls"] = [f.get("url") for f in (state.get("frames") or [])]
            extra["buttons"] = state.get("buttons") or []
        except Exception as exc:
            extra["inspect_error"] = str(exc)
        self.event("capture", title, claim=claim, extra=extra)

    def capture_error(self, page, err: Exception, title: str, claim: str = "") -> None:
        import traceback

        extra = {
            "error": str(err),
            "type": type(err).__name__,
            "traceback": traceback.format_exc()[-4000:],
        }
        try:
            extra["url"] = page.url
            extra["page"] = page.title()
            state = self.inspect_page(page)
            extra["iframe_text"] = (state.get("iframe_text") or "")[:2000]
            extra["frames"] = state.get("frames") or []
            extra["buttons"] = state.get("buttons") or []
            extra["body_excerpt"] = extra["iframe_text"] or page.locator("body").inner_text()[:2000]
        except Exception as inner:
            extra["page_meta_error"] = str(inner)
        self.event("error", title, level="error", claim=claim, extra=extra)
        try:
            self.capture_page(page, f"ERROR_{title}", claim=claim, dom=True, full_page=True)
        except Exception as inner:
            self.event("error", f"Could not screenshot {title}: {inner}", level="error", claim=claim)

    def save_video(self, page, stem: str) -> Path | None:
        """Close is not done here — caller closes the page first, then we rename the webm."""
        dest = self.dir / "video" / f"{_safe(stem)}.webm"
        try:
            video = getattr(page, "video", None)
            if video is None:
                return None
            src = Path(video.path())
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.unlink()
                src.replace(dest)
                self.event("video", dest.name, extra={"bytes": dest.stat().st_size, "stem": stem})
                return dest
        except Exception as exc:
            self.event("video", f"save failed: {exc}", level="warn", extra={"stem": stem})
        return None

    def finish(self, queue: list[dict], summary: str) -> None:
        export_csv(self.result_dir / "RESULT.csv", queue)
        export_csv(self.reports_dir / "report.csv", queue)
        slim = []
        counts = {"done": 0, "error": 0, "queued": 0, "running": 0, "other": 0}
        for item in queue:
            claim = item.get("claim") or {}
            cred = item.get("credential") or {}
            st = str(item.get("status") or "other")
            if st not in counts:
                st = "other"
            counts[st] += 1
            slim.append(
                {
                    "claimRef": claim.get("claimRef"),
                    "mli": claim.get("mliCanonical") or claim.get("mliId"),
                    "maker": cred.get("makerUser"),
                    "checker": cred.get("checkerUser"),
                    "status": item.get("status"),
                    "phase": item.get("phase"),
                    "message": item.get("message"),
                    "remark": item.get("remark"),
                }
            )
        self.write_json("queue.json", slim)
        summary_txt = "\n".join(
            [
                "CGTMSE Resubmit Desk — RESULT",
                f"Folder: {self.root}",
                f"Time:   {datetime.now().isoformat(timespec='seconds')}",
                "",
                f"Total    {len(queue)}",
                f"Done     {counts.get('done', 0)}",
                f"Error    {counts.get('error', 0)}",
                f"Queued   {counts.get('queued', 0)}",
                f"Running  {counts.get('running', 0)}",
                "",
                summary,
                "",
            ]
        )
        (self.result_dir / "SUMMARY.txt").write_text(summary_txt, encoding="utf-8")
        readme = "\n".join(
            [
                "CGTMSE Resubmit Desk — run pack",
                f"Folder: {self.root}",
                "",
                "result/RESULT.csv     claim-wise result table",
                "result/SUMMARY.txt    counts and outcome",
                "reports/              log, events, environment, queue",
                "evidence/screenshots  window PNG + .iframe.png (centre form)",
                "evidence/dom          iframe HTML (parent HTML on errors)",
                "evidence/page         page.json, iframe text, inputs, buttons",
                "evidence/video        live Chrome recording (.webm)",
                "evidence/trace.zip    only if Capture full HTML is ticked",
                "evidence/screenshots  parent + iframe PNG",
                "evidence/dom          parent HTML + each iframe HTML",
                "evidence/page         JSON: frames, inputs, buttons, iframe text",
                "evidence/video        live Chrome recording (.webm)",
                "evidence/trace.zip    Playwright trace (if captured)",
                "",
                summary,
                "",
            ]
        )
        (self.root / "README.txt").write_text(readme, encoding="utf-8")
        (self.reports_dir / "README.txt").write_text(readme, encoding="utf-8")
        self.event("session", "finish", extra={"summary": summary, "folder": str(self.root)})
