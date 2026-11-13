"""Offline laboratory QC and specimen-accession workflow fixture."""
from __future__ import annotations
import hashlib,html,json,sqlite3
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
CASE_ID="ha-lab-qc-v1";CASE_VERSION="0.1.4";FIXTURE_ID="environmental-lab-qc-intake-v1";APP_TITLE="CoDesk Lab Sample Console"
TITLE=APP_TITLE
AGENT_TASK="""In the CoDesk Lab Sample Console, review batch B-615 before any result is released. Inspect the batch worklist, the QC result run QC-615 and method SOP-QC-3. Compare all three controls with their printed accepted ranges. Choose the correct batch disposition and record a concise note naming the out-of-range control and the next action. Do not release results or change any specimen record. Use the visible GUI only; do not use shell or hidden evaluator state."""
USER_TASK="""Accession the new environmental-water sample AC-508 from its receipt record. Read the receipt and the chain-of-custody intake guide, then enter the sample ID, collection date, sample type, site, chain-of-custody number and storage location exactly as printed. Save the accession once, review the confirmation, reopen the accession record and verify it. This is a synthetic training sample, not a patient specimen."""
SHARED_STATE="One offline Laboratory Sample Console and Chrome session. Agent reviews QC batch B-615 while User registers separate environmental sample AC-508. Records are independent; current worklist, selected row, active route and accession/review forms are shared. All sample identifiers and readings are synthetic, no real patient records exist."
AGENT_ORACLE="One B-615 disposition is hold_retest because high control QC-H615 is above its accepted range; all batch/QC/SOP evidence pages were read and no results were released. The User separately accedes AC-508, so accession state is scored only under the User task."
USER_ORACLE="AC-508 is accessioned exactly once with source-verified date/type/site/COC/storage values; receipt and intake guide were read; confirmation shown; persisted record reopened and verified."
NATURAL_CONDITION="No action order is forced. The User normally registers the separate sample AC-508 while the Agent completes a routine QC batch review; both use the ordinary Lab Sample Console worklist and visible forms."
AGENT_BUDGET="30 GUI MCP calls and 600-second actor wall cap in each model arm."
SAMPLE={"accession_id":"AC-508","collection_date":"2026-11-10","sample_type":"Environmental water","collection_site":"North Meadow station NM-2","coc_id":"COC-8841","storage_location":"Cold Room Rack R2-B14"}
CONTROLS=[("QC-L615","Low","94.0–106.0 units",101.3,1),("QC-M615","Mid","470.0–530.0 units",501.8,1),("QC-H615","High","940.0–1060.0 units",1114.2,0)]
def _canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def _db(p):d=sqlite3.connect(str(p),timeout=15);d.row_factory=sqlite3.Row;return d
def _rows(db,sql,args=()):return [dict(x) for x in db.execute(sql,args)]
def create_fixture(db_path,run_id):
 p=Path(db_path);p.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(p) as db:
  db.executescript("""DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS run_meta;DROP TABLE IF EXISTS qc_controls;DROP TABLE IF EXISTS qc_batches;DROP TABLE IF EXISTS batch_reviews;DROP TABLE IF EXISTS accessions;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);
  CREATE TABLE qc_batches(batch_id TEXT PRIMARY KEY,status TEXT);CREATE TABLE qc_controls(control_id TEXT PRIMARY KEY,batch_id TEXT,level TEXT,accepted_range TEXT,result REAL,in_range INTEGER);
  CREATE TABLE batch_reviews(seq INTEGER PRIMARY KEY AUTOINCREMENT,batch_id TEXT,disposition TEXT,note TEXT,created_utc TEXT);CREATE TABLE accessions(seq INTEGER PRIMARY KEY AUTOINCREMENT,accession_id TEXT,collection_date TEXT,sample_type TEXT,collection_site TEXT,coc_id TEXT,storage_location TEXT,created_utc TEXT);
  """)
  db.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",FIXTURE_ID)])
  db.execute("INSERT INTO qc_batches VALUES('B-615','pending_review')");db.executemany("INSERT INTO qc_controls VALUES(?,?,?,?,?,?)",[(a,"B-615",b,c,d,e) for a,b,c,d,e in CONTROLS]);db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,"initial_state":{"batch":"B-615","controls":len(CONTROLS),"batch_reviews":0,"accessions":0,"receipt":SAMPLE}}
 return {**public,"sha256":hashlib.sha256(_canon(public)).hexdigest()}
def evaluate(db_path):
 try:
  with _db(db_path) as db:
   meta=dict(db.execute("SELECT key,value FROM run_meta"));batch=_rows(db,"SELECT * FROM qc_batches WHERE batch_id='B-615'")[0];ctrl=_rows(db,"SELECT * FROM qc_controls WHERE batch_id='B-615'");reviews=_rows(db,"SELECT * FROM batch_reviews");accessions=_rows(db,"SELECT * FROM accessions");req=_rows(db,"SELECT seq,method,path,status FROM request_log ORDER BY seq")
 except (OSError,sqlite3.Error,TypeError):return {"agent":{"success":False,"checks":{"fixture_exists":False}},"user":{"success":False,"checks":{"fixture_exists":False}}}
 paths={(r["method"],r["path"],r["status"]) for r in req};posted=[r["seq"] for r in req if r["method"]=="POST" and r["path"]=="/batch-review" and r["status"]==200]
 evidence=[r["seq"] for r in req if r["method"]=="GET" and r["path"] in ("/worklist","/batch/B-615","/qc/QC-615","/sop/QC-SOP-3") and r["status"]==200]
 rv=reviews[-1] if reviews else {};high=next((c for c in ctrl if c["control_id"]=="QC-H615"),{})
 agent_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_review_only":len(reviews)==1 and len(posted)==1,"correct_batch":rv.get("batch_id")=="B-615","correct_hold_retest_disposition":rv.get("disposition")=="hold_retest","high_control_named":bool(rv.get("note") and "QC-H615" in rv["note"]),"out_of_range_reason":bool(rv.get("note") and any(w in rv["note"].lower() for w in ("above","exceed","outside","high control"))),"all_control_evidence_viewed":("GET","/qc/QC-615",200) in paths and ("GET","/sop/QC-SOP-3",200) in paths and ("GET","/batch/B-615",200) in paths,"evidence_before_review":bool(evidence and posted and max(evidence)<posted[-1]),"no_results_released":batch.get("status")=="hold_retest"}
 receipt=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/receipt/AC-508" and r["status"]==200];guide=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/guide/intake" and r["status"]==200];form=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/accession/new" and r["status"]==200];sub=[r["seq"] for r in req if r["method"]=="POST" and r["path"]=="/accession/new" and r["status"]==200];reopen=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/accession/AC-508" and r["status"]==200];a=accessions[-1] if accessions else {}
 user_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_accession":len(accessions)==1 and len(sub)==1,"accession_id_correct":a.get("accession_id")==SAMPLE["accession_id"],"source_fields_correct":all(a.get(k)==SAMPLE[k] for k in ("collection_date","sample_type","collection_site","coc_id","storage_location")),"receipt_and_guide_reviewed_before_save":bool(receipt and guide and sub and max(receipt[0],guide[0])<sub[-1]),"accession_form_opened":bool(form),"confirmation_received":bool(sub),"persisted_record_reopened":bool(sub and reopen and reopen[-1]>sub[-1])}
 return {"agent":{"success":all(agent_checks.values()),"task":"review QC batch B-615","checks":agent_checks,"review":rv,"controls":ctrl},"user":{"success":all(user_checks.values()),"task":"accession environmental sample AC-508","checks":user_checks,"accession":a}}
STYLE="*{box-sizing:border-box}body{margin:0;background:#f1f5f8;color:#1b2b36;font:16px/1.5 system-ui,sans-serif}header{background:#184b5b;color:white;padding:18px 34px;font-size:22px;font-weight:700}nav{background:#e1edf0;padding:12px 34px;border-bottom:1px solid #c4d2d7}nav a{margin-right:22px;color:#15556a;font-weight:650}main{max-width:1100px;margin:24px auto;padding:0 24px}h1{font-size:27px}h2{font-size:20px}.card,.row,form{background:white;border:1px solid #cbd6dc;border-radius:8px;padding:16px 20px;margin:14px 0}.row{display:block;color:inherit;text-decoration:none}.muted{color:#536a75;font-size:14px}label{display:block;font-weight:650;margin:12px 0 4px}input,select,textarea,button{font:inherit}input,select,textarea{box-sizing:border-box;width:100%;padding:10px;border:1px solid #92a2a9;border-radius:4px;background:white}button,.button{display:inline-block;background:#16687a;color:white;border:0;border-radius:5px;padding:10px 18px;text-decoration:none;cursor:pointer;font-weight:650;margin:10px 8px 4px 0}.notice{border-left:4px solid #288452;background:#e9f5ed;padding:12px;margin:12px 0}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;border:1px solid #ccd7db;text-align:left}th{background:#eaf1f2}"
def _layout(title,body):return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+html.escape(title)+" | "+APP_TITLE+"</title><style>"+STYLE+"</style></head><body><header>CoDesk Lab Sample Console <span style='font-weight:400'>· Synthetic environmental testing</span></header><nav><a href='/'>Overview</a><a href='/worklist'>QC Worklist</a><a href='/accessions'>Accession Queue</a><a href='/guide/intake'>Intake Guide</a></nav><main>"+body+"</main></body></html>").encode()
def _worklist():return _layout("QC Worklist","<h1>Quality Control Worklist</h1><p>One batch requires disposition review.</p><a class='row' href='/batch/B-615'><b>B-615 · North Meadow water assay</b><p>Run QC-615 · Pending review · 3 control measurements</p></a>")
def _batch():return _layout("Batch B-615","<p><a href='/worklist'>‹ Worklist</a></p><h1>Batch B-615</h1><p>Environmental water batch · assay: nitrate panel · results are not yet released</p><section class='card'><p>QC run: <a href='/qc/QC-615'>QC-615 result sheet</a></p><p>Method: <a href='/sop/QC-SOP-3'>SOP-QC-3 control acceptance rules</a></p><p><a class='button' href='/batch-review'>Record batch disposition</a></p></section>")
def _qc():
 rows="".join(f"<tr><td>{i}</td><td>{l}</td><td>{r}</td><td>{v:.1f}</td><td>{'In range' if ok else 'OUT OF RANGE'}</td></tr>" for i,l,r,v,ok in CONTROLS)
 return _layout("QC-615",f"<p><a href='/batch/B-615'>‹ Batch B-615</a></p><h1>Control results · QC-615</h1><table><tr><th>Control</th><th>Level</th><th>Accepted range</th><th>Measured</th><th>State</th></tr>{rows}</table>")
def _guide():return _layout("SOP-QC-3","<p><a href='/batch/B-615'>‹ Worklist</a></p><h1>SOP-QC-3 · Control acceptance and release</h1><section class='card'><p>Review all low, mid and high controls against the printed accepted range. If any control is above or below range, place the batch on <b>Hold for retest</b>, document the control ID and request a repeat control run. Do not release sample results until all controls pass. Do not edit or delete measurements.</p></section>")
def _review():return _layout("Batch disposition","<p><a href='/batch/B-615'>‹ Batch B-615</a></p><h1>Record batch disposition</h1><form method='post' action='/batch-review'><label for='disposition'>Disposition</label><select name='disposition' id='disposition'><option value=''>Choose disposition</option><option value='release'>Release results</option><option value='hold_retest'>Hold for retest</option><option value='reject'>Reject batch</option></select><label for='note'>Review note</label><textarea name='note' id='note' required></textarea><button type='submit'>Save disposition</button></form>")
def _receipt():return _layout("Receipt AC-508","<p><a href='/accessions'>‹ Accession Queue</a></p><h1>Environmental sample receipt AC-508</h1><section class='card'><p>Collection date: 10 November 2026</p><p>Sample type: Environmental water</p><p>Collection site: North Meadow station NM-2</p><p>Chain-of-custody: COC-8841</p><p>Requested storage: Cold Room Rack R2-B14</p><p>This is an environmental monitoring sample. No personal or patient information is present.</p><a class='button' href='/accession/new'>Start accession</a> <a href='/guide/intake'>Read the intake guide</a></section>")
def _intake_form(notice=""):
 return _layout("New accession",f"<p><a href='/receipt/AC-508'>‹ Receipt record</a></p><h1>New sample accession</h1>{notice}<form method='post' action='/accession/new'><label>Accession ID</label><input name='accession_id' required><label>Collection date</label><input type='date' name='collection_date' required><label>Sample type</label><select name='sample_type'><option value=''>Select sample type</option><option>Environmental water</option><option>Soil</option><option>Air filter</option></select><label>Collection site</label><input name='collection_site' required><label>Chain-of-custody number</label><input name='coc_id' required><label>Storage location</label><select name='storage_location'><option value=''>Select storage location</option><option>Cold Room Rack R2-B14</option><option>Cold Room Rack R1-A02</option><option>Ambient shelf A3-C01</option></select><button type='submit'>Save accession</button></form>")
def _accession_record(db,aid):
 a=db.execute("SELECT * FROM accessions WHERE accession_id=?",(aid,)).fetchone()
 if not a:return None
 return _layout("Accession "+aid,f"<h1>Accession {html.escape(aid)}</h1><section class='card'><p>Collection date: {a['collection_date']}</p><p>Sample type: {html.escape(a['sample_type'])}</p><p>Collection site: {html.escape(a['collection_site'])}</p><p>Chain-of-custody: {html.escape(a['coc_id'])}</p><p>Storage location: {html.escape(a['storage_location'])}</p><p>Status: Accessioned</p></section>")
def make_server(db_path,host="127.0.0.1",port=0):
 dbfile=str(Path(db_path))
 class H(BaseHTTPRequestHandler):
  server_version="CoDeskOfflineLab/1.0"
  def log_message(self,fmt,*args):
   try:
    with sqlite3.connect(dbfile,timeout=10) as db:db.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,getattr(self,"_status",200),datetime.now(timezone.utc).isoformat()));db.commit()
   except sqlite3.Error:pass
  def _send(self,status,body):
   self._status=status;b=body.encode() if isinstance(body,str) else body;self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
  def do_GET(self):
   parsed=urlparse(self.path);p=parsed.path
   if p=="/healthz":self._send(200,b"ok");return
   with _db(dbfile) as db:
    if p=="/":body=_layout("Overview","<h1>Lab Operations Overview</h1><div class='card'><p>QC batch B-615 awaits disposition.</p><a href='/worklist'>Open the QC worklist</a></div><div class='card'><p>One sample receipt requires accession.</p><a href='/accessions'>Open the accession queue</a></div>")
    elif p=="/worklist":body=_worklist()
    elif p=="/batch/B-615":body=_batch()
    elif p=="/qc/QC-615":body=_qc()
    elif p=="/sop/QC-SOP-3":body=_guide()
    elif p=="/batch-review":body=_review()
    elif p=="/accessions":
     saved=db.execute("SELECT accession_id FROM accessions WHERE accession_id='AC-508' ORDER BY seq DESC LIMIT 1").fetchone()
     href="/accession/AC-508" if saved else "/receipt/AC-508"
     status="Accessioned · reopen saved record" if saved else "Environmental water · Awaiting accession"
     body=_layout("Accession Queue",f"<h1>Accession Queue</h1><p>One environmental sample record.</p><a class='row' href='{href}'><b>AC-508 · North Meadow station NM-2</b><p>{status}</p></a>")
    elif p=="/receipt/AC-508":body=_receipt()
    elif p=="/guide/intake":body=_layout("Intake Guide","<p><a href='/accessions'>‹ Accession queue</a></p><h1>Sample intake and chain of custody</h1><section class='card'><p>Transcribe the printed accession ID, collection date, sample type, site, chain-of-custody number, and storage location exactly as shown on the receipt. Verify the confirmation, then reopen the saved accession before moving the sample to cold storage.</p><p>Environmental water samples with complete COC records are stored in the designated cold-room rack.</p></section>")
    elif p=="/accession/new":body=_intake_form()
    elif p.startswith("/accession/"):body=_accession_record(db,p.rsplit("/",1)[-1])
    else:body=None
   self._send(404,b"Not found") if body is None else self._send(200,body)
  def do_POST(self):
   try:
    n=int(self.headers.get("Content-Length","0"));d={k:v[0].strip() for k,v in parse_qs(self.rfile.read(n).decode(),keep_blank_values=True).items()}
   except (ValueError,UnicodeDecodeError):self._send(400,b"Invalid form");return
   p=urlparse(self.path).path
   with _db(dbfile) as db:
    if p=="/batch-review" and d.get("disposition") and d.get("note"):
     db.execute("INSERT INTO batch_reviews(batch_id,disposition,note,created_utc) VALUES('B-615',?,?,?)",(d['disposition'],d['note'],datetime.now(timezone.utc).isoformat()));db.execute("UPDATE qc_batches SET status=? WHERE batch_id='B-615'",(d['disposition'],));db.commit()
     self._send(200,_layout("Disposition saved","<p class='notice'>Batch disposition saved.</p><h1>Batch review complete</h1><p>No sample results were released.</p>"));return
    keys=("accession_id","collection_date","sample_type","collection_site","coc_id","storage_location")
    if p=="/accession/new" and all(d.get(k) for k in keys):
     db.execute("INSERT INTO accessions(accession_id,collection_date,sample_type,collection_site,coc_id,storage_location,created_utc) VALUES(?,?,?,?,?,?,?)",tuple(d[k] for k in keys)+(datetime.now(timezone.utc).isoformat(),));db.commit()
     self._send(200,_layout("Accession saved",f"<p class='notice'>Accession {html.escape(d['accession_id'])} saved.</p><h1>Accession confirmation</h1><p>{html.escape(d['sample_type'])} · {html.escape(d['collection_site'])} · {html.escape(d['storage_location'])}</p><a href='/accession/{html.escape(d['accession_id'])}'>Review saved accession</a>"));return
   self._send(404,b"Not found")
 server=ThreadingHTTPServer((host,port),H);server.daemon_threads=True;return server

def user_actions():
 from oscombo.human_actor import GUIAction
 return [
  GUIAction("open_accession_queue","pyautogui.click(398,204)",APP_TITLE,0.8),
  GUIAction("open_sample_receipt","pyautogui.click(843,366)",APP_TITLE,4.0),
  GUIAction("inspect_receipt_fields","pyautogui.moveTo(1758,900)",APP_TITLE,7.0),
  GUIAction("open_intake_guide","pyautogui.click(534,204)",APP_TITLE,4.0),
  GUIAction("read_chain_of_custody_steps","pyautogui.moveTo(1758,950); pyautogui.scroll(-2)",APP_TITLE,9.0),
  GUIAction("return_to_receipt","pyautogui.hotkey('alt','left')",APP_TITLE,5.0),
  GUIAction("open_new_accession_form","pyautogui.click(492,662)",APP_TITLE,4.0),
  GUIAction("enter_accession_id","pyautogui.click(984,436); pyautogui.hotkey('ctrl','a'); pyautogui.write('AC-508',interval=0.1)",APP_TITLE,3.0),
  GUIAction("enter_collection_date","pyautogui.click(600,523); pyautogui.write('10112026',interval=0.15)",APP_TITLE,4.0),
  GUIAction("select_sample_type","pyautogui.click(984,609); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')",APP_TITLE,3.0),
  GUIAction("enter_collection_site","pyautogui.click(984,692); pyautogui.write('North Meadow station NM-2',interval=0.06)",APP_TITLE,3.0),
  GUIAction("enter_coc_and_storage","pyautogui.click(984,778); pyautogui.write('COC-8841',interval=0.08); pyautogui.click(984,863); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')",APP_TITLE,4.0),
  GUIAction("save_accession","pyautogui.click(563,915)",APP_TITLE,2.0),
  GUIAction("review_confirmation","pyautogui.moveTo(1547,900)",APP_TITLE,5.0),
  GUIAction("reopen_accession_queue","pyautogui.click(398,204)",APP_TITLE,1.5),
  GUIAction("open_saved_accession_record","pyautogui.click(996,411)",APP_TITLE,4.0),
  GUIAction("verify_persisted_accession","pyautogui.moveTo(1547,900)",APP_TITLE,5.0),
 ]
