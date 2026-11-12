"""Deterministic route/dispatch fixture for ROUTE-RECON1."""
import json,os,shutil,sys
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
from lib_w import fresh_db
JOBS=[("WO-501","Harbor Clinic","10 Bay St","2026-11-13","08:30-10:00","High","Scheduled",""),
("WO-502","Pine Library","22 Oak Ave","2026-11-13","09:00-11:00","Normal","Scheduled",""),
("WO-503","Riverside Hall","48 River Rd","2026-11-13","10:00-12:00","High","Scheduled",""),
("WO-504","West End Market","7 Market Sq","2026-11-13","11:00-13:00","Normal","Scheduled","")]
def build(out_dir):
 os.makedirs(out_dir,exist_ok=True);shutil.copyfile(os.path.join(HERE,"app_k2.py"),os.path.join(out_dir,"app_k2.py"))
 con,app=fresh_db(HERE,"app_k2.py",f"{out_dir}/seed.db");con.executemany("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",JOBS)
 con.executemany("INSERT INTO manifest VALUES('RTE-17',?,?)",[(i+1,r[0]) for i,r in enumerate(JOBS)])
 con.commit();con.close()
 json.dump({"route":{"route_id":"RTE-17","service_date":"2026-11-13","vehicle":"Van 4","depart_time":"08:00","status":"Draft","sequence":[r[0] for r in JOBS]},
 "update":{"job_id":"WO-503","status":"Deferred","service_date":"2026-11-14","note":"Customer requested Saturday access; no Friday attendance."}},open(f"{out_dir}/expected.json","w"),indent=2)
if __name__=="__main__":build(sys.argv[1])
