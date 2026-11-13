"""Shared setup and deterministic oracle adapters for COMMUNITY-PANTRY1."""
import requests
from evaluation_examples.task_class import pg_common as pc
NAME,PORT="v3",8138
URL=f"http://127.0.0.1:{PORT}/desk"
MARKER=f"{pc.HOME}/.codesk-community-pantry1-setup-v3"
def _already_open(sc):
 r=requests.post(f"http://{sc.vm_ip}:{sc.server_port}/execute",json={"command":["bash","-lc",f"test -f {MARKER} && echo V3_READY"],"shell":False,"timeout":20},timeout=25)
 r.raise_for_status();return "V3_READY" in (r.json().get("output") or "")
def setup(sc):
 if _already_open(sc):return
 pc.start_webapp(sc,"v3/app_v3.py",NAME,PORT,"v3/seed.db")
 pc.open_chrome(sc,[URL])
 pc.sh(sc,f"touch {MARKER}")
def state(env):
 return pc.sql(env,pc.webapp_db(NAME),{"volunteers":"SELECT id,name,mileage,shift_station,shift_window,shift_status,claim_amount,claim_status,claim_note FROM volunteers ORDER BY id","desk":"SELECT active_volunteer_id,active_panel FROM desk WHERE id=1","events":"SELECT id,event,volunteer_id,panel,payload FROM events ORDER BY id"})
def evaluate_shift(env,dest):
 from evaluation_examples.task_class.pg_v3_oracle import checks
 c,s=checks(state(env),pc.expected(NAME),"shift");return pc.result(s,c)
def evaluate_mileage(env,dest):
 from evaluation_examples.task_class.pg_v3_oracle import checks
 c,s=checks(state(env),pc.expected(NAME),"mileage");return pc.result(s,c)
