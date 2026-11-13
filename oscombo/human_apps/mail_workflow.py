"""Offline shared-mailbox fixture; oracle is only callable after GUI actors stop."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

FIXTURE_ID = "shared-mailbox-customer-review-and-ops-reply-v1"
CASE_ID = "ha-mail-review-normal-user-v1"
CUSTOMER_THREAD = "CUST-2048"
USER_THREAD = "OPS-117"
CUSTOMER_EMAIL = "casey.rivera@customer.test"
OPS_EMAIL = "ops-oncall@company.test"
USER_REPLY = "I can cover 14:00-16:00 today; please assign me the queue."
_POLICY = ("Warranty and Delivery-Damage Playbook POL-WAR-3",
 "For a product within its active warranty, verified physical damage during carrier delivery is eligible for a replacement. Classify verified delivery damage as P2. Do not promise a refund unless separately approved. After a replacement is approved, dispatch is normally within two business days; tracking details follow dispatch.")
_THREADS = {
 CUSTOMER_THREAD:{"subject":"Damaged dock on order SO-7718","sender":"Casey Rivera <casey.rivera@customer.test>","recipient":"support@northstar.test","summary":"Customer reports a damaged USB-C dock delivered yesterday.","kind":"customer"},
 USER_THREAD:{"subject":"Afternoon queue coverage","sender":"Ops On-call <ops-oncall@company.test>","recipient":"team-ops@company.test","summary":"Please confirm whether you can cover the afternoon queue today.","kind":"internal"},
}
_MESSAGES = {
 CUSTOMER_THREAD:[
  ("Casey Rivera <casey.rivera@customer.test>","support@northstar.test","The USB-C dock from order SO-7718 arrived with a cracked connector. The carton was dented. Can you help?"),
  ("Warehouse Desk <warehouse@northstar.test>","support@northstar.test","Delivery record DLV-7718 confirms carrier impact on 2026-11-09. The dock housing and connector were visibly cracked at delivery."),
  ("Service Desk <service@northstar.test>","support@northstar.test","Order SO-7718 was delivered yesterday. The device serial is NS-DK-2208; no replacement has been issued."),
 ],
 USER_THREAD:[("Ops On-call <ops-oncall@company.test>","team-ops@company.test","Could someone confirm coverage for the afternoon support queue today? Please reply with the time window so I can finish the rota.")],
}
_USER_EXPECTED={"thread_id":USER_THREAD,"recipient":OPS_EMAIL,"body":USER_REPLY}

def _canonical(value:Any)->bytes:
 return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def _source_digest(db:sqlite3.Connection)->str:
 payload={"threads":[tuple(r) for r in db.execute("SELECT thread_id,subject,sender,recipient,summary,kind FROM threads ORDER BY thread_id")],
  "messages":[tuple(r) for r in db.execute("SELECT thread_id,sender,recipient,body FROM messages ORDER BY thread_id,sequence")],
  "policy":[tuple(r) for r in db.execute("SELECT policy_id,title,body FROM policies ORDER BY policy_id")]}
 return hashlib.sha256(_canonical(payload)).hexdigest()
def create_fixture(db_path:str|Path,run_id:str)->dict[str,Any]:
 path=Path(db_path);path.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(path) as db:
  db.executescript("""
  DROP TABLE IF EXISTS request_log; DROP TABLE IF EXISTS sent_messages; DROP TABLE IF EXISTS drafts;
  DROP TABLE IF EXISTS reviews; DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS threads;
  DROP TABLE IF EXISTS policies; DROP TABLE IF EXISTS run_meta;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE threads(thread_id TEXT PRIMARY KEY,subject TEXT NOT NULL,sender TEXT NOT NULL,recipient TEXT NOT NULL,
   summary TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',label TEXT NOT NULL DEFAULT '',priority TEXT NOT NULL DEFAULT '');
  CREATE TABLE messages(sequence INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,sender TEXT NOT NULL,recipient TEXT NOT NULL,body TEXT NOT NULL);
  CREATE TABLE policies(policy_id TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL);
  CREATE TABLE reviews(sequence INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,label TEXT NOT NULL,priority TEXT NOT NULL,created_utc TEXT NOT NULL);
  CREATE TABLE drafts(sequence INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,created_utc TEXT NOT NULL);
  CREATE TABLE sent_messages(sequence INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT NOT NULL,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,created_utc TEXT NOT NULL);
  CREATE TABLE request_log(sequence INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT NOT NULL,path TEXT NOT NULL,status INTEGER NOT NULL,received_utc TEXT NOT NULL);
  """)
  db.execute("INSERT INTO run_meta VALUES('run_id',?)",(str(run_id),));db.execute("INSERT INTO run_meta VALUES('fixture_id',?)",(FIXTURE_ID,))
  for tid,t in _THREADS.items():
   db.execute("INSERT INTO threads(thread_id,subject,sender,recipient,summary,kind) VALUES(?,?,?,?,?,?)",(tid,t["subject"],t["sender"],t["recipient"],t["summary"],t["kind"]))
   for sender,recipient,body in _MESSAGES[tid]:db.execute("INSERT INTO messages(thread_id,sender,recipient,body) VALUES(?,?,?,?)",(tid,sender,recipient,body))
  db.execute("INSERT INTO policies VALUES('POL-WAR-3',?,?)",_POLICY);digest=_source_digest(db)
  db.execute("INSERT INTO run_meta VALUES('source_sha256',?)",(digest,));db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,
  "initial_state":{"thread_ids":sorted(_THREADS),"review_count":0,"draft_count":0,"sent_count":0,"thread_statuses":{k:"open" for k in sorted(_THREADS)}},"source_content_sha256":digest}
 manifest={**public,"sha256":hashlib.sha256(_canonical(public)).hexdigest()}
 path.with_suffix(path.suffix+".fixture.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 return manifest
def _rows(db:sqlite3.Connection,query:str,args:tuple[Any,...]=())->list[dict[str,Any]]:
 db.row_factory=sqlite3.Row;return [dict(r) for r in db.execute(query,args)]
def evaluate_agent(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;meta=dict(db.execute("SELECT key,value FROM run_meta"))
   reviews=_rows(db,"SELECT * FROM reviews WHERE thread_id=? ORDER BY sequence",(CUSTOMER_THREAD,))
   drafts=_rows(db,"SELECT * FROM drafts WHERE thread_id=? ORDER BY sequence",(CUSTOMER_THREAD,))
   sent=_rows(db,"SELECT * FROM sent_messages WHERE thread_id=?",(CUSTOMER_THREAD,))
   customer=db.execute("SELECT * FROM threads WHERE thread_id=?",(CUSTOMER_THREAD,)).fetchone()
   logs=_rows(db,"SELECT * FROM request_log ORDER BY sequence");source_now=_source_digest(db)
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"fixture_integrity":False,"review_saved_once":False}}
 review=reviews[-1] if reviews else None;draft=drafts[-1] if drafts else None
 body=" ".join((draft or {}).get("body","").lower().split());seen={(r["method"],r["path"],r["status"]) for r in logs}
 checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,
  "review_saved_once":len(reviews)==1,
  "correct_thread_label":bool(review and review["label"]=="replacement_eligible" and customer and customer["label"]=="replacement_eligible"),
  "correct_priority":bool(review and review["priority"]=="P2" and customer and customer["priority"]=="P2"),
  "draft_saved_once":len(drafts)==1,"draft_has_correct_recipient":bool(draft and draft["recipient"].lower()==CUSTOMER_EMAIL),
  "draft_subject_matches":bool(draft and draft["subject"].lower().startswith("re: damaged dock")),
  "draft_contains_apology":"sorry" in body,"draft_commits_to_replacement":"replacement" in body,
  "draft_includes_sla":"two business days" in body or "2 business days" in body,
  "draft_not_sent":len(sent)==0,"customer_thread_remains_open":bool(customer and customer["status"]=="open"),
  "customer_thread_and_policy_viewed":all(("GET",p,200) in seen for p in ("/thread/CUST-2048","/policy/POL-WAR-3")),
  "source_records_unchanged":source_now==meta.get("source_sha256")}
 return {"task":"customer-delivery-damage-review-and-draft","success":all(checks.values()),"checks":checks,
  "review_count":len(reviews),"draft_count":len(drafts),"customer_sent_count":len(sent),
  "latest_review":{k:review.get(k) for k in ("thread_id","label","priority")} if review else None,
  "latest_draft":{k:draft.get(k) for k in ("thread_id","recipient","subject","body")} if draft else None,"observed_source_sha256":source_now}
def evaluate_user(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;meta=dict(db.execute("SELECT key,value FROM run_meta"))
   sent=_rows(db,"SELECT * FROM sent_messages WHERE thread_id=? ORDER BY sequence",(USER_THREAD,))
   thread=db.execute("SELECT * FROM threads WHERE thread_id=?",(USER_THREAD,)).fetchone()
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"fixture_integrity":False,"reply_sent_once":False}}
 latest=sent[-1] if sent else None
 checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"reply_sent_once":len(sent)==1,
  "correct_internal_thread":bool(latest and latest["thread_id"]==_USER_EXPECTED["thread_id"]),
  "correct_recipient":bool(latest and latest["recipient"].lower()==_USER_EXPECTED["recipient"]),
  "exact_reply_body":bool(latest and latest["body"].strip()==_USER_EXPECTED["body"]),
  "user_thread_marked_done":bool(thread and thread["status"]=="done")}
 return {"task":"confirm-afternoon-queue-coverage","success":all(checks.values()),"checks":checks,"sent_count":len(sent),
  "latest_sent":{k:latest.get(k) for k in ("thread_id","recipient","subject","body")} if latest else None}
def evaluate(db_path:str|Path)->dict[str,Any]:return {"agent":evaluate_agent(db_path),"user":evaluate_user(db_path)}

def _layout(title:str,content:str)->bytes:
 return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f5f8;color:#17212b;font:16px/1.45 system-ui,sans-serif}}
header{{height:66px;background:#174d72;color:white;padding:16px 34px;font-size:21px;font-weight:650}}
nav{{height:47px;background:#e4edf4;padding:10px 34px;border-bottom:1px solid #c9d4df}}a{{color:#0b5686}}nav a{{margin-right:24px;font-weight:600}}
main{{max-width:1050px;margin:24px auto;padding:0 22px}}h1{{font-size:26px;margin:0 0 16px}}h2{{font-size:20px;margin:0 0 8px}}
.panel,.thread-row,.message,.form-card{{background:white;border:1px solid #cbd6df;border-radius:8px;padding:16px 20px;margin:12px 0}}
.thread-row{{display:block;color:inherit;text-decoration:none;padding:18px 22px}}.thread-row:hover{{background:#f8fbfd}}
.meta{{color:#536779;font-size:14px}}.message{{border-left:4px solid #76a9c9}}.message p{{margin:8px 0}}
.actions{{display:flex;gap:12px;align-items:center;margin:16px 0}}button,.button{{border:0;border-radius:5px;background:#155b89;color:white;padding:10px 18px;font:600 16px system-ui,sans-serif;text-decoration:none;cursor:pointer}}
button.secondary,.button.secondary{{background:#edf3f7;color:#174d72;border:1px solid #aebdca}}label{{display:block;font-weight:650;margin:13px 0 5px}}
input,textarea,select{{width:100%;padding:10px;border:1px solid #9aabba;border-radius:4px;font:16px system-ui,sans-serif;background:#fff}}textarea{{min-height:150px;resize:vertical}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.notice{{border-left:4px solid #298558;background:#e8f5ec;padding:10px 14px}}
</style></head><body><header>CoDesk Mail &nbsp; <span style='font-weight:400'>Northstar Operations</span></header>
<nav><a href='/mail'>Inbox</a><a href='/drafts'>Drafts</a><a href='/sent'>Sent</a><a href='/policy/POL-WAR-3'>Warranty playbook</a></nav><main>{content}</main></body></html>""".encode()
def _inbox_page(db:sqlite3.Connection)->bytes:
 rows=_rows(db,"SELECT * FROM threads ORDER BY CASE kind WHEN 'customer' THEN 0 ELSE 1 END,thread_id")
 cards="".join(f"<a class='thread-row' href='/thread/{html.escape(r['thread_id'])}'><h2>{html.escape(r['subject'])}</h2><div class='meta'>{html.escape(r['sender'])} · {html.escape(r['status'].upper())}</div><p>{html.escape(r['summary'])}</p></a>" for r in rows)
 return _layout("CoDesk Mail - Inbox",f"<h1>Inbox</h1><p>Shared mailbox · 2 conversations</p>{cards}")
def _thread_page(db:sqlite3.Connection,thread_id:str,notice:str="")->bytes|None:
 row=db.execute("SELECT * FROM threads WHERE thread_id=?",(thread_id,)).fetchone()
 if row is None:return None
 messages=_rows(db,"SELECT * FROM messages WHERE thread_id=? ORDER BY sequence",(thread_id,))
 cards="".join(f"<section class='message'><div class='meta'>{html.escape(m['sender'])} → {html.escape(m['recipient'])}</div><p>{html.escape(m['body'])}</p></section>" for m in messages)
 internal=""
 if thread_id==CUSTOMER_THREAD:
  internal=f"""<form class='form-card' method='post' action='/review'><input type='hidden' name='thread_id' value='{CUSTOMER_THREAD}'><h2>Internal review</h2>
<div class='grid'><div><label for='label'>Case label</label><select id='label' name='label'><option value=''>Choose a label</option><option value='replacement_eligible'>Replacement eligible</option><option value='refund_review'>Refund review</option><option value='request_evidence'>Request more evidence</option></select></div>
<div><label for='priority'>Priority</label><select id='priority' name='priority'><option value=''>Choose priority</option><option value='P1'>P1 · Urgent</option><option value='P2'>P2 · Standard elevated</option><option value='P3'>P3 · Routine</option></select></div></div><button type='submit'>Save review</button></form>"""
 mark=""
 if thread_id==USER_THREAD:mark=f"<form method='post' action='/thread/done'><input type='hidden' name='thread_id' value='{USER_THREAD}'><button class='secondary' type='submit'>Mark as done</button></form>"
 content=f"<div class='meta'><a href='/mail'>‹ Back to Inbox</a></div><h1>{html.escape(row['subject'])}</h1><p class='meta'>Thread {html.escape(thread_id)} · {html.escape(row['sender'])}</p>{notice}{cards}<div class='actions'><a class='button' href='/reply?thread_id={html.escape(thread_id)}'>Reply</a>{mark}</div>{internal}"
 return _layout(f"CoDesk Mail - {row['subject']}",content)
def _compose_page(db:sqlite3.Connection,thread_id:str,notice:str="")->bytes|None:
 row=db.execute("SELECT * FROM threads WHERE thread_id=?",(thread_id,)).fetchone()
 if row is None:return None
 recipient=row["sender"].split("<")[-1].rstrip("> ")
 subject=row["subject"] if row["subject"].lower().startswith("re:") else "Re: "+row["subject"]
 content=f"""<div class='meta'><a href='/thread/{html.escape(thread_id)}'>‹ Back to conversation</a></div><h1>Reply</h1>
<div class='meta'>Replying in thread {html.escape(thread_id)}</div>{notice}<form class='form-card' method='post' action='/reply/submit'>
<input type='hidden' name='thread_id' value='{html.escape(thread_id)}'><label for='to'>To</label><input id='to' name='recipient' value='{html.escape(recipient,quote=True)}' required>
<label for='subject'>Subject</label><input id='subject' name='subject' value='{html.escape(subject,quote=True)}' required>
<label for='body'>Message</label><textarea id='body' name='body' autofocus required></textarea>
<div class='actions'><button class='secondary' type='submit' name='action' value='draft'>Save draft</button><button type='submit' name='action' value='send'>Send reply</button><a class='button secondary' href='/mail'>Discard</a></div></form>"""
 return _layout("CoDesk Mail - Reply",content)
def make_server(db_path:str|Path,host:str="127.0.0.1",port:int=0)->ThreadingHTTPServer:
 dbfile=str(Path(db_path))
 class Handler(BaseHTTPRequestHandler):
  server_version="CoDeskOfflineMail/1.0"
  def log_message(self,fmt:str,*args:Any)->None:
   try:
    with sqlite3.connect(dbfile,timeout=10) as db:
     db.execute("INSERT INTO request_log(method,path,status,received_utc) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,int(getattr(self,"_status",200)),datetime.now(timezone.utc).isoformat()));db.commit()
   except sqlite3.Error:pass
  def _send(self,status:int,body:bytes,content_type:str="text/html; charset=utf-8")->None:
   self._status=status;self.send_response(status);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(body)))
   self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
   self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
   self.end_headers();self.wfile.write(body)
  def do_GET(self)->None:
   parsed=urlparse(self.path);p=parsed.path
   if p=="/healthz":self._send(200,b"ok","text/plain; charset=utf-8");return
   with sqlite3.connect(dbfile) as db:
    db.row_factory=sqlite3.Row
    if p=="/mail":payload=_inbox_page(db)
    elif p.startswith("/thread/"):payload=_thread_page(db,p.rsplit("/",1)[-1])
    elif p=="/policy/POL-WAR-3":
     title,body=_POLICY;payload=_layout(title,f"<div class='meta'><a href='/mail'>‹ Back to Inbox</a></div><h1>{html.escape(title)}</h1><div class='panel'><p>{html.escape(body)}</p><p>Reference: POL-WAR-3</p></div>")
    elif p=="/reply":payload=_compose_page(db,parse_qs(parsed.query).get("thread_id",[""])[0])
    elif p in {"/drafts","/sent"}:
     table="drafts" if p=="/drafts" else "sent_messages";rows=_rows(db,f"SELECT * FROM {table} ORDER BY sequence DESC")
     cards="".join(f"<section class='panel'><h2>{html.escape(r['subject'])}</h2><p>Thread {html.escape(r['thread_id'])} · To {html.escape(r['recipient'])}</p><p>{html.escape(r['body'])}</p></section>" for r in rows)
     payload=_layout("CoDesk Mail - "+table.title(),f"<h1>{table.title()}</h1>{cards or '<p>No messages.</p>'}")
    else:payload=None
   self._send(404,b"Not found","text/plain; charset=utf-8") if payload is None else self._send(200,payload)
  def do_POST(self)->None:
   try:
    n=int(self.headers.get("Content-Length","0"))
    if n<=0 or n>16000:raise ValueError("invalid form size")
    q=parse_qs(self.rfile.read(n).decode("utf-8"),keep_blank_values=True);d={k:q.get(k,[""])[0].strip() for k in ("thread_id","label","priority","recipient","subject","body","action")}
   except (UnicodeDecodeError,ValueError,KeyError):self._send(400,b"Invalid form submission","text/plain; charset=utf-8");return
   p=urlparse(self.path).path
   with sqlite3.connect(dbfile,timeout=10) as db:
    db.row_factory=sqlite3.Row
    if p=="/review" and d["thread_id"]==CUSTOMER_THREAD and d["label"] and d["priority"]:
     now=datetime.now(timezone.utc).isoformat();db.execute("INSERT INTO reviews(thread_id,label,priority,created_utc) VALUES(?,?,?,?)",(d["thread_id"],d["label"],d["priority"],now))
     db.execute("UPDATE threads SET label=?,priority=? WHERE thread_id=?",(d["label"],d["priority"],d["thread_id"]));db.commit()
     self._send(200,_thread_page(db,CUSTOMER_THREAD,"<p class='notice'>Review saved.</p>") or b"Not found");return
    if p=="/reply/submit":
     tid=d["thread_id"];exists=db.execute("SELECT 1 FROM threads WHERE thread_id=?",(tid,)).fetchone()
     if not exists or not all(d[k] for k in ("recipient","subject","body")):self._send(400,b"Complete the reply fields","text/plain; charset=utf-8");return
     now=datetime.now(timezone.utc).isoformat()
     if d["action"]=="send":
      db.execute("INSERT INTO sent_messages(thread_id,recipient,subject,body,created_utc) VALUES(?,?,?,?,?)",(tid,d["recipient"],d["subject"],d["body"],now));db.commit()
      notice="<p class='notice'>Reply sent.</p>"
      self._send(200,_thread_page(db,tid,notice) or b"Not found");return
     if d["action"]=="draft":
      db.execute("INSERT INTO drafts(thread_id,recipient,subject,body,created_utc) VALUES(?,?,?,?,?)",(tid,d["recipient"],d["subject"],d["body"],now));db.commit()
      notice="<p class='notice'>Draft saved.</p>"
      self._send(200,_compose_page(db,tid,notice) or b"Not found");return
     self._send(400,b"Choose Send reply or Save draft","text/plain; charset=utf-8");return
    if p=="/thread/done" and d["thread_id"]==USER_THREAD:
     db.execute("UPDATE threads SET status='done' WHERE thread_id=?",(USER_THREAD,));db.commit()
     self._send(200,_thread_page(db,USER_THREAD,"<p class='notice'>Conversation marked done.</p>") or b"Not found");return
   self._send(404,b"Not found","text/plain; charset=utf-8")
 server=ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True;return server