"""Shared setup and deterministic host-side evaluation for CONC-08."""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class.conc08_grade import grade
CHECKPOINTS=23
ROOT=f"{C.HOME}/.cache/paragui/conc08";STATE="/tmp/conc08-runtime/state.json"
FILES=[("CONC-08/service.py",f"{ROOT}/service.py"),
       ("CONC-08/guest/shared/Corp_Annual_2026.xlsx","/home/user/workspace/shared/Corp_Annual_2026.xlsx"),
       ("CONC-08/guest/in_a/close_spec_a.txt","/home/user/workspace/in_a/close_spec_a.txt"),
       ("CONC-08/guest/out_a/Finance_Close.pptx","/home/user/workspace/out_a/Finance_Close.pptx"),
       ("CONC-08/guest/in_b/close_spec_b.txt","/home/user/workspace/in_b/close_spec_b.txt"),
       ("CONC-08/guest/out_b/HR_Close.pptx","/home/user/workspace/out_b/HR_Close.pptx"),
       *[(f"CONC-08/guest/in_a/sales_q{i}.csv",f"/home/user/workspace/in_a/sales_q{i}.csv") for i in range(1,5)],
       *[(f"CONC-08/guest/in_a/credit_memos/CM-{i:02d}.png",f"/home/user/workspace/in_a/credit_memos/CM-{i:02d}.png") for i in range(1,5)],
       *[(f"CONC-08/guest/in_b/payroll_q{i}.csv",f"/home/user/workspace/in_b/payroll_q{i}.csv") for i in range(1,5)],
       *[(f"CONC-08/guest/in_b/allowances/ALW-{i:02d}.png",f"/home/user/workspace/in_b/allowances/ALW-{i:02d}.png") for i in range(1,5)]
       ]
def setup(sc):
    if not getattr(setup,"_inputs_uploaded",False):
        C.upload(sc,FILES)
        C.sh(sc,f"mkdir -p {ROOT} /tmp/conc08-runtime /home/user/workspace/shared /home/user/workspace/in_a/credit_memos /home/user/workspace/in_b/allowances /home/user/workspace/out_a /home/user/workspace/out_b")
        # A separate-profile XLSX-to-PDF conversion proves the installed Calc component can read and render a workbook.
        probe="\n".join([
            "probe_dir=/tmp/conc08-runtime/calc-probe-$(date +%s)",
            "mkdir -p \"$probe_dir\"",
            "if ! command -v libreoffice >/dev/null 2>&1; then echo SKIPPED_NO_CALC > /tmp/conc08-runtime/calc-probe.status; exit 42; fi",
            "if ! libreoffice -env:UserInstallation=file:///tmp/conc08-runtime/calc-profile-$$ --headless --convert-to pdf --outdir \"$probe_dir\" /home/user/workspace/shared/Corp_Annual_2026.xlsx >\"$probe_dir/probe.log\" 2>&1 || [ ! -s \"$probe_dir/Corp_Annual_2026.pdf\" ]; then echo SKIPPED_NO_CALC > /tmp/conc08-runtime/calc-probe.status; exit 42; fi",
            "echo CALC_OK > /tmp/conc08-runtime/calc-probe.status",
        ])
        try:sc.execute(["bash","-c",probe],timeout=120,check=True)
        except Exception as exc:
            try:sc.execute(["bash","-c","mkdir -p /tmp/conc08-runtime; echo SKIPPED_NO_CALC > /tmp/conc08-runtime/calc-probe.status"],timeout=10,check=False)
            except Exception:pass
            raise RuntimeError("SKIPPED_NO_CALC: Guest Calc preflight failed before actor execution") from exc
        setup._inputs_uploaded=True
    if not getattr(setup,"_service_started",False):
        sc.launch(f"exec python3 {ROOT}/service.py --assets {ROOT} --state {STATE}",shell=True);setup._service_started=True
        C.sh(sc,f"for i in $(seq 1 30); do curl -sf -m 1 http://127.0.0.1:18141/health >/dev/null && curl -sf -m 1 http://127.0.0.1:18142/health >/dev/null && break; sleep 1; done; curl -sf -m 2 http://127.0.0.1:18141/health >/dev/null && curl -sf -m 2 http://127.0.0.1:18142/health >/dev/null")
    if not getattr(setup,"_office_started",False):
        sc.launch("exec libreoffice --calc --impress /home/user/workspace/shared/Corp_Annual_2026.xlsx /home/user/workspace/out_a/Finance_Close.pptx /home/user/workspace/out_b/HR_Close.pptx",shell=True);setup._office_started=True
    if not getattr(setup,"_chrome_started",False):
        sc.launch("exec google-chrome --remote-debugging-port=1337 --force-device-scale-factor=1 --start-maximized",shell=True)
        C.open_chrome(sc,["http://127.0.0.1:18141/?actor=a","http://127.0.0.1:18142/?actor=b"]);setup._chrome_started=True
def _eval(env,actor):
    root=Path(os.environ.get("CONC08_EVAL_OUT",tempfile.mkdtemp(prefix="conc08-eval-")));out=root/f"actor-{actor}";out.mkdir(parents=True,exist_ok=True);ws=out/"workspace";ws.mkdir(parents=True,exist_ok=True)
    files=("Rev_Ledger.pdf","Finance_Close.pptx","Finance_Close.pdf","rev_trend.png","finance_close.json") if actor=="a" else ("HR_Cost.pdf","HR_Close.pptx","HR_Close.pdf","hr_cost_chart.png","hr_close.json")
    for name in files:
        try:C.fetch(env,f"/home/user/workspace/out_{actor}/{name}",str(ws/name))
        except Exception:pass
    try:C.fetch(env,"/home/user/workspace/shared/Corp_Annual_2026.xlsx",str(ws/"Corp_Annual_2026.xlsx"))
    except Exception:pass
    try:C.fetch(env,STATE,str(out/"state.json"));state=json.loads((out/"state.json").read_text(encoding="utf-8"))
    except Exception:state={}
    expected=Path(os.environ.get("PARAGUI_TASK_ASSETS",str(Path.cwd())))/"CONC-08/private/expected.json"
    result=grade(ws,state,expected,out/"rendered");(out/"checks.json").write_text(json.dumps(result,indent=2),encoding="utf-8");key="actor_a" if actor=="a" else "actor_b"
    raw_score=float(result[key]);normalized=max(0.0,min(1.0,raw_score/CHECKPOINTS))
    return C.result(normalized,{"raw_checkpoint_count":raw_score,"normalization_denominator":CHECKPOINTS,"checks":result["checks"][key],"flags":result["flags"],"close_code":state.get("finalized",{}).get(actor),"concurrency_metrics":state.get("metrics",{})})
def evaluate_actor_a(env):return _eval(env,"a")
def evaluate_actor_b(env):return _eval(env,"b")
