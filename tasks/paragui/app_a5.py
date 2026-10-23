#!/usr/bin/env python3
"""ShopAdmin - the back office of Fenwick & Bloom Home & Garden (paraGUI pair a5).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Product catalogue with a full edit form (every field is written back on Save, like most small shop admins), pricing
policy, suppliers, activity log with per-field price history.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import secrets
import sqlite3
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP, COOKIE = "ShopAdmin", "shopadmin_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
PAGE = 20
STATUSES = ["Active", "Hidden", "Discontinued"]
FIELDS = ["name", "category", "supplier", "supplier_code", "cost", "retail", "sale_price", "sale_start", "sale_end",
          "promo_label", "stock", "status", "weight_kg", "description"]
RUNTIME_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(sid TEXT PRIMARY KEY, user_id INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, sku TEXT, field TEXT, old TEXT, new TEXT);
"""


def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def route(method, pattern):
    def deco(f):
        ROUTES.append((method, re.compile(pattern + r"$"), f))
        return f
    return deco


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def gbp(v):
    if v is None or v == "":
        return ""
    return f"£{float(v):,.2f}"


def nice_date(s):
    try:
        return dt.date.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s or ""


def parse_money(s):
    s = re.sub(r"[£,\s]", "", s or "")
    if s == "":
        return ""
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return v if v >= 0 else None


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%a %d %b %Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def setting(con, key):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else ""


class Req:
    def __init__(self, h, method):
        self.h, self.method = h, method
        u = urllib.parse.urlsplit(h.path)
        self.path = u.path
        self.q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
        self.form = {}
        if method == "POST":
            n = int(h.headers.get("Content-Length") or 0)
            body = h.rfile.read(n) if n else b""
            self.form = {k: v[-1] for k, v in urllib.parse.parse_qs(body.decode("utf8", "replace"),
                                                                     keep_blank_values=True).items()}
        self.sid, self.user, self.flashes, self.cookie = None, None, [], None
        c = SimpleCookie(h.headers.get("Cookie", ""))
        if "shopadmin_flash" in c:
            try:
                self.flashes = json.loads(urllib.parse.unquote(c["shopadmin_flash"].value))
            except Exception:
                self.flashes = []
        if COOKIE in c:
            con = db()
            r = con.execute("SELECT s.sid, u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE sid=?",
                            (c[COOKIE].value,)).fetchone()
            con.close()
            if r:
                self.sid, self.user = r["sid"], dict(r)


def audit(con, req, action, detail):
    con.execute("INSERT INTO audit(ts, user, action, detail) VALUES (?,?,?,?)",
                (now(), req.user["username"] if req.user else "-", action, detail))


CSS = """
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#f2f4ef;color:#1f2a1f}
a{color:#2f6b3a;text-decoration:none}a:hover{text-decoration:underline}
header{background:#24452b;color:#eef5e8;display:flex;align-items:center;gap:22px;padding:0 22px;height:56px}
header .brand{font-weight:700;font-size:19px}header .brand small{font-weight:400;opacity:.75;margin-left:8px;font-size:13px}
header nav a{color:#eef5e8;margin-right:16px;font-size:14px}header nav a.on{border-bottom:2px solid #b7d98b;padding-bottom:3px}
header .who{margin-left:auto;font-size:13px}header .who a{color:#d6f0b0}
main{max-width:1240px;margin:22px auto;padding:0 22px}h1{font-size:23px;margin:4px 0 16px}h2{font-size:17px;margin:20px 0 10px}
.card{background:#fff;border:1px solid #d4dccd;border-radius:6px;padding:16px 18px;margin-bottom:16px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d4dccd}
table.t th{background:#e5ecdf;text-align:left;font-size:13px;padding:7px 8px;border-bottom:1px solid #c9d4c0}
table.t td{padding:6px 8px;border-bottom:1px solid #e8eee3;font-size:14px}table.t tr:hover td{background:#f7faf3}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.b-Active{background:#dcefdc;color:#25632a}.b-Hidden{background:#e8e8e8;color:#555}.b-Discontinued{background:#fbe0dc;color:#9b2a1c}
.promo{background:#fff0cc;color:#7a5200;border-radius:10px;padding:1px 8px;font-size:12px;font-weight:600}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#e1f3e1;border:1px solid #9ccf9c}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}
label{display:block;font-size:13px;color:#555;margin:9px 0 3px}
input[type=text],input[type=password],select,textarea{padding:6px 8px;border:1px solid #bfcab6;border-radius:4px;font-size:14px;width:100%}
button,.btn{background:#2f6b3a;color:#fff;border:0;border-radius:4px;padding:8px 16px;font-size:14px;cursor:pointer}
.filters{display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;flex-wrap:wrap}.filters label{margin:0 0 3px}
.filters input,.filters select{width:auto}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.kpi{font-size:24px;font-weight:700}.muted{color:#6b7466;font-size:13px}
.pager{margin:10px 0;font-size:14px}.pager a{margin-right:10px}
.login{max-width:380px;margin:90px auto}.two{display:grid;grid-template-columns:1.5fr 1fr;gap:18px}
.f3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 14px}.f2{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}
fieldset{border:1px solid #d4dccd;border-radius:6px;margin:12px 0;padding:6px 14px 12px}legend{font-weight:600;font-size:14px}
.policy h2{border-bottom:1px solid #d4dccd;padding-bottom:4px}.policy li{margin:4px 0}
"""


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.flashes)
    head = f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
    if not req.user:
        return head + flashes + body + "</body></html>"
    links = [("dashboard", "/", "Dashboard"), ("products", "/products", "Products"), ("suppliers", "/suppliers", "Suppliers"),
             ("policy", "/policy", "Pricing policy"), ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    return (head + f'<header><div class="brand">{APP}<small>Fenwick &amp; Bloom Home &amp; Garden</small></div><nav>{navh}</nav>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header>'
            f"<main>{flashes}{body}</main></body></html>")


def redirect(url, flash=None):
    h = {"Location": url}
    if flash:
        h["Set-Cookie"] = "shopadmin_flash=" + urllib.parse.quote(json.dumps(flash)) + "; Path=/; Max-Age=60"
    return 303, h, b""


def page(req, title, body, nav=""):
    h = {"Content-Type": "text/html; charset=utf-8"}
    if req.flashes:
        h["Set-Cookie"] = "shopadmin_flash=; Path=/; Max-Age=0"
    return 200, h, layout(req, title, body, nav).encode()


# ---------------------------------------------------------------- auth
@route("GET", "/login")
def login_form(req, err=""):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>ShopAdmin</h1><p class="muted">Fenwick &amp; Bloom Home &amp; Garden · back office</p>'
            + (f'<div class="flash err">{E(err)}</div>' if err else "")
            + '<form method=post action="/login"><label>Username</label><input type=text name=username autofocus>'
            '<label>Password</label><input type=password name=password><p><button>Sign in</button></p></form></div>')
    return page(req, "Sign in", body)


@route("POST", "/login")
def login(req):
    con = db()
    u = con.execute("SELECT * FROM users WHERE username=?", (req.form.get("username", "").strip().lower(),)).fetchone()
    if not u or hashlib.sha256((u["salt"] + req.form.get("password", "")).encode()).hexdigest() != u["pw"]:
        con.close()
        return login_form(req, "Wrong username or password.")
    sid = secrets.token_hex(16)
    con.execute("INSERT INTO sessions VALUES (?,?,?)", (sid, u["id"], now()))
    con.execute("INSERT INTO audit(ts, user, action, detail) VALUES (?,?,?,?)", (now(), u["username"], "login", ""))
    con.commit()
    con.close()
    return 303, {"Location": "/", "Set-Cookie": f"{COOKIE}={sid}; Path=/; HttpOnly; SameSite=Lax"}, b""


@route("GET", "/logout")
def logout(req):
    con = db()
    con.execute("DELETE FROM sessions WHERE sid=?", (req.sid,))
    con.commit()
    con.close()
    return 303, {"Location": "/login", "Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0"}, b""


# ---------------------------------------------------------------- pages
def on_promo(p, today):
    return p["sale_price"] is not None and (p["sale_end"] or "9999") >= today


def promo_cell(p, today):
    if p["sale_price"] is None:
        return ""
    state = "running" if (p["sale_start"] or "") <= today <= (p["sale_end"] or "9999") else (
        "scheduled" if (p["sale_start"] or "") > today else "ended")
    return f'<span class="promo">{E(p["promo_label"] or "Sale")}</span> <span class="muted">{state}</span>'


@route("GET", "/")
def dashboard(req):
    con = db()
    today = setting(con, "business_date")
    ps = con.execute("SELECT * FROM products").fetchall()
    acts = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 10").fetchall()
    con.close()
    active = sum(p["status"] == "Active" for p in ps)
    promo = sum(on_promo(p, today) for p in ps)
    low = sum(p["stock"] < 5 and p["status"] == "Active" for p in ps)
    body = (f'<h1>Dashboard</h1><p class="muted">Business date {nice_date(today)}</p><div class="grid">'
            f'<div class="card"><div class="muted">Products</div><div class="kpi">{len(ps)}</div></div>'
            f'<div class="card"><div class="muted">Active</div><div class="kpi">{active}</div></div>'
            f'<div class="card"><div class="muted">On promotion (running or scheduled)</div><div class="kpi">{promo}</div></div>'
            f'<div class="card"><div class="muted">Low stock (&lt; 5)</div><div class="kpi">{low}</div></div></div>'
            '<h2>Recent activity</h2><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
            + "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in acts)
            + "</table>")
    return page(req, "Dashboard", body, "dashboard")


@route("GET", "/products")
def products(req):
    q = req.q.get("q", "").strip()
    cat, sup, st = req.q.get("category", ""), req.q.get("supplier", ""), req.q.get("status", "")
    promo = req.q.get("promo", "")
    con = db()
    today = setting(con, "business_date")
    cats = [r["name"] for r in con.execute("SELECT name FROM categories ORDER BY name")]
    sups = [r["name"] for r in con.execute("SELECT name FROM suppliers ORDER BY name")]
    rows = []
    for p in con.execute("SELECT * FROM products ORDER BY sku"):
        if q and q.lower() not in " ".join([p["sku"], p["name"], p["supplier_code"] or ""]).lower():
            continue
        if cat and p["category"] != cat or sup and p["supplier"] != sup or st and p["status"] != st:
            continue
        if promo == "yes" and not on_promo(p, today):
            continue
        rows.append(p)
    con.close()
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = req.q.get("page", "1")
    pg = min(max(1, int(pg)), pages) if pg.isdigit() else 1
    opt = lambda vals, cur, blank: f'<option value="">{blank}</option>' + "".join(  # noqa: E731
        f'<option{" selected" if v == cur else ""}>{E(v)}</option>' for v in vals)
    body = ('<h1>Products</h1><form class="filters" method=get action="/products">'
            f'<div><label>Search SKU / name / supplier code</label><input type=text name=q value="{E(q)}" style="width:260px"></div>'
            f'<div><label>Category</label><select name=category>{opt(cats, cat, "All categories")}</select></div>'
            f'<div><label>Supplier</label><select name=supplier>{opt(sups, sup, "All suppliers")}</select></div>'
            f'<div><label>Status</label><select name=status>{opt(STATUSES, st, "Any status")}</select></div>'
            f'<div><label>Promotion</label><select name=promo><option value="">Any</option><option value="yes"{" selected" if promo else ""}>On promotion</option></select></div>'
            '<div><button>Filter</button></div><div><a class="muted" href="/products">Clear</a></div></form>'
            '<table class="t"><tr><th>SKU</th><th>Product</th><th>Category</th><th>Supplier code</th><th class=n>Cost</th>'
            '<th class=n>Retail</th><th class=n>Sale</th><th>Promotion</th><th class=n>Stock</th><th>Status</th></tr>')
    for p in rows[(pg - 1) * PAGE: pg * PAGE]:
        body += (f'<tr><td><a href="/products/{E(p["sku"])}">{E(p["sku"])}</a></td><td><a href="/products/{E(p["sku"])}">{E(p["name"])}</a></td>'
                 f'<td>{E(p["category"])}</td><td>{E(p["supplier_code"])}</td><td class=n>{gbp(p["cost"])}</td>'
                 f'<td class=n>{gbp(p["retail"])}</td><td class=n>{gbp(p["sale_price"])}</td><td>{promo_cell(p, today)}</td>'
                 f'<td class=n>{p["stock"]}</td><td><span class="badge b-{E(p["status"])}">{E(p["status"])}</span></td></tr>')
    if not rows:
        body += '<tr><td colspan=10 class=muted>No products match.</td></tr>'
    keep = urllib.parse.urlencode({k: v for k, v in (("q", q), ("category", cat), ("supplier", sup), ("status", st), ("promo", promo)) if v})
    body += f'</table><div class="pager">{len(rows)} products · page {pg} of {pages} &nbsp; '
    if pg > 1:
        body += f'<a href="/products?{keep}&amp;page={pg - 1}">&laquo; Previous</a>'
    if pg < pages:
        body += f'<a href="/products?{keep}&amp;page={pg + 1}">Next &raquo;</a>'
    return page(req, "Products", body + "</div>", "products")


def product_form(req, p, err="", vals=None):
    con = db()
    cats = [r["name"] for r in con.execute("SELECT name FROM categories ORDER BY name")]
    sups = [r["name"] for r in con.execute("SELECT name FROM suppliers ORDER BY name")]
    hist = con.execute("SELECT * FROM changes WHERE sku=? ORDER BY id DESC LIMIT 12", (p["sku"],)).fetchall()
    today = setting(con, "business_date")
    con.close()
    v = dict(p)
    if vals:
        v.update(vals)
    money = lambda k: "" if v.get(k) in (None, "") else (f"{float(v[k]):.2f}" if isinstance(v[k], (int, float)) else v[k])  # noqa: E731
    sel = lambda name, opts, cur: f'<select name={name}>' + "".join(  # noqa: E731
        f'<option{" selected" if o == cur else ""}>{E(o)}</option>' for o in opts) + "</select>"
    inp = lambda name, val, ph="": f'<input type=text name={name} value="{E(val)}" placeholder="{E(ph)}">'  # noqa: E731
    margin = ""
    try:
        margin = f'{(float(v["retail"]) - float(v["cost"])) / float(v["retail"]) * 100:.1f}%'
    except Exception:
        pass
    body = (f'<p><a href="/products">&laquo; Products</a></p><h1>{E(p["name"])} <span class="muted">{E(p["sku"])}</span></h1>'
            + (f'<div class="flash err">{E(err)} Nothing was saved.</div>' if err else "")
            + f'<div class="two"><div><form method=post action="/products/{E(p["sku"])}" class="card">'
            '<fieldset><legend>Product</legend>'
            f'<label>Product name</label>{inp("name", v["name"])}'
            f'<div class="f3"><div><label>Category</label>{sel("category", cats, v["category"])}</div>'
            f'<div><label>Supplier</label>{sel("supplier", sups, v["supplier"])}</div>'
            f'<div><label>Supplier code</label>{inp("supplier_code", v["supplier_code"])}</div></div>'
            f'<div class="f3"><div><label>Stock</label>{inp("stock", v["stock"])}</div>'
            f'<div><label>Weight (kg)</label>{inp("weight_kg", v["weight_kg"])}</div>'
            f'<div><label>Status</label>{sel("status", STATUSES, v["status"])}</div></div>'
            f'<label>Description</label><textarea name=description rows=3>{E(v["description"])}</textarea></fieldset>'
            '<fieldset><legend>Pricing</legend>'
            f'<div class="f2"><div><label>Cost price (£, ex VAT)</label>{inp("cost", money("cost"))}</div>'
            f'<div><label>Regular retail price (£, inc VAT)</label>{inp("retail", money("retail"))}</div></div>'
            f'<p class="muted">Current margin on regular price: {margin}</p></fieldset>'
            '<fieldset><legend>Promotion</legend>'
            f'<div class="f2"><div><label>Sale price (£)</label>{inp("sale_price", money("sale_price"), "empty = no promotion")}</div>'
            f'<div><label>Promotion label</label>{inp("promo_label", v["promo_label"] or "", "e.g. Spring sale -10%")}</div></div>'
            f'<div class="f2"><div><label>Sale starts</label>{inp("sale_start", v["sale_start"] or "", "YYYY-MM-DD")}</div>'
            f'<div><label>Sale ends</label>{inp("sale_end", v["sale_end"] or "", "YYYY-MM-DD")}</div></div></fieldset>'
            '<p><button>Save product</button> <a href="/products" class="muted" style="margin-left:12px">Cancel</a></p></form></div>'
            f'<div><div class="card"><h2 style="margin-top:0">Summary</h2>Retail {gbp(p["retail"])}'
            + (f'<br>On promotion: {promo_cell(p, today)} {gbp(p["sale_price"])} from {nice_date(p["sale_start"])} to {nice_date(p["sale_end"])}'
               if p["sale_price"] is not None else "<br>No promotion")
            + '</div><div class="card"><h2 style="margin-top:0">Price history</h2><table class="t"><tr><th>When</th><th>Field</th><th>Old</th><th>New</th></tr>'
            + "".join(f'<tr><td class=muted>{E(h["ts"])}</td><td>{E(h["field"])}</td><td>{E(h["old"])}</td><td>{E(h["new"])}</td></tr>' for h in hist)
            + ("" if hist else '<tr><td colspan=4 class=muted>No changes recorded.</td></tr>')
            + "</table></div></div></div>")
    return page(req, p["name"], body, "products")


@route("GET", r"/products/([A-Z]{2}-[A-Z]{2}-\d{3})")
def product(req, sku):
    con = db()
    p = con.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
    con.close()
    if not p:
        return 404, {"Content-Type": "text/html"}, layout(req, "Not found", "<h1>Product not found</h1>").encode()
    return product_form(req, p)


@route("POST", r"/products/([A-Z]{2}-[A-Z]{2}-\d{3})")
def save_product(req, sku):
    con = db()
    p = con.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
    if not p:
        con.close()
        return redirect("/products")
    f = {k: req.form.get(k, "") for k in FIELDS}
    new, err = {}, ""
    new["name"] = f["name"].strip()
    new["category"], new["supplier"], new["supplier_code"] = f["category"], f["supplier"], f["supplier_code"].strip()
    new["description"], new["status"] = f["description"].strip(), f["status"]
    new["promo_label"] = f["promo_label"].strip() or None
    cost, retail, sale = parse_money(f["cost"]), parse_money(f["retail"]), parse_money(f["sale_price"])
    start, end = parse_date(f["sale_start"]), parse_date(f["sale_end"])
    try:
        new["stock"] = int(f["stock"].strip())
    except ValueError:
        new["stock"] = None
    try:
        new["weight_kg"] = round(float(f["weight_kg"].strip() or 0), 2)
    except ValueError:
        new["weight_kg"] = None
    if not new["name"]:
        err = "The product needs a name."
    elif new["status"] not in STATUSES:
        err = "Choose a status."
    elif cost in (None, "") or retail in (None, "") or cost <= 0 or retail <= 0:
        err = "Enter the cost and regular retail price as amounts, e.g. 12.40."
    elif new["stock"] is None or new["stock"] < 0:
        err = "Stock must be a whole number."
    elif new["weight_kg"] is None:
        err = "Weight must be a number."
    elif sale is None:
        err = "The sale price is not a valid amount."
    elif start is None or end is None:
        err = "Enter the sale dates as YYYY-MM-DD (e.g. 2026-11-27)."
    elif sale == "" and (start or end):
        err = "Enter a sale price, or clear the sale dates."
    elif sale != "" and not (start and end):
        err = "A sale price needs a start and an end date."
    elif sale != "" and sale >= retail:
        err = "The sale price must be lower than the regular retail price."
    elif sale != "" and start > end:
        err = "The sale cannot end before it starts."
    if err:
        con.close()
        return product_form(req, p, err, {k: f[k] for k in FIELDS})
    new.update(cost=cost, retail=retail, sale_price=None if sale == "" else sale, sale_start=start or None,
               sale_end=end or None)
    if new["sale_price"] is None:
        new["promo_label"] = None
    changed = []
    for k in FIELDS:
        old = p[k]
        if (old if old not in ("",) else None) != new[k] and not (isinstance(old, float) and isinstance(new[k], float) and abs(old - new[k]) < 0.0001):
            changed.append(k)
            con.execute("INSERT INTO changes(ts, user, sku, field, old, new) VALUES (?,?,?,?,?,?)",
                        (now(), req.user["username"], sku, k, "" if old is None else str(old), "" if new[k] is None else str(new[k])))
    con.execute("UPDATE products SET " + ", ".join(f"{k}=?" for k in FIELDS) + ", updated_at=? WHERE sku=?",
                [new[k] for k in FIELDS] + [now(), sku])
    audit(con, req, "product saved", f"{sku} {p['name']}: " + (", ".join(changed) if changed else "no changes"))
    con.commit()
    con.close()
    return redirect(f"/products/{sku}", [["ok", f"Saved {p['name']} ({sku})."]])


@route("GET", "/suppliers")
def suppliers(req):
    con = db()
    rows = con.execute("SELECT s.*, (SELECT COUNT(*) FROM products p WHERE p.supplier=s.name) n FROM suppliers s ORDER BY name").fetchall()
    con.close()
    body = ('<h1>Suppliers</h1><table class="t"><tr><th>Supplier</th><th>Code prefix</th><th>Contact</th><th>Email</th>'
            '<th>Phone</th><th class=n>Products</th></tr>')
    for s in rows:
        body += (f'<tr><td><a href="/products?supplier={urllib.parse.quote(s["name"])}">{E(s["name"])}</a></td><td>{E(s["prefix"])}</td>'
                 f'<td>{E(s["contact"])}</td><td>{E(s["email"])}</td><td>{E(s["phone"])}</td><td class=n>{s["n"]}</td></tr>')
    return page(req, "Suppliers", body + "</table>", "suppliers")


@route("GET", "/policy")
def policy(req):
    con = db()
    cats = con.execute("SELECT * FROM categories ORDER BY name").fetchall()
    text = setting(con, "policy_html")
    con.close()
    tab = ('<table class="t" style="max-width:520px"><tr><th>Category</th><th class=n>Markup on cost</th></tr>'
           + "".join(f'<tr><td>{E(c["name"])}</td><td class=n>× {c["markup"]:.2f}</td></tr>' for c in cats) + "</table>")
    return page(req, "Pricing policy", f'<div class="policy card">{text.replace("{{MARKUPS}}", tab)}</div>', "policy")


@route("GET", "/activity")
def activity(req):
    pg = int(req.q.get("page", "1")) if req.q.get("page", "1").isdigit() else 1
    con = db()
    rows = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30 OFFSET ?", ((pg - 1) * 30,)).fetchall()
    n = con.execute("SELECT COUNT(*) n FROM audit").fetchone()["n"]
    con.close()
    body = '<h1>Activity log</h1><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
    body += "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in rows)
    body += f'</table><div class="pager">{n} entries · page {pg} '
    if pg > 1:
        body += f'<a href="/activity?page={pg - 1}">&laquo; Newer</a>'
    if pg * 30 < n:
        body += f'<a href="/activity?page={pg + 1}">Older &raquo;</a>'
    return page(req, "Activity", body + "</div>", "activity")


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "ShopAdmin/3.1"

    def log_message(self, fmt, *args):
        pass

    def handle_any(self, method, head=False):
        try:
            req = Req(self, method)
            for m, rx, fn in ROUTES:
                mt = rx.match(req.path)
                if m == method and mt:
                    if not req.user and req.path != "/login":
                        status, headers, body = redirect("/login")
                    else:
                        status, headers, body = fn(req, *mt.groups())
                    break
            else:
                status, headers, body = 404, {"Content-Type": "text/plain"}, b"Not found"
        except Exception as e:  # keep the server alive whatever happens
            status, headers, body = 500, {"Content-Type": "text/plain"}, f"Internal error: {e!r}".encode()
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_GET(self):
        self.handle_any("GET")

    def do_HEAD(self):
        self.handle_any("GET", head=True)

    def do_POST(self):
        self.handle_any("POST")


def main():
    global DB
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8135)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
