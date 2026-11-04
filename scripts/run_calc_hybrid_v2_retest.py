#!/usr/bin/env python3
"""Matched GPT-6-Sol Hybrid-v2 Selection and Undo/Redo retests."""
from __future__ import annotations
import argparse, concurrent.futures, json, os, secrets, shlex, subprocess, sys, threading, time, uuid
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
from scripts import run_calc_mechanism_qwen_v1 as old
from scripts import probe_selection_active_object_v1 as task
from swcub.resource_safety import ensure_resource_identity
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON
MODEL = "gpt-6-sol"
BUDGET = 20
TOKEN_BUDGET = 12000
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")
def _prompts(mechanism):
    b = ("In the open LibreOffice Calc sheet, select cell C3 with Ctrl+Home, Right twice, Down twice. "
         "Type exactly B-2042 to replace that whole cell, press Enter, then Ctrl+S. Preserve every other cell.")
    if mechanism == "selection":
        a = ("In the open LibreOffice Calc sheet, select B2 with Ctrl+Home, Right once, Down once. "
             "Type exactly A-7319 to replace that whole cell, press Enter, then Ctrl+S. Preserve every other cell.")
    else:
        a = ("In LibreOffice Calc, select B2 with Ctrl+Home, Right once, Down once. Replace it with "
             "A-TEMP, press Enter, then Ctrl+S. Next press Ctrl+Z exactly once to undo your edit, then Ctrl+S "
             "again. Do not edit C3 or other cells.")
    return {"actor_a": a, "actor_b": b}
def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def _setup_env(out, run_id):
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    ledger = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger), "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
        "OSWORLD_V2_DIR": str(OSWORLD)})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    return ledger, ensure_resource_identity(ledger)
def _selected(sel, cell):
    col, row = ord(cell[0]) - 65, int(cell[1:]) - 1
    return bool(sel and sel.get("start_column") == col and sel.get("start_row") == row
                and sel.get("end_column") == col and sel.get("end_row") == row)
def _actor_actions(out, actor):
    path = out / "actor_runs" / actor / actor / "actions.jsonl"
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    except FileNotFoundError: pass
    return rows
def _tool_usage(out):
    result = {}
    for actor in ("A", "B"):
        rows = _actor_actions(out, actor); counts = {}
        for row in rows:
            tool = str(row.get("tool", "unknown")); counts[tool] = counts.get(tool, 0) + 1
        result[actor] = {"calls": len(rows), "by_tool": counts}
    return result
def _run_arm(parent, mechanism, condition, baseline):
    run_id = ("s01" if mechanism == "selection" else "u01") + "-sol-hybrid-" + condition + "-" + uuid.uuid4().hex[:8]
    out = parent / run_id; out.mkdir(parents=True, exist_ok=False)
    for b in ("actor_a", "actor_b", "shared", "protocol_gate", "locks"): (out / b).mkdir(parents=True, exist_ok=True)
    ledger, identity = _setup_env(out, run_id)
    log = base.EventLog(); prompts = _prompts(mechanism)
    shared = condition != "ma_id"
    if mechanism == "selection":
        gate_tool, gate_arg, gate_match = "type_text", "text", "A-7319"
    else:
        gate_tool, gate_arg, gate_match = "key", "keys", "ctrl+z"
    gate = {"enabled": shared, "gate_id": run_id + "-A-held-native-action",
        "phase": "not_started", "trigger": f"A {gate_tool} {gate_match}",
        "pending": None, "released": False, "precondition": None}
    signal = out / "protocol_gate" / "actor_a"; signal.mkdir(parents=True, exist_ok=True)
    gate_config = out / "protocol_gate" / "gate-config.json"
    _json(gate_config, {"gate_id": gate["gate_id"], "actor_id": "A", "tool": gate_tool,
        "argument": gate_arg, "contains": gate_match, "signal_dir": str(signal), "timeout_seconds": 3500})
    envs, desktops, bindings, setup = {}, {}, {}, {}
    relay_procs, server, statuses = [], None, {}
    started = time.time()
    task_id = task.TASK_ID if mechanism == "selection" else "CODESK-FAMILY-UNDO-HISTORY-001"
    task_version = old.TASK_VERSION
    report = {"run_id": run_id, "task_id": task_id, "task_version": task_version,
        "mechanism": mechanism, "condition": condition, "runtime_profile": "gui-cli-mcp-v2",
        "actor_implementation": "CodexHarness/Codex CLI 0.155.0", "model": MODEL,
        "endpoint": os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
        "budget_per_actor": BUDGET, "per_actor_output_budget": TOKEN_BUDGET,
        "tool_permissions": ["GUI MCP", "read-only Guest CLI MCP", "Collaboration MCP"],
        "schedule_version": f"{mechanism}-v{task_version}-held-native-action",
        "prompts": prompts, "setup": setup, "bindings": bindings,
        "manifest": {"initial_grid": task.INITIAL, "targets": {
            "actor_a": {"cell": "B2", "entry": "A-7319" if mechanism == "selection" else "A-TEMP"},
            "actor_b": {"cell": "C3", "entry": "B-2042"}},
            "shared_gate_effect": "A's pre-observed cell/history action is dispatched only after B commits"},
        "protocol_gate": gate, "actors": {}, "evaluation": {}, "states": {},
        "reset_success": False, "valid_model_run": False}
    try:
        if shared:
            if not baseline or baseline.get("model_task_outcome") != "PASS" or not baseline.get("valid_model_run"):
                raise RuntimeError("matched passing MA-ID baseline missing; Shared arm gated off")
            report["baseline_accepted"] = True; report["baseline_run_id"] = baseline["run_id"]
        plan = [("shared", ["A", "B"])] if shared else [("actor_a", ["A"]), ("actor_b", ["B"])]
        for binding, roles in plan:
            ep, desk, ready = old._setup(binding, log, out)
            envs[binding], desktops[binding], setup[binding] = ep, desk, ready
            for actor in roles: bindings[actor] = binding
        cli_roots = {}
        for actor, binding in bindings.items():
            root = f"/tmp/codesk_cli_{run_id}_{actor}"
            envs[binding].cli_action("coordinator", "mkdir -p " + shlex.quote(root))
            cli_roots[actor] = root
        report["bindings"] = dict(bindings)
        store = ProtocolStore(out / "collaboration", run_id)
        tokens = {a: secrets.token_urlsafe(32) for a in ("A", "B")}
        server = make_server(store, tokens); threading.Thread(target=server.serve_forever, daemon=True).start()
        token_envs = {}
        for actor in ("A", "B"):
            name = "CODESK_MECH_COLLAB_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[name] = tokens[actor]; token_envs[actor] = name
        def actor_task(actor):
            root = out / "actor_runs" / actor; root.mkdir(parents=True, exist_ok=True)
            relay_env = "CODESK_MECH_RELAY_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[relay_env] = secrets.token_urlsafe(32)
            relay, url = _start_codex_compat_relay(root,
                os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
                "SWCUB_SOL_API_KEY", os.environ[relay_env], relay_env,
                output_token_budget=TOKEN_BUDGET, response_token_cap=2048, reserve_on_missing_usage=True)
            relay_procs.append(relay)
            from oscombo.guest import Guest
            guest = Guest(desktops[bindings[actor]]); guest.guest_key = bindings[actor]; guest.actor = actor
            lock_file = str(out / "locks" / "guest-actions.lock") if condition == "ma_sd_lock" else None
            overrides = {"OSCOMBO_MCP_GATE_CONFIG": str(gate_config)} if actor == "A" and shared else None
            return _run_model_actor(actor, guest, prompts["actor_" + actor.lower()], out, MODEL, url,
                "SWCUB_SOL_API_KEY", MCP_PYTHON, f"http://127.0.0.1:{server.server_port}", token_envs[actor],
                max_steps=BUDGET, effort="medium", timeout=3500, request_retries=1, tool_cooldown_sec=0.0,
                relay_client_token_env=relay_env, hybrid_v2=True,
                condition="collaborative_shared_lock" if condition == "ma_sd_lock" else
                    "collaborative_shared" if shared else "collaborative_isolated",
                episode_id=run_id + "-" + actor, cli_root=cli_roots[actor],
                action_lock_file=lock_file, mcp_env_overrides=overrides,
                task_id=task_id + "@" + task_version, desktop_tool_timeout_sec=3600)
        if not shared:
            for actor in ("A", "B"): statuses[actor] = actor_task(actor)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fa = pool.submit(actor_task, "A")
                pending_path = signal / "pending.json"
                deadline = time.monotonic() + 3300; pending = None
                while time.monotonic() < deadline and pending is None and not fa.done():
                    try: pending = json.loads(pending_path.read_text(encoding="utf-8"))
                    except (FileNotFoundError, json.JSONDecodeError): time.sleep(.5)
                if pending is None:
                    gate["phase"] = "held_action_not_reached"
                    statuses["A"] = fa.result(timeout=3700)
                    raise RuntimeError("mechanism gate not reached; no scheduled exposure")
                gate["pending"] = pending; gate["phase"] = "held_action_pending"
                desk = desktops["shared"]
                if mechanism == "selection":
                    precondition = {"selected_b2": _selected(task.selection(desk), "B2"),
                        "selection": task.selection(desk), "active_window": task.active(desk),
                        "b2_uno": old._uno_cell(desk, "B2")}
                    gate["precondition"] = precondition
                else:
                    precondition = {"b2_is_a_temp": old._uno_cell(desk, "B2") == "A-TEMP",
                        "b2_uno": old._uno_cell(desk, "B2"), "b2_on_disk": old._cell(old._disk_grid(desk), "B2"),
                        "selection": task.selection(desk), "active_window": task.active(desk)}
                    gate["precondition"] = precondition
                gate["a_action_before_hold"] = pending
                statuses["B"] = actor_task("B")
                b_grid_pre = old._disk_grid(desk)
                gate["actor_b_pre_resume_grid"] = b_grid_pre
                gate["actor_b_pre_resume_goal_success"] = old._cell(b_grid_pre, "C3") == "B-2042"
                gate["actor_b_status"] = statuses["B"].get("status")
                if mechanism == "undo":
                    gate["b2_after_actor_b_before_undo"] = old._uno_cell(desk, "B2")
                    gate["c3_after_actor_b_before_undo"] = old._uno_cell(desk, "C3")
                message = store.send("S", "A",
                    "Actor B has completed and the coordination pause is over. Resume your pending GUI action now.", [])
                gate["coordination_message"] = message
                release_reason = "B completed; dispatch A's previously observed native action into shared Calc state"
                _json(signal / "release.json", {"gate_id": gate["gate_id"], "reason": release_reason,
                    "actor_b_status": statuses["B"].get("status"), "coordination_message_id": message.get("message_id")})
                gate["released"] = True; gate["phase"] = "A_action_dispatched"
                statuses["A"] = fa.result(timeout=3700)
                gate["after_resume_selection"] = task.selection(desk)
                gate["after_resume_window"] = task.active(desk)
                gate["after_resume_grid"] = old._disk_grid(desk)
        report["actors"] = statuses
        pending = gate.get("pending") if isinstance(gate.get("pending"), dict) else {}
        valid_pending = (pending.get("actor_id") == "A" and pending.get("tool") == gate_tool
            and gate_match.casefold() in str(pending.get("args", {}).get(gate_arg, "")).casefold())
        precondition = gate.get("precondition") or {}
        precondition_ok = (precondition.get("selected_b2") is True
            if mechanism == "selection" else precondition.get("b2_is_a_temp") is True)
        gate["sequence_valid"] = bool(not shared or (valid_pending and precondition_ok and gate.get("released")
            and gate.get("actor_b_pre_resume_goal_success") and gate.get("actor_b_status") in {"done", "max_steps", "fail"}
            and statuses.get("A", {}).get("status") in {"done", "max_steps", "fail"}))
        gate["mechanism_exposure"] = bool(shared and gate["sequence_valid"])
        report["states"] = {binding: {"grid": old._disk_grid(desk), "selection": task.selection(desk),
            "active_window": task.active(desk), "b2_uno": old._uno_cell(desk, "B2"),
            "c3_uno": old._uno_cell(desk, "C3")} for binding, desk in desktops.items()}
        evaluations = {}
        if shared:
            evaluations["shared"] = old._evaluate(desktops["shared"], ["actor_a", "actor_b"], mechanism)
        else:
            for actor in ("A", "B"):
                evaluations[bindings[actor]] = old._evaluate(desktops[bindings[actor]], ["actor_" + actor.lower()], mechanism)
        report["evaluation"] = evaluations
        report["actor_goal_success"] = {}
        for actor in ("A", "B"):
            binding = bindings[actor]
            roles = ["actor_a", "actor_b"] if shared else ["actor_" + actor.lower()]
            ev = old._evaluate(desktops[binding], roles, mechanism)
            address = "B2" if actor == "A" else "C3"
            final = ("A-7319" if mechanism == "selection" else str(task.INITIAL[1][1])) if actor == "A" else "B-2042"
            report["actor_goal_success"][actor] = old._cell(ev["actual_grid"], address) == final
        report["condition_success"] = (evaluations["shared"]["success"] if shared else
            all(v["success"] for v in evaluations.values()))
        report["observed_interference"] = bool(gate.get("mechanism_exposure") and not report["condition_success"])
        report["autonomous_recovery"] = bool(gate.get("mechanism_exposure") and report["condition_success"])
        report["tool_usage"] = _tool_usage(out)
        allowed = {"done", "max_steps", "fail"}
        actor_statuses_valid = bool(statuses) and all(v.get("status") in allowed for v in statuses.values())
        report["protocol_valid"] = (not shared or gate["sequence_valid"])
        report["valid_model_run"] = actor_statuses_valid and report["protocol_valid"]
        report["model_task_outcome"] = ("environment_or_model_invalid" if not report["valid_model_run"]
            else "PASS" if report["condition_success"] else "FAIL")
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
                absent = base.guest_command(desk, ["bash", "-lc", "test ! -e " + shlex.quote(task.GUEST_PATH) + " && echo reset_clean"])
                reset[binding] = {"success": "reset_clean" in absent,
                    "replacement_guest_id": ep.snapshot().get("guest_container_id")}
            except Exception as exc: reset[binding] = {"success": False, "error": type(exc).__name__ + ": " + str(exc)}
            finally:
                if ep:
                    try: ep.close()
                    except Exception: pass
        report["reset_check"] = reset; report["reset_success"] = bool(reset) and all(v.get("success") for v in reset.values())
        if not report["reset_success"]:
            report["valid_model_run"] = False; report["model_task_outcome"] = "environment_or_model_invalid"
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
        report["wall_seconds"] = round(time.time() - started, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"] = {"run_id": identity.run_id, "source_commit": base.git_source_state(),
            "condition": condition, "mechanism": mechanism,
            "guest_image": os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE"),
            "guest_path": str(base.resolve_guest_image_path()), "resource_ledger": str(ledger)}
        _json(out / "report.json", report)
    return report
def _triplet(parent, mechanism, prefix):
    root = parent / (prefix + "-triplet"); root.mkdir(parents=True, exist_ok=False)
    rows, baseline = [], None
    for condition in ARMS:
        row = _run_arm(root, mechanism, condition, baseline); rows.append(row)
        if condition == "ma_id":
            baseline = row
            if row.get("model_task_outcome") != "PASS" or not row.get("valid_model_run"): break
        elif not row.get("valid_model_run"): break
    arms = [{"run_id": r["run_id"], "condition": r["condition"],
        "outcome": r.get("model_task_outcome"), "valid": r.get("valid_model_run"),
        "success": r.get("condition_success"), "protocol_valid": r.get("protocol_valid"),
        "exposure": r.get("protocol_gate", {}).get("mechanism_exposure"),
        "wall_seconds": r.get("wall_seconds")} for r in rows]
    _json(root / "triplet_result.json", {"mechanism": mechanism, "task_version": old.TASK_VERSION,
        "runtime_profile": "gui-cli-mcp-v2", "model": MODEL, "arms": arms})
    return {"root": str(root), "arms": arms}
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mechanism", choices=["selection", "undo"], required=True)
    p.add_argument("--artifact-parent", type=Path, default=Path("/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs"))
    p.add_argument("--run-prefix", default=None)
    args = p.parse_args()
    if not os.environ.get("SWCUB_SOL_API_KEY"): raise SystemExit("SWCUB_SOL_API_KEY missing; refusing Guest startup")
    if not IMAGE.is_file(): raise SystemExit("pinned Guest image missing; no pull attempted")
    check = subprocess.run(["docker", "image", "inspect", RUNTIME], capture_output=True, text=True, timeout=15)
    if check.returncode: raise SystemExit("pinned local runtime image missing; refusing pull")
    prefix = args.run_prefix or (("s01" if args.mechanism == "selection" else "u01") + "-sol-hybrid-" + time.strftime("%Y%m%d-%H%M%S"))
    result = _triplet(args.artifact_parent.resolve(), args.mechanism, prefix.strip())
    print(json.dumps(result, ensure_ascii=False))
if __name__ == "__main__": main()
