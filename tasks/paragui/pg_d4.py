"""D4 - shorebirds (~/projects/shorebirds, report server on 8114): one repo, one working tree that the release
must build from (make_dist refuses a dirty tree), one report server both must restart, one VS Code, one Chrome.

  pgd4table    fix the Table 2 analysis (crash on the 2026 sheet + regression), match the paper's scanned Table 2
  pgd4release  release 1.4.0: changelog from git history, version x3, Zenodo DOI/date from a screenshot, tag, dist
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import HOME, expected
from evaluation_examples.task_class.pg_dlib import failed, inspect, mine, score, setup_repo, touched

NAME = "shorebirds"
REPO = f"{HOME}/projects/{NAME}"
PORT = 8114
RELEASE_FILES = {"pyproject.toml", "shorebirds/__init__.py", "CITATION.cff", "CHANGELOG.md", "README.md"}


def setup(sc):
    setup_repo(sc, "d4/shorebirds.tar.gz", NAME, PORT, [f"http://127.0.0.1:{PORT}/"])


BODY = r'''
import csv, hashlib, io, tarfile
base = P['base']
OUT['commits'] = commits(base)
OUT['status'] = git('status', '--porcelain')

def table_csv(text):
    if not text:
        return None
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return None
    years = rows[0][1:]
    t = {}
    for r in rows[1:]:
        if not r:
            continue
        t[r[0].strip()] = {y.strip(): float(v) for y, v in zip(years, r[1:]) if v.strip()}
    return t
def svg_values(text):
    t = {}
    for sp, y, v in re.findall(r'data-species="([^"]+)"\s+data-year="(\d{4})"\s+data-value="([\d.]+)"', text or ''):
        t.setdefault(sp.replace('&amp;', '&'), {})[y] = float(v)
    return t
try:
    OUT['results'] = table_csv(read('results/table2.csv'))
except Exception as e:
    OUT['results'] = None
OUT['figure'] = svg_values(read('results/fig2_trends.svg'))

# hidden survey sheets through the CLI
d = tempfile.mkdtemp(prefix='pgd4')
os.makedirs(os.path.join(d, 'data'))
for name, text in P['hidden'].items():
    open(os.path.join(d, 'data', name), 'w').write(text)
rc, o = run([sys.executable, '-m', 'shorebirds.run_all', '--data', os.path.join(d, 'data'), '--out', os.path.join(d, 'out')],
            timeout=120)
OUT['hidden_rc'], OUT['hidden_log'] = rc, o[-600:]
try:
    OUT['hidden'] = table_csv(open(os.path.join(d, 'out', 'table2.csv')).read())
except Exception:
    OUT['hidden'] = None
OUT['tests_rc'], OUT['tests_out'] = unittest_all()
w = copy_worktree()
for f in ('shorebirds/io.py', 'shorebirds/analysis.py'):
    old = show(base, f)
    if old is not None:
        open(os.path.join(w, f), 'w').write(old)
OUT['tests_old_rc'], _ = unittest_all(cwd=w)

# release state
refs = git('for-each-ref', 'refs/tags', '--format=%(refname:short)\t%(objecttype)\t%(*objectname)\t%(objectname)\t%(contents:subject)')
OUT['tags'] = {}
for line in refs.splitlines():
    p = line.split('\t')
    if len(p) == 5:
        OUT['tags'][p[0]] = {'type': p[1], 'commit': p[2] if p[1] == 'tag' else p[3], 'message': p[4]}
rel = 'v1.4.0' if 'v1.4.0' in OUT['tags'] else 'HEAD'
OUT['rel_ref'] = rel
OUT['at_rel'] = {f: show(rel, f) for f in ('pyproject.toml', 'shorebirds/__init__.py', 'CITATION.cff', 'CHANGELOG.md', 'README.md')}
OUT['head_files'] = {f: read(f) for f in ('CITATION.cff', 'README.md', 'shorebirds/__init__.py')}
dist = 'dist/shorebirds-%s.tar.gz' % P['version']
OUT['dist'] = None
if os.path.exists(dist) and 'v1.4.0' in OUT['tags']:
    tree = {}
    for line in git('ls-tree', '-r', 'v1.4.0').splitlines():
        meta, path = line.split('\t', 1)
        tree[path] = meta.split()[2]
    got, prefixes, problems = {}, set(), []
    try:
        with tarfile.open(dist) as t:
            for m in t.getmembers():
                if not m.isfile():
                    continue
                top, _, rest = m.name.partition('/')
                prefixes.add(top)
                data = t.extractfile(m).read()
                got[rest] = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
    except Exception as e:
        problems.append(repr(e))
    OUT['dist'] = {'prefixes': sorted(prefixes), 'missing': sorted(set(tree) - set(got))[:10],
                   'extra': sorted(set(got) - set(tree))[:10],
                   'changed': sorted(p for p in set(tree) & set(got) if tree[p] != got[p])[:10], 'problems': problems}

# live report
st, _, page = Client(P['port']).req('/')
m = re.search(r'<footer[^>]*>(.*?)</footer>', page, re.S)
live = {}
for sp, cells in re.findall(r'<tr data-species="([^"]+)">(.*?)</tr>', page, re.S):
    live[sp.replace('&amp;', '&')] = {y: float(v) for y, v in re.findall(r'data-year="(\d{4})">([\d.]+)<', cells)}
OUT['live'] = {'status': st, 'footer': m.group(1) if m else '', 'table': live, 'error': 'Analysis failed' in page}
'''


def _inspect(env):
    exp = expected("d4")
    return inspect(env, REPO, BODY, {"base": exp["base"], "port": PORT, "hidden": exp["hidden_files"],
                                     "version": exp["version"]}), exp


def _same_table(got, want, tol=0.051) -> bool:
    if not isinstance(got, dict) or set(got) != set(want):
        return False
    for sp, ys in want.items():
        g = got.get(sp) or {}
        if set(g) != set(ys) or any(abs(g[y] - v) > tol for y, v in ys.items()):
            return False
    return True


def _dirty(info) -> set[str]:
    return {ln[3:].strip() for ln in info["status"].splitlines() if ln[:2].strip()}


def evaluate_table(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    mine_c = [c for c in mine(info, r"table\s*2|2026 survey") if not re.search(r"release", c["subject"], re.I)]
    files = touched(mine_c)
    want = exp["table2"]
    hidden_ok = info["hidden_rc"] == 0 and _same_table(info["hidden"], exp["hidden_table"])
    results_ok = _same_table(info["results"], want)
    fig_ok = _same_table(info["figure"], want)
    tests_added = any(f.startswith("tests/") and f.endswith(".py") for f in files)
    live = info["live"]
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", bool(files) and not (files & (RELEASE_FILES - {"CHANGELOG.md"})), 1),
        ("analysis_correct_on_unseen_sheets", hidden_ok, 2),
        ("results_table_matches_paper", results_ok, 1.5),
        ("figure_matches_paper", fig_ok, 1),
        ("results_committed", {"results/table2.csv", "results/fig2_trends.svg"} <= files and
         not ({"results/table2.csv", "results/fig2_trends.svg"} & _dirty(info)), 0.5),
        ("tests_pass_and_test_added", info["tests_rc"] == 0 and tests_added, 1),
        ("new_test_fails_on_old_code", info["tests_old_rc"] != 0 and info["tests_rc"] == 0, 1),
        ("report_server_shows_fixed_table", live["status"] == 200 and _same_table(live["table"], want), 1),
    ]
    caps = [(not hidden_ok, 0.4, "analysis still wrong"), (not mine_c, 0.5, "no Table 2 commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "hidden_log": info["hidden_log"][-300:] if not hidden_ok else "",
                                "results": info["results"]})


def _changelog_section(text: str):
    lines = (text or "").splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^##\s*\[?v?1\.4\.0\]?", ln):
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            return ln, "\n".join(lines[i + 1:j]), "\n".join(lines[:i])
    return None, "", text or ""


def evaluate_release(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    v, doi, old_doi, date = exp["version"], exp["doi"], exp["old_doi"], exp["date"]
    mine_c = mine(info, r"release\s*v?1\.4\.0")
    files = touched(mine_c)
    at = info["at_rel"]
    py = at.get("pyproject.toml") or ""
    ini = at.get("shorebirds/__init__.py") or ""
    cff = at.get("CITATION.cff") or ""
    versions_ok = bool(re.search(r'(?m)^version\s*=\s*"%s"' % re.escape(v), py)) and \
        bool(re.search(r'__version__\s*=\s*["\']%s["\']' % re.escape(v), ini)) and \
        bool(re.search(r'(?m)^version:\s*"?%s"?\s*$' % re.escape(v), cff))
    cff_ok = bool(re.search(r'(?m)^date-released:\s*"?%s"?\s*$' % date, cff)) and \
        bool(re.search(r'(?m)^doi:\s*"?%s"?\s*$' % re.escape(doi), cff))
    readme = at.get("README.md") or ""
    badge_ok = doi in readme and old_doi not in readme
    head, section, before = _changelog_section(at.get("CHANGELOG.md"))
    cl_ok = bool(head) and date in head and all(re.search(r"#%s\b" % i[1:], section) for i in exp["issues"])
    unrel = re.search(r"(?ms)^##\s*\[?Unreleased\]?\s*$(.*)", before)
    unrel_empty = bool(unrel) and not re.search(r"(?m)^\s*[-*]\s+\S", unrel.group(1))
    tag = info["tags"].get("v1.4.0")
    rel_hashes = {c["hash"] for c in mine_c}
    tag_ok = bool(tag) and tag["type"] == "tag" and tag["commit"] in rel_hashes
    dist = info["dist"]
    dist_ok = bool(dist) and dist["prefixes"] == ["shorebirds-%s" % v] and not (
        dist["missing"] or dist["extra"] or dist["changed"] or dist["problems"])
    live = info["live"]
    footer_ok = live["status"] == 200 and re.search(r"\b%s\b" % re.escape(v), live["footer"]) and doi in live["footer"]
    checks = [
        ("release_commit_exists", bool(mine_c), 1),
        ("release_commit_focused", bool(files) and files <= RELEASE_FILES, 1),
        ("version_bumped_in_three_places", versions_ok, 1.5),
        ("citation_date_and_doi_from_zenodo", cff_ok, 1),
        ("readme_doi_badge", badge_ok, 0.5),
        ("changelog_1_4_0_lists_all_changes", cl_ok, 1.5),
        ("changelog_unreleased_emptied", unrel_empty, 0.5),
        ("annotated_tag_on_release_commit", tag_ok, 1),
        ("dist_archive_matches_tag", dist_ok, 1.5),
        ("report_footer_shows_release", bool(footer_ok), 1),
    ]
    caps = [(not versions_ok, 0.4, "version not bumped"), (not tag, 0.5, "no v1.4.0 tag")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "tag": tag, "dist": dist, "footer": live["footer"][:200], "changelog_head": head})
