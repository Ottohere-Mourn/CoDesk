#!/usr/bin/env python3
"""Deterministic warehouse bin-label and parcel-label work queue."""
import json,os,shutil,sqlite3,sys
HERE=os.path.dirname(os.path.abspath(__file__))
BINS=[
("B-104","bin","Aisle 1 | Bin 04 | SKU 731-AX | Slot count 18",2),
("B-118","bin","Aisle 1 | Bin 18 | SKU 205-QM | Slot count 7",1),
("B-203","bin","Aisle 2 | Bin 03 | SKU 418-LP | Slot count 24",3),
("B-417","bin","Aisle 4 | Bin 17 | SKU 966-RC | Slot count 11",2),
("B-512","bin","Aisle 5 | Bin 12 | SKU 332-TN | Slot count 5",1),
]
PARCELS=[
("P-6201","parcel","Order 6201 | Northside Clinic | Examination gloves",3),
("P-6207","parcel","Order 6207 | Pine Street Books | Returns carton",2),
("P-6214","parcel","Order 6214 | River Depot | Hose fittings",1),
("P-6228","parcel","Order 6228 | Metro Repair | Bearing kit",4),
("P-6233","parcel","Order 6233 | Fern Market | Display stands",2),
]
def build(out_dir):
 os.makedirs(out_dir,exist_ok=True)
 shutil.copyfile(os.path.join(HERE,"app_v2.py"),os.path.join(out_dir,"app_v2.py"))
 db=os.path.join(out_dir,"seed.db")
 if os.path.exists(db):os.remove(db)
 con=sqlite3.connect(db)
 con.executescript("CREATE TABLE labels(id INTEGER PRIMARY KEY,code TEXT,kind TEXT,description TEXT,required_copies INTEGER);CREATE TABLE station(id INTEGER PRIMARY KEY CHECK(id=1),profile TEXT);CREATE TABLE jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,label_id INTEGER,profile TEXT,copies INTEGER);CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,value TEXT);")
 rows=BINS+PARCELS
 con.executemany("INSERT INTO labels(code,kind,description,required_copies) VALUES(?,?,?,?)",rows)
 con.execute("INSERT INTO station VALUES(1,'BIN_2X1')");con.commit()
 labels=[{"id":i+1,"code":r[0],"kind":r[1],"description":r[2],"copies":r[3]} for i,r in enumerate(rows)]
 with open(os.path.join(out_dir,"expected.json"),"w",encoding="utf-8") as f:
  json.dump({"bins":{"profile":"BIN_2X1","labels":[x for x in labels if x["kind"]=="bin"]},"parcels":{"profile":"PARCEL_4X6","labels":[x for x in labels if x["kind"]=="parcel"]}},f,indent=2)
 con.close()
if __name__=="__main__":build(sys.argv[1])
