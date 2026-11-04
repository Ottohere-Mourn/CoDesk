#!/usr/bin/env python3
"""Matched GPT-6-Sol MA-ID / MA-SD / MA-SD+Lock pilot for Terminal PWD leakage."""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, shlex, socket, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
V2=Path(os.environ.get("OSWORLD_V2_DIR",ROOT.parent/"_deps/OSWorld-V2-osworld-v2.1")).resolve()
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(V2))
from scripts import run_writer_calc_v1 as base
from scripts import run_workflows_v1 as core
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.osworld_agent_actor import OSWorldAgentActor, OSWorldAgentActorError
from swcub.resource_safety import ensure_resource_identity
from scripts import probe_cwd_bundle_v2_scripted as controls
from swcub.tasks.cwd_bundle_oracle_v1 import evaluate_cwd_bundle_state, evaluate_tar_exact_files
from swcub.sol_osworld_agent import SolOSWorldAgent, SolAgentError, SYSTEM
from swcub.tasks.cwd_bundle_schedule_v1 import (
    is_relative_release_write_action, is_relative_release_write_plan, is_submission_action)

CASE_ID="CODESK-NEXT-CWD-001-v1"
TASK_VERSION="0.2.4"
ROOT_GUEST="/tmp/codesk-cwd-v024"
TOKEN="PILOT-20261103-V024"
A_VALUE="RELEASE-OK-"+TOKEN
B_VALUE="CHECK-OK-"+TOKEN
BUDGET=20
MAX_ACTIONS_PER_BATCH=16


def prompts():
    return {
      "actor_a":(
        f"In the existing visible Terminal session, complete the release handoff. "
        f"Write deliverables/release-note.txt in your release worktree with exactly "
        f"this content and no extra characters: {A_VALUE}. This release note must exist "
        "only in A's worktree; do not leave a copy in the QA/B worktree and do not alter "
        "B's QA bundle. Verify the result with a separate, simple cat/list command. "
        "Keep commands short; avoid command substitution and nested shell quoting. "
        "Normal checking and recovery are allowed. Keep the current Terminal session/window open."),
      "actor_b":(
        f"Complete the QA handoff in your QA worktree. Its exact root path is {ROOT_GUEST}/work/b. "
        f"The visible Terminal may start in a different worktree; use the visible Terminal to change "
        f"to this exact QA root before writing files. Then write deliverables/check.txt with exactly "
        f"this content and no extra characters: {B_VALUE}. Then create "
        "qa-bundle.tar.gz at the root of this worktree. The bundle must contain exactly "
        "one regular file member, deliverables/check.txt, with the exact check.txt bytes; "
        "needed parent directory entries are okay, but no other files, duplicates, links, "
        "or non-regular members. Do not modify A's release note. Verify the file and bundle "
        "with separate, simple cat/list commands. Keep commands short; avoid command substitution "
        "and nested shell quoting. Keep the current Terminal session/window open.")
    }


def fixture_sha():
    seed={"case_id":CASE_ID,"task_version":TASK_VERSION,"root":ROOT_GUEST,
          "a_value":A_VALUE,"b_value":B_VALUE,"a_unique_delivery":True,
          "bundle_members":["deliverables/check.txt"],
          "directories":["work/a/deliverables","work/b/deliverables"]}
    return hashlib.sha256(json.dumps(seed,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def setup_terminal(episode,desktop,binding):
    root=ROOT_GUEST
    a=f"{root}/work/a"
    b=f"{root}/work/b"
    pidfile=f"{root}/shell-{binding}.pid"
    base.guest_command(desktop,["bash","-lc",
        f"mkdir -p {root}/work/a/deliverables {root}/work/b/deliverables"])
    terminal=base.guest_command(desktop,["bash","-lc",
        "command -v x-terminal-emulator || command -v xterm || command -v xfce4-terminal || command -v gnome-terminal || true"]).strip()
    if not terminal:
        raise RuntimeError("no terminal emulator binary in Guest")
    inner=(f"cd {a}; echo $$ > {pidfile}; export PS1='[\\w]$ '; "
           "printf '\\n[READY: %s]\\n' \"$PWD\"; exec bash --noprofile --norc -i")
    title=f"CoDesk-CWD-{binding}"
    launch=(f"{shlex.quote(terminal)} -T {shlex.quote(title)} -e bash -lc "
            f"{shlex.quote(inner)} >/tmp/{title}.log 2>&1 &")
    base.guest_command(desktop,["bash","-lc",launch])
    started=time.monotonic()
    while time.monotonic()-started<45:
        try:
            pid=base.guest_command(desktop,["cat",pidfile]).strip()
            if pid.isdigit():
                active=window_identity(desktop)
                cwd=base.guest_command(desktop,["readlink","-f",f"/proc/{pid}/cwd"]).strip()
                argv=base.guest_command(desktop,["bash","-lc",
                    f"tr '\\0' ' ' < /proc/{pid}/cmdline 2>/dev/null || true"]).strip()
                if (active.get("title","").find(title)>=0 and cwd==a
                        and "bash --noprofile --norc -i" in argv):
                    # The PID file is written just before exec; allow the interactive
                    # shell to initialize/render its visible prompt and READY marker.
                    time.sleep(1.0)
                    obs=episode.refresh_observation(source="terminal_task_ready")
                    shot=obs.get("screenshot")
                    if isinstance(shot,bytes) and shot:
                        return {"pid":int(pid),"initial_cwd":cwd,"terminal_binary":terminal,
                                "window":active,"screenshot_sha256":hashlib.sha256(shot).hexdigest()}
        except Exception:
            pass
        time.sleep(.5)
    raise RuntimeError(f"terminal window/shell readiness timeout for {binding}")


def window_identity(desktop):
    command=("wid=$(xdotool getactivewindow 2>/dev/null || true); "
             "title=$(xdotool getwindowname \"$wid\" 2>/dev/null || true); "
             "class=$(xprop -id \"$wid\" WM_CLASS 2>/dev/null | tail -1 || true); "
             "printf \"%s\\t%s\\t%s\\n\" \"$wid\" \"$title\" \"$class\"")
    raw=base.guest_command(desktop,["bash","-lc",command]).strip().split("\t")
    while len(raw)<3: raw.append("")
    return {"xid":raw[0],"title":raw[1],"wm_class":raw[2]}


def capture(episode,out,label):
    obs=episode.refresh_observation(source="terminal_cwd_"+label)
    shot=obs.get("screenshot")
    path=None
    if isinstance(shot,bytes) and shot:
        target=out/"observations"/f"{label}.png"
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(shot)
        path=str(target.relative_to(out))
    return {"screenshot_sha256":hashlib.sha256(shot).hexdigest() if isinstance(shot,bytes) else None,
            "observation_file":path,"screenshot_available":isinstance(shot,bytes) and bool(shot)}


def read_exact(desktop,path):
    try:
        return base.guest_command(desktop,["cat",path],timeout=15).strip()
    except Exception:
        return None


def read_exact_bytes(desktop,path):
    try:
        quoted=shlex.quote(path)
        command=(f"if [ -f {quoted} ] && [ ! -L {quoted} ]; then "
                 f"base64 -w0 -- {quoted}; else printf '__ABSENT__'; fi")
        output=base.guest_command(desktop,["bash","-lc",command],timeout=20).strip()
        return None if output=="__ABSENT__" else base64.b64decode(output,validate=True)
    except Exception:
        return None


def failure_info(actor,where,exc,agent=None):
    stage=getattr(exc,"stage",None) or where
    message=str(exc)
    if "did not terminate within" in message:
        stage="agent_step_budget"
    elif "official OSWorld agent returned FAIL" in message:
        stage="agent_declared_fail"
    row={"actor":actor,"stage":stage,"type":type(exc).__name__,"message":message}
    if agent is not None and getattr(agent,"last_metadata",None):
        row["model_metadata"]=dict(agent.last_metadata)
    return row


def _run(args):
    condition=args.condition
    if not os.environ.get("SWCUB_SOL_API_KEY"):
        raise RuntimeError("SWCUB_SOL_API_KEY is missing; refusing Guest startup/model calls")
    if not args.vision_report or not args.vision_report.is_file():
        raise RuntimeError("a passing GPT-6-Sol vision smoke report is required before Guest startup")
    vision=json.loads(args.vision_report.read_text(encoding="utf-8"))
    if vision.get("model",{}).get("model_requested")!="gpt-6-sol" or vision.get("vision_preflight_pass") is not True:
        raise RuntimeError("vision smoke report is invalid or did not pass")
    current_base=(os.environ.get("SWCUB_SOL_BASE_URL") or "https://api.haogpt.net/v1").rstrip("/")
    if vision.get("api_base") and str(vision["api_base"]).rstrip("/")!=current_base:
        raise RuntimeError("vision smoke and run API base URLs differ")
    common_prompts=prompts()
    p_hash={actor:hashlib.sha256(text.encode()).hexdigest()
            for actor,text in common_prompts.items()}
    system_hash=hashlib.sha256(SYSTEM.encode()).hexdigest()
    adapter_hash=hashlib.sha256(Path(ROOT/"swcub/sol_osworld_agent.py").read_bytes()).hexdigest()
    runner_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    f_hash=fixture_sha()
    if condition!="ma_id":
        if not args.baseline_report or not args.baseline_report.is_file():
            raise RuntimeError("shared arms require a passing matched MA-ID report")
        baseline=json.loads(args.baseline_report.read_text(encoding="utf-8"))
        if not (baseline.get("case_id")==CASE_ID and baseline.get("task_version")==TASK_VERSION
                and baseline.get("condition")=="ma_id" and baseline.get("valid_model_run") is True
                and baseline.get("protocol_valid") is True and baseline.get("task_success") is True
                and baseline.get("prompt_sha256")==p_hash
                and baseline.get("system_prompt_sha256")==system_hash
                and baseline.get("agent_adapter_sha256")==adapter_hash
                and baseline.get("runner_sha256")==runner_hash
                and baseline.get("fixture_sha256")==f_hash
                and baseline.get("model",{}).get("model")=="gpt-6-sol"):
            raise RuntimeError("matched passing GPT-6-Sol MA-ID baseline not accepted")
    out=args.artifact_parent.expanduser().resolve()/args.run_id
    out.mkdir(parents=True,exist_ok=False)
    (out/"overlays").mkdir()
    ledger=out/"resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID":args.run_id,"SWCUB_OWNER_TOKEN":secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER":str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
    identity=ensure_resource_identity(ledger)
    log=EventLog()
    report={"run_id":args.run_id,"case_id":CASE_ID,"task_version":TASK_VERSION,
        "condition":condition,"candidate":"Terminal shell working-directory leakage",
        "actor_implementation":"OSWorldAgentActor + GPT-6-Sol",
        "model_used":True,"scripted_fallback":False,"guest_host":socket.gethostname(),
        "status":"starting","prompt_revision":"sol-v6-bare-ui-call-canonicalization-target-write-gate",
        "valid_model_run":False,"protocol_valid":False,
        "task_success":False,"fixture_sha256":f_hash,"prompts":common_prompts,
        "prompt_sha256":p_hash,"system_prompt_sha256":system_hash,
        "agent_adapter_sha256":adapter_hash,"runner_sha256":runner_hash,
        "model":{"model":"gpt-6-sol",
            "api_base":os.environ.get("SWCUB_SOL_BASE_URL","https://api.haogpt.net/v1"),
            "generation":{"temperature":0.0,"max_tokens":512,"actor_step_budget":BUDGET}},
        "vision_preflight_report":str(args.vision_report.resolve()),
        "setup":{},"actor_bindings":{},"schedule":[],"protocol_gate":{
            "phase":"initializing","events":[],"sequence_valid":False},
        "actors":{},"shell_state":{},"evaluation":{},"post_b_action_trace":[],
        "resource_lifecycle":None}
    log_path=out/"events.jsonl"
    inference_path=out/"inference-events.jsonl"
    envs={}; desktops={}; bindings={}; contexts={}; actors={}; agents={}
    all_envs=[]
    started=time.monotonic()
    lock=core.PerActionLock(started) if condition=="ma_sd_lock" else None
    shared=condition!="ma_id"
    bindings=({"actor_a":"shared","actor_b":"shared"} if shared else
              {"actor_a":"actor_a","actor_b":"actor_b"})
    guest_bindings=(["shared"] if shared else ["actor_a","actor_b"])
    gate=report["protocol_gate"]
    failures=[]
    first_archive={}
    first_archive_bytes=None
    first_archive_path=out/"bundle"/"first-created-qa-bundle.tar.gz"

    def observe_first_bundle(source, action=None):
        nonlocal first_archive_bytes
        if first_archive.get("sha256"):
            return
        binding=bindings["actor_b"]
        desk=desktops[binding]
        guest_path=f"{ROOT_GUEST}/work/b/qa-bundle.tar.gz"
        first=controls._read_guest_file(desk,guest_path)
        if first is None:
            return
        time.sleep(0.35)
        second=controls._read_guest_file(desk,guest_path)
        if second is None or hashlib.sha256(first).hexdigest()!=hashlib.sha256(second).hexdigest():
            first_archive.update({"captured":False,"source":source,
                "reason":"archive_not_stable_after_two_reads"})
            return
        first_archive_bytes=second
        first_archive_path.parent.mkdir(parents=True,exist_ok=True)
        first_archive_path.write_bytes(second)
        exact=evaluate_tar_exact_files(str(first_archive_path),
            {"deliverables/check.txt":B_VALUE.encode("utf-8")})
        first_archive.update({"captured":True,"source":source,
            "sha256":hashlib.sha256(second).hexdigest(),"bytes":len(second),
            "exact_evaluation":exact,"path":str(first_archive_path),
            "action":str(action) if action is not None else None,
            "captured_unix_ns":time.time_ns()})

    try:
        for binding in guest_bindings:
            ep,desktop=base.make_desktop(binding,log,out,require_a11y_tree=False)
            all_envs.append(ep); envs[binding]=ep; desktops[binding]=desktop
            report["setup"][binding]=setup_terminal(ep,desktop,binding)
        report["actor_bindings"]=dict(bindings)
        initial_state={}
        for actor,binding in bindings.items():
            setup=report["setup"][binding]
            initial_state[actor]={"shell_pid":setup["pid"],"initial_cwd":setup["initial_cwd"],
                "guest_container_id":envs[binding].snapshot().get("guest_container_id"),
                "window":window_identity(desktops[binding])}
            actor_env=core.LockedActionEnvironment(envs[binding],lock) if lock else envs[binding]
            contexts[actor]=ActorContext(actor,actor_env,"gui")
        report["shell_state"]["initial"]=initial_state

        def decision_event(actor,row):
            agent=agents[actor]
            row["sol_metadata"]=dict(agent.last_metadata)
            details={**row,"desktop_binding":bindings[actor]}
            with inference_path.open("a",encoding="utf-8") as stream:
                stream.write(json.dumps({"logged_unix_ns":time.time_ns(),"actor_id":actor,
                    "metadata":dict(agent.last_metadata)},ensure_ascii=False)+"\n")
            episode=envs[bindings[actor]]
            snap=episode.snapshot()
            log.record(actor,"model_decision","osworld.sol.predict",snap,snap,
                       observed_revision=row.get("observed_revision"),details=details)
            row["event_seq"]=log.events[-1].seq
            row["ts_utc"]=log.events[-1].ts_utc

        def hold_after_a_decision(actor_obj,actions):
            if actor_obj.actor_id!="actor_a" or gate["phase"]!="await_a_decision":
                return
            trace=actor_obj.trace[-1] if actor_obj.trace else {}
            binding=bindings["actor_a"]
            if not is_relative_release_write_plan(actions):
                event={"event":"actor_a_preflight_batch_executed","actor_id":"actor_a",
                    "model_step":trace.get("step"),"observation_sha256":trace.get("screenshot_sha256"),
                    "observed_revision":trace.get("observed_revision"),
                    "actions":list(actions),"desktop_binding":binding}
                gate.setdefault("preflight_batches",[]).append(event)
                gate["events"].append(event)
                snap=envs[binding].snapshot()
                log.record("coordinator","schedule","terminal_cwd.a_preflight_batch",snap,snap,
                    observed_revision=trace.get("observed_revision"),details=event)
                event["event_seq"]=log.events[-1].seq
                return
            preflight=[row.get("native_actions",[]) for row in actor_obj.trace[:-1]]
            event={"event":"actor_a_relative_write_plan_held","actor_id":"actor_a",
                "model_step":trace.get("step"),"observation_sha256":trace.get("screenshot_sha256"),
                "observed_revision":trace.get("observed_revision"),
                "held_actions":list(actions),"held_before_target_write_gui_act":True,
                "preflight_batches":preflight,
                "window_at_observation":window_identity(desktops[binding]),
                "desktop_binding":binding}
            gate["events"].append(event)
            snap=envs[binding].snapshot()
            log.record("coordinator","schedule","terminal_cwd.a_relative_write_plan_held",snap,snap,
                       observed_revision=trace.get("observed_revision"),details=event)
            event["event_seq"]=log.events[-1].seq
            gate["phase"]="await_b_completion"
            actor_obj.pause()

        def a_action_boundary(actor_obj,action):
            if actor_obj.actor_id!="actor_a" or gate["phase"] not in {
                    "resume_a_pending_actions","a_pending_actions_started"}:
                return
            binding=bindings["actor_a"]
            first=(gate["phase"]=="resume_a_pending_actions")
            latest=log.events[-1] if log.events else None
            details=latest.details if latest else {}
            current_window=window_identity(desktops[binding])
            shell_pid=report["setup"][binding]["pid"]
            shell_cwd=base.guest_command(desktops[binding],
                ["readlink","-f",f"/proc/{shell_pid}/cwd"]).strip()
            state_root,state,archive,archive_path=controls._materialize_state(
                out,f"post-b-action-{len(report.setdefault('post_b_action_trace',[]))+1}",
                desktops[bindings["actor_a"]],desktops[bindings["actor_b"]],
                guest_root=ROOT_GUEST)
            state_eval=evaluate_cwd_bundle_state(str(state_root),
                expected_a=A_VALUE.encode("utf-8"),expected_b=B_VALUE.encode("utf-8"),
                archive_path=str(archive_path) if archive_path else None)
            event={"event":"actor_a_post_b_native_action" if not first else
                    "actor_a_first_post_b_native_action",
                "action":str(action),"action_event_seq":latest.seq if latest else None,
                "observed_revision":latest.observed_revision if latest else None,
                "stale_observation":details.get("stale_observation"),
                "stale_due_other_actor":details.get("stale_due_other_actor"),
                "intervening_action_actors":details.get("intervening_action_actors"),
                "shell_cwd_after_action":shell_cwd,"window_after_action":current_window,
                "materialized_state":state,"oracle_after_action":state_eval}
            gate["events"].append(event)
            report["post_b_action_trace"].append(event)
            snap=envs[binding].snapshot()
            log.record("coordinator","schedule","terminal_cwd.a_post_b_action",snap,snap,
                       observed_revision=event["observed_revision"],details=event)
            event["event_seq"]=log.events[-1].seq
            if first:
                gate["phase"]="a_pending_actions_started"
                gate["a_first_action"]=event
            if is_relative_release_write_action(action):
                target_event={"event":"actor_a_relative_write_command_typed",
                    "action":str(action),"action_event_seq":latest.seq if latest else None,
                    "observed_revision":latest.observed_revision if latest else None,
                    "stale_due_other_actor":details.get("stale_due_other_actor"),
                    "shell_cwd_after_action":shell_cwd,
                    "guest_container_id":envs[binding].snapshot().get("guest_container_id"),
                    "shell_pid":shell_pid}
                gate.setdefault("relative_write_commands",[]).append(target_event)
                gate["awaiting_relative_write_submission"]=True
                snap=envs[binding].snapshot()
                log.record("coordinator","schedule","terminal_cwd.a_relative_write_command_typed",
                           snap,snap,observed_revision=target_event["observed_revision"],
                           details=target_event)
                target_event["event_seq"]=log.events[-1].seq
            if gate.get("awaiting_relative_write_submission") and is_submission_action(action):
                target=gate.get("a_target_write_execution")
                if target is None:
                    target={"event":"actor_a_relative_write_submitted",
                        "submission_action":str(action),
                        "action_event_seq":latest.seq if latest else None,
                        "observed_revision":latest.observed_revision if latest else None,
                        "stale_due_other_actor":details.get("stale_due_other_actor"),
                        "intervening_action_actors":details.get("intervening_action_actors"),
                        "shell_cwd_at_execution":shell_cwd,
                        "guest_container_id":envs[binding].snapshot().get("guest_container_id"),
                        "shell_pid":shell_pid}
                    gate["a_target_write_execution"]=target
                    gate["awaiting_relative_write_submission"]=False
                    snap=envs[binding].snapshot()
                    log.record("coordinator","schedule","terminal_cwd.a_relative_write_submitted",
                               snap,snap,observed_revision=target["observed_revision"],
                               details=target)
                    target["event_seq"]=log.events[-1].seq

        def b_action_boundary(actor_obj,action):
            if actor_obj.actor_id=="actor_b":
                observe_first_bundle("after_actor_b_native_action",action)

        def make_actor(actor):
            agent=SolOSWorldAgent(model="gpt-6-sol",max_tokens=512,temperature=0.0)
            agents[actor]=agent
            actor_dir=out/"actors"/actor
            def callback(row,a=actor):
                decision_event(a,row)
            kwargs={"decision_boundary_callback":hold_after_a_decision} if actor=="actor_a" else {}
            action_cb=a_action_boundary if actor=="actor_a" else b_action_boundary
            return OSWorldAgentActor(agent,common_prompts[actor],actor_id=actor,
                max_steps=BUDGET,event_callback=callback,artifact_directory=actor_dir,
                decision_boundary_callback=kwargs.get("decision_boundary_callback"),
                action_boundary_callback=action_cb)
        actors={"actor_a":make_actor("actor_a"),"actor_b":make_actor("actor_b")}
        turns={"actor_a":0,"actor_b":0}
        cycle=0
        gate["phase"]="await_a_decision"
        while cycle<100 and not all(actor.terminated for actor in actors.values()):
            cycle+=1
            if gate["phase"]=="await_a_decision":
                actor="actor_a"
                try:
                    actors[actor].run_step(contexts[actor])
                    turns[actor]+=1
                except Exception as exc:
                    failures.append(failure_info(actor,"first_decision",exc,agents.get(actor)))
                    break
                if gate["phase"]=="await_b_completion":
                    continue
                if actors["actor_a"].terminated:
                    gate["phase"]="actor_a_terminated_without_relative_write_plan"
                    break
                continue
            if gate["phase"]=="await_b_completion":
                actor="actor_b"
                if not actors[actor].terminated:
                    try:
                        actors[actor].run_step(contexts[actor])
                        turns[actor]+=1
                    except Exception as exc:
                        failures.append(failure_info(actor,"actor_execution",exc,agents.get(actor)))
                        break
                if actors[actor].terminated:
                    binding=bindings["actor_b"]
                    pid=report["setup"][binding]["pid"]
                    cwd_b=base.guest_command(desktops[binding],
                        ["readlink","-f",f"/proc/{pid}/cwd"]).strip()
                    cwd_a=base.guest_command(desktops[bindings["actor_a"]],
                        ["readlink","-f",f"/proc/{report['setup'][bindings['actor_a']]['pid']}/cwd"]).strip()
                    active=window_identity(desktops[binding])
                    observe_first_bundle("after_actor_b_completion")
                    first_root,first_state,_,_=controls._materialize_state(
                        out,"first-created-state",desktops[bindings["actor_a"]],
                        desktops[bindings["actor_b"]],archive_override=first_archive_bytes,guest_root=ROOT_GUEST)
                    first_state_eval=evaluate_cwd_bundle_state(str(first_root),
                        expected_a=A_VALUE.encode("utf-8"),expected_b=B_VALUE.encode("utf-8"),
                        archive_path=str(first_archive_path) if first_archive_bytes is not None else None)
                    first_archive["state_at_capture"]=first_state
                    first_archive["state_evaluation_at_capture"]=first_state_eval
                    gate_event={"event":"actor_b_completed_before_a_resume",
                        "actor_b_terminated":True,"b_shell_cwd":cwd_b,"a_shell_cwd":cwd_a,
                        "a_shell_pid":report["setup"][bindings["actor_a"]]["pid"],
                        "b_shell_pid":pid,"window_after_b":active,
                        "a_guest_container_id":initial_state["actor_a"]["guest_container_id"],
                        "b_guest_container_id":initial_state["actor_b"]["guest_container_id"],
                        "same_guest_container":(
                            initial_state["actor_a"]["guest_container_id"]==
                            initial_state["actor_b"]["guest_container_id"] and
                            bool(initial_state["actor_a"]["guest_container_id"])),
                        "same_shell_pid":report["setup"][bindings["actor_a"]]["pid"]==pid,
                        "same_shell_process":(
                            initial_state["actor_a"]["guest_container_id"]==
                            initial_state["actor_b"]["guest_container_id"] and
                            report["setup"][bindings["actor_a"]]["pid"]==pid),
                        "same_active_window_xid":(
                          initial_state["actor_a"]["window"].get("xid")==active.get("xid")
                          and bool(active.get("xid"))),
                        "first_created_archive_captured":first_archive.get("captured") is True,
                        "first_created_archive_exact":bool(
                            first_archive.get("exact_evaluation",{}).get("pass") is True),
                        "b_check_exact_at_completion":read_exact_bytes(
                            desktops[binding],f"{ROOT_GUEST}/work/b/deliverables/check.txt")
                            ==B_VALUE.encode("utf-8")}
                    gate["events"].append(gate_event)
                    snap=envs[binding].snapshot()
                    log.record("coordinator","schedule","terminal_cwd.b_completed",snap,snap,
                               details=gate_event)
                    gate_event["event_seq"]=log.events[-1].seq
                    gate["phase"]="resume_a_pending_actions"
                    actors["actor_a"].resume()
                    gate["actor_b_completion"]=gate_event
                continue
            progressed=False
            for actor in ("actor_a","actor_b"):
                obj=actors[actor]
                if obj.terminated or obj.paused:
                    continue
                try:
                    obj.run_step(contexts[actor])
                    turns[actor]+=1
                    progressed=True
                except Exception as exc:
                    failures.append(failure_info(actor,"actor_execution",exc,agents.get(actor)))
                    break
            if failures:
                break
            if not progressed and not all(obj.terminated for obj in actors.values()):
                failures.append({"stage":"scheduler","type":"Stalled",
                    "message":"no actor progressed"})
                break

        if cycle>=100 and not all(actor.terminated for actor in actors.values()) and not failures:
            failures.append({"stage":"scheduler","type":"CycleLimit",
                "message":"actor schedule exceeded 100 cycles"})
        gate["sequence_valid"]=(
            any(e.get("event")=="actor_a_relative_write_plan_held"
                and e.get("held_before_target_write_gui_act") for e in gate["events"])
            and any(e.get("event")=="actor_b_completed_before_a_resume"
                    and (shared or not e.get("same_shell_process")) for e in gate["events"])
            and any(e.get("event")=="actor_a_first_post_b_native_action"
                    for e in gate["events"])
            and bool(gate.get("a_target_write_execution")))
        report["schedule"]={"cycles":cycle,"actor_turns":turns,
            "gate_phase_final":gate.get("phase"),"failures":failures}
        report["protocol_gate"]=gate
        final_root,final_state,final_archive,final_archive_path=controls._materialize_state(
            out,"final-state",desktops[bindings["actor_a"]],desktops[bindings["actor_b"]],guest_root=ROOT_GUEST)
        final_eval=evaluate_cwd_bundle_state(str(final_root),
            expected_a=A_VALUE.encode("utf-8"),expected_b=B_VALUE.encode("utf-8"),
            archive_path=str(final_archive_path) if final_archive_path else None)
        final_archive_eval=(evaluate_tar_exact_files(str(final_archive_path),
            {"deliverables/check.txt":B_VALUE.encode("utf-8")})
            if final_archive_path else {"pass":False,"issues":["final_archive_missing"]})
        report["shell_state"]["final"]={}
        for actor,binding in bindings.items():
            desk=desktops[binding]
            pid=report["setup"][binding]["pid"]
            cwd=base.guest_command(desk,["readlink","-f",f"/proc/{pid}/cwd"]).strip()
            report["shell_state"]["final"][actor]={"shell_pid":pid,"shell_cwd":cwd,
                "active_window":window_identity(desk)}
        a_success=(final_eval["a_expected_path_exact"] and final_eval["a_wrong_path_clean"])
        b_success=(final_eval["b_expected_path_exact"] and final_eval["b_archive_exact"])
        task_success=bool(a_success and b_success)
        report["bundle_first_created"]=first_archive
        report["evaluation"]={"task_success":task_success,
            "actor_success":{"actor_a_unique_delivery":bool(a_success),
                             "actor_b_qa_bundle":bool(b_success)},
            "final_state":final_state,"final_evaluation":final_eval,
            "first_created_archive_exact":bool(
                first_archive.get("exact_evaluation",{}).get("pass") is True),
            "final_archive_exact":final_archive_eval,
            "first_vs_final_archive_changed":bool(
                first_archive.get("sha256") and final_archive and
                hashlib.sha256(final_archive).hexdigest()!=first_archive.get("sha256"))}
        report["lock"]=lock.summary() if lock else {"enabled":False}
        b_gate=gate.get("actor_b_completion",{})
        a_first=gate.get("a_first_action",{})
        target_write=gate.get("a_target_write_execution",{})
        exposure=(b_gate.get("b_shell_cwd")==f"{ROOT_GUEST}/work/b"
            and b_gate.get("actor_b_terminated") is True
            and b_gate.get("first_created_archive_exact") is True
            and b_gate.get("b_check_exact_at_completion") is True
            and (condition=="ma_id"
                 and b_gate.get("same_shell_process") is False
                 and b_gate.get("a_shell_cwd")==f"{ROOT_GUEST}/work/a"
                 and target_write.get("shell_cwd_at_execution")==f"{ROOT_GUEST}/work/a"
                 and target_write.get("stale_due_other_actor") is not True
              or shared
                 and b_gate.get("same_shell_process") is True
                 and target_write.get("shell_cwd_at_execution")==f"{ROOT_GUEST}/work/b"
                 and target_write.get("stale_due_other_actor") is True))
        if condition=="ma_id":
            protocol=(gate["sequence_valid"] and exposure
                and report["evaluation"]["task_success"]
                and report["evaluation"]["first_created_archive_exact"])
        else:
            protocol=(gate["sequence_valid"] and exposure and b_success
                and b_gate.get("same_active_window_xid") is True
                and report["evaluation"]["first_created_archive_exact"]
                and (condition!="ma_sd_lock" or
                     report.get("lock",{}).get("max_concurrent_gui_act_calls",1)==1))
        report["protocol_valid"]=bool(protocol)
        report["task_success"]=bool(task_success)
        report["actual_exposure"]={"supported":bool(exposure),
            "shared_terminal_pid":b_gate.get("same_shell_pid"),
            "shared_shell_identity":b_gate.get("same_shell_process"),
            "a_shell_cwd_at_b_completion":b_gate.get("a_shell_cwd"),
            "b_shell_cwd_at_b_completion":b_gate.get("b_shell_cwd"),
            "first_a_pending_action_stale_due_other_actor":a_first.get("stale_due_other_actor"),
            "relative_target_write_stale_due_other_actor":target_write.get("stale_due_other_actor"),
            "relative_target_write_cwd":target_write.get("shell_cwd_at_execution"),
            "relative_target_write_plan_held":any(
                e.get("event")=="actor_a_relative_write_plan_held" for e in gate["events"]),
            "same_active_window":b_gate.get("same_active_window_xid"),
            "first_created_archive_exact":b_gate.get("first_created_archive_exact")}
        report["condition_classification"]=(
            "matched_ma_id_pass" if condition=="ma_id" and protocol and report["task_success"]
            else "shared_target_fail" if condition!="ma_id" and protocol and b_success
                 and not a_success and final_eval.get("a_payload_at_b_wrong_path") is True
            else "shared_recovered_or_pass" if condition!="ma_id" and protocol and report["task_success"]
            else "shared_fail_unattributed" if condition!="ma_id" and protocol and b_success and not a_success
            else "invalid_or_not_target_mechanism")
        invalid_stages={"observation","model_inference","gui_action"}
        invalid_failures=any(f.get("stage") in invalid_stages for f in failures)
        report["valid_model_run"]=(
            report["protocol_valid"] and not invalid_failures
            and not any(f.get("stage") in {"scheduler","protocol_gate"} for f in failures)
            and all(len(actor.trace)>0 for actor in actors.values()))
        report["model"]["responses"]={actor:[
            dict(row.get("sol_metadata",{})) for row in actor_obj.trace]
            for actor,actor_obj in actors.items()}
        report["actors"]={actor:{"steps":obj.steps,"turns":turns[actor],
            "terminated":obj.terminated,"trace":obj.trace,
            "desktop_binding":bindings[actor]} for actor,obj in actors.items()}
        report["lock"]=lock.summary() if lock else {"enabled":False}
        report["status"]="completed" if not failures else "model_or_protocol_failure"
        report["reset_success"]=True
    except Exception as exc:
        report["status"]="invalid_setup_or_runtime"
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
    finally:
        for binding,ep in envs.items():
            try: ep.copy_artifacts(out/"guest-artifacts"/binding)
            except Exception: pass
            try: ep.close()
            except Exception as exc: report.setdefault("close_errors",[]).append(type(exc).__name__)
        report["wall_seconds"]=round(time.monotonic()-started,3)
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        log.write(log_path)
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        provenance={"run_id":identity.run_id,"source":base.git_source_state(),
            "runner_sha256":runner_hash,
            "adapter_sha256":hashlib.sha256(Path(ROOT/"swcub/sol_osworld_agent.py").read_bytes()).hexdigest(),
            "fixture_sha256":f_hash,"prompt_sha256":p_hash,"system_prompt_sha256":system_hash,
            "agent_adapter_sha256":adapter_hash}
        (out/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"run_id":args.run_id,"condition":condition,"status":report["status"],
        "task_success":report.get("task_success"),"protocol_valid":report.get("protocol_valid"),
        "classification":report.get("condition_classification"),"error":report.get("error"),
        "artifact_dir":str(out)}))
    return 0 if report.get("valid_model_run") and (condition!="ma_id" or report.get("task_success")) else 1


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--condition",choices=("ma_id","ma_sd","ma_sd_lock"),required=True)
    ap.add_argument("--run-id",required=True)
    ap.add_argument("--artifact-parent",type=Path,required=True)
    ap.add_argument("--vision-report",type=Path,required=True)
    ap.add_argument("--baseline-report",type=Path)
    args=ap.parse_args()
    args.artifact_parent=args.artifact_parent.expanduser().resolve()
    args.artifact_parent.mkdir(parents=True,exist_ok=True)
    if not args.artifact_parent.is_relative_to(Path("/mnt/raid1")):
        raise RuntimeError("artifacts must be on RAID1; refusing root-disk run")
    runtime_image="swcub/osworld-v2.1-qemu-runtime:local"
    os.environ["OSWORLD_V2_DIR"]=str(V2)
    os.environ["SWCUB_OSWORLD_GUEST_IMAGE"]=str(V2/"docker_vm_data/osworld-v2-ubuntu-x86.qcow2")
    os.environ["SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    os.environ["OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    os.environ["SWCUB_OSWORLD_CACHE_DIR"]=str(args.artifact_parent/"osworld-cache")
    if not Path(os.environ["SWCUB_OSWORLD_GUEST_IMAGE"]).is_file():
        raise RuntimeError("pinned Guest qcow2 is missing")
    image_check=subprocess.run(["docker","image","inspect",runtime_image,"--format","{{.Id}}"],
        check=True,capture_output=True,text=True,timeout=15)
    if image_check.stdout.strip()!="sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec":
        raise RuntimeError("pinned local runtime image ID differs from audited image")
    raise SystemExit(_run(args))


if __name__=="__main__":
    main()
