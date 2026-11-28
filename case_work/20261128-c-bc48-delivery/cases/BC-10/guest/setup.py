from __future__ import annotations
import argparse,csv,sqlite3,subprocess,sys
from pathlib import Path

ROOMS=[("CEDAR",10,"projector,whiteboard"),("BIRCH",12,"projector,whiteboard,vc"),("MAPLE",8,"vc,whiteboard"),("ATLAS",16,"projector,vc,whiteboard")]
MEETINGS=[
 ("CR-101","customer","2026-12-02 09:00","-05:00",60,8,"projector","Client review with Orion Labs","orion@example.invalid"),
 ("CR-104","customer","2026-12-03 08:30","+00:00",60,6,"vc","Renewal review with Cedar Group","cedar@example.invalid"),
 ("CR-108","customer","2026-12-04 11:00","-05:00",60,13,"projector,vc","Escalation review with Northstar","northstar@example.invalid"),
 ("TS-201","training","2026-12-02 09:00","-05:00",60,9,"projector","Product certification workshop","training@example.invalid"),
 ("TS-203","training","2026-12-03 08:30","+00:00",60,11,"vc","Support readiness clinic","support@example.invalid"),
 ("TS-207","training","2026-12-05 10:15","-05:00",90,7,"vc,whiteboard","Weekend escalation drill","response@example.invalid"),
]
def pdf(path,lines):
 s=("BT /F1 10 Tf 48 748 Td "+" ".join(f"({x.replace('(','[').replace(')',']')}) Tj 0 -16 Td" for x in lines)+" ET").encode("ascii","replace");o=bytearray(b"%PDF-1.4\n");objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(s)).encode()+b" >>\nstream\n"+s+b"\nendstream"];offs=[0]
 for i,x in enumerate(objs,1):offs.append(len(o));o.extend(f"{i} 0 obj\n".encode()+x+b"\nendobj\n")
 x=len(o);o.extend(f"xref\n0 {len(offs)}\n0000000000 65535 f \n".encode());[o.extend(f"{n:010d} 00000 n \n".encode()) for n in offs[1:]];o.extend(f"trailer\n<< /Size {len(offs)} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode());path.write_bytes(o)
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True);p.add_argument('--workspace',required=True);p.add_argument('--start-service',action='store_true');p.add_argument('--open-browser',action='store_true');a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"calendar";root.mkdir(parents=True,exist_ok=True);(root/"out").mkdir(exist_ok=True)
 db=sqlite3.connect(root/"rooms.db");db.executescript("CREATE TABLE rooms(room_id TEXT PRIMARY KEY,capacity INTEGER,features TEXT,building TEXT);CREATE TABLE reservations(uid TEXT PRIMARY KEY,room_id TEXT,start_utc TEXT,end_utc TEXT,status TEXT,owner_ref TEXT);CREATE TABLE preview_tokens(token TEXT PRIMARY KEY,owner TEXT,revision TEXT,payload_json TEXT,status TEXT);CREATE TABLE confirmations(uid TEXT PRIMARY KEY,token TEXT,confirmation_id TEXT NOT NULL);")
 db.executemany("INSERT INTO rooms VALUES(?,?,?,?)",[(r[0],r[1],r[2],"HQ") for r in ROOMS]);db.execute("INSERT INTO reservations VALUES('BASE-900','MAPLE','2026-12-03T09:00:00Z','2026-12-03T10:00:00Z','CONFIRMED','facilities')");db.commit();db.close()
 with (root/"mail_threads.csv").open('w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(["team","thread_id","message_version","state","event_uid","local_start","utc_offset","duration_min","attendee_count","features","subject","attendee"])
  for uid,team,local,offset,dur,cap,feat,subject,att in MEETINGS:
   w.writerow([team,uid,"1","DRAFT",uid,local,offset,dur,cap,feat,subject,att]);w.writerow([team,uid,"2","CANCELLED",uid,local,offset,dur,cap,feat,"Cancellation notice - superseded",att]);w.writerow([team,uid,"3","CONFIRMED",uid,local,offset,dur,cap,feat,subject,att])
  w.writerow(["customer","CR-101","4","DRAFT","CR-101","2026-12-07 09:00","-05:00",60,8,"projector","Old time proposal","orion@example.invalid"])
  w.writerow(["training","TS-201","4","DRAFT","TS-201","2026-12-08 09:00","-05:00",60,9,"projector","Cancelled follow-up draft","training@example.invalid"])
 (root/"team_schedule.ics").write_text("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//BC-10//EN\r\nBEGIN:VEVENT\r\nUID:BASE-900\r\nDTSTART:20261203T090000Z\r\nDTEND:20261203T100000Z\r\nSUMMARY:Facilities hold\r\nROOM:MAPLE\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n",encoding='utf-8')
 pdf(root/"room_policy.pdf",["NORTHSTAR ROOM BOOKING POLICY","Use latest CONFIRMED non-cancelled thread message; ignore DRAFT and CANCELLED versions.","Convert local start to UTC using the explicit signed UTC offset. End time equals start plus duration.","Choose rooms whose capacity and every requested feature are satisfied.","Do not overlap existing confirmed reservations. Room comparison is case-insensitive.","Preview before confirmation. Confirm only with the most recent revision token.","Meeting UID, attendee, UTC start/end, and chosen room must match the source thread."])
 if a.start_service:
  log=(root/"calendar_service.log").open('ab',buffering=0);proc=subprocess.Popen([sys.executable,str(Path(a.source_dir)/"calendar_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18110/mail?team=customer"],start_new_session=True)
if __name__=='__main__':main()
