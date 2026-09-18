"""Self and environment awareness for troubleshooting."""

from __future__ import annotations

import os
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

from .sop import PORTAL_URL


def _pkg_ver(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        try:
            mod = __import__(name)
            return getattr(mod, "__version__", "present")
        except Exception:
            return "not installed"


def _disk_free(path: Path) -> str:
    try:
        usage = os.statvfs(path) if hasattr(os, "statvfs") else None
        if usage:
            free = usage.f_bavail * usage.f_frsize
            return f"{free / (1024 ** 3):.1f} GB"
    except Exception:
        pass
    try:
        import shutil

        free = shutil.disk_usage(path).free
        return f"{free / (1024 ** 3):.1f} GB"
    except Exception as exc:
        return str(exc)


def _portal() -> dict:
    out = {"url": PORTAL_URL, "dns": "", "http": "", "ok": False}
    host = "inter.cgtmse.in"
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        out["dns"] = ", ".join(sorted({i[4][0] for i in infos}))
    except Exception as exc:
        out["dns"] = f"fail: {exc}"
        return out
    try:
        import urllib.request

        req = urllib.request.Request(PORTAL_URL, method="GET", headers={"User-Agent": "CGTMSE-Resubmit-Desk/1.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            out["http"] = f"{resp.status} {resp.reason}"
            out["ok"] = resp.status < 500
    except Exception as exc:
        out["http"] = str(exc)
    return out


def _playwright() -> dict:
    info = {"package": _pkg_ver("playwright"), "import": False, "chromium": "unknown", "chrome_channel": []}
    for path in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ):
        if Path(path).exists():
            info["chrome_channel"].append(path)
    try:
        from playwright.sync_api import sync_playwright

        info["import"] = True
        with sync_playwright() as pw:
            path = pw.chromium.executable_path
            info["chromium"] = path
            info["chromium_present"] = Path(path).exists()
            info["browsers"] = [b.name for b in pw.browsers] if hasattr(pw, "browsers") else []
    except Exception as exc:
        info["chromium"] = str(exc)
        info["chromium_present"] = False
    return info


def _machine() -> dict:
    out: dict = {
        "cpu_count": os.cpu_count(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "locale": "",
        "ram": "",
    }
    try:
        import locale

        out["locale"] = locale.getdefaultlocale()[0] or ""
    except Exception:
        pass
    try:
        if sys.platform.startswith("win"):
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            out["ram"] = f"{stat.ullTotalPhys / (1024 ** 3):.1f} GB  ({stat.dwMemoryLoad}% in use)"
        else:
            pages = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            out["ram"] = f"{pages / (1024 ** 3):.1f} GB"
    except Exception as exc:
        out["ram"] = str(exc)
    return out


def _bot_files(root: Path) -> list[dict]:
    rows = []
    for p in sorted((root / "bot").glob("*.py")) if (root / "bot").is_dir() else []:
        st = p.stat()
        rows.append({"name": p.name, "bytes": st.st_size, "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    for name in ("dashboard.py", "launcher.py", "requirements.txt"):
        p = root / name
        if p.exists():
            st = p.stat()
            rows.append({"name": name, "bytes": st.st_size, "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return rows


def collect_environment(bot_root: Path | None = None, screen: str = "", extra: dict | None = None) -> dict:
    root = Path(bot_root) if bot_root else Path.cwd()
    now = datetime.now().astimezone()
    env = {
        "bot": {
            "name": "CGTMSE Resubmit Desk",
            "version": "1.6.0",
            "root": str(root.resolve()),
            "frozen": bool(getattr(sys, "frozen", False)),
            "files": _bot_files(root),
        },
        "time": {
            "local": now.isoformat(timespec="seconds"),
            "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tz": str(now.tzinfo),
        },
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "prefix": sys.prefix,
            "venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
            "path0": sys.path[0] if sys.path else "",
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
            **_machine(),
        },
        "display": {
            "tk": screen or "n/a",
        },
        "disk_free": _disk_free(root),
        "packages": {
            "openpyxl": _pkg_ver("openpyxl"),
            "playwright": _pkg_ver("playwright"),
        },
        "playwright": _playwright(),
        "portal": _portal(),
        "cwd": os.getcwd(),
        "run": extra or {},
    }
    return env


def format_environment(env: dict) -> str:
    bot = env["bot"]
    py = env["python"]
    osinfo = env["os"]
    pw = env["playwright"]
    portal = env["portal"]
    lines = [
        f"{bot['name']}  v{bot['version']}",
        f"Root          {bot['root']}",
        f"Frozen EXE    {bot['frozen']}",
        "",
        f"Local time    {env['time']['local']}  ({env['time']['tz']})",
        f"UTC           {env['time']['utc']}",
        "",
        f"Python        {py['version']}  {py['implementation']}",
        f"Executable    {py['executable']}",
        f"Virtual env   {py['venv']}",
        "",
        f"OS            {osinfo['system']} {osinfo['release']}  {osinfo['machine']}",
        f"Host          {osinfo['hostname']}",
        f"User          {osinfo.get('user') or '—'}",
        f"CPU           {osinfo.get('cpu_count')}",
        f"RAM           {osinfo.get('ram') or '—'}",
        f"Locale        {osinfo.get('locale') or '—'}",
        f"Display       {env['display']['tk']}",
        f"Disk free     {env['disk_free']}",
        f"Working dir   {env['cwd']}",
        "",
        f"openpyxl      {env['packages']['openpyxl']}",
        f"playwright    {env['packages']['playwright']}  import={pw['import']}",
        f"Chromium      {pw.get('chromium')}",
        f"Chrome/Edge   {', '.join(pw.get('chrome_channel') or []) or 'not found'}",
        "",
        f"Portal        {portal['url']}",
        f"DNS           {portal['dns']}",
        f"HTTP          {portal['http']}",
        f"Reachable     {portal['ok']}",
        "",
    ]
    run = env.get("run") or {}
    if run:
        lines.append("Run")
        for k, v in run.items():
            lines.append(f"  {k:12} {v}")
        lines.append("")
    lines += [
        "Passwords are never written to evidence.",
    ]
    return "\n".join(lines)
