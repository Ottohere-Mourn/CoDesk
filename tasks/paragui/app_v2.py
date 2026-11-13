#!/usr/bin/env python3
"""Shared warehouse label station with one global media-stock profile."""
import argparse, html, sqlite3, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
DB=None
CSS="""<style>body{font:16px Arial;background:#eef2f4;color:#1c2932;margin:0}header{background:#203f55;color:white;padding:14px 26px}main{max-width:1160px;margin:18px auto;background:white;padding:20px}.profiles{display:flex;gap:20px;padding:12px;background:#e4edf2}.profiles form{margin:0}button{font:inherit;background:#155f72;color:white;border:0;padding:8px 12px;cursor:pointer}table{border-collapse:collapse;width:100%;margin-top:14px;font-size:15px}td,th{border:1px solid #b6c5cc;padding:7px;text-align:left}th{background:#dce9ed}input{font:inherit;width:60px;padding:5px}.muted{color:#66777d}.good{color:#176a42;font-weight:bold}.recent{margin-top:14px}</style>"""
def esc(x): return html.escape(str(x or ""),quote=True)
def one(q,a=()): return DB.execute(q,a).fetchone()
def all_(q,a=()): return DB.execute(q,a).fetchall()
def page(title,body): return f"<!doctype html><meta charset='utf-8'><title>{esc(title)}</title>{CSS}<body><header><b>Riverside Logistics | Shared Thermal Label Desk</b></header><main><h1>{esc(title)}</h1>{body}</main></body>"
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def send(self,body,status=200):
  b=body.encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def redirect(self): self.send_response(303);self.send_header("Location","/desk");self.end_headers()
 def do_GET(self):
  p=urllib.parse.urlparse(self.path)
  if p.path=="/health": return self.send("ok")
  if p.path not in ("/","/desk"): return self.send(page("Not found","<p>Not found</p>"),404)
  profile=one("SELECT profile FROM station WHERE id=1")[0]
  labels=all_("SELECT id,code,kind,description,required_copies FROM labels ORDER BY kind,id")
  trs=[]
  for r in labels:
   kind="Bin location" if r[2]=="bin" else "Parcel"
   trs.append(f"<tr><td>{esc(kind)}</td><td><b>{esc(r[1])}</b></td><td>{esc(r[3])}</td><td>{r[4]}</td><td><form method='post' action='/print'><input type='hidden' name='label_id' value='{r[0]}'><input name='copies' aria-label='copies {esc(r[1])}' type='number' min='1' max='20' required><button>Print</button></form></td></tr>")
  jobs=all_("SELECT l.code,l.kind,j.profile,j.copies FROM jobs j JOIN labels l ON l.id=j.label_id ORDER BY j.id DESC LIMIT 8")
  jtrs="".join(f"<tr><td>{esc(r[0])}</td><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td>{r[3]}</td></tr>" for r in jobs)
  body=f"<p>Prepare the assigned label batches. <span class='muted'>The selected stock is a shared station setting and is captured when each print job is submitted.</span></p><section class='profiles'><div><b>Current stock profile:</b> <span class='good'>{esc(profile)}</span></div><form method='post' action='/profile'><input type='hidden' name='profile' value='BIN_2X1'><button>Use Bin 2 x 1 stock</button></form><form method='post' action='/profile'><input type='hidden' name='profile' value='PARCEL_4X6'><button>Use Parcel 4 x 6 stock</button></form></section><h2>Work queue</h2><table><tr><th>Type</th><th>Label ID</th><th>Label content</th><th>Required copies</th><th>Enter copies and print</th></tr>{''.join(trs)}</table><section class='recent'><h2>Recent print jobs</h2><table><tr><th>Label ID</th><th>Type</th><th>Stock captured</th><th>Copies</th></tr>{jtrs}</table></section>"
  return self.send(page("Warehouse label work queue",body))
 def do_POST(self):
  p=urllib.parse.urlparse(self.path); size=int(self.headers.get("Content-Length","0")); d=urllib.parse.parse_qs(self.rfile.read(size).decode(),keep_blank_values=True)
  if p.path=="/profile":
   profile=d.get("profile",[""])[0]
   if profile not in ("BIN_2X1","PARCEL_4X6"): return self.send(page("Invalid profile","<p>Profile rejected</p>"),400)
   DB.execute("UPDATE station SET profile=? WHERE id=1",(profile,));DB.execute("INSERT INTO events(kind,value) VALUES('profile',?)",(profile,));DB.commit();return self.redirect()
  if p.path=="/print":
   try: label_id=int(d.get("label_id",["0"])[0]); copies=int(d.get("copies",["0"])[0])
   except ValueError: return self.send(page("Invalid print job","<p>Enter copies.</p>"),400)
   label=one("SELECT kind FROM labels WHERE id=?",(label_id,));profile=one("SELECT profile FROM station WHERE id=1")[0]
   if not label or copies<1 or copies>20: return self.send(page("Invalid print job","<p>Invalid label or copies.</p>"),400)
   DB.execute("INSERT INTO jobs(label_id,profile,copies) VALUES(?,?,?)",(label_id,profile,copies));DB.execute("INSERT INTO events(kind,value) VALUES('print',?)",(f"{label_id}|{profile}|{copies}",));DB.commit();return self.redirect()
  return self.send(page("Not found","<p>Unknown operation</p>"),404)
def main():
 global DB
 ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--port',type=int,required=True);a=ap.parse_args()
 DB=sqlite3.connect(a.db,check_same_thread=False);DB.row_factory=sqlite3.Row
 DB.executescript("CREATE TABLE IF NOT EXISTS labels(id INTEGER PRIMARY KEY,code TEXT,kind TEXT,description TEXT,required_copies INTEGER);CREATE TABLE IF NOT EXISTS station(id INTEGER PRIMARY KEY CHECK(id=1),profile TEXT);CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,label_id INTEGER,profile TEXT,copies INTEGER);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,value TEXT);")
 DB.commit();ThreadingHTTPServer(('127.0.0.1',a.port),H).serve_forever()
if __name__=='__main__': main()
