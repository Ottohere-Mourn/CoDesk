#!/usr/bin/env python3
"""Run one scripted CoDesk Clipboard 001 Guest episode with exact artifacts."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = Path(os.environ.get("OSWORLD_V2_DIR", ROOT.parent / "external/OSWorld-V2-osworld-v2.1")).resolve()
sys.path[:0] = [str(ROOT), str(V2)]

from scripts import run_writer_calc_v1 as base
from swcub.actors import ScriptedClipboardActor
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.clipboard_v1 import (
    CALC_PATH, CALC_SOURCE, WRITER_PATH, WRITER_SOURCE, ClipboardTaskEvaluator,
    calc_seed_odf, readiness_state, validate_topology, writer_seed_odf,
)

TASK_VERSION = "1.0.0-proposed"
GUEST_IMAGE = os.environ.get(
    "SWCUB_OSWORLD_GUEST_IMAGE",
    "/home1/mjh/Projects/CoDesk-V0-A6000/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2")


def read_state(desktop):
    return readiness_state(lambda path: base.guest_command(desktop, ["cat", path]))


def start_app(episode, desktop, out, app):
    path = WRITER_PATH if app == "writer" else CALC_PATH
    flag = "--writer" if app == "writer" else "--calc"
    base.guest_command(desktop, ["bash", "-lc",
        f"soffice --nologo --norestore --nofirststartwizard {flag} {path} "
        f">/tmp/codesk-clipboard-{app}.log 2>&1 & sleep 6"])
    return base.wait_for_app_document(episode, desktop, app, path,
                                      out / "readiness", timeout=120)


def setup_episode(episode, desktop, out, apps):
    for argv in __import__("swcub.tasks.clipboard_v1", fromlist=["clipboard_setup_commands"]).clipboard_setup_commands():
        base.guest_command(desktop, argv)
    initial = read_state(desktop)
    if not initial["ready"]:
        raise RuntimeError(f"clipboard initial fixture mismatch: {initial}")
    readiness = []
    # Calc first, Writer last gives the declared initial Writer focus in MA-SD.
    for app in apps:
        readiness.append(start_app(episode, desktop, out, app))
    return initial, readiness


def evaluate_binding(desktop, required_actor):
    return ClipboardTaskEvaluator(
        read_file=lambda path: base.guest_command(desktop, ["cat", path]),
        required_actors=(required_actor,)).evaluate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("solo_writer", "solo_calc", "ma_id", "ma_sd"),
                        required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--observer", choices=("on", "off"), default="on")
    parser.add_argument("--recopy-writer", action="store_true",
                        help="positive Writer clipboard-recovery control")
    args = parser.parse_args()
    out = args.artifact_parent.expanduser().resolve() / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    ledger = out / "resource-events.jsonl"
    owner = secrets.token_hex(32)
    os.environ.update({"SWCUB_RUN_ID": args.run_id, "SWCUB_OWNER_TOKEN": owner,
        "SWCUB_RESOURCE_LEDGER": str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays")})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    log = base.EventLog()
    envs, desktops, setup, actors = {}, {}, {}, {}
    report = {"run_id": args.run_id, "task_id": "CODESK-TB-CLIPBOARD-001",
        "task_version": TASK_VERSION, "condition": args.condition,
        "observer": args.observer, "recopy_writer": args.recopy_writer,
        "actor_implementation": "scripted", "guest_host": os.uname().nodename,
        "model_used": False, "status": "starting", "actors": {},
        "scheduled_exposure": False,
        "workspace_fixture_sha256": hashlib.sha256(
            json.dumps({"writer": hashlib.sha256(writer_seed_odf()).hexdigest(),
                        "calc": hashlib.sha256(calc_seed_odf()).hexdigest()},
                       sort_keys=True).encode()).hexdigest()}
    failure = None
    try:
        if args.condition in {"solo_writer", "solo_calc"}:
            actor_id = "writer_actor" if args.condition == "solo_writer" else "calc_actor"
            binding = "writer_desktop" if actor_id == "writer_actor" else "calc_desktop"
            apps = ["writer" if actor_id == "writer_actor" else "calc"]
            episode, desktop = base.make_desktop(binding, log, out)
            envs[binding], desktops[binding] = episode, desktop
            setup[binding] = setup_episode(episode, desktop, out / binding, apps)
            actors[actor_id] = (binding, ScriptedClipboardActor(actor_id,
                shared_desktop=False, recopy_on_resume=args.recopy_writer and actor_id=="writer_actor"))
        elif args.condition == "ma_id":
            for actor_id, binding, app in (
                ("writer_actor", "writer_desktop", "writer"),
                ("calc_actor", "calc_desktop", "calc")):
                episode, desktop = base.make_desktop(binding, log, out)
                envs[binding], desktops[binding] = episode, desktop
                setup[binding] = setup_episode(episode, desktop, out / binding, [app])
                actors[actor_id] = (binding, ScriptedClipboardActor(actor_id,
                    shared_desktop=False,
                    recopy_on_resume=args.recopy_writer and actor_id=="writer_actor"))
            report["scheduled_exposure"] = True
        else:
            binding = "shared_desktop"
            episode, desktop = base.make_desktop(binding, log, out)
            envs[binding], desktops[binding] = episode, desktop
            setup[binding] = setup_episode(episode, desktop, out / binding, ["calc", "writer"])
            actors["writer_actor"] = (binding, ScriptedClipboardActor("writer_actor",
                shared_desktop=True, recopy_on_resume=args.recopy_writer))
            actors["calc_actor"] = (binding, ScriptedClipboardActor("calc_actor",
                shared_desktop=True))
            report["scheduled_exposure"] = True

        topology_rows = {}
        for actor_id, (binding, _actor) in actors.items():
            episode, desktop = envs[binding], desktops[binding]
            backend = (f"backend-{args.run_id}-{binding}" if args.condition == "ma_id"
                       else f"backend-{args.run_id}")
            clipboard_id = (f"clipboard-{episode.environment_id}"
                            if args.condition in {"solo_writer", "solo_calc", "ma_id"}
                            else f"clipboard-{episode.environment_id}")
            topology_rows[actor_id] = {
                "workspace_backend_id": backend,
                "desktop_session_id": episode.environment_id,
                "clipboard_session_id": clipboard_id,
                "workspace_fixture_sha256": report["workspace_fixture_sha256"]}
        topology = validate_topology(args.condition, topology_rows)
        report["topology"] = topology
        installed_observers = set()
        payload_digests = {
            "writer_actor": hashlib.sha256(WRITER_SOURCE.encode("utf-8")).hexdigest(),
            "calc_actor": hashlib.sha256((CALC_SOURCE + "\n").encode("utf-8")).hexdigest()}
        for actor_id, (binding, _actor) in actors.items():
            episode, desktop = envs[binding], desktops[binding]
            if args.observer == "on":
                if binding not in installed_observers:
                    probe, state_path = install_guest_probe(
                        lambda argv, desktop=desktop: base.guest_command(desktop, argv),
                        ROOT / "scripts/guest_clipboard_probe.py",
                        args.run_id + "-" + binding)
                    sampler = GuestCommandClipboardSampler(
                        lambda argv, desktop=desktop: base.guest_command(desktop, argv),
                        probe_path=probe, state_path=state_path)
                    episode.attach_clipboard_sampler(sampler,
                        actor_payload_digests=payload_digests, required=True)
                    installed_observers.add(binding)
                report["actors"].setdefault(actor_id, {})["observer_readiness"] =                     episode.clipboard_sampler.sample()

        schedule = []
        if args.condition == "ma_sd":
            writer_binding, writer = actors["writer_actor"]
            calc_binding, calc = actors["calc_actor"]
            a_ctx = ActorContext("writer_actor", envs[writer_binding], "gui")
            b_ctx = ActorContext("calc_actor", envs[calc_binding], "gui")
            log.record("coordinator", "schedule", "clipboard.writer_copy", {}, {},
                       details={"actor": "writer_actor"})
            writer.run_step(a_ctx)
            schedule.append("writer_actor.copy_yield")
            log.record("coordinator", "schedule", "clipboard.calc_copy_paste", {}, {},
                       details={"actor": "calc_actor"})
            calc.run(b_ctx)
            schedule.append("calc_actor.copy_paste_save")
            log.record("coordinator", "schedule", "clipboard.writer_resume", {}, {},
                       details={"actor": "writer_actor", "recopy": args.recopy_writer})
            writer.run_step(a_ctx)
            schedule.append("writer_actor.resume_paste_save")
        else:
            for actor_id, (binding, actor) in actors.items():
                log.record("coordinator", "schedule", "clipboard.actor_run", {}, {},
                           details={"actor": actor_id, "binding": binding})
                actor.run(ActorContext(actor_id, envs[binding], "gui"))
                schedule.append(actor_id)
        report["schedule"] = schedule
        report["setup"] = {binding: {"initial_state": row[0],
            "app_readiness": row[1]} for binding, row in setup.items()}
        report["evaluation_by_binding"] = {}
        for actor_id, (binding, _actor) in actors.items():
            report["evaluation_by_binding"].setdefault(binding, {})
            report["evaluation_by_binding"][binding][actor_id] = evaluate_binding(
                desktops[binding], actor_id)
        required = [actor for actor in actors]
        report["success_by_actor"] = {
            actor_id: report["evaluation_by_binding"][binding][actor_id]["success"]
            for actor_id, (binding, _actor) in actors.items()}
        report["joint_success"] = all(report["success_by_actor"].values())
        report["success"] = report["joint_success"]
        report["status"] = "completed"
        report["actor_turns"] = {actor_id: actor.turn for actor_id, (_binding, actor) in actors.items()}
        report["observer_health"] = {
            actor_id: envs[binding].clipboard_observer_health
            for actor_id, (binding, _actor) in actors.items()}
        for binding, episode in envs.items():
            episode.copy_artifacts(out / binding / "guest-artifacts")
        # Destroy each task Guest before making replacement Guests for reset verification.
        for episode in envs.values():
            episode.close()
        envs.clear()
        report["reset_check"] = {}
        for binding in desktops:
            episode, desktop = base.make_desktop(binding + "_reset", log, out)
            absent = base.guest_command(desktop, ["bash", "-lc",
                f"test ! -e {WRITER_PATH} && test ! -e {CALC_PATH} && echo reset_clean"])
            report["reset_check"][binding] = {"success": "reset_clean" in absent,
                "task_files_absent": "reset_clean" in absent,
                "replacement_guest_id": episode.snapshot().get("guest_container_id")}
            episode.close()
        report["reset_success"] = all(row["success"] for row in report["reset_check"].values())
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        report.update({"status": "invalid_infrastructure_or_setup", "error": failure})
    finally:
        for episode in list(envs.values()):
            try:
                episode.copy_artifacts(out / episode.environment_id / "failure-artifacts")
            except Exception:
                pass
            try:
                episode.close()
            except Exception as close_error:
                report.setdefault("close_errors", []).append(str(close_error))
        try:
            log.write(out / "events.jsonl")
        except Exception as exc:
            report["event_log_error"] = str(exc)
        report["source"] = base.git_source_state()
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        source = {"repository": base.git_source_state(), "task_id": report["task_id"],
                  "task_version": TASK_VERSION, "run_id": identity.run_id,
                  "owner_token": owner, "resource_ledger": str(ledger),
                  "guest_host": os.uname().nodename, "guest_image": GUEST_IMAGE,
                  "runtime_image": os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"),
                  "artifact_sha256": {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in out.rglob("*") if p.is_file() and p.name != "provenance.json"}}
        (out / "provenance.json").write_text(json.dumps(source, indent=2) + "\n")
    print(json.dumps({"run_id":args.run_id,"status":report["status"],
        "success_by_actor":report.get("success_by_actor"),"joint_success":report.get("joint_success"),
        "reset_success":report.get("reset_success"),"artifact_dir":str(out),"error":report.get("error")}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
