"""Pure-Python xdotool-backed pyautogui shim for X11 Docker desktop (:99)."""
from __future__ import annotations

import os
import subprocess
import time

FAILSAFE = False
PAUSE = 0.02

_KEYMAP = {
    "enter": "Return", "return": "Return", "kp_enter": "Return",
    "esc": "Escape", "escape": "Escape",
    "tab": "Tab",
    "space": "space",
    "backspace": "BackSpace",
    "delete": "Delete", "del": "Delete",
    "home": "Home", "end": "End",
    "pageup": "Prior", "pgup": "Prior", "page_up": "Prior", "prior": "Prior",
    "pagedown": "Next", "pgdn": "Next", "page_down": "Next", "next": "Next",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "ctrl": "ctrl", "control": "ctrl", "control_l": "ctrl", "control_r": "ctrl",
    "alt": "alt", "alt_l": "alt", "alt_r": "alt",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "win": "super", "super": "super", "command": "super",
}
for _i in range(1, 13):
    _KEYMAP[f"f{_i}"] = f"F{_i}"

_BUTTONS = {"left": "1", "middle": "2", "right": "3", 1: "1", 2: "2", 3: "3"}


def _xdo(*args: str, timeout: float = 30.0) -> str:
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":99")
    out = subprocess.run(["xdotool", *args], env=env, capture_output=True, text=True, timeout=timeout, check=True)
    return out.stdout


def _pause() -> None:
    if PAUSE and PAUSE > 0:
        time.sleep(PAUSE)


def size() -> tuple[int, int]:
    try:
        raw = _xdo("getdisplaygeometry").strip().split()
        return int(raw[0]), int(raw[1])
    except Exception:
        return (1920, 1080)


def position() -> tuple[int, int]:
    raw = _xdo("getmouselocation", "--shell")
    vals = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    return int(vals.get("X", "0")), int(vals.get("Y", "0"))


def moveTo(x: float, y: float, duration: float = 0.0, **_kwargs) -> None:
    tx, ty = int(round(float(x))), int(round(float(y)))
    if duration and duration > 0.05:
        sx, sy = position()
        steps = max(2, min(12, int(round(duration / 0.04))))
        for idx in range(1, steps + 1):
            ix = int(round(sx + (tx - sx) * idx / steps))
            iy = int(round(sy + (ty - sy) * idx / steps))
            _xdo("mousemove", "--sync", str(ix), str(iy))
            time.sleep(duration / steps)
    else:
        _xdo("mousemove", "--sync", str(tx), str(ty))
    _pause()


def click(x: float | None = None, y: float | None = None, clicks: int = 1,
          interval: float = 0.0, button: str = "left", **_kwargs) -> None:
    if x is not None and y is not None:
        _xdo("mousemove", "--sync", str(int(round(float(x)))), str(int(round(float(y)))))
    btn = _BUTTONS.get(button, "1")
    count = max(1, int(clicks))
    if count > 1:
        delay_ms = max(40, min(200, int(round(float(interval or 0.08) * 1000))))
        _xdo("click", "--clearmodifiers", "--repeat", str(count), "--delay", str(delay_ms), btn)
    else:
        _xdo("click", "--clearmodifiers", btn)
    _pause()


def doubleClick(x: float | None = None, y: float | None = None, interval: float = 0.1, button: str = "left", **kw) -> None:
    click(x=x, y=y, clicks=2, interval=interval, button=button, **kw)


def rightClick(x: float | None = None, y: float | None = None, **kw) -> None:
    click(x=x, y=y, clicks=1, button="right", **kw)


def dragTo(x: float, y: float, duration: float = 0.5, button: str = "left", **_kwargs) -> None:
    btn = _BUTTONS.get(button, "1")
    sx, sy = position()
    tx, ty = int(round(float(x))), int(round(float(y)))
    _xdo("mousedown", btn)
    try:
        steps = max(4, min(16, int(round(max(0.1, duration) / 0.04))))
        for idx in range(1, steps + 1):
            ix = int(round(sx + (tx - sx) * idx / steps))
            iy = int(round(sy + (ty - sy) * idx / steps))
            _xdo("mousemove", "--sync", str(ix), str(iy))
            time.sleep(max(0.1, duration) / steps)
    finally:
        _xdo("mouseup", btn)
    _pause()


def _map_key(name: str) -> str:
    s = str(name).strip()
    low = s.lower()
    if low in _KEYMAP:
        return _KEYMAP[low]
    if len(s) == 1:
        return s
    return s


def write(message: str, interval: float = 0.0, **_kwargs) -> None:
    text = str(message)
    if not text:
        return
    delay_ms = max(8, int(round(float(interval or 0.015) * 1000)))
    parts = text.split("\n")
    for idx, part in enumerate(parts):
        if part:
            _xdo("type", "--clearmodifiers", "--delay", str(delay_ms), "--", part, timeout=max(30.0, len(part) * delay_ms / 500.0 + 15.0))
        if idx + 1 < len(parts):
            _xdo("key", "--clearmodifiers", "Return")
    _pause()


typewrite = write


def press(keys, presses: int = 1, interval: float = 0.0, **_kwargs) -> None:
    seq = [keys] if isinstance(keys, str) else list(keys)
    reps = max(1, int(presses))
    for r_idx in range(reps):
        for k in seq:
            _xdo("key", "--clearmodifiers", _map_key(k))
            if interval > 0 and len(seq) > 1:
                time.sleep(float(interval))
        if r_idx + 1 < reps and interval > 0:
            time.sleep(float(interval))
    _pause()


def hotkey(*args: str, **_kwargs) -> None:
    if not args:
        return
    chord = "+".join(_map_key(k) for k in args)
    if chord.lower() == "alt+tab":
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":99")
        try:
            out = subprocess.check_output(["wmctrl", "-l"], env=env, text=True, timeout=5)
            wids = [
                ln.split()[0]
                for ln in out.splitlines()
                if ln.strip() and "codesk-top-bar" not in ln.lower() and "codesk-left-dock" not in ln.lower()
            ]
            if len(wids) >= 2:
                try:
                    act_dec = int(_xdo("getactivewindow").strip())
                    other = [w for w in wids if int(w, 16) != act_dec]
                except Exception:
                    other = wids[:-1]
                target = other[-1] if other else wids[0]
                subprocess.run(["wmctrl", "-ia", target], env=env, check=False, timeout=5)
                time.sleep(0.25)
                _pause()
                return
        except Exception:
            pass
    _xdo("key", "--clearmodifiers", chord)
    _pause()


def scroll(clicks: int, x: float | None = None, y: float | None = None, **_kwargs) -> None:
    if x is not None and y is not None:
        moveTo(x, y)
    n = int(round(float(clicks)))
    if n == 0:
        return
    btn = "4" if n > 0 else "5"
    _xdo("click", "--repeat", str(abs(n)), "--delay", "25", btn)
    _pause()


def hscroll(clicks: int, x: float | None = None, y: float | None = None, **_kwargs) -> None:
    if x is not None and y is not None:
        moveTo(x, y)
    n = int(round(float(clicks)))
    if n == 0:
        return
    btn = "7" if n > 0 else "6"
    _xdo("click", "--repeat", str(abs(n)), "--delay", "25", btn)
    _pause()
