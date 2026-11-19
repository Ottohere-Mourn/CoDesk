#!/usr/bin/env python3
"""Real OSWorld Guest controls for MECH-01: immediate-copy positive and interleaved negative."""
from __future__ import annotations
import hashlib,json,os,secrets,sys,time,traceback
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OSW=Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
SWC=Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
IMAGE=Path(os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE",OSW/"docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
ASSETS=Path(os.environ.get("PARAGUI_TASK_ASSETS","/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets"))
OUTROOT=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/controls")
TASK_A=ROOT/"tasks/mechanism_expansion_v1/task_mech01a.py";TASK_B=ROOT/"tasks/mechanism_expansion_v1/task_mech01b.py"
sys.path[:0]=[str(ROOT),str(SWC),str(OSW)]
os.environ.update({"OSWORLD_DIR":str(OSW),"PARAGUI_TASK_ASSETS":str(ASSETS),
 "OSCOMBO_GUEST_IMAGE":str(IMAGE),"SWCUB_OSWORLD_GUEST_IMAGE":str(IMAGE),
 "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "OSWORLD_DOCKER_RUNTIME_IMAGE":"swcub/osworld-v2.1-qemu-runtime:local",
 "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(OUTROOT/"overlays"),
 "SWCUB_OSWORLD_CACHE_DIR":str(OUTROOT/"osworld-cache")})
from oscombo import combo
from oscombo.osworld import load_task
from tasks.mechanism_expansion_v1 import oracle
from swcub.resource_safety import ensure_resource_identity

def call_state(env,page):
 return page.evaluate("async()=>await fetch('/api/state',{cache:'no-store'}).then(r=>r.json())")
def paste_from(role,page):
 page.locator(f"#source-{role}").select_text()
 page.keyboard.press("Control+C")
 page.locator(f"#reference-{role}").click()
 page.keyboard.press("Control+V")
def fill_role(role,page):
 page.locator(f"#{'vendor' if role=='A' else 'payee'}-{role}").fill("Northwind Safety" if role=="A" else "Riverside Testing")
 page.locator(f"#amount-{role}").fill("1840.00" if role=="A" else "965.50")
 page.locator(f"[data-save='{role}']").click()
def scores(state):
 events=state.get("events",[]);trace=[]
 for e in events:
  item={"event":e.get("kind"),"role":e.get("role"),"owner":e.get("owner"),
        "value":e.get("value"),"pasted_value":e.get("value"),
        "source_value":e.get("source_value"),"time":e.get("time")}
  if e.get("kind")=="paste" and e.get("value")!=e.get("source_value"):
   prior=[c for c in events if c.get("kind")=="copy" and c.get("time",0)<e.get("time",0)]
   latest=max(prior,key=lambda c:c.get("time",0),default=None)
   if latest and latest.get("owner") not in (None,e.get("role")) and latest.get("value")==e.get("value"):
    item["reason"]="clipboard_owner_changed"
  trace.append(item)
 return oracle.evaluate("MECH-01",{"rows":state.get("rows",{}),"clipboard_trace":trace})
def wait_event_count(env,page,n):
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  if len(call_state(env,page).get("events",[]))>=n:return
  time.sleep(.1)
 raise TimeoutError(f"Guest event count did not reach {n}")
def wait_saved(env,page,role):
 deadline=time.monotonic()+15;last={}
 while time.monotonic()<deadline:
  last=call_state(env,page)
  if (last.get("rows",{}).get(role,{}) or {}).get("saved") is True:return last
  time.sleep(.1)
 status=page.locator(f"#status-{role}").inner_text(timeout=3000)
 values={f:page.locator(f"#{f}-{role}").input_value(timeout=3000)
         for f in (("vendor","reference","amount") if role=="A" else ("payee","reference","amount"))}
 raise TimeoutError(f"Guest save was not committed for role {role}; ui_status={status!r}; values={values!r}; state={last!r}")
def reset(env,page):
 page.evaluate("async()=>await fetch('/api/reset',{method:'POST'})")
 page.reload(wait_until="domcontentloaded",timeout=30000)
 page.wait_for_selector("#source-A",timeout=30000)
 state=call_state(env,page)
 if state.get("events")!=[]:raise RuntimeError("reset did not clear case event history")
 for selector in ("#reference-A","#amount-A","#reference-B","#amount-B"):
  if page.locator(selector).input_value()!="":
   raise RuntimeError(f"reset left stale visible value in {selector}")
def save_guest_screenshot(guest,path):
 Path(path).write_bytes(guest.screenshot(patience=60))
def main():
 run_id="mech01-guest-control-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(os.getpid())
 OUTROOT.mkdir(parents=True,exist_ok=True)
 out=OUTROOT/run_id;out.mkdir(parents=True,exist_ok=False);(out/"overlays").mkdir()
 os.environ.update({"SWCUB_RUN_ID":run_id,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
                    "SWCUB_RESOURCE_LEDGER":str(out/"resource-events.jsonl"),
                    "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays")})
 os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
 identity=ensure_resource_identity(out/"resource-events.jsonl")
 env=None;page=None;close_success=False;console_log=[];api_responses=[];report={"run_id":run_id,"case_id":"MECH-01","task_version":"0.1.4","control_version":"0.1.5",
 "kind":"scripted_gui_positive_and_negative_controls","model_used":False,
 "external_containers_stopped":False,"guest_image":str(IMAGE),"fixture_manifest":None,
 "status":"starting","resource_identity":identity.run_id}
 try:
  if not IMAGE.is_file():raise FileNotFoundError(f"OSWorld Guest image absent: {IMAGE}")
  if not (ASSETS/"mechanism_expansion_v1/mech01/app.py").is_file():raise FileNotFoundError("built RAID app asset missing; run tasks/mechanism_expansion_v1/build_assets.py")
  for task_path in (TASK_A,TASK_B):
   task=load_task(str(task_path));report.setdefault("task_ids_loaded",[]).append(task.id)
  env=combo.boot(str(IMAGE),str(out/"cache"));tasks=[load_task(str(TASK_A)),load_task(str(TASK_B))]
  report["setup"]=combo.setup_tasks(env,tasks);time.sleep(8)
  report["fixture_manifest"]=json.loads((ASSETS/"mechanism_expansion_v1/mech01/manifest.json").read_text())
  guest=__import__("oscombo.guest",fromlist=["Guest"]).Guest(env)
  shot=guest.wait_desktop();(out/"initial.png").write_bytes(shot)
  cdp=f"http://{env.vm_ip}:{getattr(env,'chromium_port',9222)}";version=None
  for _ in range(40):
   try:version=requests.get(cdp+"/json/version",timeout=3).json();break
   except Exception:time.sleep(1)
  if not version:raise RuntimeError("Guest Chromium DevTools endpoint not ready")
  with sync_playwright() as pw:
   browser=pw.chromium.connect_over_cdp(cdp);context=browser.contexts[0]
   origin="http://127.0.0.1:8311"
   try:context.grant_permissions(["clipboard-read","clipboard-write"],origin=origin)
   except Exception:pass
   page=next((p for p in reversed(context.pages) if "/desk" in p.url),context.pages[-1] if context.pages else context.new_page())
   page.on("console",lambda m:console_log.append({"type":m.type,"text":m.text[:500]}))
   page.on("pageerror",lambda e:console_log.append({"type":"pageerror","text":str(e)[:500]}))
   page.on("response",lambda r:api_responses.append({"url":r.url,"status":r.status}) if "/api/" in r.url else None)
   # Re-navigate once on the selected tab: paired setup creates two tabs and the first can precede app readiness.
   page.goto(origin+"/desk",wait_until="domcontentloaded",timeout=30000)
   report["dom_probe"]=page.evaluate("""()=>({url:location.href,title:document.title,ids:[...document.querySelectorAll('[id]')].map(el=>el.id),frame_count:document.querySelectorAll('iframe').length,body:document.body.innerText.slice(0,1000)})""")
   page.wait_for_selector("#source-A",timeout=30000)
   try:page.keyboard.press("Escape")
   except Exception:pass
   initial=call_state(env,page);save_guest_screenshot(guest,out/"initial-app.png")
   report["initial_rows"]=initial["rows"]
   # Positive: each actor completes an immediate copy-paste of its own source reference.
   reset(env,page)
   paste_from("A",page);wait_event_count(env,page,2);fill_role("A",page);wait_saved(env,page,"A")
   paste_from("B",page);wait_event_count(env,page,4);fill_role("B",page);wait_saved(env,page,"B")
   positive=call_state(env,page);report["positive_control"]={"scores":scores(positive),"state":positive}
   save_guest_screenshot(guest,out/"positive.png")
   if not report["positive_control"]["scores"]["joint_success"]:
    raise AssertionError("MECH-01 GUI positive control did not pass for both roles")
   pe=positive.get("events",[])
   if sum(e.get("kind")=="copy" for e in pe)!=2 or sum(e.get("kind")=="paste" for e in pe)!=2:
    raise AssertionError("positive control lacked two real clipboard copy/paste event pairs")
   if any(e.get("kind")=="paste" and e.get("value")!=e.get("source_value") for e in pe):
    raise AssertionError("positive control unexpectedly observed a clipboard mismatch")
   # Negative mechanism control: A copies, B legitimately copies, A pastes after clipboard changes.
   reset(env,page)
   page.locator("#source-A").select_text();page.keyboard.press("Control+C");wait_event_count(env,page,1)
   page.locator("#source-B").select_text();page.keyboard.press("Control+C");wait_event_count(env,page,2)
   page.locator("#reference-A").click();page.keyboard.press("Control+V");wait_event_count(env,page,3)
   fill_role("A",page);wait_saved(env,page,"A")
   paste_from("B",page);wait_event_count(env,page,5);fill_role("B",page);wait_saved(env,page,"B")
   negative=call_state(env,page);report["interleaved_mechanism_control"]={"scores":scores(negative),"state":negative}
   save_guest_screenshot(guest,out/"interleaved-negative.png")
   if report["interleaved_mechanism_control"]["scores"]["actors"]["A"]["success"]:
    raise AssertionError("mechanism negative control failed to expose clipboard overwrite")
   if not report["interleaved_mechanism_control"]["scores"]["mechanism_evidence"]["attributed"]:
    raise AssertionError("negative result lacked clipboard-owner-change evidence")
   browser.close()
  report["status"]="passed";report["reset_success"]=True
 except Exception as exc:
  report["status"]="invalid_infra_or_control_failure";report["error"]=f"{type(exc).__name__}: {exc}";report["traceback"]=traceback.format_exc()[-5000:]
  report["console_log"]=console_log;report["api_responses"]=api_responses
  if env is not None and page is not None:
   try:report["failure_state"]=call_state(env,page)
   except Exception as state_error:report["failure_state_error"]=f"{type(state_error).__name__}: {state_error}"[:300]
 finally:
  if env:
   try:
    env.close();close_success=True
   except Exception as exc:report["close_error"]=f"{type(exc).__name__}: {exc}"
  ledger_events=[]
  try:ledger_events=[json.loads(line) for line in (out/"resource-events.jsonl").read_text().splitlines() if line.strip()]
  except Exception:pass
  report["guest_close_succeeded"]=close_success
  report["owned_guest_destroyed"]=any(e.get("event")=="destroyed" and e.get("resource_type")=="container" for e in ledger_events)
  (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
  print(json.dumps({"status":report["status"],"case_id":report["case_id"],
   "positive_joint_pass":report.get("positive_control",{}).get("scores",{}).get("joint_success"),
   "negative_A_fail":report.get("interleaved_mechanism_control",{}).get("scores",{}).get("actors",{}).get("A",{}).get("success") is False,
   "attributed":report.get("interleaved_mechanism_control",{}).get("scores",{}).get("mechanism_evidence",{}).get("attributed"),
   "artifacts":str(out),"error":report.get("error")},ensure_ascii=False))
 return 0 if report["status"]=="passed" else 1
if __name__=="__main__":raise SystemExit(main())
