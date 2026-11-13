#!/usr/bin/env python3
"""Deterministic incident-review clip frames and shared-player seed state."""
import json, os, shutil, sqlite3, sys
HERE=os.path.dirname(os.path.abspath(__file__))
FRAMES=[
(1,"00:00","Pre-shift overview","The loading bay is clear. All indicators are green; the marked pedestrian lane is empty.","Bay 4"),
(2,"00:12","Forklift and pedestrian","A loaded forklift enters the blue pedestrian crossing while an employee is still walking through it.","Crossing A"),
(3,"00:24","Conveyor C7 indicator","Conveyor C7 is stopped, but its red warning beacon stays lit after the reset button is pressed.","Conveyor C7"),
(4,"00:36","Emergency exit E2","Two loaded pallets are parked across the yellow keep-clear hatch in front of Exit E2.","Exit E2"),
(5,"00:48","Dock leveller control","The dock leveller is unloaded, yet its fault lamp remains red and the platform does not return level.","Dock 4"),
(6,"01:00","Pedestrian PPE","An employee enters the striped forklift operating zone without a high-visibility vest.","Crossing B"),
(7,"01:12","Roller shutter at Door 4","The roller shutter starts closing, stops halfway and remains open despite a second close command.","Door 4"),
(8,"01:24","Reversing vehicle","A forklift reverses around a blind corner with no spotter visible and no warning horn.","Aisle 3"),
(9,"01:36","Hydraulic leak","A fresh fluid pool is visible below the right hydraulic hose connection on the dock lift.","Dock lift"),
(10,"01:48","Clear transfer","A pallet jack moves through the marked route; pedestrians remain outside the vehicle lane.","Aisle 2"),
(11,"02:00","Conveyor belt guard","The left-side guard panel is missing from the moving conveyor belt; the drive motor is running.","Conveyor C7"),
(12,"02:12","Routine scan","An operator scans a sealed carton at the receiving desk. No abnormal condition is visible.","Receiving desk"),
(13,"02:24","End of clip","The bay is quiet. The warning board lists routine checks only.","Bay 4"),
]
SAFETY=[2,4,6,8]
MAINT=[3,5,7,9,11]
def build(out_dir):
 os.makedirs(out_dir,exist_ok=True)
 shutil.copyfile(os.path.join(HERE,"app_v1.py"),os.path.join(out_dir,"app_v1.py"))
 db=os.path.join(out_dir,"seed.db")
 if os.path.exists(db): os.remove(db)
 con=sqlite3.connect(db)
 con.executescript("CREATE TABLE frames(frame_no INTEGER PRIMARY KEY,timecode TEXT,title TEXT,observation TEXT,location TEXT);CREATE TABLE session_state(id INTEGER PRIMARY KEY CHECK(id=1),frame_no INTEGER NOT NULL);CREATE TABLE markers(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,frame_no INTEGER,timecode TEXT,note TEXT);CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,details TEXT);")
 con.executemany("INSERT INTO frames VALUES(?,?,?,?,?)",FRAMES)
 con.execute("INSERT INTO session_state VALUES(1,1)")
 con.commit();con.close()
 exp={"safety":{"category":"Safety follow-up","frames":[{"frame":n,"timecode":FRAMES[n-1][1]} for n in SAFETY]},
      "maintenance":{"category":"Maintenance","frames":[{"frame":n,"timecode":FRAMES[n-1][1]} for n in MAINT]}}
 with open(os.path.join(out_dir,"expected.json"),"w") as f: json.dump(exp,f,indent=2)
if __name__=="__main__": build(sys.argv[1])
