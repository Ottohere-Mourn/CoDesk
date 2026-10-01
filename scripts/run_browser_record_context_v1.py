#!/usr/bin/env python3
"""Run one bounded scripted A-02 Browser record-context episode on OSWorld Guests."""
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
from swcub.tasks.browser_record_context_v1 import (
    EVENTS_PATH, FIXTURE_SHA256, INITIAL_STATE, MANIFEST, PORT, PROFILE_PATH,
    SERVER_BYTES, SERVER_PATH, STATE_BYTES, STATE_PATH, TASK, TASK_ID,
    TASK_VERSION, URL, ScriptedA02Actor,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _command(desktop: Any, shell: str) -> str:
    return base.guest_command(desktop, ["bash", "-lc", shell])


def _read_state(desktop: Any) -> dict[str, Any]:
    return json.loads(base.guest_command(desktop, ["cat", STATE_PATH]))


def _events(desktop: Any) -> list[dict[str, Any]]:
    raw = _command(desktop, f"cat {shlex.quote(EVENTS_PATH)} 2>/dev/null || true")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _window(desktop: Any) -> dict[str, Any]:
    raw = _command(desktop, 'printf "ID="; xdotool getactivewindow 2>/dev/null; '
                            'printf "TITLE="; xdotool getactivewindow getwindowname 2>/dev/null')
    rows = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    targets = json.loads(_command(desktop, "curl -fsS --max-time 3 "
                                            "http://127.0.0.1:9222/json/list"))
    pages = [t for t in targets if t.get("type") == "page" and t.get("url") == URL]
    state = _read_state(desktop)
    return {"window_id": rows.get("ID"), "title": rows.get("TITLE"),
            "tab_id": pages[0].get("id") if len(pages) == 1 else None,
            "url": pages[0].get("url") if len(pages) == 1 else None,
            "matching_tab_count": len(pages),
            "selected_record": state.get("selected_record"),
            "timestamp_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat()}


def _seed(episode: Any) -> None:
    statements = ["from pathlib import Path", "import base64"]
    for path, content in ((STATE_PATH, STATE_BYTES), (SERVER_PATH, SERVER_BYTES)):
        statements.append(f"Path({path!r}).parent.mkdir(parents=True,exist_ok=True)")
        statements.append(f"Path({path!r}).write_bytes(base64.b64decode({base64.b64encode(content).decode()!r}))")
    episode.cli_action("task_setup", "python3 -c " + shlex.quote("; ".join(statements)))


def _setup(episode: Any, desktop: Any, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    _seed(episode)
    if _read_state(desktop) != INITIAL_STATE:
        raise base.SetupReadinessError("A-02 initial state mismatch", {"actual": _read_state(desktop)})
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        f"python3 {shlex.quote(SERVER_PATH)} >/tmp/codesk-a02-server.log 2>&1 & sleep 2"))
    health = json.loads(_command(desktop, f"curl -fsS --max-time 3 http://127.0.0.1:{PORT}/health"))
    if health.get("ok") is not True:
        raise base.SetupReadinessError("A-02 local server health failed", {"health": health})
    binary = _command(desktop, "command -v chromium || command -v chromium-browser || "
                               "command -v google-chrome || echo NONE").strip().splitlines()[-1]
    if binary == "NONE":
        raise base.SetupReadinessError("Chromium/Chrome unavailable", {})
    launch = (f"{shlex.quote(binary)} --no-first-run --no-default-browser-check "
              f"--disable-dev-shm-usage --remote-debugging-port=9222 "
              f"--user-data-dir={shlex.quote(PROFILE_PATH)} --new-window {shlex.quote(URL)} "
              f">/tmp/codesk-a02-browser.log 2>&1 & sleep 7")
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(
        'wmctrl -a "CoDesk record workspace"; '
        'wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz; sleep 2'))
    last: dict[str, Any] = {}
    for attempt in range(1, 11):
        episode.refresh_observation(source="task_setup")
        shot = episode.observe("task_setup").get("screenshot")
        try:
            win = _window(desktop)
        except Exception as exc:
            last = {"attempt": attempt, "error": str(exc), "ready": False}
            time.sleep(2)
            continue
        if "CoDesk record workspace" in (win.get("title") or ""):
            _command(desktop, 'wid=$(xdotool getactivewindow); hexid=$(printf "0x%x" "$wid"); '
                              'wmctrl -i -r "$hexid" -b add,maximized_vert,maximized_horz; sleep 1')
        geometry_raw = _command(desktop, 'xdotool getwindowgeometry --shell '
                                         '$(xdotool getactivewindow) 2>/dev/null || true')
        geometry = dict(row.split("=", 1) for row in geometry_raw.splitlines() if "=" in row)
        ready = (isinstance(shot, bytes) and bool(shot) and
                 "CoDesk record workspace" in (win.get("title") or "") and
                 win["tab_id"] is not None and win["matching_tab_count"] == 1 and
                 int(geometry.get("WIDTH", 0)) >= 1500 and
                 int(geometry.get("HEIGHT", 0)) >= 900)
        last = {"attempt": attempt, "window": win, "screenshot": bool(shot),
                "geometry": geometry, "ready": ready}
        if ready:
            break
        time.sleep(2)
    (out / "readiness.json").write_text(json.dumps(last, indent=2) + "\n")
    if not last.get("ready"):
        raise base.SetupReadinessError("A-02 browser readiness failed", last)
    if _read_state(desktop) != INITIAL_STATE:
        raise base.SetupReadinessError("A-02 setup changed hidden state", {})
    return {"fixture_sha256": FIXTURE_SHA256, "initial_state": INITIAL_STATE,
            "browser_binary": binary, "readiness": last}


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
    actors: dict[str, tuple[str, ScriptedA02Actor]] = {}
    windows: dict[str, dict[str, Any]] = {}
    turn_events: dict[str, list[dict[str, Any]]] = {}
    seen: dict[str, int] = {}
    start = time.monotonic()
    report: dict[str, Any] = {
        "run_id": args.run_id, "task_id": TASK_ID, "template_id": "A-02",
        "task_version": TASK_VERSION, "condition": args.condition,
        "recovery_control": args.recovery, "actor_implementation": "scripted_gui",
        "model_used": False, "guest_host": os.uname().nodename,
        "status": "starting", "scheduled_exposure": args.condition == "ma_sd",
        "fixture_sha256": FIXTURE_SHA256, "manifest": MANIFEST, "setup": {}, "schedule": []}
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
            seen[binding] = len(_events(desktop))
        active = (["actor_a", "actor_b"] if args.condition in {"ma_id", "ma_sd"} else
                  ["actor_a"] if args.condition == "solo_a" else ["actor_b"])
        for actor_id in active:
            binding = "shared" if args.condition == "ma_sd" else actor_id
            actors[actor_id] = binding, ScriptedA02Actor(actor_id, recovery=args.recovery)
        report["bindings"] = {a: b for a, (b, _) in actors.items()}
        phase = "actor_execution"
        order = ["actor_a", "actor_b", "actor_a"] if len(active) == 2 else (
            ["actor_a", "actor_a"] if active == ["actor_a"] else ["actor_b"])
        for index, actor_id in enumerate(order):
            binding, actor = actors[actor_id]
            episode, desktop = envs[binding], desktops[binding]
            before = _window(desktop)
            log.record("context_observer", "observation", "browser.record_context", {}, {},
                       details={"actor_id": actor_id, "phase": "before", "turn": index, **before})
            log.record("coordinator", "schedule", "a02.actor_turn", {}, {},
                       details={"actor_id": actor_id, "binding": binding, "turn": index})
            actor.run_step(ActorContext(actor_id, episode, "gui"))
            time.sleep(0.5)
            after = _window(desktop)
            log.record("context_observer", "observation", "browser.record_context", {}, {},
                       details={"actor_id": actor_id, "phase": "after", "turn": index, **after})
            key = f"{actor_id}_{actor.turn}"
            windows[key] = after
            if actor_id == "actor_a" and actor.turn == 2:
                windows["actor_a_2_before"] = before
            latest = _events(desktop)
            turn_events[key] = latest[seen[binding]:]
            seen[binding] = len(latest)
            report["schedule"].append({"actor_id": actor_id, "binding": binding,
                                        "window_before": before, "window_after": after,
                                        "server_events": turn_events[key]})
        phase = "evaluator"
        states = {binding: _read_state(desktop) for binding, desktop in desktops.items()}
        server_events = {binding: _events(desktop) for binding, desktop in desktops.items()}
        evaluation = TASK.evaluate(condition=args.condition, states=states,
                                   windows=windows, turn_events=turn_events,
                                   recovery=args.recovery)
        report.update({"states": states, "server_events": server_events,
                       "window_snapshots": windows, "turn_events": turn_events,
                       "evaluation": evaluation,
                       "actor_goal_success": evaluation["actor_goal_success"],
                       "condition_success": evaluation["condition_success"],
                       "joint_success": evaluation["joint_success"],
                       "observed_interference": ("wrong_in_page_record_action_supported" if
                           evaluation["wrong_record_action_supported"] else "unknown_or_absent"),
                       "scripted_recovery_observed": evaluation["recovery_supported"],
                       "autonomous_recovery": False, "status": "completed"})
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
        sources = [ROOT / "swcub/tasks/browser_record_context_v1.py",
                   ROOT / "scripts/run_browser_record_context_v1.py"]
        provenance = {"run_id": identity.run_id, "task_version": TASK_VERSION,
            "task_id": TASK_ID, "condition": args.condition,
            "guest_host": os.uname().nodename, "model_used": False,
            "source": base.git_source_state(),
            "source_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in sources},
            "fixture_sha256": FIXTURE_SHA256,
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
