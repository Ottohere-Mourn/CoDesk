"""Deterministic host-only grading for the calendar scheduling episode."""
from __future__ import annotations
import json,sqlite3
from pathlib import Path
from pipeline.grade import make_grade

ROOMS={"CEDAR":(10,{"projector","whiteboard"}),"BIRCH":(12,{"projector","whiteboard","vc"}),"MAPLE":(8,{"vc","whiteboard"}),"ATLAS":(16,{"projector","vc","whiteboard"})}
TARGETS={
 "CR-101":{"owner":"customer","start_utc":"20261202T140000Z","end_utc":"20261202T150000Z","attendee":"orion@example.invalid","capacity":8,"features":{"projector"}},
 "CR-104":{"owner":"customer","start_utc":"20261203T083000Z","end_utc":"20261203T093000Z","attendee":"cedar@example.invalid","capacity":6,"features":{"vc"}},
 "CR-108":{"owner":"customer","start_utc":"20261204T160000Z","end_utc":"20261204T170000Z","attendee":"northstar@example.invalid","capacity":13,"features":{"projector","vc"}},
 "TS-201":{"owner":"training","start_utc":"20261202T140000Z","end_utc":"20261202T150000Z","attendee":"training@example.invalid","capacity":9,"features":{"projector"}},
 "TS-203":{"owner":"training","start_utc":"20261203T083000Z","end_utc":"20261203T093000Z","attendee":"support@example.invalid","capacity":11,"features":{"vc"}},
 "TS-207":{"owner":"training","start_utc":"20261205T151500Z","end_utc":"20261205T164500Z","attendee":"response@example.invalid","capacity":7,"features":{"vc","whiteboard"}},
}
def _json(path):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {}
def _ics(path):
 try:text=path.read_text(encoding='utf-8'); rows=[];cur=None
 except OSError:return []
 import re
 for line in re.sub(r'\n[ \t]', '', text.replace('\r','')).splitlines():
  if line=='BEGIN:VEVENT':cur={}
  elif line=='END:VEVENT' and cur is not None:rows.append(cur);cur=None
  elif cur is not None and ':' in line:
   k,v=line.split(':',1);k=k.split(';',1)[0];cur[k]=v
   if k=='LOCATION':cur.setdefault('ROOM',v)
   if k=='ATTENDEE':cur[k]=v.removeprefix('mailto:')
 return rows
def _db(root):
 try:
  c=sqlite3.connect(Path(root).resolve().as_uri()+"?mode=ro",uri=True);c.row_factory=sqlite3.Row
  reservations=[dict(r) for r in c.execute("SELECT uid,room_id,start_utc,end_utc,status,owner_ref FROM reservations")]
  tokens=[dict(r) for r in c.execute("SELECT token,owner,revision,payload_json,status FROM preview_tokens")]
  confirmations=[dict(r) for r in c.execute("SELECT uid,token,confirmation_id FROM confirmations")];c.close();return reservations,tokens,confirmations
 except (OSError,sqlite3.Error):return [],[],[]
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";all_ics=_ics(root/"team_schedule.ics");by_uid={r.get('UID'):r for r in all_ics};reservations,tokens,confirmations=_db(root/"rooms.db")
 audits={"customer":_json(out/"calendar_audit.json"),"training":_json(out/"calendar_b_audit.json")};exports={"customer":_ics(out/"calendar_export_a.ics"),"training":_ics(out/"calendar_export_b.ics")}
 rows_by_owner={owner:[r for r in reservations if r.get('owner_ref')==owner and r.get('status')=='CONFIRMED'] for owner in ('customer','training')}
 def valid_event(uid,owner):
  t=TARGETS[uid];r=next((x for x in rows_by_owner[owner] if x.get('uid')==uid),None);i=by_uid.get(uid)
  if not r or not i:return False
  room=ROOMS.get(r.get('room_id',''));att=r.get('room_id','')
  return (r.get('start_utc')==t['start_utc'] and r.get('end_utc')==t['end_utc'] and room is not None and room[0]>=t['capacity'] and t['features'].issubset(room[1]) and i.get('DTSTART')==t['start_utc'] and i.get('DTEND')==t['end_utc'] and i.get('ROOM')==att and i.get('ATTENDEE')==t['attendee'])
 def audit_ok(owner):
  a=audits[owner];events=[{**x,'uid':x.get('uid',x.get('event_uid')),'thread_id':x.get('thread_id',x.get('source_thread_id'))} for x in a.get('events',[]) if isinstance(x,dict)];uids={x.get('uid') for x in events if isinstance(x,dict)};target={u for u,t in TARGETS.items() if t['owner']==owner}
  return uids==target and all(valid_event(u,owner) for u in target) and all(any(x.get('uid')==u and x.get('thread_id')==u and x.get('confirmation_id') for x in events if isinstance(x,dict)) for u in target)
 def phase_ok(owner):
  owner_tokens=[x for x in tokens if x.get('owner')==owner and x.get('status')=='CONFIRMED'];seen={}
  for x in confirmations:
   if any(t['token']==x.get('token') for t in owner_tokens):seen[x['uid']]=True
  return len(owner_tokens)>=1 and all(seen.get(u) for u,t in TARGETS.items() if t['owner']==owner)
 def export_ok(owner):
  expected={u for u,t in TARGETS.items() if t['owner']==owner};rows={x.get('UID'):x for x in exports[owner]}
  return set(rows)==expected and all(rows[u].get('DTSTART')==TARGETS[u]['start_utc'] and rows[u].get('ROOM')==by_uid.get(u,{}).get('ROOM') for u in expected)
 def check(cid,w,ok,e):return {"id":cid,"weight":w,"passed":bool(ok),"score":float(bool(ok)),"required":True,"evidence":e}
 a_ids={u for u,t in TARGETS.items() if t['owner']=='customer'};b_ids=set(TARGETS)-a_ids
 a_events=all(valid_event(u,'customer') for u in a_ids);b_events=all(valid_event(u,'training') for u in b_ids)
 a_export=export_ok('customer');b_export=export_ok('training');a_phase=phase_ok('customer');b_phase=phase_ok('training');a_audit=audit_ok('customer');b_audit=audit_ok('training')
 protected_hold=any(r.get('uid')=='BASE-900' and r.get('room_id')=='MAPLE' for r in reservations) and any(x.get('UID')=='BASE-900' for x in all_ics)
 a=[check('A01',.25,a_events,{"valid_target_events":sum(valid_event(u,'customer') for u in a_ids),"expected":3}),check('A02',.2,a_phase,{"phase_tokens_confirmed":a_phase}),check('A03',.2,a_audit,{"audit_matches_schedule":a_audit}),check('A04',.2,a_export,{"export_contains_exact_customer_set":a_export}),check('A05',.15,protected_hold,{"protected_facilities_hold_preserved":protected_hold})]
 b=[check('B01',.25,b_events,{"valid_target_events":sum(valid_event(u,'training') for u in b_ids),"expected":3}),check('B02',.2,b_phase,{"phase_tokens_confirmed":b_phase}),check('B03',.2,b_audit,{"audit_matches_schedule":b_audit}),check('B04',.2,b_export,{"export_contains_exact_training_set":b_export}),check('B05',.15,protected_hold,{"protected_facilities_hold_preserved":protected_hold})]
 all_ids=a_ids|b_ids;joint_ok=all(valid_event(u,TARGETS[u]['owner']) for u in all_ids)
 # Confirmed reservations cannot overlap in the same room; existing facilities hold is protected.
 times=[]
 for r in reservations:
  start,end=r.get('start_utc',''),r.get('end_utc','')
  for other in times:
   if r.get('room_id')==other['room_id'] and start<other['end'] and end>other['start']:joint_ok=False
  times.append({"room_id":r.get('room_id'),"start":start,"end":end})
 base_preserved=any(r.get('uid')=='BASE-900' and r.get('room_id')=='MAPLE' for r in reservations) and any(x.get('UID')=='BASE-900' for x in all_ics)
 health=(receipt.get('http_endpoints',{}).get('calendar_health',{}).get('status_code')==200)
 joint=[check('J01',1,joint_ok,{"six_target_events_valid_and_room_conflict_free":joint_ok}),check('J02',1,base_preserved,{"baseline_event_preserved":base_preserved}),check('J03',1,a_export and b_export and a_audit and b_audit,{"both_actor_exports_and_audits_consistent":a_export and b_export and a_audit and b_audit}),check('J04',1,health,{"health_status_200":health})]
 return make_grade(case_id='BC-10',run_id=run_id,actor_a_checks=a,actor_b_checks=b,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,failure_reasons=[] if (root/'rooms.db').is_file() else ['Rooms database snapshot is missing.'],run_metadata={"oracle":"BC-10 host-side deterministic calendar grader"})
