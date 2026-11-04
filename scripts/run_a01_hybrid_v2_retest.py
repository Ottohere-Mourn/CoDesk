#!/usr/bin/env python3
"""Matched GPT-6-Sol Hybrid-v2 A-01 browser-context triplet."""
from __future__ import annotations
import argparse, concurrent.futures, json, os, secrets, shlex, socket, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT = Path("/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102")
HYBRID = Path("/home/mjh/Projects/CoDesk-case2-healthcare")
OSWORLD = Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
IMAGE = Path("/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2")
RUNTIME = "swcub/osworld-v2.1-qemu-runtime:local"
os.environ.setdefault("OSWORLD_V2_DIR", str(OSWORLD))
os.environ.setdefault("SWCUB_OSWORLD_GUEST_IMAGE", str(IMAGE))
os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
sys.path[:0] = [str(ROOT), str(HYBRID), str(OSWORLD)]
from scripts import run_writer_calc_v1 as base
from scripts import run_workflows_v1 as core
from scripts import run_browser_context_v1 as fixture
from swcub.resource_safety import ensure_resource_identity
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON
from swcub.tasks.browser_context_v1 import INPUT_POINT
TASK = fixture.TASK
MODEL = "gpt-6-sol"
BUDGET = 20
TOKEN_BUDGET = 12000
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")
PROMPTS = {
    "actor_a": (f"In Chromium tab A (CoDesk tab-a), complete your review: click the empty input, "
                f"type exactly {TASK.values['actor_a']}, and submit by pressing Enter. Do not switch tabs, "
                "edit the other tab, or change the value. Use the visible GUI; do not inspect hidden task state."),
    "actor_b": (f"In Chromium tab B (CoDesk tab-b), complete your approval: click the empty input, "
                f"type exactly {TASK.values['actor_b']}, and submit by pressing Enter. Do not switch tabs, "
                "edit the other tab, or change the value. Use the visible GUI; do not inspect hidden task state."),
}
def _json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def _setup_env(out, run_id):
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    ledger = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger), "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
        "OSWORLD_V2_DIR": str(OSWORLD)})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    return ledger, ensure_resource_identity(ledger)
def _prepare_tab(actor, ep, desktop, out, log, binding, label="initial"):
    index = 1 if actor == "A" else 2
    before = fixture._read_state(desktop)
    cmd = (f"set -e; xdotool key --clearmodifiers ctrl+{index}; sleep .3; "
           f"xdotool mousemove --sync {INPUT_POINT[0]} {INPUT_POINT[1]} click 1; sleep .3")
    ep.cli_action("coordinator", "bash -lc " + shlex.quote(cmd))
    obs = ep.refresh_observation(source="hybrid_v2_role_context")
    shot = obs.get("screenshot") if isinstance(obs, dict) else None
    win = fixture._window(desktop)
    after = fixture._read_state(desktop)
    expected = "tab-a" if actor == "A" else "tab-b"
    if win.get("tab") != expected or before != after or not isinstance(shot, bytes):
        raise RuntimeError("A-01 role-tab setup failed: " + json.dumps({
            "actor": actor, "expected_tab": expected, "window": win,
            "state_unchanged": before == after, "screenshot": isinstance(shot, bytes)}))
    dest = out / binding / f"role-{actor}-{label}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(shot)
    return {"actor": actor, "binding": binding, "active_window": win,
            "fixture_state_unchanged": True, "screenshot": str(dest)}
def _new_guest(binding, out, log):
    ep, desk = base.make_desktop(binding, log, out / binding, require_a11y_tree=False)
    try:
        setup = fixture._setup(ep, desk, out / binding)
        return ep, desk, setup
    except Exception:
        try: ep.copy_artifacts(out / binding / "setup-failure-artifacts")
        except Exception: pass
        try: ep.close()
        except Exception: pass
        raise
def _action_rows(path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    except FileNotFoundError: pass
    return rows
def _actor_actions(out, actor):
    return _action_rows(out / "actor_runs" / actor / actor / "actions.jsonl")
def _usage(out):
    summary = {}
    for actor in ("A", "B"):
        rows = _actor_actions(out, actor)
        summary[actor] = {"tool_calls": len(rows), "by_tool": {}}
        for row in rows:
            tool = str(row.get("tool", "unknown"))
            summary[actor]["by_tool"][tool] = summary[actor]["by_tool"].get(tool, 0) + 1
    return summary
def _run_arm(parent, condition, baseline):
    run_id = "a01-sol-hybrid-" + condition + "-" + uuid.uuid4().hex[:8]
    out = parent / run_id
    out.mkdir(parents=True, exist_ok=False)
    for b in ("actor_a", "actor_b", "shared", "protocol_gate", "locks"):
        (out / b).mkdir(parents=True, exist_ok=True)
    ledger, identity = _setup_env(out, run_id)
    log = base.EventLog()
    shared = condition != "ma_id"
    gate = {"enabled": shared, "gate_id": run_id + "-A-held-enter", "phase": "not_started",
            "trigger": "A key Enter after typing exact tab-a value", "pending": None, "released": False}
    signal = out / "protocol_gate" / "actor_a"; signal.mkdir(parents=True, exist_ok=True)
    gate_config = out / "protocol_gate" / "gate-config.json"
    _json(gate_config, {"gate_id": gate["gate_id"], "actor_id": "A", "tool": "key",
        "argument": "keys", "contains_any": ["enter", "return"],
        "signal_dir": str(signal), "timeout_seconds": 3500})
    envs, desktops, bindings, setups = {}, {}, {}, {}
    relay_procs, server = [], None
    statuses = {}
    start = time.time()
    report = {"run_id": run_id, "task_id": fixture.MANIFEST["task_id"],
        "template_id": fixture.MANIFEST["template_id"], "task_version": fixture.TASK_VERSION,
        "condition": condition, "runtime_profile": "gui-cli-mcp-v2",
        "actor_implementation": "CodexHarness/Codex CLI 0.155.0", "model": MODEL,
        "endpoint": os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
        "budget_per_actor": BUDGET, "per_actor_output_budget": TOKEN_BUDGET,
        "tool_permissions": ["GUI MCP", "read-only Guest CLI MCP", "Collaboration MCP"],
        "schedule_version": "A-01-rc6-held-tab-a-enter-across-tab-b",
        "fixture_manifest_sha256": fixture.MANIFEST["manifest_sha256"],
        "setup": setups, "bindings": bindings, "protocol_gate": gate, "actors": {},
        "evaluation": {}, "reset_success": False, "valid_model_run": False}
    try:
        if shared:
            if not baseline or baseline.get("model_task_outcome") != "PASS" or not baseline.get("valid_model_run"):
                raise RuntimeError("matched passing A-01 MA-ID baseline missing; Shared arm gated off")
            report["baseline_accepted"] = True; report["baseline_run_id"] = baseline["run_id"]
        plan = ([("shared", ["A", "B"])] if shared else [("actor_a", ["A"]), ("actor_b", ["B"])])
        for binding, roles in plan:
            ep, desk, setup = _new_guest(binding, out, log)
            envs[binding], desktops[binding], setups[binding] = ep, desk, setup
            for actor in roles: bindings[actor] = binding
        cli_roots = {}
        for actor, binding in bindings.items():
            cli_root = f"/tmp/codesk_cli_{run_id}_{actor}"
            envs[binding].cli_action("coordinator", "mkdir -p " + shlex.quote(cli_root))
            cli_roots[actor] = cli_root
        handoffs = []
        for actor in ("A", "B"):
            if actor in bindings:
                handoffs.append(_prepare_tab(actor, envs[bindings[actor]], desktops[bindings[actor]],
                                             out, log, bindings[actor]))
        report["role_context_handoffs"] = handoffs
        store = ProtocolStore(out / "collaboration", run_id)
        tokens = {a: secrets.token_urlsafe(32) for a in ("A", "B")}
        server = make_server(store, tokens)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        token_envs = {}
        for actor in ("A", "B"):
            token_env = "CODESK_A01_COLLAB_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[token_env] = tokens[actor]; token_envs[actor] = token_env
        def actor_task(actor):
            actor_root = out / "actor_runs" / actor; actor_root.mkdir(parents=True, exist_ok=True)
            relay_env = "CODESK_A01_RELAY_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[relay_env] = secrets.token_urlsafe(32)
            relay, relay_url = _start_codex_compat_relay(actor_root,
                os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
                "SWCUB_SOL_API_KEY", os.environ[relay_env], relay_env,
                output_token_budget=TOKEN_BUDGET, response_token_cap=2048, reserve_on_missing_usage=True)
            relay_procs.append(relay)
            from oscombo.guest import Guest
            guest = Guest(desktops[bindings[actor]])
            guest.guest_key = bindings[actor]; guest.actor = actor
            overrides = {"OSCOMBO_MCP_GATE_CONFIG": str(gate_config)} if actor == "A" and shared else None
            lock_file = str(out / "locks" / "guest-actions.lock") if condition == "ma_sd_lock" else None
            return _run_model_actor(actor, guest, PROMPTS["actor_" + actor.lower()], out, MODEL,
                relay_url, "SWCUB_SOL_API_KEY", MCP_PYTHON, f"http://127.0.0.1:{server.server_port}",
                token_envs[actor], max_steps=BUDGET, effort="medium", timeout=3500,
                request_retries=1, tool_cooldown_sec=0.0, relay_client_token_env=relay_env,
                hybrid_v2=True, condition="collaborative_shared_lock" if condition == "ma_sd_lock"
                    else "collaborative_shared" if shared else "collaborative_isolated",
                episode_id=run_id + "-" + actor, cli_root=cli_roots[actor],
                action_lock_file=lock_file, mcp_env_overrides=overrides,
                task_id=fixture.MANIFEST["task_id"] + "@" + fixture.TASK_VERSION,
                desktop_tool_timeout_sec=3600)
        gate_path = signal / "pending.json"
        if not shared:
            for actor in ("A", "B"): statuses[actor] = actor_task(actor)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future_a = pool.submit(actor_task, "A")
                deadline = time.monotonic() + 3300
                pending = None
                while time.monotonic() < deadline and pending is None and not future_a.done():
                    try:
                        pending = json.loads(gate_path.read_text(encoding="utf-8"))
                    except (FileNotFoundError, json.JSONDecodeError):
                        time.sleep(.5)
                if pending is None:
                    gate["phase"] = "A_enter_not_reached"
                    statuses["A"] = future_a.result(timeout=3700)
                    raise RuntimeError("A-01 protocol gate was not reached; no scheduled exposure occurred")
                gate["pending"] = pending
                gate["phase"] = "A_enter_held"
                gate["actor_a_window_before_handoff"] = fixture._window(desktops["shared"])
                actions_a = _actor_actions(out, "A")
                gate["exact_value_typed_before_hold"] = any(
                    r.get("tool") == "type_text" and TASK.values["actor_a"] in
                    str(r.get("args", {}).get("text", "")) for r in actions_a)
                gate["tab_a_input_state_before_hold"] = fixture._read_state(desktops["shared"])
                b_handoff = _prepare_tab("B", envs["shared"], desktops["shared"], out, log, "shared",
                                         label="before_actor_b")
                report["role_context_handoffs"].append(b_handoff)
                statuses["B"] = actor_task("B")
                b_pre = fixture._read_state(desktops["shared"])
                gate["actor_b_pre_resume_state"] = b_pre
                gate["actor_b_pre_resume_goal_success"] = (
                    b_pre.get("tabs", {}).get("tab-b", {}).get("goal") == TASK.values["actor_b"])
                gate["actor_b_terminated_before_a_resume"] = statuses["B"].get("status") in {"done", "max_steps", "fail"}
                # The native tab switch is context-only; ensure stale Enter lands in tab B.
                before_restore = fixture._window(desktops["shared"])
                if before_restore.get("tab") != "tab-b":
                    envs["shared"].cli_action("coordinator",
                        "bash -lc " + shlex.quote("xdotool key --clearmodifiers ctrl+2; sleep .3"))
                gate["actor_b_window_after_completion"] = fixture._window(desktops["shared"])
                gate["actor_b_window_before_a_resume"] = gate["actor_b_window_after_completion"]
                gate["coordinator_restored_tab_b"] = before_restore.get("tab") != "tab-b"
                message = store.send("S", "A", "Actor B has finished tab B. Resume your pending Enter now.", [])
                gate["coordination_message"] = message
                _json(signal / "release.json", {"gate_id": gate["gate_id"],
                    "reason": "B turn completed; release A's stale Enter into the now-active shared tab",
                    "actor_b_status": statuses["B"].get("status"),
                    "coordination_message_id": message.get("message_id")})
                gate["released"] = True; gate["phase"] = "A_enter_dispatched"
                statuses["A"] = future_a.result(timeout=3700)
                gate["actor_a_window_after_resume"] = fixture._window(desktops["shared"])
                gate["state_after_resume"] = fixture._read_state(desktops["shared"])
        report["actors"] = statuses
        pending = gate.get("pending") if isinstance(gate.get("pending"), dict) else {}
        actions_a = _actor_actions(out, "A")
        exact_before = any(r.get("tool") == "type_text" and TASK.values["actor_a"] in
                           str(r.get("args", {}).get("text", "")) for r in actions_a)
        gate["exact_value_typed_before_hold"] = gate.get("exact_value_typed_before_hold", exact_before)
        gate["actor_a_resume_action_dispatched"] = any(
            r.get("tool") == "key" and any(k in str(r.get("args", {}).get("keys", "")).casefold() for k in ("enter", "return"))
            for r in actions_a)
        if shared:
            gate["sequence_valid"] = bool(pending.get("actor_id") == "A" and pending.get("tool") == "key"
                and any(k in str(pending.get("args", {}).get("keys", "")).casefold() for k in ("enter", "return"))
                and gate.get("exact_value_typed_before_hold") and gate.get("released")
                and gate.get("actor_b_pre_resume_goal_success")
                and gate.get("actor_b_terminated_before_a_resume")
                and gate.get("actor_a_window_before_handoff", {}).get("tab") == "tab-a"
                and gate.get("actor_b_window_after_completion", {}).get("tab") == "tab-b")
        states = {binding: fixture._read_state(desk) for binding, desk in desktops.items()}
        windows = {}
        if shared:
            windows = {"actor_a_initial": gate.get("actor_a_window_before_handoff", {}),
                "actor_b_after_completion": gate.get("actor_b_window_after_completion", {}),
                "actor_a_resume_before": gate.get("actor_b_window_before_a_resume", {}),
                "actor_a_after_resume": gate.get("actor_a_window_after_resume", {})}
        window_events = []
        if shared:
            snaps = [windows["actor_a_initial"], windows["actor_b_after_completion"],
                     windows["actor_a_after_resume"]]
            if snaps[0].get("window_id"): window_events.append({"kind": "window_observation", "window_id": snaps[0]["window_id"]})
            for x, y in zip(snaps, snaps[1:]):
                if x.get("window_id") and y.get("window_id"):
                    window_events.append({"kind": "tab_activated", "window_id": y["window_id"],
                        "before_tab": x.get("tab"), "after_tab": y.get("tab")})
        context = {"actor_a_first_window_id": windows.get("actor_a_initial", {}).get("window_id"),
            "actor_a_resume_window_id": windows.get("actor_a_resume_before", {}).get("window_id"),
            "actor_a_resume_tab": windows.get("actor_a_resume_before", {}).get("tab"),
            "actor_a_resume_after_tab": windows.get("actor_a_after_resume", {}).get("tab"),
            "actor_a_resume_after_window_id": windows.get("actor_a_after_resume", {}).get("window_id"),
            "tab_changed_between_actors": bool(shared and windows.get("actor_a_initial", {}).get("tab") !=
                                                 windows.get("actor_a_resume_before", {}).get("tab")),
            "recovery": False}
        evaluation = TASK.evaluate(condition=condition, states=states, window_events=window_events, action_context=context)
        report.update({"states": states, "window_snapshots": windows, "window_events": window_events,
            "evaluation": evaluation, "actor_goal_success": evaluation["actor_goal_success"],
            "condition_success": evaluation["condition_success"], "joint_success": evaluation["joint_success"],
            "observed_interference": evaluation["wrong_page_action_supported"],
            "tool_usage": _usage(out), "condition_success": evaluation["condition_success"]})
        allowed = {"done", "max_steps", "fail"}
        actor_statuses_valid = bool(statuses) and all(v.get("status") in allowed for v in statuses.values())
        report["protocol_valid"] = (not shared or bool(gate.get("sequence_valid")))
        report["valid_model_run"] = actor_statuses_valid and report["protocol_valid"]
        report["model_task_outcome"] = ("environment_or_model_invalid" if not report["valid_model_run"]
            else "PASS" if report["condition_success"] else "FAIL")
        # Preserve task state evidence and server audit log before Guest shutdown.
        for binding, desk in desktops.items():
            events = fixture._read_server_events(desk)
            target = out / binding / "final"; target.mkdir(parents=True, exist_ok=True)
            (target / "state.json").write_text(json.dumps(states[binding], indent=2) + "\n")
            (target / "server-events.json").write_text(json.dumps(events, indent=2) + "\n")
        report["status"] = "completed"
    except Exception as exc:
        report["status"] = "invalid_infrastructure_or_protocol"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["valid_model_run"] = False
        report["model_task_outcome"] = "environment_or_model_invalid"
    finally:
        for binding, ep in list(envs.items()):
            try: ep.copy_artifacts(out / "guest-artifacts" / binding)
            except Exception as exc: report.setdefault("artifact_errors", []).append(str(exc))
            try: ep.close()
            except Exception as exc: report.setdefault("close_errors", []).append(str(exc))
        reset = {}
        for binding in sorted(set(bindings.values())):
            ep = None
            try:
                rd = out / "reset" / binding; rd.mkdir(parents=True, exist_ok=True)
                ep, desk = base.make_desktop(binding + "_reset", log, rd, require_a11y_tree=False)
                absent = base.guest_command(desk, ["bash", "-lc", f"test ! -e {fixture.STATE_PATH} && echo reset_clean"])
                reset[binding] = {"success": "reset_clean" in absent,
                    "replacement_guest_id": ep.snapshot().get("guest_container_id")}
            except Exception as exc: reset[binding] = {"success": False, "error": type(exc).__name__ + ": " + str(exc)}
            finally:
                if ep:
                    try: ep.close()
                    except Exception: pass
        report["reset_check"] = reset
        report["reset_success"] = bool(reset) and all(v.get("success") for v in reset.values())
        if not report["reset_success"]:
            report["valid_model_run"] = False
            report["model_task_outcome"] = "environment_or_model_invalid"
            report["status"] = "invalid_environment_reset"
        if server:
            try: server.shutdown(); server.server_close()
            except Exception: pass
        for proc in relay_procs:
            try: proc.terminate(); proc.wait(timeout=10)
            except Exception:
                try: proc.kill()
                except Exception: pass
        try: log.write(out / "events.jsonl")
        except Exception: pass
        report["wall_seconds"] = round(time.time() - start, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"] = {"run_id": identity.run_id, "source_commit": base.git_source_state(),
            "fixture_manifest_sha256": fixture.MANIFEST["manifest_sha256"],
            "condition": condition, "guest_image": os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE"),
            "guest_path": str(base.resolve_guest_image_path()), "resource_ledger": str(ledger)}
        _json(out / "report.json", report)
    return report
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifact-parent", type=Path, default=Path("/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs"))
    p.add_argument("--run-prefix", default="a01-sol-hybrid-" + time.strftime("%Y%m%d-%H%M%S"))
    args = p.parse_args()
    if not os.environ.get("SWCUB_SOL_API_KEY"): raise SystemExit("SWCUB_SOL_API_KEY missing; refusing Guest startup")
    if not IMAGE.is_file(): raise SystemExit("pinned Guest image missing; no pull attempted")
    check = subprocess.run(["docker", "image", "inspect", RUNTIME], capture_output=True, text=True, timeout=15)
    if check.returncode: raise SystemExit("pinned local runtime image missing; refusing pull")
    root = args.artifact_parent.resolve() / (args.run_prefix.strip() + "-triplet")
    root.mkdir(parents=True, exist_ok=False)
    reports, baseline = [], None
    for condition in ARMS:
        row = _run_arm(root, condition, baseline); reports.append(row)
        if condition == "ma_id":
            baseline = row
            if row.get("model_task_outcome") != "PASS" or not row.get("valid_model_run"): break
        elif not row.get("valid_model_run"): break
    arms = [{"run_id": r["run_id"], "condition": r["condition"],
             "outcome": r.get("model_task_outcome"), "valid": r.get("valid_model_run"),
             "success": r.get("condition_success"), "protocol_valid": r.get("protocol_valid"),
             "wall_seconds": r.get("wall_seconds")} for r in reports]
    _json(root / "triplet_result.json", {"task": "A-01", "task_version": fixture.TASK_VERSION,
        "runtime_profile": "gui-cli-mcp-v2", "model": MODEL, "arms": arms})
    print(json.dumps({"root": str(root), "arms": arms}, ensure_ascii=False))
if __name__ == "__main__": main()
