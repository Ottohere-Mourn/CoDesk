#!/usr/bin/env python3
"""Scripted topology and exact-bundle control for CWD-1 v0.2.0.

This is deterministic Guest control only, never an LLM result.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, secrets, shlex, socket, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_writer_calc_v1 as base
from scripts import run_workflows_v1 as core
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.cwd_bundle_oracle_v1 import (
    A_RELATIVE_PATH, A_WRONG_PATH, B_RELATIVE_PATH, B_ARCHIVE_PATH,
    evaluate_cwd_bundle_state, evaluate_tar_exact_files)

ROOT_GUEST="/tmp/codesk-cwd-v020"
TOKEN="PILOT-20261103-V020"
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


def _read_guest_file(desktop,path):
    quoted=shlex.quote(path)
    command=(f"if [ -f {quoted} ] && [ ! -L {quoted} ]; then "
             f"base64 -w0 -- {quoted}; else printf '__ABSENT__'; fi")
    output=base.guest_command(desktop,["bash","-lc",command],timeout=20).strip()
    if output=="__ABSENT__":
        return None
    return base64.b64decode(output,validate=True)


def _materialize_state(out,label,desktop_a,desktop_b,archive_override=None,guest_root=None):
    guest_root=guest_root or ROOT_GUEST
    root=out/"oracle-state"/label
    root.mkdir(parents=True,exist_ok=True)
    files={
        A_RELATIVE_PATH:(desktop_a,f"{guest_root}/{A_RELATIVE_PATH}") ,
        A_WRONG_PATH:(desktop_b,f"{guest_root}/{A_WRONG_PATH}") ,
        B_RELATIVE_PATH:(desktop_b,f"{guest_root}/{B_RELATIVE_PATH}") ,
    }
    state={}
    for rel,(desktop,guest_path) in files.items():
        payload=_read_guest_file(desktop,guest_path)
        state[rel]={"present":payload is not None,
                    "sha256":hashlib.sha256(payload).hexdigest() if payload is not None else None,
                    "bytes":len(payload) if payload is not None else None}
        if payload is not None:
            dest=root/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(payload)
    archive=archive_override if archive_override is not None else _read_guest_file(
        desktop_b,f"{guest_root}/{B_ARCHIVE_PATH}")
    archive_path=None
    if archive is not None:
        archive_path=root/B_ARCHIVE_PATH
        archive_path.parent.mkdir(parents=True,exist_ok=True)
        archive_path.write_bytes(archive)
        state[B_ARCHIVE_PATH]={"present":True,"sha256":hashlib.sha256(archive).hexdigest(),
                               "bytes":len(archive)}
    else:
        state[B_ARCHIVE_PATH]={"present":False,"sha256":None,"bytes":None}
    return root,state,archive,archive_path


def _active_xid(desktop):
    return base.guest_command(desktop,["bash","-lc","xdotool getactivewindow 2>/dev/null || true"]).strip()


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
    # A observes the visible current shell and retains a preplanned GUI write.
    a_binding=bindings["actor_a"]
    a_desktop=desktops[a_binding]
    b_binding=bindings["actor_b"]
    b_desktop=desktops[b_binding]
    report={"condition":condition,"scripted_control":True,"model_used":False,
            "task_version":"0.2.0","bindings":bindings,"gate":{}}
    report["a_observation"]=_capture(envs[a_binding],out,"a-before-b")
    a_xid_before=_active_xid(a_desktop)
    planned=f"printf %s {EXPECTED_A} > deliverables/release-note.txt"
    report["planned_a_command"]=planned
    # B performs legitimate QA work and creates the exact allowlisted bundle.
    _send(contexts["actor_b"],f"cd {ROOT_GUEST}/work/b")
    time.sleep(.4)
    _send(contexts["actor_b"],f"printf %s {EXPECTED_B} > deliverables/check.txt")
    time.sleep(.4)
    _send(contexts["actor_b"],"tar -czf qa-bundle.tar.gz deliverables")
    time.sleep(.8)
    first_archive=_read_guest_file(b_desktop,f"{ROOT_GUEST}/work/b/qa-bundle.tar.gz")
    if first_archive is None:
        raise RuntimeError("B archive was not present after scripted creation")
    first_archive_path=out/f"{condition}-qa-bundle-first-created.tar.gz"
    first_archive_path.write_bytes(first_archive)
    first_archive_eval=evaluate_tar_exact_files(
        str(first_archive_path),{"deliverables/check.txt":EXPECTED_B.encode("utf-8")})
    first_state_root,first_state,_,_= _materialize_state(
        out,condition+"-first-created-state",a_desktop,b_desktop,archive_override=first_archive)
    first_state_eval=evaluate_cwd_bundle_state(
        str(first_state_root),expected_a=EXPECTED_A.encode("utf-8"),
        expected_b=EXPECTED_B.encode("utf-8"),archive_path=str(first_archive_path))
    pwd_a=base.guest_command(a_desktop,["readlink","-f",f"/proc/{pid_a}/cwd"]).strip()
    pwd_b=base.guest_command(b_desktop,["readlink","-f",f"/proc/{pid_b}/cwd"]).strip()
    a_xid_after_b=_active_xid(a_desktop)
    b_xid_after_b=_active_xid(b_desktop)
    a_guest_id=envs[a_binding].snapshot().get("guest_container_id")
    b_guest_id=envs[b_binding].snapshot().get("guest_container_id")
    same_guest=bool(a_guest_id and a_guest_id==b_guest_id)
    report["gate"]={"actor_b_completed":True,"a_old_observation_retained":True,
        "a_guest_container_id":a_guest_id,"b_guest_container_id":b_guest_id,
        "a_model_reobserved":False,"a_shell_pid":pid_a,"b_shell_pid":pid_b,
        "a_shell_cwd_before_a_action":pwd_a,"b_shell_cwd_before_a_action":pwd_b,
        "same_guest_container":same_guest,
        "same_shell_process":bool(same_guest and pid_a==pid_b),
        "a_xid_before_b":a_xid_before,"a_xid_after_b":a_xid_after_b,
        "b_xid_after_b":b_xid_after_b,
        "same_active_window_after_b":bool(same_guest and a_xid_after_b and a_xid_after_b==b_xid_after_b)}
    report["b_after_cd_and_bundle"]=_capture(envs[b_binding],out,"b-after-bundle")
    report["bundle_first_created"]={"path":str(first_archive_path),
        "sha256":hashlib.sha256(first_archive).hexdigest(),"bytes":len(first_archive),
        "exact_member_set":first_archive_eval,"state_at_capture":first_state,
        "state_evaluation_at_capture":first_state_eval}
    # Execute A's unchanged relative-path plan without another observation.
    _send(contexts["actor_a"],planned)
    time.sleep(.5)
    final_root,final_state,final_archive,final_archive_path=_materialize_state(
        out,condition+"-final-state",a_desktop,b_desktop)
    final_eval=evaluate_cwd_bundle_state(
        str(final_root),expected_a=EXPECTED_A.encode("utf-8"),
        expected_b=EXPECTED_B.encode("utf-8"))
    final_archive_eval=(evaluate_tar_exact_files(
        str(final_archive_path),{"deliverables/check.txt":EXPECTED_B.encode("utf-8")})
        if final_archive_path else None)
    report["oracle"]={"a_expected":EXPECTED_A,"b_expected":EXPECTED_B,
        "first_created_state":first_state,"first_created_archive_exact":first_archive_eval,
        "final_state":final_state,"final_evaluation":final_eval,
        "final_archive_exact":final_archive_eval,
        "first_vs_final_archive_changed":bool(final_archive is not None and
            hashlib.sha256(final_archive).hexdigest()!=hashlib.sha256(first_archive).hexdigest()),
        "task_success":final_eval["task_success"]}
    report["mechanism_supported"]=(condition!="ma_id" and same_guest
        and pid_a==pid_b and pwd_a==f"{ROOT_GUEST}/work/b"
        and report["gate"]["same_active_window_after_b"]
        and final_state.get(A_WRONG_PATH,{}).get("present") is True
        and final_eval.get("b_expected_path_exact") is True)
    report["control_class"]=("scripted_ma_id_exact_pass" if condition=="ma_id"
        and final_eval["task_success"] and not report["mechanism_supported"]
        else "scripted_shared_unique_delivery_fail" if report["mechanism_supported"]
        and not final_eval["task_success"]
        else "control_not_supported")
    report["lock"]=(lock.summary() if lock else {"enabled":False})
    report["final_observation"]=_capture(envs[a_binding],out,"a-after-write")
    return report,envs


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",required=True)
    p.add_argument("--artifact-parent",type=Path,required=True)
    args=p.parse_args()
    # Pin the already-installed local runtime before any Guest is constructed.
    # Never allow OSWorld's default provider image to trigger an implicit pull.
    runtime_image="swcub/osworld-v2.1-qemu-runtime:local"
    os.environ["OSWORLD_V2_DIR"]=str(base.OSWORLD_V2_DIR)
    os.environ["SWCUB_OSWORLD_GUEST_IMAGE"]=str(base.resolve_guest_image_path())
    os.environ["SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    os.environ["OSWORLD_DOCKER_RUNTIME_IMAGE"]=runtime_image
    if not Path(os.environ["SWCUB_OSWORLD_GUEST_IMAGE"]).is_file():
        raise RuntimeError("pinned local Guest qcow2 is missing")
    image_check=subprocess.run(["docker","image","inspect",runtime_image,"--format","{{.Id}}"],
        check=True,capture_output=True,text=True,timeout=15)
    if image_check.stdout.strip()!="sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec":
        raise RuntimeError("pinned local Docker runtime image ID differs from audited image")
    parent=args.artifact_parent.expanduser().resolve()
    if not parent.is_relative_to(Path("/mnt/raid1")):
        raise RuntimeError("artifacts must be on RAID1; refusing root-disk run")
    os.environ["SWCUB_OSWORLD_CACHE_DIR"]=str(parent/"osworld-cache")
    out=parent/args.run_id
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
    report={"run_id":args.run_id,"candidate":"CWD-1 unique-delivery / QA bundle",
        "task_version":"0.2.0","model_used":False,
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
