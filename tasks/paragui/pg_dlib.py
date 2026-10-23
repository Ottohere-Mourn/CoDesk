"""Shared helpers for the F4 software-development pairs d1-d4 (one repo + one running dev server + VS Code + Chrome).

Grading runs one Python inspection script inside the Guest (python3.10 stdlib only): it reads the git history,
runs the tests, probes the live dev server over HTTP and the repo's code in subprocesses, and prints one JSON
document. The host side turns that into weighted sub-checks."""
from __future__ import annotations

import json
import re

from evaluation_examples.task_class.pg_common import HOME, guest, open_chrome, result, sh, upload

VSCODE_SETTINGS = ("mkdir -p ~/.config/Code/User && python3 - <<'PY'\n"
                   "import json, os\np = os.path.expanduser('~/.config/Code/User/settings.json')\n"
                   "try:\n    s = json.load(open(p))\nexcept Exception:\n    s = {}\n"
                   "s.update({'security.workspace.trust.enabled': False, 'git.openRepositoryInParentFolders': 'always',"
                   " 'workbench.startupEditor': 'none', 'git.autofetch': False})\n"
                   "json.dump(s, open(p, 'w'), indent=1)\nPY")


def setup_repo(sc, asset_tar: str, name: str, port: int, urls: list[str], extra: str = ""):
    """Extract the repo once (~/projects/<name>), start its dev server once (./dev.sh start, guarded by an HTTP
    probe), open the folder in VS Code and the app in the shared Chrome. Safe to run twice (dual runs)."""
    repo = f"{HOME}/projects/{name}"
    upload(sc, [(asset_tar, f"{HOME}/projects/{name}.tar.gz")])
    sh(sc, f"mkdir -p ~/projects && cd ~/projects && {{ [ -d {name}/.git ] || tar xzf {name}.tar.gz; }} && "
           f"rm -f {name}.tar.gz; {extra}\n{VSCODE_SETTINGS}")
    sh(sc, f"cd ~/projects/{name} && {{ curl -s -o /dev/null -m 2 http://127.0.0.1:{port}/ || "
           f"setsid -f ./dev.sh start > /dev/null 2>&1 < /dev/null; }}; "
           f"for i in $(seq 60); do curl -s -o /dev/null -m 2 http://127.0.0.1:{port}/ && break; sleep 1; done", timeout=150)
    sc.launch(["code", repo])
    open_chrome(sc, urls)


# ------------------------------------------------------------------ Guest-side prelude (python3.10, stdlib only)
PRELUDE = r'''
import json, os, re, shutil, subprocess, sys, tempfile, urllib.error, urllib.request, urllib.parse, http.cookiejar
OUT = {}
REPO = os.getcwd()

def run(args, cwd=None, timeout=300, env=None, input=None):
    try:
        p = subprocess.run(args, cwd=cwd or REPO, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})}, input=input)
        return p.returncode, (p.stdout or '') + (p.stderr or '')
    except subprocess.TimeoutExpired as e:
        return 124, 'TIMEOUT'
    except Exception as e:
        return 125, repr(e)

def git(*a):
    return run(['git'] + list(a))[1]

def commits(base):
    """Commits reachable from HEAD but not from base, oldest first, with name-status file lists."""
    rc, log = run(['git', 'log', '--reverse', '--format=%H', base + '..HEAD'])
    if rc != 0:
        rc, log = run(['git', 'log', '--reverse', '--format=%H', '-n', '30'])
    out = []
    for h in log.split():
        subj = git('log', '-1', '--format=%s', h).strip()
        body = git('log', '-1', '--format=%B', h)
        ns = git('show', '--name-status', '--format=', '-M', h)
        files = []
        for line in ns.splitlines():
            parts = line.split('\t')
            if len(parts) >= 2:
                files.append([parts[0][0], parts[-1]])
                if parts[0][0] == 'R':
                    files.append(['D', parts[1]])
        out.append({'hash': h, 'subject': subj, 'body': body[:2000], 'files': files,
                    'parents': git('log', '-1', '--format=%P', h).split()})
    return out

def diff_text(h, paths=None):
    return git('show', '--format=', '-U0', h, '--', *(paths or []))

def show(rev, path):
    rc, txt = run(['git', 'show', rev + ':' + path])
    return txt if rc == 0 else None

def read(path):
    try:
        return open(os.path.join(REPO, path), encoding='utf-8', errors='replace').read()
    except OSError:
        return None

def export_tree(rev):
    """Files of a commit in a temporary directory (python files only need to import from there)."""
    d = tempfile.mkdtemp(prefix='pginsp')
    p1 = subprocess.Popen(['git', 'archive', rev], cwd=REPO, stdout=subprocess.PIPE)
    subprocess.run(['tar', 'x', '-C', d], stdin=p1.stdout)
    p1.wait()
    return d

def copy_worktree():
    d = tempfile.mkdtemp(prefix='pginsp')
    dst = os.path.join(d, 'w')
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns('.git', '__pycache__', 'logs', '_site', 'dist'))
    return dst

def pyprobe(code, cwd=None, timeout=120):
    """Run python code in a subprocess (cwd defaults to the repo); the code prints 'PROBE' + json."""
    rc, out = run([sys.executable, '-c', code], cwd=cwd, timeout=timeout)
    m = re.search(r'PROBE(.*)', out)
    if m:
        try:
            return json.loads(m.group(1)), out[-1500:]
        except Exception:
            pass
    return None, out[-1500:]

class Client:
    def __init__(self, port):
        self.base = 'http://127.0.0.1:%d' % port
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def req(self, path, data=None, timeout=20):
        try:
            body = urllib.parse.urlencode(data).encode() if data is not None else None
            r = self.op.open(urllib.request.Request(self.base + path, data=body), timeout=timeout)
            return r.status, dict(r.headers), r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {}), (e.read() or b'').decode('utf-8', 'replace')
        except Exception as e:
            return 0, {}, repr(e)

def unittest_all(cwd=None, timeout=300):
    rc, out = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.'], cwd=cwd, timeout=timeout)
    return rc, out[-1500:]
'''


def inspect(env, repo: str, body: str, params: dict, timeout: int = 600) -> dict | None:
    script = (f"cd {repo} 2>/dev/null || {{ echo 'INSPECT{{\"missing\": true}}'; exit 0; }}\n"
              f"python3 - <<'PGD_EOF'\nimport json as _j\nP = _j.loads({json.dumps(params)!r})\n" + PRELUDE + body +
              "\nprint('INSPECT' + json.dumps(OUT, default=str))\nPGD_EOF")
    out = guest(env, script, timeout=timeout)
    m = re.search(r"INSPECT(\{.*\})\s*$", out.strip(), re.S)
    if not m:
        return {"error": out[-3000:]}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {"error": out[-3000:]}


# ------------------------------------------------------------------ host-side scoring helpers
def mine(info: dict, pattern: str) -> list[dict]:
    rx = re.compile(pattern, re.I)
    return [c for c in info.get("commits", []) if rx.search(c["subject"])]


def touched(cs: list[dict]) -> set[str]:
    return {f for c in cs for _, f in c["files"]}


def added(cs: list[dict]) -> set[str]:
    return {f for c in cs for st, f in c["files"] if st == "A"}


def deleted(cs: list[dict]) -> set[str]:
    return {f for c in cs for st, f in c["files"] if st == "D"}


def score(checks: list[tuple[str, bool, float]], caps: list[tuple[bool, float, str]], extra: dict | None = None) -> dict:
    """checks: (name, ok, weight); caps: (condition, max score, reason) applied when condition is True."""
    total = sum(w for _, _, w in checks)
    s = sum(w for _, ok, w in checks if ok) / total if total else 0.0
    applied = []
    for cond, mx, why in caps:
        if cond and s > mx:
            s = mx
            applied.append(why)
    detail = {name: bool(ok) for name, ok, _ in checks}
    detail["caps_applied"] = applied
    if extra:
        detail.update(extra)
    return result(s, detail)


def failed(reason: str, info=None) -> dict:
    return result(0.0, {"error": reason, "detail": (info or {}).get("error", "")[-1500:] if isinstance(info, dict) else ""})
