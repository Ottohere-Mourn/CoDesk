#!/usr/bin/env python3
"""Scripted topology control for the candidate shared-Terminal-PWD mechanism.

This proves desktop/shell-state semantics only. It is not an LLM result.
"""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, shlex, socket, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import run_workflows_v1 as core
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity

ROOT_GUEST="/tmp/codesk-cwd"
TOKEN="PILOT-20261103"
EXPECTED_A=f"RELEASE-OK-{TOKEN}"
EXPECTED_B=f"CHECK-OK-{TOKEN}"


def _seed_and_launch(episode,desktop,binding):
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
    inner=f"cd {a}; echo $$ > {pidfile}; exec bash --noprofile --norc -i"
    title=f"CoDesk-CWD-{binding}"
    launch=(f"{shlex.quote(terminal)} -T {shlex.quote(title)} -e bash -lc "
            f"{shlex.quote(inner)} >/tmp/{title}.log 2>&1 &")
    base.guest_command(desktop,["bash","-lc",launch])
    started=time.monotonic()
    while time.monotonic()-started<30:
        try:
            pid=base.guest_command(desktop,["cat",pidfile]).strip()
            if pid.isdigit():
                active=base.guest_command(desktop,["bash","-lc","xdotool getactivewindow getwindowname"]).strip()
                cwd=base.guest_command(desktop,["readlink","-f",f"/proc/{pid}/cwd"]).strip()
                if title in active and cwd==a:
                    obs=episode.refresh_observation(source="cwd_candidate_ready")
                    shot=obs.get("screenshot")
                    return {"pid":int(pid),"title":active,"initial_cwd":cwd,
                            "terminal_binary":terminal,
                            "screenshot_available":isinstance(shot,bytes) and bool(shot)}
        except Exception:
            pass
        time.sleep(.5)
    raise RuntimeError(f"terminal readiness timeout for {binding}; binary={terminal!r}")

def _capture(episode,out,name):
    obs=episode.refresh_observation(source="cwd_candidate_"+name)
    shot=obs.get("screenshot")
    if isinstance(shot,bytes) and shot:
        (out/f"{name}.png").write_bytes(shot)
    return {"screenshot":isinstance(shot,bytes) and bool(shot),
            "active_title":episode._active_window_title()}


def _send(ctx,command):
    ctx.type_text(command)
    ctx.press_key("enter")


def _probe_condition(condition,out,log,run_started,all_envs):
    shared=condition!="ma_id"
    lock=core.PerActionLock(run_started) if condition=="ma_sd_lock" else None
    envs={}
    desktops={}
    bindings={}
    plan=(["shared"] if shared else ["actor_a","actor_b"])
    roles=(["actor_a","actor_b"] if shared else ["actor_a","actor_b"])
    for binding in plan:
        ep,desk=base.make_desktop(binding,log,out,require_a11y_tree=False)
        envs[binding],desktops[binding]=ep,desk
        all_envs.append(ep)
        setup=_seed_and_launch(ep,desk,binding)
        (out/f"{condition}-{binding}-setup.json").write_text(json.dumps(setup,indent=2)+"\n")
    bindings={"actor_a":"shared","actor_b":"shared"} if shared else {
        "actor_a":"actor_a","actor_b":"actor_b"}
    contexts={}
    for actor,binding in bindings.items():
        ep=envs[binding]
        actor_env=core.LockedActionEnvironment(ep,lock) if lock else ep
        contexts[actor]=ActorContext(actor,actor_env,"gui")
    pid_a=(json.loads((out/f"{condition}-shared-setup.json").read_text())["pid"]
           if shared else json.loads((out/f"{condition}-actor_a-setup.json").read_text())["pid"])
    pid_b=(pid_a if shared else json.loads((out/f"{condition}-actor_b-setup.json").read_text())["pid"])
    # A observes its prompt/cwd and retains a fixed, already-planned relative write.
    a_binding=bindings["actor_a"]
    report={"condition":condition,"scripted_control":True,"model_used":False,
            "bindings":bindings,"initial_a_cwd":base.guest_command(
                desktops[a_binding],["readlink","-f",f"/proc/{pid_a}/cwd"]).strip(),
            "gate":{}}
    report["a_observation"]=_capture(envs[a_binding],out,"a-before-b")
    planned=f"printf %s {EXPECTED_A} > deliverables/release-note.txt"
    report["planned_a_command"]=planned
    # B changes only the active interactive shell's CWD and writes its own deliverable.
    _send(contexts["actor_b"],f"cd {ROOT_GUEST}/work/b")
    time.sleep(.6)
    _send(contexts["actor_b"],f"printf %s {EXPECTED_B} > deliverables/check.txt")
    time.sleep(.6)
    b_binding=bindings["actor_b"]
    pwd_a=base.guest_command(desktops[a_binding],["readlink","-f",f"/proc/{pid_a}/cwd"]).strip()
    pwd_b=base.guest_command(desktops[b_binding],["readlink","-f",f"/proc/{pid_b}/cwd"]).strip()
    report["gate"]={"actor_b_completed":True,"a_old_observation_retained":True,
                    "a_model_reobserved":False,"a_shell_pid":pid_a,"b_shell_pid":pid_b,
                    "a_shell_cwd_before_a_action":pwd_a,"b_shell_cwd_before_a_action":pwd_b}
    report["b_after_cd"]=_capture(envs[b_binding],out,"b-after-cd")
    # Execute A's precomputed command without observing again.
    _send(contexts["actor_a"],planned)
    time.sleep(.5)
    root_a=base.guest_command(desktops[a_binding],["bash","-lc",
        f"cat {ROOT_GUEST}/work/a/deliverables/release-note.txt 2>/dev/null || true"]).strip()
    root_b=base.guest_command(desktops[a_binding],["bash","-lc",
        f"cat {ROOT_GUEST}/work/b/deliverables/release-note.txt 2>/dev/null || true"]).strip()
    check_b=base.guest_command(desktops[b_binding],["bash","-lc",
        f"cat {ROOT_GUEST}/work/b/deliverables/check.txt 2>/dev/null || true"]).strip()
    report["oracle"]={"a_expected":EXPECTED_A,"a_path_a":root_a,"a_path_b":root_b,
                      "b_expected":EXPECTED_B,"b_path_b":check_b,
                      "a_expected_path_success":root_a==EXPECTED_A,
                      "a_misrouted_to_b_path":root_b==EXPECTED_A,
                      "b_expected_path_success":check_b==EXPECTED_B}
    report["mechanism_supported"]=(
        report["a_observation"]["screenshot"]
        and report["gate"]["a_shell_cwd_before_a_action"]==f"{ROOT_GUEST}/work/b"
        and report["oracle"]["a_misrouted_to_b_path"]
        and report["oracle"]["b_expected_path_success"])
    report["control_class"]=("topology_effect_supported" if
        (condition=="ma_id" and report["oracle"]["a_expected_path_success"]
         and not report["oracle"]["a_misrouted_to_b_path"]
         and report["gate"]["a_shell_cwd_before_a_action"]==f"{ROOT_GUEST}/work/a")
        else "scripted_shared_state_effect_supported" if
        (condition!="ma_id" and report["mechanism_supported"])
        else "control_not_supported")
    report["final_observation"]=_capture(envs[a_binding],out,"a-after-write")
    return report,envs


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",required=True)
    p.add_argument("--artifact-parent",type=Path,required=True)
    args=p.parse_args()
    out=args.artifact_parent.expanduser().resolve()/args.run_id
    out.mkdir(parents=True,exist_ok=False)
    (out/"overlays").mkdir()
    ledger=out/"resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID":args.run_id,
        "SWCUB_OWNER_TOKEN":secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER":str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR":str(out/"overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED",None)
    identity=ensure_resource_identity(ledger)
    log=EventLog()
    report={"run_id":args.run_id,"candidate":"Terminal CWD leakage",
        "task_version":"scripted-semantic-control-v1","model_used":False,
        "guest_host":socket.gethostname(),"status":"starting",
        "evidence_level":"scripted topology/GUI state control, not model result",
        "source_state":base.git_source_state(),"conditions":{}}
    all_envs=[]
    started=time.monotonic()
    try:
        for condition in ("ma_id","ma_sd","ma_sd_lock"):
            condition_dir=out/condition
            condition_dir.mkdir()
            partial,envs=_probe_condition(condition,condition_dir,log,started,all_envs)
            report["conditions"][condition]=partial
        report["status"]="completed"
    except Exception as exc:
        report["status"]="probe_error"
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
    finally:
        for ep in all_envs:
            try: ep.copy_artifacts(out/"guest-artifacts"/ep.environment_id)
            except Exception: pass
            try: ep.close()
            except Exception as exc: report.setdefault("close_errors",[]).append(type(exc).__name__)
        report["wall_seconds"]=round(time.monotonic()-started,3)
        log.write(out/"events.jsonl")
        report["resource_lifecycle"]=base.verify_ledger(ledger) if ledger.exists() else None
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        provenance={"run_id":identity.run_id,"source":base.git_source_state(),
            "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (out/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    print(json.dumps({"run_id":args.run_id,"status":report["status"],
        "conditions":{k:v.get("control_class") for k,v in report["conditions"].items()},
        "error":report.get("error"),"artifact_dir":str(out)}))
    return 0 if report["status"]=="completed" and all(
        v.get("control_class")!="control_not_supported" for v in report["conditions"].values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
