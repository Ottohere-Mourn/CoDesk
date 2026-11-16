"""macOS-inspired Multi-Space Top Menu Bar + Bottom Dock + Wallpaper on 1920x1080 X11 (:99)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import tkinter as tk

from PIL import Image, ImageDraw


def set_macos_wallpaper() -> None:
    im = Image.new("RGB", (1920, 1080))
    draw = ImageDraw.Draw(im)
    for y in range(1080):
        r = int(16 + 22 * (y / 1080.0))
        g = int(28 + 44 * (y / 1080.0))
        b = int(56 + 68 * (y / 1080.0))
        draw.line([(0, y), (1920, y)], fill=(r, g, b))
    wp = "/tmp/macos_wallpaper.png"
    im.save(wp, "PNG")
    env = {**os.environ, "DISPLAY": ":99"}
    subprocess.run(["display", "-window", "root", wp], env=env, check=False, timeout=10)


def current_desktop_index() -> int:
    env = {**os.environ, "DISPLAY": ":99"}
    try:
        out = subprocess.check_output(["wmctrl", "-d"], env=env, text=True, timeout=3)
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) >= 2 and parts[1] == "*":
                return int(parts[0])
    except Exception:
        pass
    return 0


def current_app_label() -> str:
    env = {**os.environ, "DISPLAY": ":99"}
    try:
        title = subprocess.check_output(["xdotool", "getactivewindow", "getwindowname"], env=env, text=True, timeout=2).strip()
        low = title.lower()
        if ".pdf" in low or "arxiv" in low:
            return "Preview · PDF Reader"
        if "writer" in low:
            return "Notes · LibreOffice Writer"
        if "calc" in low:
            return "Numbers · LibreOffice Calc"
        if "inkscape" in low:
            return "Inkscape Vector Studio"
        if "gimp" in low:
            return "GIMP Image Studio"
        if "chromium" in low:
            return "Safari / Chromium"
        if title and "macos-" not in low:
            return title[:26]
    except Exception:
        pass
    return "Finder"


def switch_space(idx: int) -> None:
    env = {**os.environ, "DISPLAY": ":99"}
    subprocess.run(["wmctrl", "-s", str(idx)], env=env, check=False, timeout=3)


def activate_matching(keyword: str, fallback_space: int | None = None) -> None:
    env = {**os.environ, "DISPLAY": ":99"}
    try:
        out = subprocess.check_output(["wmctrl", "-l"], env=env, text=True, timeout=3)
        matches = [
            ln.split()[0]
            for ln in out.splitlines()
            if keyword.lower() in ln.lower() and "macos-menubar" not in ln.lower() and "macos-dock" not in ln.lower()
        ]
        if matches:
            subprocess.run(["wmctrl", "-ia", matches[-1]], env=env, check=False, timeout=3)
            return
    except Exception:
        pass
    if fallback_space is not None:
        switch_space(fallback_space)


def mark_sticky() -> None:
    env = {**os.environ, "DISPLAY": ":99"}
    try:
        out = subprocess.check_output(["wmctrl", "-l"], env=env, text=True, timeout=3)
        for ln in out.splitlines():
            if "macos-menubar" in ln or "macos-dock" in ln:
                wid = ln.split()[0]
                subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,sticky,above"], env=env, check=False, timeout=3)
    except Exception:
        pass


def main() -> int:
    case_label = sys.argv[1] if len(sys.argv) > 1 else "Shared Workstation"
    set_macos_wallpaper()

    bar = tk.Tk()
    bar.title("macos-menubar")
    bar.overrideredirect(True)
    bar.geometry("1920x30+0+0")
    bar.configure(bg="#151b28", cursor="left_ptr")

    apple_lbl = tk.Label(bar, text="  \uf8ff  ", fg="#f5f7fa", bg="#151b28", font=("DejaVu Sans", 11, "bold"))
    apple_lbl.pack(side=tk.LEFT)
    app_lbl = tk.Label(bar, text="Preview · PDF Reader", fg="#ffffff", bg="#151b28", font=("DejaVu Sans", 10, "bold"))
    app_lbl.pack(side=tk.LEFT, padx=(4, 14))
    menus_lbl = tk.Label(bar, text="File   Edit   View   Go   Window   Help", fg="#b9c6da", bg="#151b28", font=("DejaVu Sans", 10))
    menus_lbl.pack(side=tk.LEFT)

    clock_lbl = tk.Label(bar, text="", fg="#dce6f5", bg="#151b28", font=("DejaVu Sans Mono", 10))
    clock_lbl.pack(side=tk.RIGHT, padx=14)
    tag_lbl = tk.Label(bar, text=f"Wi-Fi: Online  ·  {case_label}", fg="#8fa6c9", bg="#151b28", font=("DejaVu Sans", 9))
    tag_lbl.pack(side=tk.RIGHT, padx=12)

    # Clickable Space switcher pills at deterministic screen coordinates:
    # Space 1 button center ~(1140, 15); Space 2 button center ~(1315, 15) -> (877, 10) in 1280x720 model coords!
    sp_frame = tk.Frame(bar, bg="#151b28")
    sp_frame.place(x=1045, y=3, width=365, height=24)
    sp1_btn = tk.Button(
        sp_frame, text="● Space 1: Reading", command=lambda: switch_space(0),
        relief=tk.FLAT, bd=0, padx=10, pady=2, fg="#ffffff", bg="#0a84ff", font=("DejaVu Sans", 9, "bold"),
    )
    sp1_btn.place(x=0, y=0, width=175, height=24)
    sp2_btn = tk.Button(
        sp_frame, text="○ Space 2: Agent Desk", command=lambda: switch_space(1),
        relief=tk.FLAT, bd=0, padx=10, pady=2, fg="#b8c7dd", bg="#263248", font=("DejaVu Sans", 9, "bold"),
    )
    sp2_btn.place(x=182, y=0, width=180, height=24)

    dock = tk.Toplevel(bar)
    dock.title("macos-dock")
    dock.overrideredirect(True)
    dock.geometry("760x54+580+1018")
    dock.configure(bg="#1c2638", cursor="left_ptr")

    dock_items = [
        ("Space 1 · Paper", "#0a84ff", lambda: switch_space(0)),
        ("Browser", "#2b6cb0", lambda: activate_matching("Chromium")),
        ("Writer Notes", "#3182ce", lambda: activate_matching("Writer")),
        ("Calc Sheet", "#2f855a", lambda: activate_matching("Calc")),
        ("Inkscape", "#805ad5", lambda: activate_matching("Inkscape")),
        ("Space 2 · Agent", "#d97706", lambda: switch_space(1)),
    ]
    for label, col, fn in dock_items:
        b = tk.Button(
            dock, text=label, command=fn, relief=tk.FLAT, bd=0,
            fg="#f8fafc", bg=col, activebackground=col, activeforeground="#ffffff",
            font=("DejaVu Sans", 9, "bold"), padx=10, pady=6,
        )
        b.pack(side=tk.LEFT, padx=7, pady=8, expand=True, fill=tk.X)

    bar.after(600, mark_sticky)

    def refresh() -> None:
        d_idx = current_desktop_index()
        if d_idx == 0:
            sp1_btn.configure(text="● Space 1: Reading", bg="#0a84ff", fg="#ffffff")
            sp2_btn.configure(text="○ Space 2: Agent Desk", bg="#263248", fg="#b8c7dd")
        else:
            sp1_btn.configure(text="○ Space 1: Reading", bg="#263248", fg="#b8c7dd")
            sp2_btn.configure(text="● Space 2: Agent Desk", bg="#ff9f0a", fg="#111827")
        app_lbl.configure(text=current_app_label())
        clock_lbl.configure(text=time.strftime("Mon %H:%M:%S UTC"))
        bar.after(250, refresh)

    refresh()
    bar.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
