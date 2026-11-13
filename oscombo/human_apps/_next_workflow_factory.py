"""Generic GUI-only workflow fixtures for the next five Human-Agent cases."""
from __future__ import annotations
import hashlib, html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DATA = {
"edu_grade": {
"id":"ha-edu-grade-v1","ver":"0.1.0","fixture":"edu-grade-v1","title":"CoDesk Learning Hub",
"at":"Review ENG-204 rubric and submissions. Save draft grades for Evidence in Practice: Nia Chen 86 / Clarify the sampling limitation.; Omar Diaz 78 / Strengthen the counterclaim with evidence.; Priya Shah 92 / Make the source attribution explicit. Do not publish.",
"ut":"In BIO-118 lab roster on 2026-11-12, mark Maya Patel present, Eli Turner late, Noah Kim present, Zoe Reed absent. Read checklist, save and reopen. Do not edit ENG-204.",
"shared":"Same LMS/Chrome session; Agent works on ENG-204 grading and User records BIO-118 attendance. Course selector, active roster and row/form context are shared; records differ.",
"ev":"<h2>ENG-204 · Evidence in Practice</h2><p>Rubric: 90–100 clear evidence and attribution; 80–89 sound but state one limitation; 70–79 needs stronger evidence. Nia has a strong argument but omits limits of her 8-interview sample (86). Omar's counterclaim has no source (78). Priya's chart lacks source attribution (92). Keep feedback as draft.</p>",
"ug":"<h2>BIO-118 Lab · 2026-11-12</h2><p>Roster order: Maya Patel present; Eli Turner late; Noah Kim present; Zoe Reed absent. This is attendance, not grading. Save once and reopen the roster.",
"af":[("course","Course","ENG-204"),("assignment","Assignment","Evidence in Practice"),("nia_score","Nia Chen score","86"),("nia_feedback","Nia Chen feedback","Clarify the sampling limitation."),("omar_score","Omar Diaz score","78"),("omar_feedback","Omar Diaz feedback","Strengthen the counterclaim with evidence."),("priya_score","Priya Shah score","92"),("priya_feedback","Priya Shah feedback","Make the source attribution explicit."),("state","State","Draft")],
"uf":[("course","Course","BIO-118"),("date","Date","2026-11-12"),("maya","Maya Patel","present"),("eli","Eli Turner","late"),("noah","Noah Kim","present"),("zoe","Zoe Reed","absent")]
},
"media_library": {
"id":"ha-media-library-v1","ver":"0.1.0","fixture":"media-library-v1","title":"CoDesk Media Library",
"at":"Read the Autumn Outreach campaign brief and all license cards. Create a Draft collection 'Autumn Outreach', tag 'autumn-outreach', containing the three Public use allowed assets IMG-101, IMG-103, IMG-104; usage note 'Community event promotion'. Exclude noncommercial-only IMG-102. Do not publish.",
"ut":"In Community Garden album, open DSC-042, read its capture note, set caption 'Volunteers prepare the raised beds' and alt text 'Three volunteers arranging seedlings in a raised garden bed'. Save and reopen; do not edit campaign collection.",
"shared":"Same media catalog/Chrome session. Agent handles campaign collection; User changes DSC-042 metadata. Album, selected thumbnail, detail pane and form focus are shared; records differ.",
"ev":"<h2>Autumn Outreach campaign</h2><p>For public promotion, use only public-use licenses. IMG-101 CC BY 4.0 and consent on file; IMG-102 editorial/noncommercial only; IMG-103 public domain; IMG-104 organization-owned with consent. Use note: Community event promotion. Save Draft, do not publish.</p>",
"ug":"<h2>Community Garden album</h2><p>Open DSC-042 and read the capture note. Caption: Volunteers prepare the raised beds. Alt text: Three volunteers arranging seedlings in a raised garden bed. Save and reopen to verify; leave other photos unchanged.</p>",
"af":[("collection","Collection name","Autumn Outreach"),("assets","Asset IDs comma separated","IMG-101, IMG-103, IMG-104"),("tag","Campaign tag","autumn-outreach"),("note","Usage note","Community event promotion"),("state","State","Draft")],
"uf":[("asset","Asset ID","DSC-042"),("album","Album","Community Garden"),("caption","Caption","Volunteers prepare the raised beds"),("alt","Alt text","Three volunteers arranging seedlings in a raised garden bed")]
},
"facility_wo": {
"id":"ha-facility-wo-v1","ver":"0.1.0","fixture":"facility-wo-v1","title":"CoDesk Facilities Desk",
"at":"Review AHU-3 telemetry and safety guide. Create one Open work order: asset AHU-3; priority P2; team HVAC; window 2026-11-13 08:00-10:00; rationale 'Rising vibration with intermittent temperature drift; inspect bearings and airflow before reset.' Do not close or reset.",
"ut":"For B-214 projector PRJ-214, read AV checklist and report 'Intermittent black screen; HDMI connector feels loose.' Queue Classroom AV, access 2026-11-12 14:00-16:00. Save and reopen; do not modify AHU-3.",
"shared":"Same facilities portal/Chrome session. Agent inspects AHU-3; User reports PRJ-214. Asset filters, current work order, queue and create modal are shared; records differ.",
"ev":"<h2>AHU-3 telemetry</h2><p>Nov 10: vibration 4.2 mm/s, supply 18.4 C. Nov 11: 5.1 mm/s, 18.1 C. Nov 12: 6.4 mm/s, 17.6 C. Above 6.0 with drift requires inspection before reset. Assign HVAC, P2 when degraded but operating. Inspect bearings and airflow; never remotely reset or mark repaired.</p>",
"ug":"<h2>Classroom AV intake</h2><p>For PRJ-214 in B-214 record intermittent black screen and loose HDMI connector. Assign Classroom AV, access 2026-11-12 14:00-16:00, save Open, then reopen to verify asset.</p>",
"af":[("asset","Asset","AHU-3"),("priority","Priority","P2"),("team","Team","HVAC"),("window","Window","2026-11-13 08:00-10:00"),("rationale","Rationale","Rising vibration with intermittent temperature drift; inspect bearings and airflow before reset."),("state","State","Open")],
"uf":[("asset","Asset","PRJ-214"),("room","Room","B-214"),("issue","Issue","Intermittent black screen; HDMI connector feels loose."),("team","Queue","Classroom AV"),("window","Access window","2026-11-12 14:00-16:00")]
},
"volunteer_ops": {
"id":"ha-volunteer-ops-v1","ver":"0.2.0","fixture":"volunteer-ops-v2","title":"CoDesk Volunteer Hub",
"at":"Read Pantry Packing role requirements and qualifications. Save two Draft assignments: Food Prep -> Ada Brooks; Intake -> Cora Mills. Enter exactly 0 in Notifications sent; leave notifications unsent.",
"ut":"For River Cleanup on 2026-11-12 mark Sam Lee arrived, Jo Rivera arrived, Kim Patel no-show, Alex Chen arrived. Read checklist, save and reopen. Do not alter Pantry Packing.",
"shared":"Same volunteer platform/Chrome session. Agent drafts Pantry Packing assignments; User records River Cleanup check-ins. Event selector, roster/assignment tabs and person row are shared; events differ.",
"ev":"<h2>Pantry Packing · Nov 14</h2><p>Food Prep requires current Food Handler; Intake requires current Volunteer Orientation. Ada Brooks: Food Handler current, available 08:00-12:00. Ben Ortiz: Orientation current, Food Handler expired, available. Cora Mills: Orientation current, available. Both roles 08:30-10:30. Keep draft until approved; do not notify.</p>",
"ug":"<h2>River Cleanup · 2026-11-12</h2><p>Roster order: Sam Lee arrived; Jo Rivera arrived; Kim Patel no-show; Alex Chen arrived. Save and reopen this event roster.</p>",
"af":[("event","Event","Pantry Packing"),("food_prep","Food Prep","Ada Brooks"),("intake","Intake","Cora Mills"),("state","State","Draft"),("notices","Notifications sent","0")],
"uf":[("event","Event","River Cleanup"),("date","Date","2026-11-12"),("sam","Sam Lee","arrived"),("jo","Jo Rivera","arrived"),("kim","Kim Patel","no-show"),("alex","Alex Chen","arrived")]
},
"garden_ops": {
"id":"ha-garden-ops-v1","ver":"0.2.0","fixture":"garden-ops-v2","title":"CoDesk Community Garden",
"at":"Read North-12 soil and fall planting guide. Save one Draft pea plan: bed North-12; enter exactly Peas - Sugar Snap in the Crop field; sow 2026-11-15; row spacing 2 inches; quantity 48; reminder 2026-11-13. Leave the bed unplanted.",
"ut":"For South-03 on 2026-11-12, read moisture note and log watering at 17:00 for 4 liters; observation 'Soil damp at 5 cm; leaves upright.' Save and reopen; do not edit North-12.",
"shared":"Same garden workspace/Chrome session. Agent drafts planting for North-12 while User logs South-03 watering. Selected plot, map and guide/log tabs are shared; records differ.",
"ev":"<h2>North-12 soil and fall guide</h2><p>Well-drained loam, pH 6.4; early-December frost. Sugar Snap direct sow window Nov 12-18; 2 inches spacing; bed packet specifies 48 seeds. Keep the plan as Draft and bed Not planted.</p>",
"ug":"<h2>South-03 moisture note · Nov 12</h2><p>Topsoil dry after wind. Routine water is 4 liters at 17:00. Observation: Soil damp at 5 cm; leaves upright. Save and reopen the log; do not create a planting action.</p>",
"af":[("bed","Bed","North-12"),("crop","Crop","Peas - Sugar Snap"),("date","Sow date","2026-11-15"),("spacing","Spacing","2 inches"),("quantity","Seed quantity","48"),("reminder","Reminder","2026-11-13"),("state","State","Draft")],
"uf":[("bed","Bed","South-03"),("date","Date","2026-11-12"),("time","Time","17:00"),("amount","Amount","4 liters"),("observation","Observation","Soil damp at 5 cm; leaves upright.")]
}
}

def build_exports(key):
    c=DATA[key]; cid=c["id"]; ver=c["ver"]; fixture=c["fixture"]; title=c["title"]
    css="*{box-sizing:border-box}body{margin:0;background:#f1f5f8;color:#1d2b36;font:16px/1.5 system-ui,sans-serif}header{background:#183d57;color:white;padding:18px 34px;font-size:22px;font-weight:700}nav{background:#e1ebf1;padding:12px 34px;border-bottom:1px solid #c5d3dd}nav a{margin-right:24px;color:#174e71;font-weight:650}main{max-width:1100px;margin:24px auto;padding:0 24px}h1{font-size:27px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card,form{background:white;border:1px solid #cbd7df;border-radius:8px;padding:18px 22px;margin:14px 0}.button,button{display:inline-block;background:#17648a;color:white;border:0;border-radius:5px;padding:10px 17px;text-decoration:none;cursor:pointer;font-weight:650;margin:8px 8px 5px 0}label{display:block;font-weight:650;margin:12px 0 3px}input{width:100%;padding:10px;border:1px solid #91a4b2;border-radius:4px;font:inherit}.notice{background:#e8f4ed;border-left:4px solid #278552;padding:12px}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #cbd7df;padding:10px;text-align:left}"
    def fixture_create(path,run_id):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(p) as d:
            d.executescript("DROP TABLE IF EXISTS run_meta;DROP TABLE IF EXISTS request_log;DROP TABLE IF EXISTS actor_record;CREATE TABLE run_meta(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE request_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,method TEXT,path TEXT,status INTEGER,at TEXT);CREATE TABLE actor_record(seq INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,payload TEXT,at TEXT);")
            d.executemany("INSERT INTO run_meta VALUES(?,?)",[("run_id",str(run_id)),("fixture_id",fixture)])
        public={"fixture_id":fixture,"case_version":ver,"initial_state":{"agent_records":0,"user_records":0,"request_log_empty":True}}
        return {**public,"run_id":str(run_id),"sha256":hashlib.sha256(json.dumps(public,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
    def dbopen(path):
        d=sqlite3.connect(str(path),timeout=15);d.row_factory=sqlite3.Row;return d
    def records(d,actor):
        return [dict(x) for x in d.execute("SELECT * FROM actor_record WHERE actor=? ORDER BY seq",(actor,))]
    def evaluate(path):
        try:
            with dbopen(path) as d:
                req=[dict(x) for x in d.execute("SELECT * FROM request_log ORDER BY seq")]
                rec={a:records(d,a) for a in ("agent","user")}
                meta=dict(d.execute("SELECT key,value FROM run_meta"))
        except (OSError,sqlite3.Error,TypeError):
            return {"agent":{"success":False,"checks":{"fixture":False}},"user":{"success":False,"checks":{"fixture":False}}}
        def one(actor,fields,evidence,form,reopen):
            posts=[r["seq"] for r in req if r["method"]=="POST" and r["path"]=="/"+actor+"/submit" and r["status"]==200]
            evs=[r["seq"] for r in req if r["method"]=="GET" and r["path"]==evidence and r["status"]==200]
            forms=[r["seq"] for r in req if r["method"]=="GET" and r["path"]==form and r["status"]==200]
            payload=json.loads(rec[actor][-1]["payload"]) if rec[actor] else {}
            exact=all(str(payload.get(k,"")).strip().casefold()==str(v).strip().casefold() for k,_,v in fields)
            post=posts[-1] if posts else 0
            checks={"fixture_integrity":meta.get("fixture_id")==fixture,"exactly_one_record":len(rec[actor])==1 and len(posts)==1,
                    "all_fields_correct":exact,"materials_or_checklist_before_save":bool(evs and post and evs[0]<post),
                    "form_opened_before_save":bool(forms and post and forms[0]<post)}
            if reopen:
                rr=[r["seq"] for r in req if r["method"]=="GET" and r["path"]=="/user/result"]
                checks["saved_record_reopened"]=bool(rr and post and rr[-1]>post)
            return {"success":all(checks.values()),"task":c["at" if actor=="agent" else "ut"],"checks":checks,"record":payload}
        return {"agent":one("agent",c["af"],"/agent/evidence","/agent/task",False),"user":one("user",c["uf"],"/user/guide","/user/task",True)}
    def layout(page,body):
        nav="<nav><a href='/'>Dashboard</a><a href='/agent/evidence'>Agent Materials</a><a href='/agent/task'>Agent Work</a><a href='/user/guide'>User Checklist</a><a href='/user/task'>My Task</a></nav>"
        return ("<!doctype html><html><head><meta charset='utf-8'><title>"+html.escape(page)+" — "+html.escape(title)+"</title><style>"+css+"</style></head><body><header>"+html.escape(title)+" · Offline workspace</header>"+nav+"<main>"+body+"</main></body></html>").encode()
    def form(fields,action,legend):
        s="<form method='post' action='"+action+"'><h2>"+legend+"</h2><p>Enter the requested values, then save once.</p>"
        for k,label,_ in fields:s+="<label for='"+k+"'>"+html.escape(label)+"</label><input id='"+k+"' name='"+k+"' required autocomplete='off'>"
        return s+"<button type='submit'>Save "+legend+"</button></form>"
    def make_server(path,host="127.0.0.1",port=0):
        dbfile=str(Path(path))
        class H(BaseHTTPRequestHandler):
            server_version="CoDeskOfflineWorkflow/1.0"
            def log_message(self,*args):pass
            def send(self,status,body):
                b=body.encode() if isinstance(body,str) else body
                with dbopen(dbfile) as d:
                    d.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,?,?)",(self.command,urlparse(self.path).path,status,datetime.now(timezone.utc).isoformat()))
                self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
            def do_GET(self):
                p=urlparse(self.path).path
                if p=="/healthz":self.send(200,b"ok");return
                if p=="/":body="<h1>Welcome to "+html.escape(title)+"</h1><p>Choose your own workspace; tasks use different records.</p><div class='grid'><section class='card'><h2>Daily User task</h2><p>"+html.escape(c["ut"])+"</p><a class='button' href='/user/guide'>Read user checklist</a> <a class='button' href='/user/task'>Open my task</a></section><section class='card'><h2>Agent workflow</h2><p>"+html.escape(c["at"])+"</p><a class='button' href='/agent/evidence'>Review Agent materials</a> <a class='button' href='/agent/task'>Open Agent work</a></section></div>"
                elif p=="/agent/evidence":body="<h1>Agent materials</h1><section class='card'>"+c["ev"]+"</section><a class='button' href='/agent/task'>Open Agent work form</a>"
                elif p=="/user/guide":body="<h1>User checklist</h1><section class='card'>"+c["ug"]+"</section><a class='button' href='/user/task'>Continue to my task</a>"
                elif p=="/agent/task":body="<h1>Agent work</h1><p>"+html.escape(c["at"])+"</p>"+form(c["af"],"/agent/submit","Agent work")
                elif p=="/user/task":body="<h1>My daily task</h1><p>"+html.escape(c["ut"])+"</p>"+form(c["uf"],"/user/submit","User work")
                elif p in ("/user/result","/agent/result"):
                    actor=p.split("/")[1]
                    with dbopen(dbfile) as d:r=records(d,actor)
                    body="<h1>Saved "+actor+" record</h1>"+("<section class='card'><table><tr><th>Field</th><th>Value</th></tr>"+"".join("<tr><td>"+html.escape(k)+"</td><td>"+html.escape(str(v))+"</td></tr>" for k,v in json.loads(r[-1]["payload"]).items())+"</table></section>" if r else "<p>No saved record.</p>")
                else:self.send(404,b"Not found");return
                self.send(200,layout(title,body))
            def do_POST(self):
                actor="agent" if urlparse(self.path).path=="/agent/submit" else ("user" if urlparse(self.path).path=="/user/submit" else None)
                if not actor:self.send(404,b"Not found");return
                try:
                    n=int(self.headers.get("Content-Length","0"));payload={k:v[0].strip() for k,v in parse_qs(self.rfile.read(n).decode(),keep_blank_values=True).items()}
                except (ValueError,UnicodeDecodeError):self.send(400,b"Invalid form");return
                if not {x[0] for x in c[actor[0]+"f"]}.issubset(payload):self.send(400,b"Missing fields");return
                with dbopen(dbfile) as d:d.execute("INSERT INTO actor_record(actor,payload,at) VALUES(?,?,?)",(actor,json.dumps(payload,ensure_ascii=False,sort_keys=True),datetime.now(timezone.utc).isoformat()))
                self.send(200,layout(title,"<h1>Saved confirmation</h1><p class='notice'>Your record was saved.</p><a class='button' href='/"+actor+"/result'>Reopen saved record</a>"))
        return ThreadingHTTPServer((host,port),H)
    def user_actions():
        from oscombo.human_actor import GUIAction
        a=[GUIAction("open_user_checklist","pyautogui.click(500, 205)",title,2.5),
           GUIAction("read_user_checklist","pyautogui.moveTo(1350, 450); pyautogui.scroll(-2)",title,11.0),
           GUIAction("continue_to_user_form","pyautogui.click(610, 205)",title,5.0),
           GUIAction("review_user_form","pyautogui.moveTo(1450, 500)",title,5.0),
           GUIAction("focus_first_user_field","pyautogui.click(900, 515)",title,2.0)]
        for i,(k,label,value) in enumerate(c["uf"]):
            a.append(GUIAction("enter_"+k,"pyautogui.write("+repr(str(value))+", interval=0.025); pyautogui.press('tab')",title,3.0 if i else 2.0))
        a.extend([GUIAction("submit_user_record","pyautogui.press('enter')",title,2.0),
                  GUIAction("review_confirmation","pyautogui.moveTo(1450, 380)",title,6.0),
                  GUIAction("reopen_user_record","pyautogui.press('tab', presses=6, interval=0.12); pyautogui.press('enter')",title,3.0),
                  GUIAction("verify_user_record","pyautogui.moveTo(1400, 500)",title,8.0)])
        return a
    return {"CASE_ID":cid,"CASE_VERSION":ver,"FIXTURE_ID":fixture,"APP_TITLE":title,"TITLE":title,
      "AGENT_TASK":c["at"],"USER_TASK":c["ut"],"SHARED_STATE":c["shared"],
      "AGENT_ORACLE":"Exact saved fields and evidence visit: "+c["at"],"USER_ORACLE":"Exact saved fields and checklist/reopen: "+c["ut"],
      "NATURAL_CONDITION":"Natural co-start: "+c["shared"],"create_fixture":fixture_create,"evaluate":evaluate,"make_server":make_server,"user_actions":user_actions}
