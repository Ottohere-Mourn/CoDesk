"""Lightweight GNOME-geometry status bar + left dock for 1920x1080 X11 capture."""
from __future__ import annotations

import sys
import time
import tkinter as tk


def main() -> int:
    label_text = sys.argv[1] if len(sys.argv) > 1 else "CoDesk Shared Ubuntu Desktop"
    root = tk.Tk()
    root.title("codesk-top-bar")
    root.overrideredirect(True)
    root.geometry("1920x27+0+0")
    root.configure(bg="#131924", cursor="left_ptr")
    left = tk.Label(root, text="  Activities    " + label_text, fg="#e6edf7", bg="#131924", font=("DejaVu Sans", 10, "bold"))
    left.pack(side=tk.LEFT)
    clock = tk.Label(root, text="", fg="#b8c7dd", bg="#131924", font=("DejaVu Sans Mono", 10))
    clock.pack(side=tk.RIGHT, padx=14)

    dock = tk.Toplevel(root)
    dock.title("codesk-left-dock")
    dock.overrideredirect(True)
    dock.geometry("68x1053+0+27")
    dock.configure(bg="#182232", cursor="left_ptr")
    for badge, bg_col in [("CHR", "#2b6cb0"), ("FILES", "#2f855a"), ("CALC", "#2c7a7b"), ("TERM", "#4a5568")]:
        tile = tk.Label(dock, text=badge, fg="#f7fafc", bg=bg_col, width=6, height=2, font=("DejaVu Sans", 8, "bold"))
        tile.pack(pady=8, padx=6)

    def tick() -> None:
        clock.configure(text=time.strftime("UTC %H:%M:%S"))
        root.after(1000, tick)

    tick()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
