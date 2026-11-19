#!/usr/bin/env python3
"""MECH-04 real Guest positive joint control and fixed active-cell drift control."""
from __future__ import annotations
import json,os,secrets,sys,time,traceback,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
IMAGE=OSW/"docker_vm_data/osworld-v2-ubuntu-x86.qcow2"
ASSETS=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
OUTROOT=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls")
TASK_A=ROOT/"tasks/mechanism_expansion_v1/task_mech04a.py"
TASK_B=ROOT/"tasks/mechanism_expansion_v1/task_mech04b.py"
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
from tasks.mechanism_expansion_v1 import mech04 as pair

def cmd(g,script,timeout=60):
 r=g.execute(["bash","-lc",script],timeout)
 return (r.get("output") or "")+(r.get("error") or "")
def screenshot(g,out,name): (out/name).write_bytes(g.screenshot(patience=90))
def goto_cell(g,address):
 m=re.fullmatch(r"([A-Z]+)([0-9]+)",address)
 if not m: raise ValueError(address)
 col=0
 for ch in m.group(1):col=col*26+ord(ch)-64
 row=int(m.group(2))
 keys=["Escape","ctrl+Home"]+["Right"]*(col-1)+["Down"]*(row-1)
 cmd(g,"xdotool key --clearmodifiers "+" ".join(keys)+"; sleep .2")
def enter_cell(g,address,value):
 goto_cell(g,address)
 cmd(g,f"xdotool type --clearmodifiers --delay 20 '{value}'; xdotool key Return; sleep .25")
def enter_current(g,value):
 cmd(g,f"xdotool type --clearmodifiers --delay 20 '{value}'; xdotool key Return; sleep .25")
def sort_next_count(g):
 goto_cell(g,"C1")
 cmd(g,"xdotool mousemove --sync 454 75 click 1; sleep .35; xdotool key Down Down Return; sleep 2; xdotool key ctrl+s; sleep 5")
def state(g): return {r:pair.evaluate(g.env,r) for r in ("A","B")}
def reset_docs(g,controller):
 cmd(g,"xdotool key ctrl+q; sleep 2")
 cmd(g,"for i in $(seq 25); do pgrep -x soffice.bin >/dev/null || exit 0; sleep 1; done; pkill -x soffice.bin 2>/dev/null || true; sleep 2")
 cmd(g,f"cp {pair.WORK}/baseline/range-drift-log.ods {pair.ODS}")
 key=f"{getattr(controller,'vm_ip','')}:{getattr(controller,'server_port','')}"
 pair._SETUP.discard(key);pair.setup(controller,"A");time.sleep(2)
def main():
 runid="mech04-guest-control-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(os.getpid())
 out=OUTROOT/runid;out.mkdir(parents=True,exist_ok=False);(out/"overlays").mkdir()
 os.environ.update({"SWCUB_RUN_ID":runid,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),"SWCUB_RESOURCE_LEDGER":str(out/"resource-events.jsonl")})
 os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None);ensure_resource_identity(out/"resource-events.jsonl")
 env=None;report={"run_id":runid,"case_id":"MECH-04","task_version":pair.TASK_VERSION,"control_version":"0.1.0","kind":"scripted_gui_controls","model_used":False,"status":"starting","external_containers_stopped":False}
 try:
  tasks=[load_task(str(TASK_A)),load_task(str(TASK_B))]
  env=combo.boot(str(IMAGE),str(out/"cache"));report["setup"]=combo.setup_tasks(env,tasks)
  time.sleep(4);g=Guest(env);controller=env.setup_controller;screenshot(g,out,"initial.png")
  # Positive: A completes the cell edit before B's normal sort and stable-ID edit.
  enter_cell(g,"E2","Recheck");report["positive_after_a"]=state(g);screenshot(g,out,"positive-after-a.png")
  sort_next_count(g);report["positive_after_sort"]=state(g);screenshot(g,out,"positive-after-sort.png")
  enter_cell(g,"F4","RM");cmd(g,"xdotool key ctrl+s; sleep 4")
  report["positive_state"]=state(g);screenshot(g,out,"positive-final.png")
  report["positive_joint_pass"]=all(report["positive_state"][r]["score"]==1.0 for r in ("A","B"))
  if not report["positive_joint_pass"]:raise AssertionError("MECH-04 positive control failed")
  # Negative: A selects E2; B's sort legitimately changes the shared active cell to C1;
  # A's pending text action is then delivered to that current cell, not its old target.
  reset_docs(g,controller)
  goto_cell(g,"E2");report["negative_a_selected_e2"]=True;screenshot(g,out,"negative-a-selected-e2.png")
  sort_next_count(g);report["negative_after_sort"]=state(g);screenshot(g,out,"negative-after-sort.png")
  report["negative_selected_cell_before_a_types"]="C1 (Data > Sort Ascending is invoked from the Next Count header)"
  enter_current(g,"Recheck");cmd(g,"xdotool key ctrl+s; sleep 4")
  enter_cell(g,"F4","RM");cmd(g,"xdotool key ctrl+s; sleep 4")
  report["negative_state"]=state(g);screenshot(g,out,"negative-final.png")
  a=report["negative_state"]["A"];b=report["negative_state"]["B"]
  report["fixed_active_cell_drift_passed"]=(a["score"]==0.0 and b["score"]==0.0 and a["state"]["wrong_header"] and b["state"]["wrong_header"] and b["checks"].get("b5112_verified_rm"))
  report["status"]="passed" if report["fixed_active_cell_drift_passed"] else "invalid_control_oracle"
 except Exception as e:
  report["status"]="invalid_infra_or_control_failure";report["error"]=f"{type(e).__name__}: {e}";report["traceback"]=traceback.format_exc()[-4000:]
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
  print(json.dumps({"status":report["status"],"positive_joint_pass":report.get("positive_joint_pass"),"fixed_active_cell_drift_passed":report.get("fixed_active_cell_drift_passed"),"artifacts":str(out),"error":report.get("error")},ensure_ascii=False))
 return 0 if report["status"]=="passed" else 1
if __name__=="__main__":raise SystemExit(main())
