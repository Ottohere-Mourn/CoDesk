"""Shared warehouse label setup and task-specific evaluators."""
import requests
from evaluation_examples.task_class.pg_common import HOME,expected,open_chrome,result,sh,sql,start_webapp,webapp_db
NAME,PORT="v2",8136
URL=f"http://127.0.0.1:{PORT}/desk"
MARKER=f"{HOME}/.codesk-warehouse-label1-setup-v2"
def _already_open(sc):
 response=requests.post(f"http://{sc.vm_ip}:{sc.server_port}/execute",json={"command":["bash","-lc",f"test -f {MARKER} && echo V2_READY"],"shell":False,"timeout":20},timeout=25)
 response.raise_for_status();return "V2_READY" in (response.json().get("output") or "")
def setup(sc):
 if _already_open(sc):return
 start_webapp(sc,"v2/app_v2.py",NAME,PORT,"v2/seed.db");open_chrome(sc,[URL]);sh(sc,f"touch {MARKER}")
def state(env):
 return sql(env,webapp_db(NAME),{"jobs":"SELECT label_id,profile,copies FROM jobs ORDER BY id","labels":"SELECT id,code,kind,description,required_copies FROM labels ORDER BY id","events":"SELECT id,kind,value FROM events ORDER BY id","profile":"SELECT profile FROM station WHERE id=1"})
def evaluate_bins(env,dest):
 from evaluation_examples.task_class.pg_v2_oracle import checks
 c,s=checks(state(env),expected(NAME),"bins");return result(s,c)
def evaluate_parcels(env,dest):
 from evaluation_examples.task_class.pg_v2_oracle import checks
 c,s=checks(state(env),expected(NAME),"parcels");return result(s,c)
