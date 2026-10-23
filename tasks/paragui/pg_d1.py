"""D1 - Larder & Co web shop (~/projects/larder-shop, dev server on 8111): one repo, one running server, one
VS Code window, one Chrome session (and one in-memory cart per browser session).

  pgd1cart   fix the cart-total bug of issue 42 (the customer's cart is only in a screenshot) + regression test
  pgd1export bookkeeping CSV export in the layout of a spreadsheet screenshot + Orders-page link + download
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import HOME, expected
from evaluation_examples.task_class.pg_dlib import added, failed, inspect, mine, score, setup_repo, touched

NAME = "larder-shop"
REPO = f"{HOME}/projects/{NAME}"
PORT = 8111
A_FILES = {"shop/cart.py", "tests/test_cart.py", "issues/ISSUE-42.md", "shop/catalog.py", "docs/PRICING.md"}
DOWNLOAD = f"{HOME}/Documents/Bookkeeping/larder-orders-2026-10.csv"


def setup(sc):
    setup_repo(sc, "d1/larder-shop.tar.gz", NAME, PORT, [f"http://127.0.0.1:{PORT}/"])


BODY = r'''
import csv, datetime, io
base = P['base']
OUT['commits'] = commits(base)
OUT['status'] = git('status', '--porcelain')
PRICE = """
import json
from shop.cart import price_cart
out = []
for sc in %s:
    t = price_cart([tuple(x) for x in sc])
    out.append([t.subtotal, t.shipping, t.total])
print('PROBE' + json.dumps(out))
""" % json.dumps([s['items'] for s in P['scenarios']])
OUT['pricing_head'], OUT['pricing_head_log'] = pyprobe(PRICE)
OUT['pricing_at'] = {}
for c in OUT['commits']:
    if any(f == 'shop/cart.py' for _, f in c['files']):
        d = export_tree(c['hash'])
        OUT['pricing_at'][c['hash']] = pyprobe(PRICE, cwd=d)[0]
OUT['test_cart_rc'], OUT['test_cart_out'] = run([sys.executable, '-m', 'unittest', 'tests.test_cart'], timeout=120)
OUT['test_cart_out'] = OUT['test_cart_out'][-800:]
w = copy_worktree()
old = show(base, 'shop/cart.py')
if old is not None:
    open(os.path.join(w, 'shop', 'cart.py'), 'w').write(old)
OUT['test_cart_old_rc'], o = run([sys.executable, '-m', 'unittest', 'tests.test_cart'], cwd=w, timeout=120)
OUT['test_cart_old_out'] = o[-800:]
OUT['test_cart'] = read('tests/test_cart.py') or ''
OUT['issue'] = read('issues/ISSUE-42.md') or ''
OUT['readme'] = read('README.md') or ''

# live server: the customer's cart and a second cart, each in its own cookie session
def cart_total(items):
    c = Client(P['port'])
    for sku, q in items:
        c.req('/cart/add', {'sku': sku, 'qty': str(q)})
    st, _, h = c.req('/cart')
    got = {}
    for k in ('subtotal', 'shipping', 'total'):
        m = re.search(r'id="cart-%s"[^>]*>\s*([^<]*)<' % k, h)
        got[k] = m.group(1).strip() if m else None
    return st, got
OUT['live'] = [cart_total(P['scenarios'][0]['items']), cart_total(P['scenarios'][1]['items'])]

# bookkeeping export: expected rows from the live order data
def load_orders():
    for p in ('data/orders.json', 'data/orders.seed.json'):
        try:
            return json.load(open(p, encoding='utf-8'))
        except Exception:
            pass
    return []
def money(c):
    return '%d,%02d' % (c // 100, c % 100)
def rows_for(orders, month, until=None):
    rows = []
    for o in sorted(orders, key=lambda o: (o['created'], o['id'])):
        if o.get('status') != 'paid' or o['created'][:7] != month:
            continue
        if until and o['created'] > until:
            continue
        y, m, d = o['created'][:10].split('-')
        rows.append(['LC-%s' % o['id'], '%s.%s.%s' % (d, m, y), o['customer'], str(sum(i['qty'] for i in o['items'])),
                     money(o['shipping']), money(o['total']), o['payment']])
    return rows
def parse_csv(text):
    text = text.lstrip('\ufeff')
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=';')]
    return [[x.strip() for x in r] for r in rows if any(x.strip() for x in r)]
orders = load_orders()
OUT['export'] = {}
for month in ('2026-10', '2026-09'):
    st, hd, body = Client(P['port']).req('/orders/export.csv?month=' + month)
    ctype = {k.lower(): v for k, v in hd.items()}.get('content-type', '')
    got = parse_csv(body) if st == 200 else []
    OUT['export'][month] = {'status': st, 'ctype': ctype, 'header': got[0] if got else None, 'rows': got[1:],
                            'expected': rows_for(orders, month), 'raw': body[:600]}
st, _, page = Client(P['port']).req('/orders?month=2026-09')
OUT['orders_page_status'] = st
OUT['export_links'] = re.findall(r'href="([^"]*export[^"]*)"', page)
st, _, page = Client(P['port']).req('/orders')
OUT['export_links_default'] = re.findall(r'href="([^"]*export[^"]*)"', page)
OUT['export_tests'] = []
for f in sorted(os.listdir('tests')) if os.path.isdir('tests') else []:
    if f.endswith('.py') and f.startswith('test') and re.search(r'export', read('tests/' + f) or '', re.I):
        rc, o = run([sys.executable, '-m', 'unittest', 'tests.' + f[:-3]], timeout=120)
        OUT['export_tests'].append([f, rc, o[-400:], show(base, 'tests/' + f) is None or 'export' not in (show(base, 'tests/' + f) or '')])
dl = P['download']
if os.path.exists(dl):
    until = datetime.datetime.fromtimestamp(os.path.getmtime(dl)).strftime('%Y-%m-%dT%H:%M')
    OUT['download'] = {'rows': parse_csv(open(dl, encoding='utf-8', errors='replace').read()),
                       'expected': rows_for(orders, '2026-10', until)}
'''


def _inspect(env):
    exp = expected("d1")
    return inspect(env, REPO, BODY, {"base": exp["base"], "port": PORT, "scenarios": exp["scenarios"],
                                     "download": DOWNLOAD}), exp


def _digits(text) -> str:
    """'€55.40' / '55,40 €' -> '5540' (the shop shows cents with two decimals)."""
    return re.sub(r"\D", "", text or "").lstrip("0") or "0"


def evaluate_cart(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    want = [[s["subtotal"], s["shipping"], s["total"]] for s in exp["scenarios"]]
    mine_c = mine(info, r"#\s*42\b")
    files = touched(mine_c)
    last = next((c["hash"] for c in reversed(mine_c) if c["hash"] in info["pricing_at"]), None)
    head_ok = info["pricing_head"] == want
    commit_fixed = bool(last) and info["pricing_at"].get(last) == want
    total = exp["customer_total"]
    total_rx = r"%d[.,]%02d|\b%d\b" % (total // 100, total % 100, total)
    test = info["test_cart"]
    reg_test = all(sku in test for sku, _ in exp["customer_cart"]) and bool(re.search(total_rx, test))
    issue = info["issue"]
    issue_ok = bool(re.search(r"status\s*:\s*\**\s*(fixed|resolved|closed|done)", issue, re.I)) and bool(
        re.search(r"%d[.,]%02d" % (total // 100, total % 100), issue))
    live = info["live"]
    s1 = exp["scenarios"][1]
    live_customer = live[0][0] == 200 and _digits(live[0][1].get("total")) == str(total)
    live_other = live[1][0] == 200 and _digits(live[1][1].get("total")) == str(s1["total"])
    dirty = {ln[3:].strip() for ln in info["status"].splitlines() if ln[:2].strip() and not ln.startswith("??")}
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_has_fix_and_test", {"shop/cart.py", "tests/test_cart.py"} <= files, 1),
        ("commit_focused", bool(files) and files <= A_FILES, 1),
        ("fix_in_commit", commit_fixed, 1),
        ("pricing_correct_head", head_ok, 2),
        ("cart_tests_pass", info["test_cart_rc"] == 0, 1),
        ("regression_test_is_customer_cart", reg_test, 1),
        ("regression_test_fails_on_old_code", info["test_cart_old_rc"] != 0 and info["test_cart_rc"] == 0, 1),
        ("server_restarted_customer_total", live_customer, 1),
        ("server_second_cart_total", live_other, 0.5),
        ("issue_marked_fixed_with_total", issue_ok, 1),
        ("work_committed", not (dirty & {"shop/cart.py", "tests/test_cart.py", "issues/ISSUE-42.md"}), 0.5),
    ]
    caps = [(not head_ok, 0.4, "pricing still wrong"), (not mine_c, 0.5, "no #42 commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "pricing_head": info["pricing_head"], "want": want, "live": live,
                                "test_old_rc": info["test_cart_old_rc"]})


def evaluate_export(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    head = exp["template_head"]
    mine_c = [c for c in mine(info, r"export|csv|bookkeep") if not re.search(r"#\s*42\b", c["subject"])]
    files = touched(mine_c)
    ex = info["export"]

    def exact(m):
        e = ex[m]
        return e["status"] == 200 and e["header"] == head and e["rows"] == e["expected"] and len(e["expected"]) > 0
    oct_ok, sep_ok = exact("2026-10"), exact("2026-09")
    link_ok = any("export.csv" in h and "month=2026-09" in h for h in info["export_links"]) and any(
        "export.csv" in h for h in info["export_links_default"])
    readme_ok = "/orders/export.csv" in info["readme"] and "month" in info["readme"].split("/orders/export.csv", 1)[-1][:600]
    tests_ok = any(rc == 0 and new for _, rc, _, new in info["export_tests"]) and all(
        rc == 0 for _, rc, _, _ in info["export_tests"])
    dl = info.get("download")
    dl_ok = bool(dl) and bool(dl["rows"]) and dl["rows"][0] == head and dl["rows"][1:] == dl["expected"] and len(dl["expected"]) > 0
    dirty = {ln[3:].strip() for ln in info["status"].splitlines() if ln[:2].strip()}
    untracked_code = {f for f in dirty if re.match(r"(shop|tests)/.*\.py$", f)}
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", bool(files) and not (files & A_FILES) and not any(f.startswith("data/orders.json") for f in files), 1),
        ("export_october_exact", oct_ok, 2),
        ("export_september_exact", sep_ok, 1),
        ("served_as_csv", "text/csv" in ex["2026-10"]["ctype"].lower(), 0.5),
        ("orders_page_link_for_shown_month", link_ok, 1),
        ("readme_documents_endpoint", readme_ok, 0.5),
        ("export_test_added_and_passing", tests_ok, 1),
        ("downloaded_october_file", dl_ok, 1),
        ("work_committed", bool(files) and not ((dirty & files) | (untracked_code - A_FILES)), 0.5),
    ]
    caps = [(not oct_ok, 0.4, "October export wrong or not served"), (not mine_c, 0.5, "no export commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "added": sorted(added(mine_c)), "oct_status": ex["2026-10"]["status"],
                                "oct_header": ex["2026-10"]["header"], "oct_rows_got": ex["2026-10"]["rows"][:3],
                                "oct_rows_want": ex["2026-10"]["expected"][:3], "links": info["export_links"],
                                "export_tests": [t[:2] for t in info["export_tests"]]})
