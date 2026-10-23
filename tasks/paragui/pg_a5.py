"""A5 - Fenwick & Bloom Home & Garden: one ShopAdmin back office (Chrome, one login) shared by two chores.

A (pga5prices): supplier's scanned price-change letter -> cost + recalculated retail (policy markup, 99p rule), keep
   the discount % of products on promotion, discontinued item -> status, summary CSV.
B (pga5sale):   designer's flyer proof with handwritten corrections -> Black Friday sale price / dates / label on 13
   products (sale price from the current retail), price list CSV for the printer.
8 products are in both lists. The product edit form writes every field back on Save (no version check).
"""
from __future__ import annotations

import csv
import io
import re
from decimal import ROUND_HALF_UP, Decimal

from evaluation_examples.task_class import pg_common as pc

APP, PORT = "shopadmin", 8135


def setup(sc):
    pc.sh(sc, "mkdir -p ~/Documents/Suppliers ~/Documents/Pricing ~/Documents/Marketing")
    pc.upload(sc, [("a5/Greenleaf_price_change_Nov2026.pdf", f"{pc.HOME}/Documents/Suppliers/Greenleaf_price_change_Nov2026.pdf"),
                   ("a5/BF_flyer_proof_marked.pdf", f"{pc.HOME}/Documents/Marketing/BF_flyer_proof_marked.pdf")])
    pc.start_webapp(sc, "a5/app_a5.py", APP, PORT, "a5/shopadmin_seed.db")
    pc.open_chrome(sc, [f"http://127.0.0.1:{PORT}/login"])


# ---------------------------------------------------------------- helpers
def sale_of(retail, pct) -> float:
    return float((Decimal(str(retail)) * Decimal(100 - pct) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def eq(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.006


def flat(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def money(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[£$€\s ]", "", str(v)).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def label_pct(label):
    m = re.search(r"(\d{1,2})\s*%", str(label or ""))
    return int(m.group(1)) if m else None


def read_db(env):
    return pc.sql(env, pc.webapp_db(APP), {"products": "SELECT * FROM products",
                                           "changes": "SELECT * FROM changes ORDER BY id"})


def read_csv(env, path, dest):
    """Rows (list of lists) of a CSV the agent wrote; delimiter sniffed (, ; tab)."""
    lp = pc.fetch(env, path, dest)
    if not lp:
        return None
    raw = open(lp, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.splitlines()[0] if text.strip() else ""
    delim = max([",", ";", "\t"], key=first.count)
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]


def header(rows, need):
    """Index of the first row that contains a cell matching each predicate in need; returns (row_idx, {key: col})."""
    for i, r in enumerate(rows[:5]):
        cols = {}
        for key, pred in need.items():
            for j, c in enumerate(r):
                if pred(flat(c)) and j not in cols.values():
                    cols[key] = j
                    break
        if len(cols) == len(need):
            return i, cols
    return None, {}


def saved_then_lost(changes, sku, field, value) -> bool:
    """The value was saved for this product at some point (price history), i.e. a later save overwrote it."""
    return any(c["sku"] == sku and c["field"] == field and money(c["new"]) is not None and eq(money(c["new"]), value)
               for c in changes)


def result(score, checks, caps):
    for cond, cap, why in caps:
        if cond and score > cap:
            score = cap
            checks.setdefault("caps", []).append(why)
    return pc.result(score, checks)


# ---------------------------------------------------------------- A: supplier price change
def evaluate_prices(env, dest: str) -> dict:
    exp = pc.expected("a5")
    q = read_db(env)
    if not q:
        return pc.result(0.0, {"app_db": "unreadable"})
    P = {p["sku"]: p for p in q["products"]}
    ch = q["changes"]
    checks = {}
    # 1. repriced products: cost (0.4) + retail (0.6)
    pts, wrong = 0.0, []
    for sku, r in exp["reprice"].items():
        p = P.get(sku) or {}
        c_ok, r_ok = eq(p.get("cost"), r["new_cost"]), eq(p.get("retail"), r["new_retail"])
        pts += 0.4 * c_ok + 0.6 * r_ok
        if not (c_ok and r_ok):
            why = f"{sku} {r['name']}: cost {p.get('cost')} retail {p.get('retail')} (want {r['new_cost']} / {r['new_retail']})"
            if (not r_ok and saved_then_lost(ch, sku, "retail", r["new_retail"])) or \
                    (not c_ok and saved_then_lost(ch, sku, "cost", r["new_cost"])):
                why += " - LOST UPDATE: the right price was saved, a later save overwrote it"
            wrong.append(why)
    n = len(exp["reprice"])
    frac = pts / n
    checks["repriced"] = f"{pts:g}/{n}"
    checks["reprice_problems"] = wrong
    # 2. promotions keep their discount
    au = exp["autumn"]
    p = P.get(au["sku"]) or {}
    autumn_ok = (eq(p.get("sale_price"), au["new_sale"]) and p.get("sale_start") == au["start"] and p.get("sale_end") == au["end"]
                 and label_pct(p.get("promo_label")) == au["pct"])
    checks["autumn_promo_recalculated"] = autumn_ok or f"sale {p.get('sale_price')} {p.get('promo_label')} (want {au['new_sale']})"
    stale = []
    for sku, r in exp["reprice"].items():
        p = P.get(sku) or {}
        if sku == au["sku"] or p.get("sale_price") is None:
            continue
        pct = label_pct(p.get("promo_label")) or (exp["bf"].get(sku) or {}).get("pct")
        if pct and eq(p["sale_price"], sale_of(r["old_retail"], pct)) and not eq(p.get("retail"), r["old_retail"]):
            stale.append(f"{sku} {r['name']}: sale {p['sale_price']} is -{pct}% of the old retail {r['old_retail']} "
                         f"(retail now {p.get('retail')}) - discount not kept")
    checks["promo_sale_prices_stale"] = stale
    # 3. discontinued + held + nothing else repriced
    dp, d0 = P.get(exp["discontinued"]) or {}, exp["seed"][exp["discontinued"]]
    disc_ok = dp.get("status") == "Discontinued" and eq(dp.get("cost"), d0["cost"]) and eq(dp.get("retail"), d0["retail"])
    checks["discontinued_item"] = disc_ok or f"status {dp.get('status')} cost {dp.get('cost')} retail {dp.get('retail')}"
    collateral = [f"{s} {p['name']}: cost {p['cost']} retail {p['retail']}" for s, p in P.items()
                  if s not in exp["reprice"] and s in exp["seed"]
                  and not (eq(p["cost"], exp["seed"][s]["cost"]) and eq(p["retail"], exp["seed"][s]["retail"]))]
    collateral += [f"{s} status {P[s]['status']}" for s in P if s in exp["seed"] and s != exp["discontinued"]
                   and P[s]["status"] != exp["seed"][s]["status"]]
    checks["other_products_changed"] = collateral
    # 4. CSV
    rows = read_csv(env, exp["a_csv"], dest + "_a.csv")
    csv_pts, extra = 0.0, []
    if rows is None:
        checks["csv"] = "missing"
    else:
        hi, cols = header(rows, {"sku": lambda f: "sku" in f, "oc": lambda f: "old" in f and "cost" in f,
                                 "nc": lambda f: "new" in f and "cost" in f, "or": lambda f: "old" in f and ("retail" in f or "price" in f) and "cost" not in f,
                                 "nr": lambda f: "new" in f and ("retail" in f or "price" in f) and "cost" not in f})
        if hi is None:
            checks["csv"] = f"header not recognised: {rows[0][:6] if rows else []}"
        else:
            got = {}
            for r in rows[hi + 1:]:
                cell = lambda k: r[cols[k]] if cols[k] < len(r) else None  # noqa: E731
                m = re.search(r"[A-Z]{2}-[A-Z]{2}-\d{3}", str(cell("sku") or "").upper())
                if m:
                    got[m.group(0)] = [money(cell(k)) for k in ("oc", "nc", "or", "nr")]
            bad = []
            for sku, r in exp["reprice"].items():
                v = got.get(sku)
                ok = v is not None and all(eq(a, b) for a, b in zip(v, [r["old_cost"], r["new_cost"], r["old_retail"], r["new_retail"]]))
                csv_pts += ok
                if not ok:
                    bad.append(f"{sku}: {v}")
            extra = [s for s in got if s not in exp["reprice"]]
            checks["csv"] = f"{csv_pts:g}/{n} rows right"
            checks["csv_problems"] = bad
            checks["csv_extra_rows"] = extra
    score = (0.45 * frac + 0.06 * bool(autumn_ok) + 0.09 * frac * (not stale) + 0.05 * disc_ok
             + 0.05 * frac * (not collateral) + 0.25 * csv_pts / n + 0.05 * (rows is not None and csv_pts > 0 and not extra))
    caps = [(pts == 0, 0.3, "no product repriced correctly"),
            (bool(wrong) or bool(stale) or not autumn_ok, 0.75, "a product's final price is wrong (shop shows wrong prices)"),
            (rows is None, 0.7, "summary CSV missing")]
    return result(score, checks, caps)


# ---------------------------------------------------------------- B: Black Friday sale
def evaluate_sale(env, dest: str) -> dict:
    exp = pc.expected("a5")
    q = read_db(env)
    if not q:
        return pc.result(0.0, {"app_db": "unreadable"})
    P = {p["sku"]: p for p in q["products"]}
    ch = q["changes"]
    checks = {}
    pts, wrong = 0.0, []
    for sku, b in exp["bf"].items():
        p = P.get(sku) or {}
        want = sale_of(p.get("retail") or 0, b["pct"])
        s_ok = eq(p.get("sale_price"), want)
        d_ok = p.get("sale_start") == exp["bf_start"] and p.get("sale_end") == exp["bf_end"]
        lab = str(p.get("promo_label") or "")
        l_ok = bool(re.search(r"black\s*friday", lab, re.I)) and label_pct(lab) == b["pct"]
        pts += 0.6 * s_ok + 0.2 * d_ok + 0.2 * l_ok
        if not (s_ok and d_ok and l_ok):
            why = f"{sku} {b['name']}: sale {p.get('sale_price')} (want {want} = -{b['pct']}% of retail {p.get('retail')}) " \
                  f"{p.get('sale_start')}..{p.get('sale_end')} '{lab}'"
            if p.get("sale_price") is not None and not s_ok and eq(p["sale_price"], sale_of(b["seed_retail"], b["pct"])) \
                    and not eq(p.get("retail"), b["seed_retail"]):
                why += " - STALE: computed from the pre-increase retail"
            elif p.get("sale_price") is None and any(c["sku"] == sku and c["field"] == "sale_price" and c["new"] for c in ch):
                why += " - LOST UPDATE: a sale price was saved, a later save cleared it"
            wrong.append(why)
    nb = len(exp["bf"])
    frac = pts / nb
    checks["sale_products"] = f"{pts:g}/{nb}"
    checks["sale_problems"] = wrong
    rp = P.get(exp["removed"]) or {}
    removed_ok = not re.search(r"black\s*friday", str(rp.get("promo_label") or ""), re.I) and rp.get("sale_start") != exp["bf_start"]
    checks["crossed_out_item_not_on_sale"] = removed_ok
    others = [f"{s} {p['name']}" for s, p in P.items() if s not in exp["bf"]
              and (re.search(r"black\s*friday", str(p.get("promo_label") or ""), re.I) or p.get("sale_start") == exp["bf_start"])]
    checks["other_products_given_bf_promo"] = others
    # CSV for the printer: every row from one consistent price state (all before or all after the cost update)
    rows = read_csv(env, exp["b_csv"], dest + "_b.csv")
    csv_frac, extra = 0.0, []
    if rows is None:
        checks["csv"] = "missing"
    else:
        hi, cols = header(rows, {"was": lambda f: f.startswith("was") or "regular" in f or "rrp" in f,
                                 "now": lambda f: f.startswith("now") or f.startswith("sale")})
        if hi is None:
            checks["csv"] = f"header not recognised: {rows[0][:6] if rows else []}"
        else:
            allp = {s: flat(p["name"]) for s, p in P.items()}
            got = {}
            for r in rows[hi + 1:]:
                line = " ".join(r)
                m = re.search(r"[A-Z]{2}-[A-Z]{2}-\d{3}", line.upper())
                sku = m.group(0) if m else None
                if not sku:
                    fl = flat(line)
                    cand = [s for s, nm in sorted(allp.items(), key=lambda kv: -len(kv[1])) if nm and nm in fl]
                    sku = cand[0] if cand else None
                if sku:
                    cell = lambda k: r[cols[k]] if cols[k] < len(r) else None  # noqa: E731
                    got[sku] = (money(cell("was")), money(cell("now")))
            snap = {"before": 0, "final": 0}
            for sku, b in exp["bf"].items():
                v = got.get(sku)
                if not v:
                    continue
                fr = (P.get(sku) or {}).get("retail")
                if eq(v[0], b["seed_retail"]) and eq(v[1], sale_of(b["seed_retail"], b["pct"])):
                    snap["before"] += 1
                if eq(v[0], fr) and eq(v[1], sale_of(fr, b["pct"])):
                    snap["final"] += 1
            best = max(snap, key=snap.get)
            csv_frac = snap[best] / nb
            extra = [s for s in got if s not in exp["bf"]]
            checks["csv"] = f"{snap[best]}/{nb} rows consistent with the {best} prices ({snap})"
            checks["csv_missing"] = [s for s in exp["bf"] if s not in got]
            checks["csv_extra_rows"] = extra
    score = (0.60 * frac + 0.05 * frac * removed_ok + 0.05 * frac * (not others) + 0.25 * csv_frac
             + 0.05 * (rows is not None and csv_frac > 0 and not extra))
    caps = [(pts == 0, 0.3, "no sale set"),
            (bool(wrong), 0.75, "a sale price/date/label is wrong in the shop"),
            (rows is None, 0.7, "price list CSV missing")]
    return result(score, checks, caps)
