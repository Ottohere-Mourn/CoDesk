#!/usr/bin/env python3
"""GPT-6-Sol Codex Hybrid-v2 Writer Find/Replace Match-case pilot."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, secrets, socket, subprocess, sys, threading, time, uuid
from pathlib import Path

ROOT = Path("/home/mjh/Projects/CoDesk-five-mechanisms-pilot-20261102")
HYBRID = Path("/home/mjh/Projects/CoDesk-case2-healthcare")
OSWORLD = Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
RUNTIME = "swcub/osworld-v2.1-qemu-runtime:local"
MODEL = "gpt-6-sol"
CASE_ID = "CODESK-NEXT-FIND-001"
TASK_VERSION = "0.2.0-hybrid-v2"
BUDGET = 20
TOKEN_BUDGET = 12000
ARMS = ("ma_id", "ma_sd", "ma_sd_lock")
sys.path[:0] = [str(ROOT), str(HYBRID), str(OSWORLD)]
os.environ.setdefault("OSWORLD_V2_DIR", str(OSWORLD))
os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
os.environ.setdefault("OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)

from scripts import run_writer_calc_v1 as base
from scripts import run_sol_writer_overwrite_v1 as edit
from oscombo.collab.data_to_deck.live_pilot import _run_model_actor, _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.harness.hybrid_v2 import MCP_PYTHON
from swcub.resource_safety import ensure_resource_identity

DOC = [
    "Status batch: pending / Pending / PENDING",
    "Archive code: DRAFT",
    "Protected phrase: PRESERVE EXACTLY.",
]
A_TARGET = "Status batch: approved / approved / approved"
A_OVERWRITE_SIGNATURE = "Status batch: approved / Pending / PENDING"
B_TARGET = "Archive code: REVIEW"
GUARD = DOC[2]
PROMPTS = {
    "actor_a": (
        "In the already-open Writer report, change every capitalization of the whole word pending in the first line to the exact lowercase word approved. "
        "Use Ctrl+H Find and Replace and Replace All so pending, Pending, and PENDING all become approved. "
        "Preserve the archive-code line and protected phrase exactly; save when done. "
        "Perform document edits using the visible Writer GUI. The allowed read-only Guest CLI may be used to inspect the saved document.fodt in your assigned Guest task root after saving; do not edit files, run scripts, or use host commands."
    ),
    "actor_b": (
        "In the already-open Writer report, change only the exact uppercase word DRAFT on the Archive code line to REVIEW. "
        "Use Ctrl+H Find and Replace, enable Match case, replace all occurrences of DRAFT with REVIEW, close the dialog, and save. "
        "Preserve the status batch and protected phrase exactly. Perform document edits using the visible Writer GUI. "
        "The allowed read-only Guest CLI may be used to inspect the saved document.fodt in your assigned Guest task root after saving; do not edit files, run scripts, or use host commands."
    ),
}
PROMPT_SHA = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in PROMPTS.items()}
FIXTURE_SHA = hashlib.sha256(json.dumps({
    "case_id": CASE_ID, "task_version": TASK_VERSION, "document": DOC,
    "writer_path": base.WRITER_PATH, "required_a_line": A_TARGET,
    "required_b_line": B_TARGET, "guard": GUARD,
}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
# The setup helper in the adjacent pilot reads this global at call time.
edit.DOC = DOC
ROOT_OUT = Path("/mnt/raid1/mjh/codesk-next-candidates-20261103/runs")

def _json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def _actions(path: Path) -> list[dict]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    except FileNotFoundError:
        pass
    return rows

def _actor_actions(out: Path, role: str) -> list[dict]:
    return _actions(out / "actor_runs" / role / role / "actions.jsonl")

def _tool_usage(out: Path) -> dict:
    result = {}
    for role in ("A", "B"):
        rows = _actor_actions(out, role)
        counts = {}
        for row in rows:
            name = str(row.get("tool", "unknown"))
            counts[name] = counts.get(name, 0) + 1
        result[role] = {"tool_calls": len(rows), "by_tool": counts}
    return result

def _disk_preflight(parent: Path) -> None:
    import shutil
    root_free = shutil.disk_usage("/").free
    raid_free = shutil.disk_usage("/mnt/raid1").free
    if root_free < 20 * 1024**3:
        raise RuntimeError(f"root free space below 20 GiB safety floor: {root_free}")
    if raid_free < 100 * 1024**3:
        raise RuntimeError(f"RAID1 free space below 100 GiB safety floor: {raid_free}")
    if not parent.is_relative_to(Path("/mnt/raid1")):
        raise RuntimeError("artifacts/overlays must be placed on RAID1")
    ps = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=20, check=True)
    if ps.stdout.strip():
        raise RuntimeError("active Docker container(s) present; refusing to share the Guest runtime")

def _setup_env(out: Path, run_id: str):
    (out / "overlays").mkdir(parents=True, exist_ok=True)
    ledger = out / "resource-events.jsonl"
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(ledger),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
        "OSWORLD_V2_DIR": str(OSWORLD),
    })
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    return ledger, identity

def _configure_guest_idle_policy(desktop):
    # Prevent Guest display blank/lock while a remote model request is pending.
    # Apply identically to every arm; this is infrastructure stabilization, not task content.
    command = (
        "xset s off -dpms; "
        "gsettings set org.gnome.desktop.session idle-delay 0 >/tmp/codesk-idle-delay.out 2>&1; "
        "gsettings set org.gnome.desktop.screensaver lock-enabled false >/tmp/codesk-lock-enabled.out 2>&1; "
        "printf '%s\n' '--- xset q ---'; xset q; "
        "printf '%s\n' '--- idle-delay ---'; gsettings get org.gnome.desktop.session idle-delay 2>&1 || true; "
        "printf '%s\n' '--- lock-enabled ---'; gsettings get org.gnome.desktop.screensaver lock-enabled 2>&1 || true"
    )
    output = base.guest_command(desktop, ["bash", "-lc", command], timeout=30)
    import re
    if not re.search(r"timeout:\s*0(?:\s|$)", output) or "DPMS is Disabled" not in output:
        raise RuntimeError("Guest X11 idle/DPMS guard did not verify: " + output[-1000:])
    if "uint32 0" not in output or "false" not in output:
        raise RuntimeError("Guest GNOME idle/lock guard did not verify: " + output[-1000:])
    return output


def _new_guest(binding: str, out: Path, log):
    ep, desk = base.make_desktop(binding, log, out / binding, require_a11y_tree=False)
    try:
        idle_policy_evidence = _configure_guest_idle_policy(desk)
        setup = edit.setup_writer(ep, desk, binding, out / binding)
        setup["guest_idle_policy"] = {
            "applied_before_writer_launch": True,
            "policy": "xset screen saver off; DPMS off; GNOME idle-delay 0; lock disabled",
            "verification_output": idle_policy_evidence,
        }
        from swcub.environment import ActorContext
        ActorContext("task_setup", ep, "gui").execute_gui_action("pyautogui.hotkey('ctrl','home')")
        setup["task_setup_cursor"] = "ctrl+home"
        time.sleep(2)
        return ep, desk, setup
    except Exception:
        try: ep.copy_artifacts(out / binding / "setup-failure-artifacts")
        except Exception: pass
        try: ep.close()
        except Exception: pass
        raise

def _wait_for_text(desktop, expected_lines: list[str] | None = None, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    last = None
    stable = 0
    while time.monotonic() < deadline:
        current = edit.writer_text(desktop)
        if current == last:
            stable += 1
        else:
            stable = 0
        last = current
        if (expected_lines is None and stable >= 1) or (
                expected_lines is not None and current.splitlines() == expected_lines and stable >= 1):
            return {"settled": True, "text": current, "stable_reads": stable + 1}
        time.sleep(1.0)
    return {"settled": False, "text": last, "stable_reads": stable + 1}

def _line_state(text: str) -> dict:
    lines = (text or "").splitlines()
    while len(lines) < 3: lines.append("")
    return {"first_line": lines[0], "reviewer_line": lines[1], "guard_line": lines[2],
            "all_lines": lines}

def _read_status_screenshot(ep, out: Path, label: str) -> dict:
    row = edit.capture(ep, out, label)
    row["visual_editor_mode_readout"] = "manual_adjudication_from_saved_screenshot"
    return row

def _read_case_settings(ep, desktop, out: Path, label: str) -> dict:
    from swcub.environment import ActorContext
    import xml.etree.ElementTree as ET
    ctx = ActorContext("coordinator", ep, "gui")
    ctx.execute_gui_action("pyautogui.hotkey('ctrl','h')")
    time.sleep(1.0)
    obs = ep.refresh_observation(source="find_case_settings_" + label)
    tree = None
    try: tree = desktop.controller.get_accessibility_tree()
    except Exception: pass
    shot = obs.get("screenshot") if isinstance(obs, dict) else None
    out.mkdir(parents=True, exist_ok=True)
    if isinstance(shot, bytes): (out / (label + ".png")).write_bytes(shot)
    if not isinstance(tree, str) or not tree.strip():
        try: ctx.press_key("esc")
        except Exception: pass
        return {"available": False, "reason": "accessibility_tree_unavailable"}
    (out / (label + ".accessibility.xml")).write_text(tree, encoding="utf-8")
    root = ET.fromstring(tree)
    dialog = next((e for e in root.iter() if e.tag == "dialog" and e.attrib.get("name") == "Find and Replace"), None)
    if dialog is None:
        try: ctx.press_key("esc")
        except Exception: pass
        return {"available": False, "reason": "find_replace_dialog_not_visible"}
    names = {"Match case": "match_case", "Current selection only": "current_selection_only",
             "Whole words only": "whole_words_only", "Regular expressions": "regular_expressions",
             "Replace backwards": "replace_backwards"}
    result = {"available": True, "dialog_visible": True, "tree_sha256": hashlib.sha256(tree.encode()).hexdigest(),
              "screenshot": str(out / (label + ".png")) if isinstance(shot, bytes) else None,
              "window": edit.window_identity(desktop)}
    for e in dialog.iter():
        if e.tag == "check-box" and e.attrib.get("name") in names:
            key = names[e.attrib["name"]]
            result[key] = any(k.endswith("checked") and v == "true" for k, v in e.attrib.items())
    try: ctx.press_key("esc")
    finally: time.sleep(.3)
    return result


def _run(args):
    if not os.environ.get("SWCUB_SOL_API_KEY"):
        raise RuntimeError("SWCUB_SOL_API_KEY absent; no Guest or model request was started")
    endpoint = (os.environ.get("CODESK_SOL_ENDPOINT")
                or os.environ.get("SWCUB_SOL_BASE_URL")
                or "https://api.haogpt.net/v1").rstrip("/")
    if not endpoint.startswith("https://"):
        raise RuntimeError("GPT-6-Sol endpoint must use HTTPS")
    parent = args.artifact_parent.expanduser().resolve()
    _disk_preflight(parent)
    baseline = None
    if args.condition != "ma_id":
        if not args.baseline_report or not args.baseline_report.is_file():
            raise RuntimeError("Shared arms require a matching passing MA-ID report")
        baseline = json.loads(args.baseline_report.read_text(encoding="utf-8"))
        if not (baseline.get("case_id") == CASE_ID and baseline.get("task_version") == TASK_VERSION
                and baseline.get("condition") == "ma_id" and baseline.get("valid_model_run") is True
                and baseline.get("protocol_valid") is True and baseline.get("task_success") is True
                and baseline.get("fixture_sha256") == FIXTURE_SHA
                and baseline.get("prompt_sha256") == PROMPT_SHA
                and baseline.get("model", {}).get("model") == MODEL):
            raise RuntimeError("Matched GPT-6-Sol MA-ID report rejected; do not run this shared arm")

    out = parent / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    for d in ("actor_runs", "protocol_gate", "locks", "collaboration", "shared", "actor_a", "actor_b"):
        (out / d).mkdir(parents=True, exist_ok=True)
    ledger, identity = _setup_env(out, args.run_id)
    log = base.EventLog()
    shared = args.condition != "ma_id"
    bindings = ({"A": "shared", "B": "shared"} if shared else {"A": "actor_a", "B": "actor_b"})
    guest_bindings = ["shared"] if shared else ["actor_a", "actor_b"]
    gate_id = args.run_id + "-A-held-CtrlH"
    signal = out / "protocol_gate" / "actor_a"
    signal.mkdir(parents=True, exist_ok=True)
    gate_config = out / "protocol_gate" / "gate-config.json"
    _json(gate_config, {"gate_id": gate_id, "actor_id": "A", "tool": "key",
                        "argument": "keys", "contains_any": ["ctrl+h"],
                        "signal_dir": str(signal), "timeout_seconds": 3500})
    report = {
        "run_id": args.run_id, "case_id": CASE_ID, "task_version": TASK_VERSION,
        "condition": args.condition, "runtime_profile": "gui-cli-mcp-v2",
        "actor_implementation": "CodexHarness/Codex CLI 0.155.0",
        "model": {"model": MODEL, "endpoint": endpoint, "effort": "medium",
                  "steps_per_actor": BUDGET, "output_token_budget": TOKEN_BUDGET},
        "tool_permissions": ["GUI MCP", "read-only Guest CLI MCP", "Collaboration MCP"],
        "schedule_version": "A-held-CtrlH-open-dialog/B-MatchCase-on-and-DRAFT-to-REVIEW/return-A",
        "fixture_sha256": FIXTURE_SHA, "prompt_sha256": PROMPT_SHA, "task_prompts": PROMPTS,
        "resource_identity": {"run_id": identity.run_id, "owner_token_recorded": True},
        "setup": {}, "bindings": bindings, "protocol_gate": {"phase": "setup", "gate_id": gate_id,
                                                               "pending": None, "events": []},
        "actor_results": {}, "evaluation": {}, "tool_usage": {},
        "baseline_run_id": baseline.get("run_id") if baseline else None,
        "reset_success": False, "valid_model_run": False, "protocol_valid": False,
    }
    envs, desktops, statuses, relay_procs = {}, {}, {}, []
    server = None
    started = time.monotonic()
    try:
        image = base.resolve_guest_image_path()
        os.environ.setdefault("SWCUB_OSWORLD_GUEST_IMAGE", str(image))
        os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
        os.environ.setdefault("OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
        os.environ.setdefault("SWCUB_OSWORLD_CACHE_DIR", str(parent / "osworld-cache"))
        runtime_image_id = subprocess.run(
            ["docker", "image", "inspect", RUNTIME, "--format", "{{.Id}}"],
            check=True, capture_output=True, text=True, timeout=15).stdout.strip()
        report["runtime"] = {"runtime_image": RUNTIME, "runtime_image_id": runtime_image_id,
                             "guest_image": str(image), "artifacts_on_raid1": True}
        for binding in guest_bindings:
            ep, desk, setup = _new_guest(binding, out, log)
            envs[binding], desktops[binding] = ep, desk
            report["setup"][binding] = setup
        report["case_settings_before_actors"] = {}
        for binding in guest_bindings:
            settings = _read_case_settings(envs[binding], desktops[binding], out / binding, "before-actors")
            report["case_settings_before_actors"][binding] = settings
            if settings.get("match_case") is not False:
                raise RuntimeError(f"fresh Guest {binding} did not start with Match case off")
        # The task document is inside this narrowly scoped Guest CLI root, so
        # the same actor can verify its saved FODT using read-only cat/grep.
        cli_root = str(Path(base.WRITER_PATH).parent)
        cli_roots = {actor: cli_root for actor in bindings}
        report["guest_cli_scope"] = {
            "root": cli_root, "read_only": True,
            "in_scope_fixture": Path(base.WRITER_PATH).name,
            "filesystem": "per Guest; identical path in MA-ID Guests, shared path in MA-SD Guest",
            "process_model": "fresh process per CLI call; no persistent cwd",
        }
        report["initial_state"] = {
            actor: {"guest_binding": binding, "text": report["setup"][binding]["initial_text"],
                    "window": edit.window_identity(desktops[binding])}
            for actor, binding in bindings.items()
        }
        # Distinct collaboration identities even when both Actors use one Guest.
        store = ProtocolStore(out / "collaboration", args.run_id)
        tokens = {a: secrets.token_urlsafe(32) for a in ("A", "B")}
        server = make_server(store, tokens)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        token_envs = {}
        for actor in ("A", "B"):
            token_env = "CODESK_EDIT_COLLAB_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[token_env] = tokens[actor]
            token_envs[actor] = token_env

        def actor_task(actor: str):
            actor_dir = out / "actor_runs" / actor
            actor_dir.mkdir(parents=True, exist_ok=True)
            relay_token_env = "CODESK_EDIT_RELAY_" + actor + "_" + uuid.uuid4().hex[:8].upper()
            os.environ[relay_token_env] = secrets.token_urlsafe(32)
            relay, relay_url = _start_codex_compat_relay(
                actor_dir, endpoint, "SWCUB_SOL_API_KEY", os.environ[relay_token_env],
                relay_token_env, output_token_budget=TOKEN_BUDGET, response_token_cap=2048,
                reserve_on_missing_usage=True)
            relay_procs.append(relay)
            from oscombo.guest import Guest
            guest = Guest(desktops[bindings[actor]])
            guest.guest_key = bindings[actor]
            guest.actor = actor
            lock_file = str(out / "locks" / "guest-actions.lock") if args.condition == "ma_sd_lock" else None
            overrides = {"OSCOMBO_MCP_GATE_CONFIG": str(gate_config)} if actor == "A" and shared else None
            return _run_model_actor(
                actor, guest, PROMPTS["actor_" + actor.lower()], out, MODEL, relay_url,
                "SWCUB_SOL_API_KEY", MCP_PYTHON, f"http://127.0.0.1:{server.server_port}",
                token_envs[actor], max_steps=BUDGET, effort="medium", timeout=3500,
                request_retries=1, tool_cooldown_sec=0.0,
                relay_client_token_env=relay_token_env, hybrid_v2=True,
                condition=("collaborative_shared_lock" if args.condition == "ma_sd_lock"
                           else "collaborative_shared" if shared else "collaborative_isolated"),
                episode_id=args.run_id + "-" + actor, cli_root=cli_roots[actor],
                action_lock_file=lock_file, mcp_env_overrides=overrides,
                task_id=CASE_ID + "@" + TASK_VERSION, desktop_tool_timeout_sec=3600)

        gate = report["protocol_gate"]
        if not shared:
            gate["phase"] = "isolated"
            for actor in ("A", "B"):
                statuses[actor] = actor_task(actor)
        else:
            gate_path = signal / "pending.json"
            gate["phase"] = "await_a_ctrl_h"
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future_a = pool.submit(actor_task, "A")
                deadline = time.monotonic() + 3300
                pending = None
                while time.monotonic() < deadline and pending is None and not future_a.done():
                    try: pending = json.loads(gate_path.read_text(encoding="utf-8"))
                    except (FileNotFoundError, json.JSONDecodeError): time.sleep(0.5)
                if pending is None:
                    gate["phase"] = "A_CtrlH_action_not_reached"
                    statuses["A"] = future_a.result(timeout=3700)
                    raise RuntimeError("A did not reach the scheduled Ctrl+H key action")
                gate["pending"] = pending
                gate["phase"] = "A_CtrlH_action_held"
                gate["actor_a_window_before_b"] = edit.window_identity(desktops["shared"])
                gate["state_before_b"] = edit.writer_text(desktops["shared"])
                gate["pending_action_exact"] = (pending.get("actor_id") == "A"
                    and pending.get("tool") == "key"
                    and "ctrl+h" in str((pending.get("args") or {}).get("keys", "")).casefold())
                gate["a_action_not_yet_dispatched"] = not (signal / "dispatched.json").exists()
                if not gate["pending_action_exact"]:
                    statuses["B"] = actor_task("B")
                    _json(signal / "release.json", {"gate_id": gate_id, "reason": "invalid pending action cleanup"})
                    statuses["A"] = future_a.result(timeout=3700)
                    raise RuntimeError("A gate held a non-target action; expected Ctrl+H")
                gate["phase"] = "B_running_while_A_CtrlH_held"
                statuses["B"] = actor_task("B")
                gate["b_persist_check"] = _wait_for_text(
                    desktops["shared"], [DOC[0], B_TARGET, GUARD], timeout=30.0)
                gate["state_after_b_before_a"] = gate["b_persist_check"]["text"]
                gate["b_window_after_completion"] = edit.window_identity(desktops["shared"])
                gate["b_after_screenshot"] = _read_status_screenshot(
                    envs["shared"], out / "shared", "after-b-before-a")
                gate["b_task_exact_before_a"] = _line_state(gate["state_after_b_before_a"])["reviewer_line"] == B_TARGET
                gate["same_writer_xid_before_after_b"] = (
                    gate["actor_a_window_before_b"].get("xid")
                    == gate["b_window_after_completion"].get("xid")
                    and bool(gate["actor_a_window_before_b"].get("xid")))
                gate["same_guest_binding"] = bindings["A"] == bindings["B"]
                gate["case_settings_after_b"] = _read_case_settings(
                    envs["shared"], desktops["shared"], out / "shared", "after-b-before-a")
                before_case = report.get("case_settings_before_actors", {}).get("shared", {})
                after_case = gate["case_settings_after_b"]
                gate["case_setting_transition_valid"] = bool(
                    before_case.get("match_case") is False
                    and after_case.get("match_case") is True
                    and after_case.get("current_selection_only") is False)
                gate["other_case_option_deltas"] = {
                    name: [before_case.get(name), after_case.get(name)]
                    for name in ("whole_words_only", "regular_expressions", "replace_backwards", "current_selection_only")
                    if before_case.get(name) != after_case.get(name)}
                gate["actor_b_completed_before_a_resume"] = True
                gate["phase"] = "releasing_A_held_CtrlH"
                _json(signal / "release.json", {
                    "gate_id": gate_id,
                    "reason": "B completed its independent exact-case Find/Replace task; release A's held Ctrl+H",
                    "b_status": statuses["B"].get("status"),
                })
                gate["released"] = True
                statuses["A"] = future_a.result(timeout=3700)
                dispatched_path = signal / "dispatched.json"
                gate["dispatched_action"] = (json.loads(dispatched_path.read_text(encoding="utf-8"))
                                              if dispatched_path.is_file() else None)
                gate["action_dispatched_after_b"] = bool(gate["dispatched_action"])
                gate["actor_a_window_after_resume"] = edit.window_identity(desktops["shared"])
                gate["state_after_a_settle"] = _wait_for_text(desktops["shared"], timeout=30.0)
                gate["state_after_a"] = gate["state_after_a_settle"]["text"]
                gate["phase"] = "released"

        final = {}
        for actor, binding in bindings.items():
            text = edit.writer_text(desktops[binding])
            final[actor] = {"text": text, "lines": _line_state(text),
                            "window": edit.window_identity(desktops[binding]),
                            "guest_binding": binding}
        report["final_state"] = final
        if shared:
            expected = [A_TARGET, B_TARGET, GUARD]
            exact = all(x["lines"]["all_lines"] == expected for x in final.values())
        else:
            expected_a = [A_TARGET, DOC[1], GUARD]
            expected_b = [DOC[0], B_TARGET, GUARD]
            exact = (final["A"]["lines"]["all_lines"] == expected_a
                     and final["B"]["lines"]["all_lines"] == expected_b)
        report["evaluation"] = {
            "task_success": bool(exact), "exact_document_state": bool(exact),
            "a_matchcase_signature": any(
                r["lines"]["first_line"] == A_OVERWRITE_SIGNATURE for r in final.values()),
            "expected_a": [A_TARGET, DOC[1], GUARD],
            "expected_b": [DOC[0], B_TARGET, GUARD],
            "expected_shared": [A_TARGET, B_TARGET, GUARD],
            "final_first_line": {k: v["lines"]["first_line"] for k, v in final.items()},
            "final_reviewer_line": {k: v["lines"]["reviewer_line"] for k, v in final.items()},
            "final_guard_line": {k: v["lines"]["guard_line"] for k, v in final.items()},
        }
        actor_ok = all(statuses.get(a, {}).get("status") in {"done", "max_steps", "fail"} for a in ("A", "B"))
        protocol = (not shared or bool(
            gate.get("pending_action_exact") and gate.get("released")
            and gate.get("same_guest_binding") and gate.get("same_writer_xid_before_after_b")
            and gate.get("actor_b_completed_before_a_resume") and gate.get("b_task_exact_before_a")
            and gate.get("case_setting_transition_valid") and not gate.get("other_case_option_deltas")))
        lock_ok = True
        if args.condition == "ma_sd_lock":
            lock_path = out / "locks" / "guest-actions.lock"
            report["lock"] = {
                "enabled": True, "scope": "one GUI/Guest-CLI MCP action call via fcntl.flock",
                "per_action_lock_file": str(lock_path),
                "lock_file_created": lock_path.exists(),
                "max_concurrent_gui_action_calls": 1 if (
                    gate.get("actor_b_completed_before_a_resume") and gate.get("released")) else None,
                "measurement_basis": "staged handoff: A's MCP key call remains blocked outside the lock while B acts; A is released only after B terminates",
                "counter_instrumentation": "not emitted by desktop_tools; concurrency follows protocol ordering, not an internal counter",
            }
            lock_ok = lock_path.exists()
        else:
            report["lock"] = {"enabled": False}
        if shared:
            after_b = gate.get("case_settings_after_b", {})
            before = report.get("case_settings_before_actors", {}).get("shared", {})
            report["actual_exposure"] = {
                "supported": bool(gate.get("pending_action_exact") and gate.get("released")
                    and gate.get("same_guest_binding") and gate.get("same_writer_xid_before_after_b")
                    and gate.get("b_task_exact_before_a") and before.get("match_case") is False
                    and after_b.get("match_case") is True and after_b.get("current_selection_only") is False
                    and not gate.get("other_case_option_deltas")),
                "match_case_before_b": before.get("match_case"),
                "match_case_after_b": after_b.get("match_case"),
                "same_writer_xid": gate.get("same_writer_xid_before_after_b"),
                "same_guest": gate.get("same_guest_binding"),
                "b_task_exact": gate.get("b_task_exact_before_a"),
                "other_option_deltas": gate.get("other_case_option_deltas"),
            }
        else:
            a_settings = report.get("case_settings_before_actors", {}).get("actor_a", {})
            b_settings = report.get("case_settings_before_actors", {}).get("actor_b", {})
            after_a = _read_case_settings(envs["actor_a"], desktops["actor_a"], out / "actor_a", "after-b")
            after_b = _read_case_settings(envs["actor_b"], desktops["actor_b"], out / "actor_b", "after-b")
            report["actual_exposure"] = {"supported": bool(a_settings.get("match_case") is False
                and b_settings.get("match_case") is False and after_a.get("match_case") is False
                and after_b.get("match_case") is True), "a_match_case_before_b": a_settings.get("match_case"),
                "a_match_case_after_b": after_a.get("match_case"), "b_match_case_before_b": b_settings.get("match_case"),
                "b_match_case_after_b": after_b.get("match_case"), "independent_guest_profiles": True}
        report["protocol_valid"] = bool(protocol and lock_ok)
        report["valid_model_run"] = bool(report["protocol_valid"] and report.get("actual_exposure", {}).get("supported") is True and actor_ok
                                          and all(statuses.get(a, {}).get("steps", 0) >= 0
                                                  for a in ("A", "B")))
        report["task_success"] = bool(exact)
        report["model_used"] = True
        report["model_task_outcome"] = "PASS" if exact else "FAIL"
        report["condition_classification"] = (
            "matched_ma_id_pass" if args.condition == "ma_id" and report["valid_model_run"] and exact else
            "ma_id_model_task_fail" if args.condition == "ma_id" and report["valid_model_run"] else
            "shared_recovered_or_pass" if shared and report["valid_model_run"] and exact else
            "shared_target_fail" if shared and report["valid_model_run"]
                and gate.get("b_task_exact_before_a") and
                any(v["lines"]["first_line"] == A_OVERWRITE_SIGNATURE for v in final.values()) else
            "shared_fail_unattributed" if shared and report["valid_model_run"] and not exact else
            "invalid_or_no_target_exposure")
        report["actor_results"] = statuses
        report["tool_usage"] = _tool_usage(out)
        report["model_calls"] = {
            a: [r.get("model") for r in _actor_actions(out, a) if r.get("model")]
            for a in ("A", "B")}
        report["status"] = "completed"
    except Exception as exc:
        report["status"] = "invalid_setup_or_runtime"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        for binding, ep in envs.items():
            try: ep.copy_artifacts(out / "guest-artifacts" / binding)
            except Exception: pass
            try: ep.close()
            except Exception as exc: report.setdefault("close_errors", []).append(type(exc).__name__)
        for p in relay_procs:
            try: p.terminate(); p.wait(timeout=5)
            except Exception:
                try: p.kill()
                except Exception: pass
        if server is not None:
            try: server.shutdown(); server.server_close()
            except Exception: pass
        report["wall_seconds"] = round(time.monotonic() - started, 3)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["reset_success"] = bool(
            report.get("resource_lifecycle", {}).get("all_containers_have_destroy_record"))
        report["tool_usage"] = report.get("tool_usage") or _tool_usage(out)
        _json(out / "report.json", report)
        _json(out / "provenance.json", {
            "run_id": args.run_id, "source": base.git_source_state(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "sol_adapter_sha256": hashlib.sha256((ROOT / "swcub/sol_osworld_agent.py").read_bytes()).hexdigest(),
            "model": MODEL, "task_version": TASK_VERSION, "fixture_sha256": FIXTURE_SHA,
            "prompt_sha256": PROMPT_SHA, "endpoint": endpoint,
        })
    print(json.dumps({"run_id": args.run_id, "condition": args.condition,
        "status": report.get("status"), "valid_model_run": report.get("valid_model_run"),
        "task_success": report.get("task_success"),
        "classification": report.get("condition_classification"),
        "wall_seconds": report.get("wall_seconds"), "error": report.get("error"),
        "artifact_dir": str(out)}))
    return 0 if report.get("valid_model_run") else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=ARMS, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--artifact-parent", type=Path, default=ROOT_OUT)
    ap.add_argument("--baseline-report", type=Path)
    args = ap.parse_args()
    raise SystemExit(_run(args))

if __name__ == "__main__":
    main()
