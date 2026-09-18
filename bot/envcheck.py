from __future__ import annotations

import platform
import sys
from pathlib import Path


def _pkg(name: str) -> str:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        try:
            mod = __import__(name)
            return getattr(mod, "__version__", "present")
        except Exception:
            return "missing"


def collect_environment(bot_root: Path, screen: str = "", extra: dict | None = None) -> dict:
    files = []
    bot_dir = Path(bot_root) / "bot"
    if bot_dir.exists():
        for p in sorted(bot_dir.glob("*.py")):
            files.append({"name": p.name, "bytes": p.stat().st_size, "mtime": ""})
    return {
        "bot": {
            "name": "CGTMSE Resubmit Desk",
            "version": "1.7.0",
            "video": False,
            "root": str(bot_root),
            "frozen": getattr(sys, "frozen", False),
            "files": files,
            "screen": screen,
        },
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
        },
        "os": {
            "system": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "packages": {
            "openpyxl": _pkg("openpyxl"),
            "playwright": _pkg("playwright"),
        },
        "extra": extra or {},
    }


def format_environment(env: dict) -> str:
    bot = env.get("bot") or {}
    py = env.get("python") or {}
    return "\n".join(
        [
            f"{bot.get('name')}  v{bot.get('version')}",
            f"Python        {py.get('version')}  {py.get('implementation')}",
            f"Root          {bot.get('root')}",
        ]
    )
