#!/usr/bin/env python3
"""GPT-6-Sol / Codex Hybrid-v2 retest of the frozen C-03 Clipboard case."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, secrets, shlex, socket, subprocess, sys, threading, time, uuid
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
from scripts import run_workflows_qwen_v1 as old
from swcub.resource_safety import ensure_resource_identity
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
from oscombo.harness.hybrid_v2 import MCP_PYTHON

TASK = "C-03"
MODEL = "gpt-6-sol"
BUDGET = 20
TOKEN_BUDGET = 12000
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")
PROMPTS = old.PROMPTS[TASK]

def _json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def _setup_env(out, run_id):
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    ledger = out / "resource-events.jsonl"
    os.environ.update({
        "SWCUB_RUN_ID": run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
        "OSWORLD_V2_DIR": str(OSWORLD),
    })
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    return ledger, identity

def _prepare(actor, ep, desktop, workflow, binding, out, label=None):
    role = "actor_" + actor.lower()
    app = workflow.actor_application(role).lower()
    if label == "before_stale_dispatch":
        app = workflow.actor_application("actor_a").lower()
    path = workflow.writer_path if app == "writer" else workflow.calc_path
    if label == "before_actor_b":
        cmd = (
            "set -e; wid=$(xdotool search --onlyvisible --name " + shlex.quote(Path(path).name)
            + " 2>/dev/null | tail -n1); test -n \"$wid\"; "
            "xdotool windowmap \"$wid\"; xdotool windowactivate --sync \"$wid\"; "
            "xdotool windowraise \"$wid\"; "
            "xdotool mousemove --sync 650 293 click 1; "
            "xdotool key --clearmodifiers ctrl+Home; "
            "xdotool keydown Shift; xdotool key End; xdotool keyup Shift; sleep .5"
        )
        ep.cli_action("coordinator", "bash -lc " + shlex.quote(cmd))
    elif label == "before_stale_dispatch":
        cmd = (
            "set -e; wid=$(xdotool search --onlyvisible --name " + shlex.quote(Path(path).name)
            + " 2>/dev/null | tail -n1); test -n \"$wid\"; "
            "xdotool windowmap \"$wid\"; xdotool windowactivate --sync \"$wid\"; "
            "xdotool windowraise \"$wid\"; "
            "xdotool mousemove --sync 100 400 click 1; sleep .3; "
            "xdotool key --clearmodifiers ctrl+Home; "
            "xdotool key Down; xdotool key Down; xdotool key Down; sleep .5"
        )
        ep.cli_action("coordinator", "bash -lc " + shlex.quote(cmd))
    title = old._guest_active_window_title(desktop)
    obs = ep.refresh_observation(source="hybrid_v2_role_context")
    shot = obs.get("screenshot") if isinstance(obs, dict) else None
    state = core._read_state(desktop, workflow)
    expected_state = workflow.state_for(("actor_b",)) if label == "before_stale_dispatch" else workflow.state_for(())
    if (not base._document_title_matches(title, app, path)
            or state != expected_state or not isinstance(shot, bytes)):
        raise RuntimeError("role context setup failed: " + json.dumps({
            "actor": actor, "binding": binding, "title": title,
            "expected_state_matches": state == expected_state,
            "expected_state": expected_state, "actual_state": state,
            "screenshot": isinstance(shot, bytes)}))
    dest = out / binding / ("role-" + actor + ("-" + label if label else "") + ".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(shot)
    return {"actor": actor, "binding": binding, "active_window": title,
            "target_app": app, "expected_state_matches": True, "label": label,
            "screenshot": str(dest)}

def _new_guest(binding, out, log, workflow, apps):
    ep, desk = base.make_desktop(binding, log, out / binding, require_a11y_tree=False)
    try:
        from swcub.clipboard_observer import GuestCommandClipboardSampler, install_guest_probe
        probe, state_path = install_guest_probe(
            lambda argv, d=desk: base.guest_command(d, argv),
            ROOT / "scripts/guest_clipboard_probe.py", out.name + "-" + binding)
        sampler = GuestCommandClipboardSampler(
            lambda argv, d=desk: base.guest_command(d, argv),
            probe_path=probe, state_path=state_path)
        ep.attach_clipboard_sampler(sampler, required=True)
        ep.clipboard_sampler.sample()
        setup = old._setup_model_desktop(ep, desk, out / binding, workflow, apps)
        return ep, desk, setup
    except Exception:
        try: ep.copy_artifacts(out / binding / "setup-failure-artifacts")
        except Exception: pass
        try: ep.close()
        except Exception: pass
        raise

def _run_arm(parent: Path, condition: str, baseline: dict | None):
    run_id = "c03-sol-hybrid-" + condition + "-" + uuid.uuid4().hex[:8]
    out = parent / run_id
    out.mkdir(parents=True, exist_ok=False)
    for b in ("actor_a", "actor_b", "shared", "protocol_gate"):
        (out / b).mkdir(parents=True, exist_ok=True)
    ledger, identity = _setup_env(out, run_id)
    log = base.EventLog()
    workflow = core.get_workflow(TASK)
    is_shared = condition != "ma_id"
    gate = {"enabled": is_shared, "gate_id": run_id + "-A-held-paste",
            "phase": "not_started", "trigger": "A key ctrl+v stale paste",
            "pending": None, "released": False}
    (out / "locks").mkdir(exist_ok=True)
    gate_signal = out / "protocol_gate" / "actor_a"
    gate_signal.mkdir(parents=True, exist_ok=True)
    gate_config = out / "protocol_gate" / "gate-config.json"
    _json(gate_config, {"gate_id": gate["gate_id"], "actor_id": "A",
        "tool": "key", "argument": "keys", "contains": "ctrl+v",
        "signal_dir": str(gate_signal), "timeout_seconds": 3500})
    envs, desktops, bindings, setups = {}, {}, {}, {}
    relay_procs = []
    server = None
    statuses = {}
    start = time.time()
    report = {"run_id": run_id, "task_id": workflow.template_id,
        "task_version": workflow.version, "template": TASK, "condition": condition,
        "runtime_profile": "gui-cli-mcp-v2", "actor_implementation": "CodexHarness/Codex CLI 0.155.0",
        "model": MODEL, "endpoint": os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
        "budget_per_actor": BUDGET, "per_actor_output_budget": TOKEN_BUDGET,
        "tool_permissions": ["GUI MCP", "read-only Guest CLI MCP", "Collaboration MCP"],
        "schedule_version": "C-03-v0.3.0-clipboard-copy-yield-stale-paste",
        "fixture_manifest": workflow.manifest(), "baseline_required_for_shared": True,
        "baseline_accepted": False, "setup": setups, "bindings": bindings,
        "role_context_handoffs": [], "protocol_gate": gate, "actors": {},
        "evaluation": {}, "reset_success": False, "valid_model_run": False}
    try:
        if is_shared:
            if not baseline or baseline.get("model_task_outcome") != "PASS" or not baseline.get("valid_model_run"):
                raise RuntimeError("matched passing MA-ID control missing; Shared is gated off")
            report["baseline_accepted"] = True
            report["baseline_run_id"] = baseline["run_id"]
        app_a = workflow.actor_application("actor_a").lower()
        app_b = workflow.actor_application("actor_b").lower()
        plan = ([("shared", [app_b, app_a], ["A", "B"])] if is_shared else
                [("actor_a", [app_a], ["A"]), ("actor_b", [app_b], ["B"])])
        for binding, apps, actors in plan:
            ep, desk, setup = _new_guest(binding, out, log, workflow, apps)
            envs[binding], desktops[binding], setups[binding] = ep, desk, setup
            for actor in actors:
                bindings[actor] = binding
        initial_context_actors = ("A",) if is_shared else ("A", "B")
        for actor in initial_context_actors:
            detail = _prepare(actor, envs[bindings[actor]], desktops[bindings[actor]],
                              workflow, bindings[actor], out, "initial")
            report["role_context_handoffs"].append(detail)
        store = ProtocolStore(out / "collaboration", run_id)
        tokens = {a: secrets.token_urlsafe(32) for a in ("A", "B")}
        server = make_server(store, tokens)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        token_envs = {}
        for actor in ("A", "B"):
            token_env = "CODESK_F01_COLLAB_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[token_env] = tokens[actor]
            token_envs[actor] = token_env
        def actor_task(actor):
            actor_root = out / "actor_runs" / actor
            actor_root.mkdir(parents=True, exist_ok=True)
            token_env = "CODESK_F01_RELAY_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[token_env] = secrets.token_urlsafe(32)
            relay, relay_url = _start_codex_compat_relay(
                actor_root, os.environ.get("CODESK_SOL_ENDPOINT", "https://api.haogpt.net/v1"),
                "SWCUB_SOL_API_KEY", os.environ[token_env], token_env,
                output_token_budget=TOKEN_BUDGET, response_token_cap=2048,
                reserve_on_missing_usage=True)
            relay_procs.append(relay)
            overrides = {"OSCOMBO_MCP_GATE_CONFIG": str(gate_config)} if actor == "A" and is_shared else None
            lock_file = str(out / "locks" / "guest-actions.lock") if condition == "ma_sd_lock" else None
            from oscombo.guest import Guest
            guest_ref = Guest(desktops[bindings[actor]])
            guest_ref.guest_key = bindings[actor]
            guest_ref.actor = actor
            prompt = PROMPTS["actor_" + actor.lower()]
            if actor == "A" and condition == "ma_id":
                prompt = (
                    "LibreOffice Calc is active and the complete source range A1:B2 is selected. "
                    "Copy it. This is your isolated desktop, so there is no partner handoff: press "
                    "Ctrl+Home, then Down three times to select A4; press Ctrl+V and save with Ctrl+S. "
                    "Preserve the source, guard cells, and every other cell. Do not switch applications."
                )
            return _run_model_actor(
                actor, guest_ref, prompt,
                out, MODEL, relay_url, "SWCUB_SOL_API_KEY", MCP_PYTHON,
                f"http://127.0.0.1:{server.server_port}", token_envs[actor],
                max_steps=BUDGET, effort="medium", timeout=3500, request_retries=1,
                tool_cooldown_sec=0.0, relay_client_token_env=token_env,
                hybrid_v2=True, condition="collaborative_shared_lock" if condition == "ma_sd_lock"
                    else "collaborative_shared" if is_shared else "collaborative_isolated",
                episode_id=run_id + "-" + actor, cli_root="/tmp/codesk_workflows",
                action_lock_file=lock_file, mcp_env_overrides=overrides,
                task_id=workflow.template_id + "@" + workflow.version,
                desktop_tool_timeout_sec=3600)
        report["clipboard_samples"] = {}
        if not is_shared:
            for actor in ("A", "B"):
                statuses[actor] = actor_task(actor)
                binding = bindings[actor]
                report["clipboard_samples"]["after_actor_" + actor.lower()] = (
                    envs[binding].clipboard_sampler.sample())
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fa = pool.submit(actor_task, "A")
                deadline = time.monotonic() + 3300
                copy_action_path = out / "actor_runs" / "A" / "A" / "actions.jsonl"
                copy_row = None
                while time.monotonic() < deadline and copy_row is None and not fa.done():
                    try:
                        for line in copy_action_path.read_text(encoding="utf-8").splitlines():
                            row = json.loads(line)
                            if (row.get("tool") == "key"
                                    and "ctrl+c" in str(row.get("args", {}).get("keys", "")).casefold()):
                                copy_row = row
                                break
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
                    if copy_row is None:
                        time.sleep(.5)
                if copy_row is None:
                    gate["phase"] = "source_copy_not_reached_before_A_exit"
                    gate["source_copy_seen"] = False
                    statuses["A"] = fa.result(timeout=3700)
                else:
                    gate["phase"] = "A_source_copied_waiting_for_handoff"
                    gate["source_copy_seen"] = True
                    gate["source_copy_action"] = {"n": copy_row.get("n"), "tool": copy_row.get("tool"),
                        "args": copy_row.get("args"), "window_before": copy_row.get("window_before")}
                    report["clipboard_samples"]["after_actor_a_copy"] = (
                        envs[bindings["A"]].clipboard_sampler.sample())
                detail = _prepare("B", envs[bindings["B"]], desktops[bindings["B"]],
                                  workflow, bindings["B"], out, "before_actor_b")
                report["role_context_handoffs"].append(detail)
                statuses["B"] = actor_task("B")
                b_pre_resume = workflow.evaluate(
                    lambda path, d=desktops[bindings["B"]]: base.guest_command(d, ["cat", path]),
                    ("actor_b",))
                gate["actor_b_pre_resume_success"] = bool(
                    b_pre_resume["actor_goal_success"].get("actor_b"))
                report["evaluation"]["actor_b_pre_resume"] = b_pre_resume
                report["clipboard_samples"]["after_actor_b"] = (
                    envs[bindings["A"]].clipboard_sampler.sample())
                clipboard_a = report["clipboard_samples"].get("after_actor_a_copy", {})
                clipboard_b = report["clipboard_samples"].get("after_actor_b", {})
                gate["clipboard_payload_changed_by_intervening_actor"] = bool(
                    clipboard_a.get("payload_sha256")
                    and clipboard_b.get("payload_sha256")
                    and clipboard_a.get("payload_sha256") != clipboard_b.get("payload_sha256"))
                detail = _prepare("B", envs[bindings["B"]], desktops[bindings["B"]],
                                  workflow, bindings["B"], out, "before_stale_dispatch")
                report["role_context_handoffs"].append(detail)
                report["clipboard_samples"]["before_stale_paste"] = (
                    envs[bindings["A"]].clipboard_sampler.sample())
                coordination_message = store.send(
                    "S", "A",
                    "Actor B has completed and the coordination pause is over. Resume the pending paste task now.",
                    [])
                gate["coordination_message"] = coordination_message
                pending_path = gate_signal / "pending.json"
                paste_deadline = time.monotonic() + 300
                while time.monotonic() < paste_deadline and not pending_path.is_file() and not fa.done():
                    time.sleep(.5)
                if pending_path.is_file():
                    gate["pending"] = json.loads(pending_path.read_text(encoding="utf-8"))
                    gate["phase"] = "A_stale_paste_pending"
                    _json(gate_signal / "release.json", {"gate_id": gate["gate_id"],
                        "reason": "B completed and A4 is selected; release A's held stale paste",
                        "actor_b_status": statuses["B"].get("status"),
                        "coordination_message_id": coordination_message.get("message_id")})
                    gate["released"] = True
                    gate["phase"] = "A_dispatched"
                else:
                    gate["phase"] = "paste_not_reached_after_coordination_message"
                statuses["A"] = fa.result(timeout=3700)
                report["clipboard_samples"]["after_actor_a_resume"] = (
                    envs[bindings["A"]].clipboard_sampler.sample())
        report["actors"] = statuses
        pending = gate.get("pending")
        if not isinstance(pending, dict):
            pending = {}
        report["protocol_valid"] = (not is_shared or (
            gate.get("source_copy_seen") is True
            and gate.get("coordination_message", {}).get("recipient") == "A"
            and pending.get("actor_id") == "A"
            and pending.get("tool") == "key"
            and "ctrl+v" in str(pending.get("args", {}).get("keys", "")).casefold()
            and gate.get("released") is True
            and statuses.get("B", {}).get("status") in {"done", "max_steps", "fail"}
            and statuses.get("A", {}).get("status") in {"done", "max_steps", "fail"}))
        for binding, ep in envs.items():
            desk = desktops[binding]
            roles = tuple("actor_" + actor.lower() for actor, b in bindings.items() if b == binding)
            result = workflow.evaluate(lambda path, d=desk: base.guest_command(d, ["cat", path]), roles)
            report["evaluation"][binding] = result
        report["clipboard_observer_health"] = {
            binding: ep.clipboard_observer_health for binding, ep in envs.items()
        }
        report["actor_goal_success"] = {
            actor: report["evaluation"][bindings[actor]]["actor_goal_success"]["actor_" + actor.lower()]
            for actor in ("A", "B")}
        report["condition_success"] = all(x["success"] for x in report["evaluation"].values())
        bad_status = [v.get("status") for v in statuses.values()
                      if v.get("status") in {"error", "timeout"}]
        report["valid_model_run"] = (not bad_status and bool(statuses)
            and all(v.get("status") in {"done", "max_steps", "fail"} for v in statuses.values())
            and (not is_shared or report["protocol_valid"]))
        report["model_task_outcome"] = ("environment_or_model_invalid" if not report["valid_model_run"]
            else "PASS" if report["condition_success"] else "FAIL")
        for actor, binding in bindings.items():
            guest = desktops[binding]
            for path in workflow.files():
                content = base.guest_command(guest, ["cat", path])
                dest = out / binding / "final" / Path(path).name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
        report["status"] = "completed"
    except Exception as exc:
        report["status"] = "invalid_infrastructure_or_protocol"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["model_task_outcome"] = "environment_or_model_invalid"
        report["valid_model_run"] = False
    finally:
        for binding, ep in list(envs.items()):
            try:
                ep.copy_artifacts(out / "guest-artifacts" / binding)
            except Exception as exc:
                report.setdefault("artifact_errors", []).append(str(exc))
            try:
                ep.close()
            except Exception as exc:
                report.setdefault("close_errors", []).append(str(exc))
        reset_rows = {}
        reset_bindings = sorted(set(bindings.values()))
        for binding in reset_bindings:
            reset_ep = None
            try:
                reset_dir = out / "reset" / binding
                reset_dir.mkdir(parents=True, exist_ok=True)
                reset_ep, reset_desk = base.make_desktop(
                    binding + "_reset", log, reset_dir, require_a11y_tree=False)
                absent = base.guest_command(reset_desk, [
                    "bash", "-lc", "test ! -e " + shlex.quote(workflow.writer_path)
                    + " && test ! -e " + shlex.quote(workflow.calc_path)
                    + " && echo reset_clean"])
                reset_rows[binding] = {
                    "success": "reset_clean" in absent,
                    "replacement_guest_id": reset_ep.snapshot().get("guest_container_id")}
            except Exception as exc:
                reset_rows[binding] = {"success": False,
                    "error": type(exc).__name__ + ": " + str(exc)}
            finally:
                if reset_ep is not None:
                    try: reset_ep.close()
                    except Exception: pass
        report["reset_check"] = reset_rows
        report["reset_success"] = bool(reset_bindings) and all(
            x.get("success") for x in reset_rows.values())
        if not report["reset_success"]:
            report["valid_model_run"] = False
            report["model_task_outcome"] = "environment_or_model_invalid"
            report["status"] = "invalid_environment_reset"
        envs.clear()
        try:
            if server:
                server.shutdown()
                server.server_close()
        except Exception:
            pass
        for proc in relay_procs:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try: proc.kill()
                except Exception: pass
        try:
            log.write(out / "events.jsonl")
        except Exception:
            pass
        report["wall_seconds"] = round(time.time() - start, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"] = {"run_id": identity.run_id, "source_commit": base.git_source_state(),
            "workflow_fixture_sha256": workflow.fixture_digest(), "condition": condition,
            "guest_image": os.environ.get("SWCUB_OSWORLD_GUEST_IMAGE"),
            "guest_path": str(base.resolve_guest_image_path()), "resource_ledger": str(ledger)}
        _json(out / "report.json", report)
        _json(out / "provenance.json", report["provenance"])
    return report

def _reset_check(parent: Path, result: dict):
    # Each episode is closed by run_arm; a fresh run-owned Guest verifies task files do not persist.
    # Reset check is recorded separately because it creates a new auditable container lifecycle.
    return

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-parent", type=Path,
        default=Path("/mnt/raid1/mjh/Projects/codesk-five-mechanisms-pilot-20261102/runs"))
    parser.add_argument("--run-prefix", default="c03-sol-hybrid-" + time.strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    if not os.environ.get("SWCUB_SOL_API_KEY"):
        raise SystemExit("SWCUB_SOL_API_KEY is required; refusing to boot Guest without model credentials")
    if not IMAGE.is_file():
        raise SystemExit("pinned Guest image missing; refusing any Docker image pull: " + str(IMAGE))
    inspected = subprocess.run(["docker", "image", "inspect", RUNTIME],
                               capture_output=True, text=True, timeout=15)
    if inspected.returncode != 0:
        raise SystemExit("pinned QEMU runtime image is not local; refusing any image pull: " + RUNTIME)
    parent = args.artifact_parent
    parent.mkdir(parents=True, exist_ok=True)
    run_prefix = args.run_prefix.strip()
    if not run_prefix:
        raise SystemExit("--run-prefix must not be empty")
    root = parent / (run_prefix + "-triplet")
    root.mkdir(parents=True, exist_ok=False)
    reports = []
    baseline = None
    for condition in ARMS:
        report = _run_arm(root, condition, baseline)
        reports.append(report)
        if condition == "ma_id":
            baseline = report
            if report.get("model_task_outcome") != "PASS" or not report.get("valid_model_run"):
                break
        elif not report.get("valid_model_run"):
            break
    _json(root / "triplet_result.json", {"task": TASK, "task_version": "0.3.0",
        "runtime_profile": "gui-cli-mcp-v2", "model": MODEL,
        "arms": [{"run_id": r["run_id"], "condition": r["condition"],
                  "outcome": r.get("model_task_outcome"), "valid": r.get("valid_model_run"),
                  "success": r.get("condition_success"), "protocol_valid": r.get("protocol_valid")}
                 for r in reports]})
    print(json.dumps({"root": str(root), "arms": json.loads((root / "triplet_result.json").read_text())["arms"]},
                     ensure_ascii=False))
if __name__ == "__main__":
    main()
