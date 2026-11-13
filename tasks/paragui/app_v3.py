#!/usr/bin/env python3
"""Synthetic shared volunteer-service kiosk for the COMMUNITY-PANTRY1 task pair."""
import argparse, json, os, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = """
CREATE TABLE IF NOT EXISTS volunteers(
 id TEXT PRIMARY KEY, name TEXT NOT NULL,
 shift_station TEXT NOT NULL DEFAULT '', shift_window TEXT NOT NULL DEFAULT '', shift_status TEXT NOT NULL DEFAULT '',
 mileage REAL NOT NULL, claim_amount REAL, claim_status TEXT NOT NULL DEFAULT '', claim_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS desk(id INTEGER PRIMARY KEY CHECK(id=1), active_volunteer_id TEXT NOT NULL, active_panel TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, volunteer_id TEXT, panel TEXT, payload TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP);
"""
def dbcon():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c
def state(c):
 d=dict(c.execute("SELECT * FROM desk WHERE id=1").fetchone())
 vs=[dict(x) for x in c.execute("SELECT * FROM volunteers ORDER BY id")]
 return {"desk":d,"volunteers":vs}
def esc(s):
 return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")
def page(data):
 desk=data["desk"]; active=next((v for v in data["volunteers"] if v["id"]==desk["active_volunteer_id"]),data["volunteers"][0])
 roster="".join(f'<button class="person {"sel" if v["id"]==active["id"] else ""}" data-id="{esc(v["id"])}"><b>{esc(v["name"])}</b><small>{esc(v["id"])} · mileage slip {v["mileage"]} mi</small></button>' for v in data["volunteers"])
 shift=(desk["active_panel"]=="shift")
 if shift:
  form=f"""
  <div class="form"><label>Station<select id="station"><option></option>{''.join(f'<option {"selected" if active["shift_station"]==x else ""}>{x}</option>' for x in ["Check-in","Produce","Bagging","Driver","Cold storage"])}</select></label>
  <label>Shift window<input id="window" value="{esc(active["shift_window"])}" placeholder="e.g. 08:00-10:00"></label>
  <label>Status<select id="status"><option></option><option {"selected" if active["shift_status"]=="CONFIRMED" else ""}>CONFIRMED</option></select></label>
  <button id="save">Save shift assignment</button></div>"""
 else:
  form=f"""
  <div class="form"><label>Reimbursement amount ($)<input id="amount" value="{esc(active["claim_amount"] if active["claim_amount"] is not None else "")}" placeholder="e.g. 8.04"></label>
  <label>Decision<select id="decision"><option></option>{''.join(f'<option {"selected" if active["claim_status"]==x else ""}>{x}</option>' for x in ["APPROVED","REVIEW"])}</select></label>
  <label>Note<input id="note" value="{esc(active["claim_note"])}" placeholder="e.g. mileage slip verified"></label>
  <button id="save">Save mileage claim</button></div>"""
 roster_done=sum(bool(v["shift_status"]) for v in data["volunteers"])
 claims_done=sum(bool(v["claim_status"]) for v in data["volunteers"])
 return f"""<!doctype html><html><head><meta charset="utf-8"><title>Community Pantry Desk</title>
<style>
*{{box-sizing:border-box}}body{{font:16px Arial,sans-serif;margin:0;background:#f4f6f8;color:#172033}}header{{padding:18px 26px;background:#183b56;color:white}}
header h1{{margin:0 0 5px;font-size:24px}}header p{{margin:0;color:#d6e7f3}}main{{display:grid;grid-template-columns:390px 1fr;gap:18px;padding:20px;max-width:1400px;margin:auto}}
.card{{background:#fff;border:1px solid #d8e0e8;border-radius:8px;padding:16px;box-shadow:0 1px 2px #0001}}h2{{margin:0 0 12px;font-size:20px}}.people{{display:flex;flex-direction:column;gap:7px;max-height:760px;overflow:auto}}
.person{{text-align:left;padding:12px;border:1px solid #cbd5df;border-radius:6px;background:white;cursor:pointer}}.person.sel{{border:2px solid #177db5;background:#eaf6fc}}
small{{display:block;color:#647386;margin-top:4px}}.tabs{{display:flex;gap:8px;margin-bottom:16px}}.tab{{padding:10px 14px;border:1px solid #bcc7d1;border-radius:5px;background:#eef2f5;cursor:pointer}}.tab.sel{{background:#176d91;color:white;border-color:#176d91}}
.banner{{padding:12px;background:#eef6f8;border-left:4px solid #167da3;margin-bottom:14px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.form{{display:grid;gap:13px;max-width:620px}}label{{display:grid;gap:5px;font-weight:600}}input,select{{font:16px Arial;padding:9px;border:1px solid #aab8c4;border-radius:4px}}#save{{padding:11px;background:#166b44;color:#fff;border:0;border-radius:5px;font-weight:bold;cursor:pointer}}.source{{margin-top:15px;color:#48586a;font-size:14px;line-height:1.55}}.status{{margin-top:12px;min-height:24px;color:#166b44;font-weight:bold}}
</style></head><body><header><h1>Saturday Pantry Service — Volunteer Desk</h1><p>Community Pantry · Shift date: November 21, 2026 · One shared service station</p></header>
<main><section class="card"><h2>Volunteer roster</h2><div class="people">{roster}</div></section><section class="card">
<h2>{esc(active["name"])} <small>{esc(active["id"])}</small></h2><div class="banner">Active volunteer: <b id="active">{esc(active["id"])}</b> &nbsp;|&nbsp; Active work area: <b id="panel">{'Shift roster' if shift else 'Mileage claims'}</b></div>
<div class="tabs"><button class="tab {"sel" if shift else ""}" data-panel="shift">Shift roster</button><button class="tab {"sel" if not shift else ""}" data-panel="mileage">Mileage claims</button></div>
<div id="form">{form}</div><div id="statusmsg" class="status"></div>
<div class="source"><b>Desk counts:</b> {roster_done}/6 shift assignments recorded; {claims_done}/6 mileage claims processed.<br>Use the signed shift roster and mileage slips supplied in the task instructions.</div>
</section></main>
<script>
async function refresh(){{try{{let r=await fetch('/state');let d=await r.json();if(d.desk.active_volunteer_id!=='{esc(active["id"])}'||d.desk.active_panel!=='{esc(desk["active_panel"])}')location.reload()}}catch(e){{}}}}
document.querySelectorAll('.person').forEach(b=>b.onclick=async()=>{{await fetch('/select',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:b.dataset.id}})}});location.reload()}});
document.querySelectorAll('.tab').forEach(b=>b.onclick=async()=>{{await fetch('/panel',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{panel:b.dataset.panel}})}});location.reload()}});
document.querySelector('#save').onclick=async()=>{{let payload={{}};
if('{esc(desk["active_panel"])}'==='shift')payload={{station:document.querySelector('#station').value,window:document.querySelector('#window').value,status:document.querySelector('#status').value}};
else payload={{amount:document.querySelector('#amount').value,decision:document.querySelector('#decision').value,note:document.querySelector('#note').value}};
let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});let d=await r.json();document.querySelector('#statusmsg').textContent=d.message;setTimeout(()=>location.reload(),500)
}};
setInterval(refresh,900);
</script></body></html>"""
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def send(self,body,typ="application/json",status=200):
  b=body.encode();self.send_response(status);self.send_header("Content-Type",typ+"; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  c=dbcon();d=state(c);c.close()
  if urlparse(self.path).path=="/state":self.send(json.dumps(d,ensure_ascii=False))
  elif urlparse(self.path).path in ("/","/desk"):self.send(page(d),"text/html")
  else:self.send("{}",status=404)
 def do_POST(self):
  n=int(self.headers.get("Content-Length","0"));p=json.loads(self.rfile.read(n) or b"{}");c=dbcon();desk=c.execute("SELECT * FROM desk WHERE id=1").fetchone();msg="Saved."
  if self.path=="/select":
   vid=p.get("id",""); c.execute("UPDATE desk SET active_volunteer_id=? WHERE id=1",(vid,))
  elif self.path=="/panel":
   panel=p.get("panel",""); c.execute("UPDATE desk SET active_panel=? WHERE id=1",(panel,))
  elif self.path=="/save":
   vid,panel=desk["active_volunteer_id"],desk["active_panel"]
   if panel=="shift":
    c.execute("UPDATE volunteers SET shift_station=?,shift_window=?,shift_status=? WHERE id=?",(p.get("station",""),p.get("window",""),p.get("status",""),vid))
   else:
    try:amount=round(float(p.get("amount")),2)
    except (ValueError,TypeError):amount=None
    c.execute("UPDATE volunteers SET claim_amount=?,claim_status=?,claim_note=? WHERE id=?",(amount,p.get("decision",""),p.get("note",""),vid))
   c.execute("INSERT INTO events(event,volunteer_id,panel,payload) VALUES('save',?,?,?)",(vid,panel,json.dumps(p,sort_keys=True)))
   msg=f"Saved under {vid} · {panel}."
  c.commit();c.close();self.send(json.dumps({"message":msg}))
def main():
 global DB
 a=argparse.ArgumentParser();a.add_argument("--db",default=os.path.join(HERE,"app.db"));a.add_argument("--port",type=int,default=8138);args=a.parse_args();DB=args.db
 ThreadingHTTPServer(("127.0.0.1",args.port),Handler).serve_forever()
if __name__=="__main__":main()
