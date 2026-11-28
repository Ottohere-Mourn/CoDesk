from __future__ import annotations
import argparse,hashlib,json,sqlite3,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
LOCK=threading.RLock();REQUIRED={"source_ref","impact","root_cause"}
def connect(root):c=sqlite3.connect(root/"tickets.db",timeout=8);c.row_factory=sqlite3.Row;return c
def review(root,ticket_id,evidence):
 c=connect(root);row=c.execute("SELECT * FROM tickets WHERE ticket_id=?",(ticket_id,)).fetchone()
 if not row:c.close();return {"error":"ticket_not_found"},404
 missing=sorted(REQUIRED-set(k for k,v in evidence.items() if str(v).strip()));preview=uuid.uuid4().hex;decision="REJECTED" if missing else "READY";c.execute("INSERT INTO reviews VALUES(?,?,?,?)",(preview,ticket_id,decision,json.dumps(missing)));c.commit();c.close()
 with (root/"workflow_events.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"event":"REVIEW","ticket_id":ticket_id,"preview_id":preview,"decision":decision,"missing":missing})+"\n")
 return {"preview_id":preview,"decision":decision,"missing_evidence":missing},(422 if missing else 200)
def approve(root,preview_id,evidence,assignee):
 with LOCK:
  c=connect(root);r=c.execute("SELECT * FROM reviews WHERE preview_id=?",(preview_id,)).fetchone()
  if not r or r["decision"]!="READY":c.close();return {"error":"review_not_ready"},409
  missing=sorted(REQUIRED-set(k for k,v in evidence.items() if str(v).strip()))
  if missing:c.close();return {"error":"evidence_missing","missing_evidence":missing},422
  row=c.execute("SELECT * FROM tickets WHERE ticket_id=?",(r["ticket_id"],)).fetchone();
  if row["source_ref"]!=evidence.get("source_ref") or row["impact"]!=evidence.get("impact") or row["root_cause_hint"]!=evidence.get("root_cause"):c.close();return {"error":"evidence_does_not_match_source"},422
  eid=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest();c.execute("UPDATE tickets SET status='APPROVED',assignee=?,evidence_json=? WHERE ticket_id=?",(assignee,json.dumps(evidence,sort_keys=True),r["ticket_id"]));c.execute("INSERT OR REPLACE INTO approvals VALUES(?,?,?,'APPROVED')",(r["ticket_id"],preview_id,eid));c.commit();c.close()
  with (root/"workflow_events.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"event":"APPROVED","ticket_id":r["ticket_id"],"preview_id":preview_id,"evidence_hash":eid})+"\n")
  return {"ticket_id":r["ticket_id"],"status":"APPROVED","evidence_hash":eid},200
PAGE="<!doctype html><meta charset='utf-8'><title>Escalation Hub</title><h1>Escalation Hub</h1><p>Ticket inventory: <a href='/tickets?queue=security'>security</a> | <a href='/tickets?queue=data'>data</a> | <a href='/tickets?queue=performance'>performance</a></p><p>Preview and approval endpoints accept JSON at /review and /approve.</p>"
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  b=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE)
  if self.path=="/health":return self.send(200,{"status":"ok"})
  if urlparse(self.path).path=="/tickets":
   q=parse_qs(urlparse(self.path).query).get("queue",[""])[0];c=connect(self.server.root);rows=[dict(r) for r in c.execute("SELECT * FROM tickets WHERE category=? ORDER BY ticket_id",(q,))];c.close();return self.send(200,rows)
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  try:d=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
  except json.JSONDecodeError:return self.send(400,{"error":"invalid_json"})
  if self.path=="/review":r,s=review(self.server.root,d.get("ticket_id",""),d.get("evidence",{}))
  elif self.path=="/approve":r,s=approve(self.server.root,d.get("preview_id",""),d.get("evidence",{}),d.get("assignee",""))
  else:return self.send(404,{"error":"not_found"})
  return self.send(s,r)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();s=ThreadingHTTPServer(("127.0.0.1",18118),Handler);s.root=Path(a.root);s.serve_forever()
if __name__=="__main__":main()
