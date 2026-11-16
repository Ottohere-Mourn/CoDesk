"""Offline accessible-transit itinerary fixture for the human-agent benchmark."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CASE_ID="ha-transit-itinerary-v1"
CASE_VERSION="0.2.2"
FIXTURE_ID="accessible-museum-trip-v3"
AGENT_TASK="""In CoDesk Transit Planner, build and save a draft accessible trip plan for Thursday 19 November 2026: travel from Oak Wharf to Civic Museum, arrive no later than 10:15, and require step-free access for the whole trip. Inspect the network options, service disruptions, and step-free guidance before choosing a route. Save the plan as 'Museum visit - accessible route'. Do not book or pay for tickets. Use the visible GUI only; do not use shell or hidden evaluator state."""
USER_TASK="""Prepare Riverside Park as a regular accessible transfer stop. Review the route options and service alert, check the Riverside Park station's step-free platform and entrance/help-point details, then save Riverside Park to your Personal list. Review the confirmation, reopen Saved places, and verify the saved station."""
USER_FAVORITE="Riverside Park"
def _canon(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def create_fixture(db_path,run_id):
 p=Path(db_path);p.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(p) as db:
  db.executescript("""DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS itineraries;DROP TABLE IF EXISTS favorites;DROP TABLE IF EXISTS run_meta;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);
  CREATE TABLE itineraries(seq INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,travel_date TEXT,origin TEXT,destination TEXT,route_code TEXT,departure TEXT,arrive_by TEXT,step_free INTEGER,note TEXT,ticket_booked INTEGER DEFAULT 0);
  CREATE TABLE favorites(seq INTEGER PRIMARY KEY AUTOINCREMENT,station TEXT,list_name TEXT,created_utc TEXT);
  """)
  db.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",FIXTURE_ID)]);db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,
         "initial_state":{"itinerary_count":0,"favorite_count":0}}
 return {**public,"sha256":hashlib.sha256(_canon(public)).hexdigest()}

def evaluate(db_path):
 try:
  with sqlite3.connect(db_path) as db:
   db.row_factory=sqlite3.Row;meta=dict(db.execute("SELECT key,value FROM run_meta"))
   plans=[dict(x) for x in db.execute("SELECT * FROM itineraries ORDER BY seq")]
   favs=[dict(x) for x in db.execute("SELECT * FROM favorites ORDER BY seq")]
   request_rows=[dict(x) for x in db.execute("SELECT seq,method,path,status FROM request_log ORDER BY seq")]
   visits={(x["method"],x["path"],x["status"]) for x in request_rows}
 except (OSError,sqlite3.Error):
  return {"agent":{"success":False,"checks":{"fixture_exists":False}},"user":{"success":False,"checks":{"fixture_exists":False}}}
 p=plans[-1] if plans else None;f=favs[-1] if favs else None
 ac={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_draft_plan":len(plans)==1,
  "name_correct":bool(p and p["name"]=="Museum visit - accessible route"),
  "date_correct":bool(p and p["travel_date"]=="2026-11-19"),
  "origin_destination_correct":bool(p and p["origin"]=="Oak Wharf" and p["destination"]=="Civic Museum"),
  "valid_step_free_route":bool(p and p["route_code"]=="R4-R5" and p["step_free"]==1),
  "arrival_constraint":bool(p and p["arrive_by"]=="10:15" and p["departure"]=="09:15"),
  "avoids_central_elevator_outage":bool(p and "riverside" in p["note"].lower() and "central" in p["note"].lower() and any(w in p["note"].lower() for w in ("lift","elevator")) and any(w in p["note"].lower() for w in ("out of service","outage","unavailable","closed"))),
  "all_evidence_viewed":all(("GET",path,200) in visits for path in ("/network","/disruptions/D-711","/guide/step-free")),
  "no_ticket_booked":bool(p and p["ticket_booked"]==0)}
 research={path:[x["seq"] for x in request_rows if x["method"]=="GET" and x["path"]==path and x["status"]==200]
          for path in ("/network","/disruptions/D-711","/stations/Riverside-Park")}
 save=[x["seq"] for x in request_rows if x["method"]=="POST" and x["path"]=="/favorite" and x["status"]==200]
 favorites_after=[x["seq"] for x in request_rows if x["method"]=="GET" and x["path"]=="/favorites" and x["status"]==200]
 ordered_research=all(research.values()) and research["/network"][0]<research["/disruptions/D-711"][0]<research["/stations/Riverside-Park"][0]
 uc={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_favorite":len(favs)==1,
  "station_correct":bool(f and f["station"]==USER_FAVORITE),"personal_list":bool(f and f["list_name"]=="Personal"),
  "route_options_reviewed_before_save":bool(research["/network"] and save and research["/network"][0]<save[0]),
  "service_alert_reviewed_before_save":bool(research["/disruptions/D-711"] and save and research["/disruptions/D-711"][0]<save[0]),
  "station_information_viewed_before_save":bool(research["/stations/Riverside-Park"] and save and research["/stations/Riverside-Park"][0]<save[0]),
  "research_pages_reviewed_in_order":ordered_research,
  "save_confirmation_received":bool(save),
  "favorites_reopened_after_save":bool(save and any(seq>save[-1] for seq in favorites_after))}
 return {"agent":{"success":all(ac.values()),"task":"accessible urban-transit itinerary draft","checks":ac,"itinerary":p},
         "user":{"success":all(uc.values()),"task":"save a favorite transit station","checks":uc,"favorite":f}}

def _page(title,body):
 return (f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | CoDesk Transit Planner</title><style>
body{{margin:0;background:#eef4f5;color:#17303a;font:16px/1.5 system-ui,sans-serif}}header{{background:#12546a;color:white;padding:18px 32px;font-size:22px}}
nav{{padding:12px 32px;background:#dcebee}}nav a{{margin-right:22px;color:#0d5665;font-weight:650}}main{{max-width:1050px;margin:24px auto;background:white;padding:24px 30px;border:1px solid #c4d5d9;border-radius:8px}}
section,.card{{border:1px solid #cbdadd;padding:15px 18px;border-radius:7px;margin:14px 0}}a{{color:#05627b}}label{{display:block;font-weight:650;margin:14px 0 5px}}input,select,textarea,button{{font:inherit}}input,select,textarea{{box-sizing:border-box;width:100%;padding:10px;border:1px solid #829aa1;border-radius:4px}}textarea{{min-height:95px}}button{{margin-top:16px;background:#0c6476;color:white;border:0;border-radius:4px;padding:10px 18px}}.notice{{background:#e5f4ef;border-left:4px solid #34806c;padding:10px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border:1px solid #bccdd1;text-align:left}}
</style></head><body><header>CoDesk Transit Planner</header><nav><a href="/">Trip planner</a><a href="/network">Network options</a><a href="/disruptions/D-711">Service alerts</a><a href="/guide/step-free">Accessibility guide</a><a href="/favorites">Saved places</a></nav><main>{body}</main></body></html>""").encode()

def make_server(db_path,host="127.0.0.1",port=0):
 dbfile=str(Path(db_path))
 class H(BaseHTTPRequestHandler):
  server_version="CoDeskTransit/1.0"
  def log_message(self,fmt,*args):
   with sqlite3.connect(dbfile) as db:db.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,getattr(self,"_status",200),datetime.now(timezone.utc).isoformat()))
  def send(self,status,data):
   self._status=status;b=data.encode() if isinstance(data,str) else data
   self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
  def do_GET(self):
   p=urlparse(self.path).path
   if p=="/healthz":self.send(200,b"ok");return
   if p=="/":
    body="<h1>Plan a trip</h1><p>Choose a route that meets your travel needs.</p><section><h2><a href='/trip'>New itinerary</a></h2><p>Plan, check service notices, and save a draft before booking.</p></section><section><h2><a href='/favorites'>Saved places</a></h2><p>Keep your frequently used stations close at hand.</p></section>";self.send(200,_page("Plan a trip",body));return
   if p=="/network":
    body="<h1>Network and route options</h1><table><tr><th>Route</th><th>Legs / scheduled time</th><th>Step-free</th><th>Notes</th></tr><tr><td>R1-R2</td><td>Oak Wharf 09:15 ? Central 09:42 ? Museum District 10:00</td><td>No</td><td>Transfer uses Central lift</td></tr><tr><td>R4-R5</td><td>Oak Wharf 09:15 ? Riverside Park 09:33 ? Museum District 09:58; 7-min walk to Civic Museum (10:05)</td><td>Yes</td><td>Accessible transfer at Riverside Park</td></tr><tr><td>R6-R5</td><td>Oak Wharf 09:20 ? South Gate 09:46 ? Museum District 10:09; walk reaches 10:16</td><td>Yes</td><td>Misses a 10:15 arrival deadline</td></tr></table><p><a href='/disruptions/D-711'>Check service alerts before saving.</a></p>";self.send(200,_page("Network options",body));return
   if p=="/disruptions/D-711":
    self.send(200,_page("Service alert D-711","<h1>Service alert D-711 ? Central Station lift</h1><p>On Thursday 19 November 2026, Central Station elevator is out of service from 08:00 to 12:00.</p><p>Routes using the Central transfer are not step-free during this window. Riverside Park transfer remains open.</p>"));return
   if p=="/guide/step-free":
    self.send(200,_page("Step-free trip guidance","<h1>Step-free journey guide</h1><p>For a step-free itinerary, every vehicle and transfer must have step-free access.</p><p>For arrival deadlines, include the final walk from the station to the destination. A transit arrival before the deadline may still be too late after walking.</p>"));return
   if p=="/trip":
    body="<h1>Save a draft itinerary</h1><p>Trip planning does not reserve seats or buy tickets.</p><form method='post' action='/plan'><label>Itinerary name</label><input name='name' value='' autofocus required><label>Travel date</label><input name='travel_date' value='' placeholder='YYYY-MM-DD' required><label>Origin</label><select name='origin'><option value=''>Choose</option><option>Oak Wharf</option><option>Riverside Park</option></select><label>Destination</label><select name='destination'><option value=''>Choose</option><option>Civic Museum</option><option>Central Library</option></select><label>Route</label><select name='route_code'><option value=''>Choose after checking the network and alerts</option><option value='R1-R2'>R1-R2 ? Central transfer</option><option value='R4-R5'>R4-R5 ? Riverside transfer</option><option value='R6-R5'>R6-R5 ? South Gate transfer</option></select><label>Departure time</label><input name='departure' placeholder='HH:MM' required><label>Arrive no later than</label><input name='arrive_by' placeholder='HH:MM' required><label><input type='checkbox' name='step_free' value='on'> Require step-free access for the full journey</label><label>Why this route?</label><textarea name='note' required></textarea><button type='submit'>Save draft itinerary</button></form>";self.send(200,_page("New itinerary",body));return
   if p=="/stations/Riverside-Park":
    body="<h1>Riverside Park station</h1><section><h2>Station notes</h2><p>Riverside Park is an accessible transfer point for the R4/R5 corridor. Step-free access is available between platforms.</p><p>The west entrance is open during weekday service. A staffed help point is beside the concourse map.</p></section><p><a href='/favorites'>Return to Saved places</a></p>";self.send(200,_page("Riverside Park station",body));return
   if p=="/favorites":
    with sqlite3.connect(dbfile) as db: saved=db.execute("SELECT station,list_name FROM favorites ORDER BY seq").fetchall()
    items="".join(f"<li>{html.escape(station)} - {html.escape(list_name)}</li>" for station,list_name in saved)
    saved_html=f"<ul>{items}</ul>" if items else "<p>No saved places yet.</p>"
    body=f"<h1>Saved places</h1><p>Add a station to a list for quicker trip planning.</p><section><h2>Your saved places</h2>{saved_html}</section><p><a href=\'/stations/Riverside-Park\'>Review Riverside Park station and transfer information</a></p><form method=\'post\' action=\'/favorite\'><label>Station</label><select name=\'station\' autofocus><option value=\'\'>Choose a station</option><option>Oak Wharf</option><option>Riverside Park</option><option>Central Station</option><option>Library Gardens</option></select><label>List</label><select name=\'list_name\'><option>Personal</option><option>Work</option></select><button type=\'submit\'>Save place</button></form>"
    self.send(200,_page("Saved places",body));return
   self.send(404,"Not found")
  def do_POST(self):
   try:
    n=int(self.headers.get("Content-Length","0"));q=parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
    d={k:q.get(k,[""])[0].strip() for k in ("name","travel_date","origin","destination","route_code","departure","arrive_by","note","station","list_name")}
    step=1 if q.get("step_free")==["on"] else 0
   except Exception:self.send(400,"Bad form");return
   with sqlite3.connect(dbfile) as db:
    if self.path=="/plan" and all(d[k] for k in ("name","travel_date","origin","destination","route_code","departure","arrive_by","note")):
     db.execute("INSERT INTO itineraries(name,travel_date,origin,destination,route_code,departure,arrive_by,step_free,note,ticket_booked) VALUES(?,?,?,?,?,?,?,?,?,0)",
      (d["name"],d["travel_date"],d["origin"],d["destination"],d["route_code"],d["departure"],d["arrive_by"],step,d["note"]));db.commit()
     self.send(200,_page("Draft saved","<h1>Draft itinerary saved</h1><p class='notice'>No ticket has been booked.</p>"));return
    if self.path=="/favorite" and d["station"] and d["list_name"]:
     db.execute("INSERT INTO favorites(station,list_name,created_utc) VALUES(?,?,?)",(d["station"],d["list_name"],datetime.now(timezone.utc).isoformat()));db.commit()
     self.send(200,_page("Saved place",f"<h1>Saved places</h1><p class='notice'>{html.escape(d['station'])} has been saved to {html.escape(d['list_name'])}.</p>"));return
   self.send(400,"Invalid submission")
 s=ThreadingHTTPServer((host,port),H);s.daemon_threads=True;return s


APP_TITLE="CoDesk Transit Planner"
TITLE="Accessible urban-trip planning while a user saves a favorite transit stop"
SHARED_STATE="One offline transit-planning website in a shared Chrome window. Agent consults route, outage and step-free guidance then drafts an itinerary; User saves a personal favorite station. Shared state is browser route/focus and current form."
AGENT_ORACLE="A single unbooked 19-Nov-2026 Oak Wharf?Civic Museum itinerary uses step-free R4-R5, departs 09:15, arrives by 10:15 accounting for the walk, and accounts for the Central lift outage; network, alert and guidance pages were viewed."
USER_ORACLE="User reviews the relevant network, alert and station information, saves exactly one Riverside Park Personal favorite, sees the save confirmation, then reopens Saved places and verifies the saved item."
NATURAL_CONDITION="No event order is forced in the natural arm. User checks route options and the Central-lift alert, inspects Riverside Park transfer details, saves it to Personal and revisits Saved places to verify persistence; Agent plans the museum trip."
def user_actions():
 from ..actors import GUIAction
 return [
  GUIAction("open_network_options","pyautogui.click(300, 205)","CoDesk Transit Planner",0.8),
  GUIAction("review_riverside_route_options","pyautogui.moveTo(1500, 700); pyautogui.scroll(-2)","CoDesk Transit Planner",8.0),
  GUIAction("open_service_alerts","pyautogui.click(420, 205)","CoDesk Transit Planner",4.0),
  GUIAction("read_central_lift_service_alert","pyautogui.moveTo(1450, 680); pyautogui.scroll(-2)","CoDesk Transit Planner",8.0),
  GUIAction("open_saved_places","pyautogui.click(740, 205)","CoDesk Transit Planner",4.0),
  GUIAction("open_riverside_station_info","pyautogui.click(670, 588)","CoDesk Transit Planner",5.0),
  GUIAction("read_station_access_notes","pyautogui.moveTo(1450, 680); pyautogui.scroll(-2)","CoDesk Transit Planner",10.0),
  GUIAction("return_to_saved_places","pyautogui.hotkey('alt', 'left')","CoDesk Transit Planner",5.0),
  GUIAction("choose_riverside_and_personal","pyautogui.click(1000, 665); pyautogui.press('r'); pyautogui.press('enter'); pyautogui.click(1000, 747); pyautogui.press('home'); pyautogui.press('enter')","CoDesk Transit Planner",5.0),
  GUIAction("save_personal_favorite","pyautogui.click(525, 808)","CoDesk Transit Planner",2.0),
  GUIAction("review_save_confirmation","pyautogui.moveTo(600, 500)","CoDesk Transit Planner",5.0),
  GUIAction("reopen_saved_places","pyautogui.click(740, 205)","CoDesk Transit Planner",5.0),
  GUIAction("verify_persisted_favorite","pyautogui.moveTo(600, 500)","CoDesk Transit Planner",5.0),
 ]
