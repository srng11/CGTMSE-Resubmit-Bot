#!/usr/bin/env python3
"""Launcher for CGTMSE Resubmit Desk."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

HERE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent

PAPER = "#F3EFE6"
NAVY = "#3B5368"
INK = "#2E3A47"
MUTED = "#6B7380"
WHITE = "#FFFFFF"


def py() -> str:
    return sys.executable


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CGTMSE Resubmit Desk")
        self.geometry("480x520")
        self.resizable(False, False)
        self.configure(bg=PAPER)
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=PAPER)
        s.configure("Navy.TFrame", background=NAVY)
        s.configure("TLabel", background=PAPER, foreground=INK)
        s.configure("Muted.TLabel", background=PAPER, foreground=MUTED, font=("Segoe UI", 10))
        s.configure("Title.TLabel", background=PAPER, foreground=NAVY, font=("Georgia", 22))
        s.configure("Navy.TLabel", background=NAVY, foreground=WHITE, font=("Segoe UI", 11))
        s.configure("TButton", background=WHITE, foreground=INK, padding=10, font=("Segoe UI", 10))
        s.configure("Navy.TButton", background=NAVY, foreground=WHITE, padding=12, font=("Segoe UI", 11))
        s.map("Navy.TButton", background=[("active", "#2F4456")])

        bar = ttk.Frame(self, style="Navy.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="CGTMSE  ·  Maker–Checker", style="Navy.TLabel").pack(padx=28, pady=16, anchor="w")

        ttk.Label(self, text="Resubmit Desk", style="Title.TLabel").pack(anchor="w", padx=36, pady=(36, 8))
        ttk.Label(self, text="Four screens: Files, Queue, Run, Report.\nClaim reference and MLI ID come from the claims workbook.", style="Muted.TLabel", justify="left").pack(anchor="w", padx=36)

        box = ttk.Frame(self)
        box.pack(fill="x", padx=36, pady=28)
        ttk.Button(box, text="Open desk", style="Navy.TButton", command=self.start_desk).pack(fill="x", pady=5)
        ttk.Button(box, text="Install / repair packages", command=self.install).pack(fill="x", pady=5)
        ttk.Button(box, text="Open templates folder", command=self.templates).pack(fill="x", pady=5)
        ttk.Button(box, text="Build EXE", command=self.build_exe).pack(fill="x", pady=5)
        ttk.Button(box, text="Exit", command=self.destroy).pack(fill="x", pady=5)

        self.status = ttk.Label(self, text=f"Python {sys.version.split()[0]}", style="Muted.TLabel")
        self.status.pack(anchor="w", padx=36, pady=8)

    def start_desk(self) -> None:
        dash = HERE / "dashboard.py"
        if getattr(sys, "frozen", False):
            import dashboard as dashmod
            self.withdraw()
            dashmod.main()
            self.deiconify()
            return
        if not dash.exists():
            messagebox.showerror("Launcher", f"Missing {dash}")
            return
        subprocess.Popen([py(), str(dash)], cwd=str(HERE))

    def install(self) -> None:
        req = HERE / "requirements.txt"
        if not req.exists():
            messagebox.showerror("Install", "requirements.txt not found.")
            return
        self.status.configure(text="Installing packages…")
        self.update_idletasks()
        try:
            subprocess.check_call([py(), "-m", "pip", "install", "-r", str(req)], cwd=str(HERE))
            subprocess.call([py(), "-m", "playwright", "install", "chromium"], cwd=str(HERE))
            self.status.configure(text="Packages installed.")
            messagebox.showinfo("Install", "Packages installed.")
        except subprocess.CalledProcessError as exc:
            messagebox.showerror("Install", str(exc))
            self.status.configure(text="Install failed.")

    def templates(self) -> None:
        folder = HERE / "templates"
        folder.mkdir(exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def build_exe(self) -> None:
        bat = HERE / "build_exe.bat"
        if sys.platform.startswith("win") and bat.exists():
            subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(HERE))
            messagebox.showinfo("Build EXE", "build_exe.bat started.")
            return
        messagebox.showinfo("Build EXE", "On Windows, double-click build_exe.bat.")


def main() -> None:
    Launcher().mainloop()


if __name__ == "__main__":
    main()
