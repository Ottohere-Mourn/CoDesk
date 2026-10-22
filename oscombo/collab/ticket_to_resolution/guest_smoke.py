"""Bounded scripted OSWorld Guest smoke for CDD-TTR-001.

This is a GUI plumbing test, never model evidence. It drives the visible web
forms through the existing OSWorld Guest action interface and preserves the
run-owned overlay, screenshots, action samples, server log, and DB snapshots.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sqlite3
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Any

from . import CASE_ID, spec
from .database import business_snapshot, business_state_digest
from .oracle import evaluate
from .runner import hidden_manifest_path, reset_owned_run
from .webapp import make_server as make_web_server


def _append(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def _record_owned_resource(root: Path, value: dict[str, Any]) -> None:
    ledger_path = root / "ownership.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("case_id") != CASE_ID:
        raise PermissionError("ownership ledger case mismatch")
    ledger.setdefault("resources", []).append(value)
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mark_runtime_resource(root: Path, run_id: str, kind: str, status: str,
                           **details: Any) -> None:
    ledger_path = root / "ownership.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    matches = [r for r in ledger.get("resources", [])
               if r.get("kind") == kind and r.get("run_id") == run_id]
    for resource in matches:
        resource["status"] = status
        resource.update(details)
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_write(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"preserving existing smoke evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_meminfo(key: str) -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith(key + ":"):
            return int(line.split()[1]) * 1024
    return 0


def _psi_avg10() -> float:
    for line in Path("/proc/pressure/cpu").read_text().splitlines():
        if line.startswith("some "):
            match = re.search(r"avg10=([0-9.]+)", line)
            return float(match.group(1)) if match else 100.0
    return 100.0


def _cmd(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def _resource_preflight(base_image: Path, provider: Path, runtime_image: str) -> dict[str, Any]:
    try:
        load = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
        cpus = os.cpu_count() or 1
        psi = _psi_avg10()
        available = _read_meminfo("MemAvailable")
        swap_free = _read_meminfo("SwapFree")
        kvm = Path("/dev/kvm")
        kvm_access = kvm.exists() and os.access(kvm, os.R_OK | os.W_OK)
        docker_info = _cmd(["docker", "info", "--format", "{{.ServerVersion}} {{.NCPU}} {{.MemTotal}}"])
        image = _cmd(["docker", "image", "inspect", runtime_image, "--format", "{{.Id}} {{.Size}}"])
        active = _cmd(["docker", "ps", "--filter", f"ancestor={runtime_image}", "-q"])
        bridge = _cmd(["docker", "network", "inspect", "bridge", "--format",
                       "{{range .IPAM.Config}}{{.Gateway}}{{end}}"])
        provider_head = _cmd(["git", "-C", str(provider), "rev-parse", "HEAD"])
        provider_status = _cmd(["git", "-C", str(provider), "status", "--short"])
        provider_file = provider / "desktop_env" / "providers" / "docker" / "provider.py"
        provider_source = provider_file.read_text(encoding="utf-8") if provider_file.is_file() else ""
        tcg_fallback = ('self.environment["KVM"] = "N"' in provider_source
                        and "TCG_CPU_MODEL" in provider_source)
        qemu = _cmd(["bash", "-lc", "ps -eo comm | awk '$1 ~ /^qemu/ {n++} END {print n+0}'"])
        checks = {
            "base_image_readable": base_image.is_file() and os.access(base_image, os.R_OK),
            "provider_directory": provider.is_dir() and provider_head.returncode == 0,
            "docker_access": docker_info.returncode == 0,
            "runtime_image_available": image.returncode == 0,
            "no_active_same_runtime_guest": active.returncode == 0 and not active.stdout.strip(),
            "no_qemu_process": qemu.returncode == 0 and qemu.stdout.strip() == "0",
            "kvm_read_write": kvm_access,
            "provider_tcg_fallback_supported": tcg_fallback,
            "cpu_psi_avg10_below_10_percent": psi < 10,
            "one_minute_load_below_logical_cpu_count": bool(load and load[0] / cpus < 1.0),
            "memory_available_at_least_8_gib": available >= 8 * 1024**3,
            "docker_bridge_gateway_available": bridge.returncode == 0 and bool(bridge.stdout.strip()),
        }
        return {
            "sampled_at_epoch": time.time(), "load_average_1_5_15": load,
            "logical_cpus": cpus, "cpu_psi_some_avg10_percent": psi,
            "memory_available_bytes": available, "swap_free_bytes": swap_free,
            "kvm_device": str(kvm), "kvm_access": kvm_access,
            "docker_info": docker_info.stdout.strip(), "runtime_image": runtime_image,
            "runtime_image_inspect": image.stdout.strip(),
            "active_runtime_guest_count": len(active.stdout.splitlines()) if active.returncode == 0 else None,
            "qemu_process_count": int(qemu.stdout.strip() or "0") if qemu.returncode == 0 else None,
            "docker_bridge_gateway": bridge.stdout.strip() if bridge.returncode == 0 else None,
            "base_image": {"path": str(base_image), "bytes": base_image.stat().st_size if base_image.exists() else None,
                           "read_only_by_smoke": True},
            "provider": {"path": str(provider), "head": provider_head.stdout.strip() if provider_head.returncode == 0 else None,
                         "preexisting_status": provider_status.stdout.splitlines()},
            "checks": checks,
            "non_blocking_risks": ([] if kvm_access else ["Guest would use QEMU TCG, not KVM; slower and CPU intensive"]),
            "ready": all(value for key, value in checks.items() if key != "kvm_read_write"),
            "limits": {"max_guest_count": 1, "start_guest_only_if_all_checks_pass": True},
        }
    except Exception as exc:
        return {"sampled_at_epoch": time.time(), "ready": False,
                "error": f"{type(exc).__name__}: {exc}", "checks": {"resource_probe": False}}


def _check_run(root: Path, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", run_id):
        raise ValueError("run_id must be a safe 1-100 character filesystem label")
    ownership_path = root / "ownership.json"
    if not ownership_path.is_file() or ownership_path.is_symlink():
        raise PermissionError("missing or symlinked run ownership ledger")
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or ownership.get("run_id") != run_id:
        raise PermissionError("case/run ID does not match ownership ledger")
    if Path(ownership.get("run_root", "")).resolve() != root.resolve():
        raise PermissionError("run root does not match ownership ledger")
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure the run condition before starting Guest smoke")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("condition") != "collaborative_shared":
        raise ValueError("Gate 2 shared-desktop smoke requires a collaborative_shared run config")
    if (root / "provenance.json").exists() or (root / "guest_smoke_report.json").exists():
        raise FileExistsError("this run already contains smoke provenance/report; use a new run root")
    baseline = json.loads(hidden_manifest_path(root).read_text(encoding="utf-8"))
    state = business_snapshot(root / "db" / spec.FIXTURE_DB)
    if business_state_digest(state) != baseline.get("business_state_sha256"):
        raise RuntimeError("episode business DB is no longer at its initial fixture state")
    return ownership, config


def _parse_window_ids(sample: dict[str, Any]) -> list[str]:
    output = str(sample.get("output", ""))
    inside = output.split("WINDOWS_BEGIN", 1)[-1].split("WINDOWS_END", 1)[0]
    return [line.split()[0] for line in inside.splitlines() if line.strip() and line.split()]


def _active_window_id(sample: dict[str, Any]) -> str | None:
    match = re.search(r"ACTIVE_WINDOW_ID=(0x[0-9a-fA-F]+|[0-9]+)", str(sample.get("output", "")))
    return match.group(1) if match else None


def _guest_shell(guest: Any, script: str, timeout: int = 30) -> dict[str, Any]:
    result = guest.env.controller.run_bash_script(script, timeout=timeout)
    if not isinstance(result, dict) or result.get("status") != "success":
        raise RuntimeError(f"Guest readiness command failed: {result}")
    return result


def _launch_browser(guest: Any, actor: str, profile: str, url: str) -> None:
    safe_profile = shlex.quote(profile)
    safe_url = shlex.quote(url)
    script = f"""set -e
    BROWSER="$(command -v google-chrome || command -v chromium-browser || command -v chromium || true)"
    test -n "$BROWSER"
    mkdir -p {safe_profile}
    nohup "$BROWSER" --user-data-dir={safe_profile} --no-first-run --no-default-browser-check \\
      --disable-infobars --new-window {safe_url} >/tmp/codesk-ttr-{actor}-browser.log 2>&1 </dev/null &
    for i in $(seq 1 40); do sleep 1; wmctrl -lp 2>/dev/null | grep -qi 'Case queue\\|Sign in' && exit 0; done
    exit 1
    """
    _guest_shell(guest, script, timeout=50)


def _gui_action(guest: Any, root: Path, actor: str, label: str, code: str,
                expected_route: str, run_id: str, action_index: int) -> None:
    from oscombo.collab.data_to_deck.live_pilot import _append, _stamp
    guest.actor = actor
    before = guest._window_sample("ttr_before_" + label)
    guest.run_pyautogui(code)
    after = guest._window_sample("ttr_after_" + label)
    shot = guest.screenshot(patience=45)
    shot_path = root / "screenshots" / f"{action_index:02d}-{actor}-{label}.png"
    shot_path.parent.mkdir(parents=True, exist_ok=True)
    shot_path.write_bytes(shot)
    _append(root / "ticket_to_resolution_steps.jsonl", {
        "time_utc": _stamp(), "run_id": run_id, "actor": actor,
        "step": action_index, "label": label, "expected_route": expected_route,
        "action_code": code, "window_before": before, "window_after": after,
        "window_samples_atomic": False, "screenshot": str(shot_path.relative_to(root)),
    })


def _open_url(url: str, seconds: float = 1.6) -> str:
    return ("import pyautogui,time; pyautogui.hotkey('ctrl','l'); time.sleep(0.2); "
            f"pyautogui.write({url!r}, interval=0.002); pyautogui.press('enter'); time.sleep({seconds})")


def _login(password: str) -> str:
    return ("import pyautogui,time; time.sleep(0.5); "
            f"pyautogui.write({password!r}, interval=0.004); pyautogui.press('tab'); "
            "pyautogui.press('enter'); time.sleep(2)")


def _review_form_actions() -> tuple[str, str]:
    choose = ("import pyautogui,time; time.sleep(0.4); pyautogui.press('e'); pyautogui.press('enter'); "
              "pyautogui.press('tab'); pyautogui.press('home'); pyautogui.press('down', presses=2); pyautogui.press('enter'); "
              "pyautogui.press('tab'); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); "
              "pyautogui.press('tab'); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')")
    fill = ("import pyautogui,time; pyautogui.press('tab'); pyautogui.write('80.00'); pyautogui.press('tab'); "
            "pyautogui.write('8.00'); pyautogui.press('tab'); pyautogui.write('0.00'); pyautogui.press('tab'); "
            "pyautogui.write('88.00'); pyautogui.press('tab'); "
            "pyautogui.write('Delivery evidence matches the damaged dock line; policy permits line price plus tax, not shipping.', interval=0.004); "
            "pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(2)")
    return choose, fill


def _refund_form_actions() -> tuple[str, str]:
    choose = ("import pyautogui,time; time.sleep(0.4); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); "
              "pyautogui.press('tab'); pyautogui.press('home'); pyautogui.press('down', presses=2); pyautogui.press('enter')")
    fill = ("import pyautogui,time; pyautogui.press('tab'); pyautogui.write('80.00'); pyautogui.press('tab'); "
            "pyautogui.write('8.00'); pyautogui.press('tab'); pyautogui.write('0.00'); pyautogui.press('tab'); "
            "pyautogui.write('88.00'); pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(2)")
    return choose, fill


def _resolve_form_actions() -> tuple[str, str]:
    choose = ("import pyautogui,time; time.sleep(0.4); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter'); "
              "pyautogui.press('tab'); pyautogui.press('home'); pyautogui.press('down'); pyautogui.press('enter')")
    fill = ("import pyautogui,time; pyautogui.press('tab'); "
            "pyautogui.write('Verified the damaged dock and completed the permitted partial refund.', interval=0.004); "
            "pyautogui.press('tab'); pyautogui.press('enter'); time.sleep(2)")
    return choose, fill


def _cleanup_guest(container_id: str, run_id: str, root: Path) -> dict[str, Any]:
    from oscombo.collab.data_to_deck.live_pilot import _missing_container, _verify_container
    if _missing_container(container_id):
        result = {"container_id": container_id, "status": "already_absent", "ownership_verified_by_run_ledger": True}
    else:
        container = _verify_container(container_id, run_id)
        actual = container.attrs.get("Config", {}).get("Labels") or {}
        if container.id != container_id or actual.get("oscombo") != "1" or actual.get("oscombo.run") != run_id:
            raise PermissionError("exact container ID and run ownership labels do not match; resource preserved")
        container.stop(timeout=10)
        container.remove(force=True)
        if not _missing_container(container_id):
            raise RuntimeError("owned Guest container still exists after removal")
        result = {"container_id": container_id, "status": "removed", "ownership_verified": True,
                  "labels": actual, "overlay_preserved": True}
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "guest_cleanup",
                                                **result, "time_epoch": time.time()})
    ledger_path = root / "ownership.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for item in ledger.get("resources", []):
        if item.get("kind") == "guest-container" and item.get("container_id") == container_id:
            item["status"] = result["status"]
            item["cleanup_verified"] = True
            item["cleanup_time_epoch"] = time.time()
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def run_guest_smoke(args) -> dict[str, Any]:
    root = Path(args.run_root).resolve()
    run_id = args.run_id
    ownership, config = _check_run(root, run_id)
    base_image = Path(args.base_image).resolve()
    provider = Path(args.provider).resolve()
    preflight = _resource_preflight(base_image, provider, args.runtime_image)
    _json_write(root / "guest_resource_preflight.json", preflight)
    if not preflight.get("ready"):
        gates = {
            "gate_1_guest_web_readiness": "BLOCKED_RESOURCE",
            "gate_2_scripted_gui_e2e": "BLOCKED_DEPENDS_GATE_1",
            "gate_3_isolated_compatibility": "NOT_RUN_RESOURCE_BLOCK",
        }
        report = {"case_id": CASE_ID, "case_version": spec.CASE_VERSION, "run_id": run_id,
                  "execution_kind": "scripted_guest_smoke", "model_called": False,
                  "status": "BLOCKED_RESOURCE", "resource_preflight": preflight,
                  "gates": gates, "historical_artifacts_preserved": True}
        _json_write(root / "guest_smoke_report.json", report)
        return report

    from oscombo.collab.data_to_deck.live_pilot import _boot_guest, _stamp
    from oscombo.collab.data_to_deck.provenance import RunLedger, collect_artifacts
    from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server as make_collab_server
    from .database import CaseStore

    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text(encoding="utf-8"))
    collab_tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    gateway = str(preflight["docker_bridge_gateway"])
    old_cwd = Path.cwd()
    env_names = ("OSWORLD_DIR", "OSCOMBO_GUEST_IMAGE", "OSCOMBO_RUNTIME_IMAGE", "OSCOMBO_OVERLAY_DIR",
                 "SWCUB_VM_OVERLAY", "OSCOMBO_RUN_LABEL", "OSCOMBO_GUEST_RAM", "OSCOMBO_GUEST_CPUS",
                 "OSCOMBO_VM_READY_TIMEOUT")
    old_env = {name: os.environ.get(name) for name in env_names}
    env_path_added = False
    ledger = RunLedger(root, {"run_id": run_id, "case_id": CASE_ID, "case_version": spec.CASE_VERSION,
        "condition": "collaborative_shared", "execution_kind": "scripted_guest_smoke", "model_called": False,
        "base_image": str(base_image), "provider_path": str(provider),
        "provider_head": preflight["provider"]["head"], "preexisting_provider_status": preflight["provider"]["preexisting_status"],
        "runtime_image": args.runtime_image, "backend_topology": config["backend_topology"],
        "app_gateway_bind_ip": gateway, "browser_profiles": {"A": f"/tmp/codesk-ttr-{run_id}-A",
                                                                  "B": f"/tmp/codesk-ttr-{run_id}-B"}})
    app_server = collab_server = None
    app_thread = collab_thread = None
    env = guest = None
    container_id = None
    gates = {"gate_1_guest_web_readiness": "NOT_RUN", "gate_2_scripted_gui_e2e": "NOT_RUN",
             "gate_3_isolated_compatibility": "NOT_RUN_RESOURCE_LIMITED"}
    errors: list[dict[str, str]] = []
    oracle_result = None
    reset_result = None
    cleanup_result = None
    try:
        app_server = make_web_server(root / "db" / spec.FIXTURE_DB, credentials, host=gateway, port=0)
        app_port = app_server.server_address[1]
        app_url = f"http://{gateway}:{app_port}"
        app_thread = threading.Thread(target=app_server.serve_forever, daemon=True)
        app_thread.start()
        with urllib.request.urlopen(app_url + "/health", timeout=5) as response:
            host_health = json.loads(response.read())
        if not host_health.get("ready"):
            raise RuntimeError("case Web service health check failed on host")
        collab_server = make_collab_server(ProtocolStore(root / "collaboration", run_id), collab_tokens,
                                           host="127.0.0.1", port=0)
        collab_thread = threading.Thread(target=collab_server.serve_forever, daemon=True)
        collab_thread.start()
        _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "case_web_service_started",
            "bind_ip": gateway, "port": app_port, "app_url": app_url, "owner": "current process", "time_utc": _stamp()})
        _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "collab_service_started",
            "bind_ip": "127.0.0.1", "port": collab_server.server_port, "owner": "current process", "time_utc": _stamp()})
        _record_owned_resource(root, {"kind": "case_web_service", "run_id": run_id,
            "pid": os.getpid(), "thread_name": "ticket-to-resolution-web", "bind_ip": gateway,
            "port": app_port, "status": "active", "started_at_epoch": time.time()})
        _record_owned_resource(root, {"kind": "collaboration_service", "run_id": run_id,
            "pid": os.getpid(), "thread_name": "ticket-to-resolution-collaboration", "bind_ip": "127.0.0.1",
            "port": collab_server.server_port, "status": "active", "started_at_epoch": time.time()})
        _record_owned_resource(root, {"kind": "http_access_log", "run_id": run_id,
            "path": str((root / "db" / "case.http.jsonl").resolve()), "status": "active"})

        # _boot_guest uses the pinned isolated provider and creates its overlay
        # under this run root. It verifies the full container ID, labels, and
        # that the given base-image mount is read-only.
        env, guest, container_id = _boot_guest(root, run_id, "shared", str(base_image), provider,
                                               args.runtime_image, ledger)
        env_path_added = str(provider) in sys.path
        host_probe = _guest_shell(guest, f"set -e; curl -fsS --max-time 12 {app_url}/health")
        try:
            guest_health = json.loads(host_probe.get("output", "{}"))
        except json.JSONDecodeError:
            guest_health = {}
        if not guest_health.get("ready"):
            raise RuntimeError(f"Guest could not reach the episode Web service: {host_probe}")
        ticket = CaseStore(root / "db" / spec.FIXTURE_DB).get_ticket()
        order = CaseStore(root / "db" / spec.FIXTURE_DB).get_order()
        policy = CaseStore(root / "db" / spec.FIXTURE_DB).get_policy()
        if not (ticket["status"] == "OPEN" and order["status"] == "PAID"
                and policy["id"] == spec.POLICY_ID and len(order["lines"]) == 2):
            raise RuntimeError("service-side Gate 1 fixture readiness does not match the fixed manifest")
        gates["gate_1_guest_web_readiness"] = "PASS"

        profile_a = f"/tmp/codesk-ttr-{run_id}-A"
        profile_b = f"/tmp/codesk-ttr-{run_id}-B"
        login_a = app_url + "/login?actor=A"
        login_b = app_url + "/login?actor=B"
        idx = 0
        _launch_browser(guest, "A", profile_a, login_a)
        _gui_action(guest, root, "A", "login", _login(credentials["A"]), "/login", run_id, idx := idx + 1)
        for label, route in (("order_facts", f"/order/{spec.ORDER_ID}"),
                             ("policy", f"/policy/{spec.POLICY_ID}"),
                             ("review_form", "/reviews/new")):
            _gui_action(guest, root, "A", label, _open_url(app_url + route), route, run_id, idx := idx + 1)
        choose, fill = _review_form_actions()
        _gui_action(guest, root, "A", "review_select_values", choose, "/reviews/new", run_id, idx := idx + 1)
        _gui_action(guest, root, "A", "review_amounts_and_save", fill, "/reviews/new", run_id, idx := idx + 1)
        reviews = CaseStore(root / "db" / spec.FIXTURE_DB).list_reviews()
        if not reviews:
            raise RuntimeError("GUI review form did not persist a Case Review")
        review_id = reviews[-1]["id"]
        window_a = guest._window_sample("actor_A_after_review")

        _launch_browser(guest, "B", profile_b, login_b)
        _gui_action(guest, root, "B", "login", _login(credentials["B"]), "/login", run_id, idx := idx + 1)
        window_b = guest._window_sample("actor_B_after_login")
        _gui_action(guest, root, "B", "open_case_review", _open_url(app_url + "/reviews/current"),
                    f"/reviews/{review_id}", run_id, idx := idx + 1)
        choose, fill = _refund_form_actions()
        _gui_action(guest, root, "B", "refund_form", _open_url(app_url + "/refunds/new"), "/refunds/new", run_id, idx := idx + 1)
        _gui_action(guest, root, "B", "refund_select_targets", choose, "/refunds/new", run_id, idx := idx + 1)
        _gui_action(guest, root, "B", "refund_amounts_and_submit", fill, "/refunds/new", run_id, idx := idx + 1)
        choose, fill = _resolve_form_actions()
        _gui_action(guest, root, "B", "resolution_form", _open_url(app_url + "/resolve"), "/resolve", run_id, idx := idx + 1)
        _gui_action(guest, root, "B", "resolution_select_targets", choose, "/resolve", run_id, idx := idx + 1)
        _gui_action(guest, root, "B", "resolution_notes_and_submit", fill, "/resolve", run_id, idx := idx + 1)

        store = CaseStore(root / "db" / spec.FIXTURE_DB)
        audit = store.list_audit()
        window_records = [
            {"actor": "A", "sample": window_a, "active_window_id": _active_window_id(window_a),
             "window_ids": _parse_window_ids(window_a), "atomic_with_input": False},
            {"actor": "B", "sample": window_b, "active_window_id": _active_window_id(window_b),
             "window_ids": _parse_window_ids(window_b), "atomic_with_input": False},
        ]
        distinct_active_window_ids = bool(window_records[0]["active_window_id"]
                                          and window_records[1]["active_window_id"]
                                          and window_records[0]["active_window_id"] != window_records[1]["active_window_id"])
        _append(root / "ticket_to_resolution_steps.jsonl", {"run_id": run_id, "event": "window_identity_check",
            "records": window_records, "distinct_active_window_ids_observed": distinct_active_window_ids,
            "window_identity_claim": "non-atomic wmctrl window samples; separate browser profiles are recorded in provenance"})
        if not reviews[-1]["is_valid_current_review"]:
            raise RuntimeError("saved Review failed application-side validation")

        oracle_result = evaluate(root / "db" / spec.FIXTURE_DB, hidden_manifest_path(root), "collaborative_shared")
        oracle_path = root / "oracle_result.json"
        _json_write(oracle_path, oracle_result)
        gates["gate_2_scripted_gui_e2e"] = "PASS" if oracle_result["joint_business_success"] else "FAIL_ORACLE"
        if not oracle_result["joint_business_success"]:
            raise RuntimeError("formal hidden-state Joint Oracle rejected scripted GUI result")

        # Capture final server-side DB and GUI trace before reset. Reset is a
        # separate evaluator-side operation, not an Actor action.
        from oscombo.collab.data_to_deck.provenance import collect_artifacts
        artifact_items = [
            {"actor": "system", "local_path": "final-business-state/case.sqlite3",
             "source_path": str(root / "db" / spec.FIXTURE_DB)},
            {"actor": "system", "local_path": "logs/ticket_to_resolution_steps.jsonl",
             "source_path": str(root / "ticket_to_resolution_steps.jsonl")},
            {"actor": "system", "local_path": "logs/gui_actions.jsonl",
             "source_path": str(root / "gui_actions.jsonl")},
            {"actor": "system", "local_path": "logs/oracle_result.json",
             "source_path": str(oracle_path)},
        ]
        for screenshot in sorted((root / "screenshots").glob("*.png")):
            artifact_items.append({"actor": "system", "local_path": f"screenshots/{screenshot.name}",
                                   "source_path": str(screenshot)})
        collect_artifacts(root, artifact_items)

        before_reset = reset_owned_run(root, run_id)
        state_after = business_snapshot(root / "db" / spec.FIXTURE_DB)
        reset_hash = business_state_digest(state_after)
        reset_result = {"business_state_hash_matches_initial": reset_hash == before_reset["business_state_sha256"],
                        "review_count": len(CaseStore(root / "db" / spec.FIXTURE_DB).list_reviews()),
                        "audit_count": len(CaseStore(root / "db" / spec.FIXTURE_DB).list_audit()),
                        "pre_reset_snapshot": before_reset["pre_reset_snapshot"],
                        "pre_reset_manifest": before_reset["pre_reset_manifest"],
                        "guest_reset": "Backend reset verified; Guest container removed after smoke"}
        # `refund_count` is explicitly read from its own table rather than
        # inferred from audit events.
        with sqlite3.connect(root / "db" / spec.FIXTURE_DB) as conn:
            reset_result["refund_count"] = conn.execute("select count(*) from refunds").fetchone()[0]
        reset_result["pass"] = (reset_result["business_state_hash_matches_initial"]
                                 and reset_result["review_count"] == 0
                                 and reset_result["refund_count"] == 0
                                 and reset_result["audit_count"] == 0)
        _json_write(root / "reset_verification.json", reset_result)
        if not reset_result["pass"]:
            raise RuntimeError("run-owned backend reset did not restore clean initial business state")
        _json_write(root / "guest_smoke_precleanup.json", {"gate_1": "PASS", "gate_2": gates["gate_2_scripted_gui_e2e"],
                     "oracle_pass": True, "reset_pass": True, "model_called": False,
                     "message_api_integration": "reused Data-to-Deck protocol; separate protocol test covers bidirectional API"})

    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
        if gates["gate_1_guest_web_readiness"] == "PASS" and gates["gate_2_scripted_gui_e2e"] == "NOT_RUN":
            gates["gate_2_scripted_gui_e2e"] = "FAIL_SCRIPTED_GUI_OR_READINESS"
    finally:
        if container_id:
            try:
                cleanup_result = _cleanup_guest(container_id, run_id, root)
            except Exception as exc:
                errors.append({"type": "GuestCleanupError", "message": str(exc), "traceback": traceback.format_exc()})
        for server, thread in ((collab_server, collab_thread), (app_server, app_thread)):
            if server:
                try:
                    server.shutdown()
                    server.server_close()
                    if hasattr(server, "access_log"):
                        server.access_log.close()
                except Exception:
                    pass
            if thread:
                thread.join(timeout=3)
        if collab_server:
            _mark_runtime_resource(root, run_id, "collaboration_service", "stopped", stopped_at_epoch=time.time())
        if app_server:
            _mark_runtime_resource(root, run_id, "case_web_service", "stopped", stopped_at_epoch=time.time())
            _mark_runtime_resource(root, run_id, "http_access_log", "preserved", closed_at_epoch=time.time())
        for name, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value
        try:
            os.chdir(old_cwd)
        except OSError:
            pass
        if env_path_added:
            try:
                sys.path.remove(str(provider))
            except ValueError:
                pass

    report = {"case_id": CASE_ID, "case_version": spec.CASE_VERSION, "run_id": run_id,
              "execution_kind": "scripted_guest_smoke", "model_called": False,
              "status": "PASS" if (oracle_result and oracle_result["joint_business_success"]
                                    and reset_result and reset_result.get("pass") and not errors) else "FAIL_OR_BLOCKED",
              "resource_preflight": preflight, "gates": gates,
              "oracle_pass": bool(oracle_result and oracle_result.get("joint_business_success")),
              "oracle_result_path": str(root / "oracle_result.json") if oracle_result else None,
              "reset_pass": bool(reset_result and reset_result.get("pass")),
              "reset_result_path": str(root / "reset_verification.json") if reset_result else None,
              "cleanup": cleanup_result, "errors": errors,
              "evidence_paths": [str(root / p) for p in ("provenance.json", "gui_actions.jsonl",
                    "ticket_to_resolution_steps.jsonl", "screenshots", "artifact_manifest.json",
                    "oracle_result.json", "reset_verification.json") if (root / p).exists()],
              "gate_3_note": "Not run: this entrypoint intentionally provisions at most one Guest; MA-ID requires separate two-Guest capacity gate."}
    if not (root / "guest_smoke_report.json").exists():
        _json_write(root / "guest_smoke_report.json", report)
    return report
