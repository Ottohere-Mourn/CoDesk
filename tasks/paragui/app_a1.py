#!/usr/bin/env python3
"""RotaDesk - staff rota and leave management of Elmbrook House Care Home (paraGUI pair a1).

Single file, Python 3 standard library only:   python3 app.py --db PATH --port N     (binds 127.0.0.1)
Weekly shift rota (Early / Late / Night), staff records, leave requests with approve/decline, policies, a printable
rota and an activity log. Like most small rota tools it records what the manager decides and shows a warning or two,
but it never blocks a change: the rota rules are the manager's responsibility.
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

APP, COOKIE = "RotaDesk", "rotadesk_sid"
DB = ""
E = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
ROUTES = []
SHIFTS = [("E", "Early", "07:00–15:00"), ("L", "Late", "14:00–22:00"), ("N", "Night", "21:30–07:30")]
SNAME = {k: n for k, n, _ in SHIFTS}
STIME = {k: t for k, _, t in SHIFTS}
NEED = {"E": 3, "L": 3, "N": 2}
WEEK0 = dt.date(2026, 11, 16)
WEEK = [(WEEK0 + dt.timedelta(days=i)).isoformat() for i in range(7)]
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


def dlabel(d, long=False):
    x = dt.date.fromisoformat(d)
    return x.strftime("%A %-d %B") if long else f"{x.strftime('%a')} {x.day} {x.strftime('%b')}"


def nice(d):
    try:
        return dt.date.fromisoformat(d).strftime("%-d %b %Y")
    except Exception:
        return d or ""


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
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'Segoe UI',Ubuntu,Arial,sans-serif;background:#eef3f1;color:#1f2a28}
a{color:#1f6f5c;text-decoration:none}a:hover{text-decoration:underline}
header{background:#21463d;color:#e8f3ef;display:flex;align-items:center;gap:22px;padding:0 22px;height:54px}
header .brand{font-weight:700;font-size:19px}header .brand small{font-weight:400;opacity:.75;margin-left:8px;font-size:13px}
header nav a{color:#e8f3ef;margin-right:15px;font-size:14px}header nav a.on{border-bottom:2px solid #8fd3bd;padding-bottom:3px}
header .who{margin-left:auto;font-size:13px}header .who a{color:#bdf0de}
main{max-width:1240px;margin:20px auto;padding:0 22px}h1{font-size:22px;margin:4px 0 14px}h2{font-size:17px;margin:20px 0 10px}
.card{background:#fff;border:1px solid #cfdcd7;border-radius:6px;padding:14px 18px;margin-bottom:14px}
table.t{width:100%;border-collapse:collapse;background:#fff;border:1px solid #cfdcd7}
table.t th{background:#dfebe6;text-align:left;font-size:13px;padding:7px 9px;border-bottom:1px solid #c3d4cd}
table.t td{padding:6px 9px;border-bottom:1px solid #e3ece8;font-size:14px;vertical-align:top}
td.n,th.n{text-align:right}
table.grid td{min-width:150px}.slot{display:block;padding:2px 6px;margin:2px 0;border-radius:4px;background:#e9f4ef;font-size:13px}
.slot.sen{background:#d7ecf9}.slot.open{background:#fff3cd;color:#7a5a00;font-weight:600;border:1px dashed #d9b44a}
.slot.warn{background:#fde0db;color:#8b2316}.tag{font-size:11px;font-weight:700;color:#21608a;margin-left:4px}
.leave{font-size:12px;color:#8b2316}.muted{color:#6b7a76;font-size:13px}
.flash{padding:9px 14px;border-radius:5px;margin-bottom:12px}.flash.ok{background:#e1f3e8;border:1px solid #9ccfae}
.flash.err{background:#fde3e0;border:1px solid #e3a49b}
label{display:block;font-size:13px;color:#4c5b57;margin:8px 0 3px}
input[type=text],input[type=password],select,textarea{padding:6px 8px;border:1px solid #b9c9c3;border-radius:4px;font-size:14px}
button{background:#1f6f5c;color:#fff;border:0;border-radius:4px;padding:7px 14px;font-size:14px;cursor:pointer}
button.ghost{background:#fff;color:#1f6f5c;border:1px solid #b9c9c3}button.danger{background:#a8321f}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.b-Pending{background:#fff0cc;color:#8a5a00}.b-Approved{background:#dcefdc;color:#25632a}.b-Declined{background:#e8e8e8;color:#555}
.two{display:grid;grid-template-columns:1.3fr 1fr;gap:18px}.login{max-width:380px;margin:90px auto}
.policy li{margin:6px 0}.kpi{font-size:26px;font-weight:700}.grid4{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
"""


def layout(req, title, body, nav=""):
    flashes = "".join(f'<div class="flash {k}">{E(m)}</div>' for k, m in req.state.pop("flash", []))
    if flashes:
        req._dirty = True
    head = f"<!doctype html><html><head><meta charset=utf-8><title>{E(title)} · {APP}</title><style>{CSS}</style></head><body>"
    if not req.user:
        return head + flashes + body + "</body></html>"
    links = [("home", "/", "Overview"), ("rota", "/rota", "Rota"), ("staff", "/staff", "Staff"), ("leave", "/leave", "Leave requests"),
             ("policies", "/policies", "Policies"), ("activity", "/activity", "Activity")]
    navh = "".join(f'<a href="{u}" class="{"on" if k == nav else ""}">{t}</a>' for k, u, t in links)
    return (head + f'<header><div class="brand">{APP}<small>Elmbrook House Care Home</small></div><nav>{navh}</nav>'
            f'<div class="who">{E(req.user["name"])} · <a href="/logout">Log out</a></div></header><main>{flashes}{body}</main></body></html>')


def redirect(url):
    return 303, {"Location": url}, b""


def page(req, title, body, nav=""):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, layout(req, title, body, nav).encode()


# ---------------------------------------------------------------- data access
def staff_all(con):
    return {r["id"]: dict(r) for r in con.execute("SELECT * FROM staff ORDER BY role DESC, name")}


def rota(con):
    out = {(d, s): [] for d in WEEK for s in NEED}
    for r in con.execute("SELECT a.*, s.name, s.role FROM assignments a JOIN staff s ON s.id=a.staff_id WHERE a.deleted=0 ORDER BY a.id"):
        if (r["day"], r["shift"]) in out:
            out[(r["day"], r["shift"])].append(dict(r))
    return out


def leave_days(con, status="Approved"):
    out = {}
    for r in con.execute("SELECT * FROM leave_requests WHERE status=?", (status,)):
        d0, d1 = dt.date.fromisoformat(r["start"]), dt.date.fromisoformat(r["end"])
        while d0 <= d1:
            out.setdefault(r["staff_id"], set()).add(d0.isoformat())
            d0 += dt.timedelta(days=1)
    return out


def shift_counts(con):
    c = {}
    for r in con.execute("SELECT staff_id FROM assignments WHERE deleted=0 AND day BETWEEN ? AND ?", (WEEK[0], WEEK[-1])):
        c[r["staff_id"]] = c.get(r["staff_id"], 0) + 1
    return c


def is_senior(role):
    return role.startswith("Senior")


# ---------------------------------------------------------------- auth
@route("GET", "/login")
def login_form(req):
    if req.user:
        return redirect("/")
    body = ('<div class="login card"><h1>RotaDesk</h1><p class="muted">Elmbrook House Care Home · rota &amp; leave</p>'
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
    con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], now(), "{}"))
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
@route("GET", "/")
def home(req):
    con = db()
    r = rota(con)
    open_n = sum(max(0, NEED[s] - len(v)) for (d, s), v in r.items())
    pend = con.execute("SELECT COUNT(*) n FROM leave_requests WHERE status='Pending'").fetchone()["n"]
    acts = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 10").fetchall()
    biz = setting(con, "business_date")
    con.close()
    body = (f'<h1>Overview</h1><p class="muted">Today is {nice(biz)}. Next rota to finalise: week 47, 16–22 November 2026.</p>'
            f'<div class="grid4"><div class="card"><div class="muted">Open shifts, week 47</div><div class="kpi">{open_n}</div>'
            '<a href="/rota">Open the rota</a></div>'
            f'<div class="card"><div class="muted">Leave requests waiting for a decision</div><div class="kpi">{pend}</div>'
            '<a href="/leave">Review requests</a></div><div class="card"><div class="muted">Staffing levels</div>'
            '<div>Early 3 · Late 3 · Night 2<br>at least one senior carer per shift</div><a href="/policies">Policies</a></div></div>'
            '<h2>Recent activity</h2><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
            + "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in acts)
            + "</table>")
    return page(req, "Overview", body, "home")


@route("GET", "/rota")
def rota_page(req):
    con = db()
    r = rota(con)
    st = staff_all(con)
    lv = leave_days(con)
    cnt = shift_counts(con)
    con.close()
    body = ('<h1>Rota · week 47 <span class="muted">· 16–22 November 2026 (draft)</span></h1>'
            '<p class="muted">Click a name to replace or remove it, or an OPEN slot to assign someone. '
            '<a href="/rota/print" target="_blank">Print view</a></p>'
            '<table class="t grid"><tr><th>Shift</th>' + "".join(f"<th>{dlabel(d)}</th>" for d in WEEK) + "</tr>")
    for s, name, times in SHIFTS:
        body += f'<tr><td><b>{name}</b><br><span class="muted">{times}<br>needs {NEED[s]}</span></td>'
        for d in WEEK:
            cell = ""
            for a in r[(d, s)]:
                warn = d in lv.get(a["staff_id"], ())
                cls = "slot" + (" sen" if is_senior(a["role"]) else "") + (" warn" if warn else "")
                cell += (f'<a class="{cls}" href="/rota/a/{a["id"]}">{E(a["name"])}'
                         f'{"<span class=tag>SC</span>" if is_senior(a["role"]) else ""}{" ⚠ on leave" if warn else ""}</a>')
            missing = NEED[s] - len(r[(d, s)])
            no_sen = not any(is_senior(a["role"]) for a in r[(d, s)])
            for i in range(max(0, missing)):
                lab = "OPEN – senior needed" if no_sen and i == 0 else "OPEN"
                cell += f'<a class="slot open" href="/rota/assign?day={d}&amp;shift={s}">{lab}</a>'
            body += f"<td>{cell}</td>"
        body += "</tr>"
    body += '<tr><td><b>On leave</b></td>'
    for d in WEEK:
        names = [st[i]["name"] for i, days in lv.items() if d in days and i in st]
        body += f'<td class="leave">{"<br>".join(E(n) for n in sorted(names)) or "–"}</td>'
    body += ('</tr></table><h2>Shifts this week</h2><table class="t"><tr><th>Name</th><th>Role</th><th class=n>Rostered</th>'
             '<th class=n>Contracted</th><th class=n>Maximum</th><th>Availability</th></tr>')
    for i, s in st.items():
        body += (f'<tr><td><a href="/staff/{i}">{E(s["name"])}</a></td><td>{E(s["role"])}</td><td class=n>{cnt.get(i, 0)}</td>'
                 f'<td class=n>{s["contracted"]}</td><td class=n>{s["max_shifts"]}</td><td>{E(s["availability"])}</td></tr>')
    return page(req, "Rota", body + "</table>", "rota")


def staff_options(st, sel=None):
    return "".join(f'<option value="{i}"{" selected" if i == sel else ""}>{E(s["name"])} – {E(s["role"])}</option>'
                   for i, s in sorted(st.items(), key=lambda kv: kv[1]["name"]))


@route("GET", "/rota/assign")
def assign_form(req):
    d, s = req.q.get("day", ""), req.q.get("shift", "")
    if d not in WEEK or s not in NEED:
        return redirect("/rota")
    con = db()
    r = rota(con)
    st = staff_all(con)
    con.close()
    cur = ", ".join(a["name"] for a in r[(d, s)]) or "nobody yet"
    body = (f'<p><a href="/rota">&laquo; Rota</a></p><h1>Assign · {SNAME[s]} shift, {dlabel(d, True)}</h1>'
            f'<div class="card">Shift {STIME[s]} · needs {NEED[s]} staff incl. one senior carer<br>Currently on this shift: {E(cur)}</div>'
            f'<div class="card"><form method=post action="/rota/assign"><input type=hidden name=day value="{d}">'
            f'<input type=hidden name=shift value="{s}"><label>Staff member</label><select name=staff_id>'
            f'<option value="">– choose –</option>{staff_options(st)}</select><p><button>Assign to shift</button></p></form></div>')
    return page(req, "Assign", body, "rota")


@route("POST", "/rota/assign")
def assign(req):
    d, s, sid = req.form.get("day", ""), req.form.get("shift", ""), req.form.get("staff_id", "")
    if d not in WEEK or s not in NEED or not sid.isdigit():
        req.flash("Choose a staff member.", "err")
        return redirect(f"/rota/assign?day={d}&shift={s}")
    con = db()
    p = con.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone()
    dup = con.execute("SELECT 1 FROM assignments WHERE deleted=0 AND day=? AND shift=? AND staff_id=?", (d, s, sid)).fetchone()
    if not p or dup:
        con.close()
        req.flash("That person is already on this shift.", "err")
        return redirect("/rota")
    con.execute("INSERT INTO assignments(day, shift, staff_id, created_at, created_by, deleted) VALUES (?,?,?,?,?,0)",
                (d, s, sid, now(), req.user["username"]))
    audit(con, req, "shift assigned", f"{p['name']} → {SNAME[s]} {dlabel(d)}")
    con.commit()
    con.close()
    req.flash(f"{p['name']} assigned to the {SNAME[s]} shift on {dlabel(d, True)}.")
    return redirect("/rota")


@route("GET", r"/rota/a/(\d+)")
def assignment(req, aid):
    con = db()
    a = con.execute("SELECT a.*, s.name, s.role FROM assignments a JOIN staff s ON s.id=a.staff_id WHERE a.id=?", (aid,)).fetchone()
    st = staff_all(con)
    con.close()
    if not a or a["deleted"]:
        req.flash("That assignment no longer exists - the rota has changed.", "err")
        return redirect("/rota")
    body = (f'<p><a href="/rota">&laquo; Rota</a></p><h1>{E(a["name"])} · {SNAME[a["shift"]]} shift, {dlabel(a["day"], True)}</h1>'
            f'<div class="two"><div class="card"><h2 style="margin-top:0">Replace with a colleague</h2>'
            f'<form method=post action="/rota/a/{aid}/replace"><label>New staff member</label><select name=staff_id>'
            f'<option value="">– choose –</option>{staff_options(st)}</select><p><button>Replace</button></p></form></div>'
            f'<div class="card"><h2 style="margin-top:0">Remove from shift</h2><p class="muted">The slot becomes OPEN.</p>'
            f'<form method=post action="/rota/a/{aid}/remove"><button class="danger">Remove {E(a["name"])}</button></form>'
            f'<p class="muted">Added {E(a["created_at"])} by {E(a["created_by"])}</p></div></div>')
    return page(req, "Assignment", body, "rota")


@route("POST", r"/rota/a/(\d+)/(replace|remove)")
def change_assignment(req, aid, what):
    con = db()
    a = con.execute("SELECT a.*, s.name FROM assignments a JOIN staff s ON s.id=a.staff_id WHERE a.id=?", (aid,)).fetchone()
    if not a or a["deleted"]:
        con.close()
        req.flash("That assignment no longer exists - the rota has changed.", "err")
        return redirect("/rota")
    if what == "replace":
        sid = req.form.get("staff_id", "")
        p = con.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone() if sid.isdigit() else None
        if not p:
            con.close()
            req.flash("Choose the colleague who takes over the shift.", "err")
            return redirect(f"/rota/a/{aid}")
        con.execute("UPDATE assignments SET deleted=1, deleted_at=? WHERE id=?", (now(), aid))
        con.execute("INSERT INTO assignments(day, shift, staff_id, created_at, created_by, deleted) VALUES (?,?,?,?,?,0)",
                    (a["day"], a["shift"], sid, now(), req.user["username"]))
        audit(con, req, "shift reassigned", f"{SNAME[a['shift']]} {dlabel(a['day'])}: {a['name']} → {p['name']}")
        req.flash(f"{p['name']} now covers the {SNAME[a['shift']]} shift on {dlabel(a['day'], True)} instead of {a['name']}.")
    else:
        con.execute("UPDATE assignments SET deleted=1, deleted_at=? WHERE id=?", (now(), aid))
        audit(con, req, "shift removed", f"{a['name']} off {SNAME[a['shift']]} {dlabel(a['day'])}")
        req.flash(f"{a['name']} removed from the {SNAME[a['shift']]} shift on {dlabel(a['day'], True)}.")
    con.commit()
    con.close()
    return redirect("/rota")


@route("GET", "/rota/print")
def rota_print(req):
    con = db()
    r = rota(con)
    st = staff_all(con)
    lv = leave_days(con)
    con.close()
    rows = ""
    for d in WEEK:
        for s, name, times in SHIFTS:
            names = []
            for a in r[(d, s)]:
                warn = d in lv.get(a["staff_id"], ())
                names.append(E(a["name"]) + (" (SC)" if is_senior(a["role"]) else "") + (" ⚠ ON LEAVE" if warn else ""))
            names += ["OPEN"] * max(0, NEED[s] - len(r[(d, s)]))
            rows += (f'<tr><td>{dlabel(d)}</td><td>{name}</td><td>{times}</td><td>{", ".join(names)}</td></tr>')
    onleave = "; ".join(f'{E(st[i]["name"])}: ' + ", ".join(dlabel(x) for x in sorted(days) if x in WEEK)
                        for i, days in lv.items() if i in st and any(x in WEEK for x in days))
    html_ = (f"<!doctype html><html><head><meta charset=utf-8><title>Rota week 47 · Elmbrook House</title><style>"
             "body{font:13px Arial,sans-serif;margin:24px;color:#000}table{border-collapse:collapse;width:100%}"
             "td,th{border:1px solid #888;padding:4px 7px;text-align:left}th{background:#eee}h1{font-size:19px;margin:0 0 4px}"
             "@media print{.noprint{display:none}}</style></head><body>"
             '<p class="noprint"><button onclick="window.print()">Print</button> <a href="/rota">Back to RotaDesk</a></p>'
             "<h1>Elmbrook House Care Home – staff rota</h1><p>Week 47 · 16–22 November 2026 · SC = senior carer</p>"
             "<table><tr><th>Day</th><th>Shift</th><th>Hours</th><th>Staff</th></tr>" + rows + "</table>"
             f"<p>Approved leave this week: {onleave or 'none'}</p><p>Printed from RotaDesk {now()[:16]}</p></body></html>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, html_.encode()


@route("GET", "/staff")
def staff_list(req):
    con = db()
    st = staff_all(con)
    cnt = shift_counts(con)
    lv = leave_days(con)
    con.close()
    body = ('<h1>Staff</h1><table class="t"><tr><th>Name</th><th>Role</th><th>Contract</th><th class=n>Contracted shifts/wk</th>'
            '<th class=n>Max shifts/wk</th><th class=n>Rostered wk 47</th><th>Availability</th><th class=n>Leave balance</th><th>Approved leave wk 47</th></tr>')
    for i, s in st.items():
        days = ", ".join(dlabel(d) for d in sorted(lv.get(i, ())) if d in WEEK)
        body += (f'<tr><td><a href="/staff/{i}">{E(s["name"])}</a></td><td>{E(s["role"])}</td><td>{E(s["employment"])}</td>'
                 f'<td class=n>{s["contracted"]}</td><td class=n>{s["max_shifts"]}</td><td class=n>{cnt.get(i, 0)}</td>'
                 f'<td>{E(s["availability"])}</td><td class=n>{s["leave_balance"]:g} days</td><td>{days or "–"}</td></tr>')
    return page(req, "Staff", body + "</table>", "staff")


@route("GET", r"/staff/(\d+)")
def staff_detail(req, sid):
    con = db()
    s = con.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone()
    if not s:
        con.close()
        return redirect("/staff")
    shifts = con.execute("SELECT * FROM assignments WHERE staff_id=? AND deleted=0 ORDER BY day, shift", (sid,)).fetchall()
    reqs = con.execute("SELECT * FROM leave_requests WHERE staff_id=? ORDER BY start", (sid,)).fetchall()
    con.close()
    body = (f'<p><a href="/staff">&laquo; Staff</a></p><h1>{E(s["name"])}</h1><div class="two"><div class="card">'
            f'{E(s["role"])} · {E(s["employment"])} · started {nice(s["start_date"])}<br>Phone {E(s["phone"])}<br>'
            f'Contracted {s["contracted"]} shifts a week · maximum {s["max_shifts"]}<br><b>Availability:</b> {E(s["availability"])}<br>'
            f'Annual leave balance: {s["leave_balance"]:g} days</div><div class="card"><h2 style="margin-top:0">Shifts in week 47</h2>'
            + ("".join(f'<div>{dlabel(a["day"])} · {SNAME[a["shift"]]} {STIME[a["shift"]]}</div>' for a in shifts) or '<span class="muted">none</span>')
            + '</div></div><h2>Leave</h2><table class="t"><tr><th>Dates</th><th>Type</th><th>Status</th><th></th></tr>')
    for r in reqs:
        body += (f'<tr><td>{nice(r["start"])} – {nice(r["end"])}</td><td>{E(r["kind"])}</td>'
                 f'<td><span class="badge b-{r["status"]}">{r["status"]}</span></td><td><a href="/leave/{r["id"]}">open</a></td></tr>')
    return page(req, s["name"], body + "</table>", "staff")


@route("GET", "/leave")
def leave_list(req):
    stf = req.q.get("status", "Pending")
    con = db()
    rows = con.execute("SELECT r.*, s.name, s.role FROM leave_requests r JOIN staff s ON s.id=r.staff_id ORDER BY r.submitted, r.id").fetchall()
    con.close()
    rows = [r for r in rows if stf == "all" or r["status"] == stf]
    tabs = " · ".join(f'<a href="/leave?status={k}"{" style=font-weight:700" if k == stf else ""}>{t}</a>'
                      for k, t in (("Pending", "Pending"), ("Approved", "Approved"), ("Declined", "Declined"), ("all", "All")))
    body = (f'<h1>Leave requests</h1><p>{tabs}</p><table class="t"><tr><th>Submitted</th><th>Name</th><th>Role</th><th>Type</th>'
            '<th>From</th><th>To</th><th class=n>Days</th><th>Status</th></tr>')
    for r in rows:
        body += (f'<tr><td>{nice(r["submitted"])}</td><td><a href="/leave/{r["id"]}">{E(r["name"])}</a></td><td>{E(r["role"])}</td>'
                 f'<td>{E(r["kind"])}</td><td>{nice(r["start"])}</td><td>{nice(r["end"])}</td><td class=n>{r["days"]}</td>'
                 f'<td><span class="badge b-{r["status"]}">{r["status"]}</span></td></tr>')
    if not rows:
        body += '<tr><td colspan=8 class="muted">No requests.</td></tr>'
    return page(req, "Leave requests", body + "</table>", "leave")


@route("GET", r"/leave/(\d+)")
def leave_detail(req, rid):
    con = db()
    r = con.execute("SELECT r.*, s.name, s.role, s.leave_balance, s.id sid FROM leave_requests r JOIN staff s ON s.id=r.staff_id WHERE r.id=?",
                    (rid,)).fetchone()
    if not r:
        con.close()
        return redirect("/leave")
    shifts = con.execute("SELECT * FROM assignments WHERE staff_id=? AND deleted=0 AND day BETWEEN ? AND ? ORDER BY day",
                         (r["sid"], r["start"], r["end"])).fetchall()
    con.close()
    body = (f'<p><a href="/leave">&laquo; Leave requests</a></p><h1>{E(r["name"])} · {E(r["kind"])} '
            f'<span class="badge b-{r["status"]}">{r["status"]}</span></h1><div class="two"><div class="card">'
            f'{E(r["role"])}<br><b>{nice(r["start"])} – {nice(r["end"])}</b> ({r["days"]} day{"s" if r["days"] != 1 else ""})<br>'
            f'Submitted {nice(r["submitted"])}<br>Reason: {E(r["reason"])}<br>Annual leave balance now: {r["leave_balance"]:g} days'
            '<h2>Rostered shifts during this leave</h2>'
            + ("".join(f'<div>{dlabel(a["day"])} · {SNAME[a["shift"]]}</div>' for a in shifts) or '<span class="muted">none</span>')
            + '</div><div class="card">')
    if r["status"] == "Pending":
        body += (f'<h2 style="margin-top:0">Decision</h2><form method=post action="/leave/{rid}/decide">'
                 '<label>Comment to the employee (required when declining)</label><textarea name=comment rows=4 style="width:100%"></textarea>'
                 '<p><button name=decision value="Approved">Approve</button> <button class="danger" name=decision value="Declined">Decline</button></p></form>'
                 '<p class="muted">Approving does not change the rota - take the person off their shifts and arrange cover on the Rota page.</p>')
    else:
        body += (f'<h2 style="margin-top:0">{r["status"]}</h2><p>{E(r["decided_by"])} {E(r["decided_at"])}</p>'
                 f'<p>{E(r["comment"]) or "<span class=muted>no comment</span>"}</p>'
                 f'<form method=post action="/leave/{rid}/reopen"><button class="ghost">Undo decision</button></form>')
    return page(req, "Leave request", body + "</div></div>", "leave")


@route("POST", r"/leave/(\d+)/(decide|reopen)")
def leave_decide(req, rid, what):
    con = db()
    r = con.execute("SELECT r.*, s.name FROM leave_requests r JOIN staff s ON s.id=r.staff_id WHERE r.id=?", (rid,)).fetchone()
    if not r:
        con.close()
        return redirect("/leave")
    annual = r["kind"] == "Annual leave"
    if what == "reopen" and r["status"] != "Pending":
        if r["status"] == "Approved" and annual:
            con.execute("UPDATE staff SET leave_balance=leave_balance+? WHERE id=?", (r["days"], r["staff_id"]))
        con.execute("UPDATE leave_requests SET status='Pending', decided_at=NULL, decided_by=NULL, comment='' WHERE id=?", (rid,))
        audit(con, req, "leave decision undone", f"{r['name']} {r['start']}–{r['end']}")
        req.flash("Decision undone; the request is pending again.")
    elif what == "decide" and r["status"] == "Pending":
        dec, comment = req.form.get("decision", ""), req.form.get("comment", "").strip()
        if dec not in ("Approved", "Declined"):
            req.flash("Choose approve or decline.", "err")
        elif dec == "Declined" and not comment:
            req.flash("Please give the reason when you decline a request.", "err")
            con.close()
            return redirect(f"/leave/{rid}")
        else:
            if dec == "Approved" and annual:
                con.execute("UPDATE staff SET leave_balance=leave_balance-? WHERE id=?", (r["days"], r["staff_id"]))
            con.execute("UPDATE leave_requests SET status=?, comment=?, decided_at=?, decided_by=? WHERE id=?",
                        (dec, comment, now(), req.user["username"], rid))
            audit(con, req, f"leave {dec.lower()}", f"{r['name']} {r['start']}–{r['end']}" + (f": {comment}" if comment else ""))
            req.flash(f"{r['name']}'s request {dec.lower()}.")
    con.commit()
    con.close()
    return redirect(f"/leave/{rid}")


POLICY = """
<h2>Rota rules</h2><ol class=policy>
<li><b>Staffing levels.</b> Early (07:00–15:00) 3 staff, Late (14:00–22:00) 3 staff, Night (21:30–07:30) 2 staff. Every shift needs at least one senior carer (SC).</li>
<li><b>One shift a day.</b> Nobody works two shifts on the same day.</li>
<li><b>Rest.</b> At least 11 hours between shifts: no Early the day after a Late or a Night, and no Late the day after a Night.</li>
<li><b>Maximum shifts.</b> Nobody works more shifts in a week than the maximum on their staff record.</li>
<li><b>Availability.</b> Respect the availability notes on the staff record (no nights, nights only, earlies only, not Sundays...).</li>
<li><b>Leave.</b> Nobody is rostered on a day of approved leave.</li>
<li><b>Open shifts</b> are offered first to staff who are below their contracted shifts that week; bank staff after that.</li>
</ol>
<h2>Leave policy</h2><ol class=policy>
<li><b>Notice.</b> Annual leave must be requested at least 14 days before the first day of leave (counted from the date the request was submitted). Requests with less notice are declined.</li>
<li><b>Balance.</b> The days requested must not exceed the employee's remaining annual leave balance.</li>
<li><b>Senior cover.</b> No more than one senior carer may be on leave on any day. Requests are considered in the order they were submitted.</li>
<li><b>Compassionate leave</b> (bereavement, family emergency, up to 3 days) is exempt from the notice rule and does not use the annual leave balance.</li>
<li><b>Cover.</b> When you approve leave, take the person off every shift they are rostered on during the leave and put an eligible colleague (rota rules above) on each of those shifts. If a shift cannot be covered by anyone eligible, decline the request and say so.</li>
<li><b>Declining.</b> Always give the reason in the comment.</li>
</ol>
"""


@route("GET", "/policies")
def policies(req):
    return page(req, "Policies", '<h1>Policies</h1><div class="card">' + POLICY + '<p class="muted">Approved by the registered manager, '
                'Elmbrook House, April 2026.</p></div>', "policies")


@route("GET", "/activity")
def activity(req):
    pg = int(req.q.get("page", "1")) if req.q.get("page", "1").isdigit() else 1
    con = db()
    rows = con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 40 OFFSET ?", ((pg - 1) * 40,)).fetchall()
    n = con.execute("SELECT COUNT(*) n FROM audit").fetchone()["n"]
    con.close()
    body = '<h1>Activity log</h1><table class="t"><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr>'
    body += "".join(f'<tr><td>{E(a["ts"])}</td><td>{E(a["user"])}</td><td>{E(a["action"])}</td><td>{E(a["detail"])}</td></tr>' for a in rows)
    body += f"</table><p>{n} entries · page {pg} "
    if pg > 1:
        body += f'<a href="/activity?page={pg - 1}">&laquo; Newer</a> '
    if pg * 40 < n:
        body += f'<a href="/activity?page={pg + 1}">Older &raquo;</a>'
    return page(req, "Activity", body + "</p>", "activity")


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "RotaDesk/1.8"

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
    ap.add_argument("--port", type=int, default=8131)
    a = ap.parse_args()
    DB = a.db
    con = db()
    con.executescript(RUNTIME_SCHEMA)
    con.close()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
