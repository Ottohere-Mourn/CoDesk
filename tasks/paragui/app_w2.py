#!/usr/bin/env python3
"""Fenwick Spend - expenses & approvals portal of Fenwick & Hale (single file, Python 3 stdlib only).

    python3 app.py --db spend.db --port 8102          # serves http://127.0.0.1:8102/

http.server + sqlite3, server-rendered HTML, cookie sessions stored in the database. The session carries the active
role ("Employee view" / "Approver view", like delegate/role modes in SAP or Concur) and the remembered filters of the
Reports list; "Export CSV" exports whatever the session's current filter is.
"""
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
import sys
import threading
import traceback
import urllib.parse
from email import policy as email_policy
from email.parser import BytesParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TITLE = "Fenwick Spend"
CATEGORIES = ["Airfare", "Lodging", "Meals", "Ground transport", "Conference fees", "Software & subscriptions",
              "Office supplies", "Courier & postage", "Other"]
STATUSES = ["Draft", "Submitted", "Approved", "Rejected", "Paid"]
PER_PAGE = 20
MAX_FILE = 8_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT,
  department TEXT, title TEXT, manager_id INTEGER, can_login INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, employee_id INTEGER, title TEXT, purpose TEXT,
  preapproval TEXT DEFAULT '', status TEXT, approver_id INTEGER, created TEXT, submitted TEXT, decided TEXT,
  decided_by INTEGER, comment TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS lines (id INTEGER PRIMARY KEY, report_id INTEGER, date TEXT, category TEXT, merchant TEXT,
  amount REAL, attendees INTEGER, description TEXT DEFAULT '', receipt_id INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS receipts (id INTEGER PRIMARY KEY, filename TEXT, ctype TEXT, size INTEGER, md5 TEXT,
  data BLOB, uploaded TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, report_id INTEGER, user_id INTEGER, ts TEXT, action TEXT,
  detail TEXT);
CREATE TABLE IF NOT EXISTS exports (id INTEGER PRIMARY KEY, user_id INTEGER, ts TEXT, filters TEXT, report_ids TEXT);
CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, user_id INTEGER, data TEXT, created TEXT);
"""

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",Ubuntu,Arial,sans-serif;color:#1d2b28;background:#f2f5f4}
a{color:#0c6b58;text-decoration:none}a:hover{text-decoration:underline}
header{background:#0f3d35;color:#fff;display:flex;align-items:center;padding:0 18px;height:52px;gap:22px}
header .brand{font-weight:700;font-size:17px}header .brand span{color:#8fe3c8;font-weight:400}
header nav a{color:#cfe9e1;padding:16px 8px;display:inline-block}header nav a.on{color:#fff;border-bottom:3px solid #8fe3c8}
header .right{margin-left:auto;display:flex;align-items:center;gap:14px;color:#cfe9e1}header .right a{color:#fff}
.role{display:flex;border:1px solid #5f9c8c;border-radius:16px;overflow:hidden}
.role button{background:transparent;color:#cfe9e1;border:0;padding:5px 12px;border-radius:0;font-size:13px}
.role button.on{background:#8fe3c8;color:#0f3d35;font-weight:700}
main{padding:18px 24px;max-width:1450px;margin:0 auto}h1{font-size:21px;margin:4px 0 14px}h2{font-size:16px;margin:20px 0 8px}
.flash{padding:9px 12px;border-radius:4px;margin-bottom:12px;background:#e1f5ec;border:1px solid #93d2b6}
.flash.err{background:#fde8e8;border-color:#f0a5a5}.note{padding:10px 12px;background:#fff8e1;border:1px solid #f1d27a;border-radius:4px;margin:10px 0}
table.list{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d5dedb}
table.list th{background:#e9f0ee;text-align:left;padding:7px 9px;font-weight:600;border-bottom:1px solid #d5dedb;white-space:nowrap}
table.list td{padding:7px 9px;border-bottom:1px solid #edf1f0;vertical-align:top}table.list tr:hover td{background:#f7fbfa}
td.num,th.num{text-align:right;white-space:nowrap}
.badge{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:600;background:#e4e7eb}
.s-Draft{background:#e4e7eb}.s-Submitted{background:#ffe7a8}.s-Approved{background:#c9efd9}.s-Rejected{background:#ffd2cc}.s-Paid{background:#cfe3ff}
.filters{background:#fff;border:1px solid #d5dedb;padding:9px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],input[type=password],input[type=number],select,textarea{font:inherit;padding:5px 7px;border:1px solid #b5c4bf;border-radius:3px;background:#fff}
textarea{width:100%}button,.btn{font:inherit;background:#0c6b58;color:#fff;border:0;border-radius:3px;padding:6px 14px;cursor:pointer;display:inline-block}
.btn:hover{text-decoration:none}button.red{background:#b3261e}button.sec,.btn.sec{background:#e3ebe8;color:#1d2b28}
.pager{margin:10px 0;display:flex;gap:6px;align-items:center}.pager a,.pager b{padding:3px 9px;border:1px solid #d5dedb;background:#fff;border-radius:3px}
.pager b{background:#0c6b58;color:#fff}.card{background:#fff;border:1px solid #d5dedb;border-radius:4px;padding:12px 16px;margin-bottom:14px}
.muted{color:#66766f;font-size:12px}.kv td{padding:3px 14px 3px 0;vertical-align:top}.kv td:first-child{color:#66766f;width:170px}
.thumb{max-width:230px;max-height:170px;border:1px solid #c5d0cc;display:block;margin-top:3px}.warn{color:#b3261e;font-weight:600;font-size:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px}.grid2 label{display:block;font-weight:600;margin-bottom:3px}
.grid2 input,.grid2 select{width:100%}.login{max-width:370px;margin:90px auto;background:#fff;border:1px solid #d5dedb;padding:26px;border-radius:6px}
.login input{width:100%;margin:4px 0 12px}.total td{font-weight:700;background:#f4f8f7}
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


def report_id(s):
    """'EXP-2041', '2041' -> 2041."""
    m = re.fullmatch(r"\s*(?:EXP-?)?(\d{1,9})\s*", str(s or ""), re.I)
    return int(m.group(1)) if m else None


def parse_date(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y"):
        try:
            d = dt.datetime.strptime(s, fmt).date()
            return d.isoformat() if 2000 <= d.year <= 2100 else None
        except ValueError:
            pass
    return None


def parse_amount(s):
    s = re.sub(r"[\s$,]|USD", "", str(s or ""), flags=re.I)
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return v if 0 < v < 100000 else None


def money(v):
    return f"${v:,.2f}" if v is not None else "—"


def code(rid):
    return f"EXP-{rid}"


def q(sql, args=()):
    return DB.execute(sql, args).fetchall()


def q1(sql, args=()):
    return DB.execute(sql, args).fetchone()


def init_schema(con):
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()


def options(items, selected, blank=None):
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for it in items:
        v, lab = it if isinstance(it, tuple) else (it, it)
        sel = " selected" if str(v) == str(selected if selected is not None else "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{esc(lab)}</option>')
    return "".join(out)


def badge(s):
    return f'<span class="badge s-{esc(s)}">{esc(s)}</span>'


def fmt_ts(s):
    try:
        return dt.datetime.fromisoformat(s).strftime("%d %b %Y %H:%M")
    except (TypeError, ValueError):
        return s or ""


def fmt_day(s):
    try:
        return dt.date.fromisoformat(s[:10]).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return s or ""


def sniff(data, name):
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def parse_multipart(raw, ctype):
    msg = BytesParser(policy=email_policy.HTTP).parsebytes(
        b"Content-Type: " + ctype.encode("latin-1", "replace") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
    form, files = {}, {}
    if not msg.is_multipart():
        return form, files
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        fn = part.get_filename()
        if fn is not None:
            files[name] = (fn, data)
        else:
            form[name] = data.decode("utf-8", "replace")
    return form, files


# ------------------------------------------------------------------------------------------------ request handling
class Handler(BaseHTTPRequestHandler):
    server_version = "FenwickSpend/2.4"
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
            self.qs = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
            self.form, self.files = {}, {}
            if method == "POST":
                n = to_int(self.headers.get("Content-Length"), 0) or 0
                if n > 20_000_000:
                    return self.error_page(413, "Upload too large", "The upload is larger than 20 MB.")
                raw = self.rfile.read(n) if n > 0 else b""
                ctype = self.headers.get("Content-Type", "")
                if ctype.startswith("multipart/form-data"):
                    self.form, self.files = parse_multipart(raw, ctype)
                else:
                    fm = urllib.parse.parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
                    self.form = {k: v[-1] for k, v in fm.items()}
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
        except Exception:
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
        sid = c["spend_sid"].value if "spend_sid" in c else None
        if sid:
            row = q1("SELECT * FROM sessions WHERE sid=?", (sid,))
            if row:
                self.sid = sid
                try:
                    self.sess = json.loads(row["data"] or "{}")
                except ValueError:
                    self.sess = {}
                self.user = q1("SELECT * FROM users WHERE id=?", (row["user_id"],))

    @property
    def role(self):
        return "approver" if self.sess.get("role") == "approver" else "employee"

    def save_session(self):
        if self.sid:
            DB.execute("UPDATE sessions SET data=? WHERE sid=?", (json.dumps(self.sess), self.sid))

    def flash(self, msg, err=False):
        self.sess.setdefault("flash", []).append([msg, err])
        self.save_session()

    def send(self, code_, body, ctype="text/html; charset=utf-8", headers=()):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code_)
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
        navh, right = "", ""
        if self.user:
            if self.role == "approver":
                n = q1("SELECT COUNT(*) FROM reports WHERE status='Submitted' AND approver_id=?", (self.user["id"],))[0]
                links = [("approvals", "/approvals", f"Approvals ({n})"), ("reports", "/reports", "Reports")]
            else:
                links = [("my", "/my", "My reports"), ("new", "/reports/new", "New report")]
            navh = "".join(f'<a href="{h}" class="{"on" if k == nav else ""}">{t}</a>' for k, h, t in links)
            back = esc(self.path if self.method == "GET" else "/")
            right = (f"<div class='right'><form method='post' action='/role' class='role'><input type='hidden' name='back' value='{back}'>"
                     f"<button name='role' value='employee' class='{'on' if self.role == 'employee' else ''}'>Employee view</button>"
                     f"<button name='role' value='approver' class='{'on' if self.role == 'approver' else ''}'>Approver view</button></form>"
                     f"<span>{esc(self.user['name'])}</span><a href='/logout'>Log out</a></div>")
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)} - {TITLE}</title><style>{CSS}</style>"
               f"</head><body><header><div class='brand'>Fenwick Spend <span>Expenses &amp; Approvals</span></div>"
               f"<nav>{navh}</nav>{right}</header><main>{fl}{body}</main></body></html>")
        self.send(200, doc)

    def error_page(self, code_, title, msg):
        body = f"<h1>{esc(title)}</h1><div class='card'>{esc(msg)}<p><a href='/'>Back to Fenwick Spend</a></p></div>"
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style></head><body>"
               f"<header><div class='brand'>Fenwick Spend <span>Expenses &amp; Approvals</span></div></header><main>{body}</main></body></html>")
        self.send(code_, doc)

    def need_role(self, role, what):
        """Page body telling the user to switch role, or '' if the active role is right."""
        if self.role == role:
            return ""
        label = "Approver view" if role == "approver" else "Employee view"
        return (f"<div class='note'>{esc(what)} is part of the <b>{label}</b>. You are in the "
                f"{'Approver' if self.role == 'approver' else 'Employee'} view."
                f"<form method='post' action='/role' style='margin-top:8px'><input type='hidden' name='role' value='{role}'>"
                f"<button>Switch to {label}</button></form></div>")


# ------------------------------------------------------------------------------------------------ helpers
def event(rid, uid, action, detail=""):
    DB.execute("INSERT INTO events (report_id,user_id,ts,action,detail) VALUES (?,?,?,?,?)", (rid, uid, now(), action, detail))


def total(rid):
    return round(q1("SELECT COALESCE(SUM(amount),0) FROM lines WHERE report_id=?", (rid,))[0], 2)


def store_receipt(r, field):
    """Save an uploaded receipt; returns (receipt id or None, error message or None)."""
    f = r.files.get(field)
    if not f or not f[1]:
        return None, None
    name, data = f
    name = re.sub(r"[^\w .()\-]", "_", (name or "receipt").split("/")[-1].split("\\")[-1])[:120] or "receipt"
    if len(data) > MAX_FILE:
        return None, "The receipt file is larger than 8 MB."
    ctype = sniff(data, name)
    if not ctype:
        return None, "Receipts must be PDF, PNG, JPG, GIF or WEBP files."
    cur = DB.execute("INSERT INTO receipts (filename,ctype,size,md5,data,uploaded) VALUES (?,?,?,?,?,?)",
                     (name, ctype, len(data), hashlib.md5(data).hexdigest(), data, now()))
    return cur.lastrowid, None


# ------------------------------------------------------------------------------------------------ pages
def login_get(r):
    nxt = r.qs.get("next", "/")
    msg = '<div class="flash err">Wrong username or password.</div>' if r.qs.get("err") else ""
    if r.qs.get("bye"):
        msg = '<div class="flash">You have been logged out.</div>'
    body = (f"<div class='login'><h1>Sign in to Fenwick Spend</h1>{msg}<form method='post' action='/login'>"
            f"<input type='hidden' name='next' value='{esc(nxt)}'><label>Username</label><input type='text' name='username' autofocus>"
            f"<label>Password</label><input type='password' name='password'><button type='submit'>Sign in</button></form>"
            f"<p class='muted'>Fenwick &amp; Hale &middot; Finance systems</p></div>")
    r.page("Sign in", body)


def login_post(r):
    u = q1("SELECT * FROM users WHERE username=? AND can_login=1", (r.form.get("username", "").strip().lower(),))
    nxt = r.form.get("next") or "/"
    if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/login"):
        nxt = "/"
    if not u or u["password"] != r.form.get("password", ""):
        return r.redirect("/login?err=1&next=" + urllib.parse.quote(nxt))
    sid = secrets.token_hex(16)
    DB.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], json.dumps({"role": "employee"}), now()))
    r.sid, r.sess, r.user = sid, {"role": "employee"}, u
    r.out_cookies.append(f"spend_sid={sid}; Path=/; HttpOnly; SameSite=Lax")
    r.redirect(nxt)


def logout(r):
    if r.sid:
        DB.execute("DELETE FROM sessions WHERE sid=?", (r.sid,))
    r.sid = None
    r.out_cookies.append("spend_sid=; Path=/; Max-Age=0")
    r.redirect("/login?bye=1")


def home(r):
    r.redirect("/approvals" if r.role == "approver" else "/my")


def set_role(r):
    role = r.form.get("role")
    if role not in ("employee", "approver"):
        r.flash("Unknown view.", True)
        return r.redirect("/")
    if role != r.role:
        r.sess["role"] = role
        r.flash(f"Switched to the {'Approver' if role == 'approver' else 'Employee'} view.")
    r.redirect("/approvals" if role == "approver" else "/my")


def my_reports(r):
    me = r.user["id"]
    rows = q("SELECT r.*, a.name AS approver, (SELECT COALESCE(SUM(amount),0) FROM lines WHERE report_id=r.id) AS tot "
             "FROM reports r LEFT JOIN users a ON a.id=r.approver_id WHERE employee_id=? ORDER BY r.id DESC", (me,))
    pend = q1("SELECT COUNT(*) FROM reports WHERE status='Submitted' AND approver_id=?", (me,))[0]
    note = (f"<div class='note'>{pend} report(s) from your team are waiting for your approval. Switch to the "
            f"<b>Approver view</b> (top right) to review them.</div>") if pend else ""
    trs = "".join(f"<tr><td><a href='/reports/{x['id']}'>{code(x['id'])}</a></td><td>{esc(x['title'])}</td>"
                  f"<td>{fmt_day(x['submitted']) if x['submitted'] else '—'}</td><td>{badge(x['status'])}</td>"
                  f"<td>{esc(x['approver'] or '—')}</td><td class='num'>{money(x['tot'])}</td></tr>" for x in rows)
    body = (f"<h1>My expense reports</h1>{note}<p><a class='btn' href='/reports/new'>+ New report</a></p>"
            f"<table class='list'><tr><th>Report</th><th>Title</th><th>Submitted</th><th>Status</th><th>Approver</th>"
            f"<th class='num'>Total</th></tr>{trs or '<tr><td colspan=6 class=muted>No reports yet.</td></tr>'}</table>")
    r.page("My reports", body, "my")


def new_report_get(r):
    warn = r.need_role("employee", "Creating expense reports")
    if warn:
        return r.page("New report", "<h1>New expense report</h1>" + warn, "new")
    body = ("<h1>New expense report</h1><div class='card'><form method='post' action='/reports/new'><div class='grid2'>"
            "<div><label>Report title</label><input type='text' name='title' placeholder='e.g. Client visit Boston, 3-4 Nov'></div>"
            "<div><label>Pre-approval reference (if any)</label><input type='text' name='preapproval'></div>"
            "<div style='grid-column:1/3'><label>Business purpose</label><textarea name='purpose' rows='3'></textarea></div></div>"
            "<p><button type='submit'>Create report</button></p></form></div>")
    r.page("New report", body, "new")


def new_report_post(r):
    if r.role != "employee":
        r.flash("Switch to the Employee view to create expense reports.", True)
        return r.redirect("/reports/new")
    title = re.sub(r"\s+", " ", r.form.get("title", "")).strip()[:200]
    if not title:
        r.flash("Give the report a title.", True)
        return r.redirect("/reports/new")
    cur = DB.execute("INSERT INTO reports (employee_id,title,purpose,preapproval,status,approver_id,created) VALUES (?,?,?,?,?,?,?)",
                     (r.user["id"], title, r.form.get("purpose", "").strip()[:2000], r.form.get("preapproval", "").strip()[:200],
                      "Draft", r.user["manager_id"], now()))
    event(cur.lastrowid, r.user["id"], "created", title)
    r.flash(f"Report {code(cur.lastrowid)} created. Add one line per receipt, then submit it.")
    r.redirect(f"/reports/{cur.lastrowid}")


def get_report(rid):
    return q1("SELECT r.*, e.name AS employee, e.department, a.name AS approver, d.name AS decider FROM reports r "
              "JOIN users e ON e.id=r.employee_id LEFT JOIN users a ON a.id=r.approver_id LEFT JOIN users d ON d.id=r.decided_by "
              "WHERE r.id=?", (rid,))


def report_view(r, rid):
    rep = get_report(to_int(rid))
    if not rep:
        return r.error_page(404, "Report not found", f"There is no report {code(rid)}.")
    me, own = r.user["id"], rep["employee_id"] == r.user["id"]
    if not own:
        warn = r.need_role("approver", "Reviewing other people's reports")
        if warn:
            return r.page(code(rep["id"]), f"<h1>{code(rep['id'])}</h1>{warn}", "approvals")
    editable = own and rep["status"] == "Draft" and r.role == "employee"
    lines = q("SELECT l.*, c.filename, c.ctype FROM lines l LEFT JOIN receipts c ON c.id=l.receipt_id WHERE report_id=? "
              "ORDER BY l.date, l.id", (rep["id"],))
    trs = []
    for ln in lines:
        rec = ""
        if ln["receipt_id"]:
            if (ln["ctype"] or "").startswith("image/"):
                rec = (f"<a href='/receipts/{ln['receipt_id']}' target='_blank'>{esc(ln['filename'])}"
                       f"<img class='thumb' src='/receipts/{ln['receipt_id']}' alt='receipt'></a>")
            else:
                rec = f"<a href='/receipts/{ln['receipt_id']}' target='_blank'>&#128196; {esc(ln['filename'])}</a>"
        elif ln["amount"] >= 25:
            rec = "<span class='warn'>&#9888; Receipt missing</span>"
        else:
            rec = "<span class='muted'>not required (&lt; $25)</span>"
        if editable:
            if not ln["receipt_id"]:
                rec += (f"<form method='post' action='/reports/{rep['id']}/lines/{ln['id']}/receipt' enctype='multipart/form-data'>"
                        f"<input type='file' name='receipt'> <button class='sec'>Attach</button></form>")
            rec += (f"<form method='post' action='/reports/{rep['id']}/lines/{ln['id']}/delete' style='margin-top:4px'>"
                    f"<button class='sec'>Delete line</button></form>")
        att = ln["attendees"] if ln["category"] == "Meals" else ""
        trs.append(f"<tr><td>{fmt_day(ln['date'])}</td><td>{esc(ln['category'])}</td><td>{esc(ln['merchant'])}</td>"
                   f"<td>{esc(ln['description'])}</td><td class='num'>{esc(att)}</td><td class='num'>{money(ln['amount'])}</td><td>{rec}</td></tr>")
    trs.append(f"<tr class='total'><td colspan='5'>Total</td><td class='num'>{money(total(rep['id']))}</td><td></td></tr>")
    dec = ""
    if rep["decided"]:
        dec = (f"<tr><td>Decision</td><td>{badge(rep['status'] if rep['status'] != 'Paid' else 'Approved')} by {esc(rep['decider'])}, "
               f"{fmt_ts(rep['decided'])}</td></tr><tr><td>Approver comment</td><td>{esc(rep['comment'] or '—')}</td></tr>")
    info = (f"<table class='kv'><tr><td>Employee</td><td>{esc(rep['employee'])} ({esc(rep['department'])})</td></tr>"
            f"<tr><td>Business purpose</td><td>{esc(rep['purpose'] or '—')}</td></tr>"
            f"<tr><td>Pre-approval</td><td>{esc(rep['preapproval'] or '—')}</td></tr>"
            f"<tr><td>Submitted</td><td>{fmt_day(rep['submitted']) if rep['submitted'] else 'not yet'}</td></tr>"
            f"<tr><td>Approver</td><td>{esc(rep['approver'] or '—')}</td></tr>{dec}</table>")
    actions = ""
    if editable:
        actions = (f"<div class='card'><h2 style='margin-top:0'>Add an expense line</h2><form method='post' action='/reports/{rep['id']}/lines' "
                   f"enctype='multipart/form-data'><div class='grid2'><div><label>Date (YYYY-MM-DD)</label><input type='text' name='date'></div>"
                   f"<div><label>Category</label><select name='category'>{options(CATEGORIES, '', '— choose —')}</select></div>"
                   f"<div><label>Merchant</label><input type='text' name='merchant'></div><div><label>Amount (USD)</label><input type='text' name='amount'></div>"
                   f"<div><label>Attendees (meals only, incl. you)</label><input type='number' name='attendees' value='1' min='1'></div>"
                   f"<div><label>Receipt (PDF or image)</label><input type='file' name='receipt'></div>"
                   f"<div style='grid-column:1/3'><label>Description</label><input type='text' name='description'></div></div>"
                   f"<p><button type='submit'>Add line</button></p></form></div>"
                   f"<form method='post' action='/reports/{rep['id']}/submit'><button>Submit for approval</button> "
                   f"<span class='muted'>The report goes to {esc(rep['approver'] or 'your manager')}.</span></form>")
    elif own and rep["status"] == "Draft":
        actions = r.need_role("employee", "Editing your own reports")
    elif own and rep["status"] == "Submitted":
        actions = (f"<form method='post' action='/reports/{rep['id']}/recall'><button class='sec'>Recall to draft</button> "
                   f"<span class='muted'>Waiting for {esc(rep['approver'])}.</span></form>") if r.role == "employee" else ""
    elif rep["status"] == "Submitted" and rep["approver_id"] == me:
        actions = r.need_role("approver", "Approving and rejecting reports") or (
            f"<div class='card'><h2 style='margin-top:0'>Your decision</h2><form method='post' action='/reports/{rep['id']}/decide'>"
            f"<label class='muted'>Comment to {esc(rep['employee'])} (required when rejecting)</label><textarea name='comment' rows='3'></textarea>"
            f"<p><button name='decision' value='approve'>Approve</button> <button name='decision' value='reject' class='red'>Reject</button></p></form></div>")
    hist = "".join(f"<li><span class='muted'>{fmt_ts(e['ts'])}</span> {esc(e['name'])}: {esc(e['action'])} {esc(e['detail'])}</li>"
                   for e in q("SELECT e.*, u.name FROM events e LEFT JOIN users u ON u.id=e.user_id WHERE report_id=? ORDER BY e.id", (rep["id"],)))
    back = "/my" if own else "/approvals"
    body = (f"<p class='muted'><a href='{back}'>&laquo; Back</a></p><h1>{code(rep['id'])} &middot; {esc(rep['title'])} {badge(rep['status'])}</h1>"
            f"<div class='card'>{info}</div><table class='list'><tr><th>Date</th><th>Category</th><th>Merchant</th><th>Description</th>"
            f"<th class='num'>Attendees</th><th class='num'>Amount</th><th>Receipt</th></tr>{''.join(trs)}</table><br>{actions}"
            f"<h2>History</h2><ul class='muted'>{hist or '<li>—</li>'}</ul>")
    r.page(code(rep["id"]), body, "my" if own else "approvals")


def own_draft(r, rid):
    rep = q1("SELECT * FROM reports WHERE id=?", (to_int(rid),))
    if not rep:
        r.error_page(404, "Report not found", "There is no such report.")
        return None
    if rep["employee_id"] != r.user["id"] or rep["status"] != "Draft":
        r.flash("Only your own draft reports can be changed.", True)
        r.redirect(f"/reports/{rep['id']}")
        return None
    if r.role != "employee":
        r.flash("Switch to the Employee view to edit your reports. Nothing was saved.", True)
        r.redirect(f"/reports/{rep['id']}")
        return None
    return rep


def add_line(r, rid):
    rep = own_draft(r, rid)
    if not rep:
        return
    f = r.form
    date, amount = parse_date(f.get("date")), parse_amount(f.get("amount"))
    errs = []
    if not date:
        errs.append("a valid date (YYYY-MM-DD)")
    if f.get("category") not in CATEGORIES:
        errs.append("a category")
    if not f.get("merchant", "").strip():
        errs.append("the merchant")
    if amount is None:
        errs.append("an amount in USD")
    if errs:
        r.flash("The line was not added. Please enter " + ", ".join(errs) + ".", True)
        return r.redirect(f"/reports/{rep['id']}")
    att = min(max(to_int(f.get("attendees"), 1) or 1, 1), 500)
    rec, err = store_receipt(r, "receipt")
    if err:
        r.flash(err + " The line was not added.", True)
        return r.redirect(f"/reports/{rep['id']}")
    DB.execute("INSERT INTO lines (report_id,date,category,merchant,amount,attendees,description,receipt_id,created) VALUES (?,?,?,?,?,?,?,?,?)",
               (rep["id"], date, f["category"], f["merchant"].strip()[:120], amount, att, f.get("description", "").strip()[:300], rec, now()))
    event(rep["id"], r.user["id"], "line added", f"{date} {f['category']} {money(amount)}" + (" with receipt" if rec else ""))
    r.flash(f"Line added: {f['merchant'].strip()[:60]}, {money(amount)}" + ("" if rec else " (no receipt attached)") + ".")
    r.redirect(f"/reports/{rep['id']}")


def attach_receipt(r, rid, lid):
    rep = own_draft(r, rid)
    if not rep:
        return
    ln = q1("SELECT * FROM lines WHERE id=? AND report_id=?", (to_int(lid), rep["id"]))
    rec, err = store_receipt(r, "receipt")
    if not ln or not rec:
        r.flash(err or "Choose a receipt file first.", True)
        return r.redirect(f"/reports/{rep['id']}")
    DB.execute("UPDATE lines SET receipt_id=? WHERE id=?", (rec, ln["id"]))
    event(rep["id"], r.user["id"], "receipt attached", ln["merchant"])
    r.flash("Receipt attached.")
    r.redirect(f"/reports/{rep['id']}")


def delete_line(r, rid, lid):
    rep = own_draft(r, rid)
    if not rep:
        return
    ln = q1("SELECT * FROM lines WHERE id=? AND report_id=?", (to_int(lid), rep["id"]))
    if ln:
        DB.execute("DELETE FROM lines WHERE id=?", (ln["id"],))
        event(rep["id"], r.user["id"], "line deleted", f"{ln['merchant']} {money(ln['amount'])}")
        r.flash("Line deleted.")
    r.redirect(f"/reports/{rep['id']}")


def submit_report(r, rid):
    rep = own_draft(r, rid)
    if not rep:
        return
    if not q1("SELECT COUNT(*) FROM lines WHERE report_id=?", (rep["id"],))[0]:
        r.flash("Add at least one expense line before submitting.", True)
        return r.redirect(f"/reports/{rep['id']}")
    DB.execute("UPDATE reports SET status='Submitted', submitted=? WHERE id=?", (dt.date.today().isoformat(), rep["id"]))
    event(rep["id"], r.user["id"], "submitted", f"total {money(total(rep['id']))}")
    r.flash(f"{code(rep['id'])} submitted for approval.")
    r.redirect(f"/reports/{rep['id']}")


def recall_report(r, rid):
    rep = q1("SELECT * FROM reports WHERE id=?", (to_int(rid),))
    if not rep or rep["employee_id"] != r.user["id"] or rep["status"] != "Submitted" or r.role != "employee":
        r.flash("This report cannot be recalled (only your own submitted reports, in the Employee view).", True)
        return r.redirect(f"/reports/{rep['id']}" if rep else "/my")
    DB.execute("UPDATE reports SET status='Draft', submitted=NULL WHERE id=?", (rep["id"],))
    event(rep["id"], r.user["id"], "recalled to draft")
    r.flash(f"{code(rep['id'])} is a draft again.")
    r.redirect(f"/reports/{rep['id']}")


def decide(r, rid):
    rep = q1("SELECT * FROM reports WHERE id=?", (to_int(rid),))
    if not rep:
        return r.error_page(404, "Report not found", "There is no such report.")
    back = f"/reports/{rep['id']}"
    if r.role != "approver":
        r.flash("Switch to the Approver view to approve or reject reports. Your decision was not saved.", True)
        return r.redirect(back)
    if rep["employee_id"] == r.user["id"]:
        r.flash("You cannot approve or reject your own report.", True)
        return r.redirect(back)
    if rep["status"] != "Submitted" or rep["approver_id"] != r.user["id"]:
        r.flash(f"{code(rep['id'])} is not waiting for your approval (status: {rep['status']}).", True)
        return r.redirect(back)
    d, comment = r.form.get("decision"), r.form.get("comment", "").strip()[:2000]
    if d not in ("approve", "reject"):
        r.flash("Choose Approve or Reject.", True)
        return r.redirect(back)
    if d == "reject" and not comment:
        r.flash("Please write a comment explaining why the report is rejected. Nothing was saved.", True)
        return r.redirect(back)
    st = "Approved" if d == "approve" else "Rejected"
    DB.execute("UPDATE reports SET status=?, decided=?, decided_by=?, comment=? WHERE id=?", (st, now(), r.user["id"], comment, rep["id"]))
    event(rep["id"], r.user["id"], st.lower(), comment)
    r.flash(f"{code(rep['id'])} {st.lower()}.")
    r.redirect("/approvals")


def approvals(r):
    warn = r.need_role("approver", "The approvals queue")
    if warn:
        return r.page("Approvals", "<h1>Approvals</h1>" + warn, "approvals")
    me = r.user["id"]
    base = ("SELECT r.*, e.name AS employee, (SELECT COUNT(*) FROM lines WHERE report_id=r.id) AS n, "
            "(SELECT COALESCE(SUM(amount),0) FROM lines WHERE report_id=r.id) AS tot FROM reports r JOIN users e ON e.id=r.employee_id ")
    pend = q(base + "WHERE r.status='Submitted' AND r.approver_id=? ORDER BY r.submitted, r.id", (me,))
    done = q(base + "WHERE r.decided_by=? ORDER BY r.decided DESC LIMIT 15", (me,))
    tr1 = "".join(f"<tr><td><a href='/reports/{x['id']}'>{code(x['id'])}</a></td><td>{esc(x['employee'])}</td><td>{esc(x['title'])}</td>"
                  f"<td>{fmt_day(x['submitted'])}</td><td class='num'>{x['n']}</td><td class='num'>{money(x['tot'])}</td>"
                  f"<td><a class='btn sec' href='/reports/{x['id']}'>Review</a></td></tr>" for x in pend)
    tr2 = "".join(f"<tr><td><a href='/reports/{x['id']}'>{code(x['id'])}</a></td><td>{esc(x['employee'])}</td><td>{esc(x['title'])}</td>"
                  f"<td>{badge(x['status'])}</td><td>{fmt_ts(x['decided'])}</td><td class='num'>{money(x['tot'])}</td></tr>" for x in done)
    body = (f"<h1>Waiting for your approval ({len(pend)})</h1><table class='list'><tr><th>Report</th><th>Employee</th><th>Title</th>"
            f"<th>Submitted</th><th class='num'>Lines</th><th class='num'>Total</th><th></th></tr>"
            f"{tr1 or '<tr><td colspan=7 class=muted>Nothing waiting for you.</td></tr>'}</table>"
            f"<h2>Recently decided by you</h2><table class='list'><tr><th>Report</th><th>Employee</th><th>Title</th><th>Decision</th>"
            f"<th>Decided</th><th class='num'>Total</th></tr>{tr2 or '<tr><td colspan=6 class=muted>—</td></tr>'}</table>")
    r.page("Approvals", body, "approvals")


DEFAULT_F = {"q": "", "status": "any", "month": "any", "dept": "", "employee": "any", "sort": "submitted", "dir": "desc", "page": "1"}
SORTS = {"id": "r.id", "employee": "e.name COLLATE NOCASE", "title": "r.title COLLATE NOCASE", "submitted": "r.submitted",
         "status": "r.status", "total": "tot", "dept": "e.department"}


def report_filter(r):
    f = dict(DEFAULT_F, dept=r.user["department"])
    f.update(r.sess.get("rf", {}))
    if r.qs.get("reset"):
        f = dict(DEFAULT_F, dept=r.user["department"])
    elif any(k in r.qs for k in DEFAULT_F):
        for k in DEFAULT_F:
            if k in r.qs:
                f[k] = r.qs[k][:100]
        if "page" not in r.qs:
            f["page"] = "1"
    if f["sort"] not in SORTS:
        f["sort"] = "submitted"
    if f["dir"] not in ("asc", "desc"):
        f["dir"] = "desc"
    return f


def report_where(f):
    where, args = ["r.status <> 'Draft'"], []
    if f["status"] in STATUSES:
        where.append("r.status=?")
        args.append(f["status"])
    if re.fullmatch(r"\d{4}-\d{2}", f["month"] or ""):
        where.append("substr(r.submitted,1,7)=?")
        args.append(f["month"])
    if f["dept"] and f["dept"] != "any":
        where.append("e.department=?")
        args.append(f["dept"])
    if to_int(f["employee"]):
        where.append("r.employee_id=?")
        args.append(to_int(f["employee"]))
    text = (f["q"] or "").strip()
    if text:
        if report_id(text):
            where.append("r.id=?")
            args.append(report_id(text))
        else:
            where.append("(r.title LIKE ? OR e.name LIKE ?)")
            args += [f"%{text}%"] * 2
    return " WHERE " + " AND ".join(where), args


REPORT_SQL = ("SELECT r.*, e.name AS employee, e.department, d.name AS decider, "
              "(SELECT COALESCE(SUM(amount),0) FROM lines WHERE report_id=r.id) AS tot FROM reports r "
              "JOIN users e ON e.id=r.employee_id LEFT JOIN users d ON d.id=r.decided_by")


def reports_list(r):
    warn = r.need_role("approver", "The Reports list")
    if warn:
        return r.page("Reports", "<h1>Reports</h1>" + warn, "reports")
    f = report_filter(r)
    where, args = report_where(f)
    n = q1(f"SELECT COUNT(*) FROM reports r JOIN users e ON e.id=r.employee_id{where}", args)[0]
    pages = max(1, (n + PER_PAGE - 1) // PER_PAGE)
    page = min(max(1, to_int(f["page"], 1) or 1), pages)
    f["page"] = str(page)
    r.sess["rf"] = f
    r.save_session()
    rows = q(f"{REPORT_SQL}{where} ORDER BY {SORTS[f['sort']]} {f['dir']}, r.id DESC LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", args)
    months = [m[0] for m in q("SELECT DISTINCT substr(submitted,1,7) FROM reports WHERE submitted IS NOT NULL ORDER BY 1 DESC")]
    depts = [d[0] for d in q("SELECT DISTINCT department FROM users ORDER BY 1")]
    emps = [(u["id"], u["name"]) for u in q("SELECT id, name FROM users ORDER BY name")]

    def mlabel(m):
        try:
            return dt.date.fromisoformat(m + "-01").strftime("%B %Y")
        except ValueError:
            return m

    def link(**kw):
        return "/reports?" + urllib.parse.urlencode(dict(f, **kw))

    def th(key, label, cls=""):
        d = "asc" if f["sort"] != key or f["dir"] == "desc" else "desc"
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if f["sort"] == key else ""
        return f'<th class="{cls}"><a href="{esc(link(sort=key, dir=d, page=1))}">{label}{arrow}</a></th>'
    filt = (f"<form class='filters' method='get' action='/reports'><input type='text' name='q' value='{esc(f['q'])}' placeholder='EXP number, title or employee'>"
            f"<select name='status'>{options([('any', 'Any status')] + STATUSES[1:], f['status'])}</select>"
            f"<select name='month'>{options([('any', 'Any month (submitted)')] + [(m, mlabel(m)) for m in months], f['month'])}</select>"
            f"<select name='dept'>{options([('any', 'All departments')] + depts, f['dept'])}</select>"
            f"<select name='employee'>{options([('any', 'Any employee')] + emps, f['employee'])}</select>"
            f"<input type='hidden' name='sort' value='{esc(f['sort'])}'><input type='hidden' name='dir' value='{esc(f['dir'])}'>"
            f"<button type='submit'>Apply</button> <a href='/reports?reset=1'>Reset</a></form>")
    trs = "".join(f"<tr><td><a href='/reports/{x['id']}'>{code(x['id'])}</a></td><td>{esc(x['employee'])}</td><td>{esc(x['department'])}</td>"
                  f"<td>{esc(x['title'])}</td><td>{fmt_day(x['submitted'])}</td><td>{badge(x['status'])}</td>"
                  f"<td>{esc(x['decider'] or '—')}</td><td class='num'>{money(x['tot'])}</td></tr>" for x in rows)
    pager = [f"<span class='muted'>{n} report(s)</span>"]
    for p in range(1, pages + 1):
        pager.append(f"<b>{p}</b>" if p == page else f"<a href='{esc(link(page=p))}'>{p}</a>")
    body = (f"<h1>Reports</h1>{filt}<table class='list'><tr>{th('id', 'Report')}{th('employee', 'Employee')}{th('dept', 'Department')}"
            f"{th('title', 'Title')}{th('submitted', 'Submitted')}{th('status', 'Status')}<th>Decided by</th>{th('total', 'Total', 'num')}</tr>"
            f"{trs or '<tr><td colspan=8 class=muted>No reports match these filters.</td></tr>'}</table>"
            f"<div class='pager'>{''.join(pager)}</div><p><a class='btn' href='/reports/export.csv'>Export CSV</a> "
            f"<span class='muted'>Exports all {n} report(s) matching the current filters.</span></p>")
    r.page("Reports", body, "reports")


def export_csv(r):
    if r.role != "approver":
        r.flash("Exports are part of the Approver view.", True)
        return r.redirect("/my")
    f = report_filter(r)
    where, args = report_where(f)
    rows = q(f"{REPORT_SQL}{where} ORDER BY {SORTS[f['sort']]} {f['dir']}, r.id DESC", args)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Report", "Employee", "Department", "Title", "Submitted", "Status", "Total (USD)", "Decided by", "Decided on"])
    for x in rows:
        w.writerow([code(x["id"]), x["employee"], x["department"], x["title"], x["submitted"] or "", x["status"],
                    f"{x['tot']:.2f}", x["decider"] or "", (x["decided"] or "")[:10]])
    DB.execute("INSERT INTO exports (user_id,ts,filters,report_ids) VALUES (?,?,?,?)",
               (r.user["id"], now(), json.dumps(f), ",".join(str(x["id"]) for x in rows)))
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    r.send(200, out.getvalue().encode("utf-8"), "text/csv; charset=utf-8",
           [("Content-Disposition", f'attachment; filename="fenwick_spend_export_{stamp}.csv"')])


def receipt(r, cid):
    c = q1("SELECT * FROM receipts WHERE id=?", (to_int(cid),))
    if not c:
        return r.error_page(404, "Receipt not found", "This receipt does not exist.")
    r.send(200, c["data"], c["ctype"] or "application/octet-stream",
           [("Content-Disposition", 'inline; filename="%s"' % re.sub(r'[^\w .\-]', '_', c["filename"]))])


ROUTES = [
    ("GET", r"/login", login_get, True), ("POST", r"/login", login_post, True), ("GET", r"/logout", logout, True),
    ("GET", r"/", home, False), ("POST", r"/role", set_role, False), ("GET", r"/my", my_reports, False),
    ("GET", r"/reports/new", new_report_get, False), ("POST", r"/reports/new", new_report_post, False),
    ("GET", r"/reports/export\.csv", export_csv, False), ("GET", r"/reports", reports_list, False),
    ("GET", r"/reports/(\d+)", report_view, False), ("POST", r"/reports/(\d+)/lines", add_line, False),
    ("POST", r"/reports/(\d+)/lines/(\d+)/receipt", attach_receipt, False),
    ("POST", r"/reports/(\d+)/lines/(\d+)/delete", delete_line, False), ("POST", r"/reports/(\d+)/submit", submit_report, False),
    ("POST", r"/reports/(\d+)/recall", recall_report, False), ("POST", r"/reports/(\d+)/decide", decide, False),
    ("GET", r"/approvals", approvals, False), ("GET", r"/receipts/(\d+)", receipt, False),
]


def make_server(db_path, host="127.0.0.1", port=8102):
    global DB
    DB = sqlite3.connect(db_path, check_same_thread=False)
    init_schema(DB)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8102)
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
