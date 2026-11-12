#!/usr/bin/env python3
"""Synthetic local dispatch board for ROUTE-LIVE1."""
import argparse,datetime as dt,html,sqlite3,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=None
CSS="""<style>body{font:16px Arial;margin:0;background:#f5f7f9;color:#1c2933}header{background:#24544b;color:white;padding:16px 24px}main{max-width:1100px;margin:24px auto;background:white;padding:24px}nav a{color:white;margin-right:18px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd4d2;padding:8px;text-align:left}th{background:#e5efec}label{display:block;margin:12px 0}input,select,textarea{font:inherit;padding:7px}button{padding:9px 16px;background:#287568;color:white;border:0}</style>"""
SCHEMA="""CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,customer TEXT,address TEXT,service_date TEXT,window TEXT,priority TEXT,status TEXT,note TEXT);
CREATE TABLE IF NOT EXISTS manifest(route_id TEXT,position INTEGER,job_id TEXT,PRIMARY KEY(route_id,position));
CREATE TABLE IF NOT EXISTS routes(route_id TEXT PRIMARY KEY,service_date TEXT,vehicle TEXT,depart_time TEXT,status TEXT,saved_at TEXT);
CREATE TABLE IF NOT EXISTS route_stops(route_id TEXT,position INTEGER,job_id TEXT,PRIMARY KEY(route_id,position));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT,target TEXT,details TEXT,ts TEXT);"""
def init_schema(con):con.executescript(SCHEMA);con.commit()
def q(sql,args=()):return DB.execute(sql,args).fetchall()
def q1(sql,args=()):return DB.execute(sql,args).fetchone()
def esc(x):return html.escape(str(x or ""),quote=True)
def now():return dt.datetime.now().isoformat(timespec="seconds")
def page(title,body):
 nav='<nav><a href="/">Dispatch board</a><a href="/manifest">08:00 manifest</a><a href="/route">Route draft</a><a href="/jobs">Work orders</a></nav>'
 return f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)} - Lakeside Field Dispatch</title>{CSS}</head><body><header><b>Lakeside Field Dispatch</b>{nav}</header><main><h1>{esc(title)}</h1>{body}</main></body></html>'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,body,status=200):
  b=body.encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def form(self):
  n=int(self.headers.get("Content-Length","0"));return urllib.parse.parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
 def val(self,d,k,default=""):return d.get(k,[default])[0]
 def do_GET(self):
  p=urllib.parse.urlparse(self.path).path
  if p=="/":
   rows=q("SELECT id,customer,address,service_date,window,priority,status FROM jobs ORDER BY id")
   body="<p>Morning wave: RTE-17 is based on the manifest released at 08:00. Review the dispatch status and customer updates.</p><table><tr><th>Work order</th><th>Customer</th><th>Address</th><th>Date</th><th>Window</th><th>Priority</th><th>Status</th></tr>"
   for r in rows:body+=f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{esc(r[3])}</td><td>{esc(r[4])}</td><td>{esc(r[5])}</td><td>{esc(r[6])}</td></tr>"
   return self.send(page("Dispatch board",body+"</table>"))
  if p=="/manifest":
   rows=q("SELECT m.position,m.job_id,j.customer,j.address,j.window FROM manifest m JOIN jobs j ON j.id=m.job_id WHERE m.route_id='RTE-17' ORDER BY m.position")
   body="<p>Frozen route sheet released at 08:00 for the Friday morning wave.</p><table><tr><th>Sequence</th><th>Work order</th><th>Customer</th><th>Address</th><th>Window at release</th></tr>"
   for r in rows:body+=f"<tr><td>{r[0]}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{esc(r[3])}</td><td>{esc(r[4])}</td></tr>"
   return self.send(page("08:00 released manifest",body+"</table>"))
  if p=="/route":
   jobs=q("SELECT m.position,m.job_id,j.customer,j.status FROM manifest m JOIN jobs j ON j.id=m.job_id WHERE m.route_id='RTE-17' ORDER BY m.position")
   body="<form method='post' action='/route/save'><p>Use the 08:00 released manifest but confirm current work-order status on the dispatch board. Include every order still Scheduled when you save, in manifest order; exclude Deferred or Cancelled orders.</p>"
   body+="<label>Route ID <input name='route_id' value='RTE-17'></label><label>Service date <input name='service_date' value='2026-11-13'></label>"
   body+="<label>Vehicle <select name='vehicle'><option value=''>Choose</option><option>Van 4</option><option>Van 2</option></select></label><label>Departure time <select name='depart_time'><option value=''>Choose</option><option>08:00</option><option>09:00</option></select></label>"
   for r in jobs:
    body+=f"<label>Stop {r[0]} <select name='stop_{r[0]}'><option value=''>Choose work order</option>"
    for j in jobs:body+=f"<option value='{esc(j[1])}'>{esc(j[1])} - {esc(j[2])} ({esc(j[3])})</option>"
    body+="</select></label>"
   body+="<label>Status <select name='status'><option>Draft</option><option>Dispatched</option></select></label><button>Save route draft</button></form>"
   return self.send(page("Route draft",body))
  if p=="/jobs":
   rows=q("SELECT id,customer,service_date,window,status,note FROM jobs ORDER BY id")
   body="<table><tr><th>Work order</th><th>Customer</th><th>Date</th><th>Window</th><th>Status</th><th>Note</th><th>Edit</th></tr>"
   for r in rows:body+=f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{esc(r[3])}</td><td>{esc(r[4])}</td><td>{esc(r[5])}</td><td><a href='/job?id={esc(r[0])}'>Edit</a></td></tr>"
   return self.send(page("Work orders",body+"</table>"))
  if p=="/job":
   jid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("id",[""])[0]
   r=q1("SELECT id,customer,service_date,window,status,note FROM jobs WHERE id=?",(jid,))
   if not r:return self.send(page("Not found","<p>Unknown work order</p>"),404)
   body=f"<form method='post' action='/job/save'><input type='hidden' name='job_id' value='{esc(r[0])}'><p>{esc(r[0])} - {esc(r[1])}</p><label>Status <select name='status'><option>Scheduled</option><option>Deferred</option><option>Cancelled</option></select></label><label>New service date <input name='service_date' value='2026-11-14'></label><label>Update note <textarea name='note' rows='3' cols='70'></textarea></label><button>Save work-order update</button></form>"
   return self.send(page("Update customer work order",body))
  return self.send(page("Not found","<p>Unknown page</p>"),404)
 def do_POST(self):
  p=urllib.parse.urlparse(self.path).path;d=self.form();stamp=now()
  if p=="/route/save":
   rid=self.val(d,"route_id");seq=[self.val(d,f"stop_{i}") for i in range(1,5)]
   seq=[x for x in seq if x]
   DB.execute("INSERT OR REPLACE INTO routes VALUES(?,?,?,?,?,?)",(rid,self.val(d,"service_date"),self.val(d,"vehicle"),self.val(d,"depart_time"),self.val(d,"status"),stamp))
   DB.execute("DELETE FROM route_stops WHERE route_id=?",(rid,))
   DB.executemany("INSERT INTO route_stops VALUES(?,?,?)",[(rid,i+1,j) for i,j in enumerate(seq)])
   DB.execute("INSERT INTO events(action,target,details,ts) VALUES('route_saved',?,?,?)",(rid,",".join(seq),stamp));DB.commit()
   return self.send(page("Route saved",f"<p>Route {esc(rid)} saved as {esc(self.val(d,'status'))}.</p>"))
  if p=="/job/save":
   jid=self.val(d,"job_id");DB.execute("UPDATE jobs SET status=?,service_date=?,note=? WHERE id=?",(self.val(d,"status"),self.val(d,"service_date"),self.val(d,"note"),jid))
   DB.execute("INSERT INTO events(action,target,details,ts) VALUES('job_updated',?,?,?)",(jid,self.val(d,"status"),stamp));DB.commit()
   return self.send(page("Work order updated",f"<p>{esc(jid)} updated.</p>"))
  return self.send(page("Not found","<p>Unknown operation</p>"),404)
def main():
 global DB
 ap=argparse.ArgumentParser();ap.add_argument("--db",required=True);ap.add_argument("--port",type=int,required=True);a=ap.parse_args()
 DB=sqlite3.connect(a.db,check_same_thread=False);DB.executescript(SCHEMA);DB.commit()
 ThreadingHTTPServer(("127.0.0.1",a.port),Handler).serve_forever()
if __name__=="__main__":main()
