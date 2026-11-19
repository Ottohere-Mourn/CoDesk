#!/usr/bin/env python3
"""Real Guest positive and fixed-interleaving negative control for MECH-02."""
from __future__ import annotations
import json,os,secrets,sys,time,traceback,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
IMAGE=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2")
ASSETS=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
OUTROOT=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls")
TASK_A=ROOT/"tasks/mechanism_expansion_v1/task_mech02a.py"
TASK_B=ROOT/"tasks/mechanism_expansion_v1/task_mech02b.py"
sys.path[:0]=[str(ROOT),str(SWC),str(OSW)]
os.environ.update({"OSWORLD_DIR":str(OSW),"PARAGUI_TASK_ASSETS":str(ASSETS),
 "OSCOMBO_GUEST_IMAGE":str(IMAGE),"SWCUB_OSWORLD_GUEST_IMAGE":str(IMAGE),
 "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(OUTROOT/"overlays"),
 "SWCUB_OSWORLD_CACHE_DIR":str(OUTROOT/"osworld-cache")})
from oscombo import combo
from oscombo.guest import Guest
from oscombo.osworld import load_task
from swcub.resource_safety import ensure_resource_identity
from tasks.mechanism_expansion_v1 import mech02 as pair

def cmd(g,script,timeout=60):
 r=g.execute(["bash","-lc",script],timeout)
 return (r.get("output") or "")+(r.get("error") or "")

def screenshot(g,out,name):
 (out/name).write_bytes(g.screenshot(patience=90))

def goto_cell(g,address):
 # Use keyboard navigation from A1 instead of pixel coordinates; the Calc
 # sheet moves vertically when startup banners are dismissed.
 m=re.fullmatch(r"([A-Z]+)([0-9]+)",address)
 if not m: raise ValueError(f"bad Calc cell address: {address}")
 col=0
 for ch in m.group(1): col=col*26+ord(ch)-64
 row=int(m.group(2))
 keys=["Escape","ctrl+Home"]+["Right"]*(col-1)+["Down"]*(row-1)
 cmd(g,"xdotool key --clearmodifiers "+" ".join(keys)+"; sleep .2")
def enter_cell(g,address,value):
 goto_cell(g,address)
 cmd(g,f"xdotool type --clearmodifiers --delay 20 '{value}'; xdotool key Return; sleep .25")
def type_b_fields(g,row=3):
 enter_cell(g,f"E{row}","427")
 enter_cell(g,f"F{row}","JL")
 cmd(g,"xdotool key ctrl+s; sleep 1")
def type_a_note(g):
 enter_cell(g,"D2","Verified")
 cmd(g,"xdotool key ctrl+s; sleep .8")
def sort_by_qc_queue(g):
 goto_cell(g,"C1")
 # Select the QC Queue header and use Calc's actual Data > Sort Ascending command.
 cmd(g,"xdotool mousemove --sync 454 75 click 1; sleep .35; "
       "xdotool key Down Down Return; sleep 1; xdotool key ctrl+s; sleep 1")

def undo_once(g):
 cmd(g,"xdotool key --clearmodifiers ctrl+z; sleep .7; xdotool key ctrl+s; sleep 1")

def state(g):
 return {"A":pair.evaluate(g.env,"A"),"B":pair.evaluate(g.env,"B")}
def reset_docs(g,setup_controller):
 cmd(g,"xdotool key ctrl+q; sleep 2")
 cmd(g,"for i in $(seq 25); do pgrep -x soffice.bin >/dev/null || exit 0; sleep 1; done; pkill -x soffice.bin 2>/dev/null || true; sleep 2")
 cmd(g,f"cp /home/user/Documents/MECH02/baseline/qc-sample-log.ods {pair.ODS}")
 key=f"{getattr(setup_controller,'vm_ip','')}:{getattr(setup_controller,'server_port','')}"
 pair._SET_UP.discard(key)
 pair.setup(setup_controller,"A")
 time.sleep(2)

def main():
 runid="mech02-guest-control-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(os.getpid())
 out=OUTROOT/runid;out.mkdir(parents=True,exist_ok=False);(out/"overlays").mkdir()
 os.environ.update({"SWCUB_RUN_ID":runid,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
  "SWCUB_RESOURCE_LEDGER":str(out/"resource-events.jsonl")})
 os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None); ensure_resource_identity(out/"resource-events.jsonl")
 env=None
 report={"run_id":runid,"case_id":"MECH-02","task_version":pair.TASK_VERSION,
         "kind":"scripted_gui_controls","control_version":"0.1.2","model_used":False,"status":"starting",
         "external_containers_stopped":False}
 try:
  tasks=[load_task(str(TASK_A)),load_task(str(TASK_B))]
  env=combo.boot(str(IMAGE),str(out/"cache")); report["setup"]=combo.setup_tasks(env,tasks)
  time.sleep(4);g=Guest(env);controller=env.setup_controller
  screenshot(g,out,"initial.png")
  # Positive joint control: B finishes before A's sort, so A's Undo correctly targets its own sort.
  type_b_fields(g); report["positive_state_after_b"]=state(g);screenshot(g,out,"positive-after-b.png")
  type_a_note(g); sort_by_qc_queue(g); report["positive_sorted_state"]=state(g);screenshot(g,out,"positive-sorted.png")
  report["sort_control_observed"]=report["positive_sorted_state"]["A"]["state"]["row_order"] != [r[0] for r in pair.BASE_ROWS]
  if not report["sort_control_observed"]: raise AssertionError("Calc sort positive control did not change row order")
  undo_once(g); report["positive_state"]=state(g);screenshot(g,out,"positive-final.png")
  report["positive_joint_pass"]=all(report["positive_state"][r]["score"]==1.0 for r in ("A","B"))
  if not report["positive_joint_pass"]: raise AssertionError("MECH-02 scripted joint positive failed")
  # Reset files cleanly, then put B's two edits above A's sort in the shared Undo history.
  reset_docs(g,controller)
  type_a_note(g); sort_by_qc_queue(g)
  report["negative_after_a_sort"]=state(g);screenshot(g,out,"negative-after-a-sort.png")
  type_b_fields(g,row=2); report["negative_after_b"]=state(g);screenshot(g,out,"negative-after-b.png")
  undo_once(g); report["negative_state"]=state(g);screenshot(g,out,"negative-final.png")
  report["fixed_undo_interleaving_passed"]=(
    report["negative_after_a_sort"]["A"]["checks"]["a_note_verified"] and
    report["negative_after_a_sort"]["A"]["checks"]["original_order_restored"] is False and
    report["negative_after_b"]["B"]["checks"]["b_count_427"] and
    report["negative_after_b"]["B"]["checks"]["b_verifier_jl"] and
    report["negative_state"]["B"]["checks"]["b_count_427"] and
    not report["negative_state"]["B"]["checks"]["b_verifier_jl"] and
    report["negative_state"]["A"]["checks"]["original_order_restored"] is False)
  report["status"]="passed" if report["fixed_undo_interleaving_passed"] else "invalid_control_oracle"
 except Exception as e:
  report["status"]="invalid_infra_or_control_failure";report["error"]=f"{type(e).__name__}: {e}"
  report["traceback"]=traceback.format_exc()[-4000:]
 finally:
  report["guest_close_succeeded"]=False;report["owned_guest_destroyed"]=False
  if env:
   try:env.close();report["guest_close_succeeded"]=True
   except Exception as e:report["close_error"]=str(e)
  try:
   ev=[json.loads(l) for l in (out/"resource-events.jsonl").read_text().splitlines() if l.strip()]
   report["owned_guest_destroyed"]=any(x.get("event")=="destroyed" and x.get("resource_type")=="container" for x in ev)
  except Exception:pass
  (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
  print(json.dumps({"status":report["status"],"positive_joint_pass":report.get("positive_joint_pass"),
   "fixed_undo_interleaving_passed":report.get("fixed_undo_interleaving_passed"),
   "positive_sorted_state":report.get("positive_sorted_state"),"negative_state":report.get("negative_state"),
   "artifacts":str(out),"error":report.get("error")},ensure_ascii=False))
 return 0 if report["status"]=="passed" else 1
if __name__=="__main__": raise SystemExit(main())
