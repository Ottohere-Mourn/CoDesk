"""Paired browser-tab setup and host-side deterministic evaluation for CONC-05."""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc05_grade import grade

ROOT=f"{C.HOME}/.cache/paragui/conc05";STATE="/tmp/conc05-runtime/state.json"
URLS=["http://127.0.0.1:18101/docs","http://127.0.0.1:18101/form","http://127.0.0.1:18102/legacy","http://127.0.0.1:18102/editor"]
FILES=[("CONC-05/service.py",f"{ROOT}/service.py"),*[(f"CONC-05/guest/in_a/onboarding_forms/application_{i:02d}.png",f"{ROOT}/applications/application_{i:02d}.png") for i in range(1,5)]]

def setup(sc):
    C.upload(sc,FILES)
    C.sh(sc,f"""mkdir -p {ROOT}/applications /tmp/conc05-runtime /home/user/workspace/out_a /home/user/workspace/out_b
if ! curl -sf -m 1 http://127.0.0.1:18101/health >/dev/null || ! curl -sf -m 1 http://127.0.0.1:18102/health >/dev/null; then
  setsid -f python3 {ROOT}/service.py --assets {ROOT}/applications --out /home/user/workspace --state {STATE} >{ROOT}/service.log 2>&1 < /dev/null
fi
for i in $(seq 30); do curl -sf -m 1 http://127.0.0.1:18101/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18102/health >/dev/null && break; sleep 1; done
curl -sf -m 2 http://127.0.0.1:18101/health >/dev/null && curl -sf -m 2 http://127.0.0.1:18102/health >/dev/null""")
    if not getattr(setup,"_chrome_started",False):
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1",shell=True)
        C.open_chrome(sc,URLS)
        setup._chrome_started=True

def _evaluate(env,role):
    base=Path(os.environ.get("CONC05_EVAL_OUT",tempfile.mkdtemp(prefix="conc05-eval-")));out=base/f"actor-{role}";out.mkdir(parents=True,exist_ok=True)
    name="crm_records.json" if role=="a" else "wiki_migrated.json";folder=f"out_{role}"
    workspace=out/"workspace";dest=workspace/folder/name;dest.parent.mkdir(parents=True,exist_ok=True)
    try:C.fetch(env,f"/home/user/workspace/{folder}/{name}",str(dest))
    except Exception:pass
    state={}
    try:
        C.fetch(env,STATE,str(out/"state.json"));state=json.loads((out/"state.json").read_text(encoding="utf-8"))
    except Exception:pass
    result=grade(workspace,state)
    (out/"checks.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    key="actor_a" if role=="a" else "actor_b"
    return C.result(result[key],{"checks":result["checks"][key],"flags":result["flags"],"dropdown_dismiss_count":result["dropdown_dismiss_count"],"clipboard_event_count":result["clipboard_event_count"]})

def evaluate_actor_a(env):return _evaluate(env,"a")
def evaluate_actor_b(env):return _evaluate(env,"b")
