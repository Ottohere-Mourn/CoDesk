import json,sqlite3
from tasks.paragui.build_k2 import build
from tasks.paragui.pg_k2_oracle import route_checks,update_checks
def fixture(tmp_path):
 d=tmp_path/"k2";build(str(d));return d/"seed.db",json.loads((d/"expected.json").read_text())
def state(db):
 c=sqlite3.connect(db);c.row_factory=sqlite3.Row
 out={k:[dict(r) for r in c.execute(q)] for k,q in {"routes":"SELECT route_id,service_date,vehicle,depart_time,status FROM routes",
 "stops":"SELECT route_id,position,job_id FROM route_stops","jobs":"SELECT id,service_date,status,note FROM jobs"}.items()};c.close();return out
def test_route_reference_passes_before_customer_update(tmp_path):
 db,exp=fixture(tmp_path);c=sqlite3.connect(db);w=exp["route"]
 c.execute("INSERT INTO routes VALUES(?,?,?,?,?,?)",(w["route_id"],w["service_date"],w["vehicle"],w["depart_time"],w["status"],"t"))
 c.executemany("INSERT INTO route_stops VALUES(?,?,?)",[(w["route_id"],i+1,j) for i,j in enumerate(w["sequence"])]);c.commit();c.close()
 checks,score=route_checks(state(db),exp);assert score==1.0 and all(checks.values())
def test_later_deferral_invalidates_old_route_and_update_passes(tmp_path):
 db,exp=fixture(tmp_path);c=sqlite3.connect(db);rw=exp["route"];uw=exp["update"]
 c.execute("INSERT INTO routes VALUES(?,?,?,?,?,?)",(rw["route_id"],rw["service_date"],rw["vehicle"],rw["depart_time"],rw["status"],"t"))
 c.executemany("INSERT INTO route_stops VALUES(?,?,?)",[(rw["route_id"],i+1,j) for i,j in enumerate(rw["sequence"])])
 c.execute("UPDATE jobs SET service_date=?,status=?,note=? WHERE id=?",(uw["service_date"],uw["status"],uw["note"],uw["job_id"]));c.commit();c.close()
 rc,rs=route_checks(state(db),exp);uc,us=update_checks(state(db),exp)
 assert rs<1 and rc["every_stop_still_scheduled"] is False
 assert us==1 and all(uc.values())
