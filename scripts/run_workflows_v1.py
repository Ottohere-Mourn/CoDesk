#!/usr/bin/env python3
"""Run one bounded scripted F-04/C-03 workflow on real OSWorld V2.1 Guests.

Only a new, run-owned artifact directory and its ledger-owned Guest containers may
be changed.  The two workflows use local Guest files with identical fixture hashes;
no cross-actor persistent file visibility is required by either goal.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
from time import monotonic
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_writer_calc_v1 as base
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.workflows_v1 import Workflow, get_workflow
from swcub.tasks.workflow_actors_v1 import (FocusBlockCalcActor, RectangleCalcActor,
                                             WorkflowWriterActor)


def _read_state(desktop: Any, workflow: Workflow) -> dict[str, Any]:
    return workflow.parse(lambda path: base.guest_command(desktop, ["cat", path]))


def _seed_guest(episode: Any, workflow: Workflow) -> None:
    statements = ["from pathlib import Path", "import base64"]
    for path, content in sorted(workflow.files().items()):
        statements.append(f"Path({path!r}).parent.mkdir(parents=True,exist_ok=True)")
        statements.append(f"Path({path!r}).write_bytes(base64.b64decode({base64.b64encode(content).decode()!r}))")
    episode.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(statements)))


def _open_app(episode: Any, desktop: Any, out: Path,
              workflow: Workflow, app: str) -> dict[str, Any]:
    path = workflow.calc_path if app == "calc" else workflow.writer_path
    command = (f"soffice --nologo --norestore --nofirststartwizard --{app} "
               f"{shlex.quote(path)} >/tmp/codesk-workflow-{app}.log 2>&1 & sleep 7")
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(command))
    readiness = base.wait_for_app_document(episode, desktop, app, path,
                                            out / f"{app}-readiness", timeout=120)
    context = ActorContext("task_setup", episode, "gui")
    context.press_key("ctrl+s")
    episode.refresh_observation(source="task_setup")
    if _read_state(desktop, workflow) != workflow.state_for(()) or not base._document_title_matches(
            episode._active_window_title(), app, path):
        raise base.SetupReadinessError(f"{app} failed exact post-save readiness",
                                       {"app": app, "path": path,
                                        "state": _read_state(desktop, workflow),
                                        "window": episode._active_window_title()})
    return {"path": path, "readiness": readiness, "noop_save_persisted": True,
            "active_window": episode._active_window_title()}


def _setup(episode: Any, desktop: Any, out: Path, workflow: Workflow,
           apps: list[str]) -> dict[str, Any]:
    version = base.guest_command(desktop, ["bash", "-lc", "soffice --version 2>&1"])
    if "LibreOffice" not in version:
        raise base.SetupReadinessError("LibreOffice missing", {"version_output": version})
    _seed_guest(episode, workflow)
    initial = _read_state(desktop, workflow)
    if initial != workflow.state_for(()) or not apps:
        raise base.SetupReadinessError("workflow fixture mismatch", {"actual": initial})
    opened = [_open_app(episode, desktop, out, workflow, app) for app in apps]
    return {"fixture_sha256": workflow.fixture_digest(), "initial_state": initial,
            "libreoffice_version": version.strip(), "applications": opened}


def _event_metrics(events: list[Any], workflow: Workflow) -> dict[str, Any]:
    focus = []
    routes = []
    for event in events:
        if event.kind != "gui" or event.actor not in {"actor_a", "actor_b"}:
            continue
        details = event.details
        before, after = details.get("active_window_before"), details.get("active_window_after")
        if before != after:
            focus.append({"seq": event.seq, "actor": event.actor, "before": before, "after": after})
        action = str(details.get("action", ""))
        # Navigation hotkeys can intentionally begin in the partner window.
        # Only content entry and paste have a destination that can be misrouted.
        is_content_action = "pyautogui.write" in action or (
            workflow.family == "clipboard_ownership"
            and "pyautogui.hotkey" in action and '"v"' in action)
        if not is_content_action:
            continue
        expected_app = "calc" if event.actor == "actor_a" else "writer"
        routes.append({"seq": event.seq, "actor": event.actor, "expected_app": expected_app,
                       "active_window_before": before, "action": action,
                       "wrong_app": expected_app not in before.lower() if isinstance(before, str) else None})
    samples = [(event.seq, event.details) for event in events
               if event.actor == "clipboard_observer"
               and event.action == "clipboard.sample" and event.outcome == "ok"]
    wrong_route = any(row["wrong_app"] is True for row in routes)
    clipboard_evidence = {"copy_a_seq": None, "copy_b_seq": None,
                          "paste_a_seq": None, "overwrite_between_copies": None,
                          "paste_payload_matches_original": None,
                          "paste_target_app": None, "classification": "unknown"}
    if workflow.family == "clipboard_ownership":
        a_copies = [(seq, detail) for seq, detail in samples
                    if detail.get("source_actor") == "actor_a"
                    and detail.get("phase") == "after_action"
                    and detail.get("copy_or_cut_action") is True
                    and detail.get("payload_changed") is True]
        b_copies = [(seq, detail) for seq, detail in samples
                    if detail.get("source_actor") == "actor_b"
                    and detail.get("phase") == "after_action"
                    and detail.get("copy_or_cut_action") is True
                    and detail.get("payload_changed") is True]
        a_pastes = [(seq, detail) for seq, detail in samples
                    if detail.get("source_actor") == "actor_a"
                    and detail.get("phase") == "before_action"
                    and "ctrl+v" in str(detail.get("source_action", ""))]
        if a_copies and a_pastes:
            copy_seq, copy = a_copies[0]
            paste_seq, paste = a_pastes[-1]
            intervening = [(seq, detail) for seq, detail in b_copies
                           if copy_seq < seq < paste_seq]
            old_digest = copy.get("payload_sha256")
            paste_digest = paste.get("payload_sha256")
            target = paste.get("active_window_title")
            target_ok = isinstance(target, str) and "calc" in target.lower()
            overwrite = bool(intervening and old_digest and paste_digest
                             and intervening[-1][1].get("payload_sha256") == paste_digest
                             and paste_digest != old_digest)
            clipboard_evidence = {"copy_a_seq": copy_seq,
                "copy_b_seq": intervening[-1][0] if intervening else None,
                "paste_a_seq": paste_seq, "copy_a_payload_sha256": old_digest,
                "paste_payload_sha256": paste_digest,
                "overwrite_between_copies": overwrite,
                "paste_payload_matches_original": paste_digest == old_digest
                    if old_digest and paste_digest else None,
                "paste_target_app": "Calc" if target_ok else target,
                "classification": ("clipboard_overwrite_supported" if overwrite and target_ok
                                   else "mixed_or_focus_unknown" if overwrite and not target_ok
                                   else "no_overwrite_at_paste" if old_digest and paste_digest
                                        and old_digest == paste_digest
                                   else "unknown_payload_change" if old_digest and paste_digest
                                   else "unknown")}
    if wrong_route and clipboard_evidence["classification"] == "clipboard_overwrite_supported":
        mechanism = "mixed"
    elif wrong_route:
        mechanism = "focus_misroute_supported"
    else:
        mechanism = clipboard_evidence["classification"] if workflow.family == "clipboard_ownership" else "unknown_or_absent"
    return {"focus_transitions": focus, "keyboard_routes": routes,
            "known_wrong_app_content_action_count": sum(row["wrong_app"] is True for row in routes),
            "unknown_route_count": sum(row["wrong_app"] is None for row in routes),
            "clipboard_samples": [detail for _, detail in samples]
                if workflow.family == "clipboard_ownership" else [],
            "clipboard_evidence": clipboard_evidence,
            "observed_interference": mechanism}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: argparse.Namespace) -> int:
    workflow = get_workflow(args.template)
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
    envs: dict[str, Any] = {}
    desktops: dict[str, Any] = {}
    actors: dict[str, tuple[str, Any]] = {}
    start = monotonic()
    report: dict[str, Any] = {"run_id": args.run_id, "task_id": workflow.template_id,
        "task_version": workflow.version, "condition": args.condition,
        "actor_implementation": "scripted_gui", "guest_host": os.uname().nodename,
        "model_used": False, "evidence_level": "scripted_real_guest_episode",
        "status": "starting", "scheduled_exposure": args.condition == "ma_sd",
        "recovery_control": args.recovery, "manifest": workflow.manifest(),
        "schedule": [], "setup": {}, "evaluation": {}}
    phase = "guest_startup"
    try:
        if args.condition == "ma_sd":
            plan = [("shared", ["writer", "calc"], ("actor_a", "actor_b"))]
        elif args.condition == "ma_id":
            plan = [("calc", ["calc"], ("actor_a",)),
                    ("writer", ["writer"], ("actor_b",))]
        elif args.condition == "solo_a":
            plan = [("calc", ["calc"], ("actor_a",))]
        else:
            plan = [("writer", ["writer"], ("actor_b",))]
        for binding, apps, actor_ids in plan:
            episode, desktop = base.make_desktop(binding, log, out)
            envs[binding], desktops[binding] = episode, desktop
            if args.template == "C-03":
                phase = "observer_setup"
                probe, state_path = install_guest_probe(
                    lambda argv, desktop=desktop: base.guest_command(desktop, argv),
                    ROOT / "scripts/guest_clipboard_probe.py", args.run_id + "-" + binding)
                sampler = GuestCommandClipboardSampler(
                    lambda argv, desktop=desktop: base.guest_command(desktop, argv),
                    probe_path=probe, state_path=state_path)
                episode.attach_clipboard_sampler(sampler, required=True)
                episode.clipboard_sampler.sample()
            phase = "task_setup"
            report["setup"][binding] = _setup(episode, desktop, out / binding,
                                                workflow, apps)
            for actor_id in actor_ids:
                shared = args.condition == "ma_sd"
                if actor_id == "actor_b":
                    actor = WorkflowWriterActor(template=args.template, shared_desktop=shared)
                elif args.template == "F-04":
                    actor = FocusBlockCalcActor(shared_desktop=shared,
                                                recover_focus=args.recovery)
                else:
                    actor = RectangleCalcActor(shared_desktop=shared,
                                               recopy_on_resume=args.recovery)
                actors[actor_id] = binding, actor
        report["bindings"] = {actor: binding for actor, (binding, _) in actors.items()}
        phase = "actor_execution"
        if set(actors) == {"actor_a", "actor_b"}:
            for actor_id in ("actor_a", "actor_b", "actor_a"):
                binding, actor = actors[actor_id]
                log.record("coordinator", "schedule", "workflow.actor_turn", {}, {},
                           details={"actor_id": actor_id, "binding": binding})
                actor.run_step(ActorContext(actor_id, envs[binding], "gui"))
                report["schedule"].append(actor_id)
        else:
            actor_id, (binding, actor) = next(iter(actors.items()))
            actor.run(ActorContext(actor_id, envs[binding], "gui"))
            report["schedule"].append(actor_id)
        phase = "evaluator"
        for binding, episode in envs.items():
            active = tuple(actor for actor, (target, _) in actors.items() if target == binding)
            result = workflow.evaluate(
                lambda path, desktop=desktops[binding]: base.guest_command(desktop, ["cat", path]),
                active)
            report["evaluation"][binding] = result
            for path in workflow.files():
                content = base.guest_command(desktops[binding], ["cat", path])
                artifact = out / binding / "final" / Path(path).name
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text(content, encoding="utf-8")
            episode.copy_artifacts(out / binding / "guest-artifacts")
        report["actor_goal_success"] = {actor: report["evaluation"][binding]["actor_goal_success"][actor]
                                         for actor, (binding, _) in actors.items()}
        report["condition_success"] = all(result["success"] for result in report["evaluation"].values())
        report["joint_success"] = report["condition_success"] if len(actors) == 2 else None
        report["interaction_metrics"] = _event_metrics(log.events, workflow)
        report["observer_health"] = {binding: episode.clipboard_observer_health
                                     for binding, episode in envs.items()}
        report["status"] = "completed"
        phase = "reset"
        original_bindings = list(envs)
        for episode in envs.values():
            episode.close()
        envs.clear()
        report["reset_check"] = {}
        for binding in original_bindings:
            episode, desktop = base.make_desktop(binding + "_reset", log, out)
            envs[binding + "_reset"] = episode
            absent = base.guest_command(desktop, ["bash", "-lc",
                f"test ! -e {shlex.quote(workflow.writer_path)} && "
                f"test ! -e {shlex.quote(workflow.calc_path)} && echo reset_clean"])
            report["reset_check"][binding] = {"success": "reset_clean" in absent,
                "replacement_guest_id": episode.snapshot().get("guest_container_id")}
            episode.close()
            del envs[binding + "_reset"]
        report["reset_success"] = all(row["success"] for row in report["reset_check"].values())
        if not report["reset_success"]:
            report["status"] = "invalid_environment_reset"
    except Exception as exc:
        report["status"] = ("invalid_infrastructure_or_setup" if phase in {
            "guest_startup", "task_setup", "observer_setup"}
            else "invalid_environment_reset" if phase == "reset"
            else "execution_or_evaluator_error")
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    finally:
        for binding, episode in list(envs.items()):
            try:
                episode.copy_artifacts(out / binding / "failure-artifacts")
            except Exception as exc:
                report.setdefault("artifact_errors", []).append(str(exc))
            try:
                episode.close()
            except Exception as exc:
                report.setdefault("close_errors", []).append(str(exc))
        report["wall_seconds"] = round(monotonic() - start, 3)
        try:
            log.write(out / "events.jsonl")
        except Exception as exc:
            report["event_log_error"] = str(exc)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        source_files = [ROOT / "swcub/tasks/workflows_v1.py",
                        ROOT / "swcub/tasks/workflow_actors_v1.py",
                        ROOT / "scripts/run_workflows_v1.py"]
        provenance = {"run_id": identity.run_id, "owner_token": owner,
            "task_id": workflow.template_id, "task_version": workflow.version,
            "condition": args.condition, "guest_host": os.uname().nodename,
            "guest_image": os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE"),
            "fixture_sha256": workflow.fixture_digest(),
            "source": base.git_source_state(),
            "source_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in source_files},
            "resource_ledger": str(ledger),
            "artifact_sha256": {str(path.relative_to(out)): _sha(path)
                                for path in sorted(out.rglob("*"))
                                if path.is_file() and path.name != "provenance.json"
                                and "overlays" not in path.parts}}
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "status": report["status"],
                      "success": report.get("condition_success"),
                      "reset_success": report.get("reset_success"),
                      "artifact_dir": str(out), "error": report.get("error")}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", choices=("F-04", "C-03"), required=True)
    parser.add_argument("--condition", choices=("solo_a", "solo_b", "ma_id", "ma_sd"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--recovery", action="store_true")
    return _run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
