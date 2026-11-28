from __future__ import annotations
import argparse,csv,hashlib,json,sqlite3,threading,uuid
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse

LOCK=threading.RLock()
def connect(root):
 c=sqlite3.connect(root/"rooms.db",timeout=8);c.row_factory=sqlite3.Row;return c
def revision(root):return hashlib.sha256((root/"team_schedule.ics").read_bytes()).hexdigest()
def load_mail(root,team):
 with (root/"mail_threads.csv").open(encoding='utf-8',newline='') as f:rows=[r for r in csv.DictReader(f) if r["team"]==team]
 latest={}
 for r in rows:
  if r["state"]=="DRAFT":continue
  if r["thread_id"] not in latest or int(r["message_version"])>int(latest[r["thread_id"]]["message_version"]):latest[r["thread_id"]]=r
 return [r for r in latest.values() if r["state"]=="CONFIRMED"]
def to_event(row,room_id):
 start=datetime.strptime(row["local_start"],"%Y-%m-%d %H:%M");off=row["utc_offset"];sign=1 if off[0]=='+' else -1;dh,dm=map(int,off[1:].split(':'));start=(start-timedelta(minutes=sign*(dh*60+dm))).replace(tzinfo=timezone.utc);end=start+timedelta(minutes=int(row["duration_min"]))
 return {"uid":row["event_uid"],"start_utc":start.strftime('%Y%m%dT%H%M%SZ'),"end_utc":end.strftime('%Y%m%dT%H%M%SZ'),"room_id":room_id,"attendee":row["attendee"],"summary":row["subject"]}
def conflict_check(root,owner,events):
 requested=load_mail(root,owner);req_by={r['event_uid']:r for r in requested}; errors=[];options={};c=connect(root)
 if {e.get('uid') for e in events} != set(req_by): errors.append("The submitted UID set does not match the latest confirmed request set.")
 reservations=[dict(r) for r in c.execute("SELECT uid,room_id,start_utc,end_utc,status FROM reservations WHERE status='CONFIRMED'")]
 roomrows={r['room_id']:dict(r) for r in c.execute("SELECT * FROM rooms")}
 planned=[]
 for e in events:
  req=req_by.get(e.get('uid'))
  if not req:errors.append(f"Unknown request UID: {e.get('uid')}");continue
  expected=to_event(req,e.get('room_id',''))
  if any(e.get(k)!=expected[k] for k in ('start_utc','end_utc','attendee')):errors.append(f"Source time/attendee mismatch for {e.get('uid')}.")
  room=roomrows.get(e.get('room_id'));need=set(req['features'].lower().split(','))
  if not room or int(room['capacity'])<int(req['attendee_count']) or not need.issubset(set(room['features'].lower().split(','))):errors.append(f"Room requirement failure for {e.get('uid')}.")
  start=e.get('start_utc','');end=e.get('end_utc','')
  clashes=[r for r in reservations+planned if r['room_id']==e.get('room_id') and r['uid']!=e.get('uid') and start<r['end_utc'] and end>r['start_utc']]
  if clashes:errors.append(f"Room/time conflict for {e.get('uid')}.")
  if start and end:planned.append({"uid":e['uid'],"room_id":e.get('room_id'),"start_utc":start,"end_utc":end})
  choices=[]
  if req:
   for r in roomrows.values():
    if int(r['capacity'])<int(req['attendee_count']) or not need.issubset(set(r['features'].lower().split(','))):continue
    if not any(x['room_id']==r['room_id'] and x['uid']!=e.get('uid') and start<x['end_utc'] and end>x['start_utc'] for x in reservations+planned):choices.append(r['room_id'])
  options[e.get('uid','')]=choices
 c.close();return errors,options
def preview(root,owner,events):
 if owner not in ('customer','training'):return {"error":"invalid_scope"},400
 rev=revision(root);errors,options=conflict_check(root,owner,events);token=uuid.uuid4().hex
 c=connect(root);c.execute("INSERT INTO preview_tokens VALUES(?,?,?,?,?)",(token,owner,rev,json.dumps(events,sort_keys=True),"PREVIEWED"));c.commit();c.close()
 return {"token":token,"revision":rev,"conflicts":errors,"available_rooms":options,"ready":not errors},200
def confirm(root,token,events):
 with LOCK:
  c=connect(root);t=c.execute("SELECT * FROM preview_tokens WHERE token=? AND status='PREVIEWED'",(token,)).fetchone()
  if not t:c.close();return {"error":"unknown_or_used_preview"},409
  now=revision(root)
  if now!=t['revision']:c.execute("UPDATE preview_tokens SET status='STALE' WHERE token=?",(token,));c.commit();c.close();return {"error":"stale_revision","revision":now},409
  if json.dumps(events,sort_keys=True)!=t['payload_json']:c.close();return {"error":"payload_differs_from_preview"},409
  errors,options=conflict_check(root,t['owner'],events)
  if errors:c.close();return {"error":"validation_failed","conflicts":errors,"available_rooms":options},409
  confirmation_id=uuid.uuid4().hex
  try:
   for e in events:
    c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?)",(e['uid'],e['room_id'],e['start_utc'],e['end_utc'],'CONFIRMED',t['owner']))
    c.execute("INSERT INTO confirmations VALUES(?,?,?)",(e['uid'],token,confirmation_id))
   c.execute("UPDATE preview_tokens SET status='CONFIRMED' WHERE token=?",(token,));c.commit()
  except sqlite3.Error:
   c.rollback();c.close();return {"error":"reservation_commit_failed"},409
  c.close()
  old=(root/"team_schedule.ics").read_text(encoding='utf-8');lines=[]
  for e in events:lines.extend(["BEGIN:VEVENT",f"UID:{e['uid']}",f"DTSTART:{e['start_utc']}",f"DTEND:{e['end_utc']}",f"SUMMARY:{e['summary']}",f"ROOM:{e['room_id']}",f"ATTENDEE:{e['attendee']}","END:VEVENT"])
  updated=old.replace("END:VCALENDAR","\r\n".join(lines)+"\r\nEND:VCALENDAR")
  tmp=root/"team_schedule.ics.tmp";tmp.write_text(updated,encoding='utf-8');tmp.replace(root/"team_schedule.ics")
  return {"confirmed_uids":[e['uid'] for e in events],"confirmation_id":confirmation_id,"revision":revision(root)},200
class Handler(BaseHTTPRequestHandler):
 def respond(self,status,obj,kind='application/json; charset=utf-8'):
  b=obj if isinstance(obj,bytes) else json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  u=urlparse(self.path);q=parse_qs(u.query)
  if u.path=='/health':return self.respond(200,{"status":"ok"})
  if u.path=='/mail':
   team=q.get('team',['customer'])[0]
   if team not in ('customer','training'):return self.respond(400,{"error":"invalid_scope"})
   if 'text/html' in self.headers.get('Accept',''):
    return self.respond(200,f"<!doctype html><meta charset='utf-8'><title>Maildesk Calendar</title><h1>Calendar Maildesk</h1><p>{team.title()} inbox</p><ul>"+''.join(f"<li>{r['thread_id']} — {r['subject']} — latest confirmed update</li>" for r in load_mail(self.server.root,team))+"</ul><a href='/calendar'>Calendar</a>","text/html; charset=utf-8")
   return self.respond(200,load_mail(self.server.root,team))
  if u.path=='/calendar':return self.respond(200,(self.server.root/'team_schedule.ics').read_bytes(),'text/calendar; charset=utf-8')
  if u.path=='/export':
   team=q.get('team',[''])[0];c=connect(self.server.root);rows=[dict(r) for r in c.execute("SELECT uid,room_id,start_utc,end_utc,owner_ref FROM reservations WHERE status='CONFIRMED' AND owner_ref=?",(team,))];c.close();return self.respond(200,{"events":rows})
  return self.respond(404,{"error":"not_found"})
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));data=json.loads(self.rfile.read(n) or b'{}');u=urlparse(self.path)
  if u.path=='/preview':obj,status=preview(self.server.root,data.get('owner',''),data.get('events',[]))
  elif u.path=='/confirm':obj,status=confirm(self.server.root,data.get('token',''),data.get('events',[]))
  else:obj,status={"error":"not_found"},404
  return self.respond(status,obj)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();Handler.server=type('Server',(),{})();srv=ThreadingHTTPServer(('127.0.0.1',18110),Handler);srv.root=Path(a.root);srv.serve_forever()
if __name__=='__main__':main()
