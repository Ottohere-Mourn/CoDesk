"""Helpers shared by the paraGUI contention task classes (task_pg*.py); deployed next to them in task_class/."""
from __future__ import annotations

import json
import os
import re

import requests

ASSETS = os.environ.get("PARAGUI_TASK_ASSETS", os.path.expanduser("~/.cache/oscombo/paragui/assets"))
HOME = "/home/user"


def upload(setup_controller, pairs):
    """Copy (asset-relative source, absolute Guest path) pairs into the Guest."""
    setup_controller.download([{"url": os.path.join(ASSETS, src), "path": dst} for src, dst in pairs])


def sh(setup_controller, script: str, timeout: int = 120):
    setup_controller.execute(["bash", "-c", script], timeout=timeout)


def guest(env, script: str, timeout: int = 180) -> str:
    """Run a bash script in the Guest at evaluation time; returns stdout+stderr."""
    r = requests.post(f"http://{env.vm_ip}:{env.server_port}/execute",
                      json={"command": ["bash", "-c", script], "shell": False, "timeout": timeout}, timeout=timeout + 30)
    out = r.json()
    return (out.get("output") or "") + (out.get("error") or "")


def fetch(env, path: str, dest: str):
    """Copy a Guest file to the host cache; returns the local path or None."""
    from desktop_env.evaluators.getters.file import get_vm_file
    try:
        p = get_vm_file(env, {"path": path, "dest": dest})
        return p if p and os.path.exists(p) else None
    except Exception:
        return None


TREE = r"""python3 - <<'PY'
import hashlib, json, os
out = {}
for root in %s:
    root = os.path.expanduser(root)
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            try:
                out[os.path.relpath(p, os.path.expanduser('~'))] = hashlib.md5(open(p, 'rb').read()).hexdigest()
            except OSError:
                pass
print('TREE' + json.dumps(out))
PY"""


def tree(env, roots) -> dict:
    """{path relative to ~: md5} for every file under the given Guest directories."""
    out = guest(env, TREE % json.dumps(list(roots)))
    m = re.search(r"TREE(\{.*\})", out)
    return json.loads(m.group(1)) if m else {}


def guest_json(env, script: str, tag: str = "OUT", timeout: int = 180):
    """Run a Guest bash script that prints TAG + one JSON document; return the parsed JSON or None."""
    out = guest(env, script, timeout)
    m = re.search(tag + r"(\{.*\}|\[.*\])", out, re.S)
    return json.loads(m.group(1)) if m else None


# ---------------------------------------------------------------- "company intranet" web apps inside the Guest
WEBAPP_DIR = f"{HOME}/.local/share/intranet"


def start_webapp(setup_controller, app_asset: str, name: str, port: int, db_asset: str | None = None):
    """Upload a single-file stdlib web app (and its seeded sqlite db) and start it on 127.0.0.1:<port>.
    The app is started only once per Guest (the second task of a pair re-runs setup), via setsid so the
    setup call returns. Convention: the app takes --db PATH --port N and serves http://127.0.0.1:N/."""
    d = f"{WEBAPP_DIR}/{name}"
    pairs = [(app_asset, f"{d}/app.py")] + ([(db_asset, f"{d}/seed.db")] if db_asset else [])
    upload(setup_controller, pairs)
    sh(setup_controller,
       f"cd {d} && [ -f app.db ] || cp seed.db app.db 2>/dev/null; "
       f"(curl -sf -m 2 http://127.0.0.1:{port}/ >/dev/null) || "
       f"(setsid -f python3 {d}/app.py --db {d}/app.db --port {port} > {d}/server.log 2>&1 < /dev/null); "
       f"for i in $(seq 30); do curl -sf -m 2 -o /dev/null http://127.0.0.1:{port}/ && break; sleep 1; done")


def webapp_db(name: str) -> str:
    return f"{WEBAPP_DIR}/{name}/app.db"


SQL = r"""python3 - <<'PY'
import json, sqlite3
con = sqlite3.connect(%s)
con.row_factory = sqlite3.Row
out = {}
for key, q in %s.items():
    out[key] = [dict(r) for r in con.execute(q)]
print('SQL' + json.dumps(out, default=str))
PY"""


def sql(env, db_path: str, queries: dict) -> dict | None:
    """Run read-only SQL queries against a Guest sqlite db: {key: query} -> {key: [row dicts]}."""
    return guest_json(env, SQL % (repr(db_path), repr(queries)), tag="SQL")


def open_chrome(setup_controller, urls: list[str]):
    """Start Chrome the way OSWorld tasks do (remote debugging on 1337, reachable from the host) and open tabs.
    In a dual run the second task's tabs open in the already running browser, i.e. both tasks share one Chrome."""
    setup_controller.launch("pgrep -x chrome >/dev/null || exec google-chrome --remote-debugging-port=1337", shell=True)
    # the host reaches Chrome's debugging port through Guest port 9222 (as in the OSWorld tasks)
    setup_controller.launch("pgrep -x socat >/dev/null || exec socat tcp-listen:9222,fork tcp:localhost:1337",
                            shell=True)
    setup_controller._chrome_open_tabs_setup(urls)


# ---------------------------------------------------------------- Thunderbird (profiles built with lib_thunderbird.py)
MBOX = r"""python3 - <<'PY'
import email, email.policy, glob, json, os, re
out = {}
for prof in glob.glob(os.path.expanduser('~/.thunderbird/*/Mail')):
    for d, _, fs in os.walk(prof):
        for f in fs:
            p = os.path.join(d, f)
            if '.' in f or os.path.getsize(p) == 0:
                continue
            data = open(p, 'rb').read()
            if not data.startswith(b'From '):
                continue
            folder = os.path.relpath(p, prof).replace('.sbd/', '/')
            for chunk in re.split(rb'(?m)^From .*\r?\n', data)[1:]:
                m = email.message_from_bytes(chunk, policy=email.policy.default)
                status = int((m.get('X-Mozilla-Status') or '0').strip() or '0', 16)
                if status & 0x0008:
                    continue
                body = m.get_body(('plain', 'html'))
                text = body.get_content() if body is not None else ''
                atts = [(a.get_filename() or '') for a in m.iter_attachments()]
                out.setdefault(folder, []).append({
                    'id': (m.get('Message-ID') or '').strip(), 'subject': str(m.get('Subject') or ''),
                    'from': str(m.get('From') or ''), 'to': str(m.get('To') or ''), 'cc': str(m.get('Cc') or ''),
                    'irt': str(m.get('In-Reply-To') or '') + ' ' + str(m.get('References') or ''),
                    'read': bool(status & 0x0001), 'flagged': bool(status & 0x0004),
                    'keys': (m.get('X-Mozilla-Keys') or '').split(), 'attachments': atts,
                    'text': re.sub(r'<[^>]+>', ' ', text)[:4000]})
print('MBOX' + json.dumps(out))
PY"""


def start_thunderbird(setup_controller, profile_asset: str, marker: str):
    """Install a lib_thunderbird profile once per Guest and start one Thunderbird (the second task of a pair
    re-runs setup: it must neither reset the profile nor open a second window)."""
    upload(setup_controller, [(profile_asset, f"{HOME}/thunderbird-profile.tar.gz")])
    sh(setup_controller, f"[ -f ~/.thunderbird/.{marker} ] || {{ rm -rf ~/.thunderbird && "
                         f"tar xzf ~/thunderbird-profile.tar.gz -C ~ && touch ~/.thunderbird/.{marker}; }}; "
                         "rm -f ~/thunderbird-profile.tar.gz")
    setup_controller.launch("pgrep -x thunderbird >/dev/null || exec /usr/bin/thunderbird", shell=True)


def mail_folders(env) -> dict | None:
    """{folder path relative to Mail/ (e.g. 'pop.x.com/Inbox', 'pop.x.com/Projects/Apollo'): [live messages]}.
    Messages carrying Thunderbird's deleted flag (moved away / deleted, not yet compacted) are skipped."""
    return guest_json(env, MBOX, tag="MBOX")


def expected(name: str) -> dict:
    return json.load(open(os.path.join(ASSETS, name, "expected.json")))


def result(score: float, checks: dict) -> dict:
    return {"score": round(score, 4), "checks": checks}
