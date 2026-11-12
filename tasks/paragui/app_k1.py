#!/usr/bin/env python3
"""Synthetic single-session legacy docket board for COURT-SERVICE1."""
import argparse,datetime as dt,html,sqlite3,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=None
CSS="""<style>body{font:16px Arial;margin:0;background:#f3f5f8;color:#17202a}header{background:#253d63;color:white;padding:16px 24px}main{max-width:1080px;margin:24px auto;background:white;padding:24px}nav a{color:white;margin-right:18px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd3db;padding:9px;text-align:left}th{background:#e8edf4}label{display:block;margin:12px 0}input,select{font:inherit;padding:7px}button{padding:9px 16px;background:#285b8e;color:white;border:0}</style>"""
SCHEMA="""CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,plaintiff TEXT,defendant TEXT,amount REAL,due_date TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS desk_state(id INTEGER PRIMARY KEY CHECK(id=1),active_case TEXT);
CREATE TABLE IF NOT EXISTS filings(case_id TEXT PRIMARY KEY,plaintiff TEXT,defendant TEXT,amount REAL,attachment TEXT,status TEXT,saved_at TEXT);
CREATE TABLE IF NOT EXISTS services(case_id TEXT PRIMARY KEY,service_date TEXT,method TEXT,server_id TEXT,outcome TEXT,saved_at TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT,case_id TEXT,details TEXT,ts TEXT);"""
def init_schema(con):con.executescript(SCHEMA);con.commit()
def q(sql,args=()):return DB.execute(sql,args).fetchall()
def q1(sql,args=()):return DB.execute(sql,args).fetchone()
def esc(x):return html.escape(str(x or ""),quote=True)
def now():return dt.datetime.now().isoformat(timespec="seconds")
def page(title,body):
 nav='<nav><a href="/">Docket index</a><a href="/filing">Filing packet</a><a href="/service">Proof of service</a></nav>'
 return f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)} - North County Clerk Desk</title>{CSS}</head><body><header><b>North County Clerk Desk</b>{nav}</header><main><h1>{esc(title)}</h1>{body}</main></body></html>'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,body,status=200):
  b=body.encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def form(self):
  n=int(self.headers.get("Content-Length","0"));return urllib.parse.parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
 def val(self,d,k,default=""):return d.get(k,[default])[0]
 def active(self):return q1("SELECT active_case FROM desk_state WHERE id=1")[0]
 def do_GET(self):
  parsed=urllib.parse.urlparse(self.path);params=urllib.parse.parse_qs(parsed.query)
  if parsed.path=="/":
   pick=(params.get("pick") or [None])[0]
   if pick in ("SC-193","SC-208"):
    DB.execute("UPDATE desk_state SET active_case=? WHERE id=1",(pick,))
    DB.execute("INSERT INTO events(action,case_id,details,ts) VALUES('select_case',?,?,?)",(pick,"selected docket",now()));DB.commit()
   active=self.active();rows=q("SELECT id,plaintiff,defendant,amount,due_date,status FROM cases ORDER BY id")
   body="<p>This older clerk desktop has one shared active-docket selector. Verify the docket number shown in the header before saving.</p><table><tr><th>Docket</th><th>Plaintiff</th><th>Defendant</th><th>Claim</th><th>Deadline</th><th>Status</th><th>Select</th></tr>"
   for r in rows:body+=f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{r[3]:.2f}</td><td>{esc(r[4])}</td><td>{esc(r[5])}</td><td><a href='/?pick={esc(r[0])}'>Make active</a></td></tr>"
   body+="</table><h2>Active docket: "+esc(active)+"</h2><p><a href='/filing'>Open filing packet</a> | <a href='/service'>Open proof of service</a></p>"
   return self.send(page("Civil docket index",body))
  if parsed.path in ("/filing","/service"):
   cid=self.active();row=q1("SELECT plaintiff,defendant,amount,status FROM cases WHERE id=?",(cid,))
   context=f'<div style="padding:10px;background:#eef3f8"><b>Currently active docket: {esc(cid)}</b> - {esc(row[0])} v. {esc(row[1])}; claim {row[2]:.2f}; {esc(row[3])}</div>'
   if parsed.path=="/filing":
    body=context+'<form method="post" action="/filing/save"><p>Prepare the filing cover packet for the active docket.</p><label>Plaintiff <input name="plaintiff" size="48"></label><label>Defendant <input name="defendant" size="48"></label><label>Claim amount <input name="amount"></label><label>Attachment name <input name="attachment" size="44"></label><label>Packet status <select name="status"><option>Draft</option><option>Ready for clerk check</option></select></label><button>Save filing packet</button></form>'
    return self.send(page("Filing packet",body))
   body=context+'<form method="post" action="/service/save"><p>Record the process-server return for the active docket.</p><label>Service date <input name="service_date"></label><label>Method <select name="method"><option value="">Choose</option><option>Personal service</option><option>Substitute service</option></select></label><label>Server ID <input name="server_id"></label><label>Outcome <select name="outcome"><option value="">Choose</option><option>Served</option><option>Not served</option></select></label><button>Save proof of service</button></form>'
   return self.send(page("Proof of service",body))
  return self.send(page("Not found","<p>Unknown page.</p>"),404)
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path;d=self.form();cid=self.active();stamp=now()
  if path=="/filing/save":
   DB.execute("INSERT OR REPLACE INTO filings VALUES(?,?,?,?,?,?,?)",(cid,self.val(d,"plaintiff"),self.val(d,"defendant"),self.val(d,"amount"),self.val(d,"attachment"),self.val(d,"status"),stamp))
   DB.execute("INSERT INTO events(action,case_id,details,ts) VALUES('filing_saved',?,?,?)",(cid,self.val(d,"attachment"),stamp));DB.commit()
   return self.send(page("Filing packet saved",f"<p>Saved to active docket {esc(cid)}.</p><a href='/'>Return to docket index</a>"))
  if path=="/service/save":
   DB.execute("INSERT OR REPLACE INTO services VALUES(?,?,?,?,?,?)",(cid,self.val(d,"service_date"),self.val(d,"method"),self.val(d,"server_id"),self.val(d,"outcome"),stamp))
   DB.execute("INSERT INTO events(action,case_id,details,ts) VALUES('service_saved',?,?,?)",(cid,self.val(d,"server_id"),stamp));DB.commit()
   return self.send(page("Service proof saved",f"<p>Saved to active docket {esc(cid)}.</p><a href='/'>Return to docket index</a>"))
  return self.send(page("Not found","<p>Unknown operation.</p>"),404)
def main():
 global DB
 ap=argparse.ArgumentParser();ap.add_argument("--db",required=True);ap.add_argument("--port",type=int,required=True);a=ap.parse_args()
 DB=sqlite3.connect(a.db,check_same_thread=False);DB.executescript(SCHEMA);DB.commit()
 ThreadingHTTPServer(("127.0.0.1",a.port),Handler).serve_forever()
if __name__=="__main__":main()
