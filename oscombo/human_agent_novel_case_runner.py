"""Generic runner for three low-overlap human-agent workflow pilots."""
from __future__ import annotations
import argparse, hashlib, importlib, json, os, secrets, shutil, subprocess, threading, time, traceback, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from .eventlog import EventLog
from .guest import Guest, InfraError
from .human_actor import GUIAction, ScriptedGUIActor
from .human_schedule import wait_for_first_agent_input, timeline_metrics
from .human_poc import FocusMonitor
from .human_agent_case_runner import preflight, _cleanup_owned_guest, _events, _run_parallel, _guest_exec, _codex_no_tool_infra_failure

CASES = {"code-review":"code_review","access-review":"access_review","transit-itinerary":"transit_planner","consumer-banking":"consumer_banking","lab-qc":"lab_qc","home-energy":"home_energy"}
MODES=("user-only","agent-only","independent","shared","shared-lock")
@dataclass(frozen=True)
class TaskCard:
    case_id:str
    version:str
    title:str
    agent_task:str
    user_task:str
    shared_state:str
    agent_oracle:str
    user_oracle:str
    natural_condition:str
    agent_budget:str="See agent_budget in run.json for exact per-run call and wall caps; paired arms must match."
    scheduled_probe:str="Natural arms co-start. Controlled probes may start the User after the Agent's first GUI input event or use an explicit fixed delay; these are not natural-concurrency observations."

def _manifest_basis(m):
    public={k:v for k,v in m.items() if k not in {"run_id","sha256"}}
    return hashlib.sha256(json.dumps(public,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

class Backend:
    def __init__(self,app,root:Path,gid:str,run_id:str,gateway:str):
        self.app=app;self.guest_id=gid
        self.db=root/"backend"/gid/(app.FIXTURE_ID+".sqlite3")
        self.db.parent.mkdir(parents=True,exist_ok=True)
        self.manifest=app.create_fixture(self.db,run_id+"-"+gid)
        self.server=app.make_server(self.db,host="0.0.0.0",port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name="app-"+gid);self.thread.start()
        self.url=f"http://{gateway}:{self.server.server_port}"
    def healthcheck(self):
        with urllib.request.urlopen(self.url+"/healthz",timeout=5) as r:
            if r.status!=200:raise InfraError("app healthcheck failed")
    def evaluate(self):return self.app.evaluate(self.db)
    def close(self):
        try:self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        except Exception:pass

def _open_app(guest:Guest,profile:str,url:str,title:str,guest_dir:Path)->dict[str,Any]:
    import shlex
    pq=shlex.quote(profile);uq=shlex.quote(url);logq=shlex.quote(profile+"-chrome-launch.log")
    _guest_exec(guest,f"mkdir -p {pq}; (DISPLAY=:0 google-chrome --user-data-dir={pq} --no-first-run --no-default-browser-check --disable-gpu --new-window {uq} >{logq} 2>&1 &)",timeout=35)
    tq=shlex.quote(title)
    wait_for_title = lambda seconds: f"""for i in $(seq 1 {seconds}); do
          if wmctrl -l 2>/dev/null | grep -Fqi {tq}; then
            wid=$(xdotool search --onlyvisible --name {tq} 2>/dev/null | tail -n 1)
            [ -z "$wid" ] || wmctrl -ia "$wid"
            wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz 2>/dev/null || true
            sleep 1; exit 0
          fi; sleep 1
        done
        exit 1
        """
    navigation_fallback = False
    try:
        try:
            _guest_exec(guest,wait_for_title(25),timeout=35)
        except Exception:
            # Chrome occasionally creates its window but ignores the initial URL
            # while its first-run/network services are still starting. Navigate in
            # the visible browser, then still require the exact task-app title.
            navigation_fallback = True
            _guest_exec(guest,f"xdotool key --clearmodifiers ctrl+l; sleep 0.3; xdotool type --clearmodifiers --delay 15 -- {uq}; xdotool key Return",timeout=20)
            _guest_exec(guest,wait_for_title(65),timeout=75)
    except Exception as e:
        _guest_exec(guest,f"echo 'case app did not become visible'; wmctrl -lpG || true; tail -40 {logq} || true",timeout=20)
        raise InfraError(f"browser app readiness failed for {title}: {e}") from e
    windows=_guest_exec(guest,"wmctrl -lpG 2>/dev/null || true",timeout=20)
    active=guest.active_window()
    if title.lower() not in (active or "").lower():raise InfraError(f"wrong active title after app setup: {active!r}")
    shot=guest.screenshot(patience=60)
    if not shot or len(shot)<1000:raise InfraError("case app screenshot blank")
    (guest_dir/"setup.png").write_bytes(shot)
    return {"url":url,"window_inventory":windows,"active_window":active,"screenshot_bytes":len(shot),"navigation_fallback_used":navigation_fallback}

def _prepare_agent(app,backend:Backend,guest:Guest,guest_id:str,out:Path,lock_path:Path|None,budget:int,timeout:float,model:str,endpoint:str):
    from .harness import AgentContext,make_harness
    binary=os.environ.get("CODEX_CLI_BIN") or shutil.which("codex")
    if not binary:
        pinned=Path.home()/".cache/codesk-codex-0.155.0-20261108/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
        if pinned.is_file():binary=str(pinned)
    if not binary:raise RuntimeError("Codex CLI 0.155.0 was not found")
    options={"codex_bin":binary,"node_bin":os.environ.get("CODEX_NODE_BIN"),"base_url":endpoint,
        "api_key_env":"OPENAI_API_KEY","wire_api":"responses","timeout":timeout,"run_id":os.environ.get("OSCOMBO_RUN_ID"),
        "expected_app":"Google Chrome","guest_id":guest_id,"mcp_required":True,"codex_home_base":os.environ.get("CODEX_HOME_BASE","/home/mjh/.cache/codesk-ha-codex-home")}
    spec={"harness":"codex","model":model,"effort":"low","base_url":endpoint,"options":options}
    instruction=app.AGENT_TASK+"\n\nStart from the open CoDesk task dashboard. Save the requested result and verify the visible confirmation. Do not inspect local files or use any evaluator."
    ctx=AgentContext(name="agent",task_id=app.CASE_ID,instruction=instruction,guest=guest,out=out,max_steps=budget,spec=spec,
        action_lock_file=str(lock_path) if lock_path else None)
    h=make_harness(spec);h.prepare(ctx);return h,ctx

def _costs(rows,user_result,agent_result,monitors,baseline):
    timeline=timeline_metrics(rows)
    ur=[x for x in rows if x.get("actor_id")=="user" and x.get("event_type")=="gui_action"]
    ar=[x for x in rows if x.get("actor_id")=="agent" and x.get("event_type")=="agent_gui_action"]
    locks=[x for x in rows if x.get("event_type")=="action_lock"]
    usage=(agent_result or {}).get("extra",{})
    title="google chrome"
    return {
      "user":{"gui_actions":len(ur),"baseline_gui_actions":baseline,"extra_operations_over_fixed_script":max(0,len(ur)-baseline),
        "wrong_foreground_actions":sum(bool(x.get("misrouted_focus_before")) or title not in str(x.get("window_before") or "").lower() for x in ur),
        "input_errors":sum(bool(x.get("error")) for x in ur),"observed_gui_action_s":round(sum(float(x.get("duration_s",0)) for x in ur),3),
        "actor_wall_s":(user_result or {}).get("elapsed_s"),"lock_wait_s":round(sum(float(x.get("lock_wait_s",0)) for x in ur),3),
        "recovery_strategy":"fixed-open-loop; no automatic recovery"},
      "agent":{"gui_mcp_calls":len(ar),"wrong_foreground_actions":sum(title not in str(x.get("window_before") or "").lower() for x in ar),
        "mcp_errors":sum(x.get("status") in {"error","out_of_budget"} for x in ar),
        "actor_wall_s":usage.get("agent_s"),"token_usage":usage.get("token_usage")},
      "focus_transitions":sum(m.transitions for m in monitors),"action_lock_calls":len(locks),
      "total_lock_wait_s":round(sum(float(x.get("lock_wait_s",0)) for x in locks),3),
      "timeline":timeline}

def run_condition(*,case:str,mode:str,out:Path,model:str="gpt-6-sol",endpoint:str|None=None,budget:int=40,timeout:float=1200,
                  image:str|None=None,user_start_delay:float=0.0,user_start_trigger:str="simultaneous")->dict[str,Any]:
    if case not in CASES:raise ValueError(f"case must be one of {tuple(CASES)}")
    if mode not in MODES:raise ValueError(f"mode must be one of {MODES}")
    if user_start_delay<0 or user_start_delay>300:raise ValueError("user_start_delay must be within [0,300]")
    if user_start_trigger not in {"simultaneous","first-agent-input"}:raise ValueError("user_start_trigger must be simultaneous or first-agent-input")
    if user_start_trigger!="simultaneous" and (mode not in {"independent","shared","shared-lock"} or user_start_delay):raise ValueError("first-agent-input trigger requires a paired User+Agent mode and no fixed delay")
    app=importlib.import_module(".human_apps."+CASES[case],package="oscombo")
    root=out.resolve()
    if not str(root).startswith("/mnt/raid1/"):raise ValueError("all outputs must be under /mnt/raid1")
    if root.exists() and any(root.iterdir()):raise FileExistsError(f"refusing to overwrite non-empty run: {root}")
    root.mkdir(parents=True,exist_ok=True)
    run_id=f"{app.CASE_ID}-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    image_path=Path(image or os.environ.get("OSCOMBO_GUEST_IMAGE","/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
    if not image_path.is_file():raise FileNotFoundError(image_path)
    resource=preflight(root,image_path)
    (root/"resource-preflight.json").write_text(json.dumps(resource,indent=2,ensure_ascii=False)+"\n")
    if not resource["ready"]:
        result={"case_id":app.CASE_ID,"case_version":app.CASE_VERSION,"mode":mode,"status":"blocked-resource-preflight",
            "experiment_valid":False,"model_called":False,"resource_preflight":resource}
        (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n");return result

    os.environ.setdefault("OSWORLD_DIR","/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
    from . import osworld,combo
    from .osworld import client_password
    osworld.activate()
    os.environ["SWCUB_RUN_ID"]=run_id;os.environ["OSCOMBO_RUN_ID"]=run_id
    started_mono=time.monotonic();os.environ["OSCOMBO_RUN_START_MONO"]=str(started_mono)
    os.environ["SWCUB_OWNER_TOKEN"]=secrets.token_hex(32);os.environ["SWCUB_RESOURCE_LEDGER"]=str(root/"resource-ledger.jsonl")
    os.environ["SWCUB_OSWORLD_OVERLAY_HOST_DIR"]=str(root/"overlays")
    os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",resource["runtime_image"])
    os.environ["SWCUB_OSWORLD_VM_READY_TIMEOUT"]="600"
    os.environ.setdefault("OSWORLD_DIR","/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
    gids=["guest-user","guest-agent"] if mode=="independent" else ["guest-shared"]
    needs_user=mode in {"user-only","independent","shared","shared-lock"}
    needs_agent=mode in {"agent-only","independent","shared","shared-lock"}
    backends={};envs={};guests={};monitors=[];setups={};boots={}
    event_log=EventLog(root/"events.jsonl",run_id,root,started_mono)
    probe=user_start_delay>0 or user_start_trigger!="simultaneous"
    event_log.emit("orchestrator","run_started",case_id=app.CASE_ID,case_version=app.CASE_VERSION,mode=mode,
      agent_kind="codex",model=model if needs_agent else None,user_strategy="fixed-open-loop",
      fixed_mechanism_probe=user_start_delay>0,event_trigger_probe=user_start_trigger!="simultaneous",
      user_start_trigger=user_start_trigger,natural_parallelism=mode in {"independent","shared","shared-lock"} and not probe,
      user_start_delay_s=user_start_delay)
    lock_path=Path(f"/tmp/{run_id}.gui-action.lock") if mode=="shared-lock" else None
    if lock_path:os.environ["OSCOMBO_ACTION_LOCK_FILE"]=str(lock_path)
    else:os.environ.pop("OSCOMBO_ACTION_LOCK_FILE",None)
    actor_runs={"results":{},"errors":{}};oracle={};status="finished";model_called=False;run_started=time.monotonic();trigger_info={}
    try:
        gateway=resource["docker_bridge_gateway"]
        for gid in gids:backends[gid]=Backend(app,root,gid,run_id,gateway)
        def boot_one(gid):
            guest_dir=root/"guests"/gid;guest_dir.mkdir(parents=True,exist_ok=True)
            t0=time.monotonic();env=combo.boot(str(image_path),str(guest_dir/"cache"));envs[gid]=env;guest=Guest(env);guests[gid]=guest
            guest.wait_desktop(patience=600);shot=guest.screenshot(patience=60)
            if not shot or len(shot)<1000:raise InfraError("blank Guest desktop")
            (guest_dir/"desktop-ready.png").write_bytes(shot)
            provider=getattr(env,"provider",None);container=getattr(provider,"container",None);cid=getattr(container,"id",None)
            live_qemu="";container_kvm=False
            if cid:
                q=subprocess.run(["docker","exec",cid,"ps","-eo","args"],capture_output=True,text=True,timeout=15)
                live_qemu=next((line.strip() for line in q.stdout.splitlines() if "qemu-system" in line),"")
                k=subprocess.run(["docker","exec",cid,"test","-r","/dev/kvm"],capture_output=True,timeout=15);container_kvm=k.returncode==0
            accel="KVM" if "accel=kvm" in live_qemu and container_kvm else ("TCG/unknown" if live_qemu else "not-observed")
            boots[gid]={"ready_wait_s":round(time.monotonic()-t0,3),"screenshot_bytes":len(shot),
              "live_qemu_acceleration":accel,"container_kvm_readable":container_kvm,"qemu_command":live_qemu[:1000]}
        if mode=="independent":
            ts=[threading.Thread(target=boot_one,args=(gid,)) for gid in gids]
            [t.start() for t in ts];[t.join() for t in ts]
            if len(guests)!=2:raise InfraError("Independent requires two ready Guests")
        else:boot_one(gids[0])
        for gid in gids:
            backends[gid].healthcheck()
            guest=guests[gid]
            url=backends[gid].url+"/"
            _guest_exec(guest,f"curl -fsS --max-time 10 {url!r}",timeout=20)
            setups[gid]=_open_app(guest,f"/tmp/{run_id}-{gid}",url,app.APP_TITLE,root/"guests"/gid)
        for gid in gids:
            m=FocusMonitor(guests[gid],gid,event_log,root/"focus"/gid,interval=.5);monitors.append(m);m.start()
        ugid="guest-user" if mode=="independent" else gids[0];agid="guest-agent" if mode=="independent" else gids[0]
        funcs=[]
        if needs_user:
            actions=app.user_actions()
            if probe and actions:
                a=actions[0];actions[0]=GUIAction(a.name,a.code,a.expected_app,a.delay_before_s+user_start_delay)
            ua=ScriptedGUIActor(actor_id="user",guest=guests[ugid],actions=actions,event_log=event_log,out=root,guest_id=ugid,
                lock_path=lock_path,strategy="fixed")
            if user_start_trigger=="first-agent-input":
                def start_user_after_agent_input():
                    trigger_info.update(wait_for_first_agent_input(root/"events.jsonl",event_log,timeout_s=timeout+60))
                    return ua.run()
                funcs.append(("user",start_user_after_agent_input))
            else:funcs.append(("user",ua.run))
        if needs_agent:
            h,ctx=_prepare_agent(app,backends[agid],guests[agid],agid,root,lock_path,budget,timeout,model,
                endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.haogpt.net/v1")
            def agent_call():
                nonlocal model_called
                model_called=True;t0=time.monotonic()
                event_log.emit("agent","actor_started",guest_id=agid,actor_kind="codex_gui")
                try:
                    ctx.t0=time.time();ar=h.run(ctx);result={"status":ar.status,"error":ar.error,"steps":ar.steps,"extra":ar.extra}
                    event_log.emit("agent","actor_finished",guest_id=agid,elapsed_s=round(time.monotonic()-t0,6),
                        status=ar.status,steps=ar.steps,token_usage=ar.extra.get("token_usage"))
                    return result
                except Exception as exc:
                    event_log.emit("agent","actor_finished",guest_id=agid,elapsed_s=round(time.monotonic()-t0,6),
                        status="exception",error=f"{type(exc).__name__}: {exc}"[:500])
                    raise
            funcs.append(("agent",agent_call))
        actor_runs=_run_parallel(funcs);time.sleep(1)
        for m in monitors:m.stop()
        actor_results=actor_runs["results"];oracle_by_gid={"user":ugid,"agent":agid}
        for actor,needed in (("user",needs_user),("agent",needs_agent)):
            if needed:oracle[actor]=backends[oracle_by_gid[actor]].evaluate()[actor]
        successes={"user":oracle.get("user",{}).get("success") if needs_user else None,
                   "agent":oracle.get("agent",{}).get("success") if needs_agent else None}
        joint=bool(successes["user"] and successes["agent"]) if needs_user and needs_agent else None
        if any(v is False for v in successes.values() if v is not None):status="valid-task-failure"
        rows=_events(root/"events.jsonl");costs=_costs(rows,actor_results.get("user"),actor_results.get("agent"),monitors,len(app.user_actions()))
        if _codex_no_tool_infra_failure("codex",needs_agent,actor_results.get("agent"),costs["agent"]["gui_mcp_calls"],root/"agent"/"stdout.log"):status="infrastructure-invalid"
        equivalence=None
        if mode=="independent":
            basis={gid:_manifest_basis(backends[gid].manifest) for gid in gids}
            equivalence={"fixture_basis_sha256_equal":basis["guest-user"]==basis["guest-agent"],"basis_hashes":basis}
            if not equivalence["fixture_basis_sha256_equal"]:status="invalid-fixture-inequivalence"
        result={"case_id":app.CASE_ID,"case_version":app.CASE_VERSION,"case":case,"mode":mode,
          "task_card":asdict(TaskCard(app.CASE_ID,app.CASE_VERSION,app.TITLE,app.AGENT_TASK,app.USER_TASK,
              app.SHARED_STATE,app.AGENT_ORACLE,app.USER_ORACLE,app.NATURAL_CONDITION,
              agent_budget=f"{budget} GUI MCP calls and {timeout:g}-second actor wall cap; identical in each comparison arm.")),
          "run_id":run_id,"agent_kind":"codex","model":model if needs_agent else None,"status":status,
          "experiment_valid":status not in {"invalid-fixture-inequivalence","infrastructure-invalid","orchestrator-error"},
          "model_called":model_called,"actor_results":actor_results,"actor_errors":actor_runs["errors"],"actor_success":successes,
          "joint_success":joint,"oracle":oracle,"costs":costs,"fixture_equivalence":equivalence,
          "fixture_hashes":{gid:{"manifest_sha256":backends[gid].manifest.get("sha256"),"fixture_basis_sha256":_manifest_basis(backends[gid].manifest)} for gid in gids},
          "guest_setup":setups,"guest_boot":boots,"resource_preflight":resource,"guest_count":len(guests),
          "base_image":str(image_path),"resource_ledger":str(root/"resource-ledger.jsonl"),"overlay_root":str(root/"overlays"),
          "app_topology":"one run-local offline case app per Guest, opened in one maximized Chrome window; the browser/foreground input state is shared in Shared",
          "user_task":app.USER_TASK,"agent_task":app.AGENT_TASK,"agent_budget":{"gui_mcp_calls":budget,"actor_wall_cap_s":timeout},
          "natural_parallelism":mode in {"shared","shared-lock","independent"} and user_start_trigger=="simultaneous" and not user_start_delay,
          "fixed_mechanism_probe":user_start_delay>0,"event_trigger_probe":user_start_trigger!="simultaneous",
          "user_start_trigger":user_start_trigger,"trigger_result":trigger_info or None,
          "user_start_delay_s":user_start_delay,"elapsed_s":round(time.monotonic()-run_started,3),
          "limitations":["one pilot run per condition; no occurrence-rate claim","User is fixed open-loop and does not recover automatically",
            "the local app is a controlled workflow fixture, not the production service","browser window/focus and server-side request logs provide task evidence; no OS-level per-keystroke recipient attribution",
            "Shared interference is interpreted only from UI/event chronology plus independent post-run oracles"]}
        (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+"\n")
        event_log.emit("orchestrator","run_finished",status=status,elapsed_s=result["elapsed_s"],actor_success=successes,joint_success=joint)
        return result
    except Exception as exc:
        status="infrastructure-invalid" if isinstance(exc,InfraError) else "orchestrator-error"
        failed={"case_id":app.CASE_ID,"run_id":run_id,"mode":mode,"status":status,"experiment_valid":False,
          "model_called":model_called,"elapsed_s":round(time.monotonic()-run_started,3),"error":f"{type(exc).__name__}: {exc}",
          "traceback":traceback.format_exc()[-4000:],"resource_preflight":resource,"historical_artifacts_preserved":True}
        if not (root/"run.json").exists():(root/"run.json").write_text(json.dumps(failed,indent=2,ensure_ascii=False)+"\n")
        event_log.emit("orchestrator","run_failed",status=status,error=failed["error"][:1000]);raise
    finally:
        for m in monitors:
            try:m.stop()
            except Exception:pass
        for b in backends.values():b.close()
        for e in envs.values():
            try:e.close()
            except Exception:pass
        try:
            c=_cleanup_owned_guest(root,run_id)
            if c:(root/"cleanup.json").write_text(json.dumps(c,indent=2)+"\n")
        except Exception as e:
            (root/"cleanup-warning.json").write_text(json.dumps({"status":"safe-cleanup-error","error":str(e)[:500]},indent=2)+"\n")
        for name in ("OSCOMBO_ACTION_LOCK_FILE","OSCOMBO_ACTION_LOCK_EVENTS_FILE","OSCOMBO_RUN_ID","OSCOMBO_RUN_START_MONO"):
            os.environ.pop(name,None)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--case",choices=tuple(CASES),required=True);p.add_argument("--mode",choices=MODES,required=True)
 p.add_argument("--out",type=Path,required=True);p.add_argument("--model",default="gpt-6-sol");p.add_argument("--base-url",default=os.environ.get("OPENAI_BASE_URL"))
 p.add_argument("--budget",type=int,default=40);p.add_argument("--timeout",type=float,default=1200);p.add_argument("--image")
 p.add_argument("--user-start-delay",type=float,default=0.0);p.add_argument("--user-start-trigger",choices=("simultaneous","first-agent-input"),default="simultaneous");a=p.parse_args()
 r=run_condition(case=a.case,mode=a.mode,out=a.out,model=a.model,endpoint=a.base_url,budget=a.budget,timeout=a.timeout,image=a.image,user_start_delay=a.user_start_delay,user_start_trigger=a.user_start_trigger)
 print(json.dumps(r,indent=2,ensure_ascii=False,default=str))
if __name__=="__main__":main()

