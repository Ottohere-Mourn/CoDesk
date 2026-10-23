#!/usr/bin/env python3
"""HireDesk - the applicant tracking intranet of Fernleaf Analytics (paraGUI pair x2).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Requisitions, candidates, applications with a screening scorecard and stages, interview slots with bookings.
The requisition selector in the header and the pipeline filters are remembered per login session; the selector also
pre-selects the requisition in the "new candidate" and "add to requisition" forms.
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

APP, COOKIE = "HireDesk", "hiredesk_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
PAGE = 10
STAGES = ["Applied", "Phone screen", "Interview - to schedule", "Interview scheduled", "Offer", "Hired", "Rejected", "Withdrawn"]
CLOSED = ("Rejected", "Withdrawn", "Hired")
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


def nice_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10]).strftime("%d %b %Y")
    except Exception:
        return s or ""


def slot_label(s):
    try:
        t = dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
        return t.strftime("%a %d %b %Y, %H:%M")
    except Exception:
        return s


def reqs(con):
    return con.execute("SELECT * FROM requisitions ORDER BY code DESC").fetchall()


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
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#eef3ef;color:#1d2a24}
a{color:#1f6b4a;text-decoration:none}a:hover{text-decoration:underline}
header{background:#173f30;color:#e6f2ea;display:flex;align-items:center;gap:22px;padding:0 22px;height:56px}
header .brand{font-weight:700;font-size:19px}header .brand small{font-weight:400;opacity:.75;margin-left:8px;font-size:13px}
header nav a{color:#e6f2ea;margin-right:15px;font-size:14px}header nav a.on{border-bottom:2px solid #8fd6a8;padding-bottom:3px}
header form{margin-left:auto;display:flex;gap:6px;align-items:center;font-size:13px}header select{padding:3px 6px;max-width:320px}
header .who{font-size:13px;opacity:.9}header .who a{color:#b9f0cc}
main{max-width:1200px;margin:22px auto;padding:0 22px}h1{font-size:23px;margin:4px 0 16px}h2{font-size:17px;margin:20px 0 10px}
.card{background:#fff;border:1px solid #cfdcd3;border-radius:6px;padding:16px 18px;margin-bottom:16px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #cfdcd3}
table.t th{background:#e2ece5;text-align:left;font-size:13px;padding:7px 9px;border-bottom:1px solid #c5d5ca}
table.t td{padding:6px 9px;border-bottom:1px solid #e6eee8;font-size:14px}table.t tr:hover td{background:#f6faf7}
td.n,th.n{text-align:right}.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;background:#e6eaf2;color:#344}
.s-Phonescreen{background:#dbeefe;color:#1d4f86}.s-Interview-toschedule{background:#fff0cc;color:#7a5200}
.s-Interviewscheduled{background:#d8f2df;color:#1f6b3a}.s-Rejected{background:#fbe0dc;color:#9b2a1c}.s-Withdrawn{background:#ececec;color:#666}
.s-Offer,.s-Hired{background:#e8dcfb;color:#5b2d91}.free{color:#1f6b3a;font-weight:600}.booked{color:#7a5200}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#e1f3e1;border:1px solid #9ccf9c}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}label{display:block;font-size:13px;color:#4a5a52;margin:8px 0 3px}
input[type=text],input[type=password],input[type=email],select,textarea{padding:6px 8px;border:1px solid #b9cbbf;border-radius:4px;font-size:14px}
button{background:#1f6b4a;color:#fff;border:0;border-radius:4px;padding:7px 14px;font-size:14px;cursor:pointer}
button.ghost{background:#fff;color:#1f6b4a;border:1px solid #b9cbbf}.filters{display:flex;gap:10px;align-items:flex-end;margin-bottom:12px;flex-wrap:wrap}
.filters label{margin:0 0 3px}.muted{color:#6b7a72;font-size:13px}.pager{margin:10px 0;font-size:14px}.pager a{margin-right:8px}
.two{display:grid;grid-template-columns:1.3fr 1fr;gap:18px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.kpi{font-size:22px;font-weight:700}.login{max-width:380px;margin:90px auto}.sc td{padding:4px 8px}.inl{display:inline}
"""


def badge(stage):
    return f'<span class="badge s-{re.sub(r"[^A-Za-z-]", "", stage)}">{E(stage)}</span>'


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.state.pop("flash", []))
    if flashes:
        req._dirty = True
    head = f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
    if not req.user:
        return head + flashes + body + "</body></html>"
    links = [("dash", "/", "Dashboard"), ("pipeline", "/pipeline", "Pipeline"), ("candidates", "/candidates", "Candidates"),
             ("interviews", "/interviews", "Interviews"), ("reqs", "/requisitions", "Requisitions"), ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    con = db()
    cur = req.get("req", "all")
    opts = "".join(f'<option value="{E(r["code"])}"{" selected" if r["code"] == cur else ""}>{E(r["code"])} · {E(r["title"])}</option>'
                   for r in reqs(con))
    con.close()
    opts += f'<option value="all"{" selected" if cur == "all" else ""}>All requisitions</option>'
    return (head + f'<header><div class="brand">{APP}<small>Fernleaf Analytics · Talent</small></div><nav>{navh}</nav>'
            f'<form method=post action="/req"><input type=hidden name=next value="{E(req.h.path)}">Requisition '
            f'<select name=req onchange="this.form.submit()">{opts}</select><noscript><button>Set</button></noscript></form>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header>'
            f"<main>{flashes}{body}</main></body></html>")


def redirect(url):
    return 303, {"Location": url}, b""


def page(req, title, body, nav=""):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, layout(req, title, body, nav).encode()


APP_SQL = """SELECT a.*, c.name, c.email, c.id AS cid, r.code, r.title FROM applications a
    JOIN candidates c ON c.id=a.candidate_id JOIN requisitions r ON r.id=a.req_id"""


def total(a):
    vals = [a["score_sql"], a["score_code"], a["score_bi"], a["score_degree"]]
    return None if any(v is None for v in vals) else sum(vals)


def req_select(con, name, selected, allow_blank=False):
    o = '<option value="">- choose -</option>' if allow_blank else ""
    for r in reqs(con):
        if r["status"] != "Open":
            continue
        o += f'<option value="{r["id"]}"{" selected" if r["code"] == selected else ""}>{E(r["code"])} · {E(r["title"])}</option>'
    return f"<select name={name}>{o}</select>"


# ---------------------------------------------------------------- auth / selector
@route("GET", "/login")
def login_form(req):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>HireDesk</h1><p class="muted">Fernleaf Analytics · applicant tracking</p>'
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
    con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], now(), json.dumps({"req": u["last_req"] or "all"})))
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


@route("POST", "/req")
def set_req(req):
    code = req.form.get("req", "")
    con = db()
    if code == "all" or con.execute("SELECT 1 FROM requisitions WHERE code=?", (code,)).fetchone():
        req.set("req", code)
        req.set("pl_page", 1)
        con.execute("UPDATE users SET last_req=? WHERE id=?", (code, req.user["id"]))
        con.commit()
    con.close()
    nxt = req.form.get("next", "/")
    return redirect(nxt if nxt.startswith("/") else "/")


# ---------------------------------------------------------------- pages
@route("GET", "/")
def dashboard(req):
    con = db()
    rows = con.execute("SELECT r.code, r.title, r.status, a.stage, COUNT(*) n FROM applications a JOIN requisitions r ON r.id=a.req_id "
                       "GROUP BY r.code, a.stage").fetchall()
    up = con.execute("SELECT s.start, r.code, c.name FROM slots s JOIN requisitions r ON r.id=s.req_id JOIN applications a ON "
                     "a.id=s.application_id JOIN candidates c ON c.id=a.candidate_id ORDER BY s.start").fetchall()
    biz = con.execute("SELECT value FROM settings WHERE key='business_date'").fetchone()["value"]
    allreqs = reqs(con)
    con.close()
    by = {}
    for r in rows:
        by.setdefault(r["code"], {})[r["stage"]] = r["n"]
    body = f'<h1>Dashboard</h1><p class="muted">Today: {nice_date(biz)}</p><div class="grid">'
    for r in allreqs:
        st = by.get(r["code"], {})
        active = sum(v for k, v in st.items() if k not in CLOSED)
        body += (f'<div class="card"><b>{E(r["code"])}</b> {E(r["title"])} <span class="muted">({E(r["status"])})</span>'
                 f'<div class="kpi">{active} active</div><div class="muted">'
                 + " · ".join(f"{E(k)} {v}" for k, v in sorted(st.items(), key=lambda kv: STAGES.index(kv[0]))) + "</div></div>")
    body += '</div><h2>Booked interviews</h2><table class="t"><tr><th>When</th><th>Requisition</th><th>Candidate</th></tr>'
    body += "".join(f'<tr><td>{slot_label(u["start"])}</td><td>{E(u["code"])}</td><td>{E(u["name"])}</td></tr>' for u in up)
    return page(req, "Dashboard", body + "</table>", "dash")


@route("GET", "/pipeline")
def pipeline(req):
    for key in ("stage", "q"):
        if key in req.q:
            req.set("pl_" + key, req.q[key].strip())
            req.set("pl_page", 1)
    if req.q.get("page", "").isdigit():
        req.set("pl_page", int(req.q["page"]))
    code, st, q = req.get("req", "all"), req.get("pl_stage", ""), req.get("pl_q", "")
    con = db()
    rows = [dict(r) for r in con.execute(APP_SQL + " ORDER BY a.applied_on DESC, a.id DESC")]
    con.close()
    rows = [r for r in rows if (code == "all" or r["code"] == code) and (not st or r["stage"] == st)
            and (not q or q.lower() in (r["name"] + " " + r["email"]).lower())]
    pages = max(1, (len(rows) + PAGE - 1) // PAGE)
    pg = min(max(1, int(req.get("pl_page", 1))), pages)
    sel = '<option value="">All stages</option>' + "".join(f'<option{" selected" if s == st else ""}>{E(s)}</option>' for s in STAGES)
    body = (f'<h1>Pipeline <span class="muted">· {E(code if code != "all" else "all requisitions")}</span></h1>'
            f'<form class="filters" method=get action="/pipeline"><div><label>Stage</label><select name=stage>{sel}</select></div>'
            f'<div><label>Search name / email</label><input type=text name=q value="{E(q)}" style="width:260px"></div>'
            '<div><button>Filter</button></div><div><a class="muted" href="/pipeline?stage=&amp;q=">Clear filters</a></div>'
            '<div style="margin-left:auto"><a href="/candidates/new"><button type=button>+ New candidate</button></a></div></form>'
            '<table class="t"><tr><th>Candidate</th><th>Email</th><th>Requisition</th><th>Applied</th><th class=n>Score</th><th>Stage</th></tr>')
    for r in rows[(pg - 1) * PAGE: pg * PAGE]:
        t = total(r)
        body += (f'<tr><td><a href="/applications/{r["id"]}">{E(r["name"])}</a></td><td>{E(r["email"])}</td><td>{E(r["code"])}</td>'
                 f'<td>{nice_date(r["applied_on"])}</td><td class=n>{"" if t is None else f"{t}/5"}</td><td>{badge(r["stage"])}</td></tr>')
    if not rows:
        body += '<tr><td colspan=6 class="muted">No applications match the requisition and filters.</td></tr>'
    body += f'</table><div class="pager">{len(rows)} applications · page {pg} of {pages} &nbsp; '
    body += (f'<a href="/pipeline?page={pg - 1}">&laquo; Previous</a>' if pg > 1 else "") + \
            (f'<a href="/pipeline?page={pg + 1}">Next &raquo;</a>' if pg < pages else "")
    return page(req, "Pipeline", body + "</div>", "pipeline")


@route("GET", "/candidates")
def candidates(req):
    q = req.q.get("q", "").strip()
    pg = int(req.q["page"]) if req.q.get("page", "").isdigit() else 1
    con = db()
    rows = con.execute("SELECT c.*, (SELECT GROUP_CONCAT(r.code || ' ' || a.stage, '; ') FROM applications a JOIN requisitions r "
                       "ON r.id=a.req_id WHERE a.candidate_id=c.id) apps FROM candidates c ORDER BY c.name").fetchall()
    con.close()
    rows = [r for r in rows if not q or q.lower() in (r["name"] + " " + r["email"] + " " + (r["phone"] or "")).lower()]
    pages = max(1, (len(rows) + 14) // 15)
    body = ('<h1>Candidates</h1><form class="filters" method=get><div><label>Search name / email / phone</label>'
            f'<input type=text name=q value="{E(q)}" style="width:260px"></div><div><button>Search</button></div>'
            '<div style="margin-left:auto"><a href="/candidates/new"><button type=button>+ New candidate</button></a></div></form>'
            '<table class="t"><tr><th>Name</th><th>Email</th><th>Location</th><th>Applications</th><th>Added</th></tr>')
    for r in rows[(pg - 1) * 15: pg * 15]:
        body += (f'<tr><td><a href="/candidates/{r["id"]}">{E(r["name"])}</a></td><td>{E(r["email"])}</td><td>{E(r["location"])}</td>'
                 f'<td class=muted>{E(r["apps"] or "-")}</td><td>{nice_date(r["created_at"])}</td></tr>')
    body += f'</table><div class="pager">{len(rows)} candidates · page {pg} of {pages} &nbsp; '
    qq = urllib.parse.quote(q)
    body += (f'<a href="/candidates?q={qq}&page={pg - 1}">&laquo; Previous</a>' if pg > 1 else "") + \
            (f'<a href="/candidates?q={qq}&page={pg + 1}">Next &raquo;</a>' if pg < pages else "")
    return page(req, "Candidates", body + "</div>", "candidates")


@route("GET", "/candidates/new")
def new_candidate_form(req):
    con = db()
    sel = req_select(con, "req_id", req.get("req", "all"), allow_blank=True)
    con.close()
    f = req.get("draft", {})
    body = ('<p><a href="/candidates">&laquo; Candidates</a></p><h1>New candidate</h1><div class="card" style="max-width:640px">'
            '<form method=post action="/candidates/new">'
            f'<label>Full name *</label><input type=text name=name value="{E(f.get("name", ""))}" style="width:100%">'
            f'<label>Email *</label><input type=email name=email value="{E(f.get("email", ""))}" style="width:100%">'
            f'<label>Phone</label><input type=text name=phone value="{E(f.get("phone", ""))}" style="width:100%">'
            f'<label>Location</label><input type=text name=location value="{E(f.get("location", ""))}" style="width:100%">'
            '<label>Source</label><select name=source><option>Email application</option><option>Careers page</option>'
            '<option>LinkedIn</option><option>Referral</option><option>Agency</option></select>'
            f'<label>Apply to requisition *</label>{sel}<p><button>Create candidate</button></p></form></div>')
    if req.state.pop("draft", None) is not None:
        req._dirty = True
    return page(req, "New candidate", body, "candidates")


@route("POST", "/candidates/new")
def new_candidate(req):
    f = {k: req.form.get(k, "").strip() for k in ("name", "email", "phone", "location", "source", "req_id")}
    con = db()
    dup = con.execute("SELECT id, name FROM candidates WHERE lower(email)=?", (f["email"].lower(),)).fetchone()
    r = con.execute("SELECT * FROM requisitions WHERE id=? AND status='Open'", (f["req_id"] or 0,)).fetchone()
    err = None
    if not f["name"] or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", f["email"]):
        err = "Name and a valid email are required."
    elif dup:
        err = (f"A candidate with this email already exists ({dup['name']}, #{dup['id']}). Open their profile and use "
               "'Add to requisition' instead.")
    elif not r:
        err = "Choose the requisition the candidate applies to."
    if err:
        con.close()
        req.flash(err, "err")
        req.set("draft", f)
        return redirect("/candidates/new")
    cur = con.execute("INSERT INTO candidates(name, email, phone, location, source, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
                      (f["name"], f["email"], f["phone"], f["location"], f["source"], now(), req.user["username"]))
    cid = cur.lastrowid
    cur = con.execute("INSERT INTO applications(candidate_id, req_id, stage, applied_on, updated_at) VALUES (?,?,?,?,?)",
                      (cid, r["id"], "Applied", now()[:10], now()))
    audit(con, req, "candidate created", f"{f['name']} <{f['email']}> applied to {r['code']}")
    con.commit()
    con.close()
    req.flash(f"{f['name']} added to {r['code']} {r['title']}.")
    return redirect(f"/applications/{cur.lastrowid}")


@route("GET", r"/candidates/(\d+)")
def candidate(req, cid):
    con = db()
    c = con.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
    if not c:
        con.close()
        return redirect("/candidates")
    apps = con.execute(APP_SQL + " WHERE c.id=? ORDER BY a.applied_on DESC", (cid,)).fetchall()
    sel = req_select(con, "req_id", req.get("req", "all"), allow_blank=True)
    con.close()
    body = (f'<p><a href="/candidates">&laquo; Candidates</a></p><h1>{E(c["name"])}</h1><div class="two"><div><div class="card">'
            f'Email: {E(c["email"])}<br>Phone: {E(c["phone"] or "-")}<br>Location: {E(c["location"] or "-")}<br>'
            f'Source: {E(c["source"] or "-")}<br><span class=muted>Added {nice_date(c["created_at"])} by {E(c["created_by"])}</span></div>'
            '<h2>Applications</h2><table class="t"><tr><th>Requisition</th><th>Applied</th><th class=n>Score</th><th>Stage</th></tr>')
    for a in apps:
        t = total(a)
        body += (f'<tr><td><a href="/applications/{a["id"]}">{E(a["code"])} {E(a["title"])}</a></td><td>{nice_date(a["applied_on"])}</td>'
                 f'<td class=n>{"" if t is None else f"{t}/5"}</td><td>{badge(a["stage"])}</td></tr>')
    body += (f'</table></div><div class="card"><h2 style="margin-top:0">Add to requisition</h2><form method=post action="/candidates/{c["id"]}/apply">'
             f'<label>Requisition</label>{sel}<p><button>Add application</button></p></form></div></div>')
    return page(req, c["name"], body, "candidates")


@route("POST", r"/candidates/(\d+)/apply")
def candidate_apply(req, cid):
    con = db()
    r = con.execute("SELECT * FROM requisitions WHERE id=? AND status='Open'", (req.form.get("req_id") or 0,)).fetchone()
    c = con.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
    if not r or not c:
        req.flash("Choose an open requisition.", "err")
        con.close()
        return redirect(f"/candidates/{cid}")
    if con.execute("SELECT 1 FROM applications WHERE candidate_id=? AND req_id=?", (cid, r["id"])).fetchone():
        req.flash(f"{c['name']} already has an application for {r['code']}.", "err")
        con.close()
        return redirect(f"/candidates/{cid}")
    cur = con.execute("INSERT INTO applications(candidate_id, req_id, stage, applied_on, updated_at) VALUES (?,?,?,?,?)",
                      (cid, r["id"], "Applied", now()[:10], now()))
    audit(con, req, "application added", f"{c['name']} applied to {r['code']}")
    con.commit()
    con.close()
    req.flash(f"{c['name']} added to {r['code']}.")
    return redirect(f"/applications/{cur.lastrowid}")


@route("GET", r"/applications/(\d+)")
def application(req, aid):
    con = db()
    a = con.execute(APP_SQL + " WHERE a.id=?", (aid,)).fetchone()
    if not a:
        con.close()
        return redirect("/pipeline")
    slot = con.execute("SELECT * FROM slots WHERE application_id=?", (aid,)).fetchone()
    con.close()

    def sel(name, hi, val):
        o = '<option value="">-</option>' + "".join(f'<option{" selected" if val == v else ""}>{v}</option>' for v in range(hi + 1))
        return f"<select name={name}>{o}</select>"
    rtw = "".join(f'<option{" selected" if a["rtw"] == v else ""}>{v}</option>' for v in ("Yes", "No"))
    t = total(a)
    stages = "".join(f'<option{" selected" if s == a["stage"] else ""}>{E(s)}</option>' for s in STAGES)
    body = (f'<p><a href="/pipeline">&laquo; Pipeline</a></p><h1><a href="/candidates/{a["cid"]}">{E(a["name"])}</a> · '
            f'{E(a["code"])} {E(a["title"])} {badge(a["stage"])}</h1><div class="two"><div><div class="card">'
            f'Email: {E(a["email"])}<br>Applied: {nice_date(a["applied_on"])}<br>Last update: {E(a["updated_at"])}'
            + (f'<br>Rejection / withdrawal reason: {E(a["reason"])}' if a["reason"] else "")
            + (f'<br>Interview: <a href="/interviews/{slot["id"]}">{slot_label(slot["start"])}</a>' if slot else "") + "</div>"
            '<div class="card"><h2 style="margin-top:0">Screening scorecard</h2>'
            f'<form method=post action="/applications/{a["id"]}/scores"><table class="sc">'
            f'<tr><td>SQL experience (0-2)</td><td>{sel("score_sql", 2, a["score_sql"])}</td></tr>'
            f'<tr><td>Python or R (0-1)</td><td>{sel("score_code", 1, a["score_code"])}</td></tr>'
            f'<tr><td>BI tool (0-1)</td><td>{sel("score_bi", 1, a["score_bi"])}</td></tr>'
            f'<tr><td>Quantitative degree (0-1)</td><td>{sel("score_degree", 1, a["score_degree"])}</td></tr>'
            f'<tr><td>Right to work in the UK</td><td><select name=rtw><option value="">-</option>{rtw}</select></td></tr>'
            f'<tr><td><b>Total</b></td><td><b>{"-" if t is None else f"{t} / 5"}</b></td></tr></table>'
            '<p><button>Save scorecard</button></p></form></div></div><div><div class="card"><h2 style="margin-top:0">Stage</h2>'
            f'<form method=post action="/applications/{a["id"]}/stage"><label>Move to stage</label><select name=stage>{stages}</select>'
            '<label>Reason (required for Rejected)</label><input type=text name=reason style="width:100%">'
            '<p><button>Update stage</button></p></form></div>'
            f'<div class="card"><h2 style="margin-top:0">Notes</h2><div class="muted">{E(a["notes"] or "No notes.")}</div></div></div></div>')
    return page(req, a["name"], body, "pipeline")


@route("POST", r"/applications/(\d+)/scores")
def save_scores(req, aid):
    vals = {}
    for k, hi in (("score_sql", 2), ("score_code", 1), ("score_bi", 1), ("score_degree", 1)):
        v = req.form.get(k, "")
        if not v.isdigit() or int(v) > hi:
            req.flash("Fill in every score before saving.", "err")
            return redirect(f"/applications/{aid}")
        vals[k] = int(v)
    if req.form.get("rtw") not in ("Yes", "No"):
        req.flash("Record the right to work (Yes/No).", "err")
        return redirect(f"/applications/{aid}")
    con = db()
    a = con.execute(APP_SQL + " WHERE a.id=?", (aid,)).fetchone()
    con.execute("UPDATE applications SET score_sql=?, score_code=?, score_bi=?, score_degree=?, rtw=?, updated_at=? WHERE id=?",
                (vals["score_sql"], vals["score_code"], vals["score_bi"], vals["score_degree"], req.form["rtw"], now(), aid))
    audit(con, req, "scorecard saved", f"{a['name']} {a['code']}: total {sum(vals.values())}/5, right to work {req.form['rtw']}")
    con.commit()
    con.close()
    req.flash(f"Scorecard saved: {sum(vals.values())}/5.")
    return redirect(f"/applications/{aid}")


@route("POST", r"/applications/(\d+)/stage")
def save_stage(req, aid):
    stage, reason = req.form.get("stage", ""), req.form.get("reason", "").strip()
    con = db()
    a = con.execute(APP_SQL + " WHERE a.id=?", (aid,)).fetchone()
    if stage not in STAGES or not a:
        req.flash("Unknown stage.", "err")
    elif stage == "Rejected" and not reason:
        req.flash("Give a reason when rejecting a candidate.", "err")
    elif stage == "Interview scheduled" and not con.execute("SELECT 1 FROM slots WHERE application_id=?", (aid,)).fetchone():
        req.flash("Book an interview slot (Interviews page) - the stage changes automatically.", "err")
    else:
        con.execute("UPDATE applications SET stage=?, reason=?, updated_at=? WHERE id=?",
                    (stage, reason if stage in ("Rejected", "Withdrawn") else a["reason"], now(), aid))
        if stage in CLOSED:
            con.execute("UPDATE slots SET application_id=NULL, booked_by=NULL, booked_at=NULL WHERE application_id=?", (aid,))
        audit(con, req, "stage changed", f"{a['name']} {a['code']}: {a['stage']} -> {stage}" + (f" ({reason})" if reason else ""))
        con.commit()
        req.flash(f"{a['name']} moved to {stage}.")
    con.close()
    return redirect(f"/applications/{aid}")


@route("GET", "/interviews")
def interviews(req):
    code = req.get("req", "all")
    con = db()
    rows = con.execute("SELECT s.*, r.code, r.title, c.name FROM slots s JOIN requisitions r ON r.id=s.req_id LEFT JOIN applications a "
                       "ON a.id=s.application_id LEFT JOIN candidates c ON c.id=a.candidate_id ORDER BY s.start").fetchall()
    con.close()
    rows = [r for r in rows if code == "all" or r["code"] == code]
    body = (f'<h1>Interview slots <span class="muted">· {E(code if code != "all" else "all requisitions")}</span></h1>'
            '<p class="muted">Slots are created by the hiring managers. Open a slot to see the video link and to book a candidate.</p>'
            '<table class="t"><tr><th>When</th><th>Length</th><th>Requisition</th><th>Panel</th><th>Status</th></tr>')
    for r in rows:
        st = f'<span class="booked">Booked: {E(r["name"])}</span>' if r["application_id"] else '<span class="free">Free</span>'
        body += (f'<tr><td><a href="/interviews/{r["id"]}">{slot_label(r["start"])}</a></td><td>{r["minutes"]} min</td>'
                 f'<td>{E(r["code"])}</td><td>{E(r["panel"])}</td><td>{st}</td></tr>')
    if not rows:
        body += '<tr><td colspan=5 class="muted">No slots for this requisition.</td></tr>'
    return page(req, "Interviews", body + "</table>", "interviews")


@route("GET", r"/interviews/(\d+)")
def slot_page(req, sid):
    con = db()
    s = con.execute("SELECT s.*, r.code, r.title FROM slots s JOIN requisitions r ON r.id=s.req_id WHERE s.id=?", (sid,)).fetchone()
    if not s:
        con.close()
        return redirect("/interviews")
    booked = con.execute(APP_SQL + " WHERE a.id=?", (s["application_id"],)).fetchone() if s["application_id"] else None
    cands = con.execute(APP_SQL + " WHERE a.req_id=? AND a.stage NOT IN ('Rejected','Withdrawn','Hired') AND a.id NOT IN "
                        "(SELECT application_id FROM slots WHERE application_id IS NOT NULL) ORDER BY c.name", (s["req_id"],)).fetchall()
    con.close()
    body = (f'<p><a href="/interviews">&laquo; Interview slots</a></p><h1>{slot_label(s["start"])} · {E(s["code"])}</h1>'
            f'<div class="two"><div class="card">Requisition: {E(s["code"])} {E(s["title"])}<br>Length: {s["minutes"]} minutes<br>'
            f'Panel: {E(s["panel"])}<br>Format: {E(s["location"])}<br>Video link: <b>{E(s["video_link"])}</b></div><div class="card">')
    if booked:
        body += (f'<h2 style="margin-top:0">Booked</h2><a href="/applications/{booked["id"]}">{E(booked["name"])}</a> '
                 f'({E(booked["email"])})<br><span class=muted>by {E(s["booked_by"])} at {E(s["booked_at"])}</span>'
                 f'<form method=post action="/interviews/{s["id"]}/cancel" onsubmit="return confirm(\'Cancel this booking?\')">'
                 '<p><button class="ghost">Cancel booking</button></p></form>')
    else:
        opts = "".join(f'<option value="{c["id"]}">{E(c["name"])} ({E(c["stage"])})</option>' for c in cands)
        body += ('<h2 style="margin-top:0">Book a candidate</h2>'
                 f'<form method=post action="/interviews/{s["id"]}/book"><label>Candidate ({E(s["code"])})</label>'
                 f'<select name=application_id><option value="">- choose -</option>{opts}</select><p><button>Book slot</button></p></form>')
    return page(req, "Slot", body + "</div></div>", "interviews")


@route("POST", r"/interviews/(\d+)/book")
def book(req, sid):
    con = db()
    s = con.execute("SELECT s.*, r.code FROM slots s JOIN requisitions r ON r.id=s.req_id WHERE s.id=?", (sid,)).fetchone()
    a = con.execute(APP_SQL + " WHERE a.id=?", (req.form.get("application_id") or 0,)).fetchone()
    if not s or not a or a["req_id"] != s["req_id"]:
        req.flash("Choose a candidate of this requisition.", "err")
    elif s["application_id"]:
        req.flash("This slot is already booked.", "err")
    elif a["stage"] in CLOSED:
        req.flash(f"{a['name']} is {a['stage'].lower()}.", "err")
    elif con.execute("SELECT 1 FROM slots WHERE application_id=?", (a["id"],)).fetchone():
        req.flash(f"{a['name']} already has an interview booked - cancel that booking first.", "err")
    else:
        con.execute("UPDATE slots SET application_id=?, booked_by=?, booked_at=? WHERE id=?", (a["id"], req.user["username"], now(), sid))
        con.execute("UPDATE applications SET stage='Interview scheduled', updated_at=? WHERE id=?", (now(), a["id"]))
        audit(con, req, "interview booked", f"{a['name']} {s['code']} {s['start']}")
        con.commit()
        req.flash(f"{a['name']} booked for {slot_label(s['start'])}.")
    con.close()
    return redirect(f"/interviews/{sid}")


@route("POST", r"/interviews/(\d+)/cancel")
def cancel(req, sid):
    con = db()
    s = con.execute("SELECT s.*, r.code FROM slots s JOIN requisitions r ON r.id=s.req_id WHERE s.id=?", (sid,)).fetchone()
    if s and s["application_id"]:
        a = con.execute(APP_SQL + " WHERE a.id=?", (s["application_id"],)).fetchone()
        con.execute("UPDATE slots SET application_id=NULL, booked_by=NULL, booked_at=NULL WHERE id=?", (sid,))
        if a["stage"] == "Interview scheduled":
            con.execute("UPDATE applications SET stage='Interview - to schedule', updated_at=? WHERE id=?", (now(), a["id"]))
        audit(con, req, "booking cancelled", f"{a['name']} {s['code']} {s['start']}")
        con.commit()
        req.flash("Booking cancelled.")
    con.close()
    return redirect(f"/interviews/{sid}")


@route("GET", "/requisitions")
def requisitions(req):
    con = db()
    rows = con.execute("SELECT r.*, (SELECT COUNT(*) FROM applications a WHERE a.req_id=r.id) n FROM requisitions r ORDER BY code DESC").fetchall()
    con.close()
    body = ('<h1>Requisitions</h1><table class="t"><tr><th>Code</th><th>Title</th><th>Location</th><th>Hiring manager</th>'
            '<th>Opened</th><th>Status</th><th class=n>Applications</th></tr>')
    body += "".join(f'<tr><td>{E(r["code"])}</td><td>{E(r["title"])}</td><td>{E(r["location"])}</td><td>{E(r["hiring_manager"])}</td>'
                    f'<td>{nice_date(r["opened"])}</td><td>{E(r["status"])}</td><td class=n>{r["n"]}</td></tr>' for r in rows)
    return page(req, "Requisitions", body + "</table>", "reqs")


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
    body += (f'<a href="/activity?page={pg - 1}">&laquo; Newer</a>' if pg > 1 else "") + \
            (f'<a href="/activity?page={pg + 1}">Older &raquo;</a>' if pg * 30 < n else "")
    return page(req, "Activity", body + "</div>", "activity")


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "HireDesk/4.1"

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
    ap.add_argument("--port", type=int, default=8122)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
