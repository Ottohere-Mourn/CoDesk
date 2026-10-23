#!/usr/bin/env python3
"""Bluepeak CRM - Bluepeak Outdoor's internal sales CRM (single file, Python 3 stdlib only).

    python3 app.py --db crm.db --port 8103          # serves http://127.0.0.1:8103/

http.server + sqlite3, server-rendered HTML, cookie sessions stored in the database. The account list remembers its
search/filters per session, edit forms save every field shown on them, and merging two accounts moves contacts,
opportunities and activities to the surviving record and retires the other one (read-only tombstone).
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

TITLE = "Bluepeak CRM"
STAGES = ["Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
ACT_TYPES = ["Call", "Meeting", "Email", "Note"]
INDUSTRIES = ["Outdoor Retail", "Sporting Goods Retail", "Climbing & Mountaineering", "Paddle Sports", "Camping",
              "Ski & Snowboard", "Cycling", "Marine Supply", "Online Retail", "Rental & Guiding"]
COUNTRIES = ["United States", "Canada", "United Kingdom", "Germany", "Austria", "Switzerland"]
PER_PAGE = 20
FIELDS = [("name", "Account name"), ("website", "Website"), ("tax_id", "Tax / VAT ID"), ("erp_no", "ERP number"),
          ("phone", "Phone"), ("industry", "Industry"), ("street", "Street"), ("city", "City"), ("postcode", "Postcode"),
          ("country", "Country"), ("owner_id", "Owner")]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, name TEXT, email TEXT,
  title TEXT, region TEXT, active INTEGER DEFAULT 1, left_on TEXT, can_login INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, name TEXT, website TEXT, tax_id TEXT, erp_no TEXT,
  phone TEXT, industry TEXT, street TEXT, city TEXT, postcode TEXT, country TEXT, owner_id INTEGER, created TEXT,
  updated TEXT, status TEXT DEFAULT 'active', merged_into INTEGER, merged_at TEXT);
CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, account_id INTEGER, first TEXT, last TEXT, title TEXT,
  email TEXT, phone TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS opps (id INTEGER PRIMARY KEY, account_id INTEGER, name TEXT, amount REAL, stage TEXT,
  close_date TEXT, owner_id INTEGER, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS activities (id INTEGER PRIMARY KEY, account_id INTEGER, contact_id INTEGER, type TEXT,
  date TEXT, subject TEXT, notes TEXT, user_id INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS merges (id INTEGER PRIMARY KEY, master_id INTEGER, merged_id INTEGER, user_id INTEGER,
  choices TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, entity TEXT, entity_id INTEGER, user_id INTEGER, rid TEXT,
  field TEXT, old TEXT, new TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS pages (slug TEXT PRIMARY KEY, title TEXT, body TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, user_id INTEGER, data TEXT, created TEXT);
"""

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",Ubuntu,Arial,sans-serif;color:#1f2a24;background:#f2f5f3}
a{color:#1b6b4a;text-decoration:none}a:hover{text-decoration:underline}
header{background:#173d2e;color:#fff;display:flex;align-items:center;padding:0 18px;height:48px;gap:22px}
header .brand{font-weight:700;font-size:16px}header .brand span{color:#8fd9a8}
header nav a{color:#cfe6d8;padding:14px 8px;display:inline-block}header nav a.on{color:#fff;border-bottom:3px solid #8fd9a8}
header .me{margin-left:auto;color:#cfe6d8}header .me a{color:#fff;margin-left:10px}
main{padding:18px 22px;max-width:1500px;margin:0 auto}h1{font-size:20px;margin:4px 0 14px}h2{font-size:16px;margin:20px 0 8px}
.flash{padding:9px 12px;border-radius:4px;margin-bottom:12px;background:#e3f4e8;border:1px solid #9fd3ad}
.flash.err{background:#fde8e8;border-color:#f0a5a5}table.list{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d5ddd8}
table.list th{background:#e9efeb;text-align:left;padding:7px 8px;font-weight:600;border-bottom:1px solid #d5ddd8;white-space:nowrap}
table.list td{padding:6px 8px;border-bottom:1px solid #edf1ee;vertical-align:top}table.list tr:hover td{background:#f7fbf8}
.badge{display:inline-block;padding:1px 7px;border-radius:9px;font-size:12px;font-weight:600;background:#e2e8e4}
.st-ClosedWon{background:#cdeed8}.st-ClosedLost{background:#eee;color:#666}.st-Negotiation{background:#ffe2b8}
.st-Proposal{background:#d7e8ff}.st-Qualification{background:#efe3ff}.inactive{background:#fde2e2;color:#9b2c2c}
.filters{background:#fff;border:1px solid #d5ddd8;padding:9px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],input[type=password],select,textarea{font:inherit;padding:5px 7px;border:1px solid #b6c4bb;border-radius:3px;background:#fff}
textarea{width:100%}button,.btn{font:inherit;background:#1b6b4a;color:#fff;border:0;border-radius:3px;padding:6px 14px;cursor:pointer;display:inline-block}
.btn.sec{background:#e2e9e5;color:#1f2a24}.btn.warn{background:#b7791f}.pager{margin:10px 0;display:flex;gap:6px;align-items:center}
.pager a,.pager b{padding:3px 9px;border:1px solid #d5ddd8;background:#fff;border-radius:3px}.pager b{background:#1b6b4a;color:#fff}
.card{background:#fff;border:1px solid #d5ddd8;border-radius:4px;padding:12px 14px;margin-bottom:12px}
.kv td{padding:4px 14px 4px 0;vertical-align:top}.kv td.k{color:#66756c;width:170px}.muted{color:#66756c;font-size:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:4px 30px}details{margin:8px 0}summary{cursor:pointer;color:#1b6b4a;font-weight:600}
.form label{display:block;font-weight:600;margin:8px 0 3px}.form input[type=text],.form select{width:100%;max-width:420px}
.tomb{background:#fff4d6;border:1px solid #e6c36a;padding:12px 14px;border-radius:4px;margin-bottom:12px}
.act{border-left:3px solid #8fd9a8;padding:6px 10px;margin-bottom:8px;background:#fff}
.cmp td,.cmp th{padding:6px 10px;border-bottom:1px solid #e3e9e5;text-align:left}.cmp{border-collapse:collapse;background:#fff;width:100%}
.kb h3{font-size:15px;margin:14px 0 4px}.kb table{border-collapse:collapse}.kb td,.kb th{border:1px solid #cdd8d1;padding:4px 8px}
.login{max-width:360px;margin:90px auto;background:#fff;border:1px solid #d5ddd8;padding:26px;border-radius:6px}
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
        v = int(str(s).strip().lstrip("#").upper().replace("ACC-", "").replace("OPP-", ""))
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
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_amount(s):
    try:
        v = round(float(re.sub(r"[\s$,]|USD", "", str(s or ""))), 2)
        return v if 0 <= v < 1e10 else None
    except ValueError:
        return None


def money(v):
    return f"${v:,.2f}" if isinstance(v, (int, float)) else ""


def fmt_date(s):
    try:
        return dt.datetime.fromisoformat(s).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return s or ""


def options(items, selected, blank=None):
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for it in items:
        v, lab = it if isinstance(it, tuple) else (it, it)
        sel = " selected" if str(v) == str(selected if selected is not None else "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{esc(lab)}</option>')
    return "".join(out)


def render_text(body):
    """Wiki markup: '## ' headings, '- ' bullets, blank line = new paragraph."""
    out = []
    for block in re.split(r"\n\s*\n", body or ""):
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        for ln in lines:
            if ln.startswith("## "):
                out.append(f"<h3>{esc(ln[3:])}</h3>")
            elif ln.startswith("- "):
                out.append(f"<ul><li>{esc(ln[2:])}</li></ul>")
            else:
                out.append(f"<p>{esc(ln)}</p>")
    return "".join(out).replace("</ul><ul>", "")


def acc_id(i):
    return f"ACC-{i}"


def opp_id(i):
    return f"OPP-{i}"


def users():
    return q("SELECT * FROM users ORDER BY name")


def user_name(uid):
    u = q1("SELECT name, active FROM users WHERE id=?", (uid,)) if uid else None
    return (u["name"] + ("" if u["active"] else " (inactive)")) if u else ""


# ------------------------------------------------------------------------------------------------ request handling
class Handler(BaseHTTPRequestHandler):
    server_version = "BluepeakCRM/2.4"
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
                    self.form = {k: v[-1].strip() for k, v in self.fm.items()}
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
        except Exception:  # never let one bad request take the CRM down
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
        sid = c["crm_sid"].value if "crm_sid" in c else None
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
        links = [("accounts", "/accounts", "Accounts"), ("opps", "/opps", "Opportunities"), ("merges", "/merges", "Merge history"),
                 ("users", "/users", "Users"), ("guide", "/guide", "Data quality guide")]
        navh = "".join(f'<a href="{h}" class="{"on" if k == nav else ""}">{t}</a>' for k, h, t in links)
        me = (f'<div class="me">{esc(self.user["name"])} &middot; {esc(self.user["title"])}'
              f'<a href="/logout">Log out</a></div>') if self.user else ""
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)} - {TITLE}</title>"
               f"<style>{CSS}</style></head><body><header><div class='brand'>Bluepeak <span>CRM</span></div>"
               f"<nav>{navh if self.user else ''}</nav>{me}</header><main>{fl}{body}</main></body></html>")
        self.send(200, doc)

    def error_page(self, code, title, msg, link=("/accounts", "Back to accounts")):
        body = f"<h1>{esc(title)}</h1><div class='card'>{esc(msg)}<p><a href='{esc(link[0])}'>{esc(link[1])}</a></p></div>"
        doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style>"
               f"</head><body><header><div class='brand'>Bluepeak <span>CRM</span></div></header>"
               f"<main>{body}</main></body></html>")
        self.send(code, doc)


# ------------------------------------------------------------------------------------------------ auth
def login_get(r):
    nxt = r.qs.get("next", "/accounts")
    msg = '<div class="flash err">Wrong username or password.</div>' if r.qs.get("err") else ""
    if r.qs.get("bye"):
        msg = '<div class="flash">You have been logged out.</div>'
    body = (f"<div class='login'><h1>Sign in to Bluepeak CRM</h1>{msg}<form method='post' action='/login'>"
            f"<input type='hidden' name='next' value='{esc(nxt)}'><label>Username</label>"
            f"<input type='text' name='username' autofocus><label>Password</label><input type='password' name='password'>"
            f"<button type='submit'>Sign in</button></form><p class='muted'>Bluepeak Outdoor &middot; internal use only</p></div>")
    r.page("Sign in", body)


def login_post(r):
    u = q1("SELECT * FROM users WHERE username=? AND can_login=1", (r.form.get("username", "").lower(),))
    nxt = r.form.get("next") or "/accounts"
    if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/login"):
        nxt = "/accounts"
    if not u or u["password"] != r.fm.get("password", [""])[-1]:
        return r.redirect("/login?err=1&next=" + urllib.parse.quote(nxt))
    sid = secrets.token_hex(16)
    DB.execute("INSERT INTO sessions VALUES (?,?,?,?)", (sid, u["id"], "{}", now()))
    r.sid, r.sess, r.user = sid, {}, u
    r.out_cookies.append(f"crm_sid={sid}; Path=/; HttpOnly; SameSite=Lax")
    r.redirect(nxt)


def logout(r):
    if r.sid:
        DB.execute("DELETE FROM sessions WHERE sid=?", (r.sid,))
    r.sid = None
    r.out_cookies.append("crm_sid=; Path=/; Max-Age=0")
    r.redirect("/login?bye=1")


def home(r):
    r.redirect("/accounts")


# ------------------------------------------------------------------------------------------------ accounts
DEFAULT_F = {"q": "", "owner": "any", "industry": "", "country": "", "merged": "", "sort": "name", "dir": "asc", "page": "1"}
SORTS = {"id": "a.id", "name": "a.name COLLATE NOCASE", "city": "a.city COLLATE NOCASE", "country": "a.country",
         "owner": "COALESCE(u.name,'')", "created": "a.created", "website": "a.website COLLATE NOCASE"}


def accounts_list(r):
    f = dict(DEFAULT_F, **r.sess.get("af", {}))
    if r.qs.get("reset"):
        f = dict(DEFAULT_F)
    elif any(k in r.qs for k in DEFAULT_F):
        for k in DEFAULT_F:
            if k in r.qs:
                f[k] = r.qs[k]
        if "merged" not in r.qs and "q" in r.qs:
            f["merged"] = ""  # unticked checkbox of the filter form
        if "page" not in r.qs:
            f["page"] = "1"
    f["sort"] = f["sort"] if f.get("sort") in SORTS else "name"
    f["dir"] = f["dir"] if f.get("dir") in ("asc", "desc") else "asc"
    where, args = [], []
    if not f["merged"]:
        where.append("a.status='active'")
    text = (f["q"] or "").strip()
    if text:
        where.append("(a.name LIKE ? OR a.website LIKE ? OR a.tax_id LIKE ? OR a.erp_no LIKE ? OR a.city LIKE ? OR 'ACC-'||a.id = ?)")
        args += [f"%{text}%"] * 5 + [text.upper()]
    if to_int(f["owner"]):
        where.append("a.owner_id=?")
        args.append(to_int(f["owner"]))
    if f["industry"] in INDUSTRIES:
        where.append("a.industry=?")
        args.append(f["industry"])
    if f["country"] in COUNTRIES:
        where.append("a.country=?")
        args.append(f["country"])
    w = (" WHERE " + " AND ".join(where)) if where else ""
    base = "FROM accounts a LEFT JOIN users u ON u.id=a.owner_id"
    total = q1(f"SELECT COUNT(*) {base}{w}", args)[0]
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(max(1, to_int(f["page"], 1)), pages)
    f["page"] = str(page)
    r.sess["af"] = f
    rows = q(f"SELECT a.*, u.name AS owner, u.active AS owner_active {base}{w} ORDER BY {SORTS[f['sort']]} {f['dir']}, a.id "
             f"LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", args)
    hint = ""
    if text and not f["merged"]:
        n = q1("SELECT COUNT(*) FROM accounts a WHERE a.status='merged' AND (a.name LIKE ? OR a.website LIKE ? OR a.tax_id LIKE ?)",
               [f"%{text}%"] * 3)[0]
        if n:
            hint = f"<p class='muted'>{n} merged (retired) account(s) also match. <a href='/accounts?{esc(urllib.parse.urlencode(dict(f, merged='1', page=1)))}'>Show merged accounts</a></p>"

    def link(**kw):
        return "/accounts?" + urllib.parse.urlencode(dict(f, **kw))

    def th(key, label):
        d = "asc" if f["sort"] != key or f["dir"] == "desc" else "desc"
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if f["sort"] == key else ""
        return f'<th><a href="{esc(link(sort=key, dir=d, page=1))}">{label}{arrow}</a></th>'
    trs = []
    for a in rows:
        tomb = " <span class='badge'>merged</span>" if a["status"] == "merged" else ""
        own = esc(a["owner"] or "—") + ("" if a["owner_active"] or not a["owner"] else " <span class='badge inactive'>inactive</span>")
        trs.append(f"<tr><td>{acc_id(a['id'])}</td><td><a href='/accounts/{a['id']}'>{esc(a['name'])}</a>{tomb}</td>"
                   f"<td>{esc(a['city'])}</td><td>{esc(a['country'])}</td><td>{esc(a['website'])}</td><td>{esc(a['tax_id'])}</td>"
                   f"<td>{own}</td><td class='muted'>{esc(a['created'])}</td></tr>")
    if not trs:
        trs.append("<tr><td colspan='8' class='muted'>No accounts match these filters.</td></tr>")
    pager = [f"<span class='muted'>Showing {(page - 1) * PER_PAGE + 1 if total else 0}–{min(total, page * PER_PAGE)} of {total}</span>"]
    if page > 1:
        pager.append(f"<a href='{esc(link(page=page - 1))}'>&laquo; Prev</a>")
    for p in range(1, pages + 1):
        pager.append(f"<b>{p}</b>" if p == page else f"<a href='{esc(link(page=p))}'>{p}</a>")
    if page < pages:
        pager.append(f"<a href='{esc(link(page=page + 1))}'>Next &raquo;</a>")
    owners = [(u["id"], u["name"]) for u in users() if u["id"] != r.user["id"]]
    filt = (f"<form class='filters' method='get' action='/accounts'>"
            f"<input type='text' name='q' value='{esc(f['q'])}' placeholder='Name, website, tax ID, ERP no., city' size='34'>"
            f"<select name='owner'>{options([('any', 'Any owner')] + owners, f['owner'])}</select>"
            f"<select name='industry'>{options(INDUSTRIES, f['industry'], 'Any industry')}</select>"
            f"<select name='country'>{options(COUNTRIES, f['country'], 'Any country')}</select>"
            f"<label><input type='checkbox' name='merged' value='1'{' checked' if f['merged'] else ''}> include merged</label>"
            f"<input type='hidden' name='sort' value='{esc(f['sort'])}'><input type='hidden' name='dir' value='{esc(f['dir'])}'>"
            f"<button type='submit'>Search</button> <a href='/accounts?reset=1'>Clear</a></form>")
    body = (f"<h1>Accounts <a class='btn sec' style='float:right;font-size:13px' href='/accounts/new'>+ New account</a></h1>{filt}{hint}"
            f"<table class='list'><tr>{th('id', 'ID')}{th('name', 'Account name')}{th('city', 'City')}{th('country', 'Country')}"
            f"{th('website', 'Website')}<th>Tax / VAT ID</th>{th('owner', 'Owner')}{th('created', 'Created')}</tr>{''.join(trs)}</table>"
            f"<div class='pager'>{''.join(pager)}</div>")
    r.page("Accounts", body, "accounts")


def get_account(r, aid):
    a = q1("SELECT * FROM accounts WHERE id=?", (to_int(aid),))
    if not a:
        r.error_page(404, "Account not found", f"There is no account {acc_id(aid)}.")
    return a


def live_account(r, aid):
    """The account, or None after rendering an error if it does not exist or was merged away (read-only)."""
    a = get_account(r, aid)
    if a and a["status"] == "merged":
        m = q1("SELECT id, name FROM accounts WHERE id=?", (a["merged_into"],))
        r.error_page(409, "Account was merged", f"{acc_id(a['id'])} {a['name']} was merged into "
                     f"{acc_id(m['id']) if m else '?'} {m['name'] if m else ''} and is read-only. Your changes were NOT saved - "
                     f"make them on the surviving account.", (f"/accounts/{m['id'] if m else a['id']}", "Open the surviving account"))
        return None
    return a


def account_view(r, aid):
    a = get_account(r, aid)
    if not a:
        return
    tomb = ""
    if a["status"] == "merged":
        m = q1("SELECT id, name FROM accounts WHERE id=?", (a["merged_into"],))
        tomb = (f"<div class='tomb'><b>This account was merged into <a href='/accounts/{m['id']}'>{acc_id(m['id'])} {esc(m['name'])}</a>"
                f"</b> on {fmt_date(a['merged_at'])}. It is read-only; its contacts, opportunities and activities now live on the surviving account.</div>")
    live = a["status"] == "active"
    rows = [(lab, esc(user_name(a[k])) if k == "owner_id" else esc(a[k])) for k, lab in FIELDS] + [("Created", esc(a["created"]))]
    half = (len(rows) + 1) // 2
    kv = "".join("<table class='kv'>" + "".join(f"<tr><td class='k'>{k}</td><td>{v or '<span class=muted>—</span>'}</td></tr>" for k, v in part) + "</table>"
                 for part in (rows[:half], rows[half:]))
    btns = (f"<p><a class='btn' href='/accounts/{a['id']}/edit'>Edit account</a> <a class='btn warn' href='/accounts/{a['id']}/merge'>Merge duplicates…</a></p>" if live else "")
    cs = q("SELECT * FROM contacts WHERE account_id=? ORDER BY last, first", (a["id"],))
    ctr = "".join(f"<tr><td><a href='/contacts/{c['id']}'>{esc(c['first'])} {esc(c['last'])}</a></td><td>{esc(c['title'])}</td>"
                  f"<td>{esc(c['email'])}</td><td>{esc(c['phone'])}</td></tr>" for c in cs) or "<tr><td colspan=4 class=muted>No contacts.</td></tr>"
    cform = (f"<details><summary>+ Add contact</summary><form class='form card' method='post' action='/accounts/{a['id']}/contacts'><div class='grid2'>"
             f"<div><label>First name</label><input type='text' name='first'></div><div><label>Last name</label><input type='text' name='last'></div>"
             f"<div><label>Title</label><input type='text' name='title'></div><div><label>Email</label><input type='text' name='email'></div>"
             f"<div><label>Phone</label><input type='text' name='phone'></div></div><p><button type='submit'>Add contact</button></p></form></details>") if live else ""
    os_ = q("SELECT * FROM opps WHERE account_id=? ORDER BY close_date DESC", (a["id"],))
    otr = "".join(f"<tr><td>{opp_id(o['id'])}</td><td><a href='/opps/{o['id']}'>{esc(o['name'])}</a></td><td>{money(o['amount'])}</td>"
                  f"<td><span class='badge st-{esc(o['stage']).replace(' ', '')}'>{esc(o['stage'])}</span></td><td>{esc(o['close_date'])}</td></tr>"
                  for o in os_) or "<tr><td colspan=5 class=muted>No opportunities.</td></tr>"
    oform = (f"<details><summary>+ New opportunity</summary><form class='form card' method='post' action='/accounts/{a['id']}/opps'><div class='grid2'>"
             f"<div><label>Opportunity name</label><input type='text' name='name'></div><div><label>Amount (USD)</label><input type='text' name='amount'></div>"
             f"<div><label>Stage</label><select name='stage'>{options(STAGES, 'Qualification')}</select></div>"
             f"<div><label>Close date (YYYY-MM-DD)</label><input type='text' name='close_date'></div></div>"
             f"<p><button type='submit'>Create opportunity</button></p></form></details>") if live else ""
    acts = q("SELECT ac.*, c.first, c.last, u.name AS uname FROM activities ac LEFT JOIN contacts c ON c.id=ac.contact_id "
             "LEFT JOIN users u ON u.id=ac.user_id WHERE ac.account_id=? ORDER BY ac.date DESC, ac.id DESC", (a["id"],))
    atl = "".join(f"<div class='act'><b>{esc(x['type'])}</b> &middot; {esc(x['date'])}"
                  f"{' &middot; with ' + esc((x['first'] or '') + ' ' + (x['last'] or '')) if x['contact_id'] else ''}"
                  f" &middot; <span class='muted'>logged by {esc(x['uname'])}</span><br><b>{esc(x['subject'])}</b><br>{esc(x['notes'])}</div>"
                  for x in acts) or "<p class='muted'>No activities yet.</p>"
    aform = (f"<details><summary>+ Log activity</summary><form class='form card' method='post' action='/accounts/{a['id']}/activities'><div class='grid2'>"
             f"<div><label>Type</label><select name='type'>{options(ACT_TYPES, 'Call')}</select></div>"
             f"<div><label>Date (YYYY-MM-DD)</label><input type='text' name='date'></div>"
             f"<div><label>Contact</label><select name='contact_id'>{options([(c['id'], c['first'] + ' ' + c['last']) for c in cs], '', '— none —')}</select></div>"
             f"<div><label>Subject</label><input type='text' name='subject'></div></div><label>Notes</label><textarea name='notes' rows='4'></textarea>"
             f"<p><button type='submit'>Save activity</button></p></form></details>") if live else ""
    body = (f"<p class='muted'><a href='/accounts'>&laquo; Accounts</a></p><h1>{esc(a['name'])} <span class='muted'>{acc_id(a['id'])}</span></h1>"
            f"{tomb}<div class='card'><div class='grid2'>{kv}</div>{btns}</div>"
            f"<h2>Contacts ({len(cs)})</h2><table class='list'><tr><th>Name</th><th>Title</th><th>Email</th><th>Phone</th></tr>{ctr}</table>{cform}"
            f"<h2>Opportunities ({len(os_)})</h2><table class='list'><tr><th>ID</th><th>Name</th><th>Amount</th><th>Stage</th><th>Close date</th></tr>{otr}</table>{oform}"
            f"<h2>Activities ({len(acts)})</h2>{aform}{atl}")
    r.page(a["name"], body, "accounts")


def account_form(r, a, action, title):
    us = [(u["id"], u["name"] + ("" if u["active"] else " (inactive)")) for u in users()]
    fields = []
    for k, lab in FIELDS:
        v = a[k] if a else ""
        if k == "industry":
            inp = f"<select name='industry'>{options(INDUSTRIES, v, '—')}</select>"
        elif k == "country":
            inp = f"<select name='country'>{options(COUNTRIES, v, '—')}</select>"
        elif k == "owner_id":
            inp = f"<select name='owner_id'>{options(us, v if a else r.user['id'])}</select>"
        else:
            inp = f"<input type='text' name='{k}' value='{esc(v)}'>"
        fields.append(f"<div><label>{lab}</label>{inp}</div>")
    back = f"/accounts/{a['id']}" if a else "/accounts"
    body = (f"<p class='muted'><a href='{back}'>&laquo; Back</a></p><h1>{esc(title)}</h1><form class='form card' method='post' action='{action}'>"
            f"<div class='grid2'>{''.join(fields)}</div><p><button type='submit'>Save</button> <a href='{back}'>Cancel</a></p></form>")
    r.page(title, body, "accounts")


def read_account_form(r):
    vals = {}
    for k, _ in FIELDS:
        v = r.form.get(k, "")
        if k == "industry":
            v = v if v in INDUSTRIES else ""
        elif k == "country":
            v = v if v in COUNTRIES else ""
        elif k == "owner_id":
            v = to_int(v) if to_int(v) and q1("SELECT id FROM users WHERE id=?", (to_int(v),)) else None
        else:
            v = v[:300]
        vals[k] = v
    return vals


def record(entity, eid, uid, rid, field, old, new):
    if str(old if old is not None else "") != str(new if new is not None else ""):
        DB.execute("INSERT INTO history (entity,entity_id,user_id,rid,field,old,new,ts) VALUES (?,?,?,?,?,?,?,?)",
                   (entity, eid, uid, rid, field, old, new, now()))
        return True
    return False


def account_edit(r, aid):
    a = live_account(r, aid)
    if not a:
        return
    if r.method == "GET":
        return account_form(r, a, f"/accounts/{a['id']}/edit", f"Edit {a['name']}")
    vals = read_account_form(r)
    if not vals["name"]:
        r.flash("Account name is required.", True)
        return r.redirect(f"/accounts/{a['id']}/edit")
    rid = secrets.token_hex(4)
    for k, v in vals.items():  # the form saves every field
        record("account", a["id"], r.user["id"], rid, k, a[k], v)
        DB.execute(f"UPDATE accounts SET {k}=? WHERE id=?", (v, a["id"]))
    DB.execute("UPDATE accounts SET updated=? WHERE id=?", (now(), a["id"]))
    r.flash("Account saved.")
    r.redirect(f"/accounts/{a['id']}")


def account_new(r):
    if r.method == "GET":
        return account_form(r, None, "/accounts/new", "New account")
    vals = read_account_form(r)
    if not vals["name"]:
        r.flash("Account name is required.", True)
        return r.redirect("/accounts/new")
    cur = DB.execute("INSERT INTO accounts (name,website,tax_id,erp_no,phone,industry,street,city,postcode,country,owner_id,created,updated) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(vals[k] for k, _ in FIELDS) + (now()[:10], now()))
    r.flash(f"Account {acc_id(cur.lastrowid)} created.")
    r.redirect(f"/accounts/{cur.lastrowid}")


# ------------------------------------------------------------------------------------------------ children
CONTACT_FIELDS = (("first", "First name"), ("last", "Last name"), ("title", "Title"), ("email", "Email"), ("phone", "Phone"))


def contact_fields(r):
    return {k: r.form.get(k, "")[:200] for k, _ in CONTACT_FIELDS}


def contact_add(r, aid):
    a = live_account(r, aid)
    if not a:
        return
    f = contact_fields(r)
    if not f["first"] or not f["last"]:
        r.flash("First and last name are required for a contact.", True)
        return r.redirect(f"/accounts/{a['id']}")
    DB.execute("INSERT INTO contacts (account_id,first,last,title,email,phone,created,updated) VALUES (?,?,?,?,?,?,?,?)",
               (a["id"], f["first"], f["last"], f["title"], f["email"], f["phone"], now(), now()))
    r.flash(f"Contact {f['first']} {f['last']} added.")
    r.redirect(f"/accounts/{a['id']}")


def contact_edit(r, cid):
    c = q1("SELECT c.*, a.name AS acc FROM contacts c LEFT JOIN accounts a ON a.id=c.account_id WHERE c.id=?", (to_int(cid),))
    if not c:
        return r.error_page(404, "Contact not found", "This contact does not exist.")
    if r.method == "GET":
        inp = "".join(f"<div><label>{lab}</label><input type='text' name='{k}' value='{esc(c[k])}'></div>" for k, lab in CONTACT_FIELDS)
        body = (f"<p class='muted'><a href='/accounts/{c['account_id']}'>&laquo; {esc(c['acc'])}</a></p><h1>{esc(c['first'])} {esc(c['last'])}</h1>"
                f"<form class='form card' method='post' action='/contacts/{c['id']}'><p class='muted'>Account: {acc_id(c['account_id'])} {esc(c['acc'])}</p>"
                f"<div class='grid2'>{inp}</div><p><button type='submit'>Save contact</button></p></form>")
        return r.page(f"{c['first']} {c['last']}", body, "accounts")
    f = contact_fields(r)
    if not f["first"] or not f["last"]:
        r.flash("First and last name are required.", True)
        return r.redirect(f"/contacts/{c['id']}")
    rid = secrets.token_hex(4)
    for k, v in f.items():  # the form saves every field
        record("contact", c["id"], r.user["id"], rid, k, c[k], v)
    DB.execute("UPDATE contacts SET first=?,last=?,title=?,email=?,phone=?,updated=? WHERE id=?",
               (f["first"], f["last"], f["title"], f["email"], f["phone"], now(), c["id"]))
    r.flash("Contact saved.")
    r.redirect(f"/accounts/{c['account_id']}")


def opp_fields(r):
    stage = r.form.get("stage") if r.form.get("stage") in STAGES else None
    f = {"name": r.form.get("name", "")[:200], "amount": parse_amount(r.form.get("amount")), "stage": stage,
         "close_date": parse_date(r.form.get("close_date"))}
    return f if f["name"] and f["amount"] is not None and f["stage"] and f["close_date"] else None


OPP_ERR = "name, a numeric amount, a stage and a close date (YYYY-MM-DD) are required."


def opp_create(r, aid):
    a = live_account(r, aid)
    if not a:
        return
    f = opp_fields(r)
    if not f:
        r.flash("Opportunity not created: " + OPP_ERR, True)
        return r.redirect(f"/accounts/{a['id']}")
    cur = DB.execute("INSERT INTO opps (account_id,name,amount,stage,close_date,owner_id,created,updated) VALUES (?,?,?,?,?,?,?,?)",
                     (a["id"], f["name"], f["amount"], f["stage"], f["close_date"], a["owner_id"], now(), now()))
    r.flash(f"Opportunity {opp_id(cur.lastrowid)} created.")
    r.redirect(f"/accounts/{a['id']}")


def opp_edit(r, oid):
    o = q1("SELECT o.*, a.name AS acc FROM opps o LEFT JOIN accounts a ON a.id=o.account_id WHERE o.id=?", (to_int(oid),))
    if not o:
        return r.error_page(404, "Opportunity not found", "This opportunity does not exist.")
    if r.method == "GET":
        body = (f"<p class='muted'><a href='/accounts/{o['account_id']}'>&laquo; {esc(o['acc'])}</a></p><h1>{opp_id(o['id'])} {esc(o['name'])}</h1>"
                f"<form class='form card' method='post' action='/opps/{o['id']}'><div class='grid2'>"
                f"<div><label>Opportunity name</label><input type='text' name='name' value='{esc(o['name'])}'></div>"
                f"<div><label>Amount (USD)</label><input type='text' name='amount' value='{o['amount']:.2f}'></div>"
                f"<div><label>Stage</label><select name='stage'>{options(STAGES, o['stage'])}</select></div>"
                f"<div><label>Close date (YYYY-MM-DD)</label><input type='text' name='close_date' value='{esc(o['close_date'])}'></div>"
                f"<div><label>Owner</label><select name='owner_id'>{options([(u['id'], u['name']) for u in users()], o['owner_id'])}</select></div></div>"
                f"<p class='muted'>Account: {acc_id(o['account_id'])} {esc(o['acc'])}</p><p><button type='submit'>Save</button></p></form>")
        return r.page(o["name"], body, "opps")
    f = opp_fields(r)
    if not f:
        r.flash("Not saved: " + OPP_ERR, True)
        return r.redirect(f"/opps/{o['id']}")
    f["owner_id"] = to_int(r.form.get("owner_id")) if q1("SELECT id FROM users WHERE id=?", (to_int(r.form.get("owner_id"), -1),)) else o["owner_id"]
    rid = secrets.token_hex(4)
    for k, v in f.items():
        record("opp", o["id"], r.user["id"], rid, k, o[k], v)
        DB.execute(f"UPDATE opps SET {k}=? WHERE id=?", (v, o["id"]))
    DB.execute("UPDATE opps SET updated=? WHERE id=?", (now(), o["id"]))
    r.flash(f"{opp_id(o['id'])} saved.")
    r.redirect(f"/opps/{o['id']}")


def opps_list(r):
    stage, text = r.qs.get("stage", ""), r.qs.get("q", "").strip()
    page = max(1, to_int(r.qs.get("page"), 1))
    where, args = [], []
    if stage in STAGES:
        where.append("o.stage=?")
        args.append(stage)
    if text:
        where.append("(o.name LIKE ? OR a.name LIKE ? OR 'OPP-'||o.id = ?)")
        args += [f"%{text}%", f"%{text}%", text.upper()]
    w = (" WHERE " + " AND ".join(where)) if where else ""
    base = "FROM opps o LEFT JOIN accounts a ON a.id=o.account_id LEFT JOIN users u ON u.id=o.owner_id"
    total = q1(f"SELECT COUNT(*) {base}{w}", args)[0]
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, pages)
    rows = q(f"SELECT o.*, a.name AS acc, u.name AS owner {base}{w} ORDER BY o.id DESC LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}", args)
    trs = "".join(f"<tr><td>{opp_id(o['id'])}</td><td><a href='/opps/{o['id']}'>{esc(o['name'])}</a></td>"
                  f"<td><a href='/accounts/{o['account_id']}'>{esc(o['acc'])}</a></td><td>{money(o['amount'])}</td>"
                  f"<td><span class='badge st-{esc(o['stage']).replace(' ', '')}'>{esc(o['stage'])}</span></td><td>{esc(o['close_date'])}</td><td>{esc(o['owner'])}</td></tr>"
                  for o in rows) or "<tr><td colspan=7 class=muted>No opportunities.</td></tr>"
    pl = "".join(f"<b>{p}</b>" if p == page else f"<a href='/opps?{esc(urllib.parse.urlencode({'stage': stage, 'q': text, 'page': p}))}'>{p}</a>"
                 for p in range(1, pages + 1))
    body = (f"<h1>Opportunities</h1><form class='filters' method='get'><input type='text' name='q' value='{esc(text)}' placeholder='Name, account or OPP-id'>"
            f"<select name='stage'>{options(STAGES, stage, 'Any stage')}</select><button>Search</button></form>"
            f"<table class='list'><tr><th>ID</th><th>Name</th><th>Account</th><th>Amount</th><th>Stage</th><th>Close</th><th>Owner</th></tr>{trs}</table>"
            f"<div class='pager'><span class='muted'>{total} opportunities</span>{pl}</div>")
    r.page("Opportunities", body, "opps")


def activity_log(r, aid):
    a = live_account(r, aid)
    if not a:
        return
    typ = r.form.get("type") if r.form.get("type") in ACT_TYPES else None
    date = parse_date(r.form.get("date"))
    cid = to_int(r.form.get("contact_id"))
    if cid and not q1("SELECT id FROM contacts WHERE id=? AND account_id=?", (cid, a["id"])):
        cid = None
    if not typ or not date:
        r.flash("Activity not saved: choose a type and enter the date as YYYY-MM-DD.", True)
        return r.redirect(f"/accounts/{a['id']}")
    DB.execute("INSERT INTO activities (account_id,contact_id,type,date,subject,notes,user_id,created) VALUES (?,?,?,?,?,?,?,?)",
               (a["id"], cid, typ, date, r.form.get("subject", "")[:300], r.form.get("notes", "")[:5000], r.user["id"], now()))
    r.flash(f"{typ} on {date} logged.")
    r.redirect(f"/accounts/{a['id']}")


# ------------------------------------------------------------------------------------------------ merge
def merge_search(r, aid):
    a = live_account(r, aid)
    if not a:
        return
    text = r.qs.get("q", "").strip()
    rows = []
    if text:
        rows = q("SELECT * FROM accounts WHERE status='active' AND id<>? AND (name LIKE ? OR website LIKE ? OR tax_id LIKE ? OR city LIKE ? "
                 "OR 'ACC-'||id = ?) ORDER BY name COLLATE NOCASE LIMIT 30", (a["id"], f"%{text}%", f"%{text}%", f"%{text}%", f"%{text}%", text.upper()))
    trs = "".join(f"<tr><td>{acc_id(b['id'])}</td><td>{esc(b['name'])}</td><td>{esc(b['city'])}, {esc(b['country'])}</td><td>{esc(b['website'])}</td>"
                  f"<td>{esc(b['tax_id'])}</td><td><a class='btn sec' href='/accounts/{a['id']}/merge/{b['id']}'>Compare</a></td></tr>" for b in rows)
    res = (f"<table class='list'><tr><th>ID</th><th>Name</th><th>City</th><th>Website</th><th>Tax / VAT ID</th><th></th></tr>{trs}</table>"
           if rows else (f"<p class='muted'>No active accounts match “{esc(text)}”.</p>" if text else ""))
    body = (f"<p class='muted'><a href='/accounts/{a['id']}'>&laquo; {esc(a['name'])}</a></p><h1>Merge duplicates of {esc(a['name'])} "
            f"<span class='muted'>{acc_id(a['id'])}</span></h1><div class='card'>Search for the other record of the same customer. "
            f"You will choose the surviving record and the field values on the next screen.</div>"
            f"<form class='filters' method='get'><input type='text' name='q' value='{esc(text)}' size='40' placeholder='Name, website, tax ID, city or ACC-id'>"
            f"<button>Find</button></form>{res}")
    r.page("Merge", body, "accounts")


def merge_compare(r, aid, bid):
    a, b = live_account(r, aid), None
    if not a:
        return
    b = live_account(r, bid)
    if not b:
        return
    if a["id"] == b["id"]:
        return r.error_page(400, "Cannot merge", "An account cannot be merged with itself.", (f"/accounts/{a['id']}/merge", "Back"))

    def show(x, k):
        return esc(user_name(x[k])) if k == "owner_id" else (esc(x[k]) if x[k] else "<span class='muted'>(empty)</span>")
    rows = "".join(f"<tr><th>{lab}</th><td><label><input type='radio' name='f_{k}' value='a' checked> {show(a, k)}</label></td>"
                   f"<td><label><input type='radio' name='f_{k}' value='b'> {show(b, k)}</label></td></tr>" for k, lab in FIELDS)

    def kids(x):
        return "%d contacts, %d opportunities, %d activities" % tuple(
            q1(f"SELECT COUNT(*) FROM {t} WHERE account_id=?", (x["id"],))[0] for t in ("contacts", "opps", "activities"))
    body = (f"<p class='muted'><a href='/accounts/{a['id']}/merge'>&laquo; Back to search</a></p><h1>Merge {acc_id(a['id'])} and {acc_id(b['id'])}</h1>"
            f"<form method='post' action='/accounts/{a['id']}/merge/{b['id']}'><table class='cmp'>"
            f"<tr><th></th><th>{acc_id(a['id'])} <a href='/accounts/{a['id']}'>{esc(a['name'])}</a></th><th>{acc_id(b['id'])} <a href='/accounts/{b['id']}'>{esc(b['name'])}</a></th></tr>"
            f"<tr><th>Master record (survives)</th><td><label><input type='radio' name='master' value='a' checked> keep {acc_id(a['id'])}</label></td>"
            f"<td><label><input type='radio' name='master' value='b'> keep {acc_id(b['id'])}</label></td></tr>"
            f"<tr><th>Created</th><td>{esc(a['created'])}</td><td>{esc(b['created'])}</td></tr>"
            f"<tr><th>Related records</th><td>{kids(a)}</td><td>{kids(b)}</td></tr>"
            f"<tr><td colspan=3 class='muted'>For every field choose the value the surviving record should have:</td></tr>{rows}</table>"
            f"<div class='card'><label><input type='checkbox' name='confirm' value='1'> I understand that the other record will be retired "
            f"(read-only) and its contacts, opportunities and activities move to the master.</label>"
            f"<p><button type='submit' class='btn warn'>Merge accounts</button></p></div></form>")
    r.page("Merge accounts", body, "accounts")


def merge_post(r, aid, bid):
    a = live_account(r, aid)
    if not a:
        return
    b = live_account(r, bid)
    if not b:
        return
    if a["id"] == b["id"]:
        return r.error_page(400, "Cannot merge", "An account cannot be merged with itself.")
    if r.form.get("confirm") != "1":
        r.flash("Tick the confirmation box to merge.", True)
        return r.redirect(f"/accounts/{a['id']}/merge/{b['id']}")
    master, other = (a, b) if r.form.get("master", "a") != "b" else (b, a)
    choices = {k: ("b" if r.form.get(f"f_{k}") == "b" else "a") for k, _ in FIELDS}
    rid = secrets.token_hex(4)
    for k, side in choices.items():
        v = (b if side == "b" else a)[k]
        record("account", master["id"], r.user["id"], rid, k, master[k], v)
        DB.execute(f"UPDATE accounts SET {k}=? WHERE id=?", (v, master["id"]))
    for t in ("contacts", "opps", "activities"):
        DB.execute(f"UPDATE {t} SET account_id=? WHERE account_id=?", (master["id"], other["id"]))
    DB.execute("UPDATE accounts SET status='merged', merged_into=?, merged_at=?, updated=? WHERE id=?",
               (master["id"], now(), now(), other["id"]))
    DB.execute("UPDATE accounts SET updated=? WHERE id=?", (now(), master["id"]))
    DB.execute("INSERT INTO merges (master_id,merged_id,user_id,choices,ts) VALUES (?,?,?,?,?)",
               (master["id"], other["id"], r.user["id"], json.dumps(choices), now()))
    r.flash(f"{acc_id(other['id'])} {other['name']} was merged into {acc_id(master['id'])} {master['name']}.")
    r.redirect(f"/accounts/{master['id']}")


def merges_list(r):
    rows = q("SELECT m.*, a.name AS mname, b.name AS oname, u.name AS uname FROM merges m LEFT JOIN accounts a ON a.id=m.master_id "
             "LEFT JOIN accounts b ON b.id=m.merged_id LEFT JOIN users u ON u.id=m.user_id ORDER BY m.id DESC")
    trs = "".join(f"<tr><td>{esc(m['ts'])}</td><td><a href='/accounts/{m['master_id']}'>{acc_id(m['master_id'])} {esc(m['mname'])}</a></td>"
                  f"<td><a href='/accounts/{m['merged_id']}'>{acc_id(m['merged_id'])} {esc(m['oname'])}</a></td><td>{esc(m['uname'])}</td></tr>"
                  for m in rows) or "<tr><td colspan=4 class=muted>No merges yet.</td></tr>"
    r.page("Merge history", f"<h1>Merge history</h1><table class='list'><tr><th>When</th><th>Surviving account</th><th>Merged (retired) account</th>"
                            f"<th>By</th></tr>{trs}</table>", "merges")


def users_list(r):
    def status(u):
        return "Active" if u["active"] else "<span class='badge inactive'>Inactive</span> left " + esc(u["left_on"])
    trs = "".join(f"<tr><td>{esc(u['name'])}</td><td>{esc(u['title'])}</td><td>{esc(u['region'])}</td><td>{esc(u['email'])}</td>"
                  f"<td>{status(u)}</td></tr>" for u in users())
    r.page("Users", f"<h1>Users</h1><table class='list'><tr><th>Name</th><th>Role</th><th>Region</th><th>Email</th><th>Status</th></tr>{trs}</table>", "users")


def guide(r):
    g = q1("SELECT * FROM pages WHERE slug='data-quality'")
    if not g:
        return r.error_page(404, "Page not found", "The data quality guide has not been published yet.")
    r.page(g["title"], f"<h1>{esc(g['title'])}</h1><p class='muted'>Last updated {esc(g['updated'])}</p>"
                       f"<div class='card kb'>{render_text(g['body'])}</div>", "guide")


ROUTES = [
    ("GET", r"/login", login_get, True), ("POST", r"/login", login_post, True), ("GET", r"/logout", logout, True),
    ("GET", r"/", home, False), ("GET", r"/accounts", accounts_list, False),
    ("GET", r"/accounts/new", account_new, False), ("POST", r"/accounts/new", account_new, False),
    ("GET", r"/accounts/(\d+)", account_view, False),
    ("GET", r"/accounts/(\d+)/edit", account_edit, False), ("POST", r"/accounts/(\d+)/edit", account_edit, False),
    ("POST", r"/accounts/(\d+)/contacts", contact_add, False), ("POST", r"/accounts/(\d+)/opps", opp_create, False),
    ("POST", r"/accounts/(\d+)/activities", activity_log, False),
    ("GET", r"/accounts/(\d+)/merge", merge_search, False), ("GET", r"/accounts/(\d+)/merge/(\d+)", merge_compare, False),
    ("POST", r"/accounts/(\d+)/merge/(\d+)", merge_post, False),
    ("GET", r"/contacts/(\d+)", contact_edit, False), ("POST", r"/contacts/(\d+)", contact_edit, False),
    ("GET", r"/opps", opps_list, False), ("GET", r"/opps/(\d+)", opp_edit, False), ("POST", r"/opps/(\d+)", opp_edit, False),
    ("GET", r"/merges", merges_list, False), ("GET", r"/users", users_list, False), ("GET", r"/guide", guide, False),
]


def make_server(db_path, host="127.0.0.1", port=8103):
    global DB
    DB = sqlite3.connect(db_path, check_same_thread=False)
    init_schema(DB)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8103)
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
