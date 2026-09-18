#!/usr/bin/env python3
"""CGTMSE Resubmit Desk — office dashboard, one task per screen."""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from bot.engine import run_live, run_rehearsal, start_session
from bot.envcheck import collect_environment, format_environment
from bot.match import apply_user_fallbacks, build_queue, format_passwords
from bot.parse import parse_claims, parse_credentials
from bot.report import export_csv
from bot.sop import PORTAL_URL

PAPER = "#F3EFE6"
PANEL = "#FBFAF6"
NAVY = "#3B5368"
INK = "#2E3A47"
MUTED = "#6B7380"
LINE = "#D6D0C4"
OK = "#3E7A5A"
WARN = "#9A7540"
ERR = "#A84A3E"
WHITE = "#FFFFFF"


class Desk(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CGTMSE Resubmit Desk")
        self.geometry("1120x720")
        self.minsize(960, 640)
        self.configure(bg=PAPER)
        self.credentials: list[dict] = []
        self.claims: list[dict] = []
        self.queue_items: list[dict] = []
        self.cred_name = "No file chosen"
        self.claim_name = "No file chosen"
        self.running = False
        self.stop_flag = False
        self.page = "files"
        self.uiq: queue.Queue = queue.Queue()
        self.mode = tk.StringVar(value="rehearsal")
        self.live = tk.BooleanVar(value=False)
        self.headless = tk.BooleanVar(value=False)
        self.show_pw = tk.BooleanVar(value=False)
        self.show_fb = tk.BooleanVar(value=False)
        self.full_dom = tk.BooleanVar(value=False)
        self.maker_fb = tk.StringVar()
        self.checker_fb = tk.StringVar()
        self.evidence_dir = ""
        self.last_page = "files"
        self.captcha_ready = threading.Event()
        self.captcha_value = ""
        self._captcha_photo = None
        self._style()
        self._chrome()
        self._pages()
        self.show("files")
        self.after(120, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=PAPER, foreground=INK, fieldbackground=WHITE, bordercolor=LINE)
        s.configure("TFrame", background=PAPER)
        s.configure("Paper.TFrame", background=PAPER)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("Navy.TFrame", background=NAVY)
        s.configure("TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        s.configure("Paper.TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        s.configure("Muted.TLabel", background=PAPER, foreground=MUTED, font=("Segoe UI", 10))
        s.configure("Title.TLabel", background=PAPER, foreground=NAVY, font=("Georgia", 22))
        s.configure("H2.TLabel", background=PAPER, foreground=NAVY, font=("Georgia", 16))
        s.configure("Navy.TLabel", background=NAVY, foreground=WHITE, font=("Segoe UI", 11))
        s.configure("NavyMuted.TLabel", background=NAVY, foreground="#D5DEE6", font=("Segoe UI", 9))
        s.configure("Panel.TLabel", background=PANEL, foreground=INK, font=("Segoe UI", 10))
        s.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        s.configure("TButton", background=WHITE, foreground=INK, padding=(14, 8), font=("Segoe UI", 10))
        s.map("TButton", background=[("active", "#E8E2D6")])
        s.configure("Navy.TButton", background=NAVY, foreground=WHITE, padding=(16, 9), font=("Segoe UI", 10))
        s.map("Navy.TButton", background=[("active", "#2F4456")], foreground=[("active", WHITE)])
        s.configure("TCheckbutton", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        s.configure("TRadiobutton", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        s.configure("Treeview", background=WHITE, foreground=INK, fieldbackground=WHITE, rowheight=32, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background="#E7E1D6", foreground=NAVY, font=("Segoe UI", 9), relief="flat")
        s.map("Treeview", background=[("selected", "#DDE5EC")])
        s.configure("Horizontal.TProgressbar", troughcolor="#E7E1D6", background=NAVY)
        s.configure("TSeparator", background=LINE)

    def _chrome(self) -> None:
        bar = ttk.Frame(self, style="Navy.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="CGTMSE  ·  Resubmit Desk", style="Navy.TLabel").pack(side="left", padx=28, pady=16)
        ttk.Label(bar, text="Returned first-instalment claims", style="NavyMuted.TLabel").pack(side="left")
        tk.Button(bar, text="Output folder", command=self._open_evidence, bg=NAVY, fg=WHITE, activebackground="#2F4456", activeforeground=WHITE, relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2").pack(side="right", padx=(0, 20), pady=12)
        tk.Button(bar, text="Environment", command=self._open_env, bg=NAVY, fg=WHITE, activebackground="#2F4456", activeforeground=WHITE, relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2").pack(side="right", padx=8, pady=12)
        self.step_lbl = ttk.Label(bar, text="1 of 4  ·  Files", style="NavyMuted.TLabel")
        self.step_lbl.pack(side="right", padx=16)

        trail = ttk.Frame(self, style="Paper.TFrame")
        trail.pack(fill="x", padx=28, pady=(18, 0))
        self.trail = {}
        for key, label in [("files", "1  Files"), ("queue", "2  Queue"), ("run", "3  Run"), ("report", "4  Report")]:
            lbl = ttk.Label(trail, text=label, style="Muted.TLabel")
            lbl.pack(side="left", padx=(0, 28))
            self.trail[key] = lbl

        self.body = ttk.Frame(self, style="Paper.TFrame")
        self.body.pack(fill="both", expand=True, padx=28, pady=18)

        foot = ttk.Frame(self, style="Paper.TFrame")
        foot.pack(fill="x", padx=28, pady=(0, 18))
        self.back_btn = ttk.Button(foot, text="Back", command=self._back)
        self.back_btn.pack(side="left")
        self.next_btn = ttk.Button(foot, text="Next", style="Navy.TButton", command=self._next)
        self.next_btn.pack(side="right")

    def _pages(self) -> None:
        self.pages = {name: ttk.Frame(self.body, style="Paper.TFrame") for name in ("files", "queue", "run", "report", "env")}
        self._page_files()
        self._page_queue()
        self._page_run()
        self._page_report()
        self._page_env()

    def _card(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, style="Panel.TFrame")
        f.configure(padding=24)
        return f

    def _page_files(self) -> None:
        p = self.pages["files"]
        ttk.Label(p, text="Load the workbooks", style="H2.TLabel").pack(anchor="w")
        ttk.Label(p, text="MLI ID and Claim Reference No. are read from the claims file. They are not entered here.", style="Muted.TLabel").pack(anchor="w", pady=(6, 22))

        cred = self._card(p)
        cred.pack(fill="x", pady=(0, 14))
        ttk.Label(cred, text="Credential master", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(cred, text="MLI / Member ID, Maker User ID, Maker Password, Checker User ID, Checker Password. One password per cell.", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(cred, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Choose file", command=self._load_creds).pack(side="left")
        self.cred_lbl = ttk.Label(row, text=self.cred_name, style="PanelMuted.TLabel")
        self.cred_lbl.pack(side="left", padx=16)

        clm = self._card(p)
        clm.pack(fill="x")
        ttk.Label(clm, text="Claims data", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(clm, text="Required columns: MLI ID, CLAIM REF NO. Optional: URN, State, Legal Waiver, Comment.", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 12))
        row2 = ttk.Frame(clm, style="Panel.TFrame")
        row2.pack(fill="x")
        ttk.Button(row2, text="Choose file", command=self._load_claims).pack(side="left")
        self.claim_lbl = ttk.Label(row2, text=self.claim_name, style="PanelMuted.TLabel")
        self.claim_lbl.pack(side="left", padx=16)

        fb = self._card(p)
        fb.pack(fill="x", pady=(14, 0))
        ttk.Label(fb, text="Fallback passwords (optional)", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(fb, text="Not taken from Excel. Tried only if the sheet password is rejected. Comma-separated if you have more than one.", style="PanelMuted.TLabel").pack(anchor="w", pady=(4, 10))
        grid = ttk.Frame(fb, style="Panel.TFrame")
        grid.pack(fill="x")
        ttk.Label(grid, text="Maker fallbacks", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Checker fallbacks", style="Panel.TLabel").grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.maker_fb_entry = ttk.Entry(grid, textvariable=self.maker_fb, show="*", width=36)
        self.maker_fb_entry.grid(row=1, column=0, sticky="ew", pady=6)
        self.checker_fb_entry = ttk.Entry(grid, textvariable=self.checker_fb, show="*", width=36)
        self.checker_fb_entry.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        ttk.Checkbutton(fb, text="Show fallbacks", variable=self.show_fb, command=self._toggle_fb).pack(anchor="w", pady=(4, 0))

        self.file_stats = ttk.Label(p, text="", style="Muted.TLabel")
        self.file_stats.pack(anchor="w", pady=(18, 0))

    def _page_queue(self) -> None:
        p = self.pages["queue"]
        ttk.Label(p, text="Review the queue", style="H2.TLabel").pack(anchor="w")
        self.qstats = ttk.Label(p, text="", style="Muted.TLabel")
        self.qstats.pack(anchor="w", pady=(6, 10))
        ttk.Checkbutton(p, text="Show passwords", variable=self.show_pw, command=self._refresh_tree).pack(anchor="w", pady=(0, 12))

        wrap = ttk.Frame(p, style="Paper.TFrame")
        wrap.pack(fill="both", expand=True)
        cols = ("claim", "mli", "maker", "makerpw", "checker", "checkerpw", "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for c, title, w in (
            ("claim", "Claim reference", 180),
            ("mli", "MLI ID", 120),
            ("maker", "Maker", 120),
            ("makerpw", "Maker password", 160),
            ("checker", "Checker", 120),
            ("checkerpw", "Checker password", 160),
            ("status", "Status", 90),
        ):
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, stretch=True)
        ys = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.tree.tag_configure("error", foreground=ERR)
        self.tree.tag_configure("done", foreground=OK)
        self.tree.tag_configure("running", foreground=WARN)

    def _page_run(self) -> None:
        p = self.pages["run"]
        ttk.Label(p, text="Run the resubmission", style="H2.TLabel").pack(anchor="w")
        ttk.Label(p, text=f"Portal  {PORTAL_URL}", style="Muted.TLabel").pack(anchor="w", pady=(6, 16))

        box = ttk.Frame(p, style="Paper.TFrame")
        box.pack(fill="x")
        left = ttk.Frame(box, style="Paper.TFrame")
        left.pack(side="left", anchor="n", padx=(0, 48))
        ttk.Label(left, text="Mode", style="Paper.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Radiobutton(left, text="Rehearsal — walk through, do not open the portal", value="rehearsal", variable=self.mode).pack(anchor="w", pady=3)
        ttk.Radiobutton(left, text="Inspect — stop before Submit", value="inspect", variable=self.mode).pack(anchor="w", pady=3)
        ttk.Radiobutton(left, text="Resubmit — Submit, D/U, Checker ACCEPT", value="resubmit", variable=self.mode).pack(anchor="w", pady=3)
        ttk.Checkbutton(left, text="Live portal (Playwright)", variable=self.live).pack(anchor="w", pady=(14, 3))
        ttk.Checkbutton(left, text="Headless browser", variable=self.headless).pack(anchor="w")
        ttk.Checkbutton(left, text="Capture full HTML on every step", variable=self.full_dom).pack(anchor="w", pady=(3, 0))
        ttk.Label(left, text="Live mode logs in once per MLI, then walks each claim. Captcha is not required. Each Start writes output\\RESUBCL-dd-mm-yyyy-HH-MM\\ (result, reports, evidence, video).", style="Muted.TLabel", wraplength=360).pack(anchor="w", pady=(10, 0))

        right = ttk.Frame(box, style="Paper.TFrame")
        right.pack(side="left", anchor="n")
        self.start_btn = ttk.Button(right, text="Start", style="Navy.TButton", command=self._start)
        self.start_btn.pack(anchor="w")
        ttk.Button(right, text="Stop", command=self._stop).pack(anchor="w", pady=8)
        ttk.Button(right, text="Open output folder", command=self._open_evidence).pack(anchor="w")
        self.pbar = ttk.Progressbar(right, mode="determinate", maximum=100, length=240)
        self.pbar.pack(anchor="w", pady=(8, 0))
        self.ev_lbl = ttk.Label(right, text="Output is written under  output\\RESUBCL-…", style="Muted.TLabel", wraplength=260)
        self.ev_lbl.pack(anchor="w", pady=(10, 0))

        ttk.Label(p, text="Log", style="Paper.TLabel").pack(anchor="w", pady=(22, 8))
        self.log = tk.Text(p, height=14, bg=WHITE, fg=INK, insertbackground=INK, relief="solid", bd=1, highlightthickness=0, font=("Consolas", 10), wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("ok", foreground=OK)
        self.log.tag_configure("warn", foreground=WARN)
        self.log.tag_configure("error", foreground=ERR)
        self.log.tag_configure("info", foreground=MUTED)
        self.log.insert("end", "Load both files, review the queue, then Start.\n")
        self.log.configure(state="disabled")

    def _page_report(self) -> None:
        p = self.pages["report"]
        ttk.Label(p, text="Report", style="H2.TLabel").pack(anchor="w")
        self.rstats = ttk.Label(p, text="No run yet.", style="Muted.TLabel")
        self.rstats.pack(anchor="w", pady=(6, 16))
        ttk.Button(p, text="Export CSV", style="Navy.TButton", command=self._export).pack(anchor="w")
        wrap = ttk.Frame(p, style="Paper.TFrame")
        wrap.pack(fill="both", expand=True, pady=(18, 0))
        cols = ("claim", "mli", "status", "message")
        self.rtree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, title, w in (("claim", "Claim reference", 220), ("mli", "MLI ID", 150), ("status", "Status", 110), ("message", "Message", 420)):
            self.rtree.heading(c, text=title)
            self.rtree.column(c, width=w, stretch=True)
        ys = ttk.Scrollbar(wrap, orient="vertical", command=self.rtree.yview)
        self.rtree.configure(yscrollcommand=ys.set)
        self.rtree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.rtree.tag_configure("error", foreground=ERR)
        self.rtree.tag_configure("done", foreground=OK)
        ttk.Button(p, text="Open output folder", command=self._open_evidence).pack(anchor="w", pady=(12, 0))

    def _page_env(self) -> None:
        p = self.pages["env"]
        ttk.Label(p, text="Environment", style="H2.TLabel").pack(anchor="w")
        ttk.Label(p, text="Self-check of this desk, this machine, and the CGTMSE portal. Used in every evidence pack.", style="Muted.TLabel").pack(anchor="w", pady=(6, 12))
        row = ttk.Frame(p, style="Paper.TFrame")
        row.pack(fill="x", pady=(0, 10))
        ttk.Button(row, text="Refresh check", style="Navy.TButton", command=self._refresh_env).pack(side="left")
        self.env_box = tk.Text(p, bg=WHITE, fg=INK, insertbackground=INK, relief="solid", bd=1, highlightthickness=0, font=("Consolas", 10), wrap="word")
        self.env_box.pack(fill="both", expand=True)

    def show(self, name: str) -> None:
        for f in self.pages.values():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        if name != "env":
            self.last_page = name
        self.page = name
        titles = {
            "files": "1 of 4  ·  Files",
            "queue": "2 of 4  ·  Queue",
            "run": "3 of 4  ·  Run",
            "report": "4 of 4  ·  Report",
            "env": "Environment",
        }
        self.step_lbl.configure(text=titles[name])
        for key, lbl in self.trail.items():
            lbl.configure(style="Paper.TLabel" if key == name else "Muted.TLabel")
        self.back_btn.configure(state="disabled" if name == "files" else "normal")
        self.next_btn.configure(text="Finish" if name == "report" else "Next")
        if name == "queue":
            self._refresh_tree()
        if name == "report":
            self._refresh_report()
        if name == "env":
            self._refresh_env()

    def _open_env(self) -> None:
        self.show("env")

    def _refresh_env(self) -> None:
        screen = f"{self.winfo_screenwidth()}×{self.winfo_screenheight()}"
        text = format_environment(collect_environment(HERE, screen=screen))
        extra = [
            "",
            f"Credential file  {self.cred_name}",
            f"Claims file      {self.claim_name}",
            f"Queue            {len(self.queue_items)} row(s)",
            f"Output pack      {self.evidence_dir or '(none yet — created on Start)'}",
        ]
        self.env_box.delete("1.0", "end")
        self.env_box.insert("end", text + "\n" + "\n".join(extra))

    def _open_evidence(self) -> None:
        folder = Path(self.evidence_dir) if self.evidence_dir else HERE / "output"
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            os.system(f'xdg-open "{folder}"')

    def _next(self) -> None:
        order = ["files", "queue", "run", "report"]
        if self.page == "env":
            self.show(self.last_page or "files")
            return
        if self.page == "files":
            if not self.credentials:
                messagebox.showinfo("Files", "Choose the credential master.")
                return
            if not self.claims:
                messagebox.showinfo("Files", "Choose the claims file. It must contain MLI ID and CLAIM REF NO.")
                return
            self._rebuild()
        if self.page == "queue" and not any(q["status"] == "queued" for q in self.queue_items):
            if not messagebox.askyesno("Queue", "No matched claims are ready. Continue anyway?"):
                return
        if self.page == "report":
            return
        self.show(order[order.index(self.page) + 1])

    def _back(self) -> None:
        if self.page == "env":
            self.show(self.last_page or "files")
            return
        order = ["files", "queue", "run", "report"]
        i = order.index(self.page)
        if i:
            self.show(order[i - 1])

    def _log(self, level: str, text: str, claim: str = "") -> None:
        prefix = f"[{claim}] " if claim else ""
        self.uiq.put(("log", level, prefix + text))

    def _drain(self) -> None:
        try:
            while True:
                item = self.uiq.get_nowait()
                kind = item[0]
                if kind == "log":
                    _, level, text = item
                    self.log.configure(state="normal")
                    self.log.insert("end", text + "\n", level)
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "item":
                    _, cid, patch = item
                    for q in self.queue_items:
                        if q["claim"]["id"] == cid:
                            q.update(patch)
                    self._refresh_tree()
                    self._refresh_report()
                elif kind == "captcha":
                    _, path, hint = item
                    self._prompt_captcha(path, hint)
                elif kind == "done":
                    self.running = False
                    self.start_btn.configure(state="normal")
                    self._refresh_report()
        except queue.Empty:
            pass
        self.after(120, self._drain)

    def _ask_captcha(self, image_path: str, hint: str) -> str:
        self.captcha_value = ""
        self.captcha_ready.clear()
        self.uiq.put(("captcha", image_path, hint))
        if not self.captcha_ready.wait(timeout=180):
            return ""
        return self.captcha_value

    def _prompt_captcha(self, image_path: str, hint: str) -> None:
        win = tk.Toplevel(self)
        win.title("Captcha")
        win.configure(bg=PAPER)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text="Enter captcha", style="H2.TLabel").pack(anchor="w", padx=24, pady=(20, 6))
        ttk.Label(win, text=hint, style="Muted.TLabel").pack(anchor="w", padx=24)
        ttk.Label(win, text="Type the 6 characters. Type REFRESH for a new image. Leave blank if you already typed it in the browser.", style="Muted.TLabel", wraplength=420).pack(anchor="w", padx=24, pady=(4, 12))
        if image_path and Path(image_path).exists():
            try:
                self._captcha_photo = tk.PhotoImage(file=image_path)
                tk.Label(win, image=self._captcha_photo, bg=WHITE, bd=1, relief="solid").pack(padx=24, pady=8)
            except Exception:
                ttk.Label(win, text=f"Image: {image_path}", style="Muted.TLabel").pack(anchor="w", padx=24)
        var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=var, width=18, font=("Segoe UI", 14))
        entry.pack(padx=24, pady=8, anchor="w")
        entry.focus_set()

        def submit(_event=None):
            self.captcha_value = var.get().strip()
            self.captcha_ready.set()
            win.destroy()

        def refresh():
            self.captcha_value = "REFRESH"
            self.captcha_ready.set()
            win.destroy()

        row = ttk.Frame(win, style="Paper.TFrame")
        row.pack(fill="x", padx=24, pady=(8, 20))
        ttk.Button(row, text="Continue", style="Navy.TButton", command=submit).pack(side="left")
        ttk.Button(row, text="New image", command=refresh).pack(side="left", padx=8)
        win.bind("<Return>", submit)
        win.protocol("WM_DELETE_WINDOW", submit)

    def _load_creds(self) -> None:
        path = filedialog.askopenfilename(title="Credential master", filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv"), ("All", "*.*")])
        if not path:
            return
        try:
            self.credentials = parse_credentials(path)
            self.cred_name = f"{Path(path).name}  ·  {len(self.credentials)} MLI(s)"
            self.cred_lbl.configure(text=self.cred_name)
            self._rebuild()
        except Exception as exc:
            messagebox.showerror("Credential master", str(exc))

    def _load_claims(self) -> None:
        path = filedialog.askopenfilename(title="Claims data", filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv"), ("All", "*.*")])
        if not path:
            return
        try:
            rows = parse_claims(path)
            if not rows:
                messagebox.showinfo("Claims data", "No claim rows found. Put MLI ID and CLAIM REF NO in the sheet.")
                self.claims = []
                self.claim_name = f"{Path(path).name}  ·  0 claims"
                self.claim_lbl.configure(text=self.claim_name)
                self._rebuild()
                return
            self.claims = rows
            self.claim_name = f"{Path(path).name}  ·  {len(rows)} claim(s)"
            self.claim_lbl.configure(text=self.claim_name)
            self._rebuild()
        except Exception as exc:
            messagebox.showerror("Claims data", str(exc))

    def _toggle_fb(self) -> None:
        show = "" if self.show_fb.get() else "*"
        self.maker_fb_entry.configure(show=show)
        self.checker_fb_entry.configure(show=show)
        self._rebuild()

    def _rebuild(self) -> None:
        creds = apply_user_fallbacks(self.credentials, self.maker_fb.get(), self.checker_fb.get())
        self.queue_items = build_queue(self.claims, creds)
        matched = sum(1 for q in self.queue_items if q.get("credential") and q["status"] == "queued")
        blocked = sum(1 for q in self.queue_items if q["status"] == "error")
        n_fb = 0
        if self.maker_fb.get().strip() or self.checker_fb.get().strip():
            n_fb = 1
        self.file_stats.configure(text=f"{len(self.credentials)} MLIs loaded  ·  {len(self.claims)} claims loaded  ·  {matched} matched  ·  {blocked} blocked")
        extra = " Fallback passwords will be used if the Excel password is rejected." if n_fb else " No fallback passwords entered."
        self.qstats.configure(text=f"{len(self.queue_items)} row(s)  ·  {matched} ready  ·  {blocked} blocked.{extra} Show passwords to reveal.")
        self._refresh_tree()
        self._refresh_report()

    def _refresh_tree(self) -> None:
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        for q in self.queue_items:
            cred = q.get("credential") or {}
            tag = q["status"] if q["status"] in {"error", "done", "running"} else ""
            show = self.show_pw.get()
            self.tree.insert("", "end", iid=q["claim"]["id"], values=(
                q["claim"]["claimRef"],
                q["claim"].get("mliCanonical") or q["claim"].get("mliId"),
                cred.get("makerUser") or "—",
                format_passwords(cred.get("makerPasswords"), show),
                cred.get("checkerUser") or "—",
                format_passwords(cred.get("checkerPasswords"), show),
                q["status"].upper(),
            ), tags=(tag,))
        done = sum(1 for q in self.queue_items if q["status"] == "done")
        if hasattr(self, "pbar"):
            self.pbar["value"] = (100 * done / len(self.queue_items)) if self.queue_items else 0

    def _refresh_report(self) -> None:
        if not hasattr(self, "rtree"):
            return
        self.rtree.delete(*self.rtree.get_children())
        done = sum(1 for q in self.queue_items if q["status"] == "done")
        err = sum(1 for q in self.queue_items if q["status"] == "error")
        run = sum(1 for q in self.queue_items if q["status"] == "running")
        self.rstats.configure(text=f"{len(self.queue_items)} claim(s)  ·  {done} done  ·  {err} error  ·  {run} running")
        for q in self.queue_items:
            tag = q["status"] if q["status"] in {"error", "done"} else ""
            self.rtree.insert("", "end", values=(
                q["claim"]["claimRef"],
                q["claim"].get("mliCanonical") or q["claim"].get("mliId"),
                q["status"].upper(),
                q.get("message") or q.get("remark") or "",
            ), tags=(tag,))

    def _start(self) -> None:
        if self.running:
            return
        queued = [q for q in self.queue_items if q["status"] == "queued"]
        if not queued:
            messagebox.showinfo("Run", "Nothing queued. Go back to Files.")
            return
        if self.live.get():
            n = len(queued)
            mlis = {q["claim"].get("mliCanonical") for q in queued}
            if not messagebox.askyesno(
                "Live portal",
                f"This will open https://inter.cgtmse.in\n\n"
                f"{n} claim(s) across {len(mlis)} MLI(s).\n"
                f"Excel password first; fallbacks only if that is rejected.\n"
                f"Captcha is not required. Type it in the browser if the portal shows one.\n\nContinue?",
            ):
                return
        self.running = True
        self.stop_flag = False
        self.start_btn.configure(state="disabled")
        mode = self.mode.get()
        live = self.live.get()
        headless = self.headless.get()
        full_dom = self.full_dom.get()
        items = list(self.queue_items)
        screen = f"{self.winfo_screenwidth()}×{self.winfo_screenheight()}"
        evidence = start_session(
            HERE,
            mode,
            live,
            items,
            screen=screen,
            extra={
                "credential_file": self.cred_name,
                "claims_file": self.claim_name,
                "headless": headless,
                "full_html": full_dom,
            },
        )
        self.evidence_dir = str(evidence.root)
        self.ev_lbl.configure(text=f"Output\n{evidence.root}")
        self._log("info", f"Run pack: {evidence.root}")

        def on_item(cid, patch):
            self.uiq.put(("item", cid, patch))

        def work():
            try:
                if live:
                    run_live(
                        items,
                        mode,
                        lambda lv, t, c: self._log(lv, t, c),
                        lambda: self.stop_flag,
                        on_item,
                        headless,
                        evidence=evidence,
                        full_dom=full_dom,
                    )
                else:
                    run_rehearsal(items, mode, lambda lv, t, c: self._log(lv, t, c), lambda: self.stop_flag, on_item, evidence=evidence)
            except Exception as exc:
                self._log("error", str(exc))
            finally:
                self.uiq.put(("done",))

        threading.Thread(target=work, daemon=True).start()

    def _stop(self) -> None:
        self.stop_flag = True
        self._log("warn", "Stop requested…")

    def _export(self) -> None:
        if not self.queue_items:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="cgtmse-resubmit-report.csv")
        if not path:
            return
        export_csv(path, self.queue_items)
        self._log("ok", f"Report written: {path}")
        messagebox.showinfo("Report", f"Saved:\n{path}")

    def _on_close(self) -> None:
        self.stop_flag = True
        self.destroy()


def main() -> None:
    Desk().mainloop()


if __name__ == "__main__":
    main()
