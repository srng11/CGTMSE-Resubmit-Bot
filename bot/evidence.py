from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip())[:80] or "step"


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k).lower()
            if any(p in key for p in ("pass", "pwd", "captcha")):
                out[k] = "***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


class Evidence:
    def __init__(self, bot_root: Path):
        now = datetime.now()
        name = now.strftime("RESUBCL-%d-%m-%Y-%H-%M")
        self.root = Path(bot_root) / "output" / name
        self.dir = self.root / "evidence"
        for sub in ("screenshots", "dom", "page"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        (self.root / "result").mkdir(parents=True, exist_ok=True)
        self.seq = 0
        self.log_path = self.root / "reports" / "log.txt"
        self.events_path = self.root / "reports" / "events.jsonl"
        self.log_path.write_text("", encoding="utf-8")
        readme = (
            "CGTMSE Resubmit Desk output pack\n"
            f"Folder: {self.root}\n"
            "result/   RESULT.csv and SUMMARY.txt\n"
            "evidence/ screenshots, iframe HTML\n"
            "reports/  log, events, environment\n"
        )
        (self.root / "README.txt").write_text(readme, encoding="utf-8")
        (self.root / "reports" / "README.txt").write_text(readme, encoding="utf-8")

    def event(self, kind: str, title: str, level: str = "info", claim: str = "", extra: dict | None = None) -> None:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "kind": kind,
            "level": level,
            "title": title,
            "claim": claim,
            "extra": extra or {},
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if kind not in {"console"}:
            stamp = rec["ts"]
            line = f"{stamp}  {level.upper():<6} {('[' + claim + '] ') if claim else ''}{title}\n"
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def write_json(self, name: str, data: Any) -> None:
        (self.root / "reports" / name).write_text(
            json.dumps(_redact(data), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def inspect_page(self, page) -> dict[str, Any]:
        info: dict[str, Any] = {"url": "", "title": "", "frames": [], "inputs": [], "buttons": []}
        try:
            info["url"] = page.url
            info["title"] = page.title()
        except Exception as exc:
            info["page_error"] = str(exc)
        try:
            for fr in page.frames:
                info["frames"].append({"name": fr.name, "url": fr.url, "title": ""})
        except Exception:
            pass
        try:
            frame = page.frame(name="content")
            if frame:
                info["iframe_text"] = (frame.locator("body").inner_text(timeout=1500) or "")[:4000]
                info["inputs"] = frame.evaluate(
                    """() => [...document.querySelectorAll('input,select,textarea,button')].slice(0,80).map(el => ({
                        tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || '',
                        value: (el.value || el.innerText || '').slice(0,80),
                        visible: !!(el.offsetWidth || el.offsetHeight)
                    }))"""
                )
                info["buttons"] = [x for x in info["inputs"] if (x.get("type") in ("button", "submit") or x.get("tag") == "BUTTON")]
        except Exception:
            pass
        return info

    def capture_page(self, page, title: str, claim: str = "", dom: bool = False, full_page: bool = False) -> None:
        self.seq += 1
        slug = f"{self.seq:03d}_{_safe(claim)}_{_safe(title)}" if claim else f"{self.seq:03d}_{_safe(title)}"
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
        errorish = "ERROR" in title.upper() or "error" in title.lower() or dom
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
                except Exception:
                    pass
                try:
                    text = fr.locator("body").inner_text(timeout=1500)
                    (self.dir / "page" / f"{slug}.{name}.txt").write_text(text, encoding="utf-8")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            state = self.inspect_page(page)
            (self.dir / "page" / f"{slug}.json").write_text(
                json.dumps(_redact(state), indent=2, ensure_ascii=False), encoding="utf-8"
            )
            extra["page_json"] = f"{slug}.json"
            extra["iframe_text"] = (state.get("iframe_text") or "")[:800]
        except Exception:
            pass
        self.event("capture", title, claim=claim, extra=extra)

    def capture_error(self, page, exc: Exception, title: str, claim: str = "") -> None:
        self.capture_page(page, f"ERROR_{title}", claim=claim, dom=True)
        self.event("error", f"{title}: {exc}", level="error", claim=claim)

    def finish(self, items: list, note: str = "") -> None:
        from .report import write_result, write_summary

        write_result(self.root / "result" / "RESULT.csv", items)
        write_summary(self.root / "result" / "SUMMARY.txt", items, str(self.root), note=note)
        try:
            self.write_json("queue.json", items)
        except Exception:
            pass
        self.event("finish", note or "Run finished")
