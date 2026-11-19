#!/usr/bin/env python3
"""Read-only UI inspection for MECH-02's real Calc Data menu."""
from __future__ import annotations
import json,os,secrets,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
IMAGE=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2")
OUTROOT=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls")
ASSETS=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
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

def main():
 runid="mech02-ui-probe-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(os.getpid())
 out=OUTROOT/runid; out.mkdir(parents=True,exist_ok=False); (out/"overlays").mkdir()
 os.environ.update({"SWCUB_RUN_ID":runid,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
   "SWCUB_RESOURCE_LEDGER":str(out/"resource-events.jsonl")})
 os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
 ensure_resource_identity(out/"resource-events.jsonl")
 env=None
 try:
  tasks=[load_task(str(ROOT/"tasks/mechanism_expansion_v1/task_mech02a.py")),
         load_task(str(ROOT/"tasks/mechanism_expansion_v1/task_mech02b.py"))]
  env=combo.boot(str(IMAGE),str(out/"cache")); setup=combo.setup_tasks(env,tasks)
  time.sleep(3); g=Guest(env)
  (out/"initial.png").write_bytes(g.screenshot(patience=90))
  g.execute(["bash","-lc","xdotool key ctrl+home; xdotool key Right Right; sleep .3; xdotool mousemove --sync 454 75 click 1; sleep .5"],timeout=60)
  (out/"data-menu.png").write_bytes(g.screenshot(patience=90))
  print(json.dumps({"status":"captured","run":runid,"setup":setup,"active":g.active_window_info(),"artifacts":str(out)},ensure_ascii=False))
 finally:
  if env: env.close()
if __name__=="__main__": main()
