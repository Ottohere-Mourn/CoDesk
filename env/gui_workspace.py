"""Tiny real Tk application used by the Docker/Xvfb shared-workspace smoke."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import tkinter as tk
from tkinter import ttk


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("id", "actor", "value"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()


def run(csv_path: Path, stale_write: bool = False) -> None:
    if not csv_path.exists():
        write_rows(csv_path, [])
    root = tk.Tk()
    root.title("Shared Workspace")
    root.geometry("560x260+20+20")
    root.configure(padx=14, pady=12)
    ttk.Label(root, text="Shared Workspace CSV", font=("Sans", 16, "bold")).pack(anchor="w")
    ttk.Label(root, text=str(csv_path)).pack(anchor="w", pady=(0, 10))
    value = tk.StringVar()
    entry = ttk.Entry(root, textvariable=value, width=54)
    entry.pack(anchor="w")
    status = tk.StringVar(value="Ready")
    ttk.Label(root, textvariable=status).pack(anchor="w", pady=8)
    startup_rows = read_rows(csv_path)

    def refresh() -> None:
        rows = read_rows(csv_path)
        status.set("Rows: " + ", ".join(f"{r['id']}={r['value']}" for r in rows))

    def submit() -> None:
        content = value.get().strip()
        if not content:
            status.set("Enter a value")
            return
        rows = list(startup_rows) if stale_write else read_rows(csv_path)
        row_id = f"G{sum(r['actor'] == 'gui' for r in rows) + 1}"
        rows.append({"id": row_id, "actor": "gui", "value": content})
        write_rows(csv_path, rows)
        value.set("")
        refresh()

    def periodic_refresh() -> None:
        refresh()
        root.after(300, periodic_refresh)

    ttk.Button(root, text="Submit GUI row", command=submit).pack(anchor="w", pady=4)
    root.bind("<Return>", lambda _event: submit())
    entry.focus_set()
    refresh()
    root.after(300, periodic_refresh)
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("/workspace/shared.csv"))
    parser.add_argument("--stale-write", action="store_true")
    args = parser.parse_args()
    run(args.csv, stale_write=args.stale_write)
