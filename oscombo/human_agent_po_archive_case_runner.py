"""Human-like User + real Codex GUI Agent pilot: PO reconciliation + receipt archive."""
from __future__ import annotations
import hashlib, json, os, secrets, shutil, subprocess, threading, time, traceback, uuid, sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from .eventlog import EventLog
from .guest import Guest, InfraError
from .human_actor import GUIAction, ScriptedGUIActor
from .human_poc import FocusMonitor
from .human_apps.po_reconcile import (
    CASE_ID, USER_FILE, USER_FILE_CONTENT, create_fixture, evaluate, evaluate_agent, evaluate_user, make_server,
)
from .human_agent_case_runner import (
    _cleanup_owned_guest, _events, _guest_exec, _run_parallel, preflight,
)

CASE_VERSION="0.1.5"
AGENT_TASK="""Review invoice INV-4831 in the open Procurement Review Queue. Inspect the linked purchase order, receiving report, vendor invoice, and freight policy. Then complete the Invoice Reconciliation form: choose the supported disposition, enter the quantity accepted into stock and the freight amount above the authorized cap, cite the source IDs, and write a concise rationale covering each discrepancy. Save once and verify the visible saved confirmation. This is a review only: do not release payment or alter any source record. Use only the visible GUI; do not use hidden evaluator state or CLI."""
USER_TASK="""In the open Vendor Portal, download the signed receiving acknowledgement D-4831. Then attach that downloaded CSV to Finance / November 2026 in the visible Finance Archive page and submit. Verify the confirmation that it was archived. Do not edit other records."""
MODES=("user-only","agent-only","independent","shared","shared-lock")
AGENT_BUDGET=40
AGENT_TIMEOUT=1200

@dataclass(frozen=True)
class TaskCard:
    case_id:str=CASE_ID
    version:str=CASE_VERSION
    title:str="Reconcile a vendor invoice while a user archives a receipt attachment"
    actor_a_task:str=AGENT_TASK
    actor_b_task:str=USER_TASK
    shared_state:str="One Linux desktop session and one Chrome profile with separate native windows. Agent reviews procurement records; User downloads and attaches a signed receipt in a separate archive workflow. They compete for global focus and keyboard/mouse routing."
    agent_oracle:str="Offline form Oracle checks hold disposition, 11 accepted units, $26 freight overage, citations of PO/receiving/invoice/policy, all source pages visited, Agent role, and no source mutation."
    user_oracle:str="Offline archive Oracle checks the expected attachment filename, exact SHA-256 of the downloaded signed CSV, Finance/November 2026 destination, and User role."
    natural_condition:str="Actors start together with a short fixed User think-time; no event-order forcing or injected interference."
    budget:str="40 Codex GUI MCP calls and 1200-second Agent wall cap in all model arms; fixed User replay uses seven GUI actions."
    scheduled_probe:str="None in this first case version. Natural shared impact is retained as observed; no mechanism-tuned interleaving."

def _fixture_hash()->str:
    value={"agent":"PR-4831:PO12x48;accepted11;damaged1;invoicefreight86;cap60;hold",
           "user_file_sha256":hashlib.sha256(USER_FILE_CONTENT).hexdigest(),
           "archive":"Finance/November 2026"}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class Backend:
    def __init__(self,root:Path,guest_id:str,run_id:str,gateway:str):
        self.guest_id=guest_id
        self.db_path=root/"backend"/guest_id/"po-reconcile.sqlite3"
        self.manifest=create_fixture(self.db_path,run_id+"-"+guest_id)
        self.server=make_server(self.db_path,host="0.0.0.0",port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name=f"po-web-{guest_id}")
        self.thread.start()
        self.url=f"http://{gateway}:{self.server.server_port}"
    def healthcheck(self):
        import urllib.request
        with urllib.request.urlopen(self.url+"/healthz",timeout=5) as r:
            if r.status!=200:raise RuntimeError("PO/Archive fixture health failed")
    def evaluate(self):return evaluate(self.db_path)
    def close(self):
        try:self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        except Exception:pass

def _activate_window(guest:Guest,title:str)->str:
    import shlex
    q=shlex.quote(title)
    return _guest_exec(guest,f"""wid=$(wmctrl -l | grep -F {q} | tail -n1 | awk '{{print $1}}')
    test -n "$wid" || {{ wmctrl -lpG; exit 1; }}
    wmctrl -ia "$wid"
    for i in $(seq 1 30); do
      active=$(xdotool getactivewindow getwindowname 2>/dev/null || true)
      case "$active" in *{q}*) echo "$active"; exit 0;; esac
      sleep .2
    done
    echo "could not activate title {title}"; wmctrl -lpG; exit 1
    """,timeout=15).strip()

def _open_chrome_page(guest:Guest,profile:str,url:str,title:str,launchlog:str)->None:
    """Open one titled app page, retrying via the address bar if Chromium starts blank."""
    import shlex
    p,u,l=map(shlex.quote,(profile,url,launchlog))
    expected=shlex.quote(title)
    _guest_exec(guest,f"""(DISPLAY=:0 google-chrome --user-data-dir={p} --no-first-run --no-default-browser-check --disable-gpu --new-window {u} >{l} 2>&1 &)
    for attempt in 1 2 3; do
      for i in $(seq 1 35); do
        if wmctrl -l 2>/dev/null | grep -Fqi {expected}; then exit 0; fi
        sleep 1
      done
      wid=$(wmctrl -l 2>/dev/null | grep -Fqi 'Google Chrome' -B0 -A0 | tail -n1 | awk '{{print $1}}')
      if [ -z "$wid" ]; then wid=$(wmctrl -l 2>/dev/null | tail -n1 | awk '{{print $1}}'); fi
      if [ -n "$wid" ]; then
        wmctrl -ia "$wid" || true
        xdotool key --clearmodifiers ctrl+l
        xdotool type --clearmodifiers --delay 2 -- {u}
        xdotool key --clearmodifiers Return
      fi
    done
    echo "Chrome page did not load: {title}"; wmctrl -lpG; tail -80 {l} 2>/dev/null || true; exit 1
    """,timeout=125)

def _setup_po_guest(guest:Guest,backend:Backend,guest_dir:Path,run_id:str)->dict[str,Any]:
    import shlex,urllib.request
    backend.healthcheck()
    _guest_exec(guest,f"curl -fsS --max-time 10 {backend.url+'/healthz'!r}",timeout=20)
    home=_guest_exec(guest,"printf '%s' \"$HOME\"").strip().splitlines()[-1]
    downloads=f"{home}/Downloads"
    profile=f"/tmp/ha-po-{run_id}-{backend.guest_id}"
    p=shlex.quote(profile);d=shlex.quote(downloads)
    _guest_exec(guest,f"""mkdir -p {d} {p}/Default
    python3 -c "import json,pathlib; p=pathlib.Path({(profile+'/Default/Preferences')!r}); p.write_text(json.dumps({{'download':{{'default_directory':{downloads!r},'prompt_for_download':False,'directory_upgrade':True}}}}))"
    """,timeout=20)
    before=guest.screenshot(patience=60);guest_dir.mkdir(parents=True,exist_ok=True)
    (guest_dir/"desktop-before-apps.png").write_bytes(before)
    _open_chrome_page(guest,profile,backend.url+"/agent","Procurement Review Queue",profile+"-launch.log")
    # Both pages use one Chrome profile in distinct native windows. Portal launch
    # retries via the address bar if the new window initially appears blank.
    _open_chrome_page(guest,profile,backend.url+"/portal","Vendor Portal",profile+"-portal-launch.log")
    active=_activate_window(guest,"Procurement Review Queue")
    shot=guest.screenshot(patience=60);(guest_dir/"setup.png").write_bytes(shot)
    if not shot or len(shot)<1000:raise InfraError("PO/Archive Guest screenshot invalid")
    windows=_guest_exec(guest,"wmctrl -lpG 2>/dev/null || true",timeout=15)
    return {"home":home,"download_directory":downloads,"profile":profile,"window_inventory":windows,
        "active_window":active,"screenshot_bytes":len(shot),"host_health":True,"guest_health":True,
        "agent_window_present":"Procurement Review Queue" in windows,"user_window_present":"Vendor Portal" in windows,
        "initial_fixture_state_sha256":_fixture_hash()}

def _user_actions(home:str)->list[GUIAction]:
    # Navigate to the ordinary Downloads folder in the native file chooser,
    # select its only task file, then submit the visible archive form.
    return [
      GUIAction("switch_to_vendor_portal","pyautogui.hotkey('alt','tab')","Vendor Portal",0.8),
      GUIAction("download_receipt","pyautogui.click(355, 465)","Vendor Portal",1.8),
      GUIAction("open_finance_archive","pyautogui.click(220, 565)","Finance Archive",1.0),
      GUIAction("open_receipt_picker","pyautogui.click(220, 562)",None,0.7),
      # Use the visible Downloads shortcut in GTK instead of Ctrl+L path entry.
      # Earlier runs showed the location entry sometimes remained active under GUI
      # load, making the next click land in the file chooser rather than the page.
      GUIAction("open_downloads_in_picker","pyautogui.click(180, 590, clicks=2, interval=0.2); time.sleep(1.5)","Open File",0.8),
      GUIAction("select_receipt_and_confirm","pyautogui.click(420, 500); time.sleep(0.2); pyautogui.click(930, 388)","Finance Archive",0.5),
      GUIAction("submit_receipt_archive","pyautogui.click(230, 622); time.sleep(2.5)","Finance Archive",1.0),
    ]

def _prepare_agent(guest:Guest,backend:Backend,out:Path,lock_path:Path|None,budget:int,timeout:float,
                   model:str,endpoint:str):
    from .harness import AgentContext,make_harness
    binary=os.environ.get("CODEX_CLI_BIN") or shutil.which("codex")
    if not binary:
        pinned=Path.home()/".cache/codesk-codex-0.155.0-20261108/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
        if pinned.is_file():binary=str(pinned)
    if not binary:raise RuntimeError("Codex CLI not found; set CODEX_CLI_BIN to pinned 0.155.0")
    import shlex
    mcp_log=out/"mcp-server.stderr.log"
    mcp_cmd=f"exec {shlex.quote(sys.executable)} -m oscombo.desktop_tools --mcp 2>>{shlex.quote(str(mcp_log))}"
    options={"codex_bin":binary,"node_bin":os.environ.get("CODEX_NODE_BIN"),"base_url":endpoint,
        "api_key_env":"OPENAI_API_KEY","wire_api":"responses","timeout":timeout,
        "run_id":os.environ.get("OSCOMBO_RUN_ID"),"expected_app":"Google Chrome",
        "mcp_command":"/bin/bash","mcp_args":["-c",mcp_cmd],
        "codex_home_base":os.environ.get("CODEX_HOME_BASE","/home/mjh/.cache/codesk-ha-codex-home")}
    spec={"harness":"codex","model":model,"effort":"low","base_url":endpoint,"options":options}
    ctx=AgentContext(name="agent",task_id=CASE_ID,instruction=AGENT_TASK,out=out,guest=guest,
        max_steps=budget,spec=spec,action_lock_file=str(lock_path) if lock_path else None)
    harness=make_harness(spec);harness.prepare(ctx);return harness,ctx

def _costs(rows,user_result,agent_result,monitors)->dict[str,Any]:
    from .human_agent_case_runner import _costs as base_costs
    costs=base_costs(rows,user_result,agent_result,monitors)
    user_rows=[r for r in rows if r.get("actor_id")=="user" and r.get("event_type")=="gui_action"]
    agent_rows=[r for r in rows if r.get("actor_id")=="agent" and r.get("event_type")=="agent_gui_action"]
    costs["user"]["baseline_gui_actions"]=len(_user_actions("/home/oai/share"))
    costs["user"]["extra_operations_over_fixed_script"]=max(0,len(user_rows)-7)
    authorized=("procurement review queue","purchase order po-4831","receiving report rcv-4831",
                "vendor invoice inv-4831","freight policy pol-frt-2","invoice reconciliation",
                "vendor portal","finance archive","open file")
    costs["agent"]["wrong_foreground_actions_by_title"]=sum(
        bool(r.get("misrouted_focus_before")) or not any(t in (r.get("window_before") or "").lower() for t in authorized)
        for r in agent_rows)
    costs["agent"]["wrong_foreground_action_event_ids"]=[r.get("event_id") for r in agent_rows
        if bool(r.get("misrouted_focus_before")) or not any(t in (r.get("window_before") or "").lower() for t in authorized)]
    return costs

def run_condition(*,mode:str,out:Path,model:str="gpt-6-sol",endpoint:str|None=None,
                  budget:int=AGENT_BUDGET,timeout:float=AGENT_TIMEOUT,image:str|None=None)->dict[str,Any]:
    if mode not in MODES:raise ValueError(f"mode must be one of {MODES}")
    root=out.resolve()
    if not str(root).startswith("/mnt/raid1/"):raise ValueError("pilot output must be under /mnt/raid1")
    if root.exists() and any(root.iterdir()):raise FileExistsError(f"refusing to overwrite non-empty run: {root}")
    root.mkdir(parents=True,exist_ok=True)
    run_id=f"ha-po-archive-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    image_path=Path(image or os.environ.get("OSCOMBO_GUEST_IMAGE","/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
    if not image_path.is_file():raise FileNotFoundError(image_path)
    resource=preflight(root,image_path)
    (root/"resource-preflight.json").write_text(json.dumps(resource,indent=2,ensure_ascii=False)+"\n")
    if not resource["ready"]:
        result={"case_id":CASE_ID,"case_version":CASE_VERSION,"mode":mode,"status":"blocked-resource-preflight",
            "experiment_valid":False,"model_called":False,"resource_preflight":resource}
        (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n");return result
    from . import combo,osworld
    osworld.activate();os.environ["SWCUB_RUN_ID"]=run_id;os.environ["OSCOMBO_RUN_ID"]=run_id
    started=time.monotonic();os.environ["OSCOMBO_RUN_START_MONO"]=str(started)
    os.environ["SWCUB_OWNER_TOKEN"]=secrets.token_hex(32)
    os.environ["SWCUB_RESOURCE_LEDGER"]=str(root/"resource-ledger.jsonl")
    os.environ["SWCUB_OSWORLD_OVERLAY_HOST_DIR"]=str(root/"overlays")
    os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",resource["runtime_image"])
    os.environ["SWCUB_OSWORLD_VM_READY_TIMEOUT"]="600"
    os.environ.setdefault("OSWORLD_DIR","/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
    gids=["guest-user","guest-agent"] if mode=="independent" else ["guest-shared"]
    needs_user=mode in {"user-only","independent","shared","shared-lock"}
    needs_agent=mode in {"agent-only","independent","shared","shared-lock"}
    event_log=EventLog(root/"events.jsonl",run_id,root,started)
    event_log.emit("orchestrator","run_started",case_id=CASE_ID,case_version=CASE_VERSION,mode=mode,
       agent_kind="codex",model=model if needs_agent else None,user_strategy="fixed-open-loop",
       fixed_mechanism_probe=False,natural_parallelism=mode in {"independent","shared","shared-lock"})
    lock_path=Path(f"/tmp/{run_id}.gui-action.lock") if mode=="shared-lock" else None
    if lock_path:os.environ["OSCOMBO_ACTION_LOCK_FILE"]=str(lock_path)
    else:os.environ.pop("OSCOMBO_ACTION_LOCK_FILE",None)
    backends={};envs={};guests={};setup={};boot={};monitors=[]
    actor_runs={"results":{},"errors":{}};oracle={};model_called=False;status="finished";equivalence=None
    started_run=time.monotonic()
    try:
        gateway=resource["docker_bridge_gateway"]
        for gid in gids:backends[gid]=Backend(root,gid,run_id,gateway)
        def boot_one(gid):
            gd=root/"guests"/gid;gd.mkdir(parents=True,exist_ok=True)
            env=combo.boot(str(image_path),str(gd/"cache"));envs[gid]=env;guest=Guest(env);guests[gid]=guest
            t=time.monotonic();guest.wait_desktop(patience=600);shot=guest.screenshot(patience=60)
            if not shot or len(shot)<1000:raise InfraError("blank/invalid desktop screenshot")
            (gd/"desktop-ready.png").write_bytes(shot)
            provider=getattr(env,"provider",None);container=getattr(provider,"container",None);cid=getattr(container,"id",None)
            qemu="";kvm=False
            if cid:
                p=subprocess.run(["docker","exec",cid,"ps","-eo","args"],capture_output=True,text=True,timeout=15)
                qemu=next((x.strip() for x in p.stdout.splitlines() if "qemu-system" in x),"")
                kvm=subprocess.run(["docker","exec",cid,"test","-r","/dev/kvm"],capture_output=True,timeout=15).returncode==0
            boot[gid]={"ready_wait_s":round(time.monotonic()-t,3),"screenshot_bytes":len(shot),
                "live_qemu_acceleration":"KVM" if "accel=kvm" in qemu and kvm else ("TCG/unknown" if qemu else "not-observed"),
                "container_kvm_readable":kvm,"qemu_command":qemu[:1000]}
        if mode=="independent":
            ts=[threading.Thread(target=boot_one,args=(gid,),name="boot-"+gid) for gid in gids]
            [t.start() for t in ts];[t.join() for t in ts]
            if len(guests)!=2:raise InfraError("Independent requires two ready Guests")
        else:boot_one(gids[0])
        for gid in gids:
            setup[gid]=_setup_po_guest(guests[gid],backends[gid],root/"guests"/gid,run_id)
            backends[gid].healthcheck()
        for gid in gids:
            m=FocusMonitor(guests[gid],gid,event_log,root/"focus"/gid,interval=.5);monitors.append(m);m.start()
        user_gid="guest-user" if mode=="independent" else gids[0]
        agent_gid="guest-agent" if mode=="independent" else gids[0]
        funcs=[]
        if needs_user:
            actor=ScriptedGUIActor(actor_id="user",guest=guests[user_gid],actions=_user_actions(setup[user_gid]["home"]),
                event_log=event_log,out=root,guest_id=user_gid,lock_path=lock_path,strategy="fixed")
            funcs.append(("user",actor.run))
        if needs_agent:
            harness,ctx=_prepare_agent(guests[agent_gid],backends[agent_gid],root,lock_path,budget,timeout,
                model,endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.haogpt.net/v1")
            def run_agent():
                nonlocal model_called
                model_called=True;t=time.monotonic()
                event_log.emit("agent","actor_started",guest_id=agent_gid,actor_kind="codex_gui")
                ctx.t0=time.time();ar=harness.run(ctx)
                payload={"status":ar.status,"error":ar.error,"steps":ar.steps,"extra":ar.extra}
                event_log.emit("agent","actor_finished",guest_id=agent_gid,elapsed_s=round(time.monotonic()-t,3),
                    status=ar.status,steps=ar.steps,token_usage=ar.extra.get("token_usage"))
                return payload
            funcs.append(("agent",run_agent))
        actor_runs=_run_parallel(funcs)
        time.sleep(1)
        download_probe=None
        if needs_user:
            try:
                download_probe={"ok":True,"output":_guest_exec(guests[user_gid],
                    f"find {setup[user_gid]['home']!r} -maxdepth 5 -type f -name {USER_FILE!r} -print -exec sha256sum {{}} \\; 2>/dev/null || true",
                    timeout=45)}
            except Exception as probe_exc:
                # Diagnostic only: a slow Guest /execute must not invalidate completed tasks.
                download_probe={"ok":False,"error":f"{type(probe_exc).__name__}: {probe_exc}"}
            event_log.emit("evaluator","user_download_artifact_probe",guest_id=user_gid,
                probe=download_probe,probe_timing="after_actor_completion")
        for m in monitors:m.stop()
        for actor,gid in (("user",user_gid),("agent",agent_gid)):
            if (actor=="user" and needs_user) or (actor=="agent" and needs_agent):
                oracle[actor]=backends[gid].evaluate()[actor]
        success={"user":oracle.get("user",{}).get("success") if needs_user else None,
                 "agent":oracle.get("agent",{}).get("success") if needs_agent else None}
        joint=bool(success["user"] and success["agent"]) if needs_user and needs_agent else None
        if mode=="independent":
            state_hashes={g:hashlib.sha256(json.dumps(backends[g].manifest.get("initial_state",{}),
                sort_keys=True,separators=(",",":")).encode()).hexdigest() for g in gids}
            equivalence={"fixture_content_sha256_equal":len({_fixture_hash() for _ in gids})==1,
              "user_file_sha256_equal":len({hashlib.sha256(USER_FILE_CONTENT).hexdigest() for _ in gids})==1,
              "initial_state_sha256_equal":len(set(state_hashes.values()))==1,
              "initial_state_empty_on_both":all(backends[g].manifest.get("initial_state")=={"agent_submissions":0,"user_submissions":0} for g in gids)}
            if not all(equivalence.values()):status="invalid-fixture-inequivalence"
        rows=_events(root/"events.jsonl")
        costs=_costs(rows,actor_runs["results"].get("user"),actor_runs["results"].get("agent"),monitors)
        agent_steps=actor_runs["results"].get("agent",{}).get("steps",0)
        agent_no_tool=bool(needs_agent and agent_steps==0)
        if agent_no_tool:
            status="infrastructure-invalid"
        elif any(x is False for x in success.values() if x is not None):status="valid-task-failure"
        else:status="valid-task-success"
        result={"case_id":CASE_ID,"case_version":CASE_VERSION,"task_card":asdict(TaskCard()),"run_id":run_id,
          "mode":mode,"agent_kind":"codex" if needs_agent else None,"model":model if needs_agent else None,
          "status":status,"experiment_valid":status not in {"invalid-fixture-inequivalence","infrastructure-invalid","orchestrator-error"},
          "model_called":model_called,"agent_no_gui_tool_calls":agent_no_tool if needs_agent else None,
          "actor_results":actor_runs["results"],"actor_errors":actor_runs["errors"],
          "actor_success":success,"joint_success":joint,"oracle":oracle,"costs":costs,
          "fixture_equivalence":equivalence,"fixture_state_sha256":_fixture_hash(),
          "fixture_hashes":{gid:{"fixture_id":backends[gid].manifest["fixture_id"],
            "initial_state":backends[gid].manifest["initial_state"],"user_file_sha256":hashlib.sha256(USER_FILE_CONTENT).hexdigest()}
            for gid in gids},"guest_setup":setup,"guest_boot":boot,"resource_preflight":resource,"user_download_artifact_probe":download_probe,
          "guest_count":len(guests),"base_image":str(image_path),"resource_ledger":str(root/"resource-ledger.jsonl"),
          "overlay_root":str(root/"overlays"),"app_topology":"run-scoped Procurement Review and Finance Archive services; two visible Chrome windows in one Guest/profile; native file chooser for User attachment",
          "user_task":USER_TASK,"agent_task":AGENT_TASK,"agent_budget":{"gui_mcp_calls":budget,"actor_wall_cap_s":timeout},
          "natural_parallelism":mode in {"independent","shared","shared-lock"},"fixed_mechanism_probe":False,
          "elapsed_s":round(time.monotonic()-started_run,3),
          "limitations":["one run per condition; no repeated-trial claim","User uses a fixed open-loop script; no evaluator-aware or Agent-answer-aware recovery",
             "window titles are a focus proxy; app submissions and file hash are the task-result evidence",
             "the Agent and User tasks use separate fixtures; interactions are primarily shared desktop/focus rather than a business-state conflict"]}
        (root/"run.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+"\n")
        event_log.emit("orchestrator","run_finished",status=status,elapsed_s=result["elapsed_s"],actor_success=success,joint_success=joint)
        return result
    except Exception as exc:
        status="infrastructure-invalid" if isinstance(exc,InfraError) else "orchestrator-error"
        failure={"case_id":CASE_ID,"case_version":CASE_VERSION,"run_id":run_id,"mode":mode,"status":status,
          "experiment_valid":False,"model_called":model_called,"elapsed_s":round(time.monotonic()-started_run,3),
          "error":f"{type(exc).__name__}: {exc}","traceback":traceback.format_exc()[-4500:],
          "resource_preflight":resource,"resource_ledger":str(root/"resource-ledger.jsonl"),
          "overlay_root":str(root/"overlays"),"historical_artifacts_preserved":True}
        if not (root/"run.json").exists():(root/"run.json").write_text(json.dumps(failure,indent=2)+"\n")
        event_log.emit("orchestrator","run_failed",status=status,error=failure["error"][:1000])
        raise
    finally:
        for m in monitors:
            try:m.stop()
            except Exception:pass
        for b in backends.values():
            try:b.close()
            except Exception:pass
        for env in envs.values():
            try:env.close()
            except Exception:pass
        try:
            clean=_cleanup_owned_guest(root,run_id)
            if clean:(root/"cleanup.json").write_text(json.dumps(clean,indent=2)+"\n")
        except Exception as exc:(root/"cleanup-warning.json").write_text(json.dumps({"status":"safe-cleanup-error","error":str(exc)[:500]},indent=2)+"\n")
        for name in ("OSCOMBO_ACTION_LOCK_FILE","OSCOMBO_ACTION_LOCK_EVENTS_FILE","OSCOMBO_RUN_ID","OSCOMBO_RUN_START_MONO"):
            os.environ.pop(name,None)

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--mode",choices=MODES,required=True)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--model",default="gpt-6-sol")
    p.add_argument("--base-url",default=os.environ.get("OPENAI_BASE_URL"));p.add_argument("--budget",type=int,default=AGENT_BUDGET)
    p.add_argument("--timeout",type=float,default=AGENT_TIMEOUT);p.add_argument("--image")
    a=p.parse_args()
    print(json.dumps(run_condition(mode=a.mode,out=a.out,model=a.model,endpoint=a.base_url,budget=a.budget,
      timeout=a.timeout,image=a.image),indent=2,ensure_ascii=False,default=str))
if __name__=="__main__":main()

