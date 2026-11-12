"""Offline shared-calendar fixture for the Human-Agent normal-user pilot."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

CASE_ID = "ha-calendar-meeting-focus-v1"
CASE_VERSION = "0.1.0"
FIXTURE_ID = "project-meeting-and-personal-focus-calendar-v1"
AGENT_EVENT = "Release Readiness Review"
USER_EVENT = "Finalize November report"
AGENT_DATE, AGENT_START, AGENT_END, AGENT_ROOM = "2026-11-17", "10:30", "11:00", "Cedar 2"
USER_DATE, USER_START, USER_END, USER_REMINDER = "2026-11-20", "13:00", "13:45", "10"
_CALENDARS = [("team","Project Team"),("personal","Personal")]
_PARTICIPANTS = ("Ava Chen","Eli Brooks","Mina Patel")
_AVAILABILITY = [
 ("Ava Chen","Tue Nov 17","09:30-11:30","Available"),("Ava Chen","Wed Nov 18","14:00-16:00","Available"),
 ("Eli Brooks","Tue Nov 17","10:00-11:00","Available"),("Eli Brooks","Wed Nov 18","15:30-16:00","Available"),
 ("Mina Patel","Tue Nov 17","10:30-11:30","Available"),("Mina Patel","Wed Nov 18","14:00-15:00","Available")]
_ROOMS = [("Cedar 2",4,"Tue Nov 17","10:30-11:30","Available"),("Cedar 2",4,"Wed Nov 18","14:00-14:30","Available"),
 ("Oak 1",8,"Tue Nov 17","09:00-10:30","Available"),("Oak 1",8,"Wed Nov 18","14:00-16:00","Available")]

def _canonical(value: Any) -> bytes:
 return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def _source_payload(db: sqlite3.Connection) -> dict[str,Any]:
 return {"calendars":[tuple(r) for r in db.execute("SELECT calendar_id,name FROM calendars ORDER BY calendar_id")],
  "availability":[tuple(r) for r in db.execute("SELECT person,day,time_range,status FROM availability ORDER BY person,day,time_range")],
  "rooms":[tuple(r) for r in db.execute("SELECT room,capacity,day,time_range,status FROM room_windows ORDER BY room,day,time_range")],
  "brief":[tuple(r) for r in db.execute("SELECT key,value FROM meeting_brief ORDER BY key")]}
def _source_digest(db: sqlite3.Connection) -> str:
 return hashlib.sha256(_canonical(_source_payload(db))).hexdigest()
def create_fixture(db_path: str|Path,run_id: str) -> dict[str,Any]:
 path=Path(db_path);path.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(path) as db:
  db.executescript("""
  DROP TABLE IF EXISTS request_log; DROP TABLE IF EXISTS events; DROP TABLE IF EXISTS calendars;
  DROP TABLE IF EXISTS availability; DROP TABLE IF EXISTS room_windows; DROP TABLE IF EXISTS meeting_brief; DROP TABLE IF EXISTS run_meta;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE calendars(calendar_id TEXT PRIMARY KEY,name TEXT NOT NULL);
  CREATE TABLE availability(person TEXT NOT NULL,day TEXT NOT NULL,time_range TEXT NOT NULL,status TEXT NOT NULL);
  CREATE TABLE room_windows(room TEXT NOT NULL,capacity INTEGER NOT NULL,day TEXT NOT NULL,time_range TEXT NOT NULL,status TEXT NOT NULL);
  CREATE TABLE meeting_brief(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,calendar_id TEXT NOT NULL,title TEXT NOT NULL,event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,end_time TEXT NOT NULL,attendees TEXT NOT NULL,room TEXT NOT NULL,agenda TEXT NOT NULL,
    reminder_min TEXT NOT NULL,invite_status TEXT NOT NULL,created_utc TEXT NOT NULL);
  CREATE TABLE request_log(sequence INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT NOT NULL,path TEXT NOT NULL,status INTEGER NOT NULL,received_utc TEXT NOT NULL);
  """)
  db.execute("INSERT INTO run_meta VALUES('run_id',?)",(str(run_id),));db.execute("INSERT INTO run_meta VALUES('fixture_id',?)",(FIXTURE_ID,))
  db.executemany("INSERT INTO calendars VALUES(?,?)",_CALENDARS);db.executemany("INSERT INTO availability VALUES(?,?,?,?)",_AVAILABILITY)
  db.executemany("INSERT INTO room_windows VALUES(?,?,?,?,?)",_ROOMS)
  brief=[("title","Release Readiness Review"),("duration_min","30"),("participants",", ".join(_PARTICIPANTS)),
   ("room_capacity_required","4"),("agenda","Review blockers, assign owners, and confirm go/no-go criteria."),("invite_status","draft")]
  db.executemany("INSERT INTO meeting_brief VALUES(?,?)",brief)
  digest=_source_digest(db);db.execute("INSERT INTO run_meta VALUES('source_sha256',?)",(digest,));db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,"initial_state":{"calendars":["personal","team"],"event_count":0},"source_content_sha256":digest}
 manifest={**public,"sha256":hashlib.sha256(_canonical(public)).hexdigest()}
 path.with_suffix(path.suffix+".fixture.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 return manifest
def _rows(db:sqlite3.Connection,q:str,args:tuple[Any,...]=())->list[dict[str,Any]]:
 db.row_factory=sqlite3.Row;return [dict(r) for r in db.execute(q,args)]
def evaluate_agent(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;meta=dict(db.execute("SELECT key,value FROM run_meta"))
   events=_rows(db,"SELECT * FROM events WHERE title=? ORDER BY event_id",(AGENT_EVENT,))
   logs=_rows(db,"SELECT * FROM request_log ORDER BY sequence");source_hash=_source_digest(db)
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"fixture_integrity":False,"event_saved_once":False}}
 event=events[-1] if events else None;seen={(r["method"],urlparse(r["path"]).path,r["status"]) for r in logs}
 attendees={x.strip() for x in (event or {}).get("attendees","").split(",") if x.strip()};agenda=(event or {}).get("agenda","").lower()
 checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"event_saved_once":len(events)==1,
  "correct_calendar":bool(event and event["calendar_id"]=="team"),
  "correct_time_and_duration":bool(event and event["event_date"]==AGENT_DATE and event["start_time"]==AGENT_START and event["end_time"]==AGENT_END),
  "correct_room":bool(event and event["room"]==AGENT_ROOM),"all_attendees":attendees==set(_PARTICIPANTS),
  "agenda_covers_decisions":all(x in agenda for x in ("blockers","owners","go/no-go")),
  "invite_left_as_draft":bool(event and event["invite_status"]=="draft"),
  "availability_and_rooms_viewed":all(("GET",p,200) in seen for p in ("/availability","/rooms","/brief")),
  "source_records_unchanged":source_hash==meta.get("source_sha256")}
 return {"task":"schedule-release-readiness-review","success":all(checks.values()),"checks":checks,"event_count":len(events),
  "latest_event":{k:event.get(k) for k in ("calendar_id","title","event_date","start_time","end_time","attendees","room","agenda","invite_status")} if event else None,
  "observed_source_sha256":source_hash}
def evaluate_user(db_path:str|Path)->dict[str,Any]:
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;meta=dict(db.execute("SELECT key,value FROM run_meta"))
   events=_rows(db,"SELECT * FROM events WHERE title=? ORDER BY event_id",(USER_EVENT,));logs=_rows(db,"SELECT * FROM request_log ORDER BY sequence")
   wrong=_rows(db,"SELECT * FROM events WHERE title=? AND calendar_id='team'",(USER_EVENT,))
 except (OSError,sqlite3.Error):return {"success":False,"checks":{"fixture_integrity":False,"event_saved_once":False}}
 event=events[-1] if events else None;seen={(r["method"],urlparse(r["path"]).path,r["status"]) for r in logs}
 checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"event_saved_once":len(events)==1,
  "correct_calendar":bool(event and event["calendar_id"]=="personal"),
  "correct_date_and_time":bool(event and event["event_date"]==USER_DATE and event["start_time"]==USER_START and event["end_time"]==USER_END),
  "correct_reminder":bool(event and event["reminder_min"]==USER_REMINDER),"no_invitation":bool(event and event["invite_status"]=="none"),
  "no_wrong_calendar_copy":len(wrong)==0,"week_viewed":("GET","/calendar",200) in seen}
 return {"task":"add-personal-focus-block","success":all(checks.values()),"checks":checks,"event_count":len(events),
  "latest_event":{k:event.get(k) for k in ("calendar_id","title","event_date","start_time","end_time","reminder_min","invite_status")} if event else None}
def evaluate(db_path:str|Path)->dict[str,Any]:return {"agent":evaluate_agent(db_path),"user":evaluate_user(db_path)}
def _page(title:str,content:str)->bytes:
 css="""*{box-sizing:border-box}body{margin:0;background:#f1f4f7;color:#17222d;font:16px/1.4 system-ui,sans-serif}
 header{background:#234f75;color:white;padding:16px 30px;font-size:22px;font-weight:650}nav{background:#e5edf4;padding:10px 30px;border-bottom:1px solid #bdcad6}
 nav a{margin-right:24px;color:#124f7c;font-weight:600}main{max-width:1120px;margin:24px auto;padding:0 24px}.panel{background:white;border:1px solid #c8d2dc;border-radius:8px;padding:16px 20px;margin:12px 0}
 h1{font-size:26px;margin:4px 0 14px}h2{font-size:20px;margin:0 0 10px}.muted{color:#526779}
 .grid{display:grid;grid-template-columns:130px repeat(5,minmax(120px,1fr));gap:6px}.cell{min-height:65px;border:1px solid #d1dae2;border-radius:5px;background:white;padding:7px}
 .head{background:#eaf0f5;font-weight:650}button,.button{display:inline-block;border:0;border-radius:5px;background:#155c8b;color:white;padding:10px 16px;font:600 16px system-ui,sans-serif;text-decoration:none;cursor:pointer}
 .secondary{background:#eef3f7!important;color:#174d72!important;border:1px solid #afbfcc}label{display:block;font-weight:650;margin:12px 0 4px}
 input,select,textarea{width:100%;padding:9px;border:1px solid #9cabb8;border-radius:4px;font:16px system-ui,sans-serif}textarea{min-height:95px;resize:vertical}
 .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.toolbar{display:flex;gap:10px;align-items:center;margin:14px 0}
 .notice{background:#e8f5ec;border-left:4px solid #298558;padding:10px 14px}.event-chip{background:#d9eaf7;border-left:3px solid #2473a4;padding:4px 6px;border-radius:3px;font-size:13px}
 table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #ccd5de;padding:9px;text-align:left}"""
 return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{css}</style></head><body><header>CoDesk Calendar <span style='font-weight:400'>· Northstar Workspace</span></header><nav><a href='/calendar'>Week view</a><a href='/brief'>Meeting brief</a><a href='/availability'>Availability</a><a href='/rooms'>Rooms</a><a href='/event/new'>New event</a></nav><main>{content}</main></body></html>".encode()
def _calendar_page(db:sqlite3.Connection,notice:str="")->bytes:
 items=_rows(db,"SELECT * FROM events ORDER BY event_date,start_time")
 chips="".join(f"<div class='event-chip'><b>{html.escape(r['calendar_id'].title())}</b> · {html.escape(r['title'])} · {html.escape(r['start_time'])}</div>" for r in items)
 content=f"""<h1>Week of November 16–20, 2026</h1><p class='muted'>Time zone: Eastern Time · Working hours 09:00–17:00</p>
 <div class='toolbar'><a class='button' href='/event/new'>New event</a><a class='button secondary' href='/availability'>Check availability</a></div>{notice}
 <div class='grid'><div class='cell head'>Time</div><div class='cell head'>Mon 16</div><div class='cell head'>Tue 17</div><div class='cell head'>Wed 18</div><div class='cell head'>Thu 19</div><div class='cell head'>Fri 20</div>
 <div class='cell head'>09:00–12:00</div><div class='cell'>—</div><div class='cell'>{chips if any(r['event_date']==AGENT_DATE and r['start_time']<'12:00' for r in items) else '—'}</div><div class='cell'>—</div><div class='cell'>—</div><div class='cell'>—</div>
 <div class='cell head'>12:00–17:00</div><div class='cell'>—</div><div class='cell'>—</div><div class='cell'>—</div><div class='cell'>—</div><div class='cell'>{chips if any(r['event_date']==USER_DATE and r['start_time']>='12:00' for r in items) else '—'}</div></div>
 <div class='panel'><h2>Calendars</h2><span class='event-chip'>Project Team</span> <span class='event-chip'>Personal</span><p class='muted'>Select a calendar when creating an event.</p></div>"""
 return _page("CoDesk Calendar - Week view",content)
def _table_page(title:str,heading:str,rows:list[tuple[Any,...]],headers:tuple[str,...])->bytes:
 head="".join(f"<th>{html.escape(str(h))}</th>" for h in headers);body="".join("<tr>"+"".join(f"<td>{html.escape(str(v))}</td>" for v in row)+"</tr>" for row in rows)
 return _page(title,f"<h1>{html.escape(heading)}</h1><div class='panel'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")
def _new_event_page()->bytes:
 content="""<div class='muted'><a href='/calendar'>‹ Back to week</a></div><h1>New event</h1>
 <form class='panel' method='post' action='/event/save'><label for='calendar'>Calendar</label><select id='calendar' name='calendar_id' required><option value='team'>Project Team</option><option value='personal'>Personal</option></select>
 <label for='title'>Title</label><input id='title' name='title' required><div class='form-grid'><div><label for='date'>Date</label><input id='date' name='event_date' placeholder='YYYY-MM-DD' required></div><div><label for='room'>Room (optional)</label><input id='room' name='room'></div></div>
 <div class='form-grid'><div><label for='start'>Start time</label><input id='start' name='start_time' placeholder='HH:MM' required></div><div><label for='end'>End time</label><input id='end' name='end_time' placeholder='HH:MM' required></div></div>
 <label for='attendees'>Guests (comma separated)</label><input id='attendees' name='attendees' placeholder='Name, Name'><label for='agenda'>Agenda / notes</label><textarea id='agenda' name='agenda'></textarea>
 <div class='form-grid'><div><label for='reminder'>Reminder</label><select id='reminder' name='reminder_min'><option value='none'>No reminder</option><option value='10'>10 minutes before</option><option value='15'>15 minutes before</option><option value='30'>30 minutes before</option></select></div>
 <div><label for='invite'>Invitation status</label><select id='invite' name='invite_status'><option value='none'>No invitation</option><option value='draft'>Save invitation as draft</option><option value='send'>Send invitation</option></select></div></div>
 <div class='toolbar'><button type='submit'>Save event</button><a class='button secondary' href='/calendar'>Cancel</a></div></form>"""
 return _page("CoDesk Calendar - New event",content)
def make_server(db_path:str|Path,host:str="127.0.0.1",port:int=0)->ThreadingHTTPServer:
 dbfile=str(Path(db_path))
 class Handler(BaseHTTPRequestHandler):
  server_version="CoDeskOfflineCalendar/1.0"
  def log_message(self,fmt:str,*args:Any)->None:
   try:
    with sqlite3.connect(dbfile,timeout=10) as db:
     db.execute("INSERT INTO request_log(method,path,status,received_utc) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,int(getattr(self,"_status",200)),datetime.now(timezone.utc).isoformat()));db.commit()
   except sqlite3.Error:pass
  def _send(self,status:int,body:bytes,ctype:str="text/html; charset=utf-8")->None:
   self._status=status;self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)))
   self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
   self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
   self.end_headers();self.wfile.write(body)
  def do_GET(self)->None:
   p=urlparse(self.path).path
   if p=="/healthz":self._send(200,b"ok","text/plain; charset=utf-8");return
   with sqlite3.connect(dbfile) as db:
    db.row_factory=sqlite3.Row
    if p=="/calendar":payload=_calendar_page(db)
    elif p=="/brief":payload=_page("Meeting brief","<h1>Release readiness brief</h1><div class='panel'><p>Create a 30-minute 'Release Readiness Review' on the week of Nov 16–20.</p><p>Invite Ava Chen, Eli Brooks, and Mina Patel. Use the Project Team calendar. An organizer plus these three guests requires room capacity for at least four people.</p><p>Include an agenda to review blockers, assign owners, and confirm go/no-go criteria. Save the invitation as a draft; do not send it.</p></div>")
    elif p=="/availability":
     rows=_rows(db,"SELECT person,day,time_range,status FROM availability ORDER BY day,person")
     payload=_table_page("Participant availability","Participant availability · Eastern Time",[tuple(r[k] for k in ("person","day","time_range","status")) for r in rows],("Participant","Day","Available window","Status"))
    elif p=="/rooms":
     rows=_rows(db,"SELECT room,capacity,day,time_range,status FROM room_windows ORDER BY day,room,time_range")
     payload=_table_page("Room availability","Room capacity and availability",[tuple(r[k] for k in ("room","capacity","day","time_range","status")) for r in rows],("Room","Seats","Day","Available window","Status"))
    elif p=="/event/new":payload=_new_event_page()
    else:payload=None
   self._send(404,b"Not found","text/plain; charset=utf-8") if payload is None else self._send(200,payload)
  def do_POST(self)->None:
   if urlparse(self.path).path!="/event/save":self._send(404,b"Not found","text/plain");return
   try:
    n=int(self.headers.get("Content-Length","0"))
    if n<=0 or n>16000:raise ValueError()
    q=parse_qs(self.rfile.read(n).decode("utf-8"),keep_blank_values=True)
    f={k:q.get(k,[""])[0].strip() for k in ("calendar_id","title","event_date","start_time","end_time","room","attendees","agenda","reminder_min","invite_status")}
    if f["calendar_id"] not in {"team","personal"} or not all(f[k] for k in ("title","event_date","start_time","end_time")):raise ValueError()
    datetime.strptime(f["event_date"],"%Y-%m-%d");datetime.strptime(f["start_time"],"%H:%M");datetime.strptime(f["end_time"],"%H:%M")
    if f["start_time"]>=f["end_time"] or f["invite_status"] not in {"none","draft","send"} or f["reminder_min"] not in {"none","10","15","30"}:raise ValueError()
   except (UnicodeDecodeError,ValueError):self._send(400,b"Complete fields with shown date/time formats.","text/plain");return
   with sqlite3.connect(dbfile,timeout=10) as db:
    db.execute("INSERT INTO events(calendar_id,title,event_date,start_time,end_time,attendees,room,agenda,reminder_min,invite_status,created_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
     (f["calendar_id"],f["title"],f["event_date"],f["start_time"],f["end_time"],f["attendees"],f["room"],f["agenda"],f["reminder_min"],f["invite_status"],datetime.now(timezone.utc).isoformat()))
    db.commit();payload=_calendar_page(db,"<p class='notice'>Event saved.</p>")
   self._send(200,payload)
 return ThreadingHTTPServer((host,port),Handler)
