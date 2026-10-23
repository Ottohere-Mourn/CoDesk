"""D2 - meterflow (~/projects/meterflow, dashboard on 8112): one repo, one settings file both tasks change, one
dashboard process both must restart, one VS Code window, one Chrome tab.

  pgd2toml    migrate settings.ini -> settings.toml (ADR-0007) everywhere + deploy/prod.toml from a screenshot
  pgd2kelvar  parser for the new vendor Kelvar (fixed-width KMF, spec only as a scanned PDF) + config + tests
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import HOME, expected
from evaluation_examples.task_class.pg_dlib import deleted, failed, inspect, mine, score, setup_repo, touched

NAME = "meterflow"
REPO = f"{HOME}/projects/{NAME}"
PORT = 8112
B_ONLY = re.compile(r"^(meterflow/parsers/kelvar\.py|tests/test_kelvar.*|docs/vendors/|data/inbox/kelvar/)")
A_ONLY = re.compile(r"^(meterflow/config\.py|\.vscode/|deploy/|meterflow/_vendor/|docs/adr/)")


def setup(sc):
    setup_repo(sc, "d2/meterflow.tar.gz", NAME, PORT, [f"http://127.0.0.1:{PORT}/"])


BODY = r'''
import configparser, datetime
base = P['base']
OUT['commits'] = commits(base)
OUT['status'] = git('status', '--porcelain')
OUT['tracked'] = git('ls-files').split('\n')

def load_toml(text):
    if text is None:
        return None, 'missing'
    mods = []
    for name in ('tomllib', 'tomli'):
        try:
            mods.append(__import__(name))
        except ImportError:
            pass
    if not mods:
        sys.path.insert(0, REPO)
        try:
            from meterflow._vendor import tomli as t
            mods.append(t)
        except Exception as e:
            return None, 'no toml parser: %r' % e
    try:
        return mods[0].loads(text), ''
    except Exception as e:
        return None, repr(e)[:300]

def ini_dict(text):
    """What the pre-migration load_config() returned for this INI text."""
    cp = configparser.ConfigParser()
    cp.read_string(text)
    cfg = {'pipeline': {'inbox_dir': cp.get('pipeline', 'inbox_dir'), 'out_dir': cp.get('pipeline', 'out_dir'),
                        'timezone': cp.get('pipeline', 'timezone'),
                        'interval_minutes': cp.getint('pipeline', 'interval_minutes')},
           'alerts': {'enabled': cp.getboolean('alerts', 'enabled'),
                      'max_kwh_per_interval': cp.getfloat('alerts', 'max_kwh_per_interval'),
                      'notify': [x.strip() for x in cp.get('alerts', 'notify').split(',') if x.strip()]},
           'dashboard': {'title': cp.get('dashboard', 'title'), 'port': cp.getint('dashboard', 'port')},
           'vendors': {}}
    for s in cp.sections():
        if s.startswith('vendor:'):
            cfg['vendors'][s[7:]] = {'enabled': cp.getboolean(s, 'enabled'), 'format': cp.get(s, 'format'),
                                     'inbox': cp.get(s, 'inbox'), 'meter_prefix': cp.get(s, 'meter_prefix')}
    return cfg

# --- migration commits: INI of the parent vs TOML of the commit
OUT['migrations'] = {}
for c in OUT['commits']:
    if any(f == 'settings.toml' and st in 'AR' for st, f in c['files']) and c['parents']:
        ini = show(c['parents'][0], 'settings.ini')
        try:
            want = ini_dict(ini) if ini else None
        except Exception as e:
            want = None
        got, err = load_toml(show(c['hash'], 'settings.toml'))
        OUT['migrations'][c['hash']] = {'want': want, 'got': got, 'err': err}
OUT['settings_diffs'] = {c['hash']: diff_text(c['hash'], ['settings.ini', 'settings.toml']) for c in OUT['commits']}
OUT['parsers_diffs'] = {c['hash']: diff_text(c['hash'], ['meterflow/parsers/__init__.py']) for c in OUT['commits']}

# --- working tree
OUT['ini_on_disk'] = os.path.exists('settings.ini')
OUT['toml_head'], OUT['toml_err'] = load_toml(read('settings.toml'))
OUT['prod'], OUT['prod_err'] = load_toml(read('deploy/prod.toml'))
refs = []
for f in OUT['tracked'] + [ln[3:] for ln in OUT['status'].splitlines() if ln.startswith('??')]:
    if f.startswith('meterflow/_vendor/') or not re.search(r'\.(py|json|sh|toml|cfg|ini)$|(^|/)dev\.sh$', f):
        continue
    if 'settings.ini' in (read(f) or ''):
        refs.append(f)
OUT['ini_refs'] = refs
lj = read('.vscode/launch.json') or ''
try:
    lj_clean = re.sub(r',(\s*[\]}])', r'\1', re.sub(r'(?m)^\s*//.*$', '', lj))
    launch = json.loads(lj_clean)
    OUT['launch'] = [{'name': c.get('name'), 'args': c.get('args', [])} for c in launch.get('configurations', [])]
except Exception as e:
    OUT['launch'] = None
OUT['readme'] = read('README.md') or ''
OUT['tests_rc'], OUT['tests_out'] = unittest_all()
OUT['check_rc'], OUT['check_out'] = run(['bash', 'scripts/check.sh'], timeout=300)
OUT['check_out'] = OUT['check_out'][-800:]

# --- code probes
tmpd = tempfile.mkdtemp(prefix='pgd2')
custom = os.path.join(tmpd, 'custom.toml')
open(custom, 'w').write('[pipeline]\ninbox_dir = "in"\nout_dir = "out"\ntimezone = "UTC"\ninterval_minutes = 5\n'
                        '[alerts]\nenabled = false\nmax_kwh_per_interval = 1.5\nnotify = ["a@x", "b@x"]\n'
                        '[dashboard]\ntitle = "T"\nport = 9000\n'
                        '[vendors.x]\nenabled = false\nformat = "acme_csv"\ninbox = "x"\nmeter_prefix = "X"\n')
hid = os.path.join(tmpd, 'KMF_TEST_20261231.kmf')
open(hid, 'wb').write(P['hidden'].encode())
bad = os.path.join(tmpd, 'KMF_TEST_20261230.kmf')
open(bad, 'wb').write(P['bad'].encode())
PROBE = """
import json, sys, tempfile, traceback
from datetime import timezone
out = {}
try:
    from meterflow.config import load_config
    c = load_config(); c.pop('_source', None); out['default'] = c
except Exception:
    out['default_err'] = traceback.format_exc()[-600:]
try:
    c = load_config(%(custom)r); c.pop('_source', None); out['custom'] = c
except Exception:
    out['custom_err'] = traceback.format_exc()[-600:]
try:
    from meterflow.parsers import PARSERS
    out['formats'] = sorted(PARSERS)
    v = (out.get('default') or {}).get('vendors', {}).get('kelvar')
    if v:
        parse = PARSERS[v['format']]
        rows = []
        for r in parse(%(hid)r):
            ts = r.ts.astimezone(timezone.utc) if r.ts.tzinfo else r.ts
            rows.append([r.meter_id, ts.strftime('%%Y-%%m-%%dT%%H:%%M'), round(r.kwh, 4), r.quality])
        out['hidden'] = rows
        try:
            res = parse(%(bad)r)
            out['bad'] = 'returned %%d records' %% len(res)
        except Exception as e:
            out['bad'] = 'raised ' + type(e).__name__
except Exception:
    out['parser_err'] = traceback.format_exc()[-800:]
try:
    from meterflow.pipeline import run
    s = run(load_config(), tempfile.mkdtemp())
    k = s['vendors'].get('kelvar')
    out['pipeline_kelvar'] = k and {'total_kwh': k['total_kwh'], 'readings': k['readings'], 'rejected': len(k['rejected']),
                                    'meters': k['meters']}
except Exception:
    out['pipeline_err'] = traceback.format_exc()[-600:]
print('PROBE' + json.dumps(out))
""" % {'custom': custom, 'hid': hid, 'bad': bad}
OUT['probe'], OUT['probe_log'] = pyprobe(PROBE)

# --- kelvar tests
OUT['kelvar_tests'] = []
for f in sorted(os.listdir('tests')) if os.path.isdir('tests') else []:
    if f.startswith('test') and f.endswith('.py') and re.search('kelvar', read('tests/' + f) or '', re.I):
        rc, o = run([sys.executable, '-m', 'unittest', 'tests.' + f[:-3]], timeout=120)
        OUT['kelvar_tests'].append([f, rc, o[-300:]])

# --- live dashboard
c = Client(P['port'])
st, _, page = c.req('/config')
m = re.search(r'id="config-source"[^>]*>([^<]*)<', page)
OUT['live_config'] = {'status': st, 'source': m.group(1) if m else None, 'has_toml': 'settings.toml' in page}
st, _, page = c.req('/')
rows = {}
for vid, body in re.findall(r'<tr id="vendor-([\w-]+)">(.*?)</tr>', page, re.S):
    rows[vid] = dict(re.findall(r'<td class="num (\w+)">([^<]*)</td>', body))
OUT['live_vendors'] = {'status': st, 'rows': rows}
'''


def _inspect(env):
    exp = expected("d2")
    return inspect(env, REPO, BODY, {"base": exp["base"], "port": PORT, "hidden": exp["hidden_kmf"],
                                     "bad": exp["hidden_bad_trailer"]}), exp


def _same_core(got: dict | None, want: dict | None) -> bool:
    """Non-vendor sections identical; every vendor of `want` present and identical (extra vendors allowed)."""
    if not isinstance(got, dict) or not isinstance(want, dict):
        return False
    for sec in ("pipeline", "alerts", "dashboard"):
        if got.get(sec) != want.get(sec):
            return False
    gv = got.get("vendors") or {}
    return all(gv.get(n) == v for n, v in (want.get("vendors") or {}).items())


def _typed_equal(a, b) -> bool:
    """Equality that also distinguishes bool/int/float (True == 1 must not pass)."""
    if type(a) is not type(b) and not ({type(a), type(b)} <= {int, float} and not isinstance(a, bool) and not isinstance(b, bool)):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def _dirty(info) -> set[str]:
    return {ln[3:].strip() for ln in info["status"].splitlines() if ln[:2].strip()}


def evaluate_toml(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    mine_c = mine(info, r"toml|ADR-?0*7")
    mine_c = [c for c in mine_c if not re.search(r"kelvar", c["subject"], re.I)]
    files = touched(mine_c)
    hashes = {c["hash"] for c in mine_c}
    mig = [v for h, v in info["migrations"].items() if h in hashes]
    faithful = bool(mig) and all(_same_core(m["got"], m["want"]) and _typed_equal(
        {k: m["got"][k] for k in ("pipeline", "alerts", "dashboard")},
        {k: m["want"][k] for k in ("pipeline", "alerts", "dashboard")}) for m in mig)
    pr = info.get("probe") or {}
    dev = exp["dev"]
    loader_ok = _same_core(pr.get("default"), dev) and isinstance(pr.get("custom"), dict) and \
        pr["custom"].get("alerts", {}).get("notify") == ["a@x", "b@x"] and pr["custom"].get("vendors", {}).get("x", {}).get("enabled") is False
    head_toml_ok = _same_core(info["toml_head"], dev)
    ini_gone = not info["ini_on_disk"] and "settings.ini" not in info["tracked"] and "settings.ini" in deleted(mine_c)
    launch = info["launch"]
    launch_ok = bool(launch) and len(launch) >= 2 and all("settings.ini" not in " ".join(map(str, c["args"])) for c in launch)
    readme = info["readme"]
    readme_ok = "settings.toml" in readme and "vendor:<name>" not in readme and "comma-separated" not in readme
    prod_ok = isinstance(info["prod"], dict) and _typed_equal(info["prod"], exp["prod"])
    parsers_clean = not any("kelvar" in info["parsers_diffs"].get(h, "").lower() for h in hashes)
    live = info["live_config"]
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", bool(files) and not any(B_ONLY.match(f) for f in files) and parsers_clean, 1),
        ("toml_faithful_to_ini_in_commit", faithful, 2),
        ("settings_ini_deleted", ini_gone, 1),
        ("loader_reads_toml", loader_ok and head_toml_ok, 2),
        ("no_ini_references_in_code_or_config", not info["ini_refs"], 1),
        ("vscode_launch_configs_updated", launch_ok, 0.5),
        ("readme_updated", readme_ok, 0.5),
        ("deploy_prod_toml_matches_screenshot", prod_ok, 2),
        ("check_sh_passes", info["check_rc"] == 0, 1),
        ("dashboard_restarted_on_toml", live["status"] == 200 and bool(live["source"]) and "settings.toml" in live["source"], 1),
        ("work_committed", bool(files) and not (_dirty(info) & {"settings.toml", "deploy/prod.toml", "meterflow/config.py",
                                                                 "settings.ini", "tests/test_config.py"}), 0.5),
    ]
    caps = [(not (loader_ok and head_toml_ok), 0.4, "app does not load settings.toml"), (not mine_c, 0.5, "no TOML commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "ini_refs": info["ini_refs"], "prod": info["prod"], "prod_err": info["prod_err"],
                                "toml_err": info["toml_err"], "live": live, "probe_errs": {k: v for k, v in pr.items() if k.endswith("_err")},
                                "check_out": info["check_out"][-300:] if info["check_rc"] else ""})


def evaluate_kelvar(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    k = exp["kelvar"]
    mine_c = mine(info, r"kelvar|KMF")
    files = touched(mine_c)
    hashes = {c["hash"] for c in mine_c}
    removed_settings = any(re.search(r"(?m)^-(?!--)\s*\S", info["settings_diffs"].get(h, "")) for h in hashes)
    focused = bool(files) and not any(A_ONLY.match(f) for f in files) and "settings.ini" not in deleted(mine_c) and \
        not any(f == "settings.toml" and st in "AR" for c in mine_c for st, f in c["files"]) and not removed_settings
    pr = info.get("probe") or {}
    v = ((pr.get("default") or {}).get("vendors") or {}).get("kelvar") or {}
    configured = v.get("enabled") is True and v.get("format") in (pr.get("formats") or []) and \
        v.get("inbox") == k["inbox"] and v.get("meter_prefix") == k["meter_prefix"]
    hidden_ok = sorted(pr.get("hidden") or []) == sorted(exp["hidden_expected"])
    bad = pr.get("bad") or ""
    rejected_ok = bad.startswith("raised") or bad == "returned 0 records"
    pk = pr.get("pipeline_kelvar") or {}
    pipe_ok = abs((pk.get("total_kwh") or 0) - k["total_kwh"]) < 0.002 and pk.get("readings") == k["readings"] and \
        pk.get("rejected") == k["rejected"]
    row = info["live_vendors"]["rows"].get("kelvar") or {}
    try:
        live_ok = abs(float(row.get("kwh", "nan")) - k["total_kwh"]) < 0.002 and int(row.get("readings", -1)) == k["readings"]
    except ValueError:
        live_ok = False
    tests = info["kelvar_tests"]
    readme_rows = [ln for ln in info["readme"].splitlines() if ln.startswith("|") and "kelvar" in ln.lower()]
    dirty = _dirty(info)
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", focused, 1),
        ("vendor_configured_and_registered", configured, 1),
        ("hidden_kmf_file_parsed_exactly", hidden_ok, 2),
        ("incomplete_file_rejected", rejected_ok, 1),
        ("sample_deliveries_totals", pipe_ok, 1),
        ("dashboard_restarted_shows_kelvar", live_ok, 1),
        ("kelvar_tests_pass", bool(tests) and all(rc == 0 for _, rc, _ in tests), 1),
        ("check_sh_passes", info["check_rc"] == 0, 0.5),
        ("readme_vendor_table", bool(readme_rows), 0.5),
        ("work_committed", bool(files) and not any(f.startswith(("meterflow/parsers/", "tests/test_kelvar")) for f in dirty), 0.5),
    ]
    caps = [(not hidden_ok, 0.4, "parser wrong on an unseen KMF file"), (not mine_c, 0.5, "no Kelvar commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "hidden_got": pr.get("hidden"), "bad": bad, "pipeline": pk, "live_row": row,
                                "probe_errs": {k2: v2 for k2, v2 in pr.items() if k2.endswith("_err")},
                                "tests": [t[:2] for t in tests]})
