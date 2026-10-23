"""C6 - one git repository: a dependency bump vs a small feature, each to be committed on its own."""
from __future__ import annotations

import json
import re

from evaluation_examples.task_class.pg_common import HOME, expected, guest, result, sh, upload

REPO = f"{HOME}/projects/invoicer"

INSPECT = r"""cd %s && python3 - <<'PY'
import json, subprocess, sys
def run(*a):
    p = subprocess.run(a, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr
_, log = run('git', 'log', '--format=%%H%%x09%%s', '%s..HEAD')
commits = []
for line in log.splitlines():
    if '\t' not in line:
        continue
    h, s = line.split('\t', 1)
    _, files = run('git', 'show', '--name-only', '--format=', h)
    _, req = run('git', 'show', h + ':requirements.txt')
    commits.append({'hash': h, 'subject': s, 'files': [f for f in files.split() if f], 'requirements': req})
rc, tests = run(sys.executable, '-m', 'unittest', '-q')
probe = '''
import csv, os, tempfile
from app.models import Invoice
from app.report import export_csv
p = os.path.join(tempfile.mkdtemp(), "x.csv")
export_csv([Invoice("I-9", "Umbrella", 12.5, "open"), Invoice("I-10", "Acme", 3.0, "paid")], p)
print(list(csv.reader(open(p))))
'''
prc, pout = run(sys.executable, '-c', probe)
print('INSPECT' + json.dumps({'commits': commits, 'tests_rc': rc, 'tests': tests[-400:],
      'requirements': open('requirements.txt').read(), 'changelog': open('CHANGELOG.md').read(),
      'test_file': open('tests/test_report.py').read(), 'probe_rc': prc, 'probe': pout[-400:]}))
PY"""


def setup(sc):
    upload(sc, [("c6/invoicer.tar.gz", f"{HOME}/projects/invoicer.tar.gz")])
    sh(sc, "cd ~/projects && { [ -d invoicer/.git ] || tar xzf invoicer.tar.gz; } && rm -f invoicer.tar.gz; "
           "mkdir -p ~/.config/Code/User && python3 - <<'PY'\n"
           "import json, os\np = os.path.expanduser('~/.config/Code/User/settings.json')\n"
           "try:\n    s = json.load(open(p))\nexcept Exception:\n    s = {}\n"
           "s.update({'security.workspace.trust.enabled': False, 'git.openRepositoryInParentFolders': 'always'})\n"
           "json.dump(s, open(p, 'w'), indent=1)\nPY")
    sc.launch(["code", REPO])


def _inspect(env) -> dict | None:
    out = guest(env, INSPECT % (REPO, expected("c6")["base"]))
    m = re.search(r"INSPECT(\{.*\})", out, re.S)
    return json.loads(m.group(1)) if m else None


def _pins(text: str) -> dict:
    return {m.group(1).lower(): m.group(2) for m in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([^\s#]+)", text, re.M)}


def _unreleased(changelog: str) -> str:
    m = re.search(r"## Unreleased(.*?)(\n## |\Z)", changelog, re.S)
    return m.group(1) if m else ""


def evaluate_deps(env, dest: str) -> dict:
    info, exp = _inspect(env), expected("c6")
    if not info:
        return result(0.0, {"repo": "unreadable"})
    mine = [c for c in info["commits"] if "sa-2026-07" in c["subject"].lower()]
    c = mine[0] if mine else None
    want = {**exp["fixed"], **exp["unchanged"]}
    files_ok = bool(c) and "requirements.txt" in c["files"] and set(c["files"]) <= {"requirements.txt", "CHANGELOG.md"}
    commit_pins_ok = bool(c) and all(_pins(c["requirements"]).get(k) == v for k, v in want.items())
    head_pins_ok = all(_pins(info["requirements"]).get(k) == v for k, v in want.items())
    log_ok = "sa-2026-07" in _unreleased(info["changelog"]).lower()
    tests_ok = info["tests_rc"] == 0
    parts = [bool(c), files_ok, commit_pins_ok and head_pins_ok, log_ok, tests_ok]
    checks = {"commit": c["subject"] if c else None, "files": c["files"] if c else None, "pins_ok": commit_pins_ok and head_pins_ok,
              "changelog_ok": log_ok, "tests_ok": tests_ok, "all_subjects": [x["subject"] for x in info["commits"]]}
    return result(sum(parts) / len(parts), checks)


def evaluate_csv(env, dest: str) -> dict:
    info = _inspect(env)
    if not info:
        return result(0.0, {"repo": "unreadable"})
    mine = [c for c in info["commits"] if "csv export" in c["subject"].lower()]
    c = mine[0] if mine else None
    allowed = {"app/report.py", "tests/test_report.py", "CHANGELOG.md"}
    files_ok = bool(c) and {"app/report.py", "tests/test_report.py"} <= set(c["files"]) <= allowed
    want_rows = "[['id', 'customer', 'amount', 'status'], ['I-9', 'Umbrella', '12.5', 'open'], ['I-10', 'Acme', '3.0', 'paid']]"
    feature_ok = info["probe_rc"] == 0 and want_rows in info["probe"].replace('"', "'")
    test_ok = "export_csv" in info["test_file"]
    tests_ok = info["tests_rc"] == 0
    log_ok = "csv" in _unreleased(info["changelog"]).lower()
    parts = [bool(c), files_ok, feature_ok, test_ok, tests_ok, log_ok]
    checks = {"commit": c["subject"] if c else None, "files": c["files"] if c else None, "feature_ok": feature_ok,
              "probe": info["probe"][-200:], "test_added": test_ok, "tests_ok": tests_ok, "changelog_ok": log_ok,
              "all_subjects": [x["subject"] for x in info["commits"]]}
    return result(sum(parts) / len(parts), checks)
