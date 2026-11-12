"""Deterministic synthetic seed for SHELTER-INTAKE1."""
from __future__ import annotations
import json, os, sqlite3, sys, shutil
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from lib_w import copy_app, fresh_db

FAMILIES=[
 ('H-101','Marlow household',2,1,0,0,'One quiet sleeping area preferred.'),
 ('H-102','Okafor household',1,0,1,0,'Wheelchair user; needs step-free route and accessible washroom.'),
 ('H-103','Chen household',2,2,0,0,'Keep all four household members together.'),
 ('H-104','Rivera household',1,0,0,1,'Travels with a trained companion animal.'),
]
ROOMS=[
 ('CR-201','Cedar 201',4,1,0,'Open','Cedar'),
 ('CR-203','Cedar 203',2,1,0,'Open','Cedar'),
 ('MP-105','Maple 105',3,0,1,'Open','Maple'),
 ('MP-106','Maple 106',3,0,0,'Open','Maple'),
 ('MP-108','Maple 108',2,1,1,'Open','Maple'),
]
def build(out_dir):
 os.makedirs(out_dir,exist_ok=True); shutil.copyfile(os.path.join(HERE,'app_s1.py'),os.path.join(out_dir,'app_s1.py'))
 con,app=fresh_db(HERE,'app_s1.py',f'{out_dir}/seed.db')
 con.executemany('INSERT INTO families VALUES(?,?,?,?,?,?,?)',FAMILIES)
 con.executemany('INSERT INTO rooms VALUES(?,?,?,?,?,?,?)',ROOMS); con.commit(); con.close()
 json.dump({'families':{r[0]:{'occupants':r[2]+r[3],'accessible':bool(r[4]),'companion':bool(r[5])} for r in FAMILIES},
            'rooms':{r[0]:{'capacity':r[2],'accessible':bool(r[3]),'companion':bool(r[4]),'status':r[5]} for r in ROOMS},
            'required_closure':{'room':'CR-201','inspection':'SAFE-204','reason':'Electrical burning odor at west outlet'}},
           open(f'{out_dir}/expected.json','w'),indent=2)
if __name__=='__main__': build(sys.argv[1])
