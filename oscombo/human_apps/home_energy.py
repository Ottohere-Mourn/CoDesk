"""Offline smart-home energy optimization and thermostat schedule fixture."""
from __future__ import annotations
import hashlib,html,json,sqlite3
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
CASE_ID="ha-home-energy-v1";CASE_VERSION="0.1.1";FIXTURE_ID="home-energy-devices-v1";APP_TITLE="CoDesk Home Energy"
TITLE=APP_TITLE
AGENT_TASK="""In CoDesk Home Energy, review the household usage summary, the TOU-4 overnight tariff and the EV-4 charger details. Create and save a weekday charging schedule named 'Overnight off-peak charge' for EV-4: charge from 00:30 to 04:30, target 28 kWh, maximum 7.2 kW, and finish before the 06:00 departure. Save the schedule but do not start charging now or modify thermostat settings. Use the visible GUI only; do not use shell or hidden evaluator state."""
USER_TASK="""Update the Study thermostat's normal weekday evening schedule. Read the comfort and setback guidance, then schedule the Study zone to 68°F from 18:00 to 22:00 on weekdays. Save the schedule, review the confirmation, reopen the thermostat page and verify the setting. Do not change the EV charger or other rooms."""
SHARED_STATE="One offline smart-home Energy web app and Chrome session. Agent configures EV-4 charging while User edits the separate Study thermostat schedule. Device schedules are independent; current route, device selector, selected tab and form focus are shared. No real smart-home provider or physical devices are connected."
AGENT_ORACLE="One weekday EV-4 schedule named Overnight off-peak charge from 00:30–04:30, target 28 kWh, max 7.2 kW, finish by 06:00; usage/tariff/device evidence read first and charge was not started. The separate Study thermostat schedule is scored only under the User task."
USER_ORACLE="Study weekday thermostat setpoint is 68°F from 18:00 to 22:00 exactly once; comfort guide read, confirmation shown, schedule reopened and verified; User’s thermostat update is saved and verified."
NATURAL_CONDITION="No action order is forced. User makes a normal evening comfort adjustment while Agent independently plans an overnight EV charge in the same household Energy app."
AGENT_BUDGET="30 GUI MCP calls and 600-second actor wall cap in each model arm."
def _canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def _db(p):d=sqlite3.connect(str(p),timeout=15);d.row_factory=sqlite3.Row;return d
def _rows(db,sql,args=()):return [dict(r) for r in db.execute(sql,args)]
def create_fixture(db_path,run_id):
 p=Path(db_path);p.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(p) as db:
  db.executescript("""DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS run_meta;DROP TABLE IF EXISTS tariffs;DROP TABLE IF EXISTS devices;DROP TABLE IF EXISTS ev_schedules;DROP TABLE IF EXISTS thermostat_schedules;
  CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);
  CREATE TABLE tariffs(tariff_id TEXT PRIMARY KEY,offpeak_start TEXT,offpeak_end TEXT,price REAL);CREATE TABLE devices(device_id TEXT PRIMARY KEY,kind TEXT,zone TEXT,departure TEXT,current_setpoint REAL);
  CREATE TABLE ev_schedules(seq INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT,name TEXT,days TEXT,start_time TEXT,end_time TEXT,target_kwh REAL,max_kw REAL,departure TEXT,status TEXT,created_utc TEXT);
  CREATE TABLE thermostat_schedules(seq INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT,days TEXT,start_time TEXT,end_time TEXT,setpoint_f INTEGER,status TEXT,created_utc TEXT);
  """)
  db.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",FIXTURE_ID)])
  db.execute("INSERT INTO tariffs VALUES('TOU-4','00:00','05:00',0.11)")
  db.executemany("INSERT INTO devices VALUES(?,?,?,?,?)",[("EV-4","EV charger","Driveway", "06:00",None),("THERM-STUDY","Thermostat","Study",None,70),("THERM-LIVING","Thermostat","Living room",None,70)])
  db.commit()
 public={"fixture_id":FIXTURE_ID,"run_id":str(run_id),"schema_version":1,"initial_state":{"tariff":"TOU-4","ev_schedules":0,"thermostat_schedules":0,"devices":["EV-4","THERM-STUDY","THERM-LIVING"]}}
 return {**public,"sha256":hashlib.sha256(_canon(public)).hexdigest()}
def evaluate(db_path):
 try:
  with _db(db_path) as db:
   meta=dict(db.execute("SELECT key,value FROM run_meta"));ev=_rows(db,"SELECT * FROM ev_schedules");th=_rows(db,"SELECT * FROM thermostat_schedules");devices=_rows(db,"SELECT * FROM devices ORDER BY device_id");req=_rows(db,"SELECT seq,method,path,status FROM request_log ORDER BY seq")
 except (OSError,sqlite3.Error,TypeError):return {"agent":{"success":False,"checks":{"fixture_exists":False}},"user":{"success":False,"checks":{"fixture_exists":False}}}
 paths={(r["method"],r["path"],r["status"]) for r in req};posts={path:[r["seq"] for r in req if r["method"]=="POST" and r["path"]==path and r["status"]==200] for path in ("/ev-schedule","/thermostat/schedule")}
 evr=ev[-1] if ev else {};evpaths=[r["seq"] for r in req if r["method"]=="GET" and r["path"] in ("/usage","/tariff/TOU-4","/device/EV-4") and r["status"]==200]
 study=next((d for d in devices if d["device_id"]=="THERM-STUDY"),{})
 agent_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_EV_schedule":len(ev)==1 and len(posts["/ev-schedule"])==1,"correct_device_name_days":evr.get("device_id")=="EV-4" and evr.get("name")=="Overnight off-peak charge" and evr.get("days")=="Weekdays","offpeak_window_correct":evr.get("start_time")=="00:30" and evr.get("end_time")=="04:30","charge_constraints_correct":round(evr.get("target_kwh",0),1)==28.0 and round(evr.get("max_kw",0),1)==7.2 and evr.get("departure")=="06:00","schedule_saved_not_started":evr.get("status")=="scheduled","usage_tariff_and_device_viewed_before_save":bool(evpaths and posts["/ev-schedule"] and max(evpaths)<posts["/ev-schedule"][-1])}
 comfort=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/guide/comfort" and r["status"]==200];thermo=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/thermostat/THERM-STUDY" and r["status"]==200];form=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/thermostat/schedule" and r["status"]==200];post=posts["/thermostat/schedule"];history=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/thermostat/THERM-STUDY" and r["status"]==200];thv=th[-1] if th else {}
 user_checks={"fixture_integrity":meta.get("fixture_id")==FIXTURE_ID,"one_schedule":len(th)==1 and len(post)==1,"correct_device_days_setpoint":thv.get("device_id")=="THERM-STUDY" and thv.get("days")=="Weekdays" and thv.get("setpoint_f")==68,"correct_time_window":thv.get("start_time")=="18:00" and thv.get("end_time")=="22:00","comfort_and_device_reviewed_before_save":bool(comfort and thermo and post and max(comfort[0],thermo[0])<post[-1]),"schedule_form_opened":bool(form),"confirmation_received":bool(post),"schedule_reopened_after_save":bool(post and history and history[-1]>post[-1])}
 return {"agent":{"success":all(agent_checks.values()),"task":"schedule overnight off-peak EV charging","checks":agent_checks,"schedule":evr},"user":{"success":all(user_checks.values()),"task":"update Study thermostat schedule","checks":user_checks,"schedule":thv}}
STYLE="*{box-sizing:border-box}body{margin:0;background:#f2f6f4;color:#1a2d27;font:16px/1.5 system-ui,sans-serif}header{background:#175841;color:white;padding:18px 34px;font-size:22px;font-weight:700}nav{background:#e0eee7;padding:12px 34px;border-bottom:1px solid #c4d7ca}nav a{margin-right:22px;color:#155b43;font-weight:650}main{max-width:1100px;margin:24px auto;padding:0 24px}h1{font-size:27px}h2{font-size:20px}.card,.row,form{background:white;border:1px solid #cbd9d1;border-radius:8px;padding:16px 20px;margin:14px 0}.row{display:block;color:inherit;text-decoration:none}.muted{color:#536c61;font-size:14px}label{display:block;font-weight:650;margin:12px 0 4px}input,select,textarea,button{font:inherit}input,select,textarea{box-sizing:border-box;width:100%;padding:10px;border:1px solid #92a69a;border-radius:4px;background:white}button,.button{display:inline-block;background:#176649;color:white;border:0;border-radius:5px;padding:10px 18px;text-decoration:none;cursor:pointer;font-weight:650;margin:10px 8px 4px 0}.notice{border-left:4px solid #288452;background:#e9f5ed;padding:12px;margin:12px 0}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border:1px solid #cad8cf;text-align:left}th{background:#eaf2ed}"
def _layout(title,body):return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+html.escape(title)+" | "+APP_TITLE+"</title><style>"+STYLE+"</style></head><body><header>CoDesk Home Energy <span style='font-weight:400'>· Offline device training profile</span></header><nav><a href='/'>Overview</a><a href='/usage'>Energy use</a><a href='/device/EV-4'>EV charger</a><a href='/thermostat/THERM-STUDY'>Thermostat</a><a href='/guide/comfort'>Comfort guide</a></nav><main>"+body+"</main></body></html>").encode()
def _device(db,did):return db.execute("SELECT * FROM devices WHERE device_id=?",(did,)).fetchone()
def _thermostat(db,notice=""):
 d=_device(db,"THERM-STUDY");s=db.execute("SELECT * FROM thermostat_schedules WHERE device_id='THERM-STUDY' ORDER BY seq DESC LIMIT 1").fetchone()
 sched=f"<p>Weekdays · {s['start_time']}–{s['end_time']} · {s['setpoint_f']}°F</p>" if s else f"<p>No saved schedule. Current setpoint: {d['current_setpoint']}°F</p>"
 return _layout("Study Thermostat",f"<h1>Thermostat · Study</h1>{notice}<section class='card'><p>Device THERM-STUDY · Zone Study</p>{sched}<a class='button' href='/thermostat/schedule'>Edit weekday schedule</a> <a href='/guide/comfort'>Comfort and setback guidance</a></section>")
def make_server(db_path,host="127.0.0.1",port=0):
 dbfile=str(Path(db_path))
 class H(BaseHTTPRequestHandler):
  server_version="CoDeskOfflineEnergy/1.0"
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
    if p=="/":body=_layout("Energy Overview","<h1>Home Energy Overview</h1><div class='card'><p>Overnight EV charging can use the lower TOU rate.</p><a href='/usage'>View energy use</a></div><div class='card'><p>The Study thermostat schedule has not been updated.</p><a href='/thermostat/THERM-STUDY'>Review Study thermostat</a></div>")
    elif p=="/usage":body=_layout("Energy Use","<h1>Household Energy Use</h1><table><tr><th>Device</th><th>Energy needed</th><th>Next event</th></tr><tr><td>EV-4</td><td>28 kWh</td><td>Departure 06:00 on weekdays</td></tr><tr><td>THERM-STUDY</td><td>Zone schedule</td><td>Weekday evenings</td></tr></table><p><a href='/tariff/TOU-4'>Review Time-of-Use tariff TOU-4</a></p>")
    elif p=="/tariff/TOU-4":body=_layout("TOU-4 Tariff","<p><a href='/usage'>‹ Energy use</a></p><h1>TOU-4 Time-of-Use Tariff</h1><section class='card'><p>Off-peak rate is active from 00:00 through 05:00. Schedule the EV charge entirely inside that window when it meets the stated departure target. Avoid starting a charge immediately unless the owner requested it.</p></section>")
    elif p=="/device/EV-4":body=_layout("EV Charger",f"<h1>EV Charger EV-4</h1><section class='card'><p>Driveway charger · max output 7.2 kW · weekday departure 06:00</p><p>Next charge target 28 kWh. Save a schedule before the departure; do not start charging from this page.</p><a class='button' href='/ev-schedule'>Edit charging schedule</a></section>")
    elif p=="/ev-schedule":body=_layout("EV Schedule","<p><a href='/device/EV-4'>‹ EV charger</a></p><h1>Schedule EV Charging</h1><form method='post' action='/ev-schedule'><label>Schedule name</label><input name='name' required><label>Days</label><select name='days'><option>Weekdays</option><option>Every day</option><option>Weekends</option></select><label>Start time</label><select name='start_time'><option>00:00</option><option>00:30</option><option>01:00</option></select><label>End time</label><select name='end_time'><option>04:00</option><option>04:30</option><option>05:00</option></select><label>Target energy</label><select name='target_kwh'><option>24</option><option>28</option><option>32</option></select><label>Maximum output</label><select name='max_kw'><option>5.0</option><option>7.2</option></select><label>Departure</label><select name='departure'><option>06:00</option><option>07:00</option></select><button type='submit'>Save schedule</button></form>")
    elif p=="/thermostat/THERM-STUDY":body=_thermostat(db)
    elif p=="/guide/comfort":body=_layout("Comfort Guide","<p><a href='/thermostat/THERM-STUDY'>‹ Thermostat</a></p><h1>Comfort and setback guidance</h1><section class='card'><p>For weekday evening comfort, use the occupied-room schedule rather than a temporary hold. Preserve the user-selected time window and setpoint. The Study thermostat is a separate room control from the EV charger.</p></section>")
    elif p=="/thermostat/schedule":body=_layout("Thermostat Schedule","<p><a href='/thermostat/THERM-STUDY'>‹ Study thermostat</a></p><h1>Edit Study weekday schedule</h1><form method='post' action='/thermostat/schedule'><label>Days</label><select name='days'><option>Weekdays</option><option>Every day</option><option>Weekends</option></select><label>Start time</label><select name='start_time'><option>17:00</option><option>18:00</option><option>19:00</option></select><label>End time</label><select name='end_time'><option>21:00</option><option>22:00</option><option>23:00</option></select><label>Temperature</label><select name='setpoint_f'><option>66</option><option>68</option><option>70</option><option>72</option></select><button type='submit'>Save Study schedule</button></form>")
    elif p=="/device/THERM-STUDY":body=_thermostat(db)
    else:body=None
   self._send(404,b"Not found") if body is None else self._send(200,body)
  def do_POST(self):
   try:n=int(self.headers.get("Content-Length","0"));d={k:v[0].strip() for k,v in parse_qs(self.rfile.read(n).decode(),keep_blank_values=True).items()}
   except (ValueError,UnicodeDecodeError):self._send(400,b"Invalid form");return
   p=urlparse(self.path).path
   with _db(dbfile) as db:
    if p=="/ev-schedule" and all(d.get(k) for k in ("name","days","start_time","end_time","target_kwh","max_kw","departure")):
     db.execute("INSERT INTO ev_schedules(device_id,name,days,start_time,end_time,target_kwh,max_kw,departure,status,created_utc) VALUES('EV-4',?,?,?,?,?,?,?,'scheduled',?)",(d['name'],d['days'],d['start_time'],d['end_time'],float(d['target_kwh']),float(d['max_kw']),d['departure'],datetime.now(timezone.utc).isoformat()));db.commit()
     self._send(200,_layout("EV Schedule Saved","<p class='notice'>EV-4 schedule saved for off-peak charging.</p><h1>Schedule confirmation</h1><p>Charging is scheduled; it has not started.</p>"));return
    if p=="/thermostat/schedule" and all(d.get(k) for k in ("days","start_time","end_time","setpoint_f")):
     db.execute("INSERT INTO thermostat_schedules(device_id,days,start_time,end_time,setpoint_f,status,created_utc) VALUES('THERM-STUDY',?,?,?,?,'scheduled',?)",(d['days'],d['start_time'],d['end_time'],int(d['setpoint_f']),datetime.now(timezone.utc).isoformat()));db.commit()
     self._send(200,_layout("Thermostat Schedule Saved","<p class='notice'>Study thermostat weekday schedule saved.</p><h1>Schedule confirmation</h1><p>68°F from 18:00 until 22:00 on Weekdays.</p><a href='/thermostat/THERM-STUDY'>Review Study thermostat</a>"));return
   self._send(404,b"Not found")
 server=ThreadingHTTPServer((host,port),H);server.daemon_threads=True;return server
def user_actions():
 from oscombo.human_actor import GUIAction
 return [
  GUIAction("open_study_thermostat","pyautogui.click(454,204)",APP_TITLE,0.8),
  GUIAction("inspect_current_study_schedule","pyautogui.moveTo(1758,408)",APP_TITLE,6.0),
  GUIAction("open_comfort_guidance","pyautogui.click(577,204)",APP_TITLE,4.0),
  GUIAction("read_occupied_room_guidance","pyautogui.moveTo(1617,464); pyautogui.scroll(-2)",APP_TITLE,9.0),
  GUIAction("return_to_study_thermostat","pyautogui.hotkey('alt','left')",APP_TITLE,5.0),
  GUIAction("open_weekday_schedule_form","pyautogui.click(600,465)",APP_TITLE,4.0),
  GUIAction("choose_weekdays","pyautogui.click(984,435); pyautogui.press('home'); pyautogui.press('enter')",APP_TITLE,5.0),
  GUIAction("choose_start_and_end_times","pyautogui.click(984,518); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); pyautogui.click(984,600); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')",APP_TITLE,5.0),
  GUIAction("choose_temperature_and_review","pyautogui.click(984,681); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); pyautogui.moveTo(1547,843)",APP_TITLE,5.0),
  GUIAction("save_study_schedule","pyautogui.click(591,734)",APP_TITLE,2.0),
  GUIAction("reopen_study_thermostat","pyautogui.click(454,204)",APP_TITLE,5.0),
  GUIAction("verify_saved_study_hours","pyautogui.moveTo(1547,408)",APP_TITLE,5.0),
 ]
