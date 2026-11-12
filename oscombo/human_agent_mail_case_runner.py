"""Small Human-Agent shared-mailbox pilot using the existing Codex GUI harness."""
from __future__ import annotations
import hashlib,json,os,secrets,shutil,subprocess,threading,time,traceback,uuid,sys
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
from .eventlog import EventLog
from .guest import Guest,InfraError
from .human_actor import GUIAction,ScriptedGUIActor
from .human_poc import FocusMonitor
from .human_apps.mail_workflow import CASE_ID,FIXTURE_ID,CUSTOMER_THREAD,USER_THREAD,USER_REPLY,create_fixture,evaluate,make_server
from .human_agent_case_runner import _cleanup_owned_guest,_events,_guest_exec,_run_parallel,preflight

CASE_VERSION="0.1.0"
AGENT_TASK="""In the open CoDesk Mail inbox, review customer conversation CUST-2048 about order SO-7718. Read all messages in that thread and the visible Warranty and Delivery-Damage Playbook POL-WAR-3. Apply the supported internal case label and priority. Then reply to Casey Rivera but SAVE THE MESSAGE AS A DRAFT; do not send it. The draft should acknowledge the damage, apologize, confirm the eligible replacement, and state the normal dispatch timing. Do not promise a refund or alter any source message. Use the visible GUI only; do not use CLI, hidden evaluator state, or direct HTTP endpoints."""
USER_TASK="""In the open Inbox, open the Afternoon queue coverage conversation from Ops On-call. Reply to ops-oncall@company.test with exactly: \"I can cover 14:00-16:00 today; please assign me the queue.\" Send the reply and mark the conversation as done. Do not edit other threads."""
MODES=("user-only","agent-only","independent","shared","shared-lock")
AGENT_BUDGET=40
AGENT_TIMEOUT=1200

@dataclass(frozen=True)
class TaskCard:
 case_id:str=CASE_ID
 version:str=CASE_VERSION
 title:str="Review a customer damage thread while a user responds to an operations email"
 actor_a_task:str=AGENT_TASK
 actor_b_task:str=USER_TASK
 shared_state:str="One Linux GUI session, one Chrome window, one inbox and shared selected-thread/reply composer state; distinct underlying customer and internal threads."
 agent_oracle:str="Offline Oracle checks the correct eligibility/P2 review, recipient and semantically correct unsent replacement draft, required evidence page views, and unchanged source data."
 user_oracle:str="Offline Oracle checks one exact reply sent to ops-oncall@company.test in OPS-117 and the thread marked done."
 natural_condition:str="Shared actors start concurrently with ordinary fixed User think-time; no forced event ordering or injected interference."
 budget:str="40 Codex GUI MCP calls and 1200-second Agent cap in every model arm; User uses a five-action open-loop replay."


def _fixture_hash()->str:
 value={"fixture":FIXTURE_ID,"sources":"CUST-2048/DLV-7718/POL-WAR-3","user_thread":USER_THREAD,"reply":USER_REPLY}
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
class Backend:
 def __init__(self,root:Path,guest_id:str,run_id:str,gateway:str):
  self.guest_id=guest_id;self.db_path=root/"backend"/guest_id/"mailbox.sqlite3"
  self.manifest=create_fixture(self.db_path,run_id+"-"+guest_id)
  self.server=make_server(self.db_path,host="0.0.0.0",port=0)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name="mail-web-"+guest_id);self.thread.start()
  self.url=f"http://{gateway}:{self.server.server_port}"
  self.health_url=f"http://127.0.0.1:{self.server.server_port}"
 def healthcheck(self):
  import urllib.request
  with urllib.request.urlopen(self.health_url+"/healthz",timeout=5) as r:
   if r.status!=200:raise RuntimeError("Mail fixture health failed")
 def evaluate(self):return evaluate(self.db_path)
 def close(self):
  try:self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
  except Exception:pass

def _setup_mail_guest(guest:Guest,backend:Backend,guest_dir:Path,run_id:str)->dict[str,Any]:
 import shlex
 backend.healthcheck();_guest_exec(guest,f"curl -fsS --max-time 10 {backend.url+'/healthz'!r}",timeout=20)
 profile=f"/tmp/ha-mail-{run_id}-{backend.guest_id}";url=backend.url+"/mail";log=profile+"-launch.log"
 p,u,l=map(shlex.quote,(profile,url,log));title=shlex.quote("CoDesk Mail - Inbox")
 guest_dir.mkdir(parents=True,exist_ok=True)
 try:
  _guest_exec(guest,f"""mkdir -p {p}
  (DISPLAY=:0 google-chrome --user-data-dir={p} --no-first-run --no-default-browser-check --disable-gpu --new-window {u} >{l} 2>&1 &)
  ready=false
  for attempt in 1 2 3 4; do
   for i in $(seq 1 35); do if wmctrl -l 2>/dev/null | grep -Fqi {title}; then ready=true; break; fi; sleep 1; done
   [ "$ready" = true ] && break
   wid=$(wmctrl -l 2>/dev/null | awk 'tolower($0) ~ /google chrome/ {{id=$1}} END {{print id}}')
   if [ -n "$wid" ]; then
    wmctrl -ia "$wid" || true; sleep .5; xdotool windowactivate --sync "$wid" 2>/dev/null || true; sleep .5
    xdotool key --clearmodifiers ctrl+l; sleep .3; xdotool type --clearmodifiers --delay 8 -- {u}; xdotool key --clearmodifiers Return; sleep 2
   fi
  done
  [ "$ready" = true ] || {{ echo 'CoDesk Mail inbox did not load'; wmctrl -lpG; xdotool getactivewindow getwindowname 2>&1 || true; tail -80 {l}; exit 1; }}
  """,timeout=170)
 except Exception as exc:
  try:(guest_dir/"mail-readiness-failed.png").write_bytes(guest.screenshot(patience=30))
  except Exception:pass
  try:(guest_dir/"mail-readiness-diagnostics.txt").write_text(str(_guest_exec(guest,"wmctrl -lpG 2>&1 || true; xdotool getactivewindow getwindowname 2>&1 || true; ps -eo pid,comm,args | grep -E 'chrom(e|ium)' | grep -v grep || true",timeout=15)),encoding="utf-8")
  except Exception:pass
  raise InfraError(f"CoDesk Mail Chrome readiness failed: {type(exc).__name__}: {str(exc)[:500]}") from exc
 screenshot=guest.screenshot(patience=60);(guest_dir/"mail-inbox-setup.png").write_bytes(screenshot)
 if len(screenshot)<1000:raise InfraError("CoDesk Mail setup screenshot is invalid")
 active=guest.active_window();windows=_guest_exec(guest,"wmctrl -lpG 2>/dev/null || true",timeout=15)
 return {"profile":profile,"mail_url":url,"active_window":active,"window_inventory":windows,
  "screenshot_bytes":len(screenshot),"mail_window_ready":"CoDesk Mail - Inbox" in windows,
  "fixture_content_sha256":backend.manifest["source_content_sha256"],"initial_state":backend.manifest["initial_state"]}

def _user_actions()->list[GUIAction]:
 delay=.75
 return [
  GUIAction("open_ops_thread","pyautogui.click(440, 590); time.sleep(1.2)","CoDesk Mail",delay),
  GUIAction("open_reply_composer","pyautogui.click(155, 530); time.sleep(1.2)","CoDesk Mail",delay),
  GUIAction("type_ops_reply","pyautogui.click(500, 700); pyautogui.write('I can cover 14:00-16:00 today; please assign me the queue.', interval=0.02)","CoDesk Mail",delay),
  GUIAction("send_ops_reply","pyautogui.click(323, 790); time.sleep(1.2)","CoDesk Mail",delay),
  GUIAction("mark_ops_done","pyautogui.click(280, 590); time.sleep(1.0)","CoDesk Mail",delay),
 ]

def _prepare_agent(guest:Guest,backend:Backend,out:Path,lock_path:Path|None,budget:int,timeout:float,model:str,endpoint:str):
 from .harness import AgentContext,make_harness
 binary=os.environ.get("CODEX_CLI_BIN") or shutil.which("codex")
 if not binary:
  pinned=Path.home()/".cache/codesk-codex-0.155.0-20261108/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
  if pinned.is_file():binary=str(pinned)
 if not binary:raise RuntimeError("Codex CLI not found; set CODEX_CLI_BIN to pinned 0.155.0")
 import shlex
 mcp_log=out/"mcp-server.stderr.log";mcp_cmd=f"exec {shlex.quote(sys.executable)} -m oscombo.desktop_tools --mcp 2>>{shlex.quote(str(mcp_log))}"
 options={"codex_bin":binary,"node_bin":os.environ.get("CODEX_NODE_BIN"),"base_url":endpoint,
  "api_key_env":"OPENAI_API_KEY","wire_api":"responses","timeout":timeout,"run_id":os.environ.get("OSCOMBO_RUN_ID"),
  "expected_app":"Google Chrome","mcp_command":"/bin/bash","mcp_args":["-c",mcp_cmd],
  "codex_home_base":os.environ.get("CODEX_HOME_BASE","/home/mjh/.cache/codesk-ha-codex-home")}
 spec={"harness":"codex","model":model,"effort":"low","base_url":endpoint,"options":options}
 ctx=AgentContext(name="agent",task_id=CASE_ID,instruction=AGENT_TASK,out=out,guest=guest,max_steps=budget,spec=spec,action_lock_file=str(lock_path) if lock_path else None)
 harness=make_harness(spec);harness.prepare(ctx);return harness,ctx

def _schedule_user_actor(run_user, delay_s:float, event_log:EventLog, guest_id:str):
 delay=float(delay_s)
 if delay<0:raise ValueError("user_start_delay_s must be nonnegative")
 def run():
  event_log.emit("user","actor_scheduled",guest_id=guest_id,start_delay_s=delay,fixed_mechanism_probe=delay>0)
  if delay:time.sleep(delay)
  return run_user()
 return run

def _costs(rows:list[dict[str,Any]],user_result:dict[str,Any]|None,agent_result:dict[str,Any]|None)->dict[str,Any]:
 user_rows=[r for r in rows if r.get("actor_id")=="user" and r.get("event_type")=="gui_action"]
 agent_rows=[r for r in rows if r.get("actor_id")=="agent" and r.get("event_type")=="agent_gui_action"]
 return {"user":{"gui_actions":len(user_rows),"baseline_gui_actions":len(_user_actions()),
   "extra_operations_over_fixed_script":max(0,len(user_rows)-len(_user_actions())),
   "elapsed_s":(user_result or {}).get("elapsed_s"),"lock_wait_s":sum(float(x.get("lock_wait_s",0)) for x in user_rows),
   "wrong_foreground_actions":[x.get("event_id") for x in user_rows if x.get("misrouted_focus_before")],"recoveries":0},
  "agent":{"gui_mcp_calls":len(agent_rows),"elapsed_s":(agent_result or {}).get("elapsed_s"),
   "wrong_foreground_actions":[x.get("event_id") for x in agent_rows if x.get("misrouted_focus_before")],
   "token_usage":(agent_result or {}).get("extra",{}).get("token_usage")}}

def run_condition(*,mode:str,out:Path,model:str="gpt-6-sol",endpoint:str|None=None,budget:int=AGENT_BUDGET,timeout:float=AGENT_TIMEOUT,image:str|None=None,user_start_delay_s:float=0.0)->dict[str,Any]:
 if mode not in MODES:raise ValueError(f"mode must be one of {MODES}")
 root=out.resolve()
 if not str(root).startswith("/mnt/raid1/"):raise ValueError("pilot output must be under /mnt/raid1")
 if root.exists() and any(root.iterdir()):raise FileExistsError(f"refusing to overwrite non-empty run: {root}")
 root.mkdir(parents=True,exist_ok=True)
 run_id=f"ha-mail-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
 image_path=Path(image or os.environ.get("OSCOMBO_GUEST_IMAGE","/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
 if not image_path.is_file():raise FileNotFoundError(image_path)
 resource=preflight(root,image_path);(root/"resource-preflight.json").write_text(json.dumps(resource,indent=2,ensure_ascii=False)+"\n")
 if not resource["ready"]:
  result={"case_id":CASE_ID,"case_version":CASE_VERSION,"mode":mode,"status":"blocked-resource-preflight","experiment_valid":False,"model_called":False,"resource_preflight":resource}
  (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n");return result
 from . import combo,osworld
 osworld.activate();os.environ["SWCUB_RUN_ID"]=run_id;os.environ["OSCOMBO_RUN_ID"]=run_id
 started=time.monotonic();os.environ["OSCOMBO_RUN_START_MONO"]=str(started);os.environ["SWCUB_OWNER_TOKEN"]=secrets.token_hex(32)
 os.environ["SWCUB_RESOURCE_LEDGER"]=str(root/"resource-ledger.jsonl");os.environ["SWCUB_OSWORLD_OVERLAY_HOST_DIR"]=str(root/"overlays")
 os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",resource["runtime_image"]);os.environ["SWCUB_OSWORLD_VM_READY_TIMEOUT"]="600"
 os.environ.setdefault("OSWORLD_DIR","/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
 gids=["guest-user","guest-agent"] if mode=="independent" else ["guest-shared"]
 needs_user=mode in {"user-only","independent","shared","shared-lock"};needs_agent=mode in {"agent-only","independent","shared","shared-lock"}
 event_log=EventLog(root/"events.jsonl",run_id,root,started)
 event_log.emit("orchestrator","run_started",case_id=CASE_ID,case_version=CASE_VERSION,mode=mode,agent_kind="codex",model=model if needs_agent else None,user_strategy="fixed-open-loop",fixed_mechanism_probe=user_start_delay_s>0,user_start_delay_s=user_start_delay_s,
  natural_parallelism=mode in {"independent","shared","shared-lock"} and user_start_delay_s==0)
 lock_path=Path(f"/tmp/{run_id}.gui-action.lock") if mode=="shared-lock" else None
 if lock_path:os.environ["OSCOMBO_ACTION_LOCK_FILE"]=str(lock_path)
 else:os.environ.pop("OSCOMBO_ACTION_LOCK_FILE",None)
 backends={};envs={};guests={};setup={};boot={};monitors=[];actor_runs={"results":{},"errors":{}};oracle={};model_called=False;equivalence=None
 started_run=time.monotonic();status="finished"
 try:
  gateway=resource["docker_bridge_gateway"]
  for gid in gids:backends[gid]=Backend(root,gid,run_id,gateway)
  def boot_one(gid:str)->None:
   gd=root/"guests"/gid;gd.mkdir(parents=True,exist_ok=True)
   env=combo.boot(str(image_path),str(gd/"cache"));envs[gid]=env;guest=Guest(env);guests[gid]=guest
   t=time.monotonic();guest.wait_desktop(patience=600);shot=guest.screenshot(patience=60)
   if not shot or len(shot)<1000:raise InfraError("blank/invalid desktop screenshot")
   (gd/"desktop-ready.png").write_bytes(shot)
   provider=getattr(env,"provider",None);container=getattr(provider,"container",None);cid=getattr(container,"id",None);qemu="";kvm=False
   if cid:
    p=subprocess.run(["docker","exec",cid,"ps","-eo","args"],capture_output=True,text=True,timeout=15)
    qemu=next((x.strip() for x in p.stdout.splitlines() if "qemu-system" in x),"")
    kvm=subprocess.run(["docker","exec",cid,"test","-r","/dev/kvm"],capture_output=True,timeout=15).returncode==0
   boot[gid]={"ready_wait_s":round(time.monotonic()-t,3),"screenshot_bytes":len(shot),"live_qemu_acceleration":"KVM" if "accel=kvm" in qemu and kvm else ("TCG/unknown" if qemu else "not-observed"),"container_kvm_readable":kvm,"qemu_command":qemu[:1000]}
  if mode=="independent":
   ts=[threading.Thread(target=boot_one,args=(gid,),name="boot-"+gid) for gid in gids]
   [t.start() for t in ts];[t.join() for t in ts]
   if len(guests)!=2:raise InfraError("Independent requires two ready Guests")
  else:boot_one(gids[0])
  for gid in gids:
   setup[gid]=_setup_mail_guest(guests[gid],backends[gid],root/"guests"/gid,run_id);backends[gid].healthcheck()
  for gid in gids:
   mon=FocusMonitor(guests[gid],gid,event_log,root/"focus"/gid,interval=.5);monitors.append(mon);mon.start()
  user_gid="guest-user" if mode=="independent" else gids[0];agent_gid="guest-agent" if mode=="independent" else gids[0]
  funcs=[]
  if needs_user:
   actor=ScriptedGUIActor(actor_id="user",guest=guests[user_gid],actions=_user_actions(),event_log=event_log,out=root,guest_id=user_gid,lock_path=lock_path,strategy="fixed")
   funcs.append(("user",_schedule_user_actor(actor.run,user_start_delay_s,event_log,user_gid)))
  if needs_agent:
   harness,ctx=_prepare_agent(guests[agent_gid],backends[agent_gid],root,lock_path,budget,timeout,model,endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.haogpt.net/v1")
   def run_agent():
    nonlocal model_called
    model_called=True;t=time.monotonic();event_log.emit("agent","actor_started",guest_id=agent_gid,actor_kind="codex_gui")
    ctx.t0=time.time();ar=harness.run(ctx);payload={"status":ar.status,"error":ar.error,"steps":ar.steps,"extra":ar.extra,"elapsed_s":round(time.monotonic()-t,3)}
    event_log.emit("agent","actor_finished",guest_id=agent_gid,elapsed_s=payload["elapsed_s"],status=ar.status,steps=ar.steps,token_usage=ar.extra.get("token_usage"));return payload
   funcs.append(("agent",run_agent))
  actor_runs=_run_parallel(funcs);time.sleep(1)
  for mon in monitors:mon.stop()
  if needs_user:oracle["user"]=backends[user_gid].evaluate()["user"]
  if needs_agent:oracle["agent"]=backends[agent_gid].evaluate()["agent"]
  success={"user":oracle.get("user",{}).get("success") if needs_user else None,"agent":oracle.get("agent",{}).get("success") if needs_agent else None}
  joint=bool(success["user"] and success["agent"]) if needs_user and needs_agent else None
  if mode=="independent":
   manifests=[backends[g].manifest for g in gids]
   equivalence={"fixture_content_sha256_equal":len({m["source_content_sha256"] for m in manifests})==1,
    "initial_state_equal":len({json.dumps(m["initial_state"],sort_keys=True) for m in manifests})==1,
    "both_inboxes_start_unmodified":all(m["initial_state"]["review_count"]==m["initial_state"]["draft_count"]==m["initial_state"]["sent_count"]==0 for m in manifests)}
   if not all(equivalence.values()):status="invalid-fixture-inequivalence"
  rows=_events(root/"events.jsonl");costs=_costs(rows,actor_runs["results"].get("user"),actor_runs["results"].get("agent"))
  agent_gui_calls=costs["agent"]["gui_mcp_calls"];agent_no_tool=bool(needs_agent and agent_gui_calls==0)
  if agent_no_tool:status="infrastructure-invalid"
  elif any(value is False for value in success.values() if value is not None):status="valid-task-failure"
  else:status="valid-task-success"
  task_card=asdict(TaskCard())
  task_card["user_schedule"]={"kind":"fixed-mechanism-probe" if user_start_delay_s>0 else "natural-open-loop","start_delay_s":user_start_delay_s}
  if user_start_delay_s>0:
   task_card["natural_condition"]="Controlled User start offset to probe GUI-state interference; this is not the natural Shared condition."
  result={"case_id":CASE_ID,"case_version":CASE_VERSION,"task_card":task_card,"run_id":run_id,"mode":mode,
   "agent_kind":"codex" if needs_agent else None,"model":model if needs_agent else None,"status":status,
   "experiment_valid":status not in {"invalid-fixture-inequivalence","infrastructure-invalid","orchestrator-error"},
   "model_called":model_called,"agent_no_gui_tool_calls":agent_no_tool if needs_agent else None,
   "actor_results":actor_runs.get("results",{}),"actor_errors":actor_runs.get("errors",{}),"actor_success":success,"joint_success":joint,
   "oracle":oracle,"costs":costs,"fixture_equivalence":equivalence,"fixture_state_sha256":_fixture_hash(),
   "fixture_hashes":{g:{"source_content_sha256":backends[g].manifest["source_content_sha256"],"initial_state":backends[g].manifest["initial_state"]} for g in gids},
   "guest_setup":setup,"guest_boot":boot,"resource_preflight":resource,"guest_count":len(guests),"base_image":str(image_path),
   "resource_ledger":str(root/"resource-ledger.jsonl"),"overlay_root":str(root/"overlays"),
   "app_topology":"One local offline webmail app and one visible Chrome window per Guest; Independent uses equivalent two-Guest clones; Shared uses one inbox/window/thread state.",
   "user_task":USER_TASK,"agent_task":AGENT_TASK,"agent_budget":{"gui_mcp_calls":budget,"actor_wall_cap_s":timeout},
   "natural_parallelism":mode in {"independent","shared","shared-lock"} and user_start_delay_s==0,
   "fixed_mechanism_probe":user_start_delay_s>0,"user_schedule":{"kind":"fixed-mechanism-probe" if user_start_delay_s>0 else "natural-open-loop","start_delay_s":user_start_delay_s},"elapsed_s":round(time.monotonic()-started_run,3),
   "limitations":["single pilot run per condition; not a failure-rate estimate","User is fixed open-loop with no automatic recovery","the local synthetic email app does not send external mail","task threads are independent; observed differences target shared mailbox UI state"]}
  (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+"\n")
  event_log.emit("orchestrator","run_finished",status=status,elapsed_s=result["elapsed_s"],actor_success=success,joint_success=joint);return result
 except Exception as exc:
  status="infrastructure-invalid" if isinstance(exc,InfraError) else "orchestrator-error"
  failure={"case_id":CASE_ID,"case_version":CASE_VERSION,"run_id":run_id,"mode":mode,"status":status,"experiment_valid":False,"model_called":model_called,"elapsed_s":round(time.monotonic()-started_run,3),"error":f"{type(exc).__name__}: {exc}","traceback":traceback.format_exc()[-4500:],"resource_preflight":resource,"resource_ledger":str(root/"resource-ledger.jsonl"),"overlay_root":str(root/"overlays"),"historical_artifacts_preserved":True}
  if not (root/"run.json").exists():(root/"run.json").write_text(json.dumps(failure,indent=2)+"\n")
  event_log.emit("orchestrator","run_failed",status=status,error=failure["error"][:1000]);raise
 finally:
  for mon in monitors:
   try:mon.stop()
   except Exception:pass
  for backend in backends.values():
   try:backend.close()
   except Exception:pass
  for env in envs.values():
   try:env.close()
   except Exception:pass
  try:
   cleaned=_cleanup_owned_guest(root,run_id)
   if cleaned:(root/"cleanup.json").write_text(json.dumps(cleaned,indent=2)+"\n")
  except Exception as exc:(root/"cleanup-warning.json").write_text(json.dumps({"status":"safe-cleanup-error","error":str(exc)[:500]},indent=2)+"\n")
  for name in ("OSCOMBO_ACTION_LOCK_FILE","OSCOMBO_ACTION_LOCK_EVENTS_FILE","OSCOMBO_RUN_ID","OSCOMBO_RUN_START_MONO"):
   os.environ.pop(name,None)

def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--mode",choices=MODES,required=True);p.add_argument("--out",type=Path,required=True)
 p.add_argument("--model",default="gpt-6-sol");p.add_argument("--base-url",default=os.environ.get("OPENAI_BASE_URL"));p.add_argument("--budget",type=int,default=AGENT_BUDGET);p.add_argument("--timeout",type=float,default=AGENT_TIMEOUT);p.add_argument("--image");p.add_argument("--user-start-delay-s",type=float,default=0.0)
 a=p.parse_args();print(json.dumps(run_condition(mode=a.mode,out=a.out,model=a.model,endpoint=a.base_url,budget=a.budget,timeout=a.timeout,image=a.image,user_start_delay_s=a.user_start_delay_s),indent=2,ensure_ascii=False,default=str))
if __name__=="__main__":main()