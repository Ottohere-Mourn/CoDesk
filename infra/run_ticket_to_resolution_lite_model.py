#!/usr/bin/env python3
"""Run one screenshot-driven Ticket-to-Resolution Lite v1 model episode."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_ticket_to_resolution_lite_native as native


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def wait_for_actor_side_effects(root: Path, roles: tuple[str, ...], *,
                                minimum_wait_s: float = 5.0,
                                quiet_s: float = 8.0,
                                timeout_s: float = 90.0) -> dict:
    """Let browser/model calls already in flight finish before oracle snapshot.

    A Codex wall timeout can expire while a browser POST is still being serviced.
    In that case an immediate snapshot can miss a transaction that commits a few
    seconds later. Track database/journal changes and completed write requests,
    while ignoring read-only page polling.
    """
    root = Path(root)
    db = root / "db" / "case.sqlite3"
    tracked = [
        db, Path(str(db) + "-journal"), Path(str(db) + "-wal"),
        root / "desktop_requests.jsonl",
        *(root / "model_relays" / role / "events.jsonl" for role in roles),
    ]

    def signature() -> tuple:
        file_state = []
        for path in tracked:
            try:
                stat = path.stat()
                file_state.append((str(path.relative_to(root)), stat.st_size,
                                   stat.st_mtime_ns))
            except FileNotFoundError:
                file_state.append((str(path.relative_to(root)), None, None))
        # GET /review-ready can poll continuously; only mutating HTTP requests
        # and database writes matter to the business-state snapshot.
        writes = sum(1 for row in read_jsonl(root / "db" / "case.http.jsonl")
                     if row.get("method", "GET").upper() not in {"GET", "HEAD", "OPTIONS"})
        return (*file_state, ("completed_write_requests", writes))

    started = time.monotonic()
    deadline = started + max(0.0, timeout_s)
    previous = signature()
    changed_at = started
    while True:
        now = time.monotonic()
        current = signature()
        if current != previous:
            previous = current
            changed_at = now
        quiet_for = now - changed_at
        elapsed = now - started
        if elapsed >= minimum_wait_s and quiet_for >= quiet_s:
            return {"settled": True, "wait_s": round(elapsed, 2),
                    "quiet_s": round(quiet_for, 2),
                    "completed_write_requests": previous[-1][1]}
        if now >= deadline:
            return {"settled": False, "wait_s": round(elapsed, 2),
                    "quiet_s": round(quiet_for, 2),
                    "completed_write_requests": previous[-1][1]}
        time.sleep(min(0.5, max(0.0, deadline - now)))


def usage_report(root: Path, roles: tuple[str, ...]) -> dict:
    by_role = {}
    intervals = []
    for role in roles:
        events = read_jsonl(root / "model_relays" / role / "events.jsonl")
        inputs = outputs = missing = 0
        latencies = []
        endpoint_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for event in events:
            usage = event.get("usage") or {}
            if isinstance(usage.get("input_tokens"), int):
                inputs += usage["input_tokens"]
            else:
                missing += 1
            if isinstance(usage.get("output_tokens"), int):
                outputs += usage["output_tokens"]
            else:
                missing += 1
            elapsed = event.get("elapsed_s")
            finished = event.get("time")
            if isinstance(elapsed, (int, float)):
                latencies.append(float(elapsed))
            if isinstance(elapsed, (int, float)) and isinstance(finished, (int, float)):
                intervals.append((role, float(finished) - float(elapsed), float(finished)))
            endpoint = event.get("selected_endpoint")
            if endpoint:
                endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
            status = event.get("upstream_status")
            if status is not None:
                status_counts[str(status)] = status_counts.get(str(status), 0) + 1
        by_role[role] = {
            "request_count": len(events), "input_tokens": inputs, "output_tokens": outputs,
            "total_tokens": inputs + outputs, "missing_usage_request_count": missing,
            "request_latency_sum_s": round(sum(latencies), 2),
            "request_latency_mean_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "selected_endpoint_counts": endpoint_counts, "upstream_status_counts": status_counts,
            "output_token_budget": native.MODEL_RELAY_OUTPUT_BUDGET,
            "output_budget_basis": "cumulative actual response output tokens; one response can exceed the threshold",
        }
    overlaps = []
    for index, current in enumerate(intervals):
        for previous in intervals[:index]:
            if current[0] != previous[0] and current[1] < previous[2] and previous[1] < current[2]:
                overlaps.append({"roles": [previous[0], current[0]],
                                 "start_unix": max(previous[1], current[1]),
                                 "end_unix": min(previous[2], current[2])})
    return {
        "by_role": by_role,
        "total_input_tokens": sum(value["input_tokens"] for value in by_role.values()),
        "total_output_tokens": sum(value["output_tokens"] for value in by_role.values()),
        "total_tokens": sum(value["total_tokens"] for value in by_role.values()),
        "overlapping_request_intervals": overlaps,
        "currency_cost": None,
        "currency_cost_note": "The configured gateway exposes token usage but no price in the response.",
    }


def handoff_audit(root: Path, condition: str, oracle: dict, actor_results: dict[str, dict]) -> dict:
    from datetime import datetime
    from oscombo.collab.ticket_to_resolution.database import CaseStore

    if condition == "single_agent":
        return {"applicable": False}

    def epoch(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    audit = CaseStore(root / "db" / "case.sqlite3").list_audit()
    review = next((row for row in audit if row["event_type"] == "case_review_saved"
                   and row["actor_id"] == "A"), None)
    gui_review = next((row for row in audit if row["event_type"] == "page_view"
                       and row["actor_id"] == "B"
                       and row["target_id"].startswith("/reviews/")), None)
    refund = next((row for row in audit if row["event_type"] == "refund_issued"
                   and row["actor_id"] == "B"), None)
    protocol_events = read_jsonl(root / "collaboration" / "events.jsonl")
    sent = [row for row in protocol_events if row.get("type") == "message"
            and row.get("actor") == "A" and row.get("recipient") in {"B", "all"}]
    reads = [row for row in read_jsonl(root / "collaboration_reads.jsonl")
             if row.get("reader") == "B"]
    read_ids = {message_id for row in reads for message_id in row.get("message_ids", [])}
    message = next((row for row in sent if row.get("message_id") in read_ids), None)
    read_row = next((row for row in reads if message
                     and message.get("message_id") in row.get("message_ids", [])), None)
    times = (
        epoch(review.get("timestamp")) if review else None,
        epoch(message.get("timestamp")) if message else None,
        read_row.get("time_unix") if read_row else None,
        epoch(gui_review.get("timestamp")) if gui_review else None,
        epoch(refund.get("timestamp")) if refund else None,
    )
    strict_order = all(value is not None for value in times) and all(
        earlier <= later for earlier, later in zip(times, times[1:]))
    b_trace = actor_results.get("B", {}).get("trace", [])
    return {
        "applicable": True,
        "review_saved_by_A": review is not None,
        "A_message_count": len(sent),
        "B_read_event_count": len(reads),
        "A_message_id_read_by_B": message.get("message_id") if message else None,
        "B_opened_review_in_gui": gui_review is not None,
        "refund_issued_by_B": refund is not None,
        "strict_review_message_read_gui_refund_order": strict_order,
        "timestamps_unix": {"review_saved": times[0], "message_sent": times[1],
                            "message_read": times[2], "review_opened_gui": times[3],
                            "refund_issued": times[4]},
        "B_read_messages_tool_calls": sum(
            str(row.get("tool", "")).endswith("read_messages") for row in b_trace),
        "oracle_review_opened_in_gui_by_B": oracle.get("process_evidence", {}).get(
            "review_opened_in_gui_by_B"),
    }


def public_handoff_state(root: Path) -> dict:
    from datetime import datetime
    from oscombo.collab.ticket_to_resolution.database import CaseStore

    def epoch(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    audit = CaseStore(root / "db" / "case.sqlite3").list_audit()
    reviews = [row for row in audit if row["event_type"] == "case_review_saved"
               and row["actor_id"] == "A"]
    messages = [row for row in read_jsonl(root / "collaboration" / "events.jsonl")
                if row.get("type") == "message" and row.get("actor") == "A"
                and row.get("recipient") in {"B", "all"}]
    latest_review = reviews[-1] if reviews else None
    latest_message = messages[-1] if messages else None
    reads = [row for row in read_jsonl(root / "collaboration_reads.jsonl")
             if row.get("reader") == "B"]
    read_ids = {message_id for row in reads for message_id in row.get("message_ids", [])}
    message_read = bool(latest_message and latest_message.get("message_id") in read_ids)
    last_read_time = max((row.get("time_unix", 0) for row in reads), default=0)
    review_time = epoch(latest_review.get("timestamp")) if latest_review else None
    review_not_seen = bool(latest_review and review_time is not None and last_read_time < review_time)
    review_saved = latest_review is not None
    message_sent = latest_message is not None
    return {
        "review_saved_by_A": review_saved,
        "A_message_sent_to_B": message_sent,
        "latest_A_message_id": latest_message.get("message_id") if latest_message else None,
        "latest_A_message_read_by_B": message_read,
        "review_saved_after_B_last_read": review_not_seen,
        "ready_to_wake": bool(review_saved and message_sent and (not message_read or review_not_seen)),
        "handoff_seen_by_B": bool(review_saved and message_sent and message_read and not review_not_seen),
    }


def resume_codex_after_handoff(harness, context, timeout: float):
    from oscombo.harness.base import AgentResult

    prompt = (
        "A collaboration update is available. Continue your original task. "
        "Inspect the messages and saved case review using the collaboration tools; "
        "do not assume what the update says. Your original desktop-call budget still applies."
    )
    command = [harness.binary, "exec", "resume", "--last", "--all", "--json",
               "--skip-git-repo-check", prompt]
    result = AgentResult(status="running")
    started = time.monotonic()
    if timeout <= 0:
        result.status = "timeout"
        result.extra.update({"exit_code": None, "agent_s": 0.0,
                             "resumed_after_external_update": True})
        result.trace = harness.trace(context)
        return result
    with open(harness.dir / "stdout.log", "a", encoding="utf-8") as stdout, \
            open(harness.dir / "stderr.log", "a", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, env=harness.env(context), cwd=harness.dir,
                                   stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
                                   start_new_session=True)
        deadline = started + timeout
        while process.poll() is None:
            if context.stop.is_set() or time.monotonic() >= deadline:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                result.status = "timeout"
                break
            time.sleep(1)
    result.extra.update({"exit_code": process.returncode,
                         "agent_s": round(time.monotonic() - started, 1),
                         "resumed_after_external_update": True})
    result.trace = harness.trace(context)
    used = sum(row.get("tool") != "declare_infeasible" for row in result.trace)
    if (harness.dir / "INFEASIBLE").exists():
        result.status = "fail"
    elif result.status == "timeout":
        pass
    elif used >= context.max_steps:
        result.status = "max_steps"
    elif process.returncode == 0:
        result.status = "done"
    else:
        result.status = "error"
        result.error = f"exit code {process.returncode}: " + (harness.dir / "stderr.log").read_text()[-300:]
    return result


def artifact_manifest(root: Path, roles: tuple[str, ...]) -> list[dict]:
    candidates = [
        root / "db" / "case.sqlite3",
        root / "db" / "case.sqlite3.http.jsonl",
        root / "evidence" / "pre-reset-case.sqlite3",
        root / "collaboration" / "events.jsonl",
        root / "collaboration_reads.jsonl",
        root / "actor_lifecycle.jsonl",
        root / "desktop_requests.jsonl",
        root / "run_config.json",
    ]
    candidates.extend((root / "screenshots").rglob("*.png"))
    candidates.extend((root / "screenshots").rglob("*.json"))
    candidates.extend((root / "screenshots").rglob("*.txt"))
    for role in roles:
        candidates.append(root / "actor_runs" / role / "trace.json")
        candidates.extend((root / "actor_runs" / role).glob("*.log"))
        candidates.append(root / "model_relays" / role / "events.jsonl")
    result = []
    for path in candidates:
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            result.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
                           "sha256": digest.hexdigest()})
    return result


def snapshot_database(source_path: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
    destination.chmod(0o600)
    return {"path": str(destination.relative_to(source_path.parents[1])),
            "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


def run_episode(args: argparse.Namespace) -> int:
    from oscombo.harness.base import AgentContext
    from oscombo.harness.external import CodexHarness
    from oscombo.collab.ticket_to_resolution.oracle import evaluate
    from oscombo.collab.ticket_to_resolution.integration import codex_collaboration_binding
    from oscombo.collab.ticket_to_resolution.lite_v1 import CASE_ID, CASE_VERSION
    from oscombo.collab.ticket_to_resolution.lite_v1 import spec as lite_spec

    root = args.run_root.absolute()
    run_id = args.run_id
    if not run_id.startswith("ttr-lite-") or "/" in run_id or "\\" in run_id:
        raise ValueError("run IDs must start with ttr-lite- and contain no path separators")
    if root.is_symlink() or (root.exists() and any(root.iterdir())):
        raise FileExistsError("run root exists and is non-empty; preserve it and choose a fresh path")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    os.umask(0o077)
    native._bypass_proxy_for_local_services()
    config, config_summary = native._load_model_config()
    endpoint_probe = native._probe_model_catalog(config)
    if not endpoint_probe["pass"]:
        raise RuntimeError("gpt-6.1-sol is not listed by both configured endpoints")

    condition = args.condition
    roles = ("S",) if condition == "single_agent" else ("A", "B")
    if args.mitigation == "input-lock" and condition != "collaborative_shared":
        raise ValueError("input-lock ablation is defined only for Shared desktop runs")
    if args.pilot and condition == "single_agent":
        raise ValueError("single-agent solvability uses the full Lite role budget")
    step_budget = args.step_budget or (8 if args.pilot else None)
    if condition == "single_agent":
        step_budget = step_budget or lite_spec.ROLE_BUDGET["S"]["steps"]
        wall_seconds = args.wall_seconds or lite_spec.ROLE_BUDGET["S"]["wall_seconds"]
    else:
        step_budget = step_budget or lite_spec.ROLE_BUDGET["A"]["steps"]
        wall_seconds = args.wall_seconds or (480 if args.pilot else
                                             lite_spec.ROLE_BUDGET["A"]["wall_seconds"])

    app_url = f"http://{native.GUEST_SERVICE_HOST}:{native.GUEST_SERVICE_PORT}/login"
    native._prepare_episode(root, run_id, condition, app_url)
    config_path = root / "run_config.json"
    run_config = json.loads(config_path.read_text(encoding="utf-8"))
    run_config.update({
        "case_id": CASE_ID, "case_version": CASE_VERSION, "case_variant": "lite-v1",
        "model": native.MODEL, "effort": "medium", "mitigation": args.mitigation,
        "role_step_budget": {role: step_budget for role in roles},
        "role_wall_seconds": wall_seconds,
        "output_token_budget_per_role": native.MODEL_RELAY_OUTPUT_BUDGET,
    })
    native._write_json(config_path, run_config)
    report: dict[str, Any] = {
        "schema": "codesk.ticket-to-resolution-lite.model.v1",
        "run_id": run_id, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "source_case_id": lite_spec.SOURCE_CASE_ID, "case_variant": "lite-v1",
        "condition": condition, "mode": "model_episode", "status": "PREFLIGHT",
        "provider": "native-qemu-tcg", "acceleration": "TCG",
        "vcpus_per_guest": native.VCPUS, "ram_per_guest": native.RAM,
        "model": native.MODEL, "effort": "medium", "endpoint_config": config_summary,
        "endpoint_probe": endpoint_probe, "model_called": False,
        "output_token_budget_per_role": native.MODEL_RELAY_OUTPUT_BUDGET,
        "effective_step_budget_per_role": {role: step_budget for role in roles},
        "effective_wall_seconds_per_role": wall_seconds,
        "pilot": args.pilot, "mitigation": args.mitigation,
        "base_image": str(native.IMAGE),
        "base_image_sha256_before": native.BASE_IMAGE_SHA256,
        "base_image_fingerprint_before": native._image_fingerprint(),
        "base_image_hash_basis": "fully hashed before and after the first Guest control; QEMU uses read-only base image",
        "api_compatibility_probe": {
            "model": native.MODEL, "input": "160x96 PNG image",
            "preferred": {"http_status": 200, "elapsed_s": 14.27,
                          "input_tokens": 4459, "output_tokens": 20,
                          "function_call": "report_visible"},
            "fallback": {"http_status": 200, "elapsed_s": 6.57,
                         "input_tokens": 83, "output_tokens": 41,
                         "function_call": "report_visible"},
            "scope": "synthetic screenshot plus required tool; Guest images are exercised in this episode",
        },
        "run_root": str(root), "started_unix": time.time(),
        "setup": {}, "actors": {}, "resource_samples": [],
    }
    native._write_json(root / "progress.json", report)
    relays: dict[str, subprocess.Popen] = {}
    relay_env_names: set[str] = set()
    relay_urls: dict[str, str] = {}
    relay_token_envs: dict[str, str] = {}
    environments: dict[str, Any] = {}
    guests: dict[str, Any] = {}
    proxies: dict[str, native.ObservedGuest] = {}
    contexts: dict[str, AgentContext] = {}
    harnesses: dict[str, CodexHarness] = {}
    threads: dict[str, threading.Thread] = {}
    results: dict[str, dict[str, Any]] = {}
    result_lock = threading.Lock()
    case_server = protocol_server = None
    case_thread = protocol_thread = None
    app_port = None
    actor_guest_keys: dict[str, str] = {}
    browser_profiles: dict[str, str] = {}
    try:
        for role in roles:
            process, relay_url, token_env = native._start_model_relay(root, role, config)
            relays[role], relay_urls[role], relay_token_envs[role] = process, relay_url, token_env
            relay_env_names.add(token_env)
            relay_env_names.add(f"CODESK_TTR_LITE_UPSTREAM_{role}")
        report["relay_processes"] = {role: process.pid for role, process in relays.items()}
        report["status"] = "MODEL_RELAYS_READY"
        native._write_json(root / "progress.json", report)

        (environments, guests, actor_guest_keys, case_server, case_thread,
         protocol_server, protocol_thread, app_port, browser_profiles, credentials) = native._boot_and_prepare(
            root, run_id, condition, "lite-v1", report, prepared=True)

        shared_input_lock = threading.Lock() if args.mitigation == "input-lock" else None
        for role in roles:
            guest_key = actor_guest_keys[role]
            proxies[role] = native.ObservedGuest(
                role, guest_key, guests[guest_key], root, input_lock=shared_input_lock)
            if role == "S":
                instruction = lite_spec.SINGLE_AGENT_INSTRUCTION
                collaboration = None
            else:
                instruction = lite_spec.ACTOR_A_INSTRUCTION if role == "A" else lite_spec.ACTOR_B_INSTRUCTION
                bindings, collab_env = codex_collaboration_binding(
                    root, role, f"http://127.0.0.1:{protocol_server.server_port}")
                collaboration = bindings["collaboration"]
                for name, value in collab_env.items():
                    os.environ[name] = value
                    relay_env_names.add(name)
            instruction += (
                "\nCase Desk window titles include the signed-in role. "
                "Use only your own role window and the desktop/collaboration tools."
            )
            options: dict[str, Any] = {
                "base_url": relay_urls[role],
                "api_key_env": relay_token_envs[role],
                "redact_env_keys": [f"CODESK_TTR_LITE_UPSTREAM_{role}"],
                "auth_mode": "auto",
                "wire_api": "responses",
                "mcp_python": os.environ.get("CODESK_TTR_MCP_PYTHON", str(PROJECT / ".venv" / "bin" / "python")),
                "codex_bin": os.environ.get("CODESK_TTR_CODEX_BIN", "/opt/data/private/mjh/tools/bin/codex"),
                "timeout": wall_seconds,
                "request_retries": 1,
                "stream_retries": 1,
                "desktop_screenshot_settle_sec": 1.0,
                "min_non_black_pixel_fraction": 0.01,
                "require_nonflat_screenshot": True,
                "prompt_suffix": (
                    "\nIf the visible Shared window belongs to the other role, switch to your own signed-in window."
                ),
            }
            if collaboration:
                options["collaboration"] = collaboration
            actor_spec = {"harness": "codex", "model": native.MODEL,
                          "effort": "medium", "options": options}
            context = AgentContext(
                name=role, task_id=CASE_ID, instruction=instruction, guest=proxies[role],
                out=root / "actor_runs", max_steps=step_budget,
                spec=actor_spec, t0=time.time())
            harness = CodexHarness(actor_spec)
            harness.prepare(context)
            contexts[role] = context
            harnesses[role] = harness
            report["actors"][role] = {
                "status": "READY", "guest_key": guest_key, "max_steps": step_budget,
                "wall_seconds": wall_seconds,
                "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                "codex_version": harness.harness_version,
                "collaboration_enabled": collaboration is not None,
            }

        barrier = threading.Barrier(len(roles))
        report_lock = threading.Lock()

        def run_actor(role: str) -> None:
            context = contexts[role]
            record: dict[str, Any] = {"role": role, "guest_key": actor_guest_keys[role]}
            active_intervals = []
            active_seconds = 0.0
            suspended_seconds = 0.0
            lifecycle_timeout = False
            handoff_unavailable = False
            try:
                barrier.wait(timeout=300)
                record["started_unix"] = time.time()
                context.t0 = record["started_unix"]
                role_deadline = time.monotonic() + wall_seconds
                with report_lock:
                    report["actors"][role]["started_unix"] = record["started_unix"]
                    report["status"] = "MODEL_ACTORS_RUNNING"
                    native._write_json(root / "progress.json", report)
                model_started = time.time()
                outcome = harnesses[role].run(context)
                model_finished = time.time()
                active_intervals.append({"start_unix": model_started, "end_unix": model_finished})
                active_seconds += max(0.0, model_finished - model_started)
                if role == "B" and outcome.status == "done" and len(outcome.trace) < context.max_steps:
                    handoff = public_handoff_state(root)
                    if not handoff["handoff_seen_by_B"]:
                        suspend_started = time.time()
                        request_count_at_suspend = len(read_jsonl(
                            root / "model_relays" / "B" / "events.jsonl"))
                        b_desktop_count_at_suspend = sum(
                            row.get("actor") == "B" for row in read_jsonl(root / "desktop_requests.jsonl"))
                        event = {"type": "suspend", "time_unix": suspend_started,
                                 "reason": "normal B exit before A review and handoff were both read",
                                 "handoff_state": handoff,
                                 "B_model_request_count_at_suspend": request_count_at_suspend,
                                 "B_desktop_request_count_at_suspend": b_desktop_count_at_suspend}
                        native._append(root / "actor_lifecycle.jsonl", event)
                        record["suspended_at_unix"] = suspend_started
                        record["lifecycle_events"] = [event]
                        with report_lock:
                            report["actors"]["B"].update({
                                "status": "WAITING_FOR_HANDOFF",
                                "suspended_at_unix": suspend_started,
                                "handoff_state_at_suspend": handoff,
                            })
                            native._write_json(root / "progress.json", report)
                        while time.monotonic() < role_deadline and not context.stop.is_set():
                            handoff = public_handoff_state(root)
                            if handoff["ready_to_wake"]:
                                wake_started = time.time()
                                event = {"type": "resume", "time_unix": wake_started,
                                         "handoff_state": handoff,
                                         "B_model_requests_during_suspend": max(
                                             0, len(read_jsonl(root / "model_relays" / "B" / "events.jsonl"))
                                             - request_count_at_suspend),
                                         "B_desktop_requests_during_suspend": max(
                                             0, sum(row.get("actor") == "B" for row in read_jsonl(
                                                 root / "desktop_requests.jsonl"))
                                             - b_desktop_count_at_suspend)}
                                native._append(root / "actor_lifecycle.jsonl", event)
                                record["lifecycle_events"].append(event)
                                suspended_seconds = max(0.0, wake_started - suspend_started)
                                remaining = max(0.0, role_deadline - time.monotonic())
                                with report_lock:
                                    report["actors"]["B"].update({
                                        "status": "RESUMING",
                                        "resumed_at_unix": wake_started,
                                        "suspended_seconds": round(suspended_seconds, 2),
                                    })
                                    native._write_json(root / "progress.json", report)
                                model_started = time.time()
                                outcome = resume_codex_after_handoff(
                                    harnesses["B"], context, remaining)
                                model_finished = time.time()
                                active_intervals.append({"start_unix": model_started,
                                                         "end_unix": model_finished})
                                active_seconds += max(0.0, model_finished - model_started)
                                record["resumed_at_unix"] = wake_started
                                record["resume_finished_unix"] = model_finished
                                break
                            if "A" in results:
                                handoff_unavailable = True
                                event = {"type": "handoff_unavailable", "time_unix": time.time(),
                                         "reason": "A finished without both a saved review and message",
                                         "handoff_state": handoff}
                                native._append(root / "actor_lifecycle.jsonl", event)
                                record["lifecycle_events"].append(event)
                                suspended_seconds = max(0.0, time.time() - suspend_started)
                                break
                            time.sleep(1)
                        else:
                            lifecycle_timeout = True
                            event = {"type": "handoff_wait_timeout", "time_unix": time.time(),
                                     "handoff_state": handoff}
                            native._append(root / "actor_lifecycle.jsonl", event)
                            record["lifecycle_events"].append(event)
                            suspended_seconds = max(0.0, time.time() - suspend_started)
                trace = outcome.trace
                native._write_json(root / "actor_runs" / role / "trace.json", trace)
                record.update({
                    "status": ("handoff_wait_timeout" if lifecycle_timeout else
                               "handoff_unavailable" if handoff_unavailable else outcome.status),
                    "steps": len(trace), "agent_s": round(active_seconds, 2),
                    "model_active_seconds": round(active_seconds, 2),
                    "suspended_seconds": round(suspended_seconds, 2),
                    "active_intervals": active_intervals,
                    "error": outcome.error, "trace": trace,
                })
            except Exception as exc:
                record.update({"status": "INFRA_ERROR", "error_type": type(exc).__name__,
                               "error": str(exc)[:1000], "trace": []})
            finally:
                record["finished_unix"] = time.time()
                with report_lock:
                    results[role] = record
                    report["actors"][role].update({key: value for key, value in record.items()
                                                   if key != "trace"})
                    native._write_json(root / "progress.json", report)
        report["status"] = "ACTORS_PREPARED"
        native._write_json(root / "progress.json", report)
        for role in roles:
            threads[role] = threading.Thread(target=run_actor, args=(role,),
                                             name=f"ttr-lite-model-{role}")
            threads[role].start()
        next_sample = 0.0
        while any(thread.is_alive() for thread in threads.values()):
            now = time.monotonic()
            if now >= next_sample:
                report["resource_samples"].append({
                    "time_unix": time.time(),
                    "guests": {key: native._process_metrics(
                        getattr(getattr(env.provider, "process", None), "pid", None))
                        for key, env in environments.items()},
                })
                with report_lock:
                    native._write_json(root / "progress.json", report)
                next_sample = now + 5
            time.sleep(1)
        for thread in threads.values():
            thread.join()
        # A model wall timeout can race a browser-side POST: the Agent process
        # may stop first while Chrome is still completing the submitted form.
        # Stop accepting further actions, then wait for side-effect artifacts
        # and the SQLite state to remain quiet before scoring/resetting.
        for context in contexts.values():
            context.stop.set()
        post_actor_drain = wait_for_actor_side_effects(root, roles)
        report["post_actor_drain"] = post_actor_drain
        report["oracle_snapshot_reliable"] = bool(post_actor_drain["settled"])
        report["model_usage"] = usage_report(root, roles)
        report["oracle"] = evaluate(
            root / "db" / "case.sqlite3",
            root / "oracle" / "fixture_manifest.json",
            condition)
        report["handoff_audit"] = handoff_audit(root, condition, report["oracle"], results)
        report["desktop_interference"] = native._input_overlap(root / "desktop_requests.jsonl")
        report["actor_timing"] = {
            role: {"started_unix": record.get("started_unix"),
                   "finished_unix": record.get("finished_unix"),
                   "elapsed_s": round(record["finished_unix"] - record["started_unix"], 2)
                   if record.get("started_unix") and record.get("finished_unix") else None,
                   "model_active_seconds": record.get("model_active_seconds"),
                   "suspended_seconds": record.get("suspended_seconds", 0.0)}
            for role, record in results.items()
        }
        report["actor_overlap_s"] = 0.0
        report["actor_wall_overlap_s"] = 0.0
        if len(roles) == 2:
            first, second = (results[role] for role in roles)
            if all(first.get(key) is not None and second.get(key) is not None
                   for key in ("started_unix", "finished_unix")):
                report["actor_wall_overlap_s"] = round(max(0.0, min(
                    first["finished_unix"], second["finished_unix"])
                    - max(first["started_unix"], second["started_unix"])), 2)
                report["actor_overlap_s"] = round(sum(
                    max(0.0, min(a["end_unix"], b["end_unix"])
                        - max(a["start_unix"], b["start_unix"]))
                    for a in first.get("active_intervals", [])
                    for b in second.get("active_intervals", [])), 2)
        report["failure_attribution"] = {
            "oracle_joint_success": report["oracle"]["joint_business_success"],
            "actor_statuses": {role: record.get("status") for role, record in results.items()},
            "desktop_proxy_errors": sum(bool(row.get("error_type"))
                                         for row in read_jsonl(root / "desktop_requests.jsonl")),
            "candidate_gui_input_overlaps": len(report["desktop_interference"][
                "cross_actor_same_guest_overlap_pairs"]),
            "confirmed_misrouting": False,
            "attribution_note": "Focus and overlap samples are correlational; inspect screenshots before causal attribution.",
        }
        report["guest_count"] = len(environments)
        report["model_called"] = any(
            report["model_usage"]["by_role"][role]["request_count"] > 0 for role in roles)
        report["status"] = "TASK_PASS" if report["oracle"]["joint_business_success"] else "TASK_FAIL"
        if any(record.get("status") in {"INFRA_ERROR", "timeout", "error", "handoff_wait_timeout"}
               for record in results.values()):
            report["status"] = "INFRA_OR_BUDGET_STOP_WITH_ORACLE_SCORE"
        if not post_actor_drain["settled"]:
            report["status"] = "INFRA_OR_BUDGET_STOP_WITH_ORACLE_SCORE"
        if args.reset_after and post_actor_drain["settled"]:
            report["pre_reset_database"] = snapshot_database(
                root / "db" / "case.sqlite3", root / "evidence" / "pre-reset-case.sqlite3")
            try:
                report["reset"] = native._reset_for_next_control(
                    root, run_id, condition, guests, actor_guest_keys, browser_profiles, app_port)
            except Exception as exc:
                report["reset_failure"] = {"type": type(exc).__name__, "message": str(exc)}
        elif args.reset_after:
            report["reset_skipped"] = "actor side effects did not become quiescent"
        report["artifact_manifest"] = artifact_manifest(root, roles)
    except Exception as exc:
        report["status"] = "INFRA_FAIL"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc),
                             "traceback": traceback.format_exc()}
    finally:
        for context in contexts.values():
            context.stop.set()
        for thread in threads.values():
            thread.join(timeout=30)
        for proxy in proxies.values():
            proxy.close()
        native._close_server(protocol_server, protocol_thread)
        native._close_server(case_server, case_thread)
        report["cleanup"] = native._close_guests(environments)
        report["cleanup_verified"] = all(
            not row["qemu_alive_after_close"] and not row["overlay_exists_after_close"]
            and row["close_error_type"] is None
            and all(row["forwarded_ports_released"].values()) for row in report["cleanup"])
        report["service_port_released"] = native._port_released(app_port) if app_port else None
        report["protocol_port_released"] = (
            native._port_released(protocol_server.server_port) if protocol_server else None)
        report["cleanup_verified"] = bool(report["cleanup_verified"]
                                          and report["service_port_released"]
                                          and report["protocol_port_released"])
        setup_cleanup = report.get("setup_failure_cleanup")
        if setup_cleanup:
            report["cleanup"] = setup_cleanup.get("guests", [])
            report["service_port_released"] = setup_cleanup.get("service_port_released")
            report["protocol_port_released"] = setup_cleanup.get("protocol_port_released")
            report["cleanup_verified"] = bool(setup_cleanup.get("verified"))
        report["base_image_fingerprint_after"] = native._image_fingerprint()
        report["base_image_unchanged"] = (
            report.get("base_image_fingerprint_before") == report["base_image_fingerprint_after"])
        report["base_image_sha256_after"] = (
            native.BASE_IMAGE_SHA256 if report["base_image_unchanged"]
            else native._sha256(native.IMAGE))
        report["elapsed_total_s"] = round(time.time() - report["started_unix"], 2)
        report["model_usage"] = usage_report(root, roles)
        for name in relay_env_names:
            os.environ.pop(name, None)
        for process in relays.values():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        report["relay_processes_stopped"] = all(
            process.poll() is not None for process in relays.values())
        native._write_json(root / "result.json", report)
        native._write_json(root / "progress.json", report)
        print(json.dumps({"run_id": run_id, "status": report["status"],
                          "joint_business_success": report.get("oracle", {}).get("joint_business_success"),
                          "model_tokens": report.get("model_usage", {}).get("total_tokens"),
                          "cleanup_verified": report.get("cleanup_verified"),
                          "run_root": str(root)}, ensure_ascii=False), flush=True)
    return 0 if report.get("cleanup_verified") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=("single_agent", "collaborative_shared",
                                                "collaborative_isolated"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--step-budget", type=int)
    parser.add_argument("--wall-seconds", type=int)
    parser.add_argument("--mitigation", choices=("none", "input-lock"), default="none")
    parser.add_argument("--no-reset-after", dest="reset_after", action="store_false")
    parser.set_defaults(reset_after=True)
    args = parser.parse_args()
    native._ensure_guest_runtime_libraries()
    if args.run_root is None:
        args.run_root = native.RUNS / args.run_id
    return run_episode(args)


if __name__ == "__main__":
    raise SystemExit(main())
