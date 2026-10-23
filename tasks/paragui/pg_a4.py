"""A4 - Tidewater Community Libraries website (~/projects/tidewater-libraries, dev server on 8134): one working tree,
one git index, one running dev server, one VS Code window, one Chrome.

  pga4closures  "Holiday closures" page /closures from the council's scanned notice (with a handwritten correction)
  pga4fees      "Fees & charges" page /fees from a phone photo of the laminated fees sheet (with a pen correction)

The repo's CONTRIBUTING.md makes every new page touch the same five shared files (routes.py, nav.html,
tests/test_routes.py, README.md, CHANGELOG.md). Each task must commit exactly its own change; the checkers read the
added lines of each task's own commits and require all of its own hunks and none of the other page's.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from evaluation_examples.task_class.pg_common import HOME, expected
from evaluation_examples.task_class.pg_dlib import failed, inspect, mine, score, setup_repo, touched

NAME = "tidewater-libraries"
REPO = f"{HOME}/projects/{NAME}"
PORT = 8134
SHARED = {"routes": "tidewater/routes.py", "nav": "tidewater/templates/nav.html", "tests": "tests/test_routes.py",
          "readme": "README.md", "changelog": "CHANGELOG.md"}
ROLE = {
    "A": {"path": "/closures", "data": "tidewater/data/closures.json", "page": "tidewater/pages/closures.py",
          "subject": r"closure"},
    "B": {"path": "/fees", "data": "tidewater/data/fees.json", "page": "tidewater/pages/fees.py",
          "subject": r"\bfees?\b|charges"},
}


def setup(sc):
    setup_repo(sc, f"a4/{NAME}.tar.gz", NAME, PORT, [f"http://127.0.0.1:{PORT}/"])


BODY = r'''
base = P['base']
OUT['commits'] = commits(base)

def added_lines(diff):
    out, cur = {}, None
    for ln in diff.splitlines():
        if ln.startswith('+++ '):
            cur = ln[6:] if ln.startswith('+++ b/') else None
        elif ln.startswith('+') and not ln.startswith('+++') and cur:
            out.setdefault(cur, []).append(ln[1:])
    return out

PROBE = """
import json, sys
sys.path.insert(0, '.')
out = {}
try:
    from tidewater.routes import ROUTES
    from tidewater.server import render
    out['routes'] = sorted(ROUTES)
    for p in sorted(set(ROUTES) | {'/closures', '/fees'}):
        try:
            st, html = render(p)
        except Exception as e:
            st, html = -1, repr(e)
        out[p] = [st, html[:30000] if p in ('/closures', '/fees') else '']
except Exception as e:
    out['error'] = repr(e)
print('PROBE' + json.dumps(out))
"""
for c in OUT['commits']:
    c['added'] = added_lines(git('show', '--format=', '-U0', '--no-color', '--no-renames', c['hash']))
    d = export_tree(c['hash'])
    c['probe'] = pyprobe(PROBE, cwd=d)[0]
    c['data'] = {k: show(c['hash'], v) for k, v in P['data'].items()}
dh = export_tree('HEAD')
OUT['head_probe'], OUT['head_probe_log'] = pyprobe(PROBE, cwd=dh)
OUT['head_tests_rc'], OUT['head_tests_out'] = unittest_all(cwd=dh)
OUT['head_data'] = {k: show('HEAD', v) for k, v in P['data'].items()}
OUT['head_test_routes'] = show('HEAD', 'tests/test_routes.py') or ''
OUT['head_readme'] = show('HEAD', 'README.md') or ''
OUT['status'] = git('status', '--porcelain', '--untracked-files=all')
OUT['wt_added'] = added_lines(git('diff', 'HEAD', '-U0', '--no-color'))
OUT['live'] = {}
for p in ('/', '/closures', '/fees'):
    st, _, body = Client(P['port']).req(p)
    OUT['live'][p] = [st, body[:30000]]
'''


def _inspect(env):
    exp = expected("a4")
    params = {"base": exp["base"], "port": PORT, "data": {r: ROLE[r]["data"] for r in ROLE}}
    return inspect(env, REPO, BODY, params), exp


# ---------------------------------------------------------------- content checks
def _branch(s) -> str:
    s = str(s or "").lower()
    for key, words in (("central", ("central", "harbour")), ("millbrook", ("millbrook",)), ("eastgate", ("eastgate",))):
        if any(w in s for w in words):
            return key
    return s.strip()


def _hours(s) -> str:
    s = str(s or "").strip().lower().replace("–", "-").replace("—", "-").replace(" to ", "-")
    s = re.sub(r"\s+", "", s)
    if "closed" in s:
        return "closed"
    m = re.fullmatch(r"(\d{1,2})[:.](\d\d)-(\d{1,2})[:.](\d\d)", s)
    return "%02d:%s-%02d:%s" % (int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)) if m else s


def _load(text):
    try:
        data = json.loads(text) if text else None
    except Exception:
        return None
    if isinstance(data, dict):  # {"closures": [...]} style wrappers
        data = next((v for v in data.values() if isinstance(v, list)), None)
    return data if isinstance(data, list) else None


def closures_score(text, exp) -> tuple[int, int, int]:
    """(correct, extra, expected count)"""
    rows = _load(text)
    if rows is None:
        return 0, 0, len(exp["closures"])
    got = {(_branch(r.get("branch")), str(r.get("date", "")).strip(), _hours(r.get("hours"))) for r in rows if isinstance(r, dict)}
    want = {(_branch(e["branch"]), e["date"], e["hours"]) for e in exp["closures"]}
    return len(got & want), len(got - want), len(want)


def _fee(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().lower()
    if "free" in s or s in ("", "none", "-"):
        return 0.0 if "free" in s else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*p\b", s)
    if m and "£" not in s:
        return float(m.group(1)) / 100
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def fees_score(text, exp) -> tuple[int, int, int]:
    rows = _load(text)
    if rows is None:
        return 0, 0, len(exp["fees"])
    rows = [r for r in rows if isinstance(r, dict)]
    used, ok = set(), 0
    for e in exp["fees"]:
        for i, r in enumerate(rows):
            item = " ".join(str(v) for k, v in r.items() if k != "fee")
            f = _fee(r.get("fee"))
            if i not in used and f is not None and abs(f - e["fee"]) < 0.005 and re.search(e["kw"], item, re.I):
                used.add(i)
                ok += 1
                break
    return ok, len(rows) - len(used), len(exp["fees"])


def _date_forms(d: str) -> list[str]:
    x = dt.date.fromisoformat(d)
    mon, month = x.strftime("%b"), x.strftime("%B")
    return [d, f"{x.day} {mon}", f"{x.day} {month}", f"{mon} {x.day}", f"{month} {x.day}", f"{x.day:02d}/{x.month:02d}",
            f"{x.day}/{x.month}", f"{x.day}.{x.month}."]


def live_ok(role, html, exp) -> bool:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text)
    if role == "A":
        dates = {e["date"] for e in exp["closures"]}
        return all(any(f.lower() in text.lower() for f in _date_forms(d)) for d in dates) and all(
            b in text.lower() for b in ("central", "millbrook", "eastgate"))
    amounts = [e["fee"] for e in exp["fees"] if e["fee"] > 0]
    forms = lambda v: [f"{v:.2f}"] + ([f"{int(round(v * 100))}p"] if v < 1 else [])  # noqa: E731
    return all(any(f in text for f in forms(v)) for v in amounts)


# ---------------------------------------------------------------- scoring
def _evaluate(env, role: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    other = "B" if role == "A" else "A"
    me, ot = ROLE[role], ROLE[other]
    mark, omark = exp["marks"][role], exp["marks"][other]
    own = mine(info, me["subject"])
    files = touched(own)
    added = {}
    for c in own:
        for f, lines in c["added"].items():
            added.setdefault(f, []).extend(lines)

    def has(marks, f_key, lines):
        return any(re.search(re.escape(marks[f_key]) if f_key != "changelog" else marks[f_key], ln, re.I) for ln in lines)
    own_hunks = {k: has(mark, k, added.get(f, [])) for k, f in SHARED.items()}
    foreign_hunks = {k: has(omark, k, added.get(f, [])) for k, f in SHARED.items()}
    foreign_files = sorted(files & {ot["data"], ot["page"]})
    foreign_elsewhere = [f for f, lines in added.items() if f not in SHARED.values()
                         and any(ot["path"] + "'" in ln or ot["path"] + '"' in ln for ln in lines)]
    clean = not any(foreign_hunks.values()) and not foreign_files and not foreign_elsewhere
    all_own = all(own_hunks.values())

    # own commit's tree works on its own
    last = next((c for c in reversed(own) if c.get("probe")), None)
    pr = (last or {}).get("probe") or {}
    tree_ok = bool(pr) and "error" not in pr and pr.get(me["path"], [0])[0] == 200 and all(
        pr.get(p, [0])[0] == 200 for p in pr.get("routes", []))
    data_key = role
    scorer = closures_score if role == "A" else fees_score
    commit_data = scorer((last or {}).get("data", {}).get(data_key), exp) if last else (0, 0, 1)

    hp = info.get("head_probe") or {}
    head_page = bool(hp) and "error" not in hp and hp.get(me["path"], [0])[0] == 200 and me["path"] in hp.get("routes", [])
    ok_n, extra_n, want_n = scorer(info["head_data"].get(data_key), exp)
    data_exact = ok_n == want_n and extra_n == 0
    data_mostly = ok_n >= want_n - 2 and extra_n <= 1
    route_test = bool(re.search(r"""['"]%s['"]""" % re.escape(me["path"]), info["head_test_routes"]))
    readme_ok = me["path"] in info["head_readme"]
    live = info["live"]
    live_page = live.get(me["path"], [0, ""])[0] == 200 and live_ok(role, live[me["path"]][1], exp)
    live_nav = bool(re.search(r'href="%s"' % re.escape(me["path"]), live.get("/", [0, ""])[1]))
    wt = info.get("wt_added", {})
    left = {k for k, f in SHARED.items() if has(mark, k, wt.get(f, []))}
    untracked = [ln[3:] for ln in info["status"].splitlines() if ln[3:] in (me["data"], me["page"])]
    work_committed = bool(own) and not left and not untracked

    checks = [
        ("commit_exists", bool(own), 1),
        ("commit_has_page_files", {me["data"], "tidewater/routes.py"} <= files and any(
            f.startswith("tidewater/pages/") for f in files), 1),
        ("commit_has_all_own_shared_changes", bool(own) and all_own, 2),
        ("commit_has_nothing_of_other_change", bool(own) and clean, 2),
        ("commit_tree_serves_page", tree_ok and commit_data[0] >= commit_data[2] - 2, 1),
        ("data_mostly_correct_head", data_mostly, 1),
        ("data_exact_head", data_exact, 1),
        ("tests_pass_head", info["head_tests_rc"] == 0, 1),
        ("route_test_lists_page", route_test, 0.5),
        ("readme_lists_page", readme_ok, 0.5),
        ("live_server_serves_page", live_page, 1),
        ("live_menu_link", live_nav, 0.5),
        ("work_committed", work_committed, 0.5),
    ]
    caps = [(not own, 0.5, "no commit for this change"),
            (not head_page, 0.4, "page not served by the code at HEAD"),
            (bool(own) and not (all_own and clean), 0.75, "commit does not contain exactly this change")]
    return score(checks, caps, {
        "commits": [c["subject"] for c in info["commits"]], "own_commit_files": sorted(files),
        "own_shared_changes": own_hunks, "foreign_in_own_commit": {k: v for k, v in foreign_hunks.items() if v},
        "foreign_files": foreign_files, "data_head": f"{ok_n}/{want_n} (+{extra_n} extra)",
        "data_in_commit": f"{commit_data[0]}/{commit_data[2]}", "tests_tail": info["head_tests_out"][-300:],
        "live_status": live.get(me["path"], [0])[0], "uncommitted_own": sorted(left) + untracked})


def evaluate_closures(env, dest: str) -> dict:
    return _evaluate(env, "A")


def evaluate_fees(env, dest: str) -> dict:
    return _evaluate(env, "B")
