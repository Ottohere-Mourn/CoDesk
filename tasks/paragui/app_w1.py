#!/usr/bin/env python3
"""Larkspur Support Desk - the support team's internal help desk (single file, Python 3 stdlib only).

    python3 app.py --db desk.db --port 8101          # serves http://127.0.0.1:8101/

http.server + sqlite3, server-rendered HTML, cookie sessions stored in the database. List filters are remembered
per session (like most help desks do), the ticket form saves every property shown on it, and every change is
written to the ticket history.
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

TITLE = "Larkspur Support Desk"
STATUSES = ["New", "Open", "Pending", "On-hold", "Solved", "Closed"]
PRIORITIES = ["Low", "Normal", "High", "Urgent"]
TEAMS = ["Billing", "Technical", "Accounts"]
SLA = {"Urgent": "1 hour", "High": "4 hours", "Normal": "1 business day", "Low": "3 business days"}
PER_PAGE = 15

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT,
  team TEXT, title TEXT, ooo_until TEXT, backup_id INTEGER, can_login INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS orgs (id INTEGER PRIMARY KEY, name TEXT, plan TEXT, domain TEXT, phone TEXT,
  account_manager TEXT, engineer_id INTEGER, customer_since TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, subject TEXT, requester TEXT, requester_email TEXT,
  org_id INTEGER, channel TEXT, impact TEXT, status TEXT, priority TEXT, team TEXT, assignee_id INTEGER,
  tags TEXT DEFAULT '', created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, ticket_id INTEGER, author TEXT, user_id INTEGER,
  public INTEGER, body TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS attachments (id INTEGER PRIMARY KEY, ticket_id INTEGER, comment_id INTEGER,
  filename TEXT, ctype TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ticket_id INTEGER, user_id INTEGER, rid TEXT,
  field TEXT, old TEXT, new TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS kb (id INTEGER PRIMARY KEY, code TEXT UNIQUE, title TEXT, category TEXT, body TEXT,
  updated TEXT);
CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, body TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, user_id INTEGER, data TEXT, created TEXT);
"""

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",Ubuntu,Arial,sans-serif;color:#1f2933;background:#f3f5f8}
a{color:#1d5fbf;text-decoration:none}a:hover{text-decoration:underline}
header{background:#18324f;color:#fff;display:flex;align-items:center;padding:0 18px;height:48px;gap:22px}
header .brand{font-weight:700;font-size:16px;letter-spacing:.2px}header .brand span{color:#7cc4ff}
header nav a{color:#d6e4f5;padding:14px 8px;display:inline-block}header nav a.on{color:#fff;border-bottom:3px solid #7cc4ff}
header .me{margin-left:auto;color:#d6e4f5}header .me a{color:#fff;margin-left:10px}
main{padding:18px 22px;max-width:1500px;margin:0 auto}h1{font-size:20px;margin:4px 0 14px}h2{font-size:16px;margin:18px 0 8px}
.flash{padding:9px 12px;border-radius:4px;margin-bottom:12px;background:#e3f4e8;border:1px solid #9fd3ad}
.flash.err{background:#fde8e8;border-color:#f0a5a5}
table.list{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d9dee5}
table.list th{background:#eef1f5;text-align:left;padding:7px 8px;font-weight:600;border-bottom:1px solid #d9dee5;white-space:nowrap}
table.list td{padding:6px 8px;border-bottom:1px solid #edf0f3;vertical-align:top}table.list tr:hover td{background:#f8fbff}
.badge{display:inline-block;padding:1px 7px;border-radius:9px;font-size:12px;font-weight:600;background:#e4e7eb}
.s-New{background:#ffe7a8}.s-Open{background:#ffd2cc}.s-Pending{background:#cfe3ff}.s-On-hold{background:#e0d4f7}
.s-Solved{background:#d3f0dc}.s-Closed{background:#e4e7eb;color:#55606e}.p-Urgent{background:#c62828;color:#fff}
.p-High{background:#f4a261}.p-Normal{background:#dfe6ee}.p-Low{background:#eef2f6;color:#5b6b7c}
.plan-Enterprise{background:#18324f;color:#fff}.plan-Business{background:#7cc4ff}.plan-Starter{background:#e4e7eb}
.layout{display:grid;grid-template-columns:200px 1fr;gap:18px}.side a{display:block;padding:6px 8px;border-radius:4px}
.side a.on{background:#dbe9fb;font-weight:600}.side .n{float:right;color:#6b7785}
.filters{background:#fff;border:1px solid #d9dee5;padding:9px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],input[type=password],select,textarea{font:inherit;padding:5px 7px;border:1px solid #b9c2cd;border-radius:3px;background:#fff}
textarea{width:100%}button,.btn{font:inherit;background:#1d5fbf;color:#fff;border:0;border-radius:3px;padding:6px 14px;cursor:pointer}
button.sec{background:#e4e9f0;color:#1f2933}.pager{margin:10px 0;display:flex;gap:6px;align-items:center}
.pager a,.pager b{padding:3px 9px;border:1px solid #d9dee5;background:#fff;border-radius:3px}.pager b{background:#1d5fbf;color:#fff}
.card{background:#fff;border:1px solid #d9dee5;border-radius:4px;padding:12px 14px;margin-bottom:12px}
.tk{display:grid;grid-template-columns:1fr 300px;gap:18px}.props label{display:block;font-weight:600;margin:9px 0 3px}
.props select,.props input{width:100%}.muted{color:#6b7785;font-size:12px}
.c{border:1px solid #d9dee5;border-radius:4px;padding:10px 12px;margin-bottom:10px;background:#fff}
.c.pub{border-left:4px solid #1d5fbf}.c.int{background:#fff8dc;border-left:4px solid #e0b400}.c.cust{border-left:4px solid #8a98a8}
.c pre{white-space:pre-wrap;font:inherit;margin:6px 0 0}.att img{max-width:100%;border:1px solid #c7ced8;margin-top:6px}
.bulk{background:#fff;border:1px solid #d9dee5;padding:9px;margin-top:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.kb h3{font-size:15px;margin:14px 0 4px}.kb table{border-collapse:collapse}.kb td,.kb th{border:1px solid #cdd4dd;padding:4px 8px}
.login{max-width:360px;margin:90px auto;background:#fff;border:1px solid #d9dee5;padding:26px;border-radius:6px}
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


def norm_tags(s):
    out = []
    for t in re.split(r"[,\s]+", (s or "").lower()):
        t = re.sub(r"[^a-z0-9_\-]", "", t)
        if t and t not in out:
            out.append(t)
    return ", ".join(out)


def fmt_date(s):
    try:
        return dt.datetime.fromisoformat(s).strftime("%d %b %Y %H:%M")
    except (TypeError, ValueError):
        return s or ""


def options(items, selected, blank=None):
    """items: list of (value, label) or plain values."""
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for it in items:
        v, lab = it if isinstance(it, tuple) else (it, it)
        sel = " selected" if str(v) == str(selected if selected is not None else "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{esc(lab)}</option>')
    return "".join(out)


def badge(kind, value):
    return f'<span class="badge {kind}-{esc(value)}">{esc(value)}</span>' if value else '<span class="muted">—</span>'


def render_text(body):
    """Tiny markup for KB articles: '## ' headings, '- ' bullets, '|' table rows, blank line = paragraph."""
    out, para, rows, items = [], [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()
        if rows:
            out.append("<table>" + "".join(rows) + "</table>")
            rows.clear()
    for raw in (body or "").splitlines():
        line = esc(raw.rstrip())
        if raw.startswith("## "):
            flush()
            out.append(f"<h3>{line[3:]}</h3>")
        elif raw.startswith("- "):
            if para or rows:
                flush()
            items.append(line[2:])
        elif raw.startswith("|"):
            if para or items:
                flush()
            cells = [c.strip() for c in line.strip("|").split("|")]
            tag = "th" if not rows else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        elif not raw.strip():
            flush()
        else:
            if items or rows:
                flush()
            para.append(line)
    flush()
    return "".join(out)


# ------------------------------------------------------------------------------------------------ request handling
class Handler(BaseHTTPRequestHandler):
    server_version = "LarkspurDesk/3.2"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_HEAD(self):
        self.dispatch("GET")

    # -- parsing / session
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
                            nxt = urllib.parse.quote(self.path)
                            return self.redirect(f"/login?next={nxt}")
                        fn(self, *mt.groups())
                        DB.commit()
                        return
                if any(re.fullmatch(rx, self.route_path) for _, rx, _, _ in ROUTES):  # e.g. GET on a POST-only URL
                    return self.error_page(405, "Form submissions only", "This address only accepts form submissions.")
                self.error_page(404, "Page not found", "The page you asked for does not exist.")
        except Exception:  # never let one bad request take the desk down
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
        sid = c["desk_sid"].value if "desk_sid" in c else None
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

    # -- responses
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
        links = [("tickets", "/tickets", "Tickets"), ("orgs", "/orgs", "Organizations"), ("staff", "/staff", "Staff"),
                 ("kb", "/kb", "Knowledge base"), ("board", "/board", "Team board")]
        navh = "".join(f'<a href="{h}" class="{"on" if k == nav else ""}">{t}</a>' for k, h, t in links)
        me = (f'<div class="me">{esc(self.user["name"])} &middot; {esc(self.user["title"])}'
              f'<a href="/logout">Log out</a></div>') if self.user else ""
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)} - {TITLE}</title>"
               f"<style>{CSS}</style></head><body><header><div class='brand'>Larkspur <span>Support Desk</span></div>"
               f"<nav>{navh if self.user else ''}</nav>{me}</header><main>{fl}{body}</main></body></html>")
        self.send(200, doc)

    def error_page(self, code, title, msg):
        body = f"<h1>{esc(title)}</h1><div class='card'>{esc(msg)}<p><a href='/tickets'>Back to tickets</a></p></div>"
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style>"
               f"</head><body><header><div class='brand'>Larkspur <span>Support Desk</span></div></header>"
               f"<main>{body}</main></body></html>")
        self.send(code, doc)


# ------------------------------------------------------------------------------------------------ pages
def login_get(r):
    nxt = r.qs.get("next", "/tickets")
    err = r.qs.get("err")
    msg = '<div class="flash err">Wrong username or password.</div>' if err else ""
    if r.qs.get("bye"):
        msg = '<div class="flash">You have been logged out.</div>'
    body = (f"<div class='login'><h1>Sign in</h1>{msg}<form method='post' action='/login'>"
            f"<input type='hidden' name='next' value='{esc(nxt)}'><label>Username</label>"
            f"<input type='text' name='username' autofocus><label>Password</label><input type='password' name='password'>"
            f"<button type='submit'>Sign in</button></form><p class='muted'>Larkspur Software &middot; internal use only</p></div>")
    r.page("Sign in", body)


def login_post(r):
    u = q1("SELECT * FROM users WHERE username=? AND can_login=1", (r.form.get("username", "").strip().lower(),))
    nxt = r.form.get("next") or "/tickets"
    if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/login"):
        nxt = "/tickets"
    if not u or u["password"] != r.form.get("password", ""):
        return r.redirect("/login?err=1&next=" + urllib.parse.quote(nxt))
    sid = secrets.token_hex(16)
    DB.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], "{}", now()))
    r.sid, r.sess, r.user = sid, {}, u
    r.out_cookies.append(f"desk_sid={sid}; Path=/; HttpOnly; SameSite=Lax")
    r.redirect(nxt)


def logout(r):
    if r.sid:
        DB.execute("DELETE FROM sessions WHERE sid=?", (r.sid,))
    r.sid = None
    r.out_cookies.append("desk_sid=; Path=/; Max-Age=0")
    r.redirect("/login?bye=1")


def home(r):
    r.redirect("/tickets")


STATUS_FILTERS = [("unsolved", "Unsolved (not Solved/Closed)"), ("notclosed", "Any except Closed"), ("any", "Any status")] + \
                 [(s, s) for s in STATUSES]
VIEWS = {
    "untriaged": ("Untriaged", {"status": "notclosed", "team": "none"}),
    "mine": ("My open tickets", {"status": "unsolved", "assignee": "me"}),
    "unsolved": ("All unsolved", {"status": "unsolved"}),
    "pending": ("Pending", {"status": "Pending"}),
    "onhold": ("On-hold", {"status": "On-hold"}),
    "solved": ("Solved", {"status": "Solved"}),
    "all": ("All tickets", {"status": "any"}),
}
DEFAULT_F = {"q": "", "status": "unsolved", "team": "any", "priority": "any", "assignee": "any", "sort": "updated",
             "dir": "desc", "page": "1"}
SORTS = {"id": "t.id", "subject": "t.subject COLLATE NOCASE", "requester": "t.requester COLLATE NOCASE",
         "org": "o.name COLLATE NOCASE", "status": "CASE t.status " + " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(STATUSES)) + " END",
         "priority": "CASE t.priority " + " ".join(f"WHEN '{p}' THEN {i + 1}" for i, p in enumerate(PRIORITIES)) + " ELSE 0 END",
         "team": "COALESCE(t.team,'')", "assignee": "COALESCE(u.name,'')", "updated": "t.updated"}


def ticket_where(f, me_id):
    where, args = [], []
    st = f.get("status")
    if st == "unsolved":
        where.append("t.status NOT IN ('Solved','Closed')")
    elif st == "notclosed":
        where.append("t.status <> 'Closed'")
    elif st in STATUSES:
        where.append("t.status=?")
        args.append(st)
    tm = f.get("team")
    if tm == "none":
        where.append("t.team IS NULL")
    elif tm in TEAMS:
        where.append("t.team=?")
        args.append(tm)
    pr = f.get("priority")
    if pr == "none":
        where.append("t.priority IS NULL")
    elif pr in PRIORITIES:
        where.append("t.priority=?")
        args.append(pr)
    asg = f.get("assignee")
    if asg == "none":
        where.append("t.assignee_id IS NULL")
    elif asg == "me":
        where.append("t.assignee_id=?")
        args.append(me_id)
    elif to_int(asg):
        where.append("t.assignee_id=?")
        args.append(to_int(asg))
    text = (f.get("q") or "").strip()
    if text:
        if to_int(text):
            where.append("t.id=?")
            args.append(to_int(text))
        else:
            where.append("(t.subject LIKE ? OR t.requester LIKE ? OR t.requester_email LIKE ? OR o.name LIKE ? OR t.tags LIKE ?)")
            args += [f"%{text}%"] * 5
    return (" WHERE " + " AND ".join(where)) if where else "", args


def tickets_list(r):
    f = dict(DEFAULT_F, **r.sess.get("tf", {}))
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
    r.sess["tf"] = f
    where, args = ticket_where(f, r.user["id"])
    base = "FROM tickets t LEFT JOIN orgs o ON o.id=t.org_id LEFT JOIN users u ON u.id=t.assignee_id"
    total = q1(f"SELECT COUNT(*) {base}{where}", args)[0]
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(max(1, to_int(f.get("page"), 1)), pages)
    f["page"] = str(page)
    r.save_session()
    rows = q(f"SELECT t.*, o.name AS org, u.name AS assignee {base}{where} ORDER BY {SORTS[f['sort']]} {f['dir']}, t.id DESC "
             f"LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", args)
    me = r.user["id"]
    side = []
    for key, (label, vf) in VIEWS.items():
        w, a = ticket_where(dict(DEFAULT_F, **vf), me)
        n = q1(f"SELECT COUNT(*) {base}{w}", a)[0]
        on = all(f.get(k) == v for k, v in dict(DEFAULT_F, **vf).items() if k not in ("sort", "dir", "page", "q")) and not f["q"]
        side.append(f'<a href="/tickets?view={key}" class="{"on" if on else ""}">{label}<span class="n">{n}</span></a>')
    staff = q("SELECT id, name FROM users ORDER BY name")
    filt = (f"<form class='filters' method='get' action='/tickets'>"
            f"<input type='text' name='q' value='{esc(f['q'])}' placeholder='Search # / subject / requester / org'>"
            f"<select name='status'>{options(STATUS_FILTERS, f['status'])}</select>"
            f"<select name='team'>{options([('any', 'Any team'), ('none', 'No team (untriaged)')] + TEAMS, f['team'])}</select>"
            f"<select name='priority'>{options([('any', 'Any priority'), ('none', 'No priority')] + PRIORITIES, f['priority'])}</select>"
            f"<select name='assignee'>{options([('any', 'Any assignee'), ('none', 'Unassigned'), ('me', 'Me')] + [(s['id'], s['name']) for s in staff], f['assignee'])}</select>"
            f"<input type='hidden' name='sort' value='{esc(f['sort'])}'><input type='hidden' name='dir' value='{esc(f['dir'])}'>"
            f"<button type='submit'>Apply</button> <a href='/tickets?reset=1'>Reset filters</a></form>")

    def link(**kw):
        return "/tickets?" + urllib.parse.urlencode(dict(f, **kw))

    def th(key, label):
        d = "asc" if f["sort"] != key or f["dir"] == "desc" else "desc"
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if f["sort"] == key else ""
        return f'<th><a href="{esc(link(sort=key, dir=d, page=1))}">{label}{arrow}</a></th>'
    trs = []
    for t in rows:
        trs.append(f"<tr><td><input type='checkbox' name='ids' value='{t['id']}'></td><td>#{t['id']}</td>"
                   f"<td><a href='/tickets/{t['id']}'>{esc(t['subject'])}</a></td><td>{esc(t['requester'])}</td>"
                   f"<td>{esc(t['org'] or '')}</td><td>{badge('s', t['status'])}</td><td>{badge('p', t['priority'])}</td>"
                   f"<td>{esc(t['team'] or '—')}</td><td>{esc(t['assignee'] or '—')}</td><td class='muted'>{fmt_date(t['updated'])}</td></tr>")
    if not trs:
        trs.append("<tr><td colspan='10' class='muted'>No tickets match these filters.</td></tr>")
    pager = [f"<span class='muted'>Showing {(page - 1) * PER_PAGE + 1 if total else 0}–{min(total, page * PER_PAGE)} of {total}</span>"]
    if page > 1:
        pager.append(f"<a href='{esc(link(page=page - 1))}'>&laquo; Prev</a>")
    for p in range(1, pages + 1):
        pager.append(f"<b>{p}</b>" if p == page else f"<a href='{esc(link(page=p))}'>{p}</a>")
    if page < pages:
        pager.append(f"<a href='{esc(link(page=page + 1))}'>Next &raquo;</a>")
    nochg = "— no change —"
    bulk = (f"<div class='bulk'><b>Bulk update selected:</b> Status <select name='status'>{options(STATUSES, '', nochg)}</select>"
            f" Priority <select name='priority'>{options(PRIORITIES + [('none', '(clear)')], '', nochg)}</select>"
            f" Team <select name='team'>{options(TEAMS + [('none', '(unassign)')], '', nochg)}</select>"
            f" Assignee <select name='assignee'>{options([(s['id'], s['name']) for s in staff] + [('none', '(unassign)')], '', nochg)}</select>"
            f" Add tag <input type='text' name='tag' size='10'> <button type='submit'>Apply to selected</button></div>")
    table = (f"<form method='post' action='/tickets/bulk'><table class='list'><tr><th></th>{th('id', '#')}{th('subject', 'Subject')}"
             f"{th('requester', 'Requester')}{th('org', 'Organization')}{th('status', 'Status')}{th('priority', 'Priority')}"
             f"{th('team', 'Team')}{th('assignee', 'Assignee')}{th('updated', 'Updated')}</tr>{''.join(trs)}</table>"
             f"<div class='pager'>{''.join(pager)}</div>{bulk}</form>")
    body = (f"<div class='layout'><div class='side'><h2 style='margin-top:4px'>Views</h2>{''.join(side)}</div>"
            f"<div><h1>Tickets</h1>{filt}{table}</div></div>")
    r.page("Tickets", body, "tickets")


def record(ticket_id, user_id, rid, field, old, new):
    if (old or "") != (new or ""):
        DB.execute("INSERT INTO events (ticket_id,user_id,rid,field,old,new,ts) VALUES (?,?,?,?,?,?,?)",
                   (ticket_id, user_id, rid, field, old, new, now()))
        return True
    return False


def apply_changes(t, changes, user_id, rid):
    """changes: {column: new value}. Writes the columns, records history, returns number of changed fields."""
    n = 0
    for col, new in changes.items():
        old = t[col]
        if col == "assignee_id":
            on = q1("SELECT name FROM users WHERE id=?", (old,)) if old else None
            nn = q1("SELECT name FROM users WHERE id=?", (new,)) if new else None
            changed = record(t["id"], user_id, rid, "assignee", on["name"] if on else "", nn["name"] if nn else "")
        else:
            changed = record(t["id"], user_id, rid, col, old, new)
        if changed:
            DB.execute(f"UPDATE tickets SET {col}=? WHERE id=?", (new, t["id"]))
            n += 1
    if n:
        DB.execute("UPDATE tickets SET updated=? WHERE id=?", (now(), t["id"]))
    return n


def bulk_update(r):
    ids = [to_int(x) for x in r.fm.get("ids", []) if to_int(x)]
    if not ids:
        r.flash("Select at least one ticket first.", True)
        return r.redirect("/tickets")
    ch = {}
    if r.form.get("status") in STATUSES:
        ch["status"] = r.form["status"]
    if r.form.get("priority") in PRIORITIES or r.form.get("priority") == "none":
        ch["priority"] = None if r.form["priority"] == "none" else r.form["priority"]
    if r.form.get("team") in TEAMS or r.form.get("team") == "none":
        ch["team"] = None if r.form["team"] == "none" else r.form["team"]
    asg = r.form.get("assignee", "")
    if asg == "none":
        ch["assignee_id"] = None
    elif to_int(asg) and q1("SELECT id FROM users WHERE id=?", (to_int(asg),)):
        ch["assignee_id"] = to_int(asg)
    tag = norm_tags(r.form.get("tag", ""))
    if not ch and not tag:
        r.flash("Nothing to change: pick a new value in at least one field.", True)
        return r.redirect("/tickets")
    rid, n = secrets.token_hex(4), 0
    for tid in ids:
        t = q1("SELECT * FROM tickets WHERE id=?", (tid,))
        if not t:
            continue
        c = dict(ch)
        if tag:
            c["tags"] = norm_tags((t["tags"] or "") + "," + tag)
        n += apply_changes(t, c, r.user["id"], rid) > 0
    r.flash(f"Updated {n} of {len(ids)} selected ticket(s).")
    r.redirect("/tickets")


def ticket_view(r, tid):
    t = q1("SELECT t.*, o.name AS org, o.plan FROM tickets t LEFT JOIN orgs o ON o.id=t.org_id WHERE t.id=?", (to_int(tid),))
    if not t:
        return r.error_page(404, "Ticket not found", f"There is no ticket #{tid}.")
    cs = q("SELECT * FROM comments WHERE ticket_id=? ORDER BY created, id", (t["id"],))
    atts = {}
    for a in q("SELECT id, comment_id, filename FROM attachments WHERE ticket_id=?", (t["id"],)):
        atts.setdefault(a["comment_id"], []).append(a)
    conv = []
    for c in cs:
        kind = "cust" if not c["user_id"] else ("pub" if c["public"] else "int")
        label = {"cust": "Customer message", "pub": "Public reply", "int": "Internal note"}[kind]
        imgs = "".join(f"<div class='att'><a href='/att/{a['id']}' target='_blank'>{esc(a['filename'])}</a><br>"
                       f"<img src='/att/{a['id']}' alt='{esc(a['filename'])}'></div>" for a in atts.get(c["id"], []))
        conv.append(f"<div class='c {kind}'><b>{esc(c['author'])}</b> <span class='muted'>{label} &middot; {fmt_date(c['created'])}</span>"
                    f"<pre>{esc(c['body'])}</pre>{imgs}</div>")
    staff = q("SELECT id, name FROM users ORDER BY name")
    ev = q("SELECT e.*, u.name FROM events e LEFT JOIN users u ON u.id=e.user_id WHERE ticket_id=? ORDER BY e.id DESC", (t["id"],))
    hist = "".join(f"<li><span class='muted'>{fmt_date(e['ts'])}</span> {esc(e['name'])} changed <b>{esc(e['field'])}</b>"
                   f" from “{esc(e['old'] or '—')}” to “{esc(e['new'] or '—')}”</li>" for e in ev) or "<li class='muted'>No changes yet.</li>"
    org = f"<a href='/orgs/{t['org_id']}'>{esc(t['org'])}</a>" if t["org_id"] else "<span class='muted'>(no organization)</span>"
    sla = f"<p class='muted'>SLA first-response target: {SLA[t['priority']]}</p>" if t["priority"] in SLA else ""
    body = (f"<p class='muted'><a href='/tickets'>&laquo; Back to ticket list</a></p>"
            f"<h1>#{t['id']} {esc(t['subject'])} {badge('s', t['status'])}</h1>"
            f"<form method='post' action='/tickets/{t['id']}'><div class='tk'><div>{''.join(conv)}"
            f"<div class='card'><b>Add a comment</b><p><label><input type='radio' name='kind' value='public' checked> Public reply (emailed to the requester)</label>"
            f" &nbsp; <label><input type='radio' name='kind' value='internal'> Internal note (staff only)</label></p>"
            f"<textarea name='comment' rows='7'></textarea><p><button type='submit'>Submit</button>"
            f" <span class='muted'>Submitting saves the comment and all ticket properties on this page.</span></p></div>"
            f"<h2>History</h2><ul class='muted'>{hist}</ul></div>"
            f"<div class='props card'><div><b>Requester</b><br>{esc(t['requester'])}<br><span class='muted'>{esc(t['requester_email'])}</span></div>"
            f"<label>Organization</label>{org}<label>Channel</label>{esc(t['channel'])}"
            f"<label>Impact (reported by customer)</label>{esc(t['impact'] or '—')}<label>Created</label>{fmt_date(t['created'])}"
            f"<label>Status</label><select name='status'>{options(STATUSES, t['status'])}</select>"
            f"<label>Priority</label><select name='priority'>{options(PRIORITIES, t['priority'], '—')}</select>"
            f"<label>Team</label><select name='team'>{options(TEAMS, t['team'], '— Unassigned —')}</select>"
            f"<label>Assignee</label><select name='assignee'>{options([(s['id'], s['name']) for s in staff], t['assignee_id'], '— Unassigned —')}</select>"
            f"<label>Tags</label><input type='text' name='tags' value='{esc(t['tags'])}'>{sla}"
            f"<p><button type='submit'>Submit</button></p></div></div></form>")
    r.page(f"#{t['id']} {t['subject']}", body, "tickets")


def ticket_update(r, tid):
    t = q1("SELECT * FROM tickets WHERE id=?", (to_int(tid),))
    if not t:
        return r.error_page(404, "Ticket not found", f"There is no ticket #{tid}.")
    ch = {}
    if r.form.get("status") in STATUSES:
        ch["status"] = r.form["status"]
    if "priority" in r.form:
        ch["priority"] = r.form["priority"] if r.form["priority"] in PRIORITIES else None
    if "team" in r.form:
        ch["team"] = r.form["team"] if r.form["team"] in TEAMS else None
    if "assignee" in r.form:
        a = to_int(r.form["assignee"])
        ch["assignee_id"] = a if a and q1("SELECT id FROM users WHERE id=?", (a,)) else None
    if "tags" in r.form:
        ch["tags"] = norm_tags(r.form["tags"])
    rid = secrets.token_hex(4)
    n = apply_changes(t, ch, r.user["id"], rid)
    text = (r.form.get("comment") or "").strip()
    if text:
        public = 0 if r.form.get("kind") == "internal" else 1
        DB.execute("INSERT INTO comments (ticket_id,author,user_id,public,body,created) VALUES (?,?,?,?,?,?)",
                   (t["id"], r.user["name"], r.user["id"], public, text, now()))
        DB.execute("UPDATE tickets SET updated=? WHERE id=?", (now(), t["id"]))
        record(t["id"], r.user["id"], rid, "comment", "", "public reply" if public else "internal note")
    r.flash(f"Ticket #{t['id']} updated." if (n or text) else f"No changes to ticket #{t['id']}.")
    r.redirect(f"/tickets/{t['id']}")


def attachment(r, aid):
    a = q1("SELECT * FROM attachments WHERE id=?", (to_int(aid),))
    if not a:
        return r.error_page(404, "Attachment not found", "This attachment does not exist.")
    r.send(200, a["data"], a["ctype"] or "application/octet-stream",
           [("Content-Disposition", f'inline; filename="{a["filename"]}"')])


def orgs_list(r):
    text = r.qs.get("q", "").strip()
    plan = r.qs.get("plan", "")
    where, args = [], []
    if text:
        where.append("(o.name LIKE ? OR o.domain LIKE ?)")
        args += [f"%{text}%"] * 2
    if plan in ("Enterprise", "Business", "Starter"):
        where.append("o.plan=?")
        args.append(plan)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    rows = q(f"SELECT o.*, (SELECT COUNT(*) FROM tickets t WHERE t.org_id=o.id AND t.status NOT IN ('Solved','Closed')) AS n "
             f"FROM orgs o{w} ORDER BY o.name COLLATE NOCASE", args)
    trs = "".join(f"<tr><td><a href='/orgs/{o['id']}'>{esc(o['name'])}</a></td><td>{badge('plan', o['plan'])}</td>"
                  f"<td>{esc(o['domain'])}</td><td>{esc(o['account_manager'])}</td><td>{o['n']}</td></tr>" for o in rows)
    body = (f"<h1>Organizations</h1><form class='filters' method='get'><input type='text' name='q' value='{esc(text)}' placeholder='Search name or domain'>"
            f"<select name='plan'>{options(['Enterprise', 'Business', 'Starter'], plan, 'Any plan')}</select><button>Search</button></form>"
            f"<table class='list'><tr><th>Name</th><th>Plan</th><th>Domain</th><th>Account manager</th><th>Unsolved tickets</th></tr>"
            f"{trs or '<tr><td colspan=5 class=muted>No organizations found.</td></tr>'}</table>")
    r.page("Organizations", body, "orgs")


def org_view(r, oid):
    o = q1("SELECT o.*, u.name AS engineer FROM orgs o LEFT JOIN users u ON u.id=o.engineer_id WHERE o.id=?", (to_int(oid),))
    if not o:
        return r.error_page(404, "Organization not found", "This organization does not exist.")
    ts = q("SELECT t.*, u.name AS assignee FROM tickets t LEFT JOIN users u ON u.id=t.assignee_id WHERE org_id=? ORDER BY t.id DESC", (o["id"],))
    trs = "".join(f"<tr><td>#{t['id']}</td><td><a href='/tickets/{t['id']}'>{esc(t['subject'])}</a></td><td>{badge('s', t['status'])}</td>"
                  f"<td>{badge('p', t['priority'])}</td><td>{esc(t['team'] or '—')}</td><td>{esc(t['assignee'] or '—')}</td></tr>" for t in ts)
    eng = esc(o["engineer"]) if o["engineer"] else "<span class='muted'>— (Enterprise plans only)</span>"
    body = (f"<p class='muted'><a href='/orgs'>&laquo; All organizations</a></p><h1>{esc(o['name'])} {badge('plan', o['plan'])}</h1>"
            f"<div class='card'><table><tr><td class='muted' style='width:220px'>Plan</td><td>{esc(o['plan'])}</td></tr>"
            f"<tr><td class='muted'>Domain</td><td>{esc(o['domain'])}</td></tr><tr><td class='muted'>Phone</td><td>{esc(o['phone'])}</td></tr>"
            f"<tr><td class='muted'>Customer since</td><td>{esc(o['customer_since'])}</td></tr>"
            f"<tr><td class='muted'>Account manager</td><td>{esc(o['account_manager'])}</td></tr>"
            f"<tr><td class='muted'>Dedicated support engineer</td><td>{eng}</td></tr>"
            f"<tr><td class='muted'>Notes</td><td>{esc(o['notes'])}</td></tr></table></div>"
            f"<h2>Tickets</h2><table class='list'><tr><th>#</th><th>Subject</th><th>Status</th><th>Priority</th><th>Team</th><th>Assignee</th></tr>{trs}</table>")
    r.page(o["name"], body, "orgs")


def staff_list(r):
    rows = q("SELECT u.*, b.name AS backup FROM users u LEFT JOIN users b ON b.id=u.backup_id ORDER BY u.team, u.name")
    trs = []
    for u in rows:
        st = f"<span class='badge s-Pending'>Out of office until {esc(u['ooo_until'])}</span>" if u["ooo_until"] else "<span class='badge s-Solved'>Available</span>"
        trs.append(f"<tr><td>{esc(u['name'])}</td><td>{esc(u['title'])}</td><td>{esc(u['team'])}</td><td>{esc(u['email'])}</td>"
                   f"<td>{st}</td><td>{esc(u['backup'] or '—')}</td></tr>")
    body = ("<h1>Staff</h1><table class='list'><tr><th>Name</th><th>Role</th><th>Team</th><th>Email</th><th>Availability</th>"
            f"<th>Backup while away</th></tr>{''.join(trs)}</table>")
    r.page("Staff", body, "staff")


def kb_list(r):
    text = r.qs.get("q", "").strip()
    cat = r.qs.get("category", "")
    where, args = [], []
    if text:
        where.append("(code LIKE ? OR title LIKE ? OR body LIKE ?)")
        args += [f"%{text}%"] * 3
    cats = [c["category"] for c in q("SELECT DISTINCT category FROM kb ORDER BY category")]
    if cat in cats:
        where.append("category=?")
        args.append(cat)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    rows = q(f"SELECT * FROM kb{w} ORDER BY code", args)
    trs = "".join(f"<tr><td>{esc(k['code'])}</td><td><a href='/kb/{esc(k['code'])}'>{esc(k['title'])}</a></td>"
                  f"<td>{esc(k['category'])}</td><td class='muted'>{esc(k['updated'])}</td></tr>" for k in rows)
    body = (f"<h1>Knowledge base</h1><form class='filters' method='get'><input type='text' name='q' value='{esc(text)}' placeholder='Search articles' size='40'>"
            f"<select name='category'>{options(cats, cat, 'All categories')}</select><button>Search</button></form>"
            f"<table class='list'><tr><th>Article</th><th>Title</th><th>Category</th><th>Updated</th></tr>"
            f"{trs or '<tr><td colspan=4 class=muted>No articles match.</td></tr>'}</table>")
    r.page("Knowledge base", body, "kb")


def kb_view(r, code):
    k = q1("SELECT * FROM kb WHERE code=? OR id=?", (code.upper(), to_int(code, -1)))
    if not k:
        return r.error_page(404, "Article not found", f"There is no knowledge-base article {code}.")
    body = (f"<p class='muted'><a href='/kb'>&laquo; Knowledge base</a></p><h1>{esc(k['code'])} · {esc(k['title'])}</h1>"
            f"<p class='muted'>{esc(k['category'])} &middot; updated {esc(k['updated'])}</p><div class='card kb'>{render_text(k['body'])}</div>")
    r.page(k["title"], body, "kb")


def board(r):
    posts = q("SELECT p.*, u.name FROM posts p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC")
    items = "".join(f"<div class='card'><b>{esc(p['title'])}</b> <span class='muted'>{esc(p['name'])} &middot; {fmt_date(p['created'])}</span>"
                    f"<pre style='white-space:pre-wrap;font:inherit'>{esc(p['body'])}</pre></div>" for p in posts)
    body = ("<h1>Team board</h1><div class='card'><b>New post</b><form method='post' action='/board'>"
            "<p><input type='text' name='title' placeholder='Title' style='width:100%'></p><textarea name='body' rows='6'></textarea>"
            f"<p><button type='submit'>Post</button></p></form></div>{items}")
    r.page("Team board", body, "board")


def board_post(r):
    title, text = r.form.get("title", "").strip(), r.form.get("body", "").strip()
    if not title and not text:
        r.flash("Write something before posting.", True)
        return r.redirect("/board")
    DB.execute("INSERT INTO posts (user_id,title,body,created) VALUES (?,?,?,?)", (r.user["id"], title or "(untitled)", text, now()))
    r.flash("Posted to the team board.")
    r.redirect("/board")


ROUTES = [
    ("GET", r"/login", login_get, True), ("POST", r"/login", login_post, True), ("GET", r"/logout", logout, True),
    ("GET", r"/", home, False), ("GET", r"/tickets", tickets_list, False), ("POST", r"/tickets/bulk", bulk_update, False),
    ("GET", r"/tickets/(\d+)", ticket_view, False), ("POST", r"/tickets/(\d+)", ticket_update, False),
    ("GET", r"/att/(\d+)", attachment, False), ("GET", r"/orgs", orgs_list, False), ("GET", r"/orgs/(\d+)", org_view, False),
    ("GET", r"/staff", staff_list, False), ("GET", r"/kb", kb_list, False), ("GET", r"/kb/([A-Za-z0-9\-]+)", kb_view, False),
    ("GET", r"/board", board, False), ("POST", r"/board", board_post, False),
]


def make_server(db_path, host="127.0.0.1", port=8101):
    global DB
    DB = sqlite3.connect(db_path, check_same_thread=False)
    init_schema(DB)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8101)
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
