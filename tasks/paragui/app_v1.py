#!/usr/bin/env python3
"""Shared clip playhead review desk."""
import argparse, html, sqlite3, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
DB=None
CSS="<style>body{font:18px Arial;background:#eef2f4;color:#1e2930;margin:0}header{background:#173d4a;color:white;padding:16px 28px}main{max-width:1120px;margin:24px auto;background:white;padding:24px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:20px}.frame{height:300px;background:#202e36;color:white;padding:25px;box-sizing:border-box}.frame h2{margin-top:38px;font-size:28px}.frame p{font-size:22px;line-height:1.4}button,a{font:inherit;padding:10px 14px;margin:4px}button{background:#155f72;color:white;border:0}input,select,textarea{font:inherit;padding:8px;width:100%;box-sizing:border-box}label{display:block;margin:10px 0}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{border:1px solid #bbb;padding:8px;text-align:left}th{background:#dce9ed}.muted{color:#66767d}</style>"
def esc(x): return html.escape(str(x or ""),quote=True)
def one(sql,args=()): return DB.execute(sql,args).fetchone()
def all_(sql,args=()): return DB.execute(sql,args).fetchall()
def page(title,body): return f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>{CSS}</head><body><header><b>Northline Operations | Clip Review Desk</b></header><main><h1>{esc(title)}</h1>{body}</main></body></html>"
def set_frame(n):
 n=max(1,min(13,int(n))); DB.execute("UPDATE session_state SET frame_no=? WHERE id=1",(n,))
 DB.execute("INSERT INTO events(kind,details) VALUES('seek',?)",(str(n),)); DB.commit()
def current(): return int(one("SELECT frame_no FROM session_state WHERE id=1")[0])
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def send(self,body,status=200):
  b=body.encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def redirect(self,url):
  self.send_response(303);self.send_header("Location",url);self.end_headers()
 def do_GET(self):
  p=urllib.parse.urlparse(self.path)
  if p.path=="/health": return self.send("ok")
  if p.path not in ("/","/review"): return self.send(page("Not found","<p>Not found.</p>"),404)
  q=urllib.parse.parse_qs(p.query)
  if "frame" in q:
   try: set_frame(int(q["frame"][0]))
   except ValueError: pass
  n=current(); f=one("SELECT timecode,title,observation,location FROM frames WHERE frame_no=?",(n,))
  if not f: return self.send(page("No frame","<p>No frame.</p>"),404)
  prev=max(1,n-1); nxt=min(13,n+1)
  body=f"""<p class="muted">Clip NL-448 | Camera B ? Frame {n} of 13 ? Current clip time: <b>{esc(f[0])}</b></p>
  <div class="grid"><div><section class="frame"><small>LOADING BAY 4 / CAMERA B</small><h2>{esc(f[1])}</h2><p>{esc(f[2])}</p><small>AREA: {esc(f[3])}</small></section>
  <p><a href="/review?frame={prev}">? Previous frame</a><a href="/review?frame={nxt}">Next frame ?</a></p></div>
  <div><form method="post" action="/mark"><label>Worklist<select name="category"><option value="">Select</option><option>Safety follow-up</option><option>Maintenance</option></select></label>
  <label>Observation note<textarea name="note" rows="5" minlength="8" required></textarea></label><button>Log observation at visible time</button></form>
  <p class="muted">The saved timestamp comes from the clip position currently shown on this desk.</p></div></div>"""
  rows=all_("SELECT category,frame_no,timecode,note FROM markers ORDER BY id DESC LIMIT 12")
  trs="".join(f"<tr><td>{esc(r[0])}</td><td>{r[1]}</td><td>{esc(r[2])}</td><td>{esc(r[3])}</td></tr>" for r in rows)
  body+="<h2>Recent observations</h2><table><tr><th>Worklist</th><th>Frame</th><th>Time</th><th>Note</th></tr>"+trs+"</table>"
  return self.send(page("NL-448 - Loading Bay 4 review",body))
 def do_POST(self):
  if urllib.parse.urlparse(self.path).path!="/mark": return self.send(page("Not found","<p>Unknown operation</p>"),404)
  size=int(self.headers.get("Content-Length","0")); d=urllib.parse.parse_qs(self.rfile.read(size).decode(),keep_blank_values=True)
  category=d.get("category",[""])[0].strip(); note=d.get("note",[""])[0].strip()
  if category not in ("Safety follow-up","Maintenance") or len(note)<8: return self.send(page("Not saved","<p>Select a worklist and add a useful note.</p>"),400)
  n=current(); f=one("SELECT timecode FROM frames WHERE frame_no=?",(n,))
  DB.execute("INSERT INTO markers(category,frame_no,timecode,note) VALUES(?,?,?,?)",(category,n,f[0],note))
  DB.execute("INSERT INTO events(kind,details) VALUES('marker',?)",(f"{category}|{n}|{note}",));DB.commit()
  return self.redirect("/review")
def main():
 global DB
 ap=argparse.ArgumentParser();ap.add_argument("--db",required=True);ap.add_argument("--port",type=int,required=True);a=ap.parse_args()
 DB=sqlite3.connect(a.db,check_same_thread=False);DB.row_factory=sqlite3.Row
 DB.executescript("CREATE TABLE IF NOT EXISTS frames(frame_no INTEGER PRIMARY KEY,timecode TEXT,title TEXT,observation TEXT,location TEXT);CREATE TABLE IF NOT EXISTS session_state(id INTEGER PRIMARY KEY CHECK(id=1),frame_no INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS markers(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,frame_no INTEGER,timecode TEXT,note TEXT);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,details TEXT);")
 DB.commit();ThreadingHTTPServer(("127.0.0.1",a.port),H).serve_forever()
if __name__=="__main__": main()
