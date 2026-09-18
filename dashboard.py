from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from bot.engine import persist, run_live, start_session
from bot.match import build_queue
from bot.parse import parse_claims, parse_credentials, split_passwords

ROOT = Path(__file__).resolve().parent
NAVY = "#1B3A4B"
TEAL = "#2E6B6B"
CREAM = "#F4F1EA"
INK = "#1E2A32"
CARD = "#FFFFFF"
LINE = "#C9C1B2"


class Desk(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CGTMSE Resubmit Desk")
        self.geometry("1100x720")
        self.minsize(960, 640)
        self.configure(bg=CREAM)
        self.cred_path = tk.StringVar()
        self.claim_path = tk.StringVar()
        self.maker_fb = tk.StringVar()
        self.checker_fb = tk.StringVar()
        self.show_maker = tk.BooleanVar(value=False)
        self.show_checker = tk.BooleanVar(value=False)
        self.headless = tk.BooleanVar(value=False)
        self.full_dom = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="resubmit")
        self.status = tk.StringVar(value="Load the two Excel files, then Build queue.")
        self.items: list[dict] = []
        self.stop_flag = False
        self.worker: threading.Thread | None = None
        self.evidence = None
        self._build()

    def _build(self) -> None:
        top = tk.Frame(self, bg=NAVY, height=56)
        top.pack(fill="x")
        tk.Label(top, text="CGTMSE Resubmit Desk", fg="white", bg=NAVY, font=("Segoe UI", 16, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(top, text="v1.7.0", fg="#D6E4E4", bg=NAVY, font=("Segoe UI", 10)).pack(side="right", padx=20)

        bar = tk.Frame(self, bg=TEAL)
        bar.pack(fill="x")
        for i, name in enumerate(("Files", "Queue", "Run", "Report")):
            tk.Button(bar, text=name, command=lambda n=i: self.nb.select(n), bg=TEAL, fg="white", relief="flat", font=("Segoe UI", 10)).pack(side="left", padx=8, pady=6)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=12)
        self.p_files = tk.Frame(self.nb, bg=CREAM)
        self.p_queue = tk.Frame(self.nb, bg=CREAM)
        self.p_run = tk.Frame(self.nb, bg=CREAM)
        self.p_rep = tk.Frame(self.nb, bg=CREAM)
        self.nb.add(self.p_files, text="  Files  ")
        self.nb.add(self.p_queue, text="  Queue  ")
        self.nb.add(self.p_run, text="  Run  ")
        self.nb.add(self.p_rep, text="  Report  ")
        self._files()
        self._queue()
        self._run()
        self._report()
        bot = tk.Frame(self, bg=CREAM)
        bot.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(bot, textvariable=self.status, bg=CREAM, fg=INK, font=("Segoe UI", 10)).pack(anchor="w")

    def _card(self, parent, title: str) -> tk.Frame:
        box = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        box.pack(fill="x", pady=8)
        tk.Label(box, text=title, bg=CARD, fg=NAVY, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        return box

    def _files(self) -> None:
        c = self._card(self.p_files, "Input workbooks")
        self._row(c, "Credential master", self.cred_path, self._pick_cred)
        self._row(c, "Claims data", self.claim_path, self._pick_claim)
        c2 = self._card(self.p_files, "Fallback passwords (used only if Excel password is rejected)")
        self._pw(c2, "Maker fallbacks, comma separated", self.maker_fb, self.show_maker)
        self._pw(c2, "Checker fallbacks, comma separated", self.checker_fb, self.show_checker)
        tk.Button(self.p_files, text="Build queue", command=self.build_queue, bg=NAVY, fg="white", relief="flat", font=("Segoe UI", 11), padx=16, pady=8).pack(anchor="w", pady=8)

    def _row(self, parent, label, var, cmd) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text=label, bg=CARD, fg=INK, width=22, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var, width=70).pack(side="left", padx=8)
        tk.Button(row, text="Browse", command=cmd, bg=TEAL, fg="white", relief="flat").pack(side="left")

    def _pw(self, parent, label, var, show) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text=label, bg=CARD, fg=INK, width=32, anchor="w").pack(side="left")
        ent = tk.Entry(row, textvariable=var, width=48, show="*")
        ent.pack(side="left", padx=8)

        def toggle() -> None:
            ent.config(show="" if show.get() else "*")

        tk.Checkbutton(row, text="Show", variable=show, command=toggle, bg=CARD).pack(side="left")

    def _queue(self) -> None:
        cols = ("mli", "claim", "maker", "checker", "status", "message")
        self.tree = ttk.Treeview(self.p_queue, columns=cols, show="headings", height=22)
        for col, w in (("mli", 120), ("claim", 150), ("maker", 120), ("checker", 120), ("status", 90), ("message", 420)):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w)
        self.tree.pack(fill="both", expand=True)

    def _run(self) -> None:
        c = self._card(self.p_run, "Live run")
        inner = tk.Frame(c, bg=CARD)
        inner.pack(anchor="w", padx=16, pady=8)
        tk.Checkbutton(inner, text="Hide browser (headless)", variable=self.headless, bg=CARD).pack(anchor="w")
        tk.Checkbutton(inner, text="Capture full HTML on key steps", variable=self.full_dom, bg=CARD).pack(anchor="w")
        btns = tk.Frame(self.p_run, bg=CREAM)
        btns.pack(anchor="w", pady=8)
        tk.Button(btns, text="Start live run", command=self.start_run, bg=NAVY, fg="white", relief="flat", padx=16, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Stop", command=self.stop_run, bg="#8B3A3A", fg="white", relief="flat", padx=16, pady=8).pack(side="left")
        self.logbox = tk.Text(self.p_run, height=18, bg=CARD, fg=INK, wrap="word")
        self.logbox.pack(fill="both", expand=True, pady=8)

    def _report(self) -> None:
        self.rep = tk.Text(self.p_rep, bg=CARD, fg=INK, wrap="word")
        self.rep.pack(fill="both", expand=True)

    def _pick_cred(self) -> None:
        p = filedialog.askopenfilename(title="Credential master", filetypes=[("Excel", "*.xlsx *.xlsm *.csv")])
        if p:
            self.cred_path.set(p)

    def _pick_claim(self) -> None:
        p = filedialog.askopenfilename(title="Claims data", filetypes=[("Excel", "*.xlsx *.xlsm *.csv")])
        if p:
            self.claim_path.set(p)

    def build_queue(self) -> None:
        try:
            creds = parse_credentials(self.cred_path.get())
            claims = parse_claims(self.claim_path.get())
            self.items = build_queue(creds, claims, self.maker_fb.get(), self.checker_fb.get())
        except Exception as exc:
            messagebox.showerror("Queue", str(exc))
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.items:
            c = item["claim"]
            cr = item.get("credential") or {}
            self.tree.insert("", "end", iid=c["id"], values=(c.get("mliCanonical"), c.get("claimRef"), cr.get("makerUser"), cr.get("checkerUser"), item.get("status"), item.get("message")))
        self.status.set(f"Queue ready · {len(self.items)} claim(s)")
        self.nb.select(1)

    def log(self, level: str, text: str, claim: str = "") -> None:
        line = f"{level.upper():<5} {('[' + claim + '] ') if claim else ''}{text}\n"
        self.after(0, lambda: (self.logbox.insert("end", line), self.logbox.see("end")))

    def on_item(self, cid: str, patch: dict) -> None:
        def apply() -> None:
            for item in self.items:
                if item["claim"]["id"] == cid:
                    item.update(patch)
                    if "status" in patch:
                        item["status"] = patch["status"]
                    if "message" in patch:
                        item["message"] = patch["message"]
                    if "remark" in patch:
                        item["remark"] = patch["remark"]
                    vals = self.tree.item(cid, "values")
                    if vals:
                        new = list(vals)
                        if "status" in patch:
                            new[4] = patch["status"]
                        if "message" in patch:
                            new[5] = patch["message"]
                        self.tree.item(cid, values=new)
                    break
        self.after(0, apply)

    def start_run(self) -> None:
        if not self.items:
            messagebox.showinfo("Run", "Build the queue first.")
            return
        if self.worker and self.worker.is_alive():
            return
        self.stop_flag = False
        self.evidence = start_session(ROOT, self.mode.get(), True, self.items, screen="run")
        self.status.set(f"Running · pack {self.evidence.root}")

        def work() -> None:
            try:
                run_live(
                    self.items,
                    self.mode.get(),
                    self.log,
                    lambda: self.stop_flag,
                    self.on_item,
                    self.headless.get(),
                    evidence=self.evidence,
                    full_dom=self.full_dom.get(),
                )
            except Exception as exc:
                self.log("error", str(exc), "")
            finally:
                persist(self.evidence, self.items)
                self.after(0, self._done)

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.nb.select(2)

    def stop_run(self) -> None:
        self.stop_flag = True
        self.status.set("Stopping…")

    def _done(self) -> None:
        persist(self.evidence, self.items)
        folder = str(self.evidence.root) if self.evidence else ""
        self.status.set(f"Finished · {folder}")
        if self.evidence:
            summary = (self.evidence.root / "result" / "SUMMARY.txt")
            if summary.exists():
                self.rep.delete("1.0", "end")
                self.rep.insert("end", summary.read_text(encoding="utf-8"))
        self.nb.select(3)


def main() -> None:
    Desk().mainloop()


if __name__ == "__main__":
    main()
