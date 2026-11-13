#!/usr/bin/env python3
"""Run a scripted browser-UI joint positive control for COMMUNITY-PANTRY1 in one fresh OSWorld Guest."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

REPO=Path("/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112")
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
sys.path[:0]=[str(REPO),str(SWC),str(OSW)]
from oscombo import combo
from oscombo.osworld import load_task, task_get
ASSETS=Path("/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets")
RUNROOT=Path("/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets")
OVERLAY_TMP=Path("/dev/shm/codesk-next3/overlays")
OVERLAY_ARCHIVE=Path("/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays")
BASE=Path("/dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2")
TASK_IDS=["v2/pgv3shift","v2/pgv3mileage"]
def main():
 runid=f"cdesk3-v3-scripted-joint-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
 out=RUNROOT/runid;over=OVERLAY_TMP/runid;archive=OVERLAY_ARCHIVE/runid
 out.mkdir(parents=True,exist_ok=False);over.mkdir(parents=True,exist_ok=False)
 os.environ.update({
  "OSWORLD_DIR":str(OSW),"PARAGUI_TASK_ASSETS":str(ASSETS),"OSCOMBO_GUEST_IMAGE":str(BASE),
  "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
  "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(over),"SWCUB_RUN_ID":runid,
  "SWCUB_OWNER_TOKEN":os.urandom(32).hex(),"SWCUB_RESOURCE_LEDGER":str(out/"resources/resource_ledger.jsonl"),
  "SWCUB_OSWORLD_VM_READY_TIMEOUT":"600","PYTHONPATH":f"{REPO}:{SWC}:{OSW}",
 })
 result={"run_id":runid,"case":"v3","kind":"scripted_gui_joint_positive","tasks":TASK_IDS,"started_utc":datetime.now(timezone.utc).isoformat(),"error":None}
 env=None
 try:
  fixture={}
  for f in sorted((ASSETS/"v3").rglob("*")):
   if f.is_file():fixture[str(f.relative_to(ASSETS/"v3"))]=__import__("hashlib").sha256(f.read_bytes()).hexdigest()
  (out/"fixture.sha256").write_text("".join(f"{h}  {p}\n" for p,h in sorted(fixture.items())))
  env=combo.boot(str(BASE),str(out/"cache"))
  tasks=[load_task(t) for t in TASK_IDS]
  result["task_ids_loaded"]=[str(task_get(t,"id")) for t in tasks]
  result["setup"]=combo.setup_tasks(env,tasks)
  time.sleep(25)
  guest=__import__("oscombo.guest",fromlist=["Guest"]).Guest(env)
  (out/"start.png").write_bytes(guest.wait_desktop())
  result["guest"]={"ip":env.vm_ip,"server_port":env.server_port}
  expected=json.loads((ASSETS/"v3"/"expected.json").read_text())
  cdp=f"http://{env.vm_ip}:9222"
  version=None
  for _ in range(30):
   try:
    version=requests.get(cdp+"/json/version",timeout=3).json();break
   except Exception:time.sleep(2)
  if not version:raise RuntimeError("Guest Chrome DevTools endpoint 9222 not ready")
  actions=[]
  with sync_playwright() as pw:
   browser=pw.chromium.connect_over_cdp(cdp)
   context=browser.contexts[0]
   page=next((p for p in context.pages if "8138/desk" in p.url),context.pages[-1] if context.pages else context.new_page())
   if "8138/desk" not in page.url:page.goto("http://127.0.0.1:8138/desk")
   page.wait_for_load_state("domcontentloaded")
   for w in expected["shift"]["rows"]:
    page.locator(f'.person[data-id="{w["id"]}"]').click();page.wait_for_timeout(250)
    page.locator('.tab[data-panel="shift"]').click();page.wait_for_timeout(250)
    page.locator("#station").select_option(label=w["station"])
    page.locator("#window").fill(w["window"])
    page.locator("#status").select_option(label=w["status"])
    page.locator("#save").click();page.wait_for_timeout(800)
    actions.append({"actor":"shift","volunteer":w["id"],"saved":True})
   for w in expected["mileage"]["rows"]:
    page.locator('.tab[data-panel="mileage"]').click();page.wait_for_timeout(250)
    page.locator(f'.person[data-id="{w["id"]}"]').click();page.wait_for_timeout(250)
    page.locator("#amount").fill(f'{w["amount"]:.2f}')
    page.locator("#decision").select_option(label=w["decision"])
    page.locator("#note").fill(w["note"])
    page.locator("#save").click();page.wait_for_timeout(800)
    actions.append({"actor":"mileage","volunteer":w["id"],"saved":True})
   result["actions"]=actions
   page.screenshot(path=str(out/"end-browser.png"),full_page=True)
   (out/"end.png").write_bytes(guest.screenshot())
   browser.close()
  result["scores"]=combo.evaluate_tasks(env,tasks,[False,False],result)
  result["status"]="complete"
 except Exception as e:
  result["status"]="error";result["error"]=f"{type(e).__name__}: {e}"[:500]
  result["traceback"]=traceback.format_exc()[-4000:]
  if env:
   try:(out/"failure.png").write_bytes(env.controller.get_screenshot() or b"")
   except Exception:pass
 finally:
  if env:
   try:env.close()
   except Exception as e:result.setdefault("warnings",[]).append(f"close:{type(e).__name__}:{e}"[:200])
  try:
   archive.mkdir(parents=True,exist_ok=True)
   if over.exists():subprocess.run(["cp","-r","--sparse=auto","--no-preserve=all",str(over)+"/.",str(archive)],check=True)
  except Exception as e:result.setdefault("warnings",[]).append(f"overlay_archive:{type(e).__name__}:{e}"[:200])
  result["finished_utc"]=datetime.now(timezone.utc).isoformat()
  (out/"result.json").write_text(json.dumps(result,indent=2))
  (out/"trace.jsonl").write_text("".join(json.dumps(x)+"\n" for x in result.get("actions",[])))
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
