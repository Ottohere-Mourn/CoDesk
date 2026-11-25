"""Shared setup and deterministic host-side evaluation for CONC-07."""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc07_grade import grade
ROOT=f"{C.HOME}/.cache/paragui/conc07";DB="/home/user/workspace/shared/enterprise_ops.db";STATE="/tmp/conc07-runtime/state.json"
FILES=[("CONC-07/service.py",f"{ROOT}/service.py"),
       ("CONC-07/guest/in_a/supplier_master.csv",f"{ROOT}/supplier_master.csv"),
       ("CONC-07/guest/in_a/brand_swatch_a.png",f"{ROOT}/brand_swatch_a.png"),
       ("CONC-07/guest/in_a/review_spec_a.txt",f"{ROOT}/review_spec_a.txt"),
       ("CONC-07/guest/out_a/Q4_Supplier_Review.pptx",f"{ROOT}/Q4_Supplier_Review.pptx"),
       ("CONC-07/guest/in_b/campaign_spend.csv",f"{ROOT}/campaign_spend.csv"),
       ("CONC-07/guest/in_b/brand_swatch_b.png",f"{ROOT}/brand_swatch_b.png"),
       ("CONC-07/guest/in_b/postmortem_spec_b.txt",f"{ROOT}/postmortem_spec_b.txt"),
       ("CONC-07/guest/out_b/Promo_Postmortem.pptx",f"{ROOT}/Promo_Postmortem.pptx"),
       *[(f"CONC-07/guest/in_a/qc_sheets/SUP-{i:02d}.png",f"{ROOT}/qc_sheets/SUP-{i:02d}.png") for i in range(1,7)],
       *[(f"CONC-07/guest/in_a/{n}.png",f"{ROOT}/{n}.png") for n in ("settlement_by_vendor","deduction_profile","q4_payable_trend")],
       *[(f"CONC-07/guest/in_b/{n}.png",f"{ROOT}/{n}.png") for n in ("channel_roi","budget_variance","revenue_mix")],
       *[(f"CONC-07/guest/in_b/roi_CH-{i:02d}.png",f"{ROOT}/roi_CH-{i:02d}.png") for i in range(1,7)],
       *[(f"CONC-07/guest/in_b/allowances/ALW-{i:02d}.png",f"{ROOT}/allowances/ALW-{i:02d}.png") for i in range(1,5)],
       *[(f"CONC-07/guest/in_b/mobile_lp_{i}.png",f"{ROOT}/mobile_lp_{i}.png") for i in (1,2)]]
def setup(sc):
    C.upload(sc,FILES)
    da="/home/user/workspace/out_a/Q4_Supplier_Review.pptx";db="/home/user/workspace/out_b/Promo_Postmortem.pptx"
    C.sh(sc,f"""mkdir -p {ROOT}/qc_sheets {ROOT}/allowances /tmp/conc07-runtime /home/user/workspace/shared /home/user/workspace/in_a/qc_sheets /home/user/workspace/in_b/allowances /home/user/workspace/out_a /home/user/workspace/out_b
cp {ROOT}/supplier_master.csv /home/user/workspace/in_a/supplier_master.csv; cp {ROOT}/brand_swatch_a.png /home/user/workspace/in_a/brand_swatch_a.png; cp {ROOT}/review_spec_a.txt /home/user/workspace/in_a/review_spec_a.txt; cp {ROOT}/qc_sheets/*.png /home/user/workspace/in_a/qc_sheets/; cp {ROOT}/Q4_Supplier_Review.pptx {da}
cp {ROOT}/campaign_spend.csv /home/user/workspace/in_b/campaign_spend.csv; cp {ROOT}/brand_swatch_b.png /home/user/workspace/in_b/brand_swatch_b.png; cp {ROOT}/postmortem_spec_b.txt /home/user/workspace/in_b/postmortem_spec_b.txt; cp {ROOT}/allowances/*.png /home/user/workspace/in_b/allowances/; cp {ROOT}/Promo_Postmortem.pptx {db}
if ! curl -sf -m 1 http://127.0.0.1:18131/health >/dev/null; then setsid -f python3 {ROOT}/service.py --assets {ROOT} --db {DB} --state {STATE} >{ROOT}/service.log 2>&1 < /dev/null; fi
for i in $(seq 1 30); do curl -sf -m 1 http://127.0.0.1:18131/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18132/health >/dev/null && break; sleep 1; done
curl -sf -m 2 http://127.0.0.1:18131/health >/dev/null && curl -sf -m 2 http://127.0.0.1:18132/health >/dev/null
if ! pgrep -x soffice.bin >/dev/null; then setsid -f libreoffice --impress {da} {db} >{ROOT}/soffice.log 2>&1 < /dev/null; fi""")
    if not getattr(setup,"_chrome_started",False):
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1 --start-maximized",shell=True)
        C.open_chrome(sc,["http://127.0.0.1:18131/","http://127.0.0.1:18132/mobile-check"]);setup._chrome_started=True
def _eval(env,actor):
    root=Path(os.environ.get("CONC07_EVAL_OUT",tempfile.mkdtemp(prefix="conc07-eval-")));out=root/f"actor-{actor}";out.mkdir(parents=True,exist_ok=True);ws=out/"workspace";folder=ws/f"out_{actor}";folder.mkdir(parents=True,exist_ok=True)
    files=("settlement_audit.json","Q4_Supplier_Review.pptx","Q4_Supplier_Review.pdf") if actor=="a" else ("campaign_summary.json","Promo_Postmortem.pptx","Promo_Postmortem.pdf","mobile_lp_1.png","mobile_lp_2.png")
    for name in files:
        try:C.fetch(env,f"/home/user/workspace/out_{actor}/{name}",str(folder/name))
        except Exception:pass
    try:C.fetch(env,"/home/user/workspace/shared/enterprise_ops.db",str(ws/"enterprise_ops.db"))
    except Exception:pass
    state={}
    try:C.fetch(env,STATE,str(out/"state.json"));state=json.loads((out/"state.json").read_text(encoding="utf-8"))
    except Exception:pass
    assets=Path(os.environ.get("PARAGUI_TASK_ASSETS",str(Path.cwd())))/"CONC-07/private/expected.json"
    result=grade(ws,state,assets,out/"rendered");(out/"checks.json").write_text(json.dumps(result,indent=2),encoding="utf-8");key="actor_a" if actor=="a" else "actor_b"
    return C.result(result[key],{"checks":result["checks"][key],"flags":result["flags"],"sqlite_busy_count":state.get("sqlite_busy_count",0)})
def evaluate_actor_a(env):return _eval(env,"a")
def evaluate_actor_b(env):return _eval(env,"b")
