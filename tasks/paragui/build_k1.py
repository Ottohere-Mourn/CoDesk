"""Deterministic COURT-SERVICE1 docket fixture."""
import json,os,shutil,sqlite3,sys
HERE=os.path.dirname(os.path.abspath(__file__));sys.path.insert(0,HERE)
from lib_w import fresh_db
CASES=[("SC-193","Northside Dental LLC","Willow Craft Studio",780.00,"2026-12-10","Awaiting service"),("SC-208","Aster HVAC LLC","Vale Apartments LLC",1240.00,"2026-11-30","Ready for filing")]
def build(out_dir):
 os.makedirs(out_dir,exist_ok=True);shutil.copyfile(os.path.join(HERE,"app_k1.py"),os.path.join(out_dir,"app_k1.py"))
 con,app=fresh_db(HERE,"app_k1.py",f"{out_dir}/seed.db");con.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?)",CASES)
 con.execute("INSERT INTO desk_state VALUES(1,'SC-193')");con.commit();con.close()
 json.dump({"filing":{"case_id":"SC-208","plaintiff":"Aster HVAC LLC","defendant":"Vale Apartments LLC","amount":1240.00,"attachment":"complaint_SC208.pdf","status":"Ready for clerk check"},
 "service":{"case_id":"SC-193","service_date":"2026-11-08","method":"Personal service","server_id":"PS-441","outcome":"Served"}},open(f"{out_dir}/expected.json","w"),indent=2)
if __name__=="__main__":build(sys.argv[1])
