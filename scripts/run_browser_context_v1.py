#!/usr/bin/env python3
"""One bounded scripted A-01 episode on real OSWorld V2.1 Guests."""
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
from swcub.environment import ActorContext
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.browser_context_v1 import (
    EVENTS_PATH, MANIFEST, PORT, SERVER_PATH, STATE_PATH, TASK, TASK_VERSION,
    ScriptedA01Actor,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _command(desktop: Any, shell: str) -> str:
    return base.guest_command(desktop, ["bash", "-lc", shell])


def _read_state(desktop: Any) -> dict[str, Any]:
    return json.loads(base.guest_command(desktop, ["cat", STATE_PATH]))


def _read_server_events(desktop: Any) -> list[dict[str, Any]]:
    raw = _command(desktop, f"cat {shlex.quote(EVENTS_PATH)} 2>/dev/null || true")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _window(desktop: Any) -> dict[str, Any]:
    raw = _command(desktop, 'printf "ID="; xdotool getactivewindow 2>/dev/null; '
                           'printf "TITLE="; xdotool getactivewindow getwindowname 2>/dev/null')
    rows = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    title = rows.get("TITLE", "")
    tab = "tab-a" if "CoDesk tab-a" in title else "tab-b" if "CoDesk tab-b" in title else None
    return {"window_id": rows.get("ID"), "title": title, "tab": tab,
            "timestamp_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat()}


def _setup(episode: Any, desktop: Any, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    statements = ["from pathlib import Path", "import base64"]
    for item in MANIFEST["initial_files"]:
        path = item["guest_path"]
        payload = item["content_base64"]
        statements.extend((f"Path({path!r}).parent.mkdir(parents=True,exist_ok=True)",
                           f"Path({path!r}).write_bytes(base64.b64decode({payload!r}))"))
    episode.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(statements)))
    initial = _read_state(desktop)
    if initial != MANIFEST["initial_state"]:
        raise base.SetupReadinessError("A-01 initial state mismatch", {"actual": initial})
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"python3 {shlex.quote(SERVER_PATH)} >/tmp/codesk-a01-server.log 2>&1 & sleep 2"))
    health = _command(desktop, f"curl -fsS --max-time 3 http://127.0.0.1:{PORT}/health")
    if json.loads(health).get("ok") is not True:
        raise base.SetupReadinessError("A-01 local server health failed", {"health": health})
    binary = _command(desktop, "command -v chromium || command -v chromium-browser || "
                               "command -v google-chrome || echo NONE").strip().splitlines()[-1]
    if binary == "NONE":
        raise base.SetupReadinessError("Chromium/Chrome unavailable", {})
    launch = (f"{shlex.quote(binary)} --no-first-run --no-default-browser-check "
              f"--disable-dev-shm-usage --remote-debugging-port=9222 "
              f"--user-data-dir=/tmp/codesk_browser_context/profile --new-window "
              f"http://127.0.0.1:{PORT}/actor-a http://127.0.0.1:{PORT}/actor-b "
              f">/tmp/codesk-a01-browser.log 2>&1 & sleep 7")
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        'wmctrl -a "CoDesk tab-b"; wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz; sleep 2'))
    last: dict[str, Any] = {}
    for attempt in range(1, 11):
        episode.refresh_observation(source="task_setup")
        shot = episode.observe("task_setup").get("screenshot")
        win = _window(desktop)
        if win["tab"] is not None:
            _command(desktop, 'wid=$(xdotool getactivewindow); hexid=$(printf "0x%x" "$wid"); '
                              'wmctrl -i -r "$hexid" -b add,maximized_vert,maximized_horz; sleep 1')
        geometry_raw = _command(desktop, 'xdotool getwindowgeometry --shell '
                                         '$(xdotool getactivewindow) 2>/dev/null || true')
        geometry = dict(row.split("=", 1) for row in geometry_raw.splitlines() if "=" in row)
        raw_targets = _command(desktop, "curl -fsS --max-time 3 http://127.0.0.1:9222/json/list")
        targets = json.loads(raw_targets)
        pages = {t.get("url", "") for t in targets if t.get("type") == "page"}
        ready = (isinstance(shot, bytes) and bool(shot) and win["tab"] is not None and
                 int(geometry.get("WIDTH", 0)) >= 1500 and
                 int(geometry.get("HEIGHT", 0)) >= 900 and
                 f"http://127.0.0.1:{PORT}/actor-a" in pages and
                 f"http://127.0.0.1:{PORT}/actor-b" in pages)
        last = {"attempt": attempt, "window": win, "page_urls": sorted(pages),
                "screenshot": isinstance(shot, bytes) and bool(shot),
                "geometry": geometry, "ready": ready}
        if ready:
            break
        time.sleep(2)
    (out / "readiness.json").write_text(json.dumps(last, indent=2) + "\n")
    if not last["ready"]:
        raise base.SetupReadinessError("A-01 browser readiness failed", last)
    if _read_state(desktop) != initial:
        raise base.SetupReadinessError("A-01 setup changed hidden goals", {})
    return {"fixture_sha256": MANIFEST["manifest_sha256"], "initial_state": initial,
            "browser_binary": binary, "readiness": last}


def _observe_window(log: Any, desktop: Any, actor: str, phase: str) -> dict[str, Any]:
    state = _window(desktop)
    log.record("context_observer", "observation", "browser.window_context", {}, {},
               details={"actor_id": actor, "phase": phase, **state})
    return state


def _run(args: argparse.Namespace) -> int:
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
    actors: dict[str, tuple[str, ScriptedA01Actor]] = {}
    windows: dict[str, dict[str, Any]] = {}
    start = time.monotonic()
    report: dict[str, Any] = {
        "run_id": args.run_id, "task_id": MANIFEST["task_id"],
        "template_id": MANIFEST["template_id"], "task_version": TASK_VERSION,
        "condition": args.condition, "recovery_control": args.recovery,
        "actor_implementation": "scripted_gui", "model_used": False,
        "guest_host": os.uname().nodename, "status": "starting",
        "scheduled_exposure": args.condition == "ma_sd",
        "manifest_sha256": MANIFEST["manifest_sha256"], "setup": {}, "schedule": []}
    phase = "guest_startup"
    try:
        bindings = (["shared"] if args.condition == "ma_sd" else
                    ["actor_a", "actor_b"] if args.condition == "ma_id" else
                    ["actor_a"] if args.condition == "solo_a" else ["actor_b"])
        for binding in bindings:
            episode, desktop = base.make_desktop(binding, log, out)
            envs[binding], desktops[binding] = episode, desktop
            phase = "task_setup"
            report["setup"][binding] = _setup(episode, desktop, out / binding)
        active = (["actor_a", "actor_b"] if args.condition in {"ma_id", "ma_sd"} else
                  ["actor_a"] if args.condition == "solo_a" else ["actor_b"])
        for actor_id in active:
            binding = "shared" if args.condition == "ma_sd" else actor_id
            actors[actor_id] = (binding, ScriptedA01Actor(
                actor_id, TASK.values[actor_id],
                reacquire_on_resume=args.recovery))
        report["bindings"] = {a: b for a, (b, _) in actors.items()}
        phase = "actor_execution"
        order = ["actor_a", "actor_b", "actor_a"] if len(active) == 2 else (
            ["actor_a", "actor_a"] if active == ["actor_a"] else ["actor_b"])
        for index, actor_id in enumerate(order):
            binding, actor = actors[actor_id]
            episode, desktop = envs[binding], desktops[binding]
            before = _observe_window(log, desktop, actor_id, f"before_turn_{index}")
            log.record("coordinator", "schedule", "a01.actor_turn", {}, {},
                       details={"actor_id": actor_id, "binding": binding, "turn": index})
            actor.run_step(ActorContext(actor_id, episode, "gui"))
            after = _observe_window(log, desktop, actor_id, f"after_turn_{index}")
            windows[f"{actor_id}_{actor.turn}"] = after
            if actor_id == "actor_a" and actor.turn == 2:
                windows["actor_a_resume_before"] = before
            report["schedule"].append(actor_id)
        phase = "evaluator"
        states = {binding: _read_state(desktop) for binding, desktop in desktops.items()}
        server_events = {binding: _read_server_events(desktop)
                         for binding, desktop in desktops.items()}
        snapshots = [windows[k] for k in ("actor_a_1", "actor_b_1", "actor_a_2")
                     if k in windows] if args.condition == "ma_sd" else []
        window_events: list[dict[str, Any]] = []
        if snapshots:
            window_events.append({"kind": "window_observation",
                                  "window_id": snapshots[0]["window_id"]})
            for earlier, later in zip(snapshots, snapshots[1:]):
                window_events.append({"kind": "tab_activated",
                                      "window_id": later["window_id"],
                                      "before_tab": earlier["tab"],
                                      "after_tab": later["tab"]})
        action_context = {
            "actor_a_first_window_id": windows.get("actor_a_1", {}).get("window_id"),
            "actor_a_resume_window_id": windows.get("actor_a_resume_before", {}).get("window_id"),
            "actor_a_resume_tab": windows.get("actor_a_resume_before", {}).get("tab"),
            "actor_a_resume_after_tab": windows.get("actor_a_2", {}).get("tab"),
            "actor_a_resume_after_window_id": windows.get("actor_a_2", {}).get("window_id"),
            "tab_changed_between_actors": bool(len(snapshots) >= 2 and
                                               snapshots[0]["tab"] != snapshots[1]["tab"]),
            "recovery": args.recovery}
        evaluation = TASK.evaluate(condition=args.condition, states=states,
                                   window_events=window_events, action_context=action_context)
        report.update({"states": states, "server_events": server_events,
                       "window_snapshots": windows, "window_events": window_events,
                       "evaluation": evaluation,
                       "actor_goal_success": evaluation["actor_goal_success"],
                       "condition_success": evaluation["condition_success"],
                       "joint_success": evaluation["joint_success"],
                       "observed_interference": ("wrong_tab_action_supported" if
                           evaluation["wrong_page_action_supported"] else "unknown_or_absent"),
                       "autonomous_recovery": evaluation["recovery_supported"],
                       "status": "completed"})
        for binding, episode in envs.items():
            target = out / binding
            (target / "final").mkdir(parents=True, exist_ok=True)
            (target / "final" / "state.json").write_text(json.dumps(states[binding], indent=2) + "\n")
            (target / "final" / "server-events.json").write_text(
                json.dumps(server_events[binding], indent=2) + "\n")
            episode.copy_artifacts(target / "guest-artifacts")
        phase = "reset"
        old = list(envs)
        for episode in envs.values():
            episode.close()
        envs.clear()
        report["reset_check"] = {}
        for binding in old:
            episode, desktop = base.make_desktop(binding + "_reset", log, out)
            envs[binding + "_reset"] = episode
            absent = _command(desktop, f"test ! -e {shlex.quote(STATE_PATH)} && echo reset_clean")
            report["reset_check"][binding] = {"success": "reset_clean" in absent,
                "replacement_guest_id": episode.snapshot().get("guest_container_id")}
            episode.close()
            del envs[binding + "_reset"]
        report["reset_success"] = all(row["success"] for row in report["reset_check"].values())
        if not report["reset_success"]:
            report["status"] = "invalid_environment_reset"
    except Exception as exc:
        report["status"] = ("invalid_infrastructure_or_setup" if phase in
                            {"guest_startup", "task_setup"} else
                            "invalid_environment_reset" if phase == "reset" else
                            "execution_or_evaluator_error")
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
        report["wall_seconds"] = round(time.monotonic() - start, 3)
        try:
            log.write(out / "events.jsonl")
        except Exception as exc:
            report["event_log_error"] = str(exc)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        sources = [ROOT / "swcub/tasks/browser_context_v1.py", ROOT / "scripts/run_browser_context_v1.py"]
        provenance = {"run_id": identity.run_id, "task_version": TASK_VERSION,
            "task_id": MANIFEST["task_id"], "condition": args.condition,
            "guest_host": os.uname().nodename, "model_used": False,
            "source": base.git_source_state(),
            "source_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in sources},
            "manifest_sha256": MANIFEST["manifest_sha256"],
            "artifact_sha256": {str(p.relative_to(out)): _sha(p) for p in sorted(out.rglob("*"))
                                if p.is_file() and p.name != "provenance.json"
                                and "overlays" not in p.parts},
            "resource_ledger": str(ledger)}
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"run_id": args.run_id, "status": report["status"],
                      "success": report.get("condition_success"),
                      "reset_success": report.get("reset_success"),
                      "artifact_dir": str(out), "error": report.get("error")}))
    return 0 if report["status"] == "completed" and report.get("reset_success") else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("solo_a", "solo_b", "ma_id", "ma_sd"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-parent", type=Path, required=True)
    parser.add_argument("--recovery", action="store_true")
    return _run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
