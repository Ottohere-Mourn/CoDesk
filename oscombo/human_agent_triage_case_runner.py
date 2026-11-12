"""Pilot runner for one real Codex GUI Agent plus one fixed, human-like GUI Actor.

HA-TRIAGE reuses the OSWorld Guest, Codex MCP harness, Case Desk source fixture,
User handoff fixture, event logging and cleanup from the Human-Agent PoC. The
Agent reads actual ticket/order/policy pages, then submits a short triage brief.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .eventlog import EventLog
from .guest import Guest, InfraError
from .human_actor import GUIAction, ScriptedGUIActor
from .human_poc import FocusMonitor
from .human_apps.triage_brief import create_fixture as create_triage_fixture
from .human_apps.triage_brief import evaluate as evaluate_triage
from .human_apps.triage_brief import make_server as make_triage_server
from .human_apps.handoff_form import evaluate as evaluate_handoff
from .human_agent_case_runner import (
    Backend as TTRHandoffBackend,
    CASE_ID as PREVIOUS_CASE_ID,
    USER_TASK,
    _cleanup_owned_guest,
    _costs as previous_costs,
    _events,
    _handoff_initial_state_sha256,
    _open_browser,
    _prepare_agent as _unused_previous_prepare_agent,
    _run_parallel,
    _setup_guest,
    _guest_exec,
    preflight,
)

CASE_ID = "ha-evidence-triage-normal-user-v1"
CASE_VERSION = "0.1.0"
AGENT_TASK = """Review ticket T-1042 in Case Desk. Inspect the ticket, linked order and delivery evidence, and refund policy. Then create a short internal triage brief using this form in the current browser window: {brief_url}. Select the issue classification and recommended next step supported by the source records, cite both the delivery evidence and policy IDs, and give a concise rationale. The brief is advisory only: do not issue a refund, create a formal Case Review, or change ticket/order status. Preserve all unrelated state. Do not use the hidden evaluator. The form URL is a task destination, not an answer."""
MODES = ("user-only", "agent-only", "user-only-negative-control",
         "independent", "shared", "shared-lock")

@dataclass(frozen=True)
class TaskCard:
    case_id: str = CASE_ID
    version: str = CASE_VERSION
    title: str = "Triage a delivery-damage case while a user updates a different ticket"
    actor_a_task: str = AGENT_TASK.replace("{brief_url}", "[run-specific Shift Triage Brief URL]")
    actor_b_task: str = USER_TASK
    shared_state: str = "Both Actors use the same Linux desktop session and one Chrome profile with distinct native task windows. The Agent reviews Case Desk records and submits a brief; User updates an independent handoff record."
    agent_oracle: str = "Requires a saved accurate triage brief, GUI visits to ticket/order/policy sources, unchanged TTR business state, no refund/review, and open/paid target records."
    user_oracle: str = "Independent HTTP-submission Oracle checks exact T-1043 note and local follow-up time."
    natural_condition: str = "Shared actors start together with a fixed ordinary User schedule; no forced event ordering."
    budget: str = "40 GUI MCP calls and 1200-second Agent actor cap; same for Agent-only, Independent, Shared and Shared+Lock."

def _load_ttr():
    package_dir = Path("/home/mjh/Projects/CoDesk-13-case-handoff-20261104/oscombo/collab/ticket_to_resolution")
    name = "codesk_ha_triage_ttr"
    if name not in sys.modules:
        pkg_spec = importlib.util.spec_from_file_location(name, package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)])
        if pkg_spec is None or pkg_spec.loader is None:
            raise ImportError(f"could not load TTR package: {package_dir}")
        module = importlib.util.module_from_spec(pkg_spec)
        sys.modules[name] = module
        pkg_spec.loader.exec_module(module)
    return SimpleNamespace(
        spec=importlib.import_module(name + ".spec"),
        database=importlib.import_module(name + ".database"),
        webapp=importlib.import_module(name + ".webapp"),
        runner=importlib.import_module(name + ".runner"),
        oracle=importlib.import_module(name + ".oracle"),
    )

class Backend(TTRHandoffBackend):
    def __init__(self, root: Path, guest_id: str, run_id: str, gateway: str, shared_password: str):
        super().__init__(root, guest_id, run_id, gateway, shared_password)
        self.triage_db = root / "backend" / guest_id / "triage.sqlite3"
        self.triage_manifest = create_triage_fixture(self.triage_db, run_id + "-" + guest_id)
        self.triage_server = make_triage_server(self.triage_db, host="0.0.0.0", port=0)
        self.triage_thread = threading.Thread(target=self.triage_server.serve_forever,
            daemon=True, name=f"triage-web-{guest_id}")
        self.triage_thread.start()
        self.triage_url = f"http://{gateway}:{self.triage_server.server_address[1]}"

    def healthcheck(self) -> None:
        super().healthcheck()
        with urllib.request.urlopen(self.triage_url + "/healthz", timeout=5) as response:
            if response.status != 200: raise RuntimeError("triage brief backend health failed")

    def evaluate_agent(self) -> dict[str, Any]:
        full = self.ttr.oracle.evaluate(self.ttr_db, self.ttr_manifest, condition="single_agent")
        brief = evaluate_triage(self.triage_db)
        access_path = self.ttr_db.with_suffix(".http.jsonl")
        reads = []
        if access_path.is_file():
            for line in access_path.read_text(encoding="utf-8").splitlines():
                try: reads.append(json.loads(line))
                except json.JSONDecodeError: pass
        required_paths = (f"/ticket/{self.ttr.spec.TICKET_ID}",
                          f"/order/{self.ttr.spec.ORDER_ID}",
                          f"/policy/{self.ttr.spec.POLICY_ID}")
        source_reads = {path: any(r.get("method") == "GET" and r.get("path") == path
                                  and int(r.get("status", 0)) == 200 for r in reads)
                        for path in required_paths}
        obs = full.get("observed", {})
        checks = {
            "brief_oracle_pass": bool(brief.get("success")),
            "case_desk_ticket_page_read": source_reads[required_paths[0]],
            "order_and_delivery_evidence_page_read": source_reads[required_paths[1]],
            "refund_policy_page_read": source_reads[required_paths[2]],
            "fixture_manifest_integrity": bool(full.get("checks", {}).get("fixture_manifest_integrity")),
            "protected_state_pass": bool(full.get("protected_state_pass")),
            "ticket_remains_open": obs.get("ticket_status") == "OPEN",
            "order_remains_paid": obs.get("order_status") == "PAID",
            "no_formal_review_created": obs.get("review_count") == 0,
            "no_refund_issued": obs.get("refund_count") == 0,
            "no_processor_precheck": obs.get("processor_precheck_count") == 0,
        }
        return {"task": "source-grounded-triage-brief", "success": all(checks.values()),
                "checks": checks, "brief": brief, "source_reads": source_reads,
                "source_http_log_path": str(access_path), "underlying_ttr_evaluation": full}

    def evaluate(self) -> dict[str, Any]:
        return {"agent": self.evaluate_agent(), "user": evaluate_handoff(self.handoff_db)}

    def close(self) -> None:
        try:
            self.triage_server.shutdown()
            self.triage_server.server_close()
            self.triage_thread.join(timeout=5)
            self.triage_server.access_log.close()
        except Exception:
            pass
        super().close()

def _triage_state_hash(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest.get("initial_state", {}), sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()

def _user_actions():
    # Click the visible note field explicitly. This is a normal user action and
    # prevents setup's prior address-bar focus from capturing typed text.
    return [
        GUIAction("switch_to_shift_handoff", "pyautogui.hotkey('alt','tab')", None, 1.2),
        GUIAction("focus_handoff_note", "pyautogui.click(500, 575)", "Shift Handoff", 1.2),
        GUIAction("type_handoff_note",
                  "pyautogui.write('Asked carrier for Tuesday delivery window; follow up at 16:00.', interval=0.025)",
                  "Shift Handoff", 2.0),
        GUIAction("tab_to_follow_up", "pyautogui.press('tab')", "Shift Handoff", 1.2),
        GUIAction("enter_follow_up", "pyautogui.write('2026-11-10 16:00')", "Shift Handoff", 2.2),
        GUIAction("submit_handoff", "pyautogui.press('tab'); pyautogui.press('enter')",
                  "Shift Handoff", 1.6),
    ]

def _user_negative_actions():
    actions = _user_actions()
    return [a if a.name != "type_handoff_note" else
            type(a)(a.name, "pyautogui.write('Asked carrier for Wednesday delivery window; follow up at 16:00.', interval=0.025)",
                    a.expected_app, a.delay_before_s) for a in actions]


def _setup_triage_guest(guest: Guest, backend: Backend, guest_dir: Path,
                       run_id: str, password: str) -> dict[str, Any]:
    """Set up both GUI apps, with a Guest-UI URL retry for sporadic cold-Chrome failures.

    The retry only navigates a visible Chrome window; it does not inject task state or
    bypass either app. This is specifically isolated to the new triage runner so the
    frozen Human Case 1?5 runner remains unchanged.
    """
    import shlex
    backend.healthcheck()
    health_urls = (backend.ttr_url + "/health", backend.handoff_url + "/healthz")
    for url in health_urls:
        _guest_exec(guest, f"curl -fsS --max-time 10 {url!r}", timeout=20)
    before = guest.screenshot(patience=60)
    guest_dir.mkdir(parents=True, exist_ok=True)
    (guest_dir / "desktop-before-apps.png").write_bytes(before)

    fallback_events: list[str] = []
    profile = f"/tmp/ha-{run_id}-{backend.guest_id}-handoff"
    profile_q = shlex.quote(profile)
    launch_log = shlex.quote(profile + "-launch.log")
    handoff_url = backend.handoff_url + "/"
    handoff_url_q = shlex.quote(handoff_url)
    launch = f"""mkdir -p {profile_q}
    (DISPLAY=:0 google-chrome --user-data-dir={profile_q} --no-first-run --no-default-browser-check --disable-gpu --new-window {handoff_url_q} >{launch_log} 2>&1 &)
    """
    _guest_exec(guest, launch, timeout=30)
    ready = False
    try:
        # Cold Chrome startup is intermittent in OSWorld. Let the first URL
        # navigation finish before sending any keyboard input into the window.
        _guest_exec(guest, f"""for i in $(seq 1 75); do
          if wmctrl -l 2>/dev/null | grep -Fqi 'Shift Handoff'; then exit 0; fi
          sleep 1
        done
        exit 1
        """, timeout=82)
        ready = True
    except Exception:
        fallback_events.append("handoff-cold-chrome-url-retry")
        retry = f"""wid=$(xdotool search --onlyvisible --name 'Google Chrome' 2>/dev/null | tail -n 1)
        test -n "$wid"
        # Prefer wmctrl's EWMH activation and verify a live Chrome title before
        # sending global keys; xdotool windowactivate can raise BadWindow on a
        # stale XID while Chrome is still creating its first native window.
        wmctrl -ia "$wid"
        active=
        for i in $(seq 1 20); do
          active=$(xdotool getactivewindow getwindowname 2>/dev/null || true)
          case "$active" in *'Google Chrome'*) break;; esac
          sleep 0.25
        done
        case "$active" in *'Google Chrome'*) ;; *) echo 'Chrome window did not accept focus'; exit 1;; esac
        xdotool key --clearmodifiers ctrl+l
        sleep 0.3
        xdotool type --clearmodifiers --delay 15 -- {handoff_url_q}
        xdotool key --clearmodifiers Return
        for i in $(seq 1 60); do
          if wmctrl -l 2>/dev/null | grep -Fqi 'Shift Handoff'; then exit 0; fi
          sleep 1
        done
        echo 'Shift Handoff page did not load after visible-browser retry'
        wmctrl -lpG 2>&1 || true
        tail -40 {launch_log} 2>/dev/null || true
        exit 1
        """
        try:
            _guest_exec(guest, retry, timeout=72)
        except Exception as exc:
            try:
                (guest_dir / "chrome-readiness-failed.png").write_bytes(guest.screenshot(patience=20))
            except Exception:
                pass
            try:
                diag = _guest_exec(guest, "wmctrl -lpG 2>&1 || true; echo ACTIVE:; xdotool getactivewindow getwindowname 2>&1 || true; ps -eo pid,comm,args | grep -E 'chrom(e|ium)' | grep -v grep || true", timeout=15)
                (guest_dir / "chrome-readiness-diagnostics.txt").write_text(str(diag), encoding="utf-8")
            except Exception:
                pass
            raise InfraError(f"Chrome readiness failed; diagnostics preserved: {exc}") from exc
        ready = True

    if not ready:
        raise InfraError("Shift Handoff Chrome window did not become ready")

    # Open the Agent's Case Desk window in the same Chrome profile, preserving the
    # one-session/two-window focus competition that the case is designed to observe.
    ticket_url = backend.ttr_url + "/login?actor=S"
    ticket_url_q = shlex.quote(ticket_url)
    new_window = f"""wid=$(wmctrl -l 2>/dev/null | awk 'tolower($0) ~ /shift handoff/ {{id=$1}} END {{print id}}')
    test -n "$wid"
    wmctrl -ia "$wid"
    for i in $(seq 1 20); do
      active=$(xdotool getactivewindow getwindowname 2>/dev/null || true)
      case "$active" in *'Shift Handoff'*) break;; esac
      sleep 0.25
    done
    case "$active" in *'Shift Handoff'*) ;; *) echo 'Shift Handoff window did not accept focus'; exit 1;; esac
    xdotool key --clearmodifiers ctrl+n
    sleep 1.5
    active=$(xdotool getactivewindow getwindowname 2>/dev/null || true)
    case "$active" in *'Google Chrome'*) ;; *) echo 'new Chrome window is not active'; wmctrl -lpG 2>&1 || true; exit 1;; esac
    xdotool key --clearmodifiers ctrl+l
    sleep 0.2
    xdotool type --clearmodifiers --delay 1 -- {ticket_url_q}
    xdotool key --clearmodifiers Return
    for i in $(seq 1 35); do
      if wmctrl -l 2>/dev/null | grep -Fqi 'Sign in'; then exit 0; fi
      sleep 1
    done
    echo 'Case Desk login window did not become ready'
    wmctrl -lpG 2>&1 || true
    exit 1
    """
    _guest_exec(guest, new_window, timeout=45)
    login = ("import pyautogui,time; time.sleep(0.4); " +
             f"pyautogui.write({password!r}, interval=0.004); pyautogui.press('tab'); " +
             "pyautogui.press('enter'); time.sleep(2)")
    guest.run_pyautogui(login)
    # Dismiss Chrome's incidental password-save bubble after the synthetic
    # account login so it cannot cover task controls or become an unmeasured
    # third-party focus disturbance.
    guest.run_pyautogui("import pyautogui,time; pyautogui.press('esc'); time.sleep(0.5)")
    time.sleep(1)
    windows = _guest_exec(guest, "wmctrl -lpG 2>/dev/null || true", timeout=20)
    if "Case queue" not in windows or "Shift Handoff" not in windows:
        raise InfraError("both triage task windows did not become visible after login: " + windows[-1600:])
    active = guest.active_window()
    if "Case Desk" not in (active or "") and "Case queue" not in (active or ""):
        _guest_exec(guest, "wid=$(xdotool search --onlyvisible --name 'Case queue' | tail -n 1); test -n \"$wid\"; xdotool windowactivate --sync \"$wid\"; xdotool windowraise \"$wid\"", timeout=20)
        time.sleep(0.5)
        active = guest.active_window()
    after = guest.screenshot(patience=60)
    (guest_dir / "setup.png").write_bytes(after)
    if not after or len(after) < 1000:
        raise InfraError("Guest setup screenshot was blank or too small")
    return {"window_inventory": windows, "active_window": active,
        "screenshot_before_bytes": len(before), "screenshot_after_bytes": len(after),
        "host_health": True, "guest_health": True,
        "case_desk_window_present": "Case queue" in windows,
        "handoff_window_present": "Shift Handoff" in windows,
        "foreground_case_desk_verified": "Case Desk" in (active or "") or "Case queue" in (active or ""),
        "authenticated_ttr_window": "Case queue" in windows,
        "chrome_readiness_retry_events": fallback_events}


def _prepare_triage_agent(guest: Guest, backend: Backend, out: Path, *, lock_path: Path | None,
                          budget: int, timeout: float, model: str, endpoint: str):
    from .harness import AgentContext, make_harness
    binary = os.environ.get("CODEX_CLI_BIN") or shutil.which("codex")
    if not binary:
        pinned = Path.home() / ".cache/codesk-codex-0.155.0-20261108/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
        if pinned.is_file(): binary = str(pinned)
    if not binary: raise RuntimeError("Codex CLI not found; set CODEX_CLI_BIN to pinned version 0.155.0")
    options = {"codex_bin": binary, "node_bin": os.environ.get("CODEX_NODE_BIN"),
        "base_url": endpoint, "api_key_env": "OPENAI_API_KEY", "wire_api": "responses",
        "timeout": timeout, "run_id": os.environ.get("OSCOMBO_RUN_ID"),
        "expected_app": "Google Chrome",
        "codex_home_base": os.environ.get("CODEX_HOME_BASE", "/home/mjh/.cache/codesk-ha-codex-home")}
    spec = {"harness": "codex", "model": model, "effort": "low", "base_url": endpoint, "options": options}
    instruction = AGENT_TASK.replace("{brief_url}", backend.triage_url + "/")
    ctx = AgentContext(name="agent", task_id=CASE_ID, instruction=instruction, guest=guest,
                       out=out, max_steps=budget, spec=spec,
                       action_lock_file=str(lock_path) if lock_path else None)
    harness = make_harness(spec)
    harness.prepare(ctx)
    return harness, ctx

def _costs(rows, user_result, agent_result, monitors) -> dict[str, Any]:
    costs = previous_costs(rows, user_result, agent_result, monitors)
    user_rows = [r for r in rows if r.get("actor_id") == "user" and r.get("event_type") == "gui_action"]
    agent_rows = [r for r in rows if r.get("actor_id") == "agent" and r.get("event_type") == "agent_gui_action"]
    def agent_window_authorized(row):
        title = (row.get("window_before") or "").lower()
        return ("case desk" in title) or ("shift triage brief" in title)
    user_baseline = len(_user_actions())
    costs["user"]["baseline_gui_actions"] = user_baseline
    costs["user"]["extra_operations_over_fixed_script"] = max(0, len(user_rows) - user_baseline)
    costs["agent"]["wrong_foreground_actions_by_title"] = sum(
        bool(r.get("misrouted_focus_before")) or not agent_window_authorized(r)
        for r in agent_rows)
    costs["agent"]["wrong_foreground_action_event_ids"] = [
        r.get("event_id") for r in agent_rows
        if bool(r.get("misrouted_focus_before")) or not agent_window_authorized(r)
    ]
    return costs

def run_condition(*, mode: str, out: Path, model: str = "gpt-6-sol",
                  endpoint: str | None = None, budget: int = 40, timeout: float = 1200,
                  image: str | None = None) -> dict[str, Any]:
    if mode not in MODES: raise ValueError(f"mode must be one of {MODES}")
    negative_control = mode == "user-only-negative-control"
    root = out.resolve()
    if not str(root).startswith("/mnt/raid1/"): raise ValueError("pilot output must be under /mnt/raid1")
    if root.exists() and any(root.iterdir()): raise FileExistsError(f"refusing to overwrite non-empty run: {root}")
    root.mkdir(parents=True, exist_ok=True)
    run_id = f"ha-triage-{mode}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    image_path = Path(image or os.environ.get("OSCOMBO_GUEST_IMAGE",
        "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"))
    if not image_path.is_file(): raise FileNotFoundError(image_path)
    resource = preflight(root, image_path)
    (root / "resource-preflight.json").write_text(json.dumps(resource, indent=2, ensure_ascii=False) + "\n")
    if not resource["ready"]:
        result = {"case_id": CASE_ID, "case_version": CASE_VERSION, "mode": mode,
                  "status": "blocked-resource-preflight", "experiment_valid": False,
                  "model_called": False, "resource_preflight": resource}
        (root / "run.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return result

    from . import osworld, combo
    from .osworld import client_password
    osworld.activate()
    os.environ["SWCUB_RUN_ID"] = run_id
    os.environ["OSCOMBO_RUN_ID"] = run_id
    started_mono = time.monotonic()
    os.environ["OSCOMBO_RUN_START_MONO"] = str(started_mono)
    os.environ["SWCUB_OWNER_TOKEN"] = secrets.token_hex(32)
    os.environ["SWCUB_RESOURCE_LEDGER"] = str(root / "resource-ledger.jsonl")
    os.environ["SWCUB_OSWORLD_OVERLAY_HOST_DIR"] = str(root / "overlays")
    os.environ.setdefault("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", resource["runtime_image"])
    os.environ["SWCUB_OSWORLD_VM_READY_TIMEOUT"] = "600"
    os.environ.setdefault("OSWORLD_DIR", "/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")

    guest_ids = ["guest-shared"] if mode not in {"independent"} else ["guest-user", "guest-agent"]
    needs_user = mode in {"user-only", "user-only-negative-control", "independent", "shared", "shared-lock"}
    needs_agent = mode in {"agent-only", "independent", "shared", "shared-lock"}
    backends: dict[str, Backend] = {}
    envs, guests, monitors, setup, boot = {}, {}, [], {}, {}
    event_log = EventLog(root / "events.jsonl", run_id, root, started_mono)
    event_log.emit("orchestrator", "run_started", case_id=CASE_ID, case_version=CASE_VERSION,
        mode=mode, agent_kind="codex", model=model if needs_agent else None,
        user_strategy="fixed-open-loop", fixed_mechanism_probe=False,
        natural_parallelism=mode in {"independent", "shared", "shared-lock"},
        negative_control=negative_control)
    lock_path = Path(f"/tmp/{run_id}.gui-action.lock") if mode == "shared-lock" else None
    if lock_path: os.environ["OSCOMBO_ACTION_LOCK_FILE"] = str(lock_path)
    else: os.environ.pop("OSCOMBO_ACTION_LOCK_FILE", None)
    actor_runs, oracle, status, model_called = {"results": {}, "errors": {}}, {}, "finished", False
    run_started = time.monotonic()
    try:
        gateway = resource["docker_bridge_gateway"]
        for gid in guest_ids:
            backends[gid] = Backend(root, gid, run_id, gateway, client_password())
        def boot_one(gid: str) -> None:
            guest_dir = root / "guests" / gid
            guest_dir.mkdir(parents=True, exist_ok=True)
            env = combo.boot(str(image_path), str(guest_dir / "cache"))
            envs[gid] = env
            guests[gid] = Guest(env)
            t0 = time.monotonic()
            guests[gid].wait_desktop(patience=600)
            shot = guests[gid].screenshot(patience=60)
            if not shot or len(shot) < 1000: raise InfraError("blank/invalid desktop screenshot")
            (guest_dir / "desktop-ready.png").write_bytes(shot)
            provider = getattr(env, "provider", None)
            container = getattr(provider, "container", None)
            container_id = getattr(container, "id", None)
            live_qemu, container_kvm = "", False
            if container_id:
                qemu_probe = subprocess.run(["docker", "exec", container_id, "ps", "-eo", "args"],
                    capture_output=True, text=True, timeout=15)
                live_qemu = next((line.strip() for line in qemu_probe.stdout.splitlines()
                                  if "qemu-system" in line), "")
                kvm_probe = subprocess.run(["docker", "exec", container_id, "test", "-r", "/dev/kvm"],
                    capture_output=True, timeout=15)
                container_kvm = kvm_probe.returncode == 0
            accel = "KVM" if "accel=kvm" in live_qemu and container_kvm else (
                    "TCG/unknown" if live_qemu else "not-observed")
            boot[gid] = {"ready_wait_s": round(time.monotonic() - t0, 3),
                "screenshot_bytes": len(shot), "live_qemu_acceleration": accel,
                "container_kvm_readable": container_kvm, "qemu_command": live_qemu[:1000]}
        if mode == "independent":
            threads = [threading.Thread(target=boot_one, args=(gid,), name="boot-" + gid) for gid in guest_ids]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            if len(guests) != 2: raise InfraError("Independent condition requires two ready Guests")
        else:
            boot_one(guest_ids[0])
        for gid in guest_ids:
            setup[gid] = _setup_triage_guest(guests[gid], backends[gid], root / "guests" / gid,
                                             run_id, client_password())
            backends[gid].healthcheck()
            with urllib.request.urlopen(backends[gid].triage_url + "/", timeout=5) as response:
                if response.status != 200: raise InfraError("triage brief page not reachable")
        monitors = []
        for gid in guest_ids:
            monitor = FocusMonitor(guests[gid], gid, event_log, root / "focus" / gid, interval=.5)
            monitors.append(monitor)
            monitor.start()

        user_gid = "guest-user" if mode == "independent" else guest_ids[0]
        agent_gid = "guest-agent" if mode == "independent" else guest_ids[0]
        functions = []
        if needs_user:
            actions = _user_negative_actions() if negative_control else _user_actions()
            actor = ScriptedGUIActor(actor_id="user", guest=guests[user_gid], actions=actions,
                event_log=event_log, out=root, guest_id=user_gid, lock_path=lock_path, strategy="fixed")
            functions.append(("user", actor.run))
        if needs_agent:
            harness, ctx = _prepare_triage_agent(guests[agent_gid], backends[agent_gid], root,
                lock_path=lock_path, budget=budget, timeout=timeout, model=model,
                endpoint=endpoint or os.environ.get("OPENAI_BASE_URL") or "https://api.haogpt.net/v1")
            def codex_agent():
                nonlocal model_called
                model_called = True
                t0 = time.monotonic()
                event_log.emit("agent", "actor_started", guest_id=agent_gid, actor_kind="codex_gui")
                ctx.t0 = time.time()
                ar = harness.run(ctx)
                payload = {"status": ar.status, "error": ar.error, "steps": ar.steps, "extra": ar.extra}
                event_log.emit("agent", "actor_finished", guest_id=agent_gid,
                    elapsed_s=round(time.monotonic()-t0, 6), status=ar.status, steps=ar.steps,
                    token_usage=ar.extra.get("token_usage"))
                return payload
            functions.append(("agent", codex_agent))

        actor_runs = _run_parallel(functions)
        time.sleep(1)
        for monitor in monitors: monitor.stop()
        actor_results = actor_runs["results"]
        gids = {"user": user_gid, "agent": agent_gid}
        for actor in (["user"] if needs_user else []) + (["agent"] if needs_agent else []):
            oracle[actor] = backends[gids[actor]].evaluate()[actor]
        actor_success = {"user": oracle.get("user", {}).get("success") if needs_user else None,
                         "agent": oracle.get("agent", {}).get("success") if needs_agent else None}
        joint = bool(actor_success["user"] and actor_success["agent"]) if needs_user and needs_agent else None
        equivalence = None
        if mode == "independent":
            equivalence = {
                "ttr_business_state_sha256_equal":
                    backends["guest-user"].ttr_manifest_obj.get("business_state_sha256") ==
                    backends["guest-agent"].ttr_manifest_obj.get("business_state_sha256"),
                "handoff_initial_state_equal":
                    _handoff_initial_state_sha256(backends["guest-user"].handoff_manifest) ==
                    _handoff_initial_state_sha256(backends["guest-agent"].handoff_manifest),
                "triage_initial_state_equal":
                    _triage_state_hash(backends["guest-user"].triage_manifest) ==
                    _triage_state_hash(backends["guest-agent"].triage_manifest),
            }
            if not all(equivalence.values()): status = "invalid-fixture-inequivalence"
        rows = _events(root / "events.jsonl")
        costs = _costs(rows, actor_results.get("user"), actor_results.get("agent"), monitors)
        if negative_control:
            checks = oracle.get("user", {}).get("checks", {})
            detected = bool(checks.get("submitted") and checks.get("ticket_id") and
                checks.get("follow_up") and checks.get("note") is False)
            status = "negative-control-pass" if detected else "negative-control-failed"
        elif any(value is False for value in actor_success.values() if value is not None):
            status = "valid-task-failure"
        result = {
            "case_id": CASE_ID, "case_version": CASE_VERSION, "task_card": asdict(TaskCard()),
            "run_id": run_id, "mode": mode, "agent_kind": "codex" if needs_agent else None,
            "model": model if needs_agent else None, "status": status,
            "experiment_valid": status not in {"invalid-fixture-inequivalence", "infrastructure-invalid", "orchestrator-error"},
            "negative_control": negative_control,
            "negative_control_detected": status == "negative-control-pass" if negative_control else None,
            "model_called": model_called, "actor_results": actor_runs["results"],
            "actor_errors": actor_runs["errors"], "actor_success": actor_success,
            "joint_success": joint, "oracle": oracle, "costs": costs,
            "fixture_equivalence": equivalence,
            "fixture_hashes": {gid: {
                "ttr_business_state_sha256": backends[gid].ttr_manifest_obj.get("business_state_sha256"),
                "handoff_initial_state_sha256": _handoff_initial_state_sha256(backends[gid].handoff_manifest),
                "triage_initial_state_sha256": _triage_state_hash(backends[gid].triage_manifest)}
                for gid in guest_ids},
            "guest_setup": setup, "guest_boot": boot, "resource_preflight": resource,
            "guest_count": len(guests), "base_image": str(image_path),
            "resource_ledger": str(root / "resource-ledger.jsonl"),
            "overlay_root": str(root / "overlays"),
            "app_topology": "run-scoped TTR, triage brief and handoff services; two visible Chrome windows in one Guest/profile; Agent triage form reuses its Case Desk window",
            "user_task": USER_TASK, "agent_task": AGENT_TASK.replace("{brief_url}", backends[agent_gid].triage_url + "/"),
            "agent_budget": {"gui_mcp_calls": budget, "actor_wall_cap_s": timeout},
            "natural_parallelism": mode in {"independent", "shared", "shared-lock"},
            "fixed_mechanism_probe": False,
            "elapsed_s": round(time.monotonic()-run_started, 3),
            "limitations": ["one run per condition; no repeated-trial claim",
                "User uses fixed open-loop replay; recovery behavior is deferred",
                "window title is a focus proxy, while actual HTTP actions and independent Oracles are retained",
                "TTR supplies the existing synthetic source records; this is an Actor-composition study, not a new underlying payment workflow"],
        }
        (root / "run.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n")
        event_log.emit("orchestrator", "run_finished", status=status, elapsed_s=result["elapsed_s"],
                       actor_success=actor_success, joint_success=joint)
        return result
    except Exception as exc:
        status = "infrastructure-invalid" if isinstance(exc, InfraError) else "orchestrator-error"
        failure = {"case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id, "mode": mode,
            "status": status, "experiment_valid": False, "model_called": model_called,
            "elapsed_s": round(time.monotonic()-run_started, 3),
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-4000:],
            "resource_preflight": resource, "resource_ledger": str(root / "resource-ledger.jsonl"),
            "overlay_root": str(root / "overlays"), "historical_artifacts_preserved": True}
        if not (root / "run.json").exists():
            (root / "run.json").write_text(json.dumps(failure, indent=2, ensure_ascii=False) + "\n")
        event_log.emit("orchestrator", "run_failed", status=status, error=failure["error"][:1000])
        raise
    finally:
        for monitor in monitors:
            try: monitor.stop()
            except Exception: pass
        for backend in backends.values():
            try: backend.close()
            except Exception: pass
        for env in envs.values():
            try: env.close()
            except Exception: pass
        try:
            cleanup = _cleanup_owned_guest(root, run_id)
            if cleanup: (root / "cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
        except Exception as exc:
            (root / "cleanup-warning.json").write_text(json.dumps(
                {"status": "safe-cleanup-error", "error": str(exc)[:500]}, indent=2) + "\n")
        for name in ("OSCOMBO_ACTION_LOCK_FILE", "OSCOMBO_ACTION_LOCK_EVENTS_FILE",
                     "OSCOMBO_RUN_ID", "OSCOMBO_RUN_START_MONO"):
            os.environ.pop(name, None)

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--timeout", type=float, default=1200)
    parser.add_argument("--image")
    args = parser.parse_args()
    result = run_condition(mode=args.mode, out=args.out, model=args.model,
        endpoint=args.base_url, budget=args.budget, timeout=args.timeout, image=args.image)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
if __name__ == "__main__":
    main()
