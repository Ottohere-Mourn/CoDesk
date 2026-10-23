#!/usr/bin/env python3
"""Ledgerline - the bookkeeping intranet of Harbour & Pine Coffee Roasters Ltd (paraGUI pair x1).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Sales invoices, customer receipts, monthly reports and board-pack uploads. The period selector in the header and
the list filters are remembered per login session (like most small accounting tools do).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import secrets
import sqlite3
import urllib.parse
from email import policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP, COOKIE = "Ledgerline", "ledgerline_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
PAGE = 15
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
    v = float(v or 0)
    return ("-" if v < -0.004 else "") + f"£{abs(v):,.2f}"


def nice_date(s):
    try:
        return dt.date.fromisoformat(s).strftime("%d %b %Y")
    except Exception:
        return s or ""


def setting(con, key):
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else ""


def periods():
    return [("2026-07", "July 2026"), ("2026-08", "August 2026"), ("2026-09", "September 2026"),
            ("2026-10", "October 2026"), ("all", "All periods")]


def period_label(p):
    return dict(periods()).get(p, p)


def parse_amount(s):
    s = re.sub(r"[£,\s]", "", s or "")
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return v if v > 0 else None


def parse_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


class Req:
    def __init__(self, h, method):
        self.h, self.method = h, method
        u = urllib.parse.urlsplit(h.path)
        self.path = u.path
        self.q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
        self.form, self.files = {}, {}
        if method == "POST":
            n = int(h.headers.get("Content-Length") or 0)
            body = h.rfile.read(n) if n else b""
            ctype = h.headers.get("Content-Type", "")
            if ctype.startswith("multipart/form-data"):
                msg = BytesParser(policy=policy.default).parsebytes(
                    b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
                for part in msg.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    if part.get_filename() is not None:
                        self.files[name] = (part.get_filename(), part.get_payload(decode=True) or b"")
                    else:
                        self.form[name] = (part.get_payload(decode=True) or b"").decode("utf8", "replace")
            else:
                self.form = {k: v[-1] for k, v in urllib.parse.parse_qs(body.decode("utf8", "replace"),
                                                                         keep_blank_values=True).items()}
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
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#f3f1ec;color:#222}
a{color:#7a4b1e;text-decoration:none}a:hover{text-decoration:underline}
header{background:#3b2a1e;color:#f4e9dc;display:flex;align-items:center;gap:22px;padding:0 22px;height:56px}
header .brand{font-weight:700;font-size:19px;letter-spacing:.3px}header .brand small{font-weight:400;opacity:.75;margin-left:8px;font-size:13px}
header nav a{color:#f4e9dc;margin-right:16px;font-size:14px}header nav a.on{border-bottom:2px solid #e2a25b;padding-bottom:3px}
header form{margin-left:auto;display:flex;gap:6px;align-items:center;font-size:13px}
header select{padding:3px 6px}header .who{font-size:13px;opacity:.9}header .who a{color:#ffd9a8}
main{max-width:1180px;margin:22px auto;padding:0 22px}h1{font-size:23px;margin:4px 0 16px}h2{font-size:17px;margin:22px 0 10px}
.card{background:#fff;border:1px solid #ddd5c8;border-radius:6px;padding:16px 18px;margin-bottom:16px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #ddd5c8}
table.t th{background:#efe7db;text-align:left;font-size:13px;padding:7px 9px;border-bottom:1px solid #d7ccbc}
table.t td{padding:6px 9px;border-bottom:1px solid #eee6da;font-size:14px}table.t tr:hover td{background:#fbf7f0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tr.tot td{font-weight:700;background:#f7f1e8}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.b-Paid{background:#dcefdc;color:#25632a}.b-Open{background:#e6eefa;color:#234f8f}.b-Overdue{background:#fbe0dc;color:#9b2a1c}
.b-Partpaid{background:#fff0cc;color:#8a5a00}.b-Void{background:#e8e8e8;color:#666}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#e1f3e1;border:1px solid #9ccf9c}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}
form.inline{display:inline}label{display:block;font-size:13px;color:#555;margin:8px 0 3px}
input[type=text],input[type=password],input[type=date],select,textarea{padding:6px 8px;border:1px solid #c9bfb0;border-radius:4px;font-size:14px}
button,.btn{background:#7a4b1e;color:#fff;border:0;border-radius:4px;padding:7px 14px;font-size:14px;cursor:pointer}
button.ghost{background:#fff;color:#7a4b1e;border:1px solid #c9bfb0}button.danger{background:#a8321f}
.filters{display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;flex-wrap:wrap}.filters label{margin:0 0 3px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.kpi{font-size:24px;font-weight:700}.muted{color:#777;font-size:13px}
.pager{margin:10px 0;font-size:14px}.pager a,.pager span{margin-right:8px}
.login{max-width:380px;margin:90px auto}.two{display:grid;grid-template-columns:1.4fr 1fr;gap:18px}
"""


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.state.pop("flash", []))
    if flashes:
        req._dirty = True
    if not req.user:
        return f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>{flashes}{body}</body></html>"
    links = [("dashboard", "/", "Dashboard"), ("invoices", "/invoices", "Invoices"), ("customers", "/customers", "Customers"),
             ("receipts", "/receipts", "Receipts"), ("reports", "/reports", "Reports"), ("boardpacks", "/boardpacks", "Board packs"),
             ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    cur = req.get("period", "2026-10")
    opts = "".join(f'<option value="{p}"{" selected" if p == cur else ""}>{E(lbl)}</option>' for p, lbl in periods())
    return (f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
            f'<header><div class="brand">{APP}<small>Harbour &amp; Pine Coffee Roasters Ltd</small></div><nav>{navh}</nav>'
            f'<form method=post action="/period"><input type=hidden name=next value="{E(req.h.path)}">Period '
            f'<select name=period onchange="this.form.submit()">{opts}</select><noscript><button>Set</button></noscript></form>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header>'
            f"<main>{flashes}{body}</main></body></html>")


def redirect(url):
    return 303, {"Location": url}, b""


def page(req, title, body, nav=""):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, layout(req, title, body, nav).encode()


# ---------------------------------------------------------------- data access
INV_SQL = """SELECT i.*, c.name AS customer, c.id AS cid,
    COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id AND p.deleted=0), 0) AS paid
    FROM invoices i JOIN customers c ON c.id=i.customer_id"""


def status_of(r, today):
    if r["void"]:
        return "Void"
    if r["paid"] >= r["gross"] - 0.005:
        return "Paid"
    if r["paid"] > 0.004:
        return "Part paid"
    return "Overdue" if r["due_date"] < today else "Open"


def badge(s):
    return f'<span class="badge b-{s.replace(" ", "")}">{s}</span>'


def in_period(datestr, p):
    return p == "all" or (datestr or "").startswith(p)


# ---------------------------------------------------------------- auth
@route("GET", "/login")
def login_form(req):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>Ledgerline</h1><p class="muted">Harbour &amp; Pine Coffee Roasters Ltd · finance intranet</p>'
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
    biz = setting(con, "business_date")
    con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], now(), json.dumps({"period": biz[:7]})))
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


@route("POST", "/period")
def set_period(req):
    p = req.form.get("period", "")
    if p in dict(periods()):
        req.set("period", p)
        req.set("inv_page", 1)
    nxt = req.form.get("next", "/")
    return redirect(nxt if nxt.startswith("/") else "/")


# ---------------------------------------------------------------- pages
@route("GET", "/")
def dashboard(req):
    con = db()
    today = setting(con, "business_date")
    rows = [dict(r) for r in con.execute(INV_SQL)]
    for r in rows:
        r["status"] = status_of(r, today)
    open_rows = [r for r in rows if r["status"] in ("Open", "Overdue", "Part paid")]
    ar = sum(r["gross"] - r["paid"] for r in open_rows)
    overdue = [r for r in open_rows if r["status"] == "Overdue" or (r["status"] == "Part paid" and r["due_date"] < today)]
    p = req.get("period", "2026-10")
    net = sum(r["net"] for r in rows if not r["void"] and in_period(r["issue_date"], p))
    rec = con.execute("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE deleted=0 AND date LIKE ?",
                      ((p if p != "all" else "") + "%",)).fetchone()["s"]
    acts = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 8").fetchall()
    con.close()
    body = (f'<h1>Dashboard</h1><p class="muted">Business date {nice_date(today)} · period shown: {E(period_label(p))}</p>'
            f'<div class="grid"><div class="card"><div class="muted">Receivables outstanding</div><div class="kpi">{gbp(ar)}</div></div>'
            f'<div class="card"><div class="muted">Overdue invoices</div><div class="kpi">{len(overdue)}</div></div>'
            f'<div class="card"><div class="muted">Net sales invoiced ({E(period_label(p))})</div><div class="kpi">{gbp(net)}</div></div>'
            f'<div class="card"><div class="muted">Receipts recorded ({E(period_label(p))})</div><div class="kpi">{gbp(rec)}</div></div></div>'
            '<h2>Recent activity</h2><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
            + "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in acts)
            + "</table>")
    return page(req, "Dashboard", body, "dashboard")


@route("GET", "/invoices")
def invoices(req):
    for key in ("status", "q"):
        if key in req.q:
            req.set("inv_" + key, req.q[key].strip())
            req.set("inv_page", 1)
    if "page" in req.q and req.q["page"].isdigit():
        req.set("inv_page", int(req.q["page"]))
    p, st, q = req.get("period", "2026-10"), req.get("inv_status", ""), req.get("inv_q", "")
    con = db()
    today = setting(con, "business_date")
    rows = []
    for r in con.execute(INV_SQL + " ORDER BY i.number DESC"):
        r = dict(r)
        r["status"] = status_of(r, today)
        if not in_period(r["issue_date"], p):
            continue
        if st == "unpaid" and r["status"] not in ("Open", "Overdue", "Part paid"):
            continue
        if st and st != "unpaid" and r["status"] != st:
            continue
        if q and q.lower() not in (r["number"] + " " + r["customer"] + " " + (r["reference"] or "")).lower():
            continue
        rows.append(r)
    con.close()
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = min(max(1, int(req.get("inv_page", 1))), pages)
    sts = [("", "All statuses"), ("unpaid", "Unpaid (open, overdue, part paid)"), ("Open", "Open"), ("Overdue", "Overdue"),
           ("Part paid", "Part paid"), ("Paid", "Paid"), ("Void", "Void")]
    sel = "".join(f'<option value="{E(v)}"{" selected" if v == st else ""}>{E(t)}</option>' for v, t in sts)
    body = (f'<h1>Sales invoices <span class="muted">· {E(period_label(p))}</span></h1>'
            f'<form class="filters" method=get action="/invoices"><div><label>Status</label><select name=status>{sel}</select></div>'
            f'<div><label>Search number / customer / reference</label><input type=text name=q value="{E(q)}" style="width:280px"></div>'
            '<div><button>Filter</button></div><div><a class="muted" href="/invoices?status=&amp;q=">Clear filters</a></div></form>'
            '<table class="t"><tr><th>Number</th><th>Customer</th><th>Issued</th><th>Due</th><th>Channel</th>'
            '<th class=n>Total</th><th class=n>Paid</th><th class=n>Outstanding</th><th>Status</th></tr>')
    for r in rows[(pg - 1) * PAGE: pg * PAGE]:
        out = 0 if r["void"] else r["gross"] - r["paid"]
        body += (f'<tr><td><a href="/invoices/{E(r["number"])}">{E(r["number"])}</a></td><td>{E(r["customer"])}</td>'
                 f'<td>{nice_date(r["issue_date"])}</td><td>{nice_date(r["due_date"])}</td><td>{E(r["channel"])}</td>'
                 f'<td class=n>{gbp(r["gross"])}</td><td class=n>{gbp(r["paid"])}</td><td class=n>{gbp(out)}</td><td>{badge(r["status"])}</td></tr>')
    if not rows:
        body += '<tr><td colspan=9 class="muted">No invoices match the period and filters.</td></tr>'
    body += f'</table><div class="pager">{len(rows)} invoices · page {pg} of {pages} &nbsp; '
    if pg > 1:
        body += f'<a href="/invoices?page={pg - 1}">&laquo; Previous</a>'
    if pg < pages:
        body += f'<a href="/invoices?page={pg + 1}">Next &raquo;</a>'
    body += "</div>"
    return page(req, "Invoices", body, "invoices")


@route("GET", r"/invoices/(INV-\d{4}-\d{4})")
def invoice(req, number):
    con = db()
    today = setting(con, "business_date")
    r = con.execute(INV_SQL + " WHERE i.number=?", (number,)).fetchone()
    if not r:
        con.close()
        return 404, {"Content-Type": "text/html"}, layout(req, "Not found", "<h1>Invoice not found</h1>").encode()
    r = dict(r)
    r["status"] = status_of(r, today)
    lines = con.execute("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY id", (r["id"],)).fetchall()
    pays = con.execute("SELECT * FROM payments WHERE invoice_id=? AND deleted=0 ORDER BY date, id", (r["id"],)).fetchall()
    cust = con.execute("SELECT * FROM customers WHERE id=?", (r["cid"],)).fetchone()
    others = [dict(o) for o in con.execute(INV_SQL + " WHERE c.id=? AND i.id<>? ORDER BY i.number", (r["cid"], r["id"]))]
    con.close()
    outstanding = 0 if r["void"] else r["gross"] - r["paid"]
    body = (f'<p><a href="/invoices">&laquo; Invoices</a></p><h1>{E(number)} {badge(r["status"])}</h1><div class="two"><div>'
            f'<div class="card"><b><a href="/customers/{cust["id"]}">{E(cust["name"])}</a></b><br><span class="muted">{E(cust["address"])}</span>'
            f'<p>Issued {nice_date(r["issue_date"])} · due {nice_date(r["due_date"])} · channel {E(r["channel"])}<br>'
            f'Reference: {E(r["reference"] or "-")}</p>'
            '<table class="t"><tr><th>Description</th><th class=n>Qty</th><th class=n>Unit price</th><th class=n>Net</th></tr>'
            + "".join(f'<tr><td>{E(ln["description"])}</td><td class=n>{ln["qty"]:g}</td><td class=n>{gbp(ln["unit_price"])}</td>'
                      f'<td class=n>{gbp(ln["net"])}</td></tr>' for ln in lines)
            + f'<tr><td colspan=3 class=n>Net</td><td class=n>{gbp(r["net"])}</td></tr>'
              f'<tr><td colspan=3 class=n>VAT 20%</td><td class=n>{gbp(r["vat"])}</td></tr>'
              f'<tr class=tot><td colspan=3 class=n>Total</td><td class=n>{gbp(r["gross"])}</td></tr></table>'
              f'{"<p class=muted>" + E(r["notes"]) + "</p>" if r["notes"] else ""}</div>'
              '<h2>Receipts against this invoice</h2><table class="t"><tr><th>Date</th><th class=n>Amount</th><th>Method</th>'
              '<th>Bank reference</th><th>Recorded by</th><th></th></tr>')
    for py in pays:
        body += (f'<tr><td>{nice_date(py["date"])}</td><td class=n>{gbp(py["amount"])}</td><td>{E(py["method"])}</td>'
                 f'<td>{E(py["reference"])}</td><td>{E(py["created_by"])} <span class=muted>{E(py["created_at"])}</span></td>'
                 f'<td><form class=inline method=post action="/payments/{py["id"]}/delete" onsubmit="return confirm(\'Delete this receipt?\')">'
                 '<button class="ghost">Delete</button></form></td></tr>')
    if not pays:
        body += '<tr><td colspan=6 class="muted">No receipts recorded.</td></tr>'
    body += (f'<tr class=tot><td>Outstanding</td><td class=n>{gbp(outstanding)}</td><td colspan=4></td></tr></table></div><div>')
    if not r["void"] and outstanding > 0.004:
        body += ('<div class="card"><h2 style="margin-top:0">Record a receipt</h2>'
                 f'<form method=post action="/invoices/{E(number)}/payments"><label>Date received</label><input type=date name=date required>'
                 f'<label>Amount (£)</label><input type=text name=amount required placeholder="{outstanding:.2f}">'
                 '<label>Method</label><select name=method><option>Bank transfer</option><option>Card</option><option>Cheque</option>'
                 '<option>Cash</option></select><label>Bank reference</label><input type=text name=reference style="width:100%">'
                 '<p><button>Save receipt</button></p></form></div>')
    body += '<div class="card"><h2 style="margin-top:0">Other invoices for this customer</h2><table class="t"><tr><th>Number</th><th>Issued</th><th class=n>Total</th><th>Status</th></tr>'
    for o in others:
        body += (f'<tr><td><a href="/invoices/{E(o["number"])}">{E(o["number"])}</a></td><td>{nice_date(o["issue_date"])}</td>'
                 f'<td class=n>{gbp(o["gross"])}</td><td>{badge(status_of(o, today))}</td></tr>')
    body += "</table></div></div></div>"
    return page(req, number, body, "invoices")


@route("POST", r"/invoices/(INV-\d{4}-\d{4})/payments")
def add_payment(req, number):
    con = db()
    r = con.execute(INV_SQL + " WHERE i.number=?", (number,)).fetchone()
    date, amount = parse_date(req.form.get("date")), parse_amount(req.form.get("amount"))
    back = redirect(f"/invoices/{number}")
    if not r or r["void"]:
        req.flash("This invoice cannot take receipts.", "err")
    elif not date or not ("2026-01-01" <= date <= setting(con, "business_date")):
        req.flash("Enter the date the money was received (not in the future).", "err")
    elif amount is None:
        req.flash("Enter a positive amount, e.g. 540.00.", "err")
    elif amount > r["gross"] - r["paid"] + 0.005:
        req.flash(f"{gbp(amount)} is more than the {gbp(r['gross'] - r['paid'])} outstanding on {number}. "
                  "Overpayments must be raised with the accountant.", "err")
    else:
        con.execute("INSERT INTO payments(invoice_id, date, amount, method, reference, created_by, created_at, deleted) "
                    "VALUES (?,?,?,?,?,?,?,0)", (r["id"], date, amount, req.form.get("method", "Bank transfer"),
                                                 req.form.get("reference", "").strip(), req.user["username"], now()))
        audit(con, req, "receipt recorded", f"{number} {gbp(amount)} received {date}")
        con.commit()
        req.flash(f"Receipt of {gbp(amount)} recorded against {number}.")
    con.close()
    return back


@route("POST", r"/payments/(\d+)/delete")
def delete_payment(req, pid):
    con = db()
    p = con.execute("SELECT p.*, i.number FROM payments p JOIN invoices i ON i.id=p.invoice_id WHERE p.id=?", (pid,)).fetchone()
    if p and not p["deleted"]:
        con.execute("UPDATE payments SET deleted=1 WHERE id=?", (pid,))
        audit(con, req, "receipt deleted", f"{p['number']} {gbp(p['amount'])} received {p['date']}")
        con.commit()
        req.flash(f"Receipt of {gbp(p['amount'])} on {p['number']} deleted.")
    con.close()
    return redirect(f"/invoices/{p['number']}" if p else "/invoices")


@route("GET", "/customers")
def customers(req):
    if "q" in req.q:
        req.set("cust_q", req.q["q"].strip())
    q = req.get("cust_q", "")
    con = db()
    today = setting(con, "business_date")
    rows = con.execute("SELECT * FROM customers ORDER BY name").fetchall()
    bal = {}
    for r in con.execute(INV_SQL):
        if not r["void"]:
            bal.setdefault(r["cid"], [0, 0])
            bal[r["cid"]][0] += r["gross"] - r["paid"]
            bal[r["cid"]][1] += status_of(r, today) == "Overdue"
    con.close()
    body = ('<h1>Customers</h1><form class="filters" method=get><div><label>Search</label>'
            f'<input type=text name=q value="{E(q)}"></div><div><button>Search</button></div></form>'
            '<table class="t"><tr><th>Name</th><th>Channel</th><th>Contact</th><th>Email</th><th class=n>Balance</th><th class=n>Overdue</th></tr>')
    for c in rows:
        if q and q.lower() not in (c["name"] + " " + c["contact"] + " " + c["email"]).lower():
            continue
        b = bal.get(c["id"], [0, 0])
        body += (f'<tr><td><a href="/customers/{c["id"]}">{E(c["name"])}</a></td><td>{E(c["channel"])}</td><td>{E(c["contact"])}</td>'
                 f'<td>{E(c["email"])}</td><td class=n>{gbp(b[0])}</td><td class=n>{b[1]}</td></tr>')
    return page(req, "Customers", body + "</table>", "customers")


@route("GET", r"/customers/(\d+)")
def customer(req, cid):
    con = db()
    today = setting(con, "business_date")
    c = con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    if not c:
        con.close()
        return redirect("/customers")
    rows = [dict(r) for r in con.execute(INV_SQL + " WHERE c.id=? ORDER BY i.number DESC", (cid,))]
    con.close()
    body = (f'<p><a href="/customers">&laquo; Customers</a></p><h1>{E(c["name"])}</h1><div class="card">{E(c["address"])}<br>'
            f'Contact: {E(c["contact"])} · {E(c["email"])} · {E(c["phone"])}<br>Payment terms: {c["terms"]} days · channel {E(c["channel"])}</div>'
            '<table class="t"><tr><th>Number</th><th>Issued</th><th>Due</th><th>Reference</th><th class=n>Total</th><th class=n>Paid</th><th>Status</th></tr>')
    for r in rows:
        body += (f'<tr><td><a href="/invoices/{E(r["number"])}">{E(r["number"])}</a></td><td>{nice_date(r["issue_date"])}</td>'
                 f'<td>{nice_date(r["due_date"])}</td><td>{E(r["reference"])}</td><td class=n>{gbp(r["gross"])}</td>'
                 f'<td class=n>{gbp(r["paid"])}</td><td>{badge(status_of(r, today))}</td></tr>')
    return page(req, c["name"], body + "</table>", "customers")


@route("GET", "/receipts")
def receipts(req):
    p = req.get("period", "2026-10")
    con = db()
    rows = con.execute("SELECT p.*, i.number, c.name FROM payments p JOIN invoices i ON i.id=p.invoice_id "
                       "JOIN customers c ON c.id=i.customer_id WHERE p.deleted=0 ORDER BY p.date DESC, p.id DESC").fetchall()
    con.close()
    rows = [r for r in rows if in_period(r["date"], p)]
    body = (f'<h1>Receipts <span class="muted">· received in {E(period_label(p))}</span></h1><table class="t"><tr><th>Date</th>'
            '<th>Invoice</th><th>Customer</th><th class=n>Amount</th><th>Method</th><th>Bank reference</th><th>Recorded by</th></tr>')
    for r in rows:
        body += (f'<tr><td>{nice_date(r["date"])}</td><td><a href="/invoices/{E(r["number"])}">{E(r["number"])}</a></td><td>{E(r["name"])}</td>'
                 f'<td class=n>{gbp(r["amount"])}</td><td>{E(r["method"])}</td><td>{E(r["reference"])}</td><td>{E(r["created_by"])}</td></tr>')
    total = sum(r["amount"] for r in rows)
    body += f'<tr class=tot><td colspan=3>Total ({len(rows)} receipts)</td><td class=n>{gbp(total)}</td><td colspan=3></td></tr></table>'
    return page(req, "Receipts", body, "receipts")


@route("GET", "/reports")
def reports(req):
    p = req.get("period", "2026-10")
    con = db()
    rows = [dict(r) for r in con.execute(INV_SQL) if not r["void"] and in_period(r["issue_date"], p)]
    con.close()
    by_ch, by_c = {}, {}
    for r in rows:
        a = by_ch.setdefault(r["channel"], [0, 0.0, 0.0, 0.0])
        a[0] += 1
        a[1] += r["net"]
        a[2] += r["vat"]
        a[3] += r["gross"]
        b = by_c.setdefault(r["customer"], [0, 0.0])
        b[0] += 1
        b[1] += r["net"]
    body = (f'<h1>Sales summary <span class="muted">· {E(period_label(p))}</span></h1>'
            '<p class="muted">Revenue is recognised on the invoice date. Void invoices are excluded. Change the period in the header to '
            'see another month.</p><h2>Revenue by channel</h2><table class="t"><tr><th>Channel</th><th class=n>Invoices</th>'
            '<th class=n>Net revenue</th><th class=n>VAT</th><th class=n>Gross</th></tr>')
    tot = [0, 0.0, 0.0, 0.0]
    for ch in ("Wholesale", "Online shop", "Training & equipment"):
        a = by_ch.get(ch, [0, 0, 0, 0])
        tot = [x + y for x, y in zip(tot, a)]
        body += f'<tr><td>{E(ch)}</td><td class=n>{a[0]}</td><td class=n>{gbp(a[1])}</td><td class=n>{gbp(a[2])}</td><td class=n>{gbp(a[3])}</td></tr>'
    body += (f'<tr class=tot><td>Total</td><td class=n>{tot[0]}</td><td class=n>{gbp(tot[1])}</td><td class=n>{gbp(tot[2])}</td>'
             f'<td class=n>{gbp(tot[3])}</td></tr></table><h2>Net revenue by customer</h2><table class="t"><tr><th>#</th><th>Customer</th>'
             '<th class=n>Invoices</th><th class=n>Net revenue</th></tr>')
    for i, (name, (n, net)) in enumerate(sorted(by_c.items(), key=lambda kv: -kv[1][1]), 1):
        body += f'<tr><td>{i}</td><td>{E(name)}</td><td class=n>{n}</td><td class=n>{gbp(net)}</td></tr>'
    return page(req, "Reports", body + "</table>", "reports")


@route("GET", "/boardpacks")
def boardpacks(req):
    con = db()
    rows = con.execute("SELECT * FROM boardpacks WHERE deleted=0 ORDER BY period DESC, id DESC").fetchall()
    con.close()
    opts = "".join(f'<option value="{p}">{E(lbl)}</option>' for p, lbl in periods() if p != "all")
    body = ('<h1>Board packs</h1><p class="muted">Monthly management reports for the directors (PDF).</p><div class="two"><div>'
            '<table class="t"><tr><th>Period</th><th>Title</th><th>File</th><th class=n>Size</th><th>Uploaded</th><th></th></tr>')
    for r in rows:
        body += (f'<tr><td>{E(period_label(r["period"]))}</td><td>{E(r["title"])}</td><td><a href="/boardpacks/{r["id"]}/file">{E(r["filename"])}</a></td>'
                 f'<td class=n>{r["size"] // 1024} KB</td><td>{E(r["uploaded_by"])} <span class=muted>{E(r["uploaded_at"])}</span></td>'
                 f'<td><form class=inline method=post action="/boardpacks/{r["id"]}/delete" onsubmit="return confirm(\'Remove this board pack?\')">'
                 '<button class=ghost>Remove</button></form></td></tr>')
    if not rows:
        body += '<tr><td colspan=6 class=muted>No board packs yet.</td></tr>'
    body += ('</table></div><div class="card"><h2 style="margin-top:0">Upload a board pack</h2>'
             '<form method=post action="/boardpacks" enctype="multipart/form-data"><label>Period</label>'
             f'<select name=period>{opts}</select><label>Title</label><input type=text name=title style="width:100%">'
             '<label>PDF file</label><input type=file name=file accept="application/pdf,.pdf"><p><button>Upload</button></p></form></div></div>')
    return page(req, "Board packs", body, "boardpacks")


@route("POST", "/boardpacks")
def upload_boardpack(req):
    period, title = req.form.get("period", ""), req.form.get("title", "").strip()
    name, data = req.files.get("file", ("", b""))
    if period not in dict(periods()) or period == "all":
        req.flash("Choose the period.", "err")
    elif not title:
        req.flash("Give the board pack a title.", "err")
    elif not name or not data.startswith(b"%PDF-"):
        req.flash("Choose a PDF file to upload.", "err")
    elif len(data) > 20 * 1024 * 1024:
        req.flash("The file is larger than 20 MB.", "err")
    else:
        con = db()
        cur = con.execute("INSERT INTO boardpacks(period, title, filename, path, size, uploaded_by, uploaded_at, deleted) "
                          "VALUES (?,?,?,?,?,?,?,0)", (period, title, os.path.basename(name), "", len(data), req.user["username"], now()))
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(name))
        path = os.path.join(os.path.dirname(os.path.abspath(DB)), "uploads", f"{cur.lastrowid}_{safe}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
        con.execute("UPDATE boardpacks SET path=? WHERE id=?", (path, cur.lastrowid))
        audit(con, req, "board pack uploaded", f"{period} {title} ({os.path.basename(name)})")
        con.commit()
        con.close()
        req.flash(f"Uploaded {os.path.basename(name)} for {period_label(period)}.")
    return redirect("/boardpacks")


@route("GET", r"/boardpacks/(\d+)/file")
def boardpack_file(req, bid):
    con = db()
    r = con.execute("SELECT * FROM boardpacks WHERE id=?", (bid,)).fetchone()
    con.close()
    if not r or not r["path"] or not os.path.exists(r["path"]):
        return redirect("/boardpacks")
    return 200, {"Content-Type": "application/pdf", "Content-Disposition": f'inline; filename="{r["filename"]}"'}, open(r["path"], "rb").read()


@route("POST", r"/boardpacks/(\d+)/delete")
def delete_boardpack(req, bid):
    con = db()
    r = con.execute("SELECT * FROM boardpacks WHERE id=?", (bid,)).fetchone()
    if r:
        con.execute("UPDATE boardpacks SET deleted=1 WHERE id=?", (bid,))
        audit(con, req, "board pack removed", f"{r['period']} {r['title']}")
        con.commit()
    con.close()
    return redirect("/boardpacks")


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
    server_version = "Ledgerline/2.3"

    def log_message(self, fmt, *args):
        pass

    def handle_any(self, method, head=False):
        try:
            req = Req(self, method)
            for m, rx, fn in ROUTES:
                mt = rx.match(req.path)
                if m == method and mt:
                    if not req.user and req.path not in ("/login",):
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
    ap.add_argument("--port", type=int, default=8121)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
