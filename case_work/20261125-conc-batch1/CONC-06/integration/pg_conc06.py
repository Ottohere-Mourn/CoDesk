"""Shared setup and deterministic host-side evaluation for CONC-06."""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc06_grade import grade
ROOT=f"{C.HOME}/.cache/paragui/conc06";STATE="/tmp/conc06-runtime/state.json"
URLS=["http://127.0.0.1:18121/","http://127.0.0.1:18122/"]
FILES=[("CONC-06/service.py",f"{ROOT}/service.py"),
       ("CONC-06/guest/out_b/Summit_Brochure.pptx",f"{ROOT}/Summit_Brochure.pptx"),
       ("CONC-06/guest/in_b/agenda_errata.txt",f"{ROOT}/agenda_errata.txt"),
       *[(f"CONC-06/guest/in_a/bi/{x}.csv",f"{ROOT}/assets/{x}.csv") for x in ("NA-Q3","EU-Q3","APAC-Q4","LATAM-Q4")],
       *[(f"CONC-06/guest/in_a/bi/{x}.png",f"{ROOT}/assets/{x}.png") for x in ("NA-Q3","EU-Q3","APAC-Q4","LATAM-Q4")],
       *[(f"CONC-06/guest/in_b/assets/{x}.png",f"{ROOT}/assets/{x}.png") for x in ("Summit_Keynote","Summit_TrackA","Summit_TrackB","Summit_Roadmap")]]
def setup(sc):
    C.upload(sc,FILES)
    deck="/home/user/workspace/out_b/Summit_Brochure.pptx"
    C.sh(sc,f"""mkdir -p {ROOT}/assets /tmp/conc06-runtime /home/user/workspace/in_b /home/user/workspace/out_a/bi_pack /home/user/workspace/out_b
cp {ROOT}/Summit_Brochure.pptx {deck}; cp {ROOT}/agenda_errata.txt /home/user/workspace/in_b/agenda_errata.txt
for i in $(seq 1 25); do curl -sf -m 1 http://127.0.0.1:18121/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18122/health >/dev/null && break; sleep 1; done
if ! curl -sf -m 1 http://127.0.0.1:18121/health >/dev/null; then setsid -f python3 {ROOT}/service.py --assets {ROOT}/assets --state {STATE} >{ROOT}/service.log 2>&1 < /dev/null; fi
for i in $(seq 1 25); do curl -sf -m 1 http://127.0.0.1:18121/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18122/health >/dev/null && break; sleep 1; done
curl -sf -m 2 http://127.0.0.1:18121/health >/dev/null && curl -sf -m 2 http://127.0.0.1:18122/health >/dev/null
if ! pgrep -x soffice.bin >/dev/null; then setsid -f libreoffice --impress {deck} >{ROOT}/soffice.log 2>&1 < /dev/null; fi""")
    if not getattr(setup,"_chrome_started",False):
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1",shell=True)
        C.open_chrome(sc,URLS);setup._chrome_started=True
def _eval(env,actor):
    base=Path(os.environ.get("CONC06_EVAL_OUT",tempfile.mkdtemp(prefix="conc06-eval-")));out=base/f"actor-{actor}";out.mkdir(parents=True,exist_ok=True)
    folder=f"out_{actor}";workspace=out/"workspace";workspace.mkdir(parents=True,exist_ok=True)
    if actor=="a":
        try:C.fetch(env,"/home/user/workspace/out_a/bi_audit.json",str(workspace/"out_a/bi_audit.json"))
        except Exception:pass
        for name in ("NA-Q3.csv","EU-Q3.csv","APAC-Q4.csv","LATAM-Q4.csv","NA-Q3.png","EU-Q3.png","APAC-Q4.png","LATAM-Q4.png"):
            try:C.fetch(env,f"/home/user/workspace/out_a/bi_pack/{name}",str(workspace/"out_a/bi_pack"/name))
            except Exception:pass
    else:
        for name in ("Summit_Brochure.pptx","Summit_Brochure.pdf"):
            try:C.fetch(env,f"/home/user/workspace/out_b/{name}",str(workspace/"out_b"/name))
            except Exception:pass
    state={}
    try:C.fetch(env,STATE,str(out/"state.json"));state=json.loads((out/"state.json").read_text(encoding="utf-8"))
    except Exception:pass
    assets=Path(os.environ.get("PARAGUI_TASK_ASSETS",str(Path.cwd())))/"CONC-06/private/expected.json"
    result=grade(workspace,state,assets,out/"rendered");(out/"checks.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    key="actor_a" if actor=="a" else "actor_b"
    return C.result(result[key],{"checks":result["checks"][key],"flags":result["flags"],"downloads_a":len([x for x in state.get("a_events",[]) if x.get("type")=="download"]),"downloads_b":len([x for x in state.get("b_events",[]) if x.get("type")=="download"])})
def evaluate_actor_a(env):return _eval(env,"a")
def evaluate_actor_b(env):return _eval(env,"b")
