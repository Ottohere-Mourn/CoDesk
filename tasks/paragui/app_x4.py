#!/usr/bin/env python3
"""LabDesk - research-group administration portal, School of Informatics, University of Northbridge (paraGUI pair x4).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Expense claims (lines in original currency, converted to GBP with the School's FX table for the receipt date,
submitted claims get a CLM number), the groups' publication records (feed of the lab websites), members, grants and
FX rates. The "Group" selector in the header and the list filters are remembered per login session.
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

APP, COOKIE = "LabDesk", "labdesk_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
PAGE = 12
CATEGORIES = ["Travel (air/rail)", "Accommodation", "Subsistence", "Local transport", "Registration", "Other"]
CURRENCIES = ["GBP", "EUR", "SEK", "USD"]
PUB_TYPES = ["Conference paper", "Journal article", "Workshop paper", "Preprint"]
RUNTIME_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(sid TEXT PRIMARY KEY, user_id INTEGER, created TEXT, state TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
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
    return f"£{float(v or 0):,.2f}"


def nice_date(s):
    try:
        return dt.date.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s or ""


def setting(con, key):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else ""


def parse_amount(s):
    s = re.sub(r"[£€$,\s]|SEK|kr", "", s or "", flags=re.I)
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return v if v > 0 else None


def parse_date(s):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime((s or "").strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def fx_rate(con, currency, date):
    if currency == "GBP":
        return 1.0
    r = con.execute("SELECT rate FROM fx WHERE currency=? AND date<=? ORDER BY date DESC LIMIT 1", (currency, date)).fetchone()
    return r["rate"] if r else None


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
            self.form = {k: v[-1] for k, v in urllib.parse.parse_qs(body.decode("utf8", "replace"), keep_blank_values=True).items()}
        self.sid, self.user, self.state, self._dirty = None, None, {}, False
        c = SimpleCookie(h.headers.get("Cookie", ""))
        if COOKIE in c:
            con = db()
            r = con.execute("SELECT s.sid, s.state, u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE sid=?",
                            (c[COOKIE].value,)).fetchone()
            con.close()
            if r:
                self.sid, self.user, self.state = r["sid"], dict(r), json.loads(r["state"] or "{}")

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        if self.state.get(key) != value:
            self.state[key] = value
            self._dirty = True

    def flash(self, msg, kind="ok"):
        self.state.setdefault("flash", []).append([kind, msg])
        self._dirty = True

    def save(self):
        if self.sid and self._dirty:
            con = db()
            con.execute("UPDATE sessions SET state=? WHERE sid=?", (json.dumps(self.state), self.sid))
            con.commit()
            con.close()

    def group(self):
        return self.get("group", "marsh")


def audit(con, req, action, detail):
    con.execute("INSERT INTO audit(ts, user, action, detail) VALUES (?,?,?,?)",
                (now(), req.user["username"] if req.user else "-", action, detail))


CSS = """
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#eef2f5;color:#1d2731}
a{color:#0f5c7a;text-decoration:none}a:hover{text-decoration:underline}
header{background:#123247;color:#e6f0f5;display:flex;align-items:center;gap:20px;padding:0 20px;height:56px;border-bottom:4px solid #c8a24a;white-space:nowrap}
header .brand{font-weight:700;font-size:19px}header .brand small{font-weight:400;opacity:.75;margin-left:8px;font-size:13px}
header nav a{color:#e6f0f5;margin-right:13px;font-size:14px}header nav a.on{border-bottom:2px solid #c8a24a;padding-bottom:3px}
header form{margin-left:auto;display:flex;gap:6px;align-items:center;font-size:13px}header select{padding:3px 6px}
header .who{font-size:13px;opacity:.9}header .who a{color:#f3d58c}
main{max-width:1200px;margin:22px auto;padding:0 22px}h1{font-size:23px;margin:4px 0 16px}h2{font-size:17px;margin:22px 0 10px}
.card{background:#fff;border:1px solid #d3dde4;border-radius:6px;padding:16px 18px;margin-bottom:16px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #d3dde4}
table.t th{background:#e2eaf0;text-align:left;font-size:13px;padding:7px 9px;border-bottom:1px solid #c9d5de}
table.t td{padding:6px 9px;border-bottom:1px solid #e8eef2;font-size:14px;vertical-align:top}table.t tr:hover td{background:#f6f9fb}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tr.tot td{font-weight:700;background:#f2f6f8}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;background:#e6e6e6}
.b-Draft{background:#fff0cc;color:#8a5a00}.b-Submitted{background:#e2ecfa;color:#204e8f}.b-Approved{background:#dcefdc;color:#25632a}
.b-Paid{background:#d5ece9;color:#14605a}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#e1f3e1;border:1px solid #9ccf9c}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}form.inline{display:inline}
label{display:block;font-size:13px;color:#4a5864;margin:8px 0 3px}
input[type=text],input[type=password],input[type=date],select,textarea{padding:6px 8px;border:1px solid #b9c7d1;border-radius:4px;font-size:14px}
button{background:#0f5c7a;color:#fff;border:0;border-radius:4px;padding:7px 14px;font-size:14px;cursor:pointer}
button.ghost{background:#fff;color:#0f5c7a;border:1px solid #b9c7d1}button.go{background:#2e7d32}
.filters{display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;flex-wrap:wrap}.filters label{margin:0 0 3px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.kpi{font-size:24px;font-weight:700}.muted{color:#6b7883;font-size:13px}
.pager{margin:10px 0;font-size:14px}.pager a{margin-right:8px}.login{max-width:380px;margin:90px auto}
.two{display:grid;grid-template-columns:1.5fr 1fr;gap:18px}.row{display:flex;gap:10px;flex-wrap:wrap}.row>div{flex:1;min-width:120px}
"""


def groups(con):
    return [(r["id"], r["name"]) for r in con.execute("SELECT * FROM groups ORDER BY id")]


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.state.pop("flash", []))
    if flashes:
        req._dirty = True
    head = f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
    if not req.user:
        return head + flashes + body + "</body></html>"
    links = [("home", "/", "Home"), ("claims", "/claims", "Expense claims"), ("pubs", "/publications", "Publications"),
             ("members", "/members", "Members"), ("grants", "/grants", "Grants"), ("fx", "/fx", "FX rates"),
             ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    con = db()
    opts = "".join(f'<option value="{g}"{" selected" if g == req.group() else ""}>{E(n)}</option>' for g, n in groups(con))
    con.close()
    return (head + f'<header><div class="brand">{APP}<small>Informatics · Northbridge</small></div>'
            f'<nav>{navh}</nav><form method=post action="/group"><input type=hidden name=next value="{E(req.h.path)}">Group '
            f'<select name=group onchange="this.form.submit()">{opts}</select><noscript><button>Set</button></noscript></form>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header>'
            f"<main>{flashes}{body}</main></body></html>")


def redirect(url):
    return 303, {"Location": url}, b""


def page(req, title, body, nav=""):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, layout(req, title, body, nav).encode()


def opts(values, cur, labels=None):
    return "".join(f'<option value="{E(v)}"{" selected" if str(v) == str(cur) else ""}>{E((labels or {}).get(v, v))}</option>'
                   for v in values)


def pager(base, pg, pages, n, what):
    s = f'<div class="pager">{n} {what} · page {pg} of {pages} &nbsp; '
    if pg > 1:
        s += f'<a href="{base}page={pg - 1}">&laquo; Previous</a>'
    if pg < pages:
        s += f'<a href="{base}page={pg + 1}">Next &raquo;</a>'
    return s + "</div>"


def group_name(con, gid):
    r = con.execute("SELECT name FROM groups WHERE id=?", (gid,)).fetchone()
    return r["name"] if r else gid


# ---------------------------------------------------------------- auth
@route("GET", "/login")
def login_form(req):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>LabDesk</h1><p class="muted">School of Informatics · research group administration</p>'
            '<form method=post action="/login"><label>Username</label><input type=text name=username autofocus style="width:100%">'
            '<label>Password</label><input type=password name=password style="width:100%"><p><button>Sign in</button></p></form></div>')
    return page(req, "Sign in", body)


@route("POST", "/login")
def login(req):
    con = db()
    u = con.execute("SELECT * FROM users WHERE username=?", (req.form.get("username", "").strip().lower(),)).fetchone()
    if not u or hashlib.sha256((u["salt"] + req.form.get("password", "")).encode()).hexdigest() != u["pw"]:
        con.close()
        req.state["flash"] = [["err", "Wrong username or password."]]
        return login_form(req)
    sid = secrets.token_hex(16)
    con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], now(), json.dumps({"group": "marsh"})))
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
    req.sid = None
    return 303, {"Location": "/login", "Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0"}, b""


@route("POST", "/group")
def set_group(req):
    con = db()
    if req.form.get("group") in dict(groups(con)):
        req.set("group", req.form["group"])
        req.set("claims_page", 1)
        req.set("pubs_page", 1)
    con.close()
    nxt = req.form.get("next", "/")
    return redirect(nxt if nxt.startswith("/") else "/")


# ---------------------------------------------------------------- home
@route("GET", "/")
def home(req):
    g = req.group()
    con = db()
    gname = group_name(con, g)
    drafts = con.execute("SELECT COUNT(*) n FROM claims WHERE group_id=? AND status='Draft'", (g,)).fetchone()["n"]
    sub = con.execute("SELECT COUNT(*) n FROM claims WHERE group_id=? AND status='Submitted'", (g,)).fetchone()["n"]
    pubs = con.execute("SELECT COUNT(*) n FROM pubs WHERE group_id=? AND deleted=0", (g,)).fetchone()["n"]
    acts = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 10").fetchall()
    biz = setting(con, "business_date")
    con.close()
    body = (f'<h1>{E(gname)}</h1><p class="muted">Today {nice_date(biz)} · switch group in the header</p><div class="grid">'
            f'<div class="card"><div class="muted">Draft claims</div><div class="kpi">{drafts}</div></div>'
            f'<div class="card"><div class="muted">Claims awaiting Finance</div><div class="kpi">{sub}</div></div>'
            f'<div class="card"><div class="muted">Publications listed</div><div class="kpi">{pubs}</div></div></div>'
            '<h2>Recent activity</h2><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
            + "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in acts)
            + "</table>")
    return page(req, "Home", body, "home")


# ---------------------------------------------------------------- claims
CLAIM_SQL = """SELECT c.*, m.name AS member, COALESCE((SELECT SUM(gbp) FROM claim_lines l WHERE l.claim_id=c.id AND l.deleted=0),0) AS total,
    (SELECT COUNT(*) FROM claim_lines l WHERE l.claim_id=c.id AND l.deleted=0) AS nlines FROM claims c JOIN members m ON m.id=c.member_id"""


@route("GET", "/claims")
def claims(req):
    for key in ("status", "q"):
        if key in req.q:
            req.set("claims_" + key, req.q[key].strip())
            req.set("claims_page", 1)
    if req.q.get("page", "").isdigit():
        req.set("claims_page", int(req.q["page"]))
    g, st, q = req.group(), req.get("claims_status", ""), req.get("claims_q", "")
    con = db()
    rows = [r for r in con.execute(CLAIM_SQL + " WHERE c.group_id=? ORDER BY c.id DESC", (g,))
            if (not st or r["status"] == st) and (not q or q.lower() in (r["member"] + " " + r["title"] + " " + (r["number"] or "")).lower())]
    gname = group_name(con, g)
    con.close()
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = min(max(1, int(req.get("claims_page", 1))), pages)
    body = (f'<h1>Expense claims <span class="muted">· {E(gname)}</span></h1><p><a href="/claims/new"><button>New claim</button></a></p>'
            '<form class="filters" method=get action="/claims"><div><label>Status</label><select name=status>'
            + opts(["", "Draft", "Submitted", "Approved", "Paid"], st, {"": "All statuses"}) +
            f'</select></div><div><label>Search traveller / trip / number</label><input type=text name=q value="{E(q)}" style="width:260px"></div>'
            '<div><button>Filter</button></div></form><table class="t"><tr><th>Number</th><th>Traveller</th><th>Trip / purpose</th>'
            '<th>Grant</th><th class=n>Lines</th><th class=n>Total</th><th>Status</th><th>Created</th></tr>')
    for r in rows[(pg - 1) * PAGE: pg * PAGE]:
        body += (f'<tr><td><a href="/claims/{r["id"]}">{E(r["number"] or "(draft #" + str(r["id"]) + ")")}</a></td><td>{E(r["member"])}</td>'
                 f'<td>{E(r["title"])}</td><td>{E(r["grant_code"])}</td><td class=n>{r["nlines"]}</td><td class=n>{gbp(r["total"])}</td>'
                 f'<td><span class="badge b-{r["status"]}">{r["status"]}</span></td><td>{E(r["created_at"][:10])}</td></tr>')
    if not rows:
        body += '<tr><td colspan=8 class=muted>No claims match.</td></tr>'
    return page(req, "Claims", body + "</table>" + pager("/claims?", pg, pages, len(rows), "claims"), "claims")


@route("GET", "/claims/new")
def claim_new(req):
    g = req.group()
    con = db()
    mem = con.execute("SELECT * FROM members WHERE group_id=? ORDER BY name", (g,)).fetchall()
    grants = con.execute("SELECT * FROM grants ORDER BY code").fetchall()
    gname = group_name(con, g)
    con.close()
    mopts = "".join(f'<option value="{m["id"]}">{E(m["name"])} ({E(m["role"])}, default grant {E(m["default_grant"])})</option>' for m in mem)
    gopts = '<option value="">Traveller\'s default grant</option>' + "".join(
        f'<option value="{E(x["code"])}">{E(x["code"])} - {E(x["title"])}</option>' for x in grants)
    body = (f'<p><a href="/claims">&laquo; Claims</a></p><h1>New expense claim <span class="muted">· {E(gname)}</span></h1>'
            '<div class="card" style="max-width:720px"><form method=post action="/claims/new">'
            f'<label>Traveller ({E(gname)} members - switch the group in the header for the other group)</label>'
            f'<select name=member_id style="width:100%">{mopts}</select><label>Trip / purpose</label>'
            '<input type=text name=title style="width:100%" placeholder="e.g. ECCV 2026, Malmö"><label>Charge to grant</label>'
            f'<select name=grant style="width:100%">{gopts}</select><p><button>Create draft claim</button></p></form></div>')
    return page(req, "New claim", body, "claims")


@route("POST", "/claims/new")
def claim_create(req):
    con = db()
    m = con.execute("SELECT * FROM members WHERE id=?", (req.form.get("member_id", "0"),)).fetchone()
    title = req.form.get("title", "").strip()
    grant = req.form.get("grant", "").strip()
    if not m or not title:
        con.close()
        req.flash("Choose the traveller and describe the trip.", "err")
        return redirect("/claims/new")
    if grant and not con.execute("SELECT 1 FROM grants WHERE code=?", (grant,)).fetchone():
        grant = ""
    grant = grant or m["default_grant"]
    cur = con.execute("INSERT INTO claims(number, member_id, group_id, grant_code, title, status, created_at, created_by) "
                      "VALUES (NULL,?,?,?,?, 'Draft', ?, ?)", (m["id"], m["group_id"], grant, title, now(), req.user["username"]))
    audit(con, req, "claim created", f"draft #{cur.lastrowid} {m['name']} - {title} ({grant})")
    con.commit()
    con.close()
    req.flash(f"Draft claim created for {m['name']}. Add a line for each receipt, then submit it.")
    return redirect(f"/claims/{cur.lastrowid}")


@route("GET", r"/claims/(\d+)")
def claim(req, cid):
    con = db()
    c = con.execute(CLAIM_SQL + " WHERE c.id=?", (cid,)).fetchone()
    if not c:
        con.close()
        return redirect("/claims")
    lines = con.execute("SELECT * FROM claim_lines WHERE claim_id=? AND deleted=0 ORDER BY date, id", (cid,)).fetchall()
    grants = [r["code"] for r in con.execute("SELECT code FROM grants ORDER BY code")]
    gname = group_name(con, c["group_id"])
    con.close()
    draft = c["status"] == "Draft"
    body = (f'<p><a href="/claims">&laquo; Claims</a></p><h1>{E(c["number"] or "Draft claim #" + str(c["id"]))} '
            f'<span class="badge b-{c["status"]}">{c["status"]}</span></h1><div class="two"><div><div class="card">'
            f'<b>{E(c["member"])}</b> · {E(gname)}<br>Trip: {E(c["title"])}<br>Grant: <b>{E(c["grant_code"])}</b><br>'
            f'<span class="muted">created {E(c["created_at"])} by {E(c["created_by"])}'
            f'{" · submitted " + E(c["submitted_at"]) if c["submitted_at"] else ""}</span></div>'
            '<table class="t"><tr><th>Date</th><th>Category</th><th>Description</th><th class=n>Amount</th><th class=n>Rate</th>'
            '<th class=n>GBP</th><th></th></tr>')
    for ln in lines:
        body += (f'<tr><td>{nice_date(ln["date"])}</td><td>{E(ln["category"])}</td><td>{E(ln["description"])}</td>'
                 f'<td class=n>{E(ln["currency"])} {ln["amount"]:,.2f}</td><td class=n>{ln["rate"]:.5g}</td><td class=n>{gbp(ln["gbp"])}</td><td>'
                 + (f'<form class=inline method=post action="/claims/{cid}/lines/{ln["id"]}/delete"><button class=ghost>Remove</button></form>' if draft else "")
                 + "</td></tr>")
    if not lines:
        body += '<tr><td colspan=7 class=muted>No lines yet.</td></tr>'
    body += f'<tr class=tot><td colspan=5>Total claimed</td><td class=n>{gbp(c["total"])}</td><td></td></tr></table></div><div>'
    if draft:
        body += ('<div class="card"><h2 style="margin-top:0">Add a receipt line</h2>'
                 f'<form method=post action="/claims/{cid}/lines"><div class=row><div><label>Receipt date</label><input type=date name=date required></div>'
                 f'<div><label>Category</label><select name=category>{opts(CATEGORIES, "")}</select></div></div>'
                 '<label>Description</label><input type=text name=description style="width:100%">'
                 f'<div class=row><div><label>Currency</label><select name=currency>{opts(CURRENCIES, "GBP")}</select></div>'
                 '<div><label>Amount (receipt currency)</label><input type=text name=amount required></div></div>'
                 '<p class=muted>Enter the amount in the currency of the receipt; LabDesk converts it at the School rate for the receipt date.</p>'
                 '<p><button>Add line</button></p></form></div>'
                 f'<div class="card"><form method=post action="/claims/{cid}/grant"><label>Charge to grant</label><select name=grant>'
                 f'{opts(grants, c["grant_code"])}</select> <button class=ghost>Change</button></form></div>'
                 f'<div class="card"><form method=post action="/claims/{cid}/submit" onsubmit="return confirm(\'Submit this claim to Finance?\')">'
                 '<p class=muted>Submitting sends the claim to School Finance and gives it a claim number.</p><button class=go>Submit claim</button></form>'
                 f'<form method=post action="/claims/{cid}/delete" onsubmit="return confirm(\'Delete this draft?\')" style="margin-top:10px">'
                 '<button class=ghost>Delete draft</button></form></div>')
    elif c["status"] == "Submitted":
        body += (f'<div class="card"><form method=post action="/claims/{cid}/reopen"><p class=muted>Finance has not processed this claim yet; '
                 'you can return it to draft to correct it (it keeps its number).</p><button class=ghost>Return to draft</button></form></div>')
    return page(req, c["number"] or "Draft claim", body + "</div></div>", "claims")


def _draft(con, cid):
    c = con.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
    return c if c and c["status"] == "Draft" else None


@route("POST", r"/claims/(\d+)/lines")
def add_line(req, cid):
    con = db()
    c = _draft(con, cid)
    date, amount = parse_date(req.form.get("date")), parse_amount(req.form.get("amount"))
    cur, cat = req.form.get("currency", "GBP"), req.form.get("category", "Other")
    if not c:
        req.flash("Only draft claims can be changed.", "err")
    elif not date or not ("2026-01-01" <= date <= setting(con, "business_date")):
        req.flash("Enter the receipt date (not in the future).", "err")
    elif amount is None or cur not in CURRENCIES or cat not in CATEGORIES:
        req.flash("Enter a positive amount and choose currency and category.", "err")
    else:
        rate = fx_rate(con, cur, date)
        if rate is None:
            req.flash(f"No {cur} rate for {date}.", "err")
        else:
            g = round(amount * rate + 1e-9, 2)
            con.execute("INSERT INTO claim_lines(claim_id, date, category, description, currency, amount, rate, gbp, deleted) "
                        "VALUES (?,?,?,?,?,?,?,?,0)", (cid, date, cat, req.form.get("description", "").strip(), cur, amount, rate, g))
            audit(con, req, "claim line added", f"claim #{cid}: {date} {cat} {cur} {amount:.2f} = {gbp(g)}")
            con.commit()
            req.flash(f"Added {cur} {amount:,.2f} ({gbp(g)}).")
    con.close()
    return redirect(f"/claims/{cid}")


@route("POST", r"/claims/(\d+)/lines/(\d+)/delete")
def del_line(req, cid, lid):
    con = db()
    if _draft(con, cid):
        con.execute("UPDATE claim_lines SET deleted=1 WHERE id=? AND claim_id=?", (lid, cid))
        audit(con, req, "claim line removed", f"claim #{cid} line {lid}")
        con.commit()
    con.close()
    return redirect(f"/claims/{cid}")


@route("POST", r"/claims/(\d+)/grant")
def change_grant(req, cid):
    con = db()
    g = req.form.get("grant", "")
    if _draft(con, cid) and con.execute("SELECT 1 FROM grants WHERE code=?", (g,)).fetchone():
        con.execute("UPDATE claims SET grant_code=? WHERE id=?", (g, cid))
        audit(con, req, "claim grant changed", f"claim #{cid} -> {g}")
        con.commit()
        req.flash(f"Claim will be charged to {g}.")
    con.close()
    return redirect(f"/claims/{cid}")


@route("POST", r"/claims/(\d+)/submit")
def submit(req, cid):
    con = db()
    c = _draft(con, cid)
    n = con.execute("SELECT COUNT(*) n FROM claim_lines WHERE claim_id=? AND deleted=0", (cid,)).fetchone()["n"]
    if not c or n == 0:
        req.flash("A claim needs at least one line before it can be submitted.", "err")
    else:
        number = c["number"]
        if not number:
            seq = int(setting(con, "next_claim")) if setting(con, "next_claim") else 1
            number = f"CLM-2026-{seq:04d}"
            con.execute("UPDATE settings SET value=? WHERE key='next_claim'", (str(seq + 1),))
        con.execute("UPDATE claims SET status='Submitted', number=?, submitted_at=? WHERE id=?", (number, now(), cid))
        audit(con, req, "claim submitted", f"{number} (draft #{cid})")
        con.commit()
        req.flash(f"Claim submitted to School Finance as {number}.")
    con.close()
    return redirect(f"/claims/{cid}")


@route("POST", r"/claims/(\d+)/reopen")
def reopen(req, cid):
    con = db()
    c = con.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
    if c and c["status"] == "Submitted":
        con.execute("UPDATE claims SET status='Draft' WHERE id=?", (cid,))
        audit(con, req, "claim returned to draft", c["number"])
        con.commit()
    con.close()
    return redirect(f"/claims/{cid}")


@route("POST", r"/claims/(\d+)/delete")
def delete_claim(req, cid):
    con = db()
    c = _draft(con, cid)
    if c and not c["number"]:
        con.execute("DELETE FROM claim_lines WHERE claim_id=?", (cid,))
        con.execute("DELETE FROM claims WHERE id=?", (cid,))
        audit(con, req, "draft claim deleted", f"#{cid} {c['title']}")
        con.commit()
        req.flash("Draft deleted.")
    else:
        req.flash("Only unsubmitted drafts can be deleted.", "err")
    con.close()
    return redirect("/claims")


# ---------------------------------------------------------------- publications
@route("GET", "/publications")
def pubs(req):
    for key in ("year", "type", "q"):
        if key in req.q:
            req.set("pubs_" + key, req.q[key].strip())
            req.set("pubs_page", 1)
    if req.q.get("page", "").isdigit():
        req.set("pubs_page", int(req.q["page"]))
    g, yr, ty, q = req.group(), req.get("pubs_year", ""), req.get("pubs_type", ""), req.get("pubs_q", "")
    con = db()
    rows = [r for r in con.execute("SELECT * FROM pubs WHERE group_id=? AND deleted=0 ORDER BY year DESC, id DESC", (g,))
            if (not yr or str(r["year"]) == yr) and (not ty or r["type"] == ty)
            and (not q or q.lower() in (r["title"] + " " + r["authors"] + " " + r["venue"]).lower())]
    years = sorted({str(r["year"]) for r in con.execute("SELECT year FROM pubs")}, reverse=True)
    gname = group_name(con, g)
    con.close()
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = min(max(1, int(req.get("pubs_page", 1))), pages)
    body = (f'<h1>Publications <span class="muted">· {E(gname)}</span></h1><p class="muted">These records feed the group\'s public web page.</p>'
            '<p><a href="/publications/new"><button>Add publication</button></a></p><form class="filters" method=get action="/publications">'
            f'<div><label>Year</label><select name=year>{opts([""] + years, yr, {"": "All years"})}</select></div>'
            f'<div><label>Type</label><select name=type>{opts([""] + PUB_TYPES, ty, {"": "All types"})}</select></div>'
            f'<div><label>Search title / authors / venue</label><input type=text name=q value="{E(q)}" style="width:260px"></div>'
            '<div><button>Filter</button></div></form><table class="t"><tr><th>Year</th><th>Title</th><th>Authors</th><th>Venue</th><th>Type</th><th>arXiv</th></tr>')
    for r in rows[(pg - 1) * PAGE: pg * PAGE]:
        body += (f'<tr><td>{r["year"]}</td><td><a href="/publications/{r["id"]}">{E(r["title"])}</a></td><td>{E(r["authors"])}</td>'
                 f'<td>{E(r["venue"])}</td><td>{E(r["type"])}</td><td>{E(r["arxiv"])}</td></tr>')
    if not rows:
        body += '<tr><td colspan=6 class=muted>No publications match.</td></tr>'
    return page(req, "Publications", body + "</table>" + pager("/publications?", pg, pages, len(rows), "publications"), "pubs")


def pub_form(con, req, p, action):
    v = lambda k, d="": E(p[k]) if p else d  # noqa: E731
    gsel = opts([g for g, _ in groups(con)], p["group_id"] if p else req.group(), dict(groups(con)))
    return (f'<form method=post action="{action}"><label>Group</label><select name=group_id>{gsel}</select>'
            f'<label>Title</label><input type=text name=title value="{v("title")}" style="width:100%">'
            f'<label>Authors (in order, comma separated)</label><input type=text name=authors value="{v("authors")}" style="width:100%">'
            f'<label>Venue</label><input type=text name=venue value="{v("venue")}" style="width:100%">'
            f'<div class=row><div><label>Year</label><input type=text name=year value="{v("year")}"></div>'
            f'<div><label>Type</label><select name=type>{opts(PUB_TYPES, p["type"] if p else "Conference paper")}</select></div>'
            f'<div><label>arXiv id</label><input type=text name=arxiv value="{v("arxiv")}" placeholder="2601.01234"></div>'
            f'<div><label>DOI</label><input type=text name=doi value="{v("doi")}"></div></div><p><button>Save</button></p></form>')


def pub_values(con, req):
    f = {k: req.form.get(k, "").strip() for k in ("group_id", "title", "authors", "venue", "year", "type", "arxiv", "doi")}
    if f["group_id"] not in dict(groups(con)) or not f["title"] or not f["authors"] or not f["venue"]:
        return None, "Group, title, authors and venue are required."
    if not re.fullmatch(r"(19|20)\d\d", f["year"]):
        return None, "Year must be a four-digit year."
    if f["type"] not in PUB_TYPES:
        f["type"] = "Conference paper"
    f["arxiv"] = re.sub(r"^(arxiv:)", "", f["arxiv"], flags=re.I).strip()
    return f, None


@route("GET", "/publications/new")
def pub_new(req):
    con = db()
    body = '<p><a href="/publications">&laquo; Publications</a></p><h1>Add publication</h1><div class="card" style="max-width:820px">'
    body += pub_form(con, req, None, "/publications/new") + "</div>"
    con.close()
    return page(req, "Add publication", body, "pubs")


@route("POST", "/publications/new")
def pub_create(req):
    con = db()
    f, err = pub_values(con, req)
    if err:
        con.close()
        req.flash(err, "err")
        return redirect("/publications/new")
    cur = con.execute("INSERT INTO pubs(group_id, title, authors, venue, year, type, arxiv, doi, deleted, updated_at, updated_by) "
                      "VALUES (?,?,?,?,?,?,?,?,0,?,?)", (f["group_id"], f["title"], f["authors"], f["venue"], int(f["year"]), f["type"],
                                                        f["arxiv"], f["doi"], now(), req.user["username"]))
    audit(con, req, "publication added", f"{group_name(con, f['group_id'])}: {f['title']} ({f['venue']} {f['year']})")
    con.commit()
    con.close()
    req.flash("Publication added.")
    return redirect(f"/publications/{cur.lastrowid}")


@route("GET", r"/publications/(\d+)")
def pub_edit(req, pid):
    con = db()
    p = con.execute("SELECT * FROM pubs WHERE id=? AND deleted=0", (pid,)).fetchone()
    if not p:
        con.close()
        return redirect("/publications")
    body = (f'<p><a href="/publications">&laquo; Publications</a></p><h1>Edit publication</h1><div class="two"><div class="card">'
            + pub_form(con, req, p, f"/publications/{pid}") + '</div><div class="card"><p class=muted>Last changed '
            f'{E(p["updated_at"])} by {E(p["updated_by"])}</p><form method=post action="/publications/{pid}/delete" '
            'onsubmit="return confirm(\'Remove this publication from the list?\')"><button class=ghost>Remove publication</button></form></div></div>')
    con.close()
    return page(req, "Edit publication", body, "pubs")


@route("POST", r"/publications/(\d+)")
def pub_update(req, pid):
    con = db()
    f, err = pub_values(con, req)
    if err:
        req.flash(err, "err")
    else:
        con.execute("UPDATE pubs SET group_id=?, title=?, authors=?, venue=?, year=?, type=?, arxiv=?, doi=?, updated_at=?, updated_by=? "
                    "WHERE id=?", (f["group_id"], f["title"], f["authors"], f["venue"], int(f["year"]), f["type"], f["arxiv"], f["doi"],
                                   now(), req.user["username"], pid))
        audit(con, req, "publication updated", f"#{pid} {f['title']} ({f['venue']} {f['year']})")
        con.commit()
        req.flash("Publication saved.")
    con.close()
    return redirect(f"/publications/{pid}")


@route("POST", r"/publications/(\d+)/delete")
def pub_delete(req, pid):
    con = db()
    p = con.execute("SELECT * FROM pubs WHERE id=?", (pid,)).fetchone()
    if p:
        con.execute("UPDATE pubs SET deleted=1 WHERE id=?", (pid,))
        audit(con, req, "publication removed", f"#{pid} {p['title']}")
        con.commit()
        req.flash("Publication removed.")
    con.close()
    return redirect("/publications")


# ---------------------------------------------------------------- reference pages
@route("GET", "/members")
def members(req):
    g = req.group()
    con = db()
    rows = con.execute("SELECT m.*, g.title AS gtitle FROM members m LEFT JOIN grants g ON g.code=m.default_grant "
                       "WHERE m.group_id=? ORDER BY m.role DESC, m.name", (g,)).fetchall()
    gname = group_name(con, g)
    con.close()
    body = (f'<h1>Members <span class="muted">· {E(gname)}</span></h1><table class="t"><tr><th>Name</th><th>Role</th><th>Email</th>'
            '<th>Default grant for travel</th></tr>')
    for m in rows:
        body += (f'<tr><td>{E(m["name"])}</td><td>{E(m["role"])}</td><td>{E(m["email"])}</td>'
                 f'<td>{E(m["default_grant"])} <span class=muted>{E(m["gtitle"])}</span></td></tr>')
    return page(req, "Members", body + "</table>", "members")


@route("GET", "/grants")
def grants_page(req):
    con = db()
    rows = con.execute("SELECT g.*, gr.name AS gname, (SELECT COALESCE(SUM(l.gbp),0) FROM claims c JOIN claim_lines l ON l.claim_id=c.id "
                       "WHERE c.grant_code=g.code AND l.deleted=0 AND c.status<>'Draft') AS spent FROM grants g "
                       "JOIN groups gr ON gr.id=g.group_id ORDER BY g.group_id, g.code").fetchall()
    con.close()
    body = ('<h1>Grants</h1><table class="t"><tr><th>Code</th><th>Title</th><th>Funder</th><th>Group</th><th>Ends</th>'
            '<th class=n>Travel budget</th><th class=n>Claimed (submitted)</th></tr>')
    for g in rows:
        body += (f'<tr><td>{E(g["code"])}</td><td>{E(g["title"])}</td><td>{E(g["funder"])}</td><td>{E(g["gname"])}</td>'
                 f'<td>{nice_date(g["end_date"])}</td><td class=n>{gbp(g["travel_budget"])}</td><td class=n>{gbp(g["spent"])}</td></tr>')
    return page(req, "Grants", body + "</table>", "grants")


@route("GET", "/fx")
def fx_page(req):
    if "month" in req.q:
        req.set("fx_month", req.q["month"])
    month = req.get("fx_month", "2026-09")
    con = db()
    months = sorted({r["date"][:7] for r in con.execute("SELECT DISTINCT date FROM fx")}, reverse=True)
    rows = con.execute("SELECT date, currency, rate FROM fx WHERE date LIKE ? ORDER BY date", (month + "%",)).fetchall()
    con.close()
    by = {}
    for r in rows:
        by.setdefault(r["date"], {})[r["currency"]] = r["rate"]
    body = ('<h1>School FX rates</h1><p class="muted">GBP per unit of foreign currency (Finance daily rate). Claim lines use the rate for '
            f'the receipt date.</p><form class="filters" method=get><div><label>Month</label><select name=month>{opts(months, month)}</select>'
            '</div><div><button>Show</button></div></form><table class="t" style="max-width:640px"><tr><th>Date</th><th class=n>EUR</th>'
            '<th class=n>SEK</th><th class=n>USD</th></tr>')
    for d in sorted(by):
        body += (f'<tr><td>{nice_date(d)}</td>' + "".join(f'<td class=n>{by[d].get(c, 0):.5f}</td>' for c in ("EUR", "SEK", "USD")) + "</tr>")
    return page(req, "FX rates", body + "</table>", "fx")


@route("GET", "/activity")
def activity(req):
    pg = int(req.q.get("page", "1")) if req.q.get("page", "1").isdigit() else 1
    con = db()
    rows = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 30 OFFSET ?", ((pg - 1) * 30,)).fetchall()
    n = con.execute("SELECT COUNT(*) n FROM audit").fetchone()["n"]
    con.close()
    body = '<h1>Activity log</h1><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
    body += "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in rows)
    return page(req, "Activity", body + "</table>" + pager("/activity?", pg, max(1, (n + 29) // 30), n, "entries"), "activity")


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "LabDesk/1.8"

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
            req.save()
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
    ap.add_argument("--port", type=int, default=8124)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
