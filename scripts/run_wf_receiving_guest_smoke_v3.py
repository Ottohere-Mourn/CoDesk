#!/usr/bin/env python3
"""No-model Guest GUI smoke for the composite warehouse workflow fixture."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
from PIL import Image, ImageStat
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path("/home/mjh/Projects/CoDesk-candidate-repair-20261104")
HYBRID = Path("/home/mjh/Projects/CoDesk-case2-healthcare")
OSWORLD = Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
IMAGE = Path("/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2")
RUNTIME = "swcub/osworld-v2.1-qemu-runtime:local"
ARTIFACTS = Path("/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/wf-receiving-v027-context-smoke")
sys.path[:0] = [str(ROOT), str(HYBRID), str(OSWORLD)]
os.environ.setdefault("OSWORLD_V2_DIR", str(OSWORLD))
os.environ.setdefault("SWCUB_OSWORLD_GUEST_IMAGE", str(IMAGE))
os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)
os.environ.setdefault("OSWORLD_DOCKER_RUNTIME_IMAGE", RUNTIME)

from scripts import run_writer_calc_v1 as base
from scripts.wf_composite_receiving_v2 import (
    APP_SERVER, ASN_LOT, EXPECTED, FIXTURE_SHA256, PORT, QA_DISPOSITION,
    RECEIPT_LEDGER, SERVER_PATH, STATE_PATH, evaluate_state,
)
from swcub.resource_safety import ensure_resource_identity


def preflight() -> None:
    if shutil.disk_usage("/").free < 20 * 1024**3:
        raise RuntimeError("root free space below 20 GiB safety floor")
    if shutil.disk_usage("/mnt/raid1").free < 100 * 1024**3:
        raise RuntimeError("RAID1 free space below 100 GiB safety floor")
    mem_kib = int(next(x.split()[1] for x in Path("/proc/meminfo").read_text().splitlines()
                       if x.startswith("MemAvailable:")))
    if mem_kib * 1024 < 20 * 1024**3:
        raise RuntimeError("MemAvailable below 20 GiB safety floor")
    active = subprocess.run(["docker", "ps", "-q"], capture_output=True,
                            text=True, timeout=20, check=True).stdout.strip()
    if active:
        raise RuntimeError("active Docker container(s); refusing to start Guest")
    if not IMAGE.is_file():
        raise RuntimeError("pinned Guest image missing: " + str(IMAGE))
    image = subprocess.run(["docker", "image", "inspect", RUNTIME],
                           capture_output=True, text=True, timeout=20)
    if image.returncode:
        raise RuntimeError("pinned Docker runtime is not local; will not pull/build")


def _scripted_controls(ep, desk, out: Path) -> dict:
    """No-model control through ActorContext GUI plus a Guest-seeded clipboard.

    Shell execution is intentionally limited to Guest clipboard seeding and fixture
    state inspection. All keyboard/mouse operations use the same OSWorld GUI path
    available to an actor; xdotool through the Guest CLI is not a GUI control.
    """
    from swcub.environment import ActorContext

    gui = ActorContext("scripted_control", ep, "gui")

    def guest(command: str) -> str:
        return base.guest_command(desk, ["bash", "-lc", command], timeout=30)

    def clip(text: str) -> None:
        payload = "/tmp/codesk-smoke-clipboard-" + hashlib.sha256(text.encode()).hexdigest()[:10] + ".txt"
        command = ("printf %s " + shlex.quote(text) + " > " + shlex.quote(payload)
                   + "; nohup xclip -selection clipboard -i " + shlex.quote(payload)
                   + " >/dev/null 2>&1 </dev/null & sleep .2; "
                   + "test \"$(timeout 2 xclip -selection clipboard -o -t UTF8_STRING)\" = " + shlex.quote(text))
        guest(command)

    def tab(key: int) -> None:
        gui.press_key(f"ctrl+{key}")
        time.sleep(1.0)

    def paste_at(x: int, y: int) -> None:
        gui.click(x, y)
        gui.press_key("ctrl+v")
        time.sleep(.35)

    def copy_asn_lot() -> None:
        tab(2)
        gui.click(735, 410)
        gui.press_key("ctrl+a")
        gui.press_key("ctrl+c")
        time.sleep(.25)

    def copy_qa_disposition() -> None:
        tab(3)
        gui.click(740, 365)
        gui.press_key("ctrl+a")
        gui.press_key("ctrl+c")
        time.sleep(.25)

    def reset_and_reload() -> None:
        guest(f"curl --noproxy '*' -fsS -X POST http://127.0.0.1:{PORT}/api/reset")
        for index in (1,2,3):
            tab(index); gui.press_key("ctrl+r"); time.sleep(1)

    def state() -> dict:
        return json.loads(guest(f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}/api/state"))

    def save_receiving(enter_held: bool) -> None:
        tab(1)
        clip(RECEIPT_LEDGER); paste_at(1000, 525)
        time.sleep(.8)
        if enter_held:
            copy_asn_lot(); tab(1); paste_at(1000, 752)
            gui.click(560, 790)

    def save_qa() -> None:
        copy_qa_disposition(); paste_at(1000, 500)
        gui.click(520, 600)

    # MA-ID UI-only positive control: complete both independent business artefacts exactly.
    reset_and_reload()
    save_receiving(enter_held=True)
    save_qa()
    positive = state()
    positive_eval = evaluate_state(positive)

    # Shared interleaving control: A saves the receipt ledger, then B overwrites the
    # copied ASN lot before A pastes into Held lot reference.
    reset_and_reload()
    tab(1); clip(RECEIPT_LEDGER); paste_at(1000, 525); time.sleep(.8)
    copy_asn_lot()
    copy_qa_disposition(); paste_at(1000, 500)
    gui.click(520, 600)
    tab(1); paste_at(1000, 752); gui.click(560, 790)
    shared = state()
    shared_eval = evaluate_state(shared)
    pasted = next((x for x in shared.get("observations", [])
                   if x.get("kind") == "paste" and x.get("route") == "/case/receiving"
                   and x.get("target_id") == "held-lot-ref"), None)
    failed_only_at_target = bool(
        pasted and pasted.get("payload_text") == QA_DISPOSITION
        and shared.get("held_lot_ref") == QA_DISPOSITION
        and shared.get("receipt_ledger") == EXPECTED["receipt_ledger"]
        and shared.get("qa_disposition") == EXPECTED["qa_disposition"]
        and shared.get("documents") == {
            "po": "PO-2407; AX-14=24; BN-07=18; CR-22=12; DT-31=6",
            "asn": "ASN-2407; AX-14 received 24 LOT-A14; BN-07 received 18 LOT-B07; "
                   "CR-22 received 11 LOT-C22; DT-31 received 6 LOT-D31",
            "qa_bulletin": "QA notice QA-19; LOT-B07; 3 cartons; storage band 2-8 C; "
                           "standard disposition: " + QA_DISPOSITION})
    shared_paste = {"target": pasted.get("target_id") if pasted else None,
                    "payload_sha256": hashlib.sha256(pasted.get("payload_text", "").encode()).hexdigest()
                        if pasted else None,
                    "payload_matches_B_QA_phrase": bool(pasted and pasted.get("payload_text") == QA_DISPOSITION),
                    "unaffected_receipt_ledger_exact": shared.get("receipt_ledger") == EXPECTED["receipt_ledger"],
                    "unaffected_qa_exact": shared.get("qa_disposition") == EXPECTED["qa_disposition"],
                    "isolated_target_failure": failed_only_at_target}

    # Sham/order control: A commits the copied lot before B changes the clipboard.
    reset_and_reload()
    save_receiving(enter_held=True)
    save_qa()
    sham = state()
    sham_eval = evaluate_state(sham)

    return {
        "model_called": False,
        "control_semantics": "deterministic Guest GUI test via ActorContext; ledger payload is Guest-seeded, ASN and QA payloads are copied from visible source tabs; not an agent run or formal arm",
        "ma_id_ui_positive": {"condition_success": positive_eval["condition_success"],
                              "receipt_totals": positive_eval["receipt_totals"]},
        "shared_interleaving": {"condition_success": shared_eval["condition_success"],
                                "actor_goal_success": shared_eval["actor_goal_success"],
                                "clipboard_paste": shared_paste,
                                "expected_oracle_failure_confirmed": failed_only_at_target},
        "sham_copy_after_commit": {"condition_success": sham_eval["condition_success"],
                                   "receipt_totals": sham_eval["receipt_totals"]},
        "all_controls_expected": bool(positive_eval["condition_success"]
            and failed_only_at_target and not shared_eval["condition_success"]
            and sham_eval["condition_success"]),
    }

def _single_paste_diagnostic(ep, desk, out: Path) -> dict:
    """Test real shared clipboard with separate ActorContext instances, no LLM."""
    from swcub.environment import ActorContext

    def guest(command: str) -> str:
        return base.guest_command(desk, ["bash", "-lc", command], timeout=30)

    actor_a = ActorContext("actor_A_context_probe", ep, "gui")
    actor_b = ActorContext("actor_B_context_probe", ep, "gui")
    actor_a.press_key("ctrl+2")
    time.sleep(.7)
    actor_a.click(735, 410)
    actor_a.press_key("ctrl+a")
    actor_a.press_key("ctrl+c")
    time.sleep(.25)
    lot_readback = guest("timeout 2 xclip -selection clipboard -o -t UTF8_STRING")
    actor_a.press_key("ctrl+1")
    time.sleep(.4)
    actor_a.click(1000, 752)

    # A distinct actor context copies the QA phrase after A's source copy.
    # B also pastes/saves QA, matching the real shared-workflow action sequence.
    actor_b.press_key("ctrl+3")
    time.sleep(.7)
    actor_b.click(740, 365)
    actor_b.press_key("ctrl+a")
    actor_b.press_key("ctrl+c")
    time.sleep(.25)
    qa_readback = guest("timeout 2 xclip -selection clipboard -o -t UTF8_STRING")
    actor_b.click(1000, 500)
    actor_b.press_key("ctrl+v")
    actor_b.click(520, 600)

    # Mirror the hybrid runner's exact context restoration sequence, including
    # CLI-driven tab selection, repeated observation refreshes, then a GUI focus click.
    coordinator = ActorContext("coordinator_restore_focus_probe", ep, "gui")
    nav = "xdotool key --clearmodifiers ctrl+1; sleep 1"
    ep.cli_action("coordinator_context_probe", "bash -lc " + shlex.quote(nav))
    activation = {}
    for attempt in range(1, 9):
        observation = ep.refresh_observation(source=f"exact_runner_restore_{attempt}")
        current_state = json.loads(guest(f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}/api/state"))
        active_route = next((x.get("route") for x in reversed(current_state.get("observations", []))
            if x.get("visible") is True and x.get("kind") in {"visibility-change", "window-focus", "page-load"}), None)
        active_title = guest('wid=$(xdotool getactivewindow 2>/dev/null || true); xdotool getwindowname "$wid" 2>/dev/null || true').strip()
        activation = {"attempt": attempt, "active_route": active_route, "active_title": active_title,
                      "screenshot_bytes": len(observation.get("screenshot", b"")) if isinstance(observation, dict) else 0}
        if active_route == "/case/receiving" and "Warehouse Receiving - PO-2407" in active_title:
            break
        time.sleep(.75)
    coordinator.click(1000, 840)
    time.sleep(.25)
    restored_clipboard = guest("timeout 2 xclip -selection clipboard -o -t UTF8_STRING")
    prepaste_state = json.loads(guest(f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}/api/state"))
    restored_focus = next((x for x in reversed(prepaste_state.get("observations", []))
        if x.get("kind") == "focus" and x.get("route") == "/case/receiving"
        and x.get("visible") is True), None)
    actor_a.press_key("ctrl+v")
    observation = ep.refresh_observation(source="separate_actor_contexts_after_paste")
    screenshot = observation.get("screenshot") if isinstance(observation, dict) else None
    screenshot_path = out / "diagnostic-after-paste.png"
    if isinstance(screenshot, bytes) and screenshot:
        screenshot_path.write_bytes(screenshot)
    actor_a.click(560, 790)

    final = json.loads(guest(f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}/api/state"))
    observed = [x for x in final.get("observations", [])
                if x.get("kind") == "paste" and x.get("route") == "/case/receiving"
                and x.get("target_id") == "held-lot-ref"]
    paste = observed[-1] if observed else None
    payload_text = QA_DISPOSITION
    return {
        "control_semantics": "no-model Guest GUI diagnostic with two separate ActorContext instances sharing one Guest; not an agent trial or arm",
        "actor_a_lot_clipboard_readback_exact_before_b": lot_readback.strip() == ASN_LOT,
        "actor_b_qa_clipboard_readback_exact": qa_readback.strip() == QA_DISPOSITION,
        "clipboard_readback_after_b_is_qa": qa_readback.strip() == payload_text,
        "clipboard_still_qa_after_coordinator_restore": restored_clipboard.strip() == QA_DISPOSITION,
        "coordinator_restored_receiving_and_held_field_focus": bool(
            restored_focus and restored_focus.get("active_id") == "held-lot-ref"),
        "coordinator_activation": activation,
        "observed_target_paste": bool(paste),
        "paste_target": paste.get("target_id") if paste else None,
        "paste_payload_matches_expected": bool(paste and paste.get("payload_text") == payload_text),
        "saved_held_lot_ref_matches": final.get("held_lot_ref") == payload_text,
        "expected": payload_text,
        "screenshot": screenshot_path.name if screenshot_path.is_file() else None,
        "observed_paste_event": paste,
        "diagnostic_pass": bool(lot_readback.strip() == ASN_LOT
            and qa_readback.strip() == payload_text
            and restored_clipboard.strip() == payload_text
            and restored_focus and restored_focus.get("active_id") == "held-lot-ref" and paste
            and paste.get("payload_text") == payload_text
            and final.get("held_lot_ref") == payload_text),
    }



def _mcp_gate_diagnostic(ep, desk, out: Path) -> dict:
    """No-model replay through the exact desktop MCP executor and scheduled-call gate."""
    import requests
    from oscombo.harness.hybrid_v2 import MCP_PYTHON, MCP_SITE

    guest_url = os.environ.get("OSCOMBO_GUEST_URL", "http://localhost:5000").rstrip("/")
    # Use the same guest URL as CodexHarness; the test is invalid if the MCP-facing
    # HTTP endpoint is not the OSWorld Guest associated with this DesktopEnv.
    shot_probe = requests.get(guest_url + "/screenshot", timeout=10)
    shot_probe.raise_for_status()

    def state() -> dict:
        return json.loads(base.guest_command(
            desk, ["curl", "--noproxy", "*", "-fsS", f"http://127.0.0.1:{PORT}/api/state"]))

    def mcp_call(actor: str, name: str, args: dict, timeout: int = 180) -> dict:
        actor_dir = out / ("mcp_actor_" + actor)
        actor_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({
            "OSCOMBO_GUEST_URL": guest_url,
            "OSCOMBO_ACTION_LOG": str(actor_dir / "actions.jsonl"),
            "OSCOMBO_MAX_STEPS": "45",
            "OSCOMBO_MCP_SETTLE": "0.15",
            "OSCOMBO_ACTOR_ID": "actor_" + actor,
            "OSCOMBO_EPISODE_ID": "mcp-parity-" + actor,
            "OSCOMBO_GUEST_KEY": "mcp-parity-shared-guest",
            "OSCOMBO_CONDITION": "no_model_mcp_parity",
            "PYTHONPATH": os.pathsep.join([MCP_SITE, str(HYBRID), str(ROOT), env.get("PYTHONPATH", "")]),
        })
        cp = subprocess.run(
            [MCP_PYTHON, "-m", "oscombo.desktop_tools", name, json.dumps(args)],
            env=env, capture_output=True, text=True, timeout=timeout, check=False)
        if cp.returncode:
            raise RuntimeError(f"desktop MCP executor exited {cp.returncode}: {cp.stderr[-1000:]}")
        try:
            result = json.loads(cp.stdout)
        except Exception as exc:
            raise RuntimeError(f"desktop MCP executor returned invalid JSON: {cp.stdout[-1000:]}") from exc
        if result.get("error"):
            raise RuntimeError(f"desktop MCP {actor}.{name} failed: {result['error']}")
        return {"actor": actor, "tool": name, "args": args,
                "text": result.get("text"), "has_image": bool(result.get("image"))}

    # Initialize the two isolated MCP per-Actor state stores and establish their
    # screenshot-to-coordinate scale, exactly as each model client must do.
    mcp_call("A", "screenshot", {})
    mcp_call("B", "screenshot", {})

    # Actor A copies the lot from the visible ASN tab, then focuses the held-lot
    # field. Its exact Ctrl+V tool call is issued and held at the same pre-lock gate
    # used by the hybrid runner while B acts.
    trace = []
    trace.append(mcp_call("A", "key", {"keys": "ctrl+2"}))
    trace.append(mcp_call("A", "click", {"x": 490, "y": 273}))
    trace.append(mcp_call("A", "key", {"keys": "ctrl+a ctrl+c"}))
    trace.append(mcp_call("A", "key", {"keys": "ctrl+1"}))
    trace.append(mcp_call("A", "click", {"x": 667, "y": 501}))
    before_b = state()
    signal = out / "mcp-paste-gate"
    signal.mkdir(parents=True, exist_ok=True)
    gate_cfg = out / "mcp-paste-gate-config.json"
    gate_cfg.write_text(json.dumps({
        "gate_id": "no-model-mcp-parity-A-paste",
        "actor_id": "actor_A",
        "tool": "key",
        "argument": "keys",
        "contains": "ctrl+v",
        "timeout_seconds": 300,
        "signal_dir": str(signal),
    }, indent=2) + "\n", encoding="utf-8")

    actor_a_dir = out / "mcp_actor_A"
    env_a = os.environ.copy()
    env_a.update({
        "OSCOMBO_GUEST_URL": guest_url,
        "OSCOMBO_ACTION_LOG": str(actor_a_dir / "actions.jsonl"),
        "OSCOMBO_MAX_STEPS": "45",
        "OSCOMBO_MCP_SETTLE": "0.15",
        "OSCOMBO_ACTOR_ID": "actor_A",
        "OSCOMBO_EPISODE_ID": "mcp-parity-A",
        "OSCOMBO_GUEST_KEY": "mcp-parity-shared-guest",
        "OSCOMBO_CONDITION": "no_model_mcp_parity",
        "OSCOMBO_MCP_GATE_CONFIG": str(gate_cfg),
        "PYTHONPATH": os.pathsep.join([MCP_SITE, str(HYBRID), str(ROOT), env_a.get("PYTHONPATH", "")]),
    })
    pending_tool = subprocess.Popen(
        [MCP_PYTHON, "-m", "oscombo.desktop_tools", "key",
         json.dumps({"keys": "ctrl+v"})],
        env=env_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pending_deadline = time.monotonic() + 20
    while time.monotonic() < pending_deadline and not (signal / "pending.json").exists():
        if pending_tool.poll() is not None:
            raise RuntimeError("scheduled MCP paste exited before reaching its gate")
        time.sleep(0.1)
    if not (signal / "pending.json").exists():
        pending_tool.kill()
        raise RuntimeError("scheduled MCP paste did not reach its pending gate")

    # B independently reads QA-19, copies the disposition, and saves its own QA
    # result while A's issued Paste tool call is pending.
    trace.append(mcp_call("B", "key", {"keys": "ctrl+3"}))
    trace.append(mcp_call("B", "click", {"x": 493, "y": 243}))
    trace.append(mcp_call("B", "key", {"keys": "ctrl+a ctrl+c"}))
    trace.append(mcp_call("B", "click", {"x": 667, "y": 333}))
    trace.append(mcp_call("B", "key", {"keys": "ctrl+v"}))
    trace.append(mcp_call("B", "click", {"x": 347, "y": 400}))
    after_b = state()
    qa_clip = base.guest_command(
        desk, ["bash", "-lc", "timeout 2 xclip -selection clipboard -o -t UTF8_STRING"])
    # Restore A through the same production Guest-facing MCP executor rather than
    # the OSWorld ActorContext path. This isolates the question whether the
    # coordinator adapter, versus the pending MCP action itself, suppresses paste.
    coordinator_trace = []
    coordinator_trace.append(mcp_call("C", "key", {"keys": "ctrl+1"}))
    coordinator_trace.append(mcp_call("C", "click", {"x": 667, "y": 501}))
    time.sleep(.25)
    restored_focus_state = state()
    route = next((x.get("route") for x in reversed(restored_focus_state.get("observations", []))
                  if x.get("visible") is True
                  and x.get("kind") in {"visibility-change", "window-focus", "page-load"}), None)
    title = base.guest_command(
        desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                              'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
    activation = {"restore_executor": "desktop_tools MCP",
                  "active_route": route, "active_title": title}
    focus = next((x for x in reversed(restored_focus_state.get("observations", []))
                  if x.get("kind") == "focus" and x.get("route") == "/case/receiving"
                  and x.get("visible") is True), None)
    clip_after_restore = base.guest_command(
        desk, ["bash", "-lc", "timeout 2 xclip -selection clipboard -o -t UTF8_STRING"])
    release = signal / "release.json"
    release.write_text(json.dumps({"gate_id": "no-model-mcp-parity-A-paste",
                                   "release_reason": "coordinator_restore_complete"}) + "\n",
                       encoding="utf-8")
    out_text, out_err = pending_tool.communicate(timeout=120)
    pending_response = json.loads(out_text)
    if pending_response.get("error"):
        raise RuntimeError("released MCP paste failed: " + pending_response["error"])
    time.sleep(.5)
    final = state()
    paste_events = [x for x in final.get("observations", [])
                    if x.get("kind") == "paste" and x.get("route") == "/case/receiving"
                    and x.get("target_id") == "held-lot-ref"]
    paste = paste_events[-1] if paste_events else None
    passed = bool(
        paste and paste.get("payload_text") == QA_DISPOSITION
        and focus and focus.get("target_id") == "held-lot-ref"
        and qa_clip.strip() == QA_DISPOSITION
        and clip_after_restore.strip() == QA_DISPOSITION
        and after_b.get("qa_disposition") == QA_DISPOSITION)
    return {
        "model_called": False,
        "control_semantics": "no-model exact desktop MCP executor replay with A's Ctrl+V held at the production scheduled-action gate; B uses a second per-Actor MCP state/log; coordinator restoration is tested through a third MCP client",
        "guest_api_url": guest_url,
        "guest_api_screenshot_http_status": shot_probe.status_code,
        "mcp_actor_a_and_b_state_separate": (out / "mcp_actor_A" / "tool_state.json").exists()
                                               and (out / "mcp_actor_B" / "tool_state.json").exists(),
        "trace": trace,
        "coordinator_mcp_trace": coordinator_trace,
        "clipboard_a_before_b": before_b.get("held_lot_ref"),
        "clipboard_b_after_save_exact": after_b.get("qa_disposition") == QA_DISPOSITION,
        "clipboard_b_readback": qa_clip.strip(),
        "clipboard_after_coordinator_restore": clip_after_restore.strip(),
        "coordinator_activation": activation,
        "coordinator_focus_target": focus.get("target_id") if focus else None,
        "held_action_pending": (signal / "pending.json").exists(),
        "held_action_dispatch": json.loads((signal / "dispatched.json").read_text())
                                if (signal / "dispatched.json").exists() else None,
        "pending_mcp_result": pending_response.get("text"),
        "pending_mcp_image_suppressed_by_gate": pending_response.get("image") is None,
        "observed_paste_event": paste,
        "paste_event_count": len(paste_events),
        "saved_held_lot_ref": final.get("held_lot_ref"),
        "final_qa_disposition": final.get("qa_disposition"),
        "diagnostic_pass": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic-only", action="store_true",
                        help="run one clipboard-GUI paste diagnostic instead of all controls")
    parser.add_argument("--visual-only", action="store_true",
                        help="verify three visible task tabs, then reset without scripted controls")
    parser.add_argument("--mcp-gate-diagnostic", action="store_true",
                        help="replay the exact desktop MCP executor with a held A Paste call while B acts")
    args = parser.parse_args()
    preflight()
    run_id = "wf-receiving-guest-smoke-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = ARTIFACTS / run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "overlays").mkdir()
    ledger = out / "resource-events.jsonl"
    os.environ.update({"SWCUB_RUN_ID": run_id, "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
                       "SWCUB_RESOURCE_LEDGER": str(ledger),
                       "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(out / "overlays"),
                       "OSWORLD_V2_DIR": str(OSWORLD)})
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    identity = ensure_resource_identity(ledger)
    log = base.EventLog()
    ep = desk = None
    report = {"run_id": run_id, "model_called": False, "guest_app": "loopback_only",
              "fixture_sha256": FIXTURE_SHA256, "runtime_image": RUNTIME,
              "status": "starting", "expected": EXPECTED}
    started = time.monotonic()
    try:
        ep, desk = base.make_desktop("receiving-smoke", log, out / "shared",
                                     require_a11y_tree=False)
        encoded = base64.b64encode(APP_SERVER.encode("utf-8")).decode("ascii")
        pycode = ("from pathlib import Path; import base64; "
                  f"p=Path({SERVER_PATH!r}); p.parent.mkdir(parents=True,exist_ok=True); "
                  f"p.write_bytes(base64.b64decode({encoded!r})); p.chmod(0o700)")
        ep.cli_action("fixture_setup", "python3 -c " + shlex.quote(pycode))
        start = ("nohup /usr/bin/python3 " + shlex.quote(SERVER_PATH)
                 + " --state " + shlex.quote(STATE_PATH) + " --port " + str(PORT)
                 + " >/tmp/codesk-warehouse-receiving.log 2>&1 </dev/null & "
                 + "echo $! >/tmp/codesk-warehouse-receiving.pid")
        ep.cli_action("fixture_setup", "bash -lc " + shlex.quote(start))
        health = ""
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                health = base.guest_command(
                    desk, ["curl", "--noproxy", "*", "-fsS", "--max-time", "2",
                           f"http://127.0.0.1:{PORT}/health"], timeout=5)
                if '"ok": true' in health or '"ok":true' in health:
                    break
            except Exception:
                time.sleep(.25)
        if '"ok"' not in health:
            raise RuntimeError("Guest app failed health: " + health[:300])
        binary = base.guest_command(desk, ["bash", "-lc",
            "command -v chromium || command -v chromium-browser || command -v google-chrome || echo NONE"]).strip().splitlines()[-1]
        if binary == "NONE":
            raise RuntimeError("Chromium not available in pinned Guest")
        task_urls=[f"http://127.0.0.1:{PORT}"+route for route in
                   ("/case/receiving","/case/asn","/case/qa")]
        launch = ("nohup " + shlex.quote(binary)
                  + " --no-sandbox --start-maximized --no-first-run --no-default-browser-check"
                  + " --disable-dev-shm-usage --disable-gpu --disable-extensions --disable-background-networking --no-proxy-server --remote-debugging-port=9222"
                  + " --user-data-dir=/tmp/codesk-warehouse-receiving-v027/profile --new-window "
                  + " ".join(shlex.quote(url) for url in task_urls)
                  + " >/tmp/codesk-warehouse-receiving-browser.log 2>&1 </dev/null & "
                  + "echo $! >/tmp/codesk-warehouse-receiving-browser.pid")
        ep.cli_action("fixture_setup", "bash -lc " + shlex.quote(launch))
        ep.cli_action("fixture_setup", "bash -lc " + shlex.quote("sleep 1; xdotool key --clearmodifiers ctrl+1; sleep .5"))
        from swcub.environment import ActorContext
        readiness_gui = ActorContext("fixture_readiness", ep, "gui")
        shot = None
        title = ""
        loaded_routes = set()
        debug = {}
        for attempt in range(1, 81):
            observation = ep.refresh_observation(source="receiving_fixture_ready")
            shot = observation.get("screenshot") if isinstance(observation, dict) else None
            title = base.guest_command(
                desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                     'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
            current = json.loads(base.guest_command(
                desk, ["curl", "--noproxy", "*", "-fsS", f"http://127.0.0.1:{PORT}/api/state"]))
            loaded_routes = {x.get("route") for x in current.get("observations", [])
                             if x.get("kind") == "page-load"}
            if (isinstance(shot, bytes) and shot and "Warehouse Receiving" in title
                    and "/case/receiving" in loaded_routes):
                break
            # Some Guest resets leave Chrome's first tab at Untitled even though
            # the loopback app is healthy. Reissue the route through GUI, not CDP/DOM.
            if attempt in {8, 24, 48}:
                readiness_gui.press_key("ctrl+l")
                readiness_gui.type_text(f"http://127.0.0.1:{PORT}/case/receiving")
                readiness_gui.press_key("enter")
                time.sleep(1.5)
            time.sleep(.5)
        if not isinstance(shot, bytes) or not shot or "Warehouse Receiving" not in title:
            def tail_guest(path):
                try:
                    return base.guest_command(desk, ["bash", "-lc", "tail -30 " + shlex.quote(path)],
                                              timeout=10)[-5000:]
                except Exception as exc:
                    return f"{type(exc).__name__}: {exc}"
            debug = {
                "health": tail_guest(f"/tmp/codesk-warehouse-receiving.log"),
                "browser_log": tail_guest("/tmp/codesk-warehouse-receiving-browser.log"),
                "browser_pid": tail_guest("cat /tmp/codesk-warehouse-receiving-browser.pid; ps -fp $(cat /tmp/codesk-warehouse-receiving-browser.pid)"),
                "chrome_targets": tail_guest("curl --noproxy '*' -fsS --max-time 3 http://127.0.0.1:9222/json/list"),
                "http_title": tail_guest(f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}/case/receiving | grep -o '<title>[^<]*</title>'"),
            }
            report["fixture_readiness_debug"] = debug
            raise RuntimeError(f"visible fixture readiness failed; title={title!r}; routes={sorted(loaded_routes)}; diagnostics={json.dumps(debug,ensure_ascii=False)[:2000]}")
        active_route = lambda state: next((x.get("route") for x in reversed(state.get("observations", []))
            if x.get("visible") is True and x.get("kind") in {"visibility-change", "window-focus", "page-load"}), None)
        def frame_audit(raw):
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            w, h = im.size
            page = im.crop((int(w*.08), int(h*.08), int(w*.96), int(h*.93))).resize((96, 54))
            colors = len(set(page.getdata()))
            stddev = max(ImageStat.Stat(page).stddev)
            return {"size": list(im.size), "page_crop_colors": colors,
                    "page_crop_max_stddev": round(stddev, 3),
                    "content_ready": colors >= 32 and stddev > 5}
        # Chrome sometimes creates the requested tabs but leaves the second
        # and third tab at Untitled. Repair them through visible GUI navigation
        # before testing separate ActorContext clipboard behavior.
        from swcub.environment import ActorContext
        tab_gui = ActorContext("visible_tab_initializer", ep, "gui")
        for key, route, marker in (("1", "/case/receiving", "Warehouse Receiving - PO-2407"),
                                   ("2", "/case/asn", "ASN Details - ASN-2407"),
                                   ("3", "/case/qa", "Quality Disposition - QA-19")):
            tab_gui.press_key("ctrl+" + key)
            time.sleep(.6)
            active_title = base.guest_command(
                desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                       'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
            if marker not in active_title:
                tab_gui.press_key("ctrl+l")
                tab_gui.type_text(f"http://127.0.0.1:{PORT}{route}")
                tab_gui.press_key("enter")
                for _ in range(12):
                    time.sleep(.5)
                    active_title = base.guest_command(
                        desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                               'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
                    if marker in active_title:
                        break
            if marker not in active_title:
                raise RuntimeError(f"visible tab initialization failed for {route}: {active_title!r}")
        tab_trace = []
        initial_route_screenshot_sha = hashlib.sha256(shot).hexdigest()
        for key, expected_route, label in (("1", "/case/receiving", "receiving"),
                                           ("2", "/case/asn", "asn"),
                                           ("3", "/case/qa", "qa")):
            from swcub.environment import ActorContext
            nav_gui = ActorContext("route_navigation_probe", ep, "gui")
            nav_gui.press_key("ctrl+"+key)
            time.sleep(1.0)
            tab_obs = ep.refresh_observation(source="receiving_tab_activation_" + key)
            tab_shot = tab_obs.get("screenshot") if isinstance(tab_obs, dict) else None
            state_now = json.loads(base.guest_command(
                desk, ["curl", "--noproxy", "*", "-fsS", f"http://127.0.0.1:{PORT}/api/state"]))
            actual_route = active_route(state_now)
            active_title = base.guest_command(
                desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                     'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
            title_marker = {"/case/receiving":"Warehouse Receiving - PO-2407",
                            "/case/asn":"ASN Details - ASN-2407",
                            "/case/qa":"Quality Disposition - QA-19"}[expected_route]
            shot_sha = hashlib.sha256(tab_shot).hexdigest() if isinstance(tab_shot, bytes) and tab_shot else None
            audit = frame_audit(tab_shot) if isinstance(tab_shot, bytes) and tab_shot else {"content_ready": False}
            visual_changed = expected_route == "/case/receiving" or shot_sha != initial_route_screenshot_sha
            row = {"navigation": expected_route, "expected_route": expected_route,
                   "active_route": actual_route, "active_window_title": active_title,
                   "expected_title_marker": title_marker, "screenshot_sha256": shot_sha,
                   "visual_changed_from_initial_route": visual_changed, "screenshot": audit}
            tab_trace.append(row)
            if (actual_route != expected_route or title_marker not in active_title
                    or not audit.get("content_ready") or not visual_changed):
                raise RuntimeError("three-tab visual activation mismatch: " + json.dumps(tab_trace))
            (out / f"browser-{label}.png").write_bytes(tab_shot)
        from swcub.environment import ActorContext
        nav_gui=ActorContext("route_navigation_probe",ep,"gui")
        nav_gui.press_key("ctrl+1")
        time.sleep(1.0)
        shot = ep.refresh_observation(source="receiving_fixture_visible_final").get("screenshot")
        title = base.guest_command(
            desk, ["bash", "-lc", 'wid=$(xdotool getactivewindow 2>/dev/null || true); '
                   'xdotool getwindowname "$wid" 2>/dev/null || true']).strip()
        if not isinstance(shot, bytes) or not shot or "Warehouse Receiving" not in title:
            raise RuntimeError(f"visible fixture readiness failed; title={title!r}; screenshot={bool(shot)}")
        (out / "browser-ready.png").write_bytes(shot)
        page = base.guest_command(desk, ["curl", "--noproxy", "*", "-fsS",
                                        f"http://127.0.0.1:{PORT}/case/receiving"])
        if "PO-2407" not in page or "held-lot-ref" not in page or "ASN-2407" not in page:
            raise RuntimeError("receiving page missed expected business content")
        state = json.loads(base.guest_command(desk, ["cat", STATE_PATH]))
        if args.visual_only:
            report.update({"status":"visual_smoke_pass","attempts":attempt,
                           "active_window_title":title,"loaded_routes":sorted(loaded_routes),
                           "tab_activation_trace":tab_trace,"screenshot_sha256":hashlib.sha256(shot).hexdigest(),
                           "screenshot_bytes":len(shot),"health":health,
                           "initial_state_oracle":evaluate_state(state),"browser":binary,
                           "page_bytes":len(page.encode())})
        elif args.mcp_gate_diagnostic:
            diagnostic = _mcp_gate_diagnostic(ep, desk, out)
            report.update({"status": "mcp_gate_diagnostic_pass" if diagnostic["diagnostic_pass"] else "mcp_gate_diagnostic_failed",
                           "attempts": attempt, "tab_activation_trace": tab_trace,
                           "mcp_gate_diagnostic": diagnostic,
                           "screenshot_sha256": hashlib.sha256(shot).hexdigest(),
                           "screenshot_bytes": len(shot), "health": health,
                           "initial_state_oracle": evaluate_state(state),
                           "browser": binary, "page_bytes": len(page.encode())})
        elif args.diagnostic_only:
            diagnostic = _single_paste_diagnostic(ep, desk, out)
            report.update({"status": "diagnostic_pass" if diagnostic["diagnostic_pass"] else "diagnostic_failed",
                           "attempts": attempt, "tab_activation_trace": tab_trace,
                           "paste_diagnostic": diagnostic,
                           "screenshot_sha256": hashlib.sha256(shot).hexdigest(),
                           "screenshot_bytes": len(shot), "health": health,
                           "initial_state_oracle": evaluate_state(state),
                           "browser": binary, "page_bytes": len(page.encode())})
        else:
            scripted = _scripted_controls(ep, desk, out)
            if not scripted["all_controls_expected"]:
                raise RuntimeError("scripted Guest GUI controls did not match expected outcomes: "
                                   + json.dumps(scripted, ensure_ascii=False))
            report.update({"status": "smoke_pass", "attempts": attempt,
                           "active_window_title": title, "loaded_routes": sorted(loaded_routes),
                           "tab_activation_trace": tab_trace, "scripted_controls": scripted,
                           "screenshot_sha256": hashlib.sha256(shot).hexdigest(),
                           "screenshot_bytes": len(shot), "health": health,
                           "initial_state_oracle": evaluate_state(state),
                           "browser": binary, "page_bytes": len(page.encode())})
    except Exception as exc:
        report["status"] = "smoke_invalid"
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if ep is not None:
            try:
                ep.copy_artifacts(out / "guest-artifacts")
            except Exception as exc:
                report["artifact_error"] = str(exc)
            try:
                ep.close()
            except Exception as exc:
                report["close_error"] = str(exc)
        try:
            log.write(out / "events.jsonl")
        except Exception as exc:
            report["event_log_error"] = str(exc)
        report["wall_seconds"] = round(time.monotonic() - started, 2)
        report["resource_lifecycle"] = base.verify_ledger(ledger) if ledger.exists() else None
        report["provenance"] = {"resource_run_id": identity.run_id,
                                "source_commit": base.git_source_state(),
                                "fixture_sha256": FIXTURE_SHA256,
                                "guest_image": str(IMAGE)}
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
        (out / "provenance.json").write_text(json.dumps(report["provenance"], indent=2,
                                                       ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "out": str(out), "status": report["status"],
                      "wall_seconds": report["wall_seconds"],
                      "resource_lifecycle": report["resource_lifecycle"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
