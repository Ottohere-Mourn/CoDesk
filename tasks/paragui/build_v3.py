#!/usr/bin/env python3
"""Build the deterministic shared volunteer roster and mileage claims fixture."""
import argparse, json, os, shutil, sqlite3
HERE=os.path.dirname(os.path.abspath(__file__))
PEOPLE=[
("V-214","Ada Bell",6.5,"Check-in","08:00-10:00"),
("V-238","Ben Carter",12.0,"Produce","08:00-11:00"),
("V-251","Chi Diaz",18.0,"Bagging","09:00-12:00"),
("V-267","Devon Evans",31.5,"Check-in","10:00-12:00"),
("V-299","Eli Flores",40.0,"Driver","07:30-11:30"),
("V-304","Faye Grant",9.5,"Cold storage","08:00-11:00"),
]
def build(out):
 os.makedirs(out,exist_ok=True)
 shutil.copyfile(os.path.join(HERE,"app_v3.py"),os.path.join(out,"app_v3.py"))
 db=os.path.join(out,"seed.db")
 if os.path.exists(db):os.remove(db)
 con=sqlite3.connect(db)
 con.executescript("""CREATE TABLE volunteers(id TEXT PRIMARY KEY,name TEXT,mileage REAL,shift_station TEXT DEFAULT '',shift_window TEXT DEFAULT '',shift_status TEXT DEFAULT '',claim_amount REAL,claim_status TEXT DEFAULT '',claim_note TEXT DEFAULT '');CREATE TABLE desk(id INTEGER PRIMARY KEY CHECK(id=1),active_volunteer_id TEXT,active_panel TEXT);CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT,volunteer_id TEXT,panel TEXT,payload TEXT,ts TEXT DEFAULT CURRENT_TIMESTAMP);""")
 con.executemany("INSERT INTO volunteers(id,name,mileage) VALUES(?,?,?)",[(i,n,m) for i,n,m,_,_ in PEOPLE])
 con.execute("INSERT INTO desk VALUES(1,?,'shift')",(PEOPLE[0][0],))
 con.commit();con.close()
 shifts=[{"id":i,"name":n,"station":station,"window":window,"status":"CONFIRMED"} for i,n,m,station,window in PEOPLE]
 miles=[{"id":i,"name":n,"miles":m,"amount":round(m*0.67+1e-9,2),"decision":"APPROVED" if m*0.67<=25 else "REVIEW","note":"Verified from signed slip."} for i,n,m,_,_ in PEOPLE]
 with open(os.path.join(out,"expected.json"),"w",encoding="utf-8") as f:json.dump({"shift":{"rows":shifts},"mileage":{"rows":miles}},f,indent=2)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);build(p.parse_args().out)
