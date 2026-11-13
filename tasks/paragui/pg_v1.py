"""Shared clip-review setup and independent task oracles."""
import requests
from evaluation_examples.task_class.pg_common import HOME, expected, open_chrome, result, sh, sql, start_webapp, webapp_db
NAME,PORT="v1",8135
URL=f"http://127.0.0.1:{PORT}/"
MARKER=f"{HOME}/.codesk-video-review1-setup-v1"
def _already_open(sc):
    response=requests.post(f"http://{sc.vm_ip}:{sc.server_port}/execute",
        json={"command":["bash","-lc",f"test -f {MARKER} && echo V1_READY"],"shell":False,"timeout":20},timeout=25)
    response.raise_for_status()
    return "V1_READY" in (response.json().get("output") or "")
def setup(sc):
    # One Chrome tab and one shared web app state for the complete pair.
    if _already_open(sc):
        return
    start_webapp(sc,"v1/app_v1.py",NAME,PORT,"v1/seed.db")
    open_chrome(sc,[URL])
    sh(sc,f"touch {MARKER}")
def state(env):
    return sql(env,webapp_db(NAME),{
        "markers":"SELECT category,frame_no,timecode,note FROM markers ORDER BY id",
        "events":"SELECT id,kind,details FROM events ORDER BY id",
        "current":"SELECT frame_no FROM session_state WHERE id=1"})
def evaluate_safety(env,dest):
    from evaluation_examples.task_class.pg_v1_oracle import safety_checks
    checks,score=safety_checks(state(env),expected(NAME));return result(score,checks)
def evaluate_maintenance(env,dest):
    from evaluation_examples.task_class.pg_v1_oracle import maintenance_checks
    checks,score=maintenance_checks(state(env),expected(NAME));return result(score,checks)
