#!/usr/bin/env python3
"""Brightwater Hub - the office intranet of Brightwater Studio (paraGUI pair x3).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Events (guest lists, hosts, CSV door-list export) and Purchasing (suppliers, catalogues, purchase orders charged to an
event). The event selector in the header and the guest-list filters are remembered per login session.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import io
import json
import re
import secrets
import sqlite3
import urllib.parse
from decimal import ROUND_HALF_UP, Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP, COOKIE = "Brightwater Hub", "bwhub_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
PAGE = 12
STATUSES = ["Invited", "Attending", "Declined"]
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


def money(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def nice_date(s):
    try:
        return dt.date.fromisoformat(s).strftime("%a %d %b %Y")
    except Exception:
        return s or ""


def po_totals(con, po):
    """(subtotal, service, vat, total) as Decimals; service charge % comes from the supplier, VAT 20% on top."""
    sub = sum((money(r["price"]) * int(r["qty"]) for r in con.execute(
        "SELECT l.qty, c.price FROM po_lines l JOIN catalogue c ON c.id=l.item_id WHERE l.po_id=?", (po["id"],))), Decimal("0"))
    pct = con.execute("SELECT service_pct FROM suppliers WHERE id=?", (po["supplier_id"],)).fetchone()["service_pct"]
    svc = money(sub * Decimal(str(pct)) / 100)
    vat = money((sub + svc) * Decimal("0.2"))
    return sub, svc, vat, sub + svc + vat


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


def audit(con, req, action, detail):
    con.execute("INSERT INTO audit(ts, user, action, detail) VALUES (?,?,?,?)",
                (now(), req.user["username"] if req.user else "-", action, detail))


CSS = """
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#eef3f4;color:#1d2a30}
a{color:#0d6e78;text-decoration:none}a:hover{text-decoration:underline}
header{background:#12343b;color:#e3f1f2;display:flex;align-items:center;gap:22px;padding:0 22px;height:56px}
header .brand{font-weight:700;font-size:19px}header .brand span{color:#5fd0c8}header nav a{color:#e3f1f2;margin-right:16px;font-size:14px}
header nav a.on{border-bottom:2px solid #5fd0c8;padding-bottom:3px}header form{margin-left:auto;display:flex;gap:6px;align-items:center;font-size:13px}
header select{padding:3px 6px}header .who{font-size:13px}header .who a{color:#9fe6df}
main{max-width:1200px;margin:22px auto;padding:0 22px}h1{font-size:23px;margin:4px 0 16px}h2{font-size:17px;margin:22px 0 10px}
.card{background:#fff;border:1px solid #cfdfe1;border-radius:6px;padding:16px 18px;margin-bottom:16px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #cfdfe1}
table.t th{background:#dcebed;text-align:left;font-size:13px;padding:7px 9px}table.t td{padding:6px 9px;border-bottom:1px solid #e3eced;font-size:14px}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tr.tot td{font-weight:700;background:#f0f7f7}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.b-Attending,.b-submitted{background:#d9f0e3;color:#1f6a3e}.b-Invited,.b-draft{background:#e5ebf7;color:#2c4b8a}
.b-Declined,.b-cancelled{background:#f7e0de;color:#93271b}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#dff3e6;border:1px solid #98cfaa}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}form.inline{display:inline}
label{display:block;font-size:13px;color:#4c5d63;margin:8px 0 3px}
input[type=text],input[type=password],input[type=number],input[type=date],select,textarea{padding:5px 7px;border:1px solid #b7c9cc;border-radius:4px;font-size:14px}
button{background:#0d6e78;color:#fff;border:0;border-radius:4px;padding:6px 13px;font-size:14px;cursor:pointer}
button.ghost{background:#fff;color:#0d6e78;border:1px solid #b7c9cc}button.danger{background:#a8321f}
.filters{display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;flex-wrap:wrap}.filters label{margin:0 0 3px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.kpi{font-size:24px;font-weight:700}.muted{color:#6b7c82;font-size:13px}
.pager{margin:10px 0;font-size:14px}.pager a{margin-right:8px}.login{max-width:380px;margin:90px auto}
.two{display:grid;grid-template-columns:1.5fr 1fr;gap:18px}.wide{grid-template-columns:2.3fr 1fr}
td.nw{white-space:nowrap}form.qty{display:flex;gap:4px;justify-content:flex-end}
"""


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.state.pop("flash", []))
    if flashes:
        req._dirty = True
    head = f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
    if not req.user:
        return head + flashes + body + "</body></html>"
    links = [("home", "/", "Home"), ("guests", "/guests", "Guest list"), ("events", "/events", "Events"),
             ("purchasing", "/purchasing", "Purchasing"), ("suppliers", "/suppliers", "Suppliers"), ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    con = db()
    evs = con.execute("SELECT id, name FROM events ORDER BY date").fetchall()
    con.close()
    cur = cur_event(req)
    opts = "".join(f'<option value="{e["id"]}"{" selected" if e["id"] == cur else ""}>{E(e["name"])}</option>' for e in evs)
    return (head + f'<header><div class="brand">Brightwater <span>Hub</span></div><nav>{navh}</nav>'
            f'<form method=post action="/event"><input type=hidden name=next value="{E(req.h.path)}">Event '
            f'<select name=event onchange="this.form.submit()">{opts}</select><noscript><button>Set</button></noscript></form>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header>'
            f"<main>{flashes}{body}</main></body></html>")


def cur_event(req):
    """The event chosen in the header (stored in the login session); falls back to the Hub default."""
    if not req.get("event"):
        con = db()
        req.set("event", int(con.execute("SELECT value FROM settings WHERE key='default_event'").fetchone()["value"]))
        con.close()
    return int(req.get("event"))


def redirect(url):
    return 303, {"Location": url}, b""


def page(req, title, body, nav=""):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, layout(req, title, body, nav).encode()


def badge(s):
    return f'<span class="badge b-{E(s)}">{E(s)}</span>'


def options(items, sel):
    return "".join(f'<option value="{E(v)}"{" selected" if str(v) == str(sel) else ""}>{E(t)}</option>' for v, t in items)


# ---------------------------------------------------------------- auth
@route("GET", "/login")
def login_form(req):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>Brightwater Hub</h1><p class="muted">Brightwater Studio · office intranet</p>'
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
    ev = con.execute("SELECT value FROM settings WHERE key='default_event'").fetchone()["value"]
    con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], now(), json.dumps({"event": int(ev)})))
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


@route("POST", "/event")
def set_event(req):
    con = db()
    ok = con.execute("SELECT 1 FROM events WHERE id=?", (req.form.get("event", "0"),)).fetchone()
    con.close()
    if ok and req.form.get("event", "").isdigit():
        req.set("event", int(req.form["event"]))
        req.set("g_page", 1)
    nxt = req.form.get("next", "/")
    return redirect(nxt if nxt.startswith("/") else "/")


# ---------------------------------------------------------------- events & guests
def event_row(con, eid):
    return con.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()


@route("GET", "/")
def home(req):
    con = db()
    ev = event_row(con, cur_event(req))
    rows = con.execute("SELECT * FROM guests WHERE event_id=? AND kind<>'staff'", (ev["id"],)).fetchall()
    hosts = con.execute("SELECT COUNT(*) n FROM guests WHERE event_id=? AND kind='staff'", (ev["id"],)).fetchone()["n"]
    acts = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 8").fetchall()
    con.close()
    cnt = {s: sum(r["status"] == s for r in rows) for s in STATUSES}
    people = sum(1 + bool((r["plus_one"] or "").strip()) for r in rows if r["status"] == "Attending")
    body = (f'<h1>{E(ev["name"])}</h1><p class="muted">{nice_date(ev["date"])} · {E(ev["venue"])} · '
            f'<a href="/events/{ev["id"]}">event page</a></p><div class="grid">'
            f'<div class="card"><div class="muted">Attending (replies)</div><div class="kpi">{cnt["Attending"]}</div></div>'
            f'<div class="card"><div class="muted">Guests incl. plus-ones</div><div class="kpi">{people}</div></div>'
            f'<div class="card"><div class="muted">Declined</div><div class="kpi">{cnt["Declined"]}</div></div>'
            f'<div class="card"><div class="muted">Awaiting reply / hosts</div><div class="kpi">{cnt["Invited"]} / {hosts}</div></div></div>'
            '<h2>Recent activity</h2><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
            + "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in acts)
            + "</table>")
    return page(req, "Home", body, "home")


@route("GET", "/guests")
def guests(req):
    for key in ("status", "q"):
        if key in req.q:
            req.set("g_" + key, req.q[key].strip())
            req.set("g_page", 1)
    if req.q.get("page", "").isdigit():
        req.set("g_page", int(req.q["page"]))
    st, q = req.get("g_status", ""), req.get("g_q", "")
    con = db()
    ev = event_row(con, cur_event(req))
    rows = [r for r in con.execute("SELECT * FROM guests WHERE event_id=? AND kind<>'staff' ORDER BY name", (ev["id"],))
            if (not st or r["status"] == st) and (not q or q.lower() in f'{r["name"]} {r["company"]} {r["email"]} {r["plus_one"]}'.lower())]
    con.close()
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = min(max(1, int(req.get("g_page", 1))), pages)
    body = (f'<h1>Guest list <span class="muted">· {E(ev["name"])}</span></h1>'
            '<form class="filters" method=get action="/guests"><div><label>Status</label><select name=status>'
            + options([("", "All")] + [(s, s) for s in STATUSES], st) +
            f'</select></div><div><label>Search name / company / email</label><input type=text name=q value="{E(q)}" style="width:260px"></div>'
            '<div><button>Filter</button></div><div><a class=muted href="/guests?status=&amp;q=">Clear filters</a></div>'
            '<div style="margin-left:auto"><a href="/guests/new">+ Add guest</a> · <a href="/guests/export.csv">Export door list (CSV)</a></div></form>'
            '<table class="t"><tr><th>Name</th><th>Company</th><th>Email</th><th>Status</th><th>Plus-one</th><th></th></tr>')
    for r in rows[(pg - 1) * PAGE: pg * PAGE]:
        body += (f'<tr><td><a href="/guests/{r["id"]}">{E(r["name"])}</a>{" <span class=muted>(added)</span>" if r["kind"] == "added" else ""}</td>'
                 f'<td>{E(r["company"])}</td><td>{E(r["email"])}</td>'
                 f'<td><select name=status form="g{r["id"]}">{options([(s, s) for s in STATUSES], r["status"])}</select></td>'
                 f'<td><input type=text name=plus_one form="g{r["id"]}" value="{E(r["plus_one"])}" placeholder="none" style="width:170px"></td>'
                 f'<td><form id="g{r["id"]}" method=post action="/guests/{r["id"]}"><button class=ghost>Save</button></form></td></tr>')
    if not rows:
        body += '<tr><td colspan=6 class=muted>No guests match the filters.</td></tr>'
    body += f'</table><div class="pager">{len(rows)} guests · page {pg} of {pages} &nbsp; '
    if pg > 1:
        body += f'<a href="/guests?page={pg - 1}">&laquo; Previous</a>'
    if pg < pages:
        body += f'<a href="/guests?page={pg + 1}">Next &raquo;</a>'
    return page(req, "Guest list", body + "</div>", "guests")


@route("GET", r"/guests/(\d+)")
def guest(req, gid):
    con = db()
    r = con.execute("SELECT g.*, e.name ev FROM guests g JOIN events e ON e.id=g.event_id WHERE g.id=?", (gid,)).fetchone()
    con.close()
    if not r:
        return redirect("/guests")
    body = (f'<p><a href="/guests">&laquo; Guest list</a></p><h1>{E(r["name"])} {badge(r["status"])}</h1><div class="two"><div class="card">'
            f'<form method=post action="/guests/{r["id"]}"><p class=muted>{E(r["ev"])} · {E(r["company"])} · {E(r["email"])}</p>'
            f'<label>Status</label><select name=status>{options([(s, s) for s in STATUSES], r["status"])}</select>'
            f'<label>Plus-one (name)</label><input type=text name=plus_one value="{E(r["plus_one"])}" style="width:100%">'
            f'<label>Main course(s)</label><input type=text name=main value="{E(r["main"])}" style="width:100%">'
            f'<label>Dietary requirements</label><input type=text name=dietary value="{E(r["dietary"])}" style="width:100%">'
            f'<label>Notes</label><textarea name=notes rows=3 style="width:100%">{E(r["notes"])}</textarea><p><button>Save</button></p></form>'
            f'</div><div class="card muted">Last updated {E(r["updated_at"] or "never")}</div></div>')
    return page(req, r["name"], body, "guests")


@route("POST", r"/guests/(\d+)")
def update_guest(req, gid):
    con = db()
    r = con.execute("SELECT * FROM guests WHERE id=?", (gid,)).fetchone()
    if r and req.form.get("status", r["status"]) in STATUSES:
        vals = {k: req.form.get(k, r[k] or "").strip() for k in ("status", "plus_one", "main", "dietary", "notes")}
        con.execute("UPDATE guests SET status=?, plus_one=?, main=?, dietary=?, notes=?, updated_at=? WHERE id=?",
                    (vals["status"], vals["plus_one"], vals["main"], vals["dietary"], vals["notes"], now(), gid))
        audit(con, req, "guest updated", f'{r["name"]}: {vals["status"]}' + (f' +1 {vals["plus_one"]}' if vals["plus_one"] else ""))
        con.commit()
        req.flash(f'{r["name"]} saved ({vals["status"]}).')
    con.close()
    return redirect(f"/guests/{gid}" if "main" in req.form else "/guests")


@route("GET", "/guests/new")
def new_guest_form(req):
    con = db()
    evs = con.execute("SELECT id, name FROM events ORDER BY date").fetchall()
    con.close()
    body = ('<p><a href="/guests">&laquo; Guest list</a></p><h1>Add a guest</h1><div class="card" style="max-width:560px">'
            '<form method=post action="/guests/new"><label>Event</label><select name=event_id>'
            + options([(e["id"], e["name"]) for e in evs], cur_event(req)) +
            '</select><label>Full name</label><input type=text name=name style="width:100%"><label>Company</label>'
            '<input type=text name=company style="width:100%"><label>Email</label><input type=text name=email style="width:100%">'
            '<label>Status</label><select name=status>' + options([(s, s) for s in STATUSES], "Attending") + '</select>'
            '<label>Plus-one (name)</label><input type=text name=plus_one style="width:100%">'
            '<label>Notes</label><textarea name=notes rows=2 style="width:100%"></textarea><p><button>Add guest</button></p></form></div>')
    return page(req, "Add guest", body, "guests")


@route("POST", "/guests/new")
def add_guest(req):
    name = req.form.get("name", "").strip()
    con = db()
    ev = event_row(con, req.form.get("event_id", "0"))
    if not name or not ev or req.form.get("status") not in STATUSES:
        con.close()
        req.flash("Enter the guest's name.", "err")
        return redirect("/guests/new")
    cur = con.execute("INSERT INTO guests(event_id, kind, name, company, email, status, plus_one, main, dietary, notes, updated_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (ev["id"], "added", name, req.form.get("company", "").strip(),
                                                         req.form.get("email", "").strip(), req.form["status"],
                                                         req.form.get("plus_one", "").strip(), "", "", req.form.get("notes", "").strip(), now()))
    audit(con, req, "guest added", f'{name} to {ev["name"]} ({req.form["status"]})')
    con.commit()
    con.close()
    req.flash(f"{name} added to {ev['name']}.")
    return redirect(f"/guests/{cur.lastrowid}")


@route("GET", "/guests/export.csv")
def export(req):
    con = db()
    ev = event_row(con, cur_event(req))
    rows = con.execute("SELECT * FROM guests WHERE event_id=? AND kind<>'staff' AND status='Attending' ORDER BY name", (ev["id"],)).fetchall()
    con.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Company", "Email", "Type"])
    for r in rows:
        w.writerow([r["name"], r["company"], r["email"], "Guest"])
        if (r["plus_one"] or "").strip():
            w.writerow([r["plus_one"].strip(), r["company"], "", f'Plus-one of {r["name"]}'])
    fn = re.sub(r"[^A-Za-z0-9]+", "_", ev["name"]).strip("_") + "_door_list.csv"
    return 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": f'attachment; filename="{fn}"'}, buf.getvalue().encode()


@route("GET", "/events")
def events(req):
    con = db()
    rows = con.execute("SELECT * FROM events ORDER BY date").fetchall()
    con.close()
    body = '<h1>Events</h1><table class="t"><tr><th>Event</th><th>Date</th><th>Venue</th><th class=n>Approved budget</th></tr>'
    body += "".join(f'<tr><td><a href="/events/{e["id"]}">{E(e["name"])}</a></td><td>{nice_date(e["date"])}</td><td>{E(e["venue"])}</td>'
                    f'<td class=n>{gbp(e["budget"])}</td></tr>' for e in rows)
    return page(req, "Events", body + "</table>", "events")


@route("GET", r"/events/(\d+)")
def event(req, eid):
    con = db()
    ev = event_row(con, eid)
    if not ev:
        con.close()
        return redirect("/events")
    hosts = con.execute("SELECT * FROM guests WHERE event_id=? AND kind='staff' ORDER BY name", (eid,)).fetchall()
    pos = con.execute("SELECT p.*, s.name sup FROM pos p JOIN suppliers s ON s.id=p.supplier_id WHERE p.event_id=? ORDER BY p.id", (eid,)).fetchall()
    body = (f'<p><a href="/events">&laquo; Events</a></p><h1>{E(ev["name"])}</h1><div class="card">{nice_date(ev["date"])}, {E(ev["time"])} · '
            f'{E(ev["venue"])}<br>{E(ev["description"])}</div><h2>Brightwater hosts ({len(hosts)})</h2>'
            '<table class="t"><tr><th>Name</th><th>Role</th><th>Main course</th><th>Dietary / drinks</th></tr>')
    for h in hosts:
        body += f'<tr><td>{E(h["name"])}</td><td>{E(h["company"])}</td><td>{E(h["main"])}</td><td>{E(h["dietary"])}</td></tr>'
    body += '</table><h2>Purchase orders charged to this event</h2><table class="t"><tr><th>PO</th><th>Supplier</th><th>Status</th><th class=n>Total</th></tr>'
    committed = Decimal("0")
    for p in pos:
        tot = po_totals(con, p)[3]
        committed += tot if p["status"] == "submitted" else 0
        body += f'<tr><td><a href="/po/{p["id"]}">{E(p["number"])}</a></td><td>{E(p["sup"])}</td><td>{badge(p["status"])}</td><td class=n>{gbp(tot)}</td></tr>'
    con.close()
    body += (f'<tr class=tot><td colspan=3>Submitted orders</td><td class=n>{gbp(committed)}</td></tr></table>'
             f'<p class=muted>Approved budget {gbp(ev["budget"])} (the full budget sheet is kept by the office manager).</p>')
    return page(req, ev["name"], body, "events")


# ---------------------------------------------------------------- purchasing
@route("GET", "/purchasing")
def purchasing(req):
    if "scope" in req.q:
        req.set("po_scope", req.q["scope"])
    scope = req.get("po_scope", "event")
    con = db()
    ev = event_row(con, cur_event(req))
    rows = con.execute("SELECT p.*, s.name sup, e.name ev FROM pos p JOIN suppliers s ON s.id=p.supplier_id JOIN events e ON e.id=p.event_id "
                       "ORDER BY p.id DESC").fetchall()
    rows = [r for r in rows if scope == "all" or r["event_id"] == ev["id"]]
    body = (f'<h1>Purchase orders <span class="muted">· {"all events" if scope == "all" else E(ev["name"])}</span></h1>'
            f'<div class="filters"><a href="/purchasing?scope=event">This event</a> · <a href="/purchasing?scope=all">All events</a>'
            '<div style="margin-left:auto"><a href="/po/new">+ New purchase order</a></div></div><table class="t"><tr><th>PO</th>'
            '<th>Supplier</th><th>Charged to</th><th>Created</th><th>Status</th><th class=n>Total</th></tr>')
    for r in rows:
        body += (f'<tr><td><a href="/po/{r["id"]}">{E(r["number"])}</a></td><td>{E(r["sup"])}</td><td>{E(r["ev"])}</td>'
                 f'<td>{E(r["created_by"])} {E(r["created_at"][:10])}</td><td>{badge(r["status"])}</td><td class=n>{gbp(po_totals(con, r)[3])}</td></tr>')
    if not rows:
        body += '<tr><td colspan=6 class=muted>No purchase orders.</td></tr>'
    con.close()
    return page(req, "Purchasing", body + "</table>", "purchasing")


@route("GET", "/po/new")
def new_po_form(req):
    con = db()
    sups = con.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    evs = con.execute("SELECT id, name FROM events ORDER BY date").fetchall()
    con.close()
    body = ('<p><a href="/purchasing">&laquo; Purchasing</a></p><h1>New purchase order</h1><div class="card" style="max-width:560px">'
            '<form method=post action="/po/new"><label>Supplier</label><select name=supplier_id>' + options([(s["id"], s["name"]) for s in sups], "")
            + '</select><label>Charge to event</label><select name=event_id>' + options([(e["id"], e["name"]) for e in evs], cur_event(req))
            + '</select><label>Notes for the supplier</label><textarea name=notes rows=3 style="width:100%"></textarea>'
              '<p><button>Create draft</button></p></form></div>')
    return page(req, "New PO", body, "purchasing")


@route("POST", "/po/new")
def new_po(req):
    con = db()
    if not event_row(con, req.form.get("event_id", "0")) or not con.execute("SELECT 1 FROM suppliers WHERE id=?", (req.form.get("supplier_id", "0"),)).fetchone():
        con.close()
        req.flash("Choose a supplier and an event.", "err")
        return redirect("/po/new")
    n = con.execute("SELECT MAX(id) m FROM pos").fetchone()["m"] or 0
    cur = con.execute("INSERT INTO pos(number, supplier_id, event_id, status, notes, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
                      (f"PO-2026-{141 + n:04d}", int(req.form["supplier_id"]), int(req.form["event_id"]), "draft",
                       req.form.get("notes", ""), req.user["username"], now()))
    audit(con, req, "PO created", f"PO-2026-{141 + n:04d}")
    con.commit()
    con.close()
    return redirect(f"/po/{cur.lastrowid}")


@route("GET", r"/po/(\d+)")
def po(req, pid):
    con = db()
    p = con.execute("SELECT p.*, s.name sup, s.service_pct, e.name ev FROM pos p JOIN suppliers s ON s.id=p.supplier_id "
                    "JOIN events e ON e.id=p.event_id WHERE p.id=?", (pid,)).fetchone()
    if not p:
        con.close()
        return redirect("/purchasing")
    lines = con.execute("SELECT l.*, c.code, c.name, c.unit, c.price FROM po_lines l JOIN catalogue c ON c.id=l.item_id WHERE l.po_id=? ORDER BY c.code", (pid,)).fetchall()
    cat = con.execute("SELECT * FROM catalogue WHERE supplier_id=? ORDER BY code", (p["supplier_id"],)).fetchall()
    evs = con.execute("SELECT id, name FROM events ORDER BY date").fetchall()
    sub, svc, vat, tot = po_totals(con, p)
    con.close()
    draft = p["status"] == "draft"
    body = (f'<p><a href="/purchasing">&laquo; Purchasing</a></p><h1>{E(p["number"])} {badge(p["status"])}</h1><div class="two wide"><div>'
            f'<div class="card"><b>{E(p["sup"])}</b> · charged to <b>{E(p["ev"])}</b><br><span class=muted>created by {E(p["created_by"])} '
            f'{E(p["created_at"])}{" · submitted " + E(p["submitted_at"]) if p["submitted_at"] else ""}</span>'
            f'<p>{E(p["notes"])}</p></div><table class="t"><tr><th>Code</th><th>Item</th><th class=n>Unit price</th><th class=n>Qty</th><th class=n>Amount</th><th></th></tr>')
    for ln in lines:
        qty = (f'<form class=qty method=post action="/po/{pid}/lines/{ln["id"]}"><input type=number name=qty min=0 value="{ln["qty"]}" '
               'style="width:70px"> <button class=ghost>Update</button></form>') if draft else ln["qty"]
        rm = (f'<form class=inline method=post action="/po/{pid}/lines/{ln["id"]}"><input type=hidden name=qty value=0>'
              '<button class=ghost>Remove</button></form>') if draft else ""
        body += (f'<tr><td class=nw>{E(ln["code"])}</td><td>{E(ln["name"])} <span class=muted>/{E(ln["unit"])}</span></td><td class=n>{gbp(ln["price"])}</td>'
                 f'<td class=n>{qty}</td><td class=n>{gbp(money(ln["price"]) * ln["qty"])}</td><td>{rm}</td></tr>')
    body += (f'<tr><td colspan=4 class=n>Subtotal</td><td class=n>{gbp(sub)}</td><td></td></tr>'
             f'<tr><td colspan=4 class=n>Service charge {p["service_pct"]:g}%</td><td class=n>{gbp(svc)}</td><td></td></tr>'
             f'<tr><td colspan=4 class=n>VAT 20%</td><td class=n>{gbp(vat)}</td><td></td></tr>'
             f'<tr class=tot><td colspan=4 class=n>Order total</td><td class=n>{gbp(tot)}</td><td></td></tr></table></div><div>')
    if draft:
        body += (f'<div class="card"><h2 style="margin-top:0">Add a line</h2><form method=post action="/po/{pid}/lines"><label>Item</label>'
                 '<select name=item_id>' + options([(c["id"], f'{c["code"]} {c["name"]} ({gbp(c["price"])}/{c["unit"]})') for c in cat], "")
                 + '</select><label>Quantity</label><input type=number name=qty min=1 value=1 style="width:90px"> <button>Add</button></form></div>'
                 f'<div class="card"><form method=post action="/po/{pid}/header"><label>Charge to event</label><select name=event_id>'
                 + options([(e["id"], e["name"]) for e in evs], p["event_id"]) +
                 f'</select><label>Notes for the supplier</label><textarea name=notes rows=3 style="width:100%">{E(p["notes"])}</textarea>'
                 '<p><button class=ghost>Save details</button></p></form>'
                 f'<form method=post action="/po/{pid}/submit" onsubmit="return confirm(\'Submit this order to the supplier?\')">'
                 '<button>Submit order</button></form></div>')
    if p["status"] != "cancelled":
        body += (f'<form method=post action="/po/{pid}/cancel" onsubmit="return confirm(\'Cancel this purchase order?\')">'
                 '<button class=danger>Cancel order</button></form>')
    return page(req, p["number"], body + "</div></div>", "purchasing")


def _po_for_edit(con, req, pid):
    p = con.execute("SELECT * FROM pos WHERE id=?", (pid,)).fetchone()
    if not p or p["status"] != "draft":
        req.flash("Only draft orders can be changed.", "err")
        return None
    return p


@route("POST", r"/po/(\d+)/lines")
def add_line(req, pid):
    con = db()
    p = _po_for_edit(con, req, pid)
    qty = req.form.get("qty", "")
    item = con.execute("SELECT * FROM catalogue WHERE id=?", (req.form.get("item_id", "0"),)).fetchone()
    if p and item and item["supplier_id"] == p["supplier_id"] and qty.isdigit() and int(qty) > 0:
        old = con.execute("SELECT * FROM po_lines WHERE po_id=? AND item_id=?", (pid, item["id"])).fetchone()
        if old:
            con.execute("UPDATE po_lines SET qty=qty+? WHERE id=?", (int(qty), old["id"]))
        else:
            con.execute("INSERT INTO po_lines(po_id, item_id, qty) VALUES (?,?,?)", (pid, item["id"], int(qty)))
        audit(con, req, "PO line added", f'{p["number"]} {item["code"]} x{qty}')
        con.commit()
        req.flash(f'Added {qty} x {item["name"]}' + (" (added to the existing line)" if old else "") + ".")
    elif p:
        req.flash("Choose an item and a whole quantity of at least 1.", "err")
    con.close()
    return redirect(f"/po/{pid}")


@route("POST", r"/po/(\d+)/lines/(\d+)")
def update_line(req, pid, lid):
    con = db()
    p = _po_for_edit(con, req, pid)
    qty = req.form.get("qty", "")
    ln = con.execute("SELECT l.*, c.code FROM po_lines l JOIN catalogue c ON c.id=l.item_id WHERE l.id=? AND l.po_id=?", (lid, pid)).fetchone()
    if p and ln and qty.isdigit():
        if int(qty) == 0:
            con.execute("DELETE FROM po_lines WHERE id=?", (lid,))
        else:
            con.execute("UPDATE po_lines SET qty=? WHERE id=?", (int(qty), lid))
        audit(con, req, "PO line changed", f'{p["number"]} {ln["code"]} -> {qty}')
        con.commit()
    con.close()
    return redirect(f"/po/{pid}")


@route("POST", r"/po/(\d+)/header")
def po_header(req, pid):
    con = db()
    p = _po_for_edit(con, req, pid)
    if p and event_row(con, req.form.get("event_id", "0")):
        con.execute("UPDATE pos SET event_id=?, notes=? WHERE id=?", (int(req.form["event_id"]), req.form.get("notes", ""), pid))
        audit(con, req, "PO details changed", p["number"])
        con.commit()
        req.flash("Order details saved.")
    con.close()
    return redirect(f"/po/{pid}")


@route("POST", r"/po/(\d+)/submit")
def submit_po(req, pid):
    con = db()
    p = _po_for_edit(con, req, pid)
    if p and not con.execute("SELECT 1 FROM po_lines WHERE po_id=?", (pid,)).fetchone():
        req.flash("Add at least one line before submitting.", "err")
    elif p:
        con.execute("UPDATE pos SET status='submitted', submitted_at=? WHERE id=?", (now(), pid))
        audit(con, req, "PO submitted", f'{p["number"]} {gbp(po_totals(con, p)[3])}')
        con.commit()
        req.flash(f'{p["number"]} submitted to the supplier.')
    con.close()
    return redirect(f"/po/{pid}")


@route("POST", r"/po/(\d+)/cancel")
def cancel_po(req, pid):
    con = db()
    p = con.execute("SELECT * FROM pos WHERE id=?", (pid,)).fetchone()
    if p and p["status"] != "cancelled":
        con.execute("UPDATE pos SET status='cancelled' WHERE id=?", (pid,))
        audit(con, req, "PO cancelled", p["number"])
        con.commit()
        req.flash(f'{p["number"]} cancelled.')
    con.close()
    return redirect(f"/po/{pid}")


@route("GET", "/suppliers")
def suppliers(req):
    con = db()
    rows = con.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    con.close()
    body = '<h1>Approved suppliers</h1><table class="t"><tr><th>Supplier</th><th>Category</th><th>Contact</th><th class=n>Service charge</th></tr>'
    body += "".join(f'<tr><td><a href="/suppliers/{s["id"]}">{E(s["name"])}</a></td><td>{E(s["category"])}</td><td>{E(s["contact"])} · '
                    f'{E(s["email"])}</td><td class=n>{s["service_pct"]:g}%</td></tr>' for s in rows)
    return page(req, "Suppliers", body + "</table>", "suppliers")


@route("GET", r"/suppliers/(\d+)")
def supplier(req, sid):
    con = db()
    s = con.execute("SELECT * FROM suppliers WHERE id=?", (sid,)).fetchone()
    if not s:
        con.close()
        return redirect("/suppliers")
    cat = con.execute("SELECT * FROM catalogue WHERE supplier_id=? ORDER BY code", (sid,)).fetchall()
    con.close()
    body = (f'<p><a href="/suppliers">&laquo; Suppliers</a></p><h1>{E(s["name"])}</h1><div class="card">{E(s["contact"])} · {E(s["email"])}<br>'
            f'{E(s["terms"])}</div><table class="t"><tr><th>Code</th><th>Item</th><th>Unit</th><th class=n>Price (ex VAT)</th></tr>')
    body += "".join(f'<tr><td>{E(c["code"])}</td><td>{E(c["name"])}<br><span class=muted>{E(c["description"])}</span></td>'
                    f'<td>{E(c["unit"])}</td><td class=n>{gbp(c["price"])}</td></tr>' for c in cat)
    return page(req, s["name"], body + "</table>", "suppliers")


@route("GET", "/activity")
def activity(req):
    pg = int(req.q["page"]) if req.q.get("page", "").isdigit() else 1
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
    server_version = "BrightwaterHub/1.8"

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
    ap.add_argument("--port", type=int, default=8123)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
