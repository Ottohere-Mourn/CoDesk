#!/usr/bin/env python3
"""One bounded scripted C-02/F-02 Browser+Writer workflow episode on real Guests."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_writer_calc_v1 as base
from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.browser_writer_workflows_v1 import WORKFLOWS, BrowserWriterWorkflow, ScriptedBrowserWriterActor


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _command(desktop: Any, shell: str) -> str:
    return base.guest_command(desktop, ["bash", "-lc", shell])


def _read_json(desktop: Any, path: str) -> dict[str, Any]:
    return json.loads(base.guest_command(desktop, ["cat", path]))


def _server_events(desktop: Any, path: str) -> list[dict[str, Any]]:
    raw = _command(desktop, f"cat {shlex.quote(path)} 2>/dev/null || true")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _window(desktop: Any, workflow: BrowserWriterWorkflow) -> dict[str, Any]:
    raw = _command(desktop, 'printf "ID="; xdotool getactivewindow 2>/dev/null; '
                            'printf "TITLE="; xdotool getactivewindow getwindowname 2>/dev/null')
    rows = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    return {"window_id": rows.get("ID"), "title": rows.get("TITLE"),
            "browser_foreground": f"CoDesk {workflow.key}" in (rows.get("TITLE") or ""),
            "timestamp_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat()}


def _seed(episode: Any, workflow: BrowserWriterWorkflow) -> None:
    statements = ["from pathlib import Path", "import base64"]
    for path, content in sorted(workflow.files().items()):
        statements.append(f"Path({path!r}).parent.mkdir(parents=True,exist_ok=True)")
        statements.append(f"Path({path!r}).write_bytes(base64.b64decode({base64.b64encode(content).decode()!r}))")
    episode.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(statements)))


def _setup(episode: Any, desktop: Any, out: Path,
           workflow: BrowserWriterWorkflow) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    _seed(episode, workflow)
    writer = workflow.parse_writer(base.guest_command(desktop, ["cat", workflow.writer_path]))
    browser = _read_json(desktop, workflow.state_path)
    if not workflow.writer_initial_ok(writer) or browser != workflow.browser_initial():
        raise base.SetupReadinessError("Browser+Writer initial fixture mismatch",
                                       {"writer": writer, "browser": browser})
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"soffice --nologo --norestore --nofirststartwizard --writer "
        f"{shlex.quote(workflow.writer_path)} >/tmp/codesk-{workflow.key}-writer.log 2>&1 & sleep 6"))
    writer_ready = base.wait_for_app_document(episode, desktop, "writer",
        workflow.writer_path, out / "writer-readiness", timeout=120)
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"python3 {shlex.quote(workflow.server_path)} "
        f">/tmp/codesk-{workflow.key}-server.log 2>&1 & sleep 2"))
    health = json.loads(_command(desktop, f"curl -fsS --max-time 3 "
        f"http://127.0.0.1:{workflow.port}/health"))
    if health.get("ok") is not True:
        raise base.SetupReadinessError("local Browser server health failed", {"health": health})
    binary = _command(desktop, "command -v chromium || command -v chromium-browser || "
                               "command -v google-chrome || echo NONE").strip().splitlines()[-1]
    if binary == "NONE":
        raise base.SetupReadinessError("Chromium/Chrome unavailable", {})
    launch = (f"{shlex.quote(binary)} --no-first-run --no-default-browser-check "
              f"--disable-dev-shm-usage --remote-debugging-port=9222 "
              f"--user-data-dir={shlex.quote(workflow.profile_path)} --new-window "
              f"{shlex.quote(workflow.url)} >/tmp/codesk-{workflow.key}-browser.log 2>&1 & sleep 7")
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        f'wmctrl -a "CoDesk {workflow.key}"; '
        'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz; sleep 2'))
    last: dict[str, Any] = {}
    for attempt in range(1, 11):
        episode.refresh_observation(source="task_setup")
        shot = episode.observe("task_setup").get("screenshot")
        win = _window(desktop, workflow)
        if win["browser_foreground"]:
            _command(desktop, 'wid=$(xdotool getactivewindow); hexid=$(printf "0x%x" "$wid"); '
                              'wmctrl -i -r "$hexid" -b add,maximized_vert,maximized_horz; sleep 1')
        geometry_raw = _command(desktop, 'xdotool getwindowgeometry --shell '
                                         '$(xdotool getactivewindow) 2>/dev/null || true')
        geometry = dict(row.split("=", 1) for row in geometry_raw.splitlines() if "=" in row)
        targets = json.loads(_command(desktop, "curl -fsS --max-time 3 "
                                               "http://127.0.0.1:9222/json/list"))
        pages = [t for t in targets if t.get("type") == "page" and t.get("url") == workflow.url]
        ready = (isinstance(shot, bytes) and bool(shot) and win["browser_foreground"]
                 and len(pages) == 1 and int(geometry.get("WIDTH", 0)) >= 1500
                 and int(geometry.get("HEIGHT", 0)) >= 900)
        last = {"attempt": attempt, "window": win, "screenshot": bool(shot),
                "geometry": geometry, "page_count": len(pages), "ready": ready}
        if ready:
            break
        time.sleep(2)
    (out / "readiness.json").write_text(json.dumps(last, indent=2) + "\n")
    if not last.get("ready"):
        raise base.SetupReadinessError("Browser readiness failed", last)
    if _read_json(desktop, workflow.state_path) != workflow.browser_initial():
        raise base.SetupReadinessError("setup changed Browser submission", {})
    return {"fixture_sha256": workflow.fixture_sha256(), "writer": writer,
            "browser": browser, "writer_readiness": writer_ready,
            "browser_readiness": last, "browser_binary": binary}


def _interaction_metrics(events: list[Any], workflow: BrowserWriterWorkflow) -> dict[str, Any]:
    focus, routes, samples = [], [], []
    for event in events:
        if event.kind == "gui" and event.actor in {"actor_a", "actor_b"}:
            d = event.details
            before, after = d.get("active_window_before"), d.get("active_window_after")
            if before != after:
                focus.append({"seq": event.seq, "actor": event.actor,
                              "before": before, "after": after})
            action = str(d.get("action", ""))
            if event.actor == "actor_a" and (
                    "pyautogui.write" in action or "pyautogui.hotkey" in action
                    and ('"v"' in action or '"c"' in action)):
                routes.append({"seq": event.seq, "action": action,
                               "active_window_before": before})
        if event.actor == "clipboard_observer" and event.action == "clipboard.sample" and event.outcome == "ok":
            samples.append((event.seq, event.details))
    evidence = {"classification": "unknown", "copy_a_seq": None, "copy_b_seq": None,
                "paste_a_seq": None}
    if workflow.key == "C-02":
        copies_a = [(s,d) for s,d in samples if d.get("source_actor") == "actor_a"
                    and d.get("phase") == "after_action" and d.get("copy_or_cut_action") is True
                    and d.get("payload_changed") is True]
        copies_b = [(s,d) for s,d in samples if d.get("source_actor") == "actor_b"
                    and d.get("phase") == "after_action" and d.get("copy_or_cut_action") is True
                    and d.get("payload_changed") is True]
        pastes_a = [(s,d) for s,d in samples if d.get("source_actor") == "actor_a"
                    and d.get("phase") == "before_action"
                    and "ctrl+v" in str(d.get("source_action", ""))]
        if copies_a and pastes_a:
            a_seq, a = copies_a[0]; p_seq, p = pastes_a[-1]
            between = [(s,d) for s,d in copies_b if a_seq < s < p_seq]
            original, pasted = a.get("payload_sha256"), p.get("payload_sha256")
            overwritten = bool(between and original and pasted
                               and between[-1][1].get("payload_sha256") == pasted
                               and original != pasted)
            target = p.get("active_window_title")
            writer_dialog = isinstance(target, str) and "Hyperlink" in target
            evidence = {"copy_a_seq": a_seq,
                "copy_b_seq": between[-1][0] if between else None,
                "paste_a_seq": p_seq, "copy_a_digest": original,
                "paste_digest": pasted, "paste_target": target,
                "classification": ("clipboard_overwrite_supported" if overwritten and writer_dialog
                    else "mixed_or_unknown_target" if overwritten
                    else "no_overwrite_at_paste" if original and original == pasted
                    else "unknown")}
    elif workflow.key == "F-02":
        wrong = any("pyautogui.write" in row["action"] and
                    "Chrome" in (row["active_window_before"] or "")
                    for row in routes)
        evidence = {"classification": "focus_misroute_supported" if wrong else "unknown_or_absent",
                    "writer_comment_text_routed_to_chrome": wrong}
    return {"focus_transitions": focus, "actor_a_content_routes": routes,
            "clipboard_samples": [d for _,d in samples] if workflow.key == "C-02" else [],
            "observed_interference": evidence}


def _run(args: argparse.Namespace) -> int:
    workflow = WORKFLOWS[args.template]
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
    actors: dict[str, tuple[str, ScriptedBrowserWriterActor]] = {}
    start = time.monotonic()
    report = {"run_id": args.run_id, "template_id": workflow.key,
        "task_version": workflow.version, "condition": args.condition,
        "recovery_control": args.recovery, "actor_implementation": "scripted_gui",
        "model_used": False, "guest_host": os.uname().nodename,
        "status": "starting", "scheduled_exposure": args.condition == "ma_sd",
        "manifest": workflow.manifest(), "setup": {}, "schedule": []}
    phase = "guest_startup"
    try:
        bindings = (["shared"] if args.condition == "ma_sd" else
                    ["actor_a", "actor_b"] if args.condition == "ma_id" else
                    ["actor_a"] if args.condition == "solo_a" else ["actor_b"])
        for binding in bindings:
            episode, desktop = base.make_desktop(binding, log, out)
            envs[binding], desktops[binding] = episode, desktop
            if workflow.key == "C-02":
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
            report["setup"][binding] = _setup(episode, desktop, out / binding, workflow)
        active = (["actor_a", "actor_b"] if args.condition in {"ma_id", "ma_sd"} else
                  ["actor_a"] if args.condition == "solo_a" else ["actor_b"])
        for actor_id in active:
            binding = "shared" if args.condition == "ma_sd" else actor_id
            actors[actor_id] = binding, ScriptedBrowserWriterActor(
                workflow, actor_id, recovery=args.recovery)
        report["bindings"] = {actor: binding for actor, (binding, _) in actors.items()}
        phase = "actor_execution"
        order = ["actor_a", "actor_b", "actor_a"] if len(active) == 2 else (
            ["actor_a", "actor_a"] if active == ["actor_a"] else ["actor_b"])
        for index, actor_id in enumerate(order):
            binding, actor = actors[actor_id]
            desktop, episode = desktops[binding], envs[binding]
            before = _window(desktop, workflow)
            log.record("coordinator", "schedule", "browser_writer.actor_turn", {}, {},
                       details={"actor_id": actor_id, "binding": binding,
                                "index": index, "window_before": before})
            actor.run_step(ActorContext(actor_id, episode, "gui"))
            time.sleep(0.5)
            after = _window(desktop, workflow)
            report["schedule"].append({"actor_id": actor_id, "binding": binding,
                                        "window_before": before, "window_after": after})
        phase = "evaluator"
        writer_xml = {binding: base.guest_command(desktop, ["cat", workflow.writer_path])
                      for binding, desktop in desktops.items()}
        browser_state = {binding: _read_json(desktop, workflow.state_path)
                         for binding, desktop in desktops.items()}
        server_events = {binding: _server_events(desktop, workflow.events_path)
                         for binding, desktop in desktops.items()}
        evaluation = workflow.evaluate(condition=args.condition,
                writer_xml=writer_xml, browser_state=browser_state)
        report.update({"evaluation": evaluation,
                       "actor_goal_success": evaluation["actor_goal_success"],
                       "condition_success": evaluation["condition_success"],
                       "joint_success": evaluation["joint_success"],
                       "browser_events": server_events,
                       "interaction_metrics": _interaction_metrics(log.events, workflow),
                       "observer_health": {binding: episode.clipboard_observer_health
                                           for binding, episode in envs.items()},
                       "autonomous_recovery": False, "status": "completed"})
        for binding, episode in envs.items():
            target = out / binding / "final"
            target.mkdir(parents=True, exist_ok=True)
            (target / "writer.fodt").write_text(writer_xml[binding])
            (target / "browser-state.json").write_text(json.dumps(browser_state[binding], indent=2) + "\n")
            (target / "browser-events.json").write_text(json.dumps(server_events[binding], indent=2) + "\n")
            episode.copy_artifacts(out / binding / "guest-artifacts")
        phase = "reset"
        old = list(envs)
        for episode in envs.values():
            episode.close()
        envs.clear()
        report["reset_check"] = {}
        for binding in old:
            episode, desktop = base.make_desktop(binding + "_reset", log, out)
            envs[binding + "_reset"] = episode
            absent = _command(desktop, f"test ! -e {shlex.quote(workflow.root)} && echo reset_clean")
            report["reset_check"][binding] = {"success": "reset_clean" in absent,
                "replacement_guest_id": episode.snapshot().get("guest_container_id")}
            episode.close(); del envs[binding + "_reset"]
        report["reset_success"] = all(row["success"] for row in report["reset_check"].values())
        if not report["reset_success"]:
            report["status"] = "invalid_environment_reset"
    except Exception as exc:
        report["status"] = ("invalid_infrastructure_or_setup" if phase in
            {"guest_startup", "task_setup", "observer_setup"} else
            "invalid_environment_reset" if phase == "reset" else
            "execution_or_evaluator_error")
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    finally:
        for binding, episode in list(envs.items()):
            try: episode.copy_artifacts(out / binding / "failure-artifacts")
            except Exception as exc: report.setdefault("artifact_errors", []).append(str(exc))
            try: episode.close()
            except Exception as exc: report.setdefault("close_errors", []).append(str(exc))
        report["wall_seconds"] = round(time.monotonic() - start, 3)
        try: log.write(out / "events.jsonl")
        except Exception as exc: report["event_log_error"] = str(exc)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        sources = [ROOT / "swcub/tasks/browser_writer_workflows_v1.py",
                   ROOT / "scripts/run_browser_writer_workflows_v1.py"]
        provenance = {"run_id": identity.run_id, "owner_token": owner,
            "template_id": workflow.key, "task_version": workflow.version,
            "condition": args.condition, "guest_host": os.uname().nodename,
            "model_used": False, "source": base.git_source_state(),
            "source_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in sources},
            "fixture_sha256": workflow.fixture_sha256(),
            "resource_ledger": str(ledger),
            "artifact_sha256": {str(p.relative_to(out)): _sha(p)
                for p in sorted(out.rglob("*")) if p.is_file() and p.name != "provenance.json"
                and "overlays" not in p.parts}}
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "template_id": workflow.key,
                      "status": report["status"], "success": report.get("condition_success"),
                      "reset_success": report.get("reset_success"), "error": report.get("error"),
                      "artifact_dir": str(out)}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", choices=tuple(WORKFLOWS), required=True)
    parser.add_argument("--condition", choices=("solo_a", "solo_b", "ma_id", "ma_sd"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--recovery", action="store_true")
    return _run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
