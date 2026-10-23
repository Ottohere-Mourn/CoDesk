#!/usr/bin/env python3
"""Quillon Talent - Quillon Health's applicant tracking system (single file, Python 3 stdlib only).

    python3 app.py --db ats.db --port 8104          # serves http://127.0.0.1:8104/

http.server + sqlite3, server-rendered HTML, cookie sessions stored in the database. List filters and the calendar
week/person are remembered per session, the candidate form saves every property shown on it, and the interview
calendar warns about (but allows) bookings outside availability or overlapping other interviews.
"""
import argparse
import datetime as dt
import html
import json
import re
import secrets
import sqlite3
import sys
import threading
import traceback
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TITLE = "Quillon Talent"
TODAY = dt.date(2026, 10, 23)  # business date of the seeded data (Friday of week 43)
STAGES = ["Applied", "Phone screen", "Interviewed - awaiting decision", "Hiring manager review", "HM interview",
          "Onsite", "Offer", "Hired", "Rejected", "Withdrawn"]
CLOSED = ("Hired", "Rejected", "Withdrawn")
REASONS = ["Did not pass interview", "Not qualified (screen)", "Withdrew", "Salary expectations", "Position filled"]
ITYPES = ["Phone interview", "Technical interview", "Hiring manager interview", "Onsite loop", "Reference call"]
DURATIONS = [30, 45, 60, 90, 120]
TIMES = [f"{h:02d}:{m:02d}" for h in range(8, 18) for m in (0, 15, 30, 45)]
SOURCES = ["LinkedIn", "Referral", "Careers site", "Indeed", "Agency"]
RECS = ["Strong hire", "Hire", "No hire"]
CRITERIA = ["Technical skills", "Problem solving", "Communication", "Values & collaboration"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
PER_PAGE = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT,
  title TEXT, can_login INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, name TEXT, title TEXT, team TEXT, email TEXT);
CREATE TABLE IF NOT EXISTS avail (id INTEGER PRIMARY KEY, person_id INTEGER, weekday INTEGER, start TEXT, end TEXT);
CREATE TABLE IF NOT EXISTS ooo (id INTEGER PRIMARY KEY, person_id INTEGER, date TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS reqs (id INTEGER PRIMARY KEY, code TEXT, title TEXT, dept TEXT, location TEXT, hm_id INTEGER,
  recruiter_id INTEGER, status TEXT, opened TEXT, plan TEXT);
CREATE TABLE IF NOT EXISTS cands (id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT, location TEXT,
  current_title TEXT, req_id INTEGER, stage TEXT, reason TEXT, source TEXT, applied TEXT, recruiter_id INTEGER,
  availability TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS scorecards (id INTEGER PRIMARY KEY, cand_id INTEGER, person_id INTEGER, round TEXT,
  s1 INTEGER, s2 INTEGER, s3 INTEGER, s4 INTEGER, rec TEXT, notes TEXT, user_id INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS atts (id INTEGER PRIMARY KEY, cand_id INTEGER, filename TEXT, label TEXT, ctype TEXT,
  data BLOB, created TEXT);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, kind TEXT, ref_id INTEGER, user_id INTEGER, body TEXT,
  created TEXT);
CREATE TABLE IF NOT EXISTS interviews (id INTEGER PRIMARY KEY, cand_id INTEGER, kind TEXT, date TEXT, start TEXT,
  minutes INTEGER, notes TEXT, user_id INTEGER, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS panel (interview_id INTEGER, person_id INTEGER);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, cand_id INTEGER, user_id INTEGER, rid TEXT, field TEXT,
  old TEXT, new TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, user_id INTEGER, data TEXT, created TEXT);
"""

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",Ubuntu,Arial,sans-serif;color:#1d2b2a;background:#f2f6f5}
a{color:#0d7a68;text-decoration:none}a:hover{text-decoration:underline}
header{background:#0f4c45;color:#fff;display:flex;align-items:center;padding:0 18px;height:50px;gap:22px}
header .brand{font-weight:700;font-size:17px}header .brand span{color:#7fe0c9;font-weight:400}
header nav a{color:#cfe9e3;padding:15px 8px;display:inline-block}header nav a.on{color:#fff;border-bottom:3px solid #7fe0c9}
header .me{margin-left:auto;color:#cfe9e3}header .me a{color:#fff;margin-left:10px}
main{padding:18px 22px;max-width:1500px;margin:0 auto}h1{font-size:20px;margin:4px 0 14px}h2{font-size:16px;margin:18px 0 8px}
.flash{padding:9px 12px;border-radius:4px;margin-bottom:12px;background:#e1f5ee;border:1px solid #8fd1bd}
.flash.err{background:#fdeee6;border-color:#eab08f}
table.list{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d5e0de}
table.list th{background:#e9f1ef;text-align:left;padding:7px 8px;font-weight:600;border-bottom:1px solid #d5e0de;white-space:nowrap}
table.list td{padding:6px 8px;border-bottom:1px solid #edf2f1;vertical-align:top}table.list tr:hover td{background:#f7fbfa}
.badge{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:600;background:#e3e9e8}
.st-Onsite,.st-Offer,.st-Hired{background:#c9efdf}.st-Rejected,.st-Withdrawn{background:#eceff1;color:#66727a}
.st-Interviewed{background:#ffe6a6}.st-HM,.st-Hiring{background:#d6e6ff}
.layout{display:grid;grid-template-columns:210px 1fr;gap:18px}.side a{display:block;padding:6px 8px;border-radius:4px}
.side a.on{background:#d3efe7;font-weight:600}.side .n{float:right;color:#6b7b79}
.filters{background:#fff;border:1px solid #d5e0de;padding:9px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],input[type=password],select,textarea{font:inherit;padding:5px 7px;border:1px solid #b6c6c3;border-radius:3px;background:#fff}
textarea{width:100%}button,.btn{font:inherit;background:#0d7a68;color:#fff;border:0;border-radius:3px;padding:6px 14px;cursor:pointer;display:inline-block}
.btn:hover{text-decoration:none}button.danger{background:#b3412d}.pager{margin:10px 0;display:flex;gap:6px;align-items:center}
.pager a,.pager b{padding:3px 9px;border:1px solid #d5e0de;background:#fff;border-radius:3px}.pager b{background:#0d7a68;color:#fff}
.card{background:#fff;border:1px solid #d5e0de;border-radius:4px;padding:12px 14px;margin-bottom:12px}
.two{display:grid;grid-template-columns:1fr 300px;gap:18px}.props label{display:block;font-weight:600;margin:9px 0 3px}
.props select{width:100%}.muted{color:#6b7b79;font-size:12px}.att img{max-width:100%;border:1px solid #c5d2cf;margin-top:6px}
.cal{border-collapse:collapse;width:100%;background:#fff;table-layout:fixed}.cal th,.cal td{border:1px solid #dfe8e6;padding:2px 5px;font-size:12px;height:22px}
.cal th{background:#e9f1ef}.cal td.av{background:#dcf5ea}.cal td.busy{background:#f6c9b8;font-weight:600}.cal td.off{background:#eceff1}
.cal td.t{width:60px;color:#6b7b79;background:#fafcfb}.warn{background:#fff4d6;border:1px solid #e8c467;padding:8px 12px;border-radius:4px;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 18px}.grid2 label{font-weight:600;display:block;margin-bottom:3px}
.chk label{font-weight:400;display:inline-block;margin:2px 14px 2px 0}
.login{max-width:360px;margin:90px auto;background:#fff;border:1px solid #d5e0de;padding:26px;border-radius:6px}
.login input{width:100%;margin:4px 0 12px}
"""

DB = None
LOCK = threading.RLock()


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def to_int(s, default=None):
    try:
        v = int(str(s).strip().lstrip("#"))
        return v if abs(v) < 2 ** 62 else default
    except (TypeError, ValueError):
        return default


def q(sql, args=()):
    return DB.execute(sql, args).fetchall()


def q1(sql, args=()):
    return DB.execute(sql, args).fetchone()


def init_schema(con):
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()


def parse_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def mins(t):
    try:
        h, m = str(t).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_date(s):
    try:
        return dt.datetime.fromisoformat(s).strftime("%d %b %Y %H:%M")
    except (TypeError, ValueError):
        return s or ""


def fmt_day(s):
    try:
        return dt.date.fromisoformat(s).strftime("%a %d %b %Y")
    except (TypeError, ValueError):
        return s or ""


def options(items, selected, blank=None):
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for it in items:
        v, lab = it if isinstance(it, tuple) else (it, it)
        sel = " selected" if str(v) == str(selected if selected is not None else "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{esc(lab)}</option>')
    return "".join(out)


def stage_badge(s):
    key = (s or "").split(" ")[0]
    return f'<span class="badge st-{esc(key)}">{esc(s)}</span>'


# ------------------------------------------------------------------------------------------------ request handling
class Handler(BaseHTTPRequestHandler):
    server_version = "QuillonTalent/2.4"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_HEAD(self):
        self.dispatch("GET")

    def dispatch(self, method):
        self.method, self.out_cookies, self.user, self.sess, self.sid = method, [], None, {}, None
        try:
            u = urllib.parse.urlsplit(self.path)
            self.route_path = urllib.parse.unquote(u.path) or "/"
            self.qm = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            self.qs = {k: v[-1] for k, v in self.qm.items()}
            self.fm, self.form = {}, {}
            if method == "POST":
                n = min(to_int(self.headers.get("Content-Length"), 0) or 0, 20_000_000)
                raw = self.rfile.read(n) if n > 0 else b""
                ctype = self.headers.get("Content-Type", "")
                if ctype.startswith("application/x-www-form-urlencoded") or not ctype:
                    self.fm = urllib.parse.parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
                    self.form = {k: v[-1] for k, v in self.fm.items()}
            with LOCK:
                self.load_session()
                for m, rx, fn, public in ROUTES:
                    mt = re.fullmatch(rx, self.route_path)
                    if mt and m == method:
                        if not public and not self.user:
                            return self.redirect("/login?next=" + urllib.parse.quote(self.path))
                        fn(self, *mt.groups())
                        DB.commit()
                        return
                if any(re.fullmatch(rx, self.route_path) for _, rx, _, _ in ROUTES):
                    return self.error_page(405, "Form submissions only", "This address only accepts form submissions.")
                self.error_page(404, "Page not found", "The page you asked for does not exist.")
        except Exception:  # never let one bad request take the ATS down
            traceback.print_exc()
            try:
                DB.rollback()
            except Exception:
                pass
            try:
                self.error_page(500, "Something went wrong", "The request could not be processed. Go back and try again.")
            except Exception:
                pass

    def load_session(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        sid = c["qt_session"].value if "qt_session" in c else None
        if sid:
            row = q1("SELECT * FROM sessions WHERE sid=?", (sid,))
            if row:
                self.sid = sid
                try:
                    self.sess = json.loads(row["data"] or "{}")
                except ValueError:
                    self.sess = {}
                self.user = q1("SELECT * FROM users WHERE id=?", (row["user_id"],))

    def save_session(self):
        if self.sid:
            DB.execute("UPDATE sessions SET data=? WHERE sid=?", (json.dumps(self.sess), self.sid))

    def flash(self, msg, err=False):
        self.sess.setdefault("flash", []).append([msg, err])
        self.save_session()

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        for ck in self.out_cookies:
            self.send_header("Set-Cookie", ck)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def redirect(self, url):
        self.save_session()
        self.send(303, "", headers=[("Location", url)])

    def page(self, title, body, nav=""):
        flashes = self.sess.pop("flash", []) if self.user else []
        self.save_session()
        fl = "".join(f'<div class="flash{" err" if e else ""}">{esc(m)}</div>' for m, e in flashes)
        links = [("cands", "/candidates", "Candidates"), ("reqs", "/reqs", "Requisitions"),
                 ("cal", "/calendar", "Interview calendar"), ("people", "/interviewers", "Interviewers"),
                 ("reports", "/reports", "Reports")]
        navh = "".join(f'<a href="{h}" class="{"on" if k == nav else ""}">{t}</a>' for k, h, t in links)
        me = (f'<div class="me">{esc(self.user["name"])} &middot; {esc(self.user["title"])}'
              f'<a href="/logout">Log out</a></div>') if self.user else ""
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)} - {TITLE}</title>"
               f"<style>{CSS}</style></head><body><header><div class='brand'>Quillon <span>Talent</span></div>"
               f"<nav>{navh if self.user else ''}</nav>{me}</header><main>{fl}{body}</main></body></html>")
        self.send(200, doc)

    def error_page(self, code, title, msg):
        body = f"<h1>{esc(title)}</h1><div class='card'>{esc(msg)}<p><a href='/candidates'>Back to candidates</a></p></div>"
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style>"
               f"</head><body><header><div class='brand'>Quillon <span>Talent</span></div></header>"
               f"<main>{body}</main></body></html>")
        self.send(code, doc)


# ------------------------------------------------------------------------------------------------ login
def login_get(r):
    nxt = r.qs.get("next", "/candidates")
    msg = '<div class="flash err">Wrong username or password.</div>' if r.qs.get("err") else ""
    if r.qs.get("bye"):
        msg = '<div class="flash">You have been logged out.</div>'
    body = (f"<div class='login'><h1>Sign in to Quillon Talent</h1>{msg}<form method='post' action='/login'>"
            f"<input type='hidden' name='next' value='{esc(nxt)}'><label>Username</label>"
            f"<input type='text' name='username' autofocus><label>Password</label><input type='password' name='password'>"
            f"<button type='submit'>Sign in</button></form><p class='muted'>Quillon Health &middot; People team</p></div>")
    r.page("Sign in", body)


def login_post(r):
    u = q1("SELECT * FROM users WHERE username=? AND can_login=1", (r.form.get("username", "").strip().lower(),))
    nxt = r.form.get("next") or "/candidates"
    if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/login"):
        nxt = "/candidates"
    if not u or u["password"] != r.form.get("password", ""):
        return r.redirect("/login?err=1&next=" + urllib.parse.quote(nxt))
    sid = secrets.token_hex(16)
    DB.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], "{}", now()))
    r.sid, r.sess, r.user = sid, {}, u
    r.out_cookies.append(f"qt_session={sid}; Path=/; HttpOnly; SameSite=Lax")
    r.redirect(nxt)


def logout(r):
    if r.sid:
        DB.execute("DELETE FROM sessions WHERE sid=?", (r.sid,))
    r.sid = None
    r.out_cookies.append("qt_session=; Path=/; Max-Age=0")
    r.redirect("/login?bye=1")


def home(r):
    r.redirect("/candidates")


# ------------------------------------------------------------------------------------------------ candidates
VIEWS = {
    "awaiting": ("Awaiting decision", {"stage": "Interviewed - awaiting decision"}),
    "mine": ("My candidates", {"stage": "active", "recruiter": "me"}),
    "active": ("All active", {"stage": "active"}),
    "onsite": ("Onsite", {"stage": "Onsite"}),
    "all": ("All candidates", {"stage": "any"}),
}
DEFAULT_F = {"q": "", "req": "any", "stage": "active", "recruiter": "any", "sort": "updated", "dir": "desc", "page": "1"}
SORTS = {"name": "c.name COLLATE NOCASE", "req": "r.code", "stage": "CASE c.stage " + " ".join(
    f"WHEN '{s}' THEN {i}" for i, s in enumerate(STAGES)) + " END", "source": "c.source", "applied": "c.applied",
    "recruiter": "COALESCE(u.name,'')", "updated": "c.updated"}


def cand_where(f, me):
    where, args = [], []
    st = f.get("stage")
    if st == "active":
        where.append("c.stage NOT IN ('Hired','Rejected','Withdrawn')")
    elif st in STAGES:
        where.append("c.stage=?")
        args.append(st)
    if to_int(f.get("req")):
        where.append("c.req_id=?")
        args.append(to_int(f.get("req")))
    rc = f.get("recruiter")
    if rc == "me":
        where.append("c.recruiter_id=?")
        args.append(me)
    elif to_int(rc):
        where.append("c.recruiter_id=?")
        args.append(to_int(rc))
    text = (f.get("q") or "").strip()
    if text:
        where.append("(c.name LIKE ? OR c.email LIKE ? OR c.current_title LIKE ? OR r.code LIKE ?)")
        args += [f"%{text}%"] * 4
    return (" WHERE " + " AND ".join(where)) if where else "", args


def cands_list(r):
    f = dict(DEFAULT_F, **r.sess.get("cf", {}))
    view = r.qs.get("view")
    if view in VIEWS:
        f = dict(DEFAULT_F, **VIEWS[view][1])
    elif r.qs.get("reset"):
        f = dict(DEFAULT_F)
    elif any(k in r.qs for k in DEFAULT_F):
        for k in DEFAULT_F:
            if k in r.qs:
                f[k] = r.qs[k]
        if "page" not in r.qs:
            f["page"] = "1"
    if f.get("sort") not in SORTS:
        f["sort"] = "updated"
    if f.get("dir") not in ("asc", "desc"):
        f["dir"] = "desc"
    base = "FROM cands c LEFT JOIN reqs r ON r.id=c.req_id LEFT JOIN users u ON u.id=c.recruiter_id"
    where, args = cand_where(f, r.user["id"])
    total = q1(f"SELECT COUNT(*) {base}{where}", args)[0]
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(max(1, to_int(f.get("page"), 1)), pages)
    f["page"] = str(page)
    r.sess["cf"] = f
    r.save_session()
    rows = q(f"SELECT c.*, r.code, r.title AS req_title, u.name AS recruiter {base}{where} ORDER BY {SORTS[f['sort']]} "
             f"{f['dir']}, c.id DESC LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", args)
    side = []
    for key, (label, vf) in VIEWS.items():
        w, a = cand_where(dict(DEFAULT_F, **vf), r.user["id"])
        n = q1(f"SELECT COUNT(*) {base}{w}", a)[0]
        full = dict(DEFAULT_F, **vf)
        on = all(f.get(k) == full[k] for k in ("stage", "req", "recruiter")) and not f["q"]
        side.append(f'<a href="/candidates?view={key}" class="{"on" if on else ""}">{label}<span class="n">{n}</span></a>')
    reqs = q("SELECT id, code, title FROM reqs ORDER BY code")
    recs = q("SELECT id, name FROM users ORDER BY name")
    filt = (f"<form class='filters' method='get' action='/candidates'>"
            f"<input type='text' name='q' value='{esc(f['q'])}' placeholder='Search name, email, title'>"
            f"<select name='req'>{options([('any', 'All requisitions')] + [(x['id'], x['code'] + ' ' + x['title']) for x in reqs], f['req'])}</select>"
            f"<select name='stage'>{options([('active', 'All active stages'), ('any', 'Any stage')] + STAGES, f['stage'])}</select>"
            f"<select name='recruiter'>{options([('any', 'Any recruiter'), ('me', 'Me')] + [(x['id'], x['name']) for x in recs], f['recruiter'])}</select>"
            f"<input type='hidden' name='sort' value='{esc(f['sort'])}'><input type='hidden' name='dir' value='{esc(f['dir'])}'>"
            f"<button type='submit'>Apply</button> <a href='/candidates?reset=1'>Reset</a></form>")

    def link(**kw):
        return "/candidates?" + urllib.parse.urlencode(dict(f, **kw))

    def th(key, label):
        d = "asc" if f["sort"] != key or f["dir"] == "desc" else "desc"
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if f["sort"] == key else ""
        return f'<th><a href="{esc(link(sort=key, dir=d, page=1))}">{label}{arrow}</a></th>'
    trs = "".join(f"<tr><td><a href='/candidates/{c['id']}'>{esc(c['name'])}</a><div class='muted'>{esc(c['current_title'])}</div></td>"
                  f"<td>{esc(c['code'])} <span class='muted'>{esc(c['req_title'])}</span></td><td>{stage_badge(c['stage'])}</td>"
                  f"<td>{esc(c['source'])}</td><td>{esc(c['applied'])}</td><td>{esc(c['recruiter'] or '—')}</td>"
                  f"<td class='muted'>{fmt_date(c['updated'])}</td></tr>" for c in rows) or \
        "<tr><td colspan='7' class='muted'>No candidates match these filters.</td></tr>"
    pager = [f"<span class='muted'>Showing {(page - 1) * PER_PAGE + 1 if total else 0}–{min(total, page * PER_PAGE)} of {total}</span>"]
    if page > 1:
        pager.append(f"<a href='{esc(link(page=page - 1))}'>&laquo; Prev</a>")
    for p in range(1, pages + 1):
        pager.append(f"<b>{p}</b>" if p == page else f"<a href='{esc(link(page=p))}'>{p}</a>")
    if page < pages:
        pager.append(f"<a href='{esc(link(page=page + 1))}'>Next &raquo;</a>")
    body = (f"<div class='layout'><div class='side'><h2 style='margin-top:4px'>Views</h2>{''.join(side)}</div><div><h1>Candidates</h1>"
            f"{filt}<table class='list'><tr>{th('name', 'Candidate')}{th('req', 'Requisition')}{th('stage', 'Stage')}"
            f"{th('source', 'Source')}{th('applied', 'Applied')}{th('recruiter', 'Recruiter')}{th('updated', 'Updated')}</tr>{trs}</table>"
            f"<div class='pager'>{''.join(pager)}</div></div></div>")
    r.page("Candidates", body, "cands")


def panel_names(iid):
    return ", ".join(p["name"] for p in q("SELECT p.name FROM panel x JOIN people p ON p.id=x.person_id WHERE x.interview_id=? "
                                          "ORDER BY p.name", (iid,)))


def cand_view(r, cid):
    c = q1("SELECT c.*, r.code, r.title AS req_title FROM cands c LEFT JOIN reqs r ON r.id=c.req_id WHERE c.id=?", (to_int(cid),))
    if not c:
        return r.error_page(404, "Candidate not found", "This candidate does not exist.")
    people = q("SELECT id, name FROM people ORDER BY name")
    atts = "".join(f"<div class='att card'><b>{esc(a['label'])}</b> &middot; <a href='/att/{a['id']}' target='_blank'>{esc(a['filename'])}</a>"
                   f" <span class='muted'>uploaded {fmt_date(a['created'])}</span><br><img src='/att/{a['id']}' alt='{esc(a['filename'])}'></div>"
                   for a in q("SELECT id, filename, label, created FROM atts WHERE cand_id=? ORDER BY id", (c["id"],)))
    sc = q("SELECT s.*, p.name FROM scorecards s LEFT JOIN people p ON p.id=s.person_id WHERE cand_id=? ORDER BY s.id", (c["id"],))
    sct = "".join(f"<tr><td>{esc(s['name'])}</td><td>{esc(s['round'])}</td>" + "".join(f"<td>{s[k]}</td>" for k in ("s1", "s2", "s3", "s4"))
                  + f"<td>{(s['s1'] + s['s2'] + s['s3'] + s['s4']) / 4:.2f}</td><td>{esc(s['rec'])}</td><td>{esc(s['notes'])}</td></tr>" for s in sc) \
        or "<tr><td colspan='9' class='muted'>No scorecards yet.</td></tr>"
    score_sel = "".join(f"<div><label>{esc(k)}</label><select name='s{i}'>{options([1, 2, 3, 4, 5], '', '—')}</select></div>"
                        for i, k in enumerate(CRITERIA, 1))
    scform = (f"<form method='post' action='/candidates/{c['id']}/scorecard' class='card'><b>Add scorecard</b><div class='grid2' style='margin-top:8px'>"
              f"<div><label>Interviewer</label><select name='interviewer'>{options([(p['id'], p['name']) for p in people], '', '— choose —')}</select></div>"
              f"<div><label>Round</label><select name='round'>{options(ITYPES, 'Phone interview')}</select></div>{score_sel}"
              f"<div><label>Recommendation</label><select name='rec'>{options(RECS, '', '— choose —')}</select></div>"
              f"<div><label>Notes</label><input type='text' name='notes' style='width:100%'></div></div><p><button>Save scorecard</button></p></form>")
    ivs = q("SELECT * FROM interviews WHERE cand_id=? ORDER BY date, start", (c["id"],))
    ivt = "".join(f"<tr><td>{fmt_day(i['date'])}</td><td>{esc(i['start'])}–{hhmm(mins(i['start']) + i['minutes']) if mins(i['start']) is not None else ''}</td>"
                  f"<td>{esc(i['kind'])}</td><td>{esc(panel_names(i['id']))}</td><td><a href='/interviews/{i['id']}'>Edit</a></td></tr>" for i in ivs) \
        or "<tr><td colspan='5' class='muted'>No interviews.</td></tr>"
    nts = "".join(f"<div class='card'><span class='muted'>{esc(n['name'])} &middot; {fmt_date(n['created'])}</span><div style='white-space:pre-wrap'>{esc(n['body'])}</div></div>"
                  for n in q("SELECT n.*, u.name FROM notes n LEFT JOIN users u ON u.id=n.user_id WHERE kind='cand' AND ref_id=? ORDER BY n.id", (c["id"],)))
    ev = q("SELECT e.*, u.name FROM events e LEFT JOIN users u ON u.id=e.user_id WHERE cand_id=? ORDER BY e.id DESC", (c["id"],))
    hist = "".join(f"<li><span class='muted'>{fmt_date(e['ts'])}</span> {esc(e['name'])} changed <b>{esc(e['field'])}</b> from “{esc(e['old'] or '—')}” "
                   f"to “{esc(e['new'] or '—')}”</li>" for e in ev) or "<li>No changes yet.</li>"
    recs = q("SELECT id, name FROM users ORDER BY name")
    body = (f"<p class='muted'><a href='/candidates'>&laquo; Back to candidates</a></p><h1>{esc(c['name'])} {stage_badge(c['stage'])}</h1>"
            f"<div class='two'><div><div class='card'><table><tr><td class='muted' style='width:200px'>Requisition</td><td><a href='/reqs/{c['req_id']}'>{esc(c['code'])} {esc(c['req_title'])}</a></td></tr>"
            f"<tr><td class='muted'>Current title</td><td>{esc(c['current_title'])}</td></tr><tr><td class='muted'>Email / phone</td><td>{esc(c['email'])} &middot; {esc(c['phone'])}</td></tr>"
            f"<tr><td class='muted'>Location</td><td>{esc(c['location'])}</td></tr><tr><td class='muted'>Source / applied</td><td>{esc(c['source'])} &middot; {esc(c['applied'])}</td></tr>"
            f"<tr><td class='muted'>Candidate availability</td><td><b>{esc(c['availability'] or '—')}</b></td></tr></table></div>"
            f"<h2>Attachments</h2>{atts or '<p class=muted>No attachments.</p>'}"
            f"<h2>Scorecards</h2><table class='list'><tr><th>Interviewer</th><th>Round</th>" + "".join(f"<th>{esc(k)}</th>" for k in CRITERIA) +
            f"<th>Avg</th><th>Recommendation</th><th>Notes</th></tr>{sct}</table>{scform}"
            f"<h2>Interviews</h2><table class='list'><tr><th>Date</th><th>Time</th><th>Type</th><th>Interviewers</th><th></th></tr>{ivt}</table>"
            f"<p><a class='btn' href='/interviews/new?candidate={c['id']}'>Schedule interview</a></p>"
            f"<h2>Notes</h2>{nts}<form method='post' action='/candidates/{c['id']}/note'><textarea name='body' rows='3'></textarea><p><button>Add note</button></p></form>"
            f"<h2>History</h2><ul class='muted'>{hist}</ul></div>"
            f"<form method='post' action='/candidates/{c['id']}' class='props card'><b>Candidate status</b>"
            f"<label>Stage</label><select name='stage'>{options(STAGES, c['stage'])}</select>"
            f"<label>Rejection reason</label><select name='reason'>{options(REASONS, c['reason'], '—')}</select>"
            f"<label>Recruiter</label><select name='recruiter'>{options([(x['id'], x['name']) for x in recs], c['recruiter_id'], '—')}</select>"
            f"<p><button type='submit'>Save</button></p><p class='muted'>Saving stores every field in this box.</p></form></div>")
    r.page(c["name"], body, "cands")


def record(cid, uid, rid, field, old, new):
    if (old or "") != (new or ""):
        DB.execute("INSERT INTO events (cand_id,user_id,rid,field,old,new,ts) VALUES (?,?,?,?,?,?,?)",
                   (cid, uid, rid, field, None if old is None else str(old), None if new is None else str(new), now()))
        return True
    return False


def cand_update(r, cid):
    c = q1("SELECT * FROM cands WHERE id=?", (to_int(cid),))
    if not c:
        return r.error_page(404, "Candidate not found", "This candidate does not exist.")
    stage = r.form.get("stage") if r.form.get("stage") in STAGES else c["stage"]
    reason = r.form.get("reason") if r.form.get("reason") in REASONS else None
    rec = to_int(r.form.get("recruiter"))
    rec = rec if rec and q1("SELECT id FROM users WHERE id=?", (rec,)) else None
    if stage == "Rejected" and not reason:
        r.flash("Choose a rejection reason before moving a candidate to Rejected. Nothing was saved.", True)
        return r.redirect(f"/candidates/{c['id']}")
    rid, n = secrets.token_hex(4), 0
    for col, new in (("stage", stage), ("reason", reason), ("recruiter_id", rec)):
        if record(c["id"], r.user["id"], rid, {"recruiter_id": "recruiter"}.get(col, col), c[col], new):
            DB.execute(f"UPDATE cands SET {col}=? WHERE id=?", (new, c["id"]))
            n += 1
    if n:
        DB.execute("UPDATE cands SET updated=? WHERE id=?", (now(), c["id"]))
    r.flash(f"Saved {c['name']}." if n else "No changes.")
    r.redirect(f"/candidates/{c['id']}")


def scorecard_add(r, cid):
    c = q1("SELECT * FROM cands WHERE id=?", (to_int(cid),))
    if not c:
        return r.error_page(404, "Candidate not found", "This candidate does not exist.")
    pid = to_int(r.form.get("interviewer"))
    scores = [to_int(r.form.get(f"s{i}")) for i in range(1, 5)]
    if not (pid and q1("SELECT id FROM people WHERE id=?", (pid,))) or any(s not in (1, 2, 3, 4, 5) for s in scores) \
            or r.form.get("rec") not in RECS:
        r.flash("A scorecard needs an interviewer, all four scores (1-5) and a recommendation. Nothing was saved.", True)
        return r.redirect(f"/candidates/{c['id']}")
    rnd = r.form.get("round") if r.form.get("round") in ITYPES else "Phone interview"
    DB.execute("INSERT INTO scorecards (cand_id,person_id,round,s1,s2,s3,s4,rec,notes,user_id,created) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (c["id"], pid, rnd, *scores, r.form["rec"], r.form.get("notes", "")[:2000], r.user["id"], now()))
    DB.execute("UPDATE cands SET updated=? WHERE id=?", (now(), c["id"]))
    r.flash("Scorecard saved.")
    r.redirect(f"/candidates/{c['id']}")


def note_add(r, kind, ref):
    body = (r.form.get("body") or "").strip()
    tbl, back = ("cands", "/candidates/") if kind == "cand" else ("reqs", "/reqs/")
    if not q1(f"SELECT id FROM {tbl} WHERE id=?", (to_int(ref),)):
        return r.error_page(404, "Not found", "This record does not exist.")
    if body:
        DB.execute("INSERT INTO notes (kind,ref_id,user_id,body,created) VALUES (?,?,?,?,?)", (kind, to_int(ref), r.user["id"], body[:5000], now()))
        r.flash("Note added.")
    else:
        r.flash("The note is empty.", True)
    r.redirect(back + str(to_int(ref)))


def attachment(r, aid):
    a = q1("SELECT * FROM atts WHERE id=?", (to_int(aid),))
    if not a:
        return r.error_page(404, "Attachment not found", "This attachment does not exist.")
    r.send(200, a["data"], a["ctype"] or "application/octet-stream", [("Content-Disposition", f'inline; filename="{a["filename"]}"')])


# ------------------------------------------------------------------------------------------------ requisitions / people
def reqs_list(r):
    rows = q("SELECT r.*, p.name AS hm, u.name AS recruiter, (SELECT COUNT(*) FROM cands c WHERE c.req_id=r.id AND c.stage NOT IN "
             "('Hired','Rejected','Withdrawn')) AS n FROM reqs r LEFT JOIN people p ON p.id=r.hm_id LEFT JOIN users u ON u.id=r.recruiter_id ORDER BY r.code")
    trs = "".join(f"<tr><td><a href='/reqs/{x['id']}'>{esc(x['code'])}</a></td><td>{esc(x['title'])}</td><td>{esc(x['dept'])}</td>"
                  f"<td>{esc(x['hm'])}</td><td>{esc(x['recruiter'])}</td><td>{esc(x['status'])}</td><td>{x['n']}</td></tr>" for x in rows)
    r.page("Requisitions", "<h1>Requisitions</h1><table class='list'><tr><th>Req</th><th>Title</th><th>Department</th><th>Hiring manager</th>"
           f"<th>Recruiter</th><th>Status</th><th>Active candidates</th></tr>{trs}</table>", "reqs")


def req_view(r, rid):
    x = q1("SELECT r.*, p.name AS hm, u.name AS recruiter FROM reqs r LEFT JOIN people p ON p.id=r.hm_id "
           "LEFT JOIN users u ON u.id=r.recruiter_id WHERE r.id=?", (to_int(rid),))
    if not x:
        return r.error_page(404, "Requisition not found", "This requisition does not exist.")
    cs = q("SELECT * FROM cands WHERE req_id=? ORDER BY CASE stage " + " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(STAGES))
           + " END, name", (x["id"],))
    trs = "".join(f"<tr><td><a href='/candidates/{c['id']}'>{esc(c['name'])}</a></td><td>{stage_badge(c['stage'])}</td>"
                  f"<td>{esc(c['source'])}</td><td>{esc(c['applied'])}</td></tr>" for c in cs)
    nts = "".join(f"<div class='card'><span class='muted'>{esc(n['name'])} &middot; {fmt_date(n['created'])}</span><div style='white-space:pre-wrap'>{esc(n['body'])}</div></div>"
                  for n in q("SELECT n.*, u.name FROM notes n LEFT JOIN users u ON u.id=n.user_id WHERE kind='req' AND ref_id=? ORDER BY n.id", (x["id"],)))
    body = (f"<p class='muted'><a href='/reqs'>&laquo; Requisitions</a></p><h1>{esc(x['code'])} · {esc(x['title'])}</h1>"
            f"<div class='card'><table><tr><td class='muted' style='width:200px'>Department / location</td><td>{esc(x['dept'])} &middot; {esc(x['location'])}</td></tr>"
            f"<tr><td class='muted'>Hiring manager</td><td>{esc(x['hm'])}</td></tr><tr><td class='muted'>Recruiter</td><td>{esc(x['recruiter'])}</td></tr>"
            f"<tr><td class='muted'>Status / opened</td><td>{esc(x['status'])} &middot; {esc(x['opened'])}</td></tr>"
            f"<tr><td class='muted'>Interview plan</td><td style='white-space:pre-wrap'>{esc(x['plan'])}</td></tr></table></div>"
            f"<h2>Candidates</h2><table class='list'><tr><th>Name</th><th>Stage</th><th>Source</th><th>Applied</th></tr>{trs}</table>"
            f"<h2>Notes for the hiring team</h2>{nts}<form method='post' action='/reqs/{x['id']}/note'><textarea name='body' rows='4'></textarea>"
            f"<p><button>Add note</button></p></form>")
    r.page(x["code"], body, "reqs")


def people_list(r):
    rows = q("SELECT * FROM people ORDER BY name")
    trs = []
    for p in rows:
        av = {}
        for a in q("SELECT * FROM avail WHERE person_id=? ORDER BY weekday, start", (p["id"],)):
            av.setdefault(a["weekday"], []).append(f"{a['start']}–{a['end']}")
        off = "<br>".join(f"{fmt_day(o['date'])} ({esc(o['reason'])})" for o in q("SELECT * FROM ooo WHERE person_id=? ORDER BY date", (p["id"],)))
        trs.append(f"<tr><td><b>{esc(p['name'])}</b><div class='muted'>{esc(p['title'])}</div></td><td>{esc(p['team'])}</td>"
                   + "".join(f"<td>{'<br>'.join(av.get(d, [])) or '<span class=muted>—</span>'}</td>" for d in range(5))
                   + f"<td>{off or '<span class=muted>—</span>'}</td><td><a href='/calendar?who={p['id']}'>Calendar</a></td></tr>")
    body = ("<h1>Interviewers</h1><p class='muted'>Weekly interview availability (Eastern Time). Interviews must start and end inside "
            "these windows. Out-of-office days override the weekly availability.</p><table class='list'><tr><th>Interviewer</th><th>Team</th>"
            + "".join(f"<th>{d}</th>" for d in DAYS) + f"<th>Out of office</th><th></th></tr>{''.join(trs)}</table>")
    r.page("Interviewers", body, "people")


# ------------------------------------------------------------------------------------------------ calendar / interviews
def problems(date, start, minutes, pids, exclude=None):
    """Warnings for a booking: outside availability, out of office, overlaps."""
    out, s, e = [], mins(start), mins(start) + minutes
    d = dt.date.fromisoformat(date)
    for pid in pids:
        p = q1("SELECT name FROM people WHERE id=?", (pid,))
        if not p:
            continue
        o = q1("SELECT reason FROM ooo WHERE person_id=? AND date=?", (pid, date))
        if o:
            out.append(f"{p['name']} is out of office on {fmt_day(date)} ({o['reason']}).")
        elif not q1("SELECT id FROM avail WHERE person_id=? AND weekday=? AND start<=? AND end>=?", (pid, d.weekday(), hhmm(s), hhmm(e))):
            out.append(f"{hhmm(s)}–{hhmm(e)} on {fmt_day(date)} is outside {p['name']}'s interview availability.")
        for i in q("SELECT i.*, c.name FROM interviews i JOIN panel x ON x.interview_id=i.id LEFT JOIN cands c ON c.id=i.cand_id "
                   "WHERE x.person_id=? AND i.date=? AND i.id<>?", (pid, date, exclude or -1)):
            js = mins(i["start"])
            if js is not None and js < e and s < js + i["minutes"]:
                out.append(f"{p['name']} already has an interview {i['start']}–{hhmm(js + i['minutes'])} ({i['name']}, {i['kind']}).")
    return out


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def calendar(r):
    cal = r.sess.get("cal", {})
    week = parse_date(r.qs.get("week")) or parse_date(cal.get("week")) or monday(TODAY)
    week = monday(week) if 2000 <= week.year <= 2100 else monday(TODAY)
    who = r.qs.get("who", cal.get("who", ""))
    who = str(to_int(who)) if to_int(who) and q1("SELECT id FROM people WHERE id=?", (to_int(who),)) else "all"
    r.sess["cal"] = {"week": week.isoformat(), "who": who}
    r.save_session()
    days = [week + dt.timedelta(days=i) for i in range(5)]
    people = q("SELECT id, name FROM people ORDER BY name")
    nav = (f"<form class='filters' method='get' action='/calendar'><a href='/calendar?week={(week - dt.timedelta(days=7)).isoformat()}'>&laquo; Previous week</a>"
           f"<b>Week of {week.strftime('%d %b %Y')}</b><a href='/calendar?week={(week + dt.timedelta(days=7)).isoformat()}'>Next week &raquo;</a>"
           f"<span style='margin-left:20px'>Interviewer</span><select name='who'>{options([('all', 'All interviewers (list only)')] + [(p['id'], p['name']) for p in people], who)}</select>"
           f"<input type='hidden' name='week' value='{week.isoformat()}'><button>Show</button>"
           f"<a class='btn' style='margin-left:auto' href='/interviews/new'>+ Schedule interview</a></form>")
    grid = ""
    if who != "all":
        pid = int(who)
        pname = q1("SELECT name FROM people WHERE id=?", (pid,))["name"]
        av = q("SELECT * FROM avail WHERE person_id=?", (pid,))
        offs = {o["date"]: o["reason"] for o in q("SELECT * FROM ooo WHERE person_id=?", (pid,))}
        books = {d.isoformat(): q("SELECT i.*, c.name FROM interviews i JOIN panel x ON x.interview_id=i.id LEFT JOIN cands c ON c.id=i.cand_id "
                                  "WHERE x.person_id=? AND i.date=? ORDER BY i.start", (pid, d.isoformat())) for d in days}
        head = "<tr><th class='t'></th>" + "".join(f"<th>{d.strftime('%a %d %b')}" + (f"<br><span class='muted'>Out of office: {esc(offs[d.isoformat()])}</span>"
                                                                                       if d.isoformat() in offs else "") + "</th>" for d in days) + "</tr>"
        rows = []
        for t in range(8 * 60, 18 * 60, 30):
            cells = [f"<td class='t'>{hhmm(t)}</td>"]
            for d in days:
                ds = d.isoformat()
                hit = [b for b in books[ds] if mins(b["start"]) is not None and mins(b["start"]) < t + 30 and t < mins(b["start"]) + b["minutes"]]
                if hit:
                    b = hit[0]
                    lab = f"{b['start']}–{hhmm(mins(b['start']) + b['minutes'])} {b['name']} ({b['kind']})" if mins(b["start"]) >= t else "″"
                    cells.append(f"<td class='busy' title='{esc(b['kind'])}'><a href='/interviews/{b['id']}'>{esc(lab)}</a></td>")
                elif ds not in offs and any(a["weekday"] == d.weekday() and mins(a["start"]) <= t and t + 30 <= mins(a["end"]) for a in av):
                    cells.append("<td class='av'>available</td>")
                else:
                    cells.append("<td class='off'></td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        grid = f"<h2>{esc(pname)}</h2><table class='cal'>{head}{''.join(rows)}</table><p class='muted'>Green = interview availability, red = booked. Grid in 30-minute rows; check exact times in the list below.</p>"
    ivs = q("SELECT i.*, c.name, c.id AS cid FROM interviews i LEFT JOIN cands c ON c.id=i.cand_id WHERE i.date BETWEEN ? AND ? ORDER BY i.date, i.start",
            (days[0].isoformat(), days[-1].isoformat()))
    trs = "".join(f"<tr><td>{fmt_day(i['date'])}</td><td>{esc(i['start'])}–{hhmm(mins(i['start']) + i['minutes']) if mins(i['start']) is not None else ''}</td>"
                  f"<td><a href='/candidates/{i['cid']}'>{esc(i['name'])}</a></td><td>{esc(i['kind'])}</td><td>{esc(panel_names(i['id']))}</td>"
                  f"<td><a href='/interviews/{i['id']}'>Edit</a></td></tr>" for i in ivs) or "<tr><td colspan='6' class='muted'>No interviews this week.</td></tr>"
    body = (f"<h1>Interview calendar</h1>{nav}{grid}<h2>All interviews this week</h2><table class='list'><tr><th>Date</th><th>Time</th><th>Candidate</th>"
            f"<th>Type</th><th>Interviewers</th><th></th></tr>{trs}</table>")
    r.page("Interview calendar", body, "cal")


def interview_form(r, i=None, pre=None):
    pre = pre or {}
    cands = q("SELECT c.id, c.name, r.code FROM cands c LEFT JOIN reqs r ON r.id=c.req_id WHERE c.stage NOT IN ('Hired','Rejected','Withdrawn') "
              + ("OR c.id=? " if i else "") + "ORDER BY c.name", (i["cand_id"],) if i else ())
    people = q("SELECT id, name, title FROM people ORDER BY name")
    sel_panel = {x["person_id"] for x in q("SELECT person_id FROM panel WHERE interview_id=?", (i["id"],))} if i else set()
    cur = {"candidate": i["cand_id"] if i else pre.get("candidate", ""), "kind": i["kind"] if i else "", "date": i["date"] if i else "",
           "start": i["start"] if i else "", "minutes": i["minutes"] if i else 60, "notes": i["notes"] if i else ""}
    chk = "".join(f"<label><input type='checkbox' name='panel' value='{p['id']}'{' checked' if p['id'] in sel_panel else ''}> {esc(p['name'])} "
                  f"<span class='muted'>{esc(p['title'])}</span></label>" for p in people)
    action = f"/interviews/{i['id']}" if i else "/interviews/new"
    body = (f"<p class='muted'><a href='/calendar'>&laquo; Interview calendar</a></p><h1>{'Edit interview' if i else 'Schedule interview'}</h1>"
            f"<form method='post' action='{action}' class='card'><div class='grid2'>"
            f"<div><label>Candidate</label><select name='candidate'>{options([(c['id'], c['name'] + ' — ' + (c['code'] or '')) for c in cands], cur['candidate'], '— choose —')}</select></div>"
            f"<div><label>Interview type</label><select name='kind'>{options(ITYPES, cur['kind'], '— choose —')}</select></div>"
            f"<div><label>Date (YYYY-MM-DD)</label><input type='text' name='date' value='{esc(cur['date'])}' placeholder='2026-10-26'></div>"
            f"<div><label>Start time (ET)</label><select name='start'>{options(TIMES, cur['start'], '— choose —')}</select></div>"
            f"<div><label>Duration</label><select name='minutes'>{options([(m, f'{m} minutes') for m in DURATIONS], cur['minutes'])}</select></div>"
            f"<div><label>Notes</label><input type='text' name='notes' value='{esc(cur['notes'])}' style='width:100%'></div></div>"
            f"<p><b>Interviewers</b></p><div class='chk'>{chk}</div><p><button type='submit'>Save interview</button></p></form>")
    if i:
        body += (f"<form method='post' action='/interviews/{i['id']}/cancel' class='card'>Cancelling removes the interview from everyone's calendar. "
                 f"<button class='danger'>Cancel interview</button></form>")
    r.page("Interview", body, "cal")


def interview_new(r):
    interview_form(r, None, {"candidate": to_int(r.qs.get("candidate"), "")})


def interview_edit(r, iid):
    i = q1("SELECT * FROM interviews WHERE id=?", (to_int(iid),))
    if not i:
        return r.error_page(404, "Interview not found", "This interview does not exist (it may have been cancelled).")
    interview_form(r, i)


def interview_save(r, iid=None):
    i = q1("SELECT * FROM interviews WHERE id=?", (to_int(iid),)) if iid else None
    if iid and not i:
        return r.error_page(404, "Interview not found", "This interview does not exist (it may have been cancelled).")
    back = f"/interviews/{i['id']}" if i else "/interviews/new"
    cid = to_int(r.form.get("candidate"))
    d = parse_date(r.form.get("date"))
    start = r.form.get("start") if r.form.get("start") in TIMES else None
    minutes = to_int(r.form.get("minutes")) if to_int(r.form.get("minutes")) in DURATIONS else None
    pids = sorted({to_int(x) for x in r.fm.get("panel", []) if to_int(x) and q1("SELECT id FROM people WHERE id=?", (to_int(x),))})
    errs = []
    if not (cid and q1("SELECT id FROM cands WHERE id=?", (cid,))):
        errs.append("choose a candidate")
    if r.form.get("kind") not in ITYPES:
        errs.append("choose an interview type")
    if not d:
        errs.append("enter the date as YYYY-MM-DD")
    if not start or not minutes:
        errs.append("choose a start time and duration")
    if not pids:
        errs.append("tick at least one interviewer")
    if errs:
        r.flash("Not saved: " + "; ".join(errs) + ".", True)
        return r.redirect(back + (f"?candidate={cid}" if cid and not i else ""))
    if d.weekday() > 4:
        r.flash("Not saved: interviews can only be scheduled Monday to Friday.", True)
        return r.redirect(back)
    warn = problems(d.isoformat(), start, minutes, pids, i["id"] if i else None)
    if i:
        DB.execute("UPDATE interviews SET cand_id=?, kind=?, date=?, start=?, minutes=?, notes=?, updated=? WHERE id=?",
                   (cid, r.form["kind"], d.isoformat(), start, minutes, r.form.get("notes", "")[:500], now(), i["id"]))
        DB.execute("DELETE FROM panel WHERE interview_id=?", (i["id"],))
        new_id = i["id"]
    else:
        new_id = DB.execute("INSERT INTO interviews (cand_id,kind,date,start,minutes,notes,user_id,created,updated) VALUES (?,?,?,?,?,?,?,?,?)",
                            (cid, r.form["kind"], d.isoformat(), start, minutes, r.form.get("notes", "")[:500], r.user["id"], now(), now())).lastrowid
    for p in pids:
        DB.execute("INSERT INTO panel VALUES (?,?)", (new_id, p))
    DB.execute("UPDATE cands SET updated=? WHERE id=?", (now(), cid))
    r.flash(f"Interview saved for {fmt_day(d.isoformat())} {start}.")
    for w in warn:
        r.flash("Warning: " + w, True)
    r.redirect(f"/candidates/{cid}")


def interview_cancel(r, iid):
    i = q1("SELECT * FROM interviews WHERE id=?", (to_int(iid),))
    if not i:
        return r.error_page(404, "Interview not found", "This interview does not exist (it may have been cancelled).")
    DB.execute("DELETE FROM panel WHERE interview_id=?", (i["id"],))
    DB.execute("DELETE FROM interviews WHERE id=?", (i["id"],))
    r.flash("Interview cancelled.")
    r.redirect(f"/candidates/{i['cand_id']}")


# ------------------------------------------------------------------------------------------------ reports
def reports(r):
    d1 = parse_date(r.qs.get("from")) or TODAY.replace(day=1)
    d2 = parse_date(r.qs.get("to")) or TODAY
    if d2 < d1:
        d1, d2 = d2, d1
    if not (2000 <= d1.year <= 2100 and 2000 <= d2.year <= 2100):
        d1, d2 = TODAY.replace(day=1), TODAY
    reqs = q("SELECT * FROM reqs ORDER BY code")
    cnt = {(x["req_id"], x["source"]): x["n"] for x in q("SELECT req_id, source, COUNT(*) AS n FROM cands WHERE applied BETWEEN ? AND ? "
                                                      "GROUP BY req_id, source", (d1.isoformat(), d2.isoformat()))}
    rows = []
    for x in reqs:
        vals = [cnt.get((x["id"], s), 0) for s in SOURCES]
        rows.append(f"<tr><td>{esc(x['code'])} {esc(x['title'])}</td>" + "".join(f"<td>{v}</td>" for v in vals) + f"<td><b>{sum(vals)}</b></td></tr>")
    tot = [sum(cnt.get((x["id"], s), 0) for x in reqs) for s in SOURCES]
    rows.append("<tr><td><b>Total</b></td>" + "".join(f"<td><b>{v}</b></td>" for v in tot) + f"<td><b>{sum(tot)}</b></td></tr>")
    pipe = []
    for x in reqs:
        c = {s["stage"]: s["n"] for s in q("SELECT stage, COUNT(*) AS n FROM cands WHERE req_id=? GROUP BY stage", (x["id"],))}
        pipe.append(f"<tr><td>{esc(x['code'])}</td>" + "".join(f"<td>{c.get(s, 0)}</td>" for s in STAGES) + "</tr>")
    body = (f"<h1>Reports</h1><form class='filters' method='get' action='/reports'><b>Applications received</b> from "
            f"<input type='text' name='from' value='{d1.isoformat()}' size='11'> to <input type='text' name='to' value='{d2.isoformat()}' size='11'>"
            f"<button>Run report</button><span class='muted'>dates as YYYY-MM-DD, both inclusive</span></form>"
            f"<h2>Applications received {d1.strftime('%d %b %Y')} – {d2.strftime('%d %b %Y')}, by requisition and source</h2>"
            f"<table class='list'><tr><th>Requisition</th>" + "".join(f"<th>{s}</th>" for s in SOURCES) + f"<th>Total</th></tr>{''.join(rows)}</table>"
            f"<h2>Current pipeline by stage</h2><table class='list'><tr><th>Req</th>" + "".join(f"<th>{esc(s)}</th>" for s in STAGES) + f"</tr>{''.join(pipe)}</table>")
    r.page("Reports", body, "reports")


ROUTES = [
    ("GET", r"/login", login_get, True), ("POST", r"/login", login_post, True), ("GET", r"/logout", logout, True),
    ("GET", r"/", home, False), ("GET", r"/candidates", cands_list, False), ("GET", r"/candidates/(\d+)", cand_view, False),
    ("POST", r"/candidates/(\d+)", cand_update, False), ("POST", r"/candidates/(\d+)/scorecard", scorecard_add, False),
    ("POST", r"/candidates/(\d+)/note", lambda r, i: note_add(r, "cand", i), False), ("GET", r"/att/(\d+)", attachment, False),
    ("GET", r"/reqs", reqs_list, False), ("GET", r"/reqs/(\d+)", req_view, False),
    ("POST", r"/reqs/(\d+)/note", lambda r, i: note_add(r, "req", i), False), ("GET", r"/interviewers", people_list, False),
    ("GET", r"/calendar", calendar, False), ("GET", r"/interviews/new", interview_new, False),
    ("POST", r"/interviews/new", interview_save, False), ("GET", r"/interviews/(\d+)", interview_edit, False),
    ("POST", r"/interviews/(\d+)", interview_save, False), ("POST", r"/interviews/(\d+)/cancel", interview_cancel, False),
    ("GET", r"/reports", reports, False),
]


def make_server(db_path, host="127.0.0.1", port=8104):
    global DB
    DB = sqlite3.connect(db_path, check_same_thread=False)
    init_schema(DB)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8104)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = make_server(a.db, a.host, a.port)
    print(f"{TITLE} on http://{a.host}:{a.port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
