import json,sqlite3
from tasks.paragui.build_k1 import build
from tasks.paragui.pg_k1_oracle import filing_checks,service_checks
def fixture(tmp_path):
 d=tmp_path/"k1";build(str(d));return d/"seed.db",json.loads((d/"expected.json").read_text())
def state(db):
 c=sqlite3.connect(db);c.row_factory=sqlite3.Row
 out={k:[dict(r) for r in c.execute(q)] for k,q in {"filings":"SELECT case_id,plaintiff,defendant,amount,attachment,status FROM filings","services":"SELECT case_id,service_date,method,server_id,outcome FROM services"}.items()};c.close();return out
def test_filing_reference_passes(tmp_path):
 db,exp=fixture(tmp_path);c=sqlite3.connect(db);w=exp["filing"]
 c.execute("INSERT INTO filings VALUES(?,?,?,?,?,?,?)",(w["case_id"],w["plaintiff"],w["defendant"],w["amount"],w["attachment"],w["status"],"t"));c.commit();c.close()
 checks,score=filing_checks(state(db),exp);assert score==1.0 and all(checks.values())
def test_wrong_active_case_does_not_pass(tmp_path):
 db,exp=fixture(tmp_path);c=sqlite3.connect(db);w=exp["filing"]
 c.execute("INSERT INTO filings VALUES(?,?,?,?,?,?,?)",("SC-193",w["plaintiff"],w["defendant"],w["amount"],w["attachment"],w["status"],"t"));c.commit();c.close()
 checks,score=filing_checks(state(db),exp);assert score==0.0 and checks["saved_to_SC208"] is False
