"""PO invoice reconciliation + human-like receipt archive GUI fixture."""
from __future__ import annotations
import email.policy, hashlib, html, json, sqlite3
from datetime import datetime, timezone
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

FIXTURE_ID="po-reconcile-and-receipt-archive-v1"
CASE_ID="ha-po-reconcile-normal-user-v1"
AGENT_CASE="PR-4831"
USER_FILE="D-4831-receipt.csv"
USER_FILE_CONTENT=("vendor,document_id,received_date,description,amount,currency\n"
 "Northstar Office Supply,D-4831,2026-11-09,Printer paper and toner,184.50,USD\n").encode()
EXPECTED={"decision":"hold_for_variance","accepted_units":"11","freight_over_cap":"26.00",
          "refs":("PO-4831","RCV-4831","INV-4831","POL-FRT-2")}
DOCS={
"/agent":("Procurement Review Queue","""
<h1>Procurement Review Queue</h1><p>Assigned work: reconcile invoice <b>INV-4831</b> against its purchase order and receiving evidence.</p>
<p>Review the linked documents and submit an internal disposition. Do not release payment or edit source records.</p>
<nav><a href="/po/PO-4831">Purchase order PO-4831</a> ? <a href="/receiving/RCV-4831">Receiving report RCV-4831</a> ?
<a href="/invoice/INV-4831">Vendor invoice INV-4831</a> ? <a href="/policy/POL-FRT-2">Freight policy POL-FRT-2</a> ?
<a href="/resolution">Reconciliation form</a></nav>"""),
"/po/PO-4831":("Purchase Order PO-4831","""
<h1>Purchase Order PO-4831</h1><p>Vendor: Northstar Office Supply. Status: OPEN. Terms: Net 30.</p>
<table><tr><th>SKU</th><th>Description</th><th>Ordered units</th><th>Unit price</th><th>Line total</th></tr>
<tr><td>FLT-20</td><td>Industrial air filters</td><td>12</td><td>$48.00</td><td>$576.00</td></tr></table>
<p>Freight authorization limit: $60.00. Payment has not been released.</p>"""),
"/receiving/RCV-4831":("Receiving Report RCV-4831","""
<h1>Receiving Report RCV-4831</h1><p>Dock report for PO-4831. Twelve cartons expected. Eleven filters accepted into stock.</p>
<p>One carton was visibly crushed and quarantined as damaged; it was not accepted.</p>
<p>Receiving clerk M. Chen. Inspection completed 2026-11-08.</p>"""),
"/invoice/INV-4831":("Vendor Invoice INV-4831","""
<h1>Vendor Invoice INV-4831</h1><p>Invoice from Northstar Office Supply, status: PENDING REVIEW.</p>
<p>FLT-20: 12 units ? $48.00 = $576.00. Freight: $86.00.</p>
<p>Invoice total: $662.00. No payment or adjustment has been posted.</p>"""),
"/policy/POL-FRT-2":("Freight Policy POL-FRT-2","""
<h1>Freight Policy POL-FRT-2</h1><p>Invoice line quantities must not exceed units accepted on the receiving report.</p>
<p>Damaged or quarantined units are not payable until a corrected invoice is received.</p>
<p>Freight above the purchase-order authorization limit must be held for vendor clarification.</p>
<p>When either condition is present, place the invoice on hold; record accepted units and each variance. Do not release payment.</p>""")}
def _canonical(value:Any)->bytes:
 return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def create_fixture(db_path:str|Path,run_id:str)->dict[str,Any]:
 path=Path(db_path);path.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(path) as db:
  db.executescript("""DROP TABLE IF EXISTS reconciliation;DROP TABLE IF EXISTS archive_submission;DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS run_meta;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE request_log(sequence INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,received_utc TEXT);
  CREATE TABLE reconciliation(sequence INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT,decision TEXT,accepted_units TEXT,
    freight_over_cap TEXT,source_refs TEXT,rationale TEXT,actor_id TEXT,received_utc TEXT);
  CREATE TABLE archive_submission(sequence INTEGER PRIMARY KEY AUTOINCREMENT,folder TEXT,file_name TEXT,
    content_sha256 TEXT,actor_id TEXT,received_utc TEXT);""")
  db.execute("INSERT INTO run_meta VALUES('run_id',?)",(str(run_id),));db.execute("INSERT INTO run_meta VALUES('fixture_id',?)",(FIXTURE_ID,));db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,
         "initial_state":{"agent_submissions":0,"user_submissions":0}}
 manifest={**public,"sha256":hashlib.sha256(_canonical(public)).hexdigest()}
 path.with_suffix(path.suffix+".fixture.json").write_text(json.dumps(manifest,indent=2)+"\n")
 return manifest
def evaluate_agent(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row
   rows=[dict(r) for r in db.execute("SELECT * FROM reconciliation ORDER BY sequence")]
   reads=[dict(r) for r in db.execute("SELECT * FROM request_log ORDER BY sequence")]
   fixture=db.execute("SELECT value FROM run_meta WHERE key='fixture_id'").fetchone()
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"fixture_integrity":False,"submitted":False}}
 latest=rows[-1] if rows else None
 refs=set((latest or {}).get("source_refs","").upper().replace(","," ").replace(";"," ").split())
 paths=("/po/PO-4831","/receiving/RCV-4831","/invoice/INV-4831","/policy/POL-FRT-2")
 visits={p:any(r["method"]=="GET" and r["path"]==p and r["status"]==200 for r in reads) for p in paths}
 checks={"fixture_integrity":bool(fixture and fixture["value"]==FIXTURE_ID),"submitted":latest is not None,
  "correct_case":bool(latest and latest["case_id"]=="INV-4831"),
  "hold_decision":bool(latest and latest["decision"]==EXPECTED["decision"]),
  "accepted_quantity":bool(latest and latest["accepted_units"].strip()==EXPECTED["accepted_units"]),
  "freight_variance":bool(latest and latest["freight_over_cap"].strip().replace("$","")==EXPECTED["freight_over_cap"]),
  "all_sources_cited":all(x in refs for x in EXPECTED["refs"]),
  "reasoning_mentions_both_variances":bool(latest and
    any(x in latest["rationale"].lower() for x in ("damaged","damage","crushed","quarantined")) and
    all(x in latest["rationale"].lower() for x in ("freight","hold"))),
  "agent_role":bool(latest and latest["actor_id"]=="S"),"viewed_all_source_pages":all(visits.values()),
  # A separate User Actor is expected to POST /archive/submit in Shared mode;
  # only unrelated writes constitute mutation of the Agent's protected sources.
  "source_fixture_unchanged":not any(r["method"]=="POST" and
      r["path"] not in {"/resolution/submit","/archive/submit"} for r in reads)}
 return {"success":all(checks.values()),"checks":checks,"submission_count":len(rows),"source_visits":visits,
  "latest":{k:latest.get(k) for k in ("case_id","decision","accepted_units","freight_over_cap","source_refs","rationale","actor_id")} if latest else None}
def evaluate_user(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;rows=[dict(r) for r in db.execute("SELECT * FROM archive_submission ORDER BY sequence")]
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"submitted":False}}
 latest=rows[-1] if rows else None
 expected=hashlib.sha256(USER_FILE_CONTENT).hexdigest()
 checks={"submitted":latest is not None,"expected_file_name":bool(latest and latest["file_name"]==USER_FILE),
  "file_content_matches":bool(latest and latest["content_sha256"]==expected),
  "correct_archive_folder":bool(latest and latest["folder"]=="Finance/November 2026"),
  "user_role":bool(latest and latest["actor_id"]=="U")}
 return {"success":all(checks.values()),"checks":checks,"submission_count":len(rows),
  "latest":{k:latest.get(k) for k in ("folder","file_name","content_sha256","actor_id")} if latest else None}
def evaluate(db_path:str|Path)->dict[str,Any]:
 return {"agent":evaluate_agent(db_path),"user":evaluate_user(db_path)}
def _page(title:str,content:str,saved:bool=False)->bytes:
 notice="<p id='saved'>Reconciliation saved.</p>" if saved else ""
 form=""
 if title=="Invoice Reconciliation":
  form=f"""<main><h2>Invoice reconciliation</h2>{notice}<form method="post" action="/resolution/submit">
  <label>Invoice ID <input name="case_id" value="INV-4831" required></label>
  <label>Disposition <select name="decision" required><option value="">Choose disposition</option>
  <option value="hold_for_variance">Hold for vendor clarification</option><option value="approve">Approve for payment</option>
  <option value="reject">Reject invoice</option></select></label>
  <label>Accepted units <input name="accepted_units" inputmode="numeric" required></label>
  <label>Freight above PO cap ($) <input name="freight_over_cap" inputmode="decimal" required></label>
  <label>Source document IDs <input name="source_refs" placeholder="List the records you checked" required></label>
  <label>Rationale <textarea name="rationale" required></textarea></label><button type="submit">Save reconciliation</button></form></main>"""
 elif title=="Finance Archive":
  notice="<p id='uploaded'>Receipt archived in Finance / November 2026.</p>" if saved else ""
  form=f"""<main><h2>Archive vendor receipt</h2><p>Destination: <b>Finance / November 2026</b></p>{notice}
  <form method="post" action="/archive/submit" enctype="multipart/form-data">
  <input type="hidden" name="folder" value="Finance/November 2026">
  <label>Signed receipt attachment <input id="attachment" type="file" name="attachment" required></label>
  <button type="submit">Archive receipt</button></form></main>"""
 return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
 <style>body{{font:18px/1.5 sans-serif;max-width:900px;margin:24px auto;padding:0 22px;background:#eef2f5;color:#182635}}
 header,main{{background:white;border:1px solid #c9d3dd;border-radius:8px;padding:18px 24px;margin:12px 0}}
 nav a{{display:inline-block;padding:8px;margin:6px;background:#edf5fc}}table{{border-collapse:collapse}}td,th{{padding:8px;border:1px solid #999}}
 label{{display:block;font-weight:bold;margin:12px 0}}input,select,textarea{{display:block;box-sizing:border-box;width:100%;font:inherit;padding:8px}}
 button,.button{{display:inline-block;font:inherit;padding:10px 18px;background:#145a8d;color:white;border:0;border-radius:4px}}</style></head>
 <body><header>{content}</header>{form}</body></html>""".encode()
def make_server(db_path:str|Path,host:str="127.0.0.1",port:int=0)->ThreadingHTTPServer:
 dbfile=str(Path(db_path));access=Path(db_path).with_suffix(".http.jsonl");access.parent.mkdir(parents=True,exist_ok=True)
 class Handler(BaseHTTPRequestHandler):
  server_version="CoDeskPOReconcile/1.0"
  def log_message(self,fmt:str,*args:Any)->None:
   row=(self.command,self.path,int(getattr(self,"_status",200)),datetime.now(timezone.utc).isoformat())
   with sqlite3.connect(dbfile) as db:db.execute("INSERT INTO request_log(method,path,status,received_utc) VALUES(?,?,?,?)",row);db.commit()
   with open(access,"a",encoding="utf-8") as f:f.write(json.dumps({"method":row[0],"path":row[1],"status":row[2],"received_utc":row[3]})+"\n")
  def send(self,code:int,data:bytes,ctype:str="text/html; charset=utf-8",extra:dict[str,str]|None=None)->None:
   self._status=code;self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(data)))
   self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
   self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
   for k,v in (extra or {}).items():self.send_header(k,v)
   self.end_headers();self.wfile.write(data)
  def do_GET(self)->None:
   path=self.path.split("?",1)[0]
   if path=="/healthz":self.send(200,b"ok","text/plain")
   elif path in DOCS:
    title,content=DOCS[path];self.send(200,_page(title,content))
   elif path=="/resolution":self.send(200,_page("Invoice Reconciliation","<h1>Invoice Reconciliation</h1>"))
   elif path=="/portal":
    c=f"""<h1>Vendor Portal</h1><h2>Receipt attachments</h2><p>Upload completed for Northstar Office Supply.</p>
    <p>File the signed receiving acknowledgement in your November finance folder.</p>
    <p><a class="button" href="/download/receipt">Download receiving acknowledgement D-4831</a></p>
    <p>Document: {USER_FILE} ? issued 2026-11-09 ? PO-4831 attachment.</p><p><a href="/archive">Open Finance Archive</a></p>"""
    self.send(200,_page("Vendor Portal",c))
   elif path=="/archive":self.send(200,_page("Finance Archive","<h1>Finance Archive</h1><p>File vendor receipts in the correct period folder.</p>"))
   elif path=="/download/receipt":self.send(200,USER_FILE_CONTENT,"text/csv; charset=utf-8",{"Content-Disposition":f'attachment; filename="{USER_FILE}"'})
   else:self.send(404,b"Not found","text/plain")
  def do_POST(self)->None:
   if self.path=="/resolution/submit":
    try:
     n=int(self.headers.get("Content-Length","0"))
     if n<=0 or n>8192:raise ValueError()
     q=parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
     d={k:q.get(k,[""])[0].strip() for k in ("case_id","decision","accepted_units","freight_over_cap","source_refs","rationale")}
     if not all(d.values()):raise ValueError()
    except (UnicodeDecodeError,ValueError,KeyError):self.send(400,b"Complete all reconciliation fields.","text/plain");return
    with sqlite3.connect(dbfile) as db:
     db.execute("""INSERT INTO reconciliation(case_id,decision,accepted_units,freight_over_cap,source_refs,rationale,actor_id,received_utc)
      VALUES(?,?,?,?,?,?,?,?)""",(d["case_id"],d["decision"],d["accepted_units"],d["freight_over_cap"],d["source_refs"],d["rationale"],"S",datetime.now(timezone.utc).isoformat()));db.commit()
    self.send(200,_page("Invoice Reconciliation","<h1>Invoice Reconciliation</h1>",True));return
   if self.path!="/archive/submit":self.send(404,b"Not found","text/plain");return
   try:
    n=int(self.headers.get("Content-Length","0"))
    if n<=0 or n>2_000_000:raise ValueError()
    ctype=self.headers.get("Content-Type","")
    msg=BytesParser(policy=email.policy.default).parsebytes(b"Content-Type: "+ctype.encode()+b"\r\nMIME-Version: 1.0\r\n\r\n"+self.rfile.read(n))
    fields={};filename="";content=b""
    for part in msg.iter_parts():
     name=part.get_param("name",header="content-disposition")
     payload=part.get_payload(decode=True) or b""
     if name=="attachment":filename=Path(part.get_filename() or "").name;content=payload
     elif name:fields[name]=payload.decode("utf-8","replace").strip()
    if not filename or not content or not fields.get("folder"):raise ValueError()
   except (UnicodeDecodeError,ValueError,TypeError):self.send(400,b"Choose a receipt file.","text/plain");return
   with sqlite3.connect(dbfile) as db:
    db.execute("INSERT INTO archive_submission(folder,file_name,content_sha256,actor_id,received_utc) VALUES(?,?,?,?,?)",
      (fields["folder"],filename,hashlib.sha256(content).hexdigest(),"U",datetime.now(timezone.utc).isoformat()));db.commit()
   self.send(200,_page("Finance Archive","<h1>Finance Archive</h1>",True))
 server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True;server.access_log_path=str(access);return server
