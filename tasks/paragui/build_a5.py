"""A5 - Fenwick & Bloom Home & Garden: supplier price increase vs Black Friday sale in one shop back office.

build(out_dir) writes:
  app_a5.py                               ShopAdmin web app (copied)
  shopadmin_seed.db                       seeded sqlite db (64 products, suppliers, categories, policy, history)
  Greenleaf_price_change_Nov2026.pdf      supplier letter, 2-page image-only scan (task A)
  BF_flyer_proof_marked.pdf               designer's flyer proof with handwritten corrections, image-only scan (task B)
  expected.json                           ground truth (host only)
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_x as X  # noqa: E402

BUSINESS_DATE = "2026-11-16"
BF_START, BF_END = "2026-11-27", "2026-11-30"
MARKUP = {"Hand tools": "1.85", "Watering": "2.00", "Pots & planters": "2.20", "Outdoor lighting": "2.10",
          "Bird care": "2.30", "Garden furniture": "1.70", "Seeds & bulbs": "2.40"}
CAT_CODE = {"Hand tools": "HT", "Watering": "WA", "Pots & planters": "PP", "Outdoor lighting": "OL", "Bird care": "BC",
            "Garden furniture": "GF", "Seeds & bulbs": "SB"}
SUPPLIERS = [("Greenleaf Tools Ltd", "GL-", "Martin Ashby", "trade@greenleaftools.co.uk", "0121 496 0733"),
             ("Terrace Pots Co", "TP-", "Rosa Delgado", "orders@terracepots.co.uk", "01632 960 218"),
             ("Lumen Garden Lighting", "LUX-", "Ben Ferris", "sales@lumengarden.co.uk", "0161 496 0512"),
             ("Hedgerow Seeds", "HS-", "Clare Moffat", "wholesale@hedgerowseeds.co.uk", "01603 555 019"),
             ("Oakline Outdoor", "OK-", "Dev Shah", "trade@oaklineoutdoor.com", "0117 496 0881"),
             ("Wrenfield Bird Care", "WB-", "Ailsa Grant", "accounts@wrenfield.co.uk", "01224 555 140")]

# Greenleaf range: code, name, category, cost, new cost (None = not in letter), letter note
GREENLEAF = [
    ("GL-1102", "Bypass secateurs 20mm", "Hand tools", "8.40", "9.10", ""),
    ("GL-1104", "Anvil secateurs 25mm", "Hand tools", "9.20", None, ""),
    ("GL-1210", "Stainless border spade", "Hand tools", "14.60", "15.80", ""),
    ("GL-1212", "Stainless border fork", "Hand tools", "14.20", "15.30", ""),
    ("GL-1330", "Hand trowel, ash handle", "Hand tools", "4.10", "4.45", ""),
    ("GL-1332", "Hand fork, ash handle", "Hand tools", "4.10", None, ""),
    ("GL-1340", "Dibber, ash", "Hand tools", "2.30", None, ""),
    ("GL-1450", "Telescopic hedge shears", "Hand tools", "17.80", "19.20", ""),
    ("GL-1520", "Long-reach pruner", "Hand tools", "21.50", "23.10", ""),
    ("GL-1600", "Kneeler pad", "Hand tools", "3.20", "3.20", "held"),
    ("GL-2290", "Bamboo leaf rake", "Hand tools", "5.90", "5.90", "disc"),
    ("GL-4417", "Copper watering can 6L", "Watering", "18.90", "20.40", "typo"),
    ("GL-4419", "Copper watering can 9L", "Watering", "23.50", "25.30", ""),
    ("GL-4502", "Brass hose nozzle, 7 patterns", "Watering", "5.60", "6.10", ""),
    ("GL-4510", "Expanding hose 30m", "Watering", "11.30", "12.20", ""),
    ("GL-4600", "Hose reel cart", "Watering", "16.80", None, ""),
    ("GL-4610", "Galvanised watering can 10L", "Watering", "9.40", None, ""),
]
LETTER_ORDER = ["GL-1102", "GL-1210", "GL-1212", "GL-1330", "GL-1450", "GL-1520", "GL-1600", "GL-2290", "GL-4417",
                "GL-4419", "GL-4502", "GL-4510"]
LETTER_DESC = {"GL-4417": "Copper watering can 6 litre", "GL-4419": "Copper watering can 9 litre",
               "GL-1102": "Bypass secateurs 20mm cut", "GL-1330": "Hand trowel - ash handle", "GL-2290": "Leaf rake, bamboo, 22 tine"}
LETTER_CODE = {"GL-4417": "GL-4471"}  # typo in the letter: description + old price identify the product

OTHER = {  # supplier: [(name, category, cost)]
    "Terrace Pots Co": [("Glazed pot 30cm, Midnight blue", "Pots & planters", "6.90"), ("Glazed pot 30cm, Ocean green", "Pots & planters", "6.90"),
                        ("Glazed pot 40cm, Midnight blue", "Pots & planters", "11.20"), ("Terracotta long tom 25cm", "Pots & planters", "4.30"),
                        ("Terracotta bowl planter 50cm", "Pots & planters", "9.80"), ("Zinc trough planter 80cm", "Pots & planters", "15.40"),
                        ("Self-watering herb planter", "Pots & planters", "5.70"), ("Fibreclay cube planter 35cm", "Pots & planters", "13.10"),
                        ("Hanging basket 35cm, coco liner", "Pots & planters", "4.90")],
    "Lumen Garden Lighting": [("Solar lantern set of 4", "Outdoor lighting", "7.80"), ("Solar lantern set of 2", "Outdoor lighting", "4.60"),
                              ("Festoon lights 10m, warm white", "Outdoor lighting", "12.30"), ("Solar spike lights, pack of 6", "Outdoor lighting", "9.10"),
                              ("Rattan table lamp, rechargeable", "Outdoor lighting", "14.70"), ("Copper wire fairy lights 5m", "Outdoor lighting", "3.80")],
    "Hedgerow Seeds": [("Wildflower meadow mix 100g", "Seeds & bulbs", "2.10"), ("Sweet pea 'Matucana' seeds", "Seeds & bulbs", "0.95"),
                       ("Tulip 'Ballerina' bulbs x10", "Seeds & bulbs", "2.40"), ("Allium 'Purple Sensation' x8", "Seeds & bulbs", "2.80"),
                       ("Narcissus 'Tete-a-tete' x20", "Seeds & bulbs", "2.20"), ("Salad leaves mix seeds", "Seeds & bulbs", "0.80"),
                       ("Snowdrop bulbs in the green x25", "Seeds & bulbs", "4.60")],
    "Oakline Outdoor": [("Rattan bistro set, 2 chairs", "Garden furniture", "64.00"), ("Acacia folding chair", "Garden furniture", "21.50"),
                        ("Acacia folding table 70cm", "Garden furniture", "38.00"), ("Steel fire pit 60cm", "Garden furniture", "27.40"),
                        ("Outdoor cushion, sage", "Garden furniture", "6.80"), ("Hammock with frame", "Garden furniture", "45.20"),
                        ("Teak bench 120cm", "Garden furniture", "92.00")],
    "Wrenfield Bird Care": [("Bird feeder station", "Bird care", "12.40"), ("Hanging seed feeder, 3 port", "Bird care", "4.20"),
                            ("Robin nest box", "Bird care", "5.10"), ("Ceramic bird bath", "Bird care", "11.90"),
                            ("Suet balls x50", "Bird care", "3.60"), ("Mealworm feeder", "Bird care", "3.30"),
                            ("Squirrel-proof peanut feeder", "Bird care", "7.70")],
}
# Black Friday flyer: (name, discount %) after the handwritten corrections; and how the proof shows them
BF_FINAL = [("Bypass secateurs 20mm", 20), ("Stainless border spade", 20), ("Stainless border fork", 20),
            ("Hand trowel, ash handle", 20), ("Telescopic hedge shears", 25), ("Brass hose nozzle, 7 patterns", 20),
            ("Expanding hose 30m", 25), ("Hose reel cart", 20), ("Solar lantern set of 4", 25),
            ("Glazed pot 30cm, Midnight blue", 20), ("Bird feeder station", 20), ("Rattan bistro set, 2 chairs", 25),
            ("Copper watering can 6L", 25)]
PROOF_TILES = [("Bypass secateurs 20mm", "20"), ("Stainless border spade", "20"), ("Stainless border fork", "20"),
               ("Hand trowel, ash handle", "20"), ("Telescopic hedge shears", "25"), ("Brass hose nozzle, 7 patterns", "20"),
               ("Expanding hose 30m", "20>25"), ("Galvanised watering can 10L", "X"), ("Hose reel cart", "20"),
               ("Solar lantern set of 4", "25"), ("Glazed pot 30cm, Midnight blue", "20"), ("Bird feeder station", "20"),
               ("Rattan bistro set, 2 chairs", "25")]
REMOVED = "Galvanised watering can 10L"
LOOKALIKES = ["Anvil secateurs 25mm", "Copper watering can 9L", "Glazed pot 30cm, Ocean green", "Solar lantern set of 2",
              "Hand fork, ash handle", "Glazed pot 40cm, Midnight blue"]
AUTUMN = {"Long-reach pruner": 15, "Terracotta bowl planter 50cm": 15}


def retail_of(cost: str, cat: str) -> Decimal:
    x = Decimal(cost) * Decimal(MARKUP[cat])
    return x.to_integral_value(rounding=ROUND_FLOOR) + Decimal("0.99")


def sale_of(retail, pct: int) -> Decimal:
    return (Decimal(str(retail)) * Decimal(100 - pct) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


POLICY = """<h1>Pricing policy</h1><p class="muted">Owner: Jess Morley · last reviewed 2 November 2026</p>
<h2>Regular retail prices</h2><ul>
<li>All shop prices include VAT. Cost prices are the supplier's trade price ex VAT.</li>
<li><b>Regular retail price = cost price &times; the category markup below, then set to the 99p price in that pound</b>: keep the
whole pounds and add &pound;0.99 (e.g. &pound;15.54 &rarr; &pound;15.99, &pound;16.835 &rarr; &pound;16.99, &pound;24.00 &rarr; &pound;24.99).</li>
<li>When a supplier changes a cost price, update the cost price and recalculate the regular retail price straight away.</li></ul>
{{MARKUPS}}
<h2>Promotions</h2><ul>
<li>A promotion is entered on the product page: sale price, sale start date, sale end date and a promotion label in the
form <b>"&lt;Promotion name&gt; -NN%"</b>, e.g. "Autumn clearance -15%".</li>
<li><b>Sale price = regular retail price &times; (100 &minus; discount)%, rounded to the nearest penny</b> (half a penny rounds up).
Always work from the product's current regular retail price.</li>
<li>If the regular retail price of a product that has a promotion (running or scheduled) changes, keep the promotion's
discount % and dates and recalculate the sale price from the new regular price.</li>
<li>When a promotion is over, the sale fields are cleared by the shop team on the next working day.</li></ul>
<h2>Promotions calendar 2026</h2><table class="t" style="max-width:760px"><tr><th>Promotion</th><th>Sale starts</th><th>Sale ends</th><th>Label</th></tr>
<tr><td>Autumn clearance</td><td>2026-11-02</td><td>2026-11-22</td><td>Autumn clearance -NN%</td></tr>
<tr><td>Black Friday weekend</td><td>2026-11-27 (Fri)</td><td>2026-11-30 (Mon)</td><td>Black Friday -NN%</td></tr>
<tr><td>Christmas gift guide (no discounts)</td><td>2026-12-01</td><td>2026-12-24</td><td>-</td></tr></table>
<h2>Supplier changes</h2><ul>
<li>Suppliers quote their own product codes; each product page shows our supplier code in the field "Supplier code".</li>
<li>Items a supplier discontinues stay on sale until sold out: set their status to <b>Discontinued</b> and leave their prices unchanged.</li>
<li>A price that the supplier holds needs no change.</li></ul>"""


def products(rng):
    out, n = [], {c: 100 for c in CAT_CODE}

    def add(name, cat, sup, code, cost, desc):
        n[cat] += 1 + rng.randrange(3)
        sku = f"FB-{CAT_CODE[cat]}-{n[cat]}"
        out.append({"sku": sku, "name": name, "category": cat, "supplier": sup, "supplier_code": code, "cost": float(cost),
                    "retail": float(retail_of(cost, cat)), "sale_price": None, "sale_start": None, "sale_end": None,
                    "promo_label": None, "stock": rng.randrange(4, 60), "status": "Active",
                    "weight_kg": round(rng.uniform(0.1, 6.0), 2), "description": desc, "updated_at": "2026-10-28 09:12:00"})
    for code, name, cat, cost, _, _ in GREENLEAF:
        add(name, cat, "Greenleaf Tools Ltd", code, cost, f"{name} from Greenleaf's professional range. 5-year guarantee.")
    pre = {s[0]: s[1] for s in SUPPLIERS}
    for sup, items in OTHER.items():
        for i, (name, cat, cost) in enumerate(items):
            add(name, cat, sup, f"{pre[sup]}{rng.randrange(1000, 9999)}", cost, f"{name}. Ships in 2-3 working days.")
    out.sort(key=lambda p: p["sku"])
    by = {p["name"]: p for p in out}
    for name, pct in AUTUMN.items():
        p = by[name]
        p.update(sale_price=float(sale_of(p["retail"], pct)), sale_start="2026-11-02", sale_end="2026-11-22",
                 promo_label=f"Autumn clearance -{pct}%")
    by["Hammock with frame"]["status"] = "Hidden"
    by["Hand fork, ash handle"]["stock"] = 2
    assert len({p["sku"] for p in out}) == len(out)
    return out


def letter_pdf(path, by_code):
    p1 = X.Page()
    p1.text(90, 80, "GREENLEAF TOOLS LTD", size=46, bold=True, fill=(30, 90, 40))
    p1.lines(90, 140, ["Unit 7, Hockley Works, Birmingham B18 5AB", "trade@greenleaftools.co.uk  ·  0121 496 0733",
                       "VAT reg. GB 284 1167 30"], size=20, fill=(70, 70, 70))
    p1.hline(90, 1150, 228)
    y = p1.lines(90, 260, ["Fenwick & Bloom Home & Garden", "Attn: Jess Morley", "14 Elm Hill, Norwich NR3 1HN"], size=22)
    p1.text(860, 260, "12 November 2026", size=22)
    y = p1.text(90, y + 30, "Trade price changes - effective for orders from 16 November 2026", size=26, bold=True)
    y = p1.lines(90, y + 10, ["Dear Jess,", "",
                              "Following increases in steel and copper costs we have to revise our trade prices. The new",
                              "prices below apply to all orders placed from Monday 16 November 2026. Items not listed are",
                              "unchanged. Prices are per unit, ex VAT, delivered."], size=21)
    rows = []
    for code in LETTER_ORDER:
        g = by_code[code]
        note = {"held": "price held", "disc": "DISCONTINUED"}.get(g[5], "")
        new = "-" if g[5] == "disc" else f"{float(g[4]):.2f}"
        rows.append((LETTER_CODE.get(code, code), LETTER_DESC.get(code, g[1]), f"{float(g[3]):.2f}", new, note))
    y = p1.table(90, y + 24, [("Code", 140, "l"), ("Description", 390, "l"), ("Current £", 140, "r"), ("New £", 120, "r"),
                              ("Note", 210, "l")], rows, size=19, row_h=40)
    p1.lines(90, y + 30, ["We appreciate your understanding and look forward to a busy winter season together.", "",
                          "Kind regards,"], size=21)
    p1.handwriting(100, y + 150, "Martin Ashby", size=40, seed=5)
    p1.text(100, y + 205, "Martin Ashby, Trade Sales Manager", size=19)
    p1.text(90, 1690, "Greenleaf Tools Ltd · Registered in England No. 04518832 · page 1 of 2", size=16, fill=(110, 110, 110))
    p2 = X.Page()
    p2.text(90, 90, "Trade terms (extract)", size=28, bold=True)
    p2.lines(90, 150, ["1. Prices are ex VAT and include delivery to UK mainland addresses for orders over £150 net.",
                       "2. Payment terms 30 days end of month. Late payments may incur interest under the Late Payment Act.",
                       "3. Discontinued lines are supplied while stocks last; no back orders are accepted.",
                       "4. Price changes are notified at least 3 working days before they take effect.",
                       "5. DISCONTINUED lines: final stock only, no further orders after 30 November 2026.",
                       "6. Retail prices are at the reseller's discretion; RRPs in our catalogue are a guide only.",
                       "7. Damaged goods must be reported within 48 hours of delivery with photographs."], size=20, gap=1.7)
    p2.text(90, 1690, "Greenleaf Tools Ltd · page 2 of 2", size=16, fill=(110, 110, 110))
    X.scanned_pdf(path, [p1, p2], seed=55)


def flyer_pdf(path):
    pg = X.Page()
    pg.d.rectangle((0, 0, pg.w, 230), fill=(20, 20, 20))
    pg.text(70, 50, "FENWICK & BLOOM", size=34, bold=True, fill=(240, 240, 240))
    pg.text(70, 105, "BLACK FRIDAY WEEKEND", size=58, bold=True, fill=(250, 210, 80))
    pg.text(72, 180, "Fri 27 - Mon 30 November  ·  online only  ·  while stocks last", size=22, fill=(230, 230, 230))
    pg.stamp(860, 250, "PROOF v2", size=34, angle=8)
    x0, y0, cw, ch = 70, 310, 370, 230
    for i, (name, badge) in enumerate(PROOF_TILES):
        cx, cy = x0 + (i % 3) * (cw + 20), y0 + (i // 3) * (ch + 20)
        pg.rect((cx, cy, cx + cw, cy + ch), outline=(120, 120, 120), width=2)
        pg.d.rectangle((cx + 20, cy + 20, cx + 150, cy + 150), fill=(205, 222, 200))
        pg.d.ellipse((cx + 230, cy + 25, cx + 345, cy + 140), fill=(200, 30, 30))
        pct = badge.split(">")[0] if badge != "X" else "20"
        pg.text(cx + 287, cy + 82, f"-{pct}%", size=34, bold=True, fill=(255, 255, 255), anchor="mm")
        words, line, yy = name.split(), "", cy + 168
        for w in words:
            if len(line) + len(w) > 24:
                yy = pg.text(cx + 20, yy, line, size=22, bold=True)
                line = w
            else:
                line = (line + " " + w).strip()
        pg.text(cx + 20, yy, line, size=22, bold=True)
        if badge == "X":
            pg.d.line((cx + 10, cy + 10, cx + cw - 10, cy + ch - 10), fill=(200, 20, 20), width=6)
            pg.d.line((cx + cw - 10, cy + 10, cx + 10, cy + ch - 10), fill=(200, 20, 20), width=6)
            pg.handwriting(cx + 25, cy + 95, "REMOVE - no stock", size=30, fill=(200, 20, 20), seed=3)
        if ">" in badge:
            pg.d.line((cx + 240, cy + 70, cx + 340, cy + 95), fill=(20, 40, 120), width=5)
            pg.handwriting(cx + 160, cy + 30, "25%!", size=40, seed=4)
    yb = y0 + 5 * (ch + 20) + 10
    pg.handwriting(80, yb + 5, "+ add:  Copper watering can 6L   -25%", size=36, seed=7)
    pg.handwriting(80, yb + 60, "prices from the shop, not from this proof - J.M. 13/11", size=28, seed=8)
    X.scanned_pdf(path, [pg], seed=77)


def build(d):
    os.makedirs(d, exist_ok=True)
    X.copy_app("app_a5.py", d)
    rng = random.Random(5135)
    prods = products(rng)
    by_name = {p["name"]: p for p in prods}
    by_code = {g[0]: g for g in GREENLEAF}
    sku_of_code = {p["supplier_code"]: p["sku"] for p in prods}
    letter_pdf(f"{d}/Greenleaf_price_change_Nov2026.pdf", by_code)
    flyer_pdf(f"{d}/BF_flyer_proof_marked.pdf")
    # ---- ground truth
    reprice = {}
    for code, name, cat, cost, new, note in GREENLEAF:
        if new is None or note in ("held", "disc"):
            continue
        p = by_name[name]
        reprice[p["sku"]] = {"name": name, "code": code, "old_cost": float(cost), "new_cost": float(new),
                             "old_retail": p["retail"], "new_retail": float(retail_of(new, cat))}
    bf = {}
    for name, pct in BF_FINAL:
        p = by_name[name]
        bf[p["sku"]] = {"name": name, "pct": pct, "seed_retail": p["retail"]}
    overlap = sorted(set(reprice) & set(bf))
    assert len(reprice) == 10 and len(bf) == 13 and len(overlap) == 8, (len(reprice), len(bf), len(overlap))
    pr = by_name["Long-reach pruner"]
    autumn_sku = pr["sku"]
    exp = {
        "business_date": BUSINESS_DATE, "bf_start": BF_START, "bf_end": BF_END, "markup": MARKUP,
        "seed": {p["sku"]: {k: p[k] for k in ("name", "category", "supplier", "supplier_code", "cost", "retail", "sale_price",
                                                "sale_start", "sale_end", "promo_label", "stock", "status")} for p in prods},
        "reprice": reprice,
        "autumn": {"sku": autumn_sku, "pct": 15, "label": pr["promo_label"], "start": pr["sale_start"], "end": pr["sale_end"],
                   "new_sale": float(sale_of(reprice[autumn_sku]["new_retail"], 15))},
        "discontinued": sku_of_code["GL-2290"], "held": sku_of_code["GL-1600"], "typo": sku_of_code["GL-4417"],
        "bf": bf, "overlap": overlap, "removed": by_name[REMOVED]["sku"],
        "lookalikes": [by_name[n]["sku"] for n in LOOKALIKES],
        "a_csv": "/home/user/Documents/Pricing/price_update_greenleaf.csv",
        "b_csv": "/home/user/Documents/Marketing/black_friday_prices.csv",
    }
    rows = {
        "settings": [{"key": "business_date", "value": BUSINESS_DATE}, {"key": "policy_html", "value": POLICY},
                     {"key": "company", "value": "Fenwick & Bloom Home & Garden"}],
        "users": [{"id": 1, "username": "jess", "name": "Jess Morley", "role": "owner", "salt": "fb3K",
                   "pw": X.pw_hash("Bloom-Admin-26", "fb3K")},
                  {"id": 2, "username": "theo", "name": "Theo Grant", "role": "warehouse", "salt": "tg8Q",
                   "pw": X.pw_hash("Warehouse#Bloom", "tg8Q")}],
        "categories": [{"name": c, "markup": float(m)} for c, m in MARKUP.items()],
        "suppliers": [{"name": s[0], "prefix": s[1], "contact": s[2], "email": s[3], "phone": s[4]} for s in SUPPLIERS],
        "products": prods,
        "audit": [{"ts": "2026-10-28 09:12:00", "user": "jess", "action": "catalogue import", "detail": f"{len(prods)} products updated from supplier price files"},
                  {"ts": "2026-10-30 16:40:12", "user": "jess", "action": "product saved",
                   "detail": f"{autumn_sku} Long-reach pruner: sale_price, sale_start, sale_end, promo_label"},
                  {"ts": "2026-11-13 11:05:31", "user": "theo", "action": "product saved",
                   "detail": f"{by_name['Hand fork, ash handle']['sku']} Hand fork, ash handle: stock"}],
        "changes": [{"ts": "2026-10-30 16:40:12", "user": "jess", "sku": autumn_sku, "field": "sale_price", "old": "",
                     "new": str(pr["sale_price"])},
                    {"ts": "2026-10-30 16:40:12", "user": "jess", "sku": autumn_sku, "field": "promo_label", "old": "",
                     "new": pr["promo_label"]}],
    }
    X.seed_db(f"{d}/shopadmin_seed.db", SCHEMA, rows)
    json.dump(exp, open(f"{d}/expected.json", "w"), indent=1)


SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT, salt TEXT, pw TEXT);
CREATE TABLE categories(name TEXT PRIMARY KEY, markup REAL);
CREATE TABLE suppliers(name TEXT PRIMARY KEY, prefix TEXT, contact TEXT, email TEXT, phone TEXT);
CREATE TABLE products(id INTEGER PRIMARY KEY, sku TEXT UNIQUE, name TEXT, category TEXT, supplier TEXT, supplier_code TEXT,
    cost REAL, retail REAL, sale_price REAL, sale_start TEXT, sale_end TEXT, promo_label TEXT, stock INTEGER, status TEXT,
    weight_kg REAL, description TEXT, updated_at TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
CREATE TABLE changes(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, sku TEXT, field TEXT, old TEXT, new TEXT);
"""

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp())
