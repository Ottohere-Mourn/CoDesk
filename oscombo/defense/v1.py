"""paraGUI defense v1 ("own view, own input, own browser, own terminal").

Everything here runs inside ONE agent's harness. It keeps no state outside this object (plus one private scratch
file in the Guest whose random name only this harness instance knows, used to return window bookkeeping from the
action process), never talks to another harness, never tells the model about anyone else, and runs the same code
path for every task and every mode (solo / sequential / parallel). Failure taxonomy and evidence: v1_NOTES.md.

Mechanisms (failure classes of v1_NOTES.md in brackets):

M1  Generic working notes appended to the instruction [H give-up on suspicion, D stale write, G terminal panels].
    Identical for every task. They describe a live desktop (windows come to the front, files and pages get updated)
    and state that this is never a hard blocker; they ask not to revert/close things that are not part of the task,
    never to write back older copies, and to use a terminal window rather than a terminal panel of another app.
    Harmless alone: they only rule out giving up for reasons that do not exist alone and ask for good practice.

M2  "Act on what you saw" [B input interleaving]. Each action is wrapped (in the same Guest process) so that the first
    action of a batch goes to the window that was in front in the screenshot the model looked at: if the focus moved
    since then, that window is re-activated first. Later actions of the batch go to the window the previous action
    left in front, unless an *older* window grabbed the focus (a window that appeared during my own batch, e.g. my
    own dialog, is accepted). If the previous action was one that opens a window (Ctrl+Alt+T, double click, ...)
    and that window has not appeared yet, the next action first waits for it (up to 10 s) instead of typing into
    whatever is in front ("Ctrl+Alt+T + type a script" in one batch sent scripts into documents).
    Alone this only adds the wait for a window the agent itself asked for.

M3  Fast, held input [B, G]. Text is typed at full speed; before each character (python-xlib read of
    _NET_ACTIVE_WINDOW, <1 ms; every 8 chars via xdotool if Xlib is missing) and before each key / hotkey / click the
    focus is checked. If an older window took it, wait 1 s, take it back; if that fails for 15 s, drop the rest of the
    input rather than deliver it elsewhere. A modal dialog of the target window that keeps the focus is followed.
    The official agent types 33 chars/s, so a typed shell script took a minute and was the most common victim.
    "moveTo(x, y); click()" is fused into one click(x, y), so the shared pointer cannot move in between.
    Ctrl+Alt+T runs `gnome-terminal --window --role=<private role>` so the harness knows which terminal is its own.
    Alone: same keystrokes and clicks at the same places, just faster.

M4  Own view before every screenshot [C view instability]. The harness remembers the window its last action left in
    front ("home"). If another window is in front right before a screenshot, home is re-activated -- except windows
    that this harness adopted as its own: windows that appeared during or right after its own actions (or after its
    own window-opening action that was still pending). Unlike SelfGuard (own windows = windows of the task setup,
    usually wrong because both tasks reuse the same app windows, and blind to the agent's new terminal) a window the
    agent opened is never hidden from it, and nothing is raised while it types.

M5  Own browser profile [A shared browser tab / login form / per-session server state]. If a Chromium-family browser
    window is open at start, the harness copies the user's browser profile (cookies, logins, settings; no caches /
    session files) into a profile of its own, opens it in the *running* browser (same process, same debugging port)
    with the open tabs (front tab first) and works there; a session started there (log in, log out, filters stored
    in a server session) is its own. Whenever an action of this harness lands in a browser window it does not own,
    its own browser window is brought up instead (made on demand). Fallback if anything fails: a new window of the
    same profile; then no M5 at all. Alone: same pages in a fresh window with the same logins.

M6  Own terminal [G shared terminal]. If an action lands in a terminal window that appeared after this harness
    started and that it did not open, the harness brings up its own terminal instead (a new one if it has none).
    Terminals open at start are left usable (task setups may open them), so alone nothing changes.

M7  Close fallback. If the agent closes a window and the focus falls on a window that appeared after start and is not
    its own, its previous own window is brought back instead. Alone: never happens (all later windows are its own).

Not addressed per harness in v1 (v1_NOTES.md): two agents inside one single-window application (one Thunderbird main
window, one VS Code window with its terminal panel, one LibreOffice document view), shared files on disk, and the
[INFEASIBLE] decision itself (the hook interface cannot intercept FAIL; a hook is proposed in the notes).
"""
from __future__ import annotations

import json
import re
import shlex
import time
import uuid

from . import DefenseBase

# ----------------------------------------------------------------------------------------------------- M1 guidance
# Identical for every task; must not match oscombo.defense.FORBIDDEN (checked in tests/test_defense.py).
GUIDANCE = """

General notes for working on this computer (they apply to every task):
- This is a live desktop. While you work, windows may come to the front or change, pop-ups may appear, the focus or \
the mouse pointer may move, and files, documents, mailboxes and web pages may be updated or reloaded. These are \
normal, temporary events of this computer. They are never a hard blocker and never a reason to output \
[INFEASIBLE]: take a fresh look at the screen, go back to the window you were using, check what really happened, \
fix only what your own actions got wrong, and continue. Output [INFEASIBLE] only if the task itself cannot be done \
as specified (for example a required app or file does not exist).
- If an action seemed to have no effect or ended up somewhere else, simply look again and repeat it where it \
belongs; the computer is slow, but the tools work.
- Keep things you did not create for this task as they are: do not close, revert, undo or overwrite windows, tabs, \
files, documents, messages, entries or edits that are not part of your task, even if they look unexpected.
- Before you save or write back a file or document, make sure it contains its current content plus your changes. \
Never replace it with an older copy, a backup or an earlier version you made, and never discard changes you did not \
make.
- For shell commands use a terminal window of your own (Ctrl+Alt+T opens a new one) rather than a terminal panel \
inside another application. After opening a window, wait until you see it before typing into it."""

# ------------------------------------------------------------------------------------------------ app classes
BROWSER = re.compile(r"google-chrome|chromium", re.I)              # WM_CLASS of Chromium-family browsers
TERMINAL = re.compile(r"gnome-terminal|xterm|konsole|tilix|terminator|alacritty|kitty|xfce4-terminal", re.I)
FILES = re.compile(r"nautilus|nemo|thunar|pcmanfm", re.I)

DESKTOP = re.compile(r"nautilus-desktop|desktop|ding|gjs", re.I)  # desktop-icons windows (double click opens files)

# actions that usually open a window: the action process waits (until a window appears, at most this long), and if
# none came up the window is expected later ("pending") and adopted when it appears
LAUNCH_TERM = re.compile(r"hotkey\('ctrl', 'alt', 't'\)")
LAUNCH_ANY = re.compile(r"hotkey\('ctrl', (?:'shift', )?'[on]'\)|hotkey\('ctrl', 'shift', 's'\)|"
                        r"hotkey\('(?:super|win)'|hotkey\('alt', 'f2'\)")
LAUNCH_DOUBLE = re.compile(r"doubleClick|clicks=2")          # opens a file only in a file manager / on the desktop
LAUNCH_ENTER = re.compile(r"press\('(?:enter|return)'\)|hotkey\('(?:enter|return)'\)")  # ... in terminals / files
DIALOG_KEYS = re.compile(r"hotkey\('ctrl', '[sp]'\)")       # may show a dialog (save format, print)
CLOSING = re.compile(r"hotkey\('alt', 'f4'\)|hotkey\('ctrl', (?:'shift', )?'[wq]'\)|"
                     r"(?:typewrite|write)\('(?:exit|logout)'")
# actions that may legitimately move the focus to another existing window (mouse, window-switching shortcuts)
SWITCHING = re.compile(r"click|Click|drag|mouse|hotkey\('(?:alt|super|win)'|hotkey\('ctrl', '(?:tab|w|q)'|"
                       r"hotkey\('ctrl', 'shift', '(?:tab|w|q)'\)")
CLOSING = re.compile(r"hotkey\('alt', 'f4'\)|hotkey\('ctrl', '(?:shift', )?'?[wq]'\)|"
                     r"typewrite\('(?:exit|logout)'|write\('(?:exit|logout)'")

# --------------------------------------------------------------------------- M2/M3 Guest-side action wrapper
# The first line must be a plain statement: the controller prepends "import pyautogui; ...; " on the same line.
# Active-window checks use the _NET_ACTIVE_WINDOW property through python-xlib (which pyautogui itself uses on X11),
# so a check costs well under a millisecond and can run before every typed character; xdotool is the fallback.
WRAPPER = r"""import subprocess as _hs, time as _ht, json as _hj, os as _ho
def _h_run(a, t=4, **kw):
    try:
        return _hs.run(a, capture_output=True, text=True, timeout=t, **kw).stdout
    except Exception:
        return ''
def _h_active_x():
    return _h_run(['xdotool', 'getactivewindow']).strip()
_h_active = _h_active_x
_H_EVERY = 8  # without python-xlib a check costs a process: check every 8 characters
_h_role = lambda w: _h_run(['xprop', '-id', w, 'WM_WINDOW_ROLE']).split('=')[-1].strip().strip('"')
try:
    from Xlib import display as _hxd, X as _hX
    _hD = _hxd.Display()
    _hR = _hD.screen().root
    _hNA = _hD.intern_atom('_NET_ACTIVE_WINDOW')
    _hWR = _hD.intern_atom('WM_WINDOW_ROLE')
    _H_EVERY = 1
    def _h_active():
        try:
            p = _hR.get_full_property(_hNA, _hX.AnyPropertyType)
            return str(int(p.value[0])) if p is not None and len(p.value) and int(p.value[0]) else ''
        except Exception:
            return _h_active_x()
    def _h_role(w):
        try:
            p = _hD.create_resource_object('window', int(w)).get_full_property(_hWR, _hX.AnyPropertyType)
            v = p.value if p is not None else b''
            return v.decode() if isinstance(v, bytes) else str(v)
        except Exception:
            return ''
except Exception:
    pass
def _h_wins():
    d = {}
    for ln in _h_run(['wmctrl', '-lx']).splitlines():
        p = ln.split(None, 4)
        if len(p) >= 3:
            try:
                d[str(int(p[0], 16))] = [p[2], p[4] if len(p) > 4 else '']
            except ValueError:
                pass
    return d
def _h_focus(w):
    _h_run(['xdotool', 'windowactivate', '--sync', w], 5)
    _ht.sleep(0.15)
_H_E = %(expected)r
_H_STRICT = %(strict)r
_H_KNOWN = set(%(known)r.split())
_H_ROLE = %(role)r
_h_pre = _h_wins()
_h_fix = 0
_h_late = []
_h_mine = []
if %(await_new)r > 0:
    _h_dl = _ht.time() + %(await_new)r
    while True:
        _h_late = [w for w in _h_pre if w not in _H_KNOWN]
        if _h_late or _ht.time() >= _h_dl:
            break
        _ht.sleep(0.4)
        _h_pre = _h_wins()
    if _h_late:
        _H_E = _h_late[-1]
_h_a0 = _h_active()
_h_tgt = _h_a0
if _H_E and _h_a0 != _H_E and _H_E in _h_pre and (_H_STRICT or _h_late or _h_a0 in _H_KNOWN):
    _h_focus(_H_E)
    _h_fix += 1
    _h_tgt = _H_E
    _h_now = _h_active()
    if _h_now and _h_now != _H_E:  # activation handed the focus on (e.g. to a modal dialog of _H_E): use that
        _h_focus(_H_E)
        _h_now2 = _h_active()
        if _h_now2 == _h_now:
            _h_tgt = _h_now
elif _H_E and _h_a0 == _H_E:
    _h_tgt = _H_E
def _h_hold(any_window=True):
    # Make sure the target window has the focus before the next input. any_window=False accepts a window that
    # appeared during this action (e.g. a dialog opened by my previous key). Returns False if the target could not
    # be given the focus back within 15 s: the caller then drops the input rather than sending it elsewhere.
    global _h_fix, _h_tgt
    dl = _ht.time() + 15
    tries = 0
    while True:
        a = _h_active()
        if not _h_tgt or not a or a == _h_tgt or (not any_window and a not in _h_pre):
            return True
        if _h_tgt not in _h_wins():
            return True  # my window is gone: behave like the plain action
        if tries >= 2 and a not in _h_pre:
            _h_tgt = a  # a new window keeps the focus (e.g. a modal dialog of my window): follow it like before
            return True
        if _ht.time() > dl:
            return False
        tries += 1
        _ht.sleep(1.0)  # another window took the focus: give it a moment (e.g. for a screenshot), then take it back
        _h_focus(_h_tgt)
        _h_fix += 1
        b = _h_active()
        if b and b != _h_tgt:  # activating my window hands the focus on (its modal dialog): follow that window
            _h_focus(_h_tgt)
            if _h_active() == b:
                _h_tgt = b
                return True
def _h_type(message, interval=0.0, *args, **kw):
    import pyautogui
    if not isinstance(message, str):
        return pyautogui.typewrite(message, interval=0) if _h_hold() else None
    for _i, _c in enumerate(message):
        if _i %% _H_EVERY == 0 and _h_active() != _h_tgt and not _h_hold():
            return
        try:
            pyautogui.typewrite(_c, interval=0, _pause=False)
        except TypeError:
            pyautogui.typewrite(_c, interval=0)
def _h_mouse(name):
    def f(*args, **kw):
        import pyautogui
        if _h_hold(False):
            return getattr(pyautogui, name)(*args, **kw)
    return f
for _n in ('click', 'doubleClick', 'tripleClick', 'rightClick', 'middleClick', 'scroll', 'hscroll', 'dragTo',
           'mouseDown', 'mouseUp'):
    globals()['_h_' + _n] = _h_mouse(_n)
def _h_terminal():
    # "open a terminal" with a private window role, so this harness knows which terminal is its own
    global _h_tgt
    before = set(_h_wins())
    ok = False
    try:
        ok = _hs.run(['gnome-terminal', '--window', '--role=' + _H_ROLE], cwd=_ho.path.expanduser('~'),
                     capture_output=True, timeout=15).returncode == 0
    except Exception:
        ok = False
    if not ok:
        import pyautogui
        return pyautogui.hotkey('ctrl', 'alt', 't')
    dl = _ht.time() + 12
    while True:
        wins = _h_wins()
        new = [w for w in wins if w not in before and _h_role(w) == _H_ROLE]
        if not new and _ht.time() >= dl:  # role not readable: a single new terminal is the one I just opened
            new = [w for w in wins if w not in before and 'term' in wins[w][0].lower()]
            new = new if len(new) == 1 else []
        if new:
            _h_mine.extend(new)
            _h_focus(new[-1])
            _h_tgt = new[-1]
            return
        if _ht.time() >= dl:
            return
        _ht.sleep(0.3)
def _h_hotkey(*keys, **kw):
    import pyautogui
    if tuple(str(k).lower() for k in keys) == ('ctrl', 'alt', 't') and _H_ROLE:
        return _h_terminal()
    if _h_hold(False):
        return pyautogui.hotkey(*keys, **kw)
def _h_press(*keys, **kw):
    import pyautogui
    if _h_hold(False):
        return pyautogui.press(*keys, **kw)
_h_ns = dict(globals())
try:
    exec(compile(%(code)r, '<action>', 'exec'), _h_ns)
finally:
    try:
        _h_dl = _ht.time() + %(wait)r
        while True:
            _h_post = _h_wins()
            if any(w not in _h_pre for w in _h_post) or _ht.time() >= _h_dl:
                break
            _ht.sleep(0.3)
        with open(%(scratch)r, 'w') as _hf:
            _hj.dump({'pre': _h_pre, 'post': _h_post, 'a0': _h_a0, 'active': _h_active(), 'fix': _h_fix,
                      'late': _h_late, 'mine': _h_mine, 'tgt': _h_tgt}, _hf)
    except Exception:
        pass
"""

FUSE_CLICK = re.compile(r"pyautogui\.moveTo\(([^()\n]*)\)[ \t]*\n([ \t]*)pyautogui\.(click|doubleClick|tripleClick|"
                        r"rightClick|middleClick)\(([^()\n]*)\)")


def rewrite(code: str) -> str:
    """Pure-python part of M3: fuse pointer moves into clicks, route typing and keys through the focus guard."""
    code = FUSE_CLICK.sub(lambda m: f"{m.group(2)}pyautogui.{m.group(3)}({m.group(1)}"
                                    f"{', ' + m.group(4) if m.group(4).strip() else ''})", code)
    code = re.sub(r"\bpyautogui\.(?:typewrite|write)\(", "_h_type(", code)
    code = re.sub(r"\bpyautogui\.hotkey\(", "_h_hotkey(", code)
    code = re.sub(r"\bpyautogui\.press\(", "_h_press(", code)
    code = re.sub(r"\bpyautogui\.(click|doubleClick|tripleClick|rightClick|middleClick|scroll|hscroll|dragTo|"
                  r"mouseDown|mouseUp)\(", r"_h_\1(", code)
    return code


def wrap(code: str, expected: str | None, strict: bool, known: set[str], wait: float, scratch: str,
         await_new: float = 0.0, role: str = "") -> str:
    """Full Guest program for one action (M2 + M3 + window bookkeeping for M4-M7)."""
    return WRAPPER % {"expected": expected or "", "strict": bool(strict), "known": " ".join(sorted(known)),
                      "code": rewrite(code), "wait": float(wait), "scratch": scratch, "await_new": float(await_new),
                      "role": role}


def launch_kind(code: str, cls: str) -> tuple[float, bool]:
    """(how long the action process waits for a window this action may open, whether to expect it later)."""
    if LAUNCH_TERM.search(code):
        return 8.0, True
    if LAUNCH_ANY.search(code):
        return 4.0, True
    if LAUNCH_DOUBLE.search(code) and (FILES.search(cls) or DESKTOP.search(cls)):
        return 4.0, True
    if LAUNCH_ENTER.search(code) and (TERMINAL.search(cls) or FILES.search(cls)):
        return 1.5, True
    if DIALOG_KEYS.search(code):
        return 2.0, False
    return 0.3, False


class Defense(DefenseBase):
    PENDING_S = 45.0  # how long a window-opening action of mine may take to show its window

    def __init__(self, env, name, guest_sh) -> None:
        super().__init__(env, name, guest_sh)
        self.tag = uuid.uuid4().hex[:12]
        self.scratch = f"/tmp/.h{self.tag}.json"  # private to this harness instance
        self.role = f"h{self.tag}"                 # WM_WINDOW_ROLE of the terminals this harness opens
        self.start_wins: set[str] = set()     # windows present when I started (the user's windows)
        self.own: set[str] = set()            # windows my own actions (or this harness) created
        self.browser: list[str] = []          # my browser windows, most recent last
        self.terminal: list[str] = []         # my terminal windows, most recent last
        self.home: str | None = None          # window my last action left in front
        self.history: list[str] = []          # earlier homes, most recent last
        self.seen: str | None = None          # window in front in the screenshot the model is looking at
        self.known: set[str] = set()          # windows that existed at the last bookkeeping point
        self.cls: dict[str, str] = {}         # WM_CLASS of the windows seen at the last bookkeeping point
        self.batch_first = True
        self.pending: tuple[float, str] | None = None  # (time, kind) of my window-opening action without window yet
        self.show_next: str | None = None     # my late window: show it in the next screenshot
        self.last_act_t = 0.0
        self.browser_failed = False
        self.browser_profile: str | None = None   # --profile-directory of my own profile (None: shared profile)
        self.browser_made_t = 0.0
        self.refreshed = False
        self.stats = {k: 0 for k in ("observe_restored", "action_refocused", "browser_windows_made",
                                     "browser_own_profile", "browser_redirects", "terminal_windows_made",
                                     "terminal_redirects", "close_fallbacks", "adopted", "late_adopted",
                                     "errors")}

    # ------------------------------------------------------------------------------------------- Guest helpers
    def _sh(self, cmd: str) -> str:
        try:
            return self.guest_sh(cmd) or ""
        except Exception:
            self.stats["errors"] += 1
            return ""

    def _snap(self) -> tuple[str, dict[str, list[str]]] | None:
        """(active window id, {id: [wm_class, title]}) of managed windows; ids in decimal like xdotool."""
        out = self._sh("echo ACT $(xdotool getactivewindow 2>/dev/null); wmctrl -lx 2>/dev/null")
        if "ACT" not in out:
            return None
        active, wins = "", {}
        for ln in out.splitlines():
            if ln.startswith("ACT"):
                active = ln[3:].strip()
                continue
            p = ln.split(None, 4)
            if len(p) >= 3:
                try:
                    wins[str(int(p[0], 16))] = [p[2], p[4] if len(p) > 4 else ""]
                except ValueError:
                    pass
        return (active, wins) if wins else None  # there is always a window: an empty list is a failed call

    def _activate(self, wid: str) -> None:
        self._sh(f"xdotool windowactivate --sync {int(wid)} 2>/dev/null; sleep 0.2")

    def _set_home(self, wid: str | None) -> None:
        if wid and wid != self.home:
            if self.home:
                self.history = [w for w in self.history if w != self.home][-15:] + [self.home]
            self.home = wid

    def _fallback_home(self, wins: dict) -> str | None:
        """Most recent earlier home that still exists and is not someone else's later window."""
        for w in reversed(self.history + ([self.home] if self.home else [])):
            if w in wins and (w in self.own or w in self.start_wins):
                return w
        return None

    def _pending_kind(self) -> str | None:
        if self.pending and time.time() - self.pending[0] < self.PENDING_S:
            return self.pending[1]
        self.pending = None
        return None

    # --------------------------------------------------------------------------------- M5 own browser profile
    BROWSER_INFO = r"""python3 - <<'PY'
import json, os, re, shutil, urllib.request
port, exe, udd = None, None, None
for pid in os.listdir('/proc'):
    try:
        args = open('/proc/%s/cmdline' % pid, 'rb').read().split(b'\0')
    except Exception:
        continue
    if not args or not re.search(rb'(chrome|chromium)[^/]*$', args[0]) or any(a.startswith(b'--type=') for a in args):
        continue
    exe = exe or args[0].decode()
    for a in args:
        m = re.match(rb'--remote-debugging-port=(\d+)', a)
        port = int(m.group(1)) if m else port
        m = re.match(rb'--user-data-dir=(.+)', a)
        udd = m.group(1).decode() if m else udd
tabs = []
if port:
    try:
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=10))
    except Exception:
        tabs = []
cmd = next((c for c in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(c)), exe)
if not udd and exe:
    udd = os.path.expanduser('~/.config/' + ('chromium' if 'chromium' in exe else 'google-chrome'))
print('TABS' + json.dumps({'cmd': cmd, 'udd': udd, 'tabs': [{'url': t.get('url', ''), 'title': t.get('title', '')}
                                                          for t in tabs if t.get('type') == 'page']}))
PY"""

    def _browser_info(self, front_title: str) -> tuple[str, str, list[str]]:
        """(browser command, user-data-dir, tab URLs with the tab shown in `front_title` first)."""
        m = re.search(r"TABS(\{.*\})", self._sh(self.BROWSER_INFO))
        if not m:
            return "", "", []
        info = json.loads(m.group(1))
        want = re.sub(r"\s+-\s+(Google Chrome|Chromium)$", "", front_title or "").strip()
        urls: list[str] = []
        for t in sorted(info["tabs"], key=lambda t: t["title"].strip() != want):
            u = t["url"]
            if u and not re.match(r"(devtools|chrome-extension|chrome-untrusted|chrome-search)://", u) \
                    and u != "chrome://newtab/" and u not in urls:
                urls.append(u)
        return info.get("cmd") or "", info.get("udd") or "", urls[:8]

    def _copy_profile(self, udd: str) -> str | None:
        """Copy the user's Default browser profile (cookies, logins, prefs; no caches / sessions / locks)."""
        prof = f"Assist-{self.tag}"
        src, dst = shlex.quote(f"{udd}/Default"), shlex.quote(f"{udd}/{prof}")
        ex = " ".join(f"--exclude={shlex.quote(x)}" for x in (
            "./Cache", "./Code Cache", "./GPUCache", "./Service Worker", "./DawnCache", "./GrShaderCache",
            "./Sessions", "./Current Session", "./Last Session", "./Current Tabs", "./Last Tabs",
            "./Singleton*", "./LOCK"))
        # the copy of a running profile says "crashed": mark it cleanly closed so no "Restore pages?" bubble shows
        fix = ("python3 -c \"import json,sys; p=sys.argv[1]; d=json.load(open(p)); pr=d.setdefault('profile', {}); "
               "pr['exit_type']='Normal'; pr['exited_cleanly']=True; json.dump(d, open(p, 'w'))\" "
               f"{shlex.quote(f'{udd}/{prof}/Preferences')} 2>/dev/null")
        out = self._sh(f"[ -d {src} ] && mkdir -p {dst} && (cd {src} && tar cf - {ex} . 2>/dev/null) | "
                       f"(cd {dst} && tar xf - 2>/dev/null); {fix}; [ -d {dst} ] && echo COPIED")
        return prof if "COPIED" in out else None

    def _launch_browser(self, cmd: str, args: list[str], before: set[str]) -> str | None:
        self._sh(f"setsid -f {' '.join(shlex.quote(a) for a in [cmd] + args)} >/dev/null 2>&1 </dev/null")
        for _ in range(30):  # a new window of a busy browser can take a while on the TCG Guest
            time.sleep(1.0)
            snap = self._snap()
            new = [w for w, (cls, _t) in (snap[1].items() if snap else []) if w not in before and BROWSER.search(cls)]
            if new:
                return new[-1]
        return None

    def _make_browser_window(self, front_title: str) -> str | None:
        if self.browser_failed:
            return None
        cmd, udd, urls = self._browser_info(front_title)
        snap = self._snap()
        if not cmd or snap is None:
            self.browser_failed = True
            return None
        wid = None
        if self.browser_profile is None and udd:
            self.browser_profile = self._copy_profile(udd) or ""
        if self.browser_profile:
            wid = self._launch_browser(cmd, [f"--profile-directory={self.browser_profile}", "--new-window"] + urls,
                                       set(snap[1]))
            if wid:
                self.stats["browser_own_profile"] += 1
            else:
                self.browser_profile = ""  # own profile did not come up: fall back to the shared profile
        if not wid:
            snap = self._snap() or snap
            wid = self._launch_browser(cmd, ["--new-window"] + urls, set(snap[1]))
        if not wid:
            self.browser_failed = True  # do not keep trying; the harness then simply works without M5
            return None
        self.browser.append(wid)
        self.own.add(wid)
        self.stats["browser_windows_made"] += 1
        self.browser_made_t = time.time()
        return wid

    # -------------------------------------------------------------------------------- M6 own terminal window
    def _make_terminal_window(self) -> str | None:
        snap = self._snap()
        if snap is None:
            return None
        before = set(snap[1])
        self._sh(f"cd ~ && setsid -f gnome-terminal --window --role={self.role} >/dev/null 2>&1 </dev/null")
        for _ in range(15):
            time.sleep(1.0)
            snap = self._snap()
            new = [w for w, (cls, _t) in (snap[1].items() if snap else []) if w not in before and TERMINAL.search(cls)]
            if len(new) > 1:  # several new terminals at once: keep the one carrying my role
                roles = self._sh("for w in %s; do echo $w $(xprop -id $w WM_WINDOW_ROLE 2>/dev/null); done"
                                 % " ".join(new))
                new = [ln.split()[0] for ln in roles.splitlines() if self.role in ln] or new[-1:]
            if new:
                self.terminal.append(new[-1])
                self.own.add(new[-1])
                self.stats["terminal_windows_made"] += 1
                return new[-1]
        return None

    def _redirect(self, active: str, wins: dict, created: set[str], closing: bool = False) -> str | None:
        """M5-M7: the window I should be in instead of `active`, or None if `active` is fine for me."""
        if not active or active not in wins or active in self.own or active in created:
            return None
        cls, title = wins[active]
        later = active not in self.start_wins  # appeared after I started and is not mine
        if closing and later:  # M7: focus fell on a later window that is not mine after I closed something
            back = self._fallback_home(wins)
            if back:
                self.stats["close_fallbacks"] += 1
                return back
        if BROWSER.search(cls) and not self.browser_failed:  # M5
            mine = next((w for w in reversed(self.browser) if w in wins), None) or self._make_browser_window(title)
            if mine:
                self.stats["browser_redirects"] += 1
                return mine
        if TERMINAL.search(cls) and later:  # M6
            mine = next((w for w in reversed(self.terminal) if w in wins), None) or self._make_terminal_window()
            if mine:
                self.stats["terminal_redirects"] += 1
                return mine
        return None

    def _adopt(self, wids, wins: dict, by_role: bool = False) -> None:
        """Windows that came up because of my own actions become mine. Terminals only when they carry my private
        window role (every terminal my agent opens with Ctrl+Alt+T gets it), so a terminal that merely appeared
        at the same time is never taken for mine."""
        for w in wids:
            if w in self.own or (TERMINAL.search((wins.get(w) or [""])[0]) and not by_role):
                continue
            self.own.add(w)
            self.stats["adopted"] += 1
            cls = (wins.get(w) or [""])[0]
            if BROWSER.search(cls):
                self.browser.append(w)
            elif TERMINAL.search(cls):
                self.terminal.append(w)

    # ------------------------------------------------------------------------------------------------- hooks
    def start(self, setup_windows: set[str]) -> None:
        snap = self._snap()
        if snap is None:
            return
        active, wins = snap
        self.start_wins = set(wins)
        browsers = [w for w, (cls, _t) in wins.items() if BROWSER.search(cls)]
        if browsers:  # M5: made now, while no agent acts yet, so the new window is unambiguously mine
            front = active if active in browsers else browsers[-1]
            self._make_browser_window(wins[front][1])
            if active and active in wins:
                self._activate(active)  # leave the desktop in front as the task setup left it
        snap = self._snap()
        self.known = set(snap[1]) if snap else set(wins)

    def instruction(self, text: str) -> str:
        return text + GUIDANCE

    def before_observe(self) -> None:
        snap = self._snap()
        if snap is None:
            return
        active, wins = snap
        now = time.time()
        if not self.last_act_t:  # before my first action: late setup windows are the user's windows, like at start
            self.start_wins |= set(wins)
        # M4: windows that came up right after my own last action, or for my pending window-opening action, are mine
        new = [w for w in wins if w not in self.known] if self.known else []
        if new and len(new) <= 2 and self.last_act_t and (now - self.last_act_t < 6.0 or self._pending_kind()):
            self._adopt(new, wins)
            self.pending = None
            if active in new and active in self.own:
                self._set_home(active)
        if self.home is None:
            self._set_home(active)
        target = None
        if self.show_next in wins:
            target = self.show_next
        elif self.home in wins:
            target = self.home
        else:
            target = self._fallback_home(wins) or active
        self.show_next = None
        if target and target not in self.own:
            target = self._redirect(target, wins, set()) or target  # e.g. the setup's browser window -> mine
        if target and target != active and not (active in new and active in self.own):
            self._activate(target)
            self.stats["observe_restored"] += 1
            active = target
        self._set_home(active)
        # sequential runs: my browser window was made at start; refresh its page once if it is long out of date
        if active in self.browser and not self.refreshed and self.browser_made_t and now - self.browser_made_t > 90:
            self._sh("xdotool key --clearmodifiers F5 2>/dev/null; sleep 1.5")
        if active in self.browser:
            self.refreshed = True
        self.seen = active
        self.known = set(wins)
        self.cls = {w: v[0] for w, v in wins.items()}
        self.batch_first = True

    def observe(self, png: bytes) -> bytes:
        """M4: the screenshot must show the window the next action will go to; if the front window changed while
        it was being captured (another program raised a window), give it a moment, raise mine and capture again."""
        for _ in range(3):
            snap = self._snap()
            if snap is None or not self.seen or snap[0] == self.seen or self.seen not in snap[1]:
                return png
            if (snap[0] not in self.known and self.last_act_t and time.time() - self.last_act_t < 10
                    and not TERMINAL.search(snap[1].get(snap[0], [""])[0])):
                # a window that came up right after my own action (e.g. a slow dialog): it is mine, show it
                self._adopt([snap[0]], snap[1])
                self.seen = snap[0]
                self._set_home(snap[0])
                self.known |= set(snap[1])
                try:
                    return self.env.controller.get_screenshot() or png
                except Exception:
                    return png
            time.sleep(1.0)
            self._activate(self.seen)
            self.stats["observe_retaken"] = self.stats.get("observe_retaken", 0) + 1
            try:
                png = self.env.controller.get_screenshot() or png
            except Exception:
                return png
        return png

    def transform_action(self, code: str) -> str | None:
        strict, self.batch_first = self.batch_first, False
        expected = self.seen if strict else self.home
        await_new = 10.0 if (not strict and self._pending_kind()) else 0.0
        wait, _ = launch_kind(code, self.cls.get(expected or "", ""))
        return wrap(code, expected, strict, self.known, wait, self.scratch, await_new, self.role)

    def after_action(self, code: str, record: dict) -> None:
        self.last_act_t = time.time()
        out = self._sh(f"cat {self.scratch} 2>/dev/null; rm -f {self.scratch}")
        try:
            info = json.loads(out.strip().splitlines()[-1]) if out.strip() else None
        except Exception:
            info = None
        if not info:  # the action process died before its bookkeeping: take a plain snapshot
            snap = self._snap()
            if snap is None:
                return
            info = {"pre": {w: v for w, v in snap[1].items() if w in self.known}, "post": snap[1],
                    "active": snap[0], "fix": 0, "late": []}
        pre, post, active = info["pre"], info["post"], info.get("active") or ""
        if not pre or not post:  # a window listing failed in the action process: learn nothing from this action
            self.stats["errors"] += 1
            return
        if info.get("fix"):
            self.stats["action_refocused"] += 1
            record["defense_refocus"] = info["fix"]
        late = [w for w in pre if w not in self.known] if self.known else []  # appeared while the model thought
        if late and len(late) <= 2 and self._pending_kind():  # my slow window: adopt it and show it next time
            self._adopt(late, pre)
            self.stats["late_adopted"] += 1
            self.pending = None
            if not info.get("late"):
                self.show_next = late[-1]
        # terminals are mine only if opened with my private window role (all Ctrl+Alt+T of my agent go that way);
        # any other terminal that comes up meanwhile is not mine, even if it appeared during my action
        mine_terms = {w for w in info.get("mine") or [] if w in post}
        self._adopt(mine_terms, post, by_role=True)
        created = {w for w in post if w not in pre and not TERMINAL.search(post[w][0])}
        created = (created if len(created) <= 2 else set()) | mine_terms  # more at once: not one action of mine
        if created:
            self._adopt(created, post)
            self.pending = None
        elif launch_kind(code, (pre.get(info.get("tgt") or info.get("a0") or "") or [""])[0])[1]:
            self.pending = (self.last_act_t, "launch")
        tgt = info.get("tgt") or ""
        if mine_terms and tgt in mine_terms:
            active = tgt  # I just opened my terminal: that is where my next input goes
        elif active and active != tgt and active not in created and tgt in post and not SWITCHING.search(code):
            active = tgt  # the focus moved during a plain typing action: not my doing, my window stays home
        mine = self._redirect(active, post, created, closing=bool(CLOSING.search(code)))
        if mine and mine != active:
            # no activation here: the next action of the batch (M2) or the next screenshot (M4) brings it up
            record["defense_redirect"] = mine
            active = mine
        if active:
            self._set_home(active)
        self.known = set(post) | set(pre)
        self.cls = {w: v[0] for w, v in {**pre, **post}.items()}
