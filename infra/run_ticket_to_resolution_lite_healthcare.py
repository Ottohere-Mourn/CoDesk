#!/usr/bin/env python3
"""Run Case 2 Lite on HealthCare's Docker/KVM OSWorld provider.

The task, browser GUI, collaboration protocol, and Oracle remain the same as
the native-QEMU pilot.  Only the service route and desktop lifecycle differ.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")

import run_ticket_to_resolution_lite_native as native
import run_ticket_to_resolution_lite_model as model

OSWORLD = Path("/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1")
IMAGE = Path("/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2")
RUNTIME = "swcub/osworld-v2.1-qemu-runtime:local"
KEY_FILE = Path("/home/mjh/.config/codesk/haogpt_case3.key")
MCP_PYTHON = Path("/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/.venv/bin/python")
CODEX_BIN = Path("/home/mjh/.local/share/codesk-case3-tools/codex")
RUNS = Path("/home/mjh/Projects/CoDesk-case2-healthcare/runs/ticket_to_resolution/healthcare")
SERVICE_HOST = "172.17.0.1"
SERVICE_PORT = 8765


def configure(root: Path, run_id: str) -> None:
    global SERVICE_PORT
    with socket.socket() as reservation:
        reservation.bind(("0.0.0.0", 0))
        SERVICE_PORT = reservation.getsockname()[1]
    native.OSWORLD = OSWORLD
    native.IMAGE = IMAGE
    native.GUEST_SERVICE_HOST = SERVICE_HOST
    native.GUEST_SERVICE_PORT = SERVICE_PORT
    native.RUNS = RUNS
    os.environ.update({
        "OSWORLD_DIR": str(OSWORLD),
        "OSCOMBO_BACKEND": "docker",
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": __import__("secrets").token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(root / "docker_ledger.jsonl"),
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": RUNTIME,
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(root / "overlays"),
        "CODESK_TTR_MCP_PYTHON": str(MCP_PYTHON),
        "CODESK_TTR_CODEX_BIN": str(CODEX_BIN),
        "CODESK_TTR_PROMOTE_TOOL_IMAGE": "1",
        "CODESK_TTR_REPEAT_TASK": "1",
    })
    native._bypass_proxy_for_local_services()


def load_model_config():
    if KEY_FILE.is_symlink() or not KEY_FILE.is_file() or KEY_FILE.stat().st_mode & 0o077:
        raise PermissionError("private HealthCare model key is missing or not mode 0600")
    config = {
        "api_key": KEY_FILE.read_text(encoding="utf-8").strip(),
        "base_url": "https://api.haogpt.net/v1",
        "fallback_base_url": "https://docode.cc/v1",
    }
    return config, {"model_requested": native.MODEL,
                    "preferred_endpoint": config["base_url"],
                    "fallback_endpoint": config["fallback_base_url"]}


def start_services(root: Path, run_id: str, credentials: dict[str, str], variant: str):
    from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server as make_protocol_server
    from oscombo.collab.ticket_to_resolution.webapp import make_server as make_case_server

    case = make_case_server(root / "db" / "case.sqlite3", credentials,
                            host="0.0.0.0", port=SERVICE_PORT, variant=variant)
    case_thread = threading.Thread(target=case.serve_forever, daemon=True)
    case_thread.start()
    store = ProtocolStore(root / "collaboration", run_id)
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text())
    original_read = store.messages
    read_lock = threading.Lock()

    def audited_read(actor: str, after: float = 0.0):
        messages = original_read(actor, after)
        native._append(root / "collaboration_reads.jsonl", {
            "time_unix": time.time(), "reader": actor, "after_unix": after,
            "message_ids": [m.get("message_id") for m in messages],
            "senders": [m.get("actor") for m in messages],
        }, read_lock)
        return messages

    store.messages = audited_read
    protocol = make_protocol_server(store, tokens, host="127.0.0.1", port=0)
    protocol_thread = threading.Thread(target=protocol.serve_forever, daemon=True)
    protocol_thread.start()
    return case, case_thread, protocol, protocol_thread, SERVICE_PORT


def close_guests(environments):
    rows = []
    for key, env in reversed(list(environments.items())):
        provider = getattr(env, "provider", None)
        container = getattr(provider, "container", None)
        container_id = getattr(container, "id", None)
        error = None
        try:
            env.close()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
        alive = False
        if container is not None:
            try:
                container.reload()
                alive = container.status == "running"
            except Exception:
                pass
        overlay_error = None
        overlay_exists = False
        overlay_name = Path(getattr(provider, "environment", {}).get("SWCUB_VM_OVERLAY", "")).name
        overlay_dir_value = os.environ.get("SWCUB_OSWORLD_OVERLAY_HOST_DIR", "")
        if overlay_name.startswith("osworld-") and overlay_name.endswith(".qcow2") and overlay_dir_value:
            overlay_dir = Path(overlay_dir_value).resolve()
            overlay = overlay_dir / overlay_name
            if alive:
                overlay_exists = overlay.exists()
            elif overlay.is_symlink():
                overlay_error = "overlay path is a symlink"
                overlay_exists = True
            else:
                try:
                    overlay.unlink(missing_ok=True)
                except OSError as exc:
                    overlay_error = f"{type(exc).__name__}: {exc}"[:300]
                overlay_exists = overlay.exists()
        rows.append({"guest_key": key, "container_id": container_id,
                     "qemu_alive_after_close": alive,
                     "overlay_exists_after_close": overlay_exists,
                     "overlay_cleanup_error": overlay_error,
                     "forwarded_ports_released": {},
                     "close_error_type": error})
    return rows


def boot_desktops(root: Path, run_id: str, condition: str, app_port: int, report: dict):
    from oscombo.osworld import activate
    from oscombo.combo import boot
    from oscombo.guest import Guest

    activate()
    if condition == "collaborative_shared":
        keys, actor_keys = ("shared",), {"A": "shared", "B": "shared"}
    elif condition == "collaborative_isolated":
        keys, actor_keys = ("A", "B"), {"A": "A", "B": "B"}
    else:
        keys, actor_keys = ("S",), {"S": "S"}
    envs, guests = {}, {}
    try:
        for key in keys:
            report["status"] = "GUEST_BOOT"
            report["stage"] = f"booting_guest_{key}"
            native._write_json(root / "progress.json", report)
            started = time.monotonic()
            cache = root / "cache" / key
            cache.mkdir(parents=True, exist_ok=True)
            env = boot(str(IMAGE), str(cache))
            envs[key] = env
            guest = Guest(env)
            guests[key] = guest
            health = native._guest_health_probe(guest)
            report.setdefault("guest_http_probes", {})[key] = [health]
            if health.get("returncode", 0) != 0 or '"ready":true' not in health.get("output", ""):
                raise RuntimeError(f"Guest {key} cannot reach the shared Case Desk service: {health}")
            ready = native._wait_for_guest_desktop(guest, root, key, report)
            report.setdefault("setup", {})[key] = {
                "boot_s": round(time.monotonic() - started, 2),
                "desktop_readiness": ready,
                "provider": "docker-kvm",
                "container_id": env.provider.container.id,
                "host_case_service_reachable": True,
            }
            native._write_json(root / "progress.json", report)
    except Exception:
        report["guest_setup_failure_cleanup"] = {"guests": close_guests(envs)}
        raise
    report["guest_count"] = len(guests)
    report["role_to_guest"] = actor_keys
    return envs, guests, actor_keys


def boot_and_prepare(root, run_id, condition, variant, report, prepared=False):
    if not prepared:
        native._prepare_episode(root, run_id, condition,
                                f"http://{SERVICE_HOST}:{SERVICE_PORT}/login")
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text())
    case = protocol = case_thread = protocol_thread = None
    envs = {}
    try:
        case, case_thread, protocol, protocol_thread, port = start_services(
            root, run_id, credentials, variant)
        envs, guests, actor_keys = boot_desktops(root, run_id, condition, port, report)
        profiles, browser_report = native._prepare_browsers(
            root, run_id, condition, credentials, guests, actor_keys, port)
        expected = ["S"] if condition == "single_agent" else ["A", "B"]
        sessions = sorted(item["actor"] for item in case.sessions.values())
        if sessions != expected:
            raise RuntimeError(f"signed-in browser roles differ from expected: {sessions}")
        report["browsers"] = browser_report
        report["identity_check"] = {"session_actors": sessions,
                                    "browser_profiles": profiles,
                                    "distinct_sessions": len(case.sessions) == len(expected)}
        report["shared_backend"] = {
            "database_path": str(root / "db" / "case.sqlite3"),
            "host_service_bind": "0.0.0.0",
            "guest_address": f"http://{SERVICE_HOST}:{SERVICE_PORT}",
            "backend_topology": "one host service and one run-scoped SQLite database",
        }
        return (envs, guests, actor_keys, case, case_thread, protocol,
                protocol_thread, port, profiles, credentials)
    except Exception:
        report["setup_failure_cleanup"] = {"guests": close_guests(envs)}
        native._close_server(protocol, protocol_thread)
        native._close_server(case, case_thread)
        raise


def patch_runtime(root: Path, run_id: str) -> None:
    configure(root, run_id)
    native._load_model_config = load_model_config
    native._start_services = start_services
    native._boot_desktops = boot_desktops
    native._boot_and_prepare = boot_and_prepare
    native._close_guests = close_guests


def run_controls(args) -> int:
    from oscombo.collab.ticket_to_resolution.lite_v1 import CASE_ID, CASE_VERSION
    root = args.run_root
    native._prepare_episode(root, args.run_id, args.condition,
                            f"http://{SERVICE_HOST}:{SERVICE_PORT}/login")
    report = {"run_id": args.run_id, "case_id": CASE_ID,
              "case_version": CASE_VERSION, "condition": args.condition,
              "provider": "docker-kvm", "acceleration": "KVM",
              "mode": "real_guest_scripted_controls", "status": "STARTING",
              "started_unix": time.time(), "setup": {}, "controls": {},
              "base_image": str(IMAGE), "base_image_fingerprint_before": native._image_fingerprint()}
    native._write_json(root / "progress.json", report)
    envs = {}
    case = protocol = case_thread = protocol_thread = None
    port = None
    try:
        (envs, guests, actor_keys, case, case_thread, protocol,
         protocol_thread, port, profiles, _) = boot_and_prepare(
             root, args.run_id, args.condition, "lite-v1", report, prepared=True)
        report["status"] = "CONTROLS_RUNNING"
        native._write_json(root / "progress.json", report)
        report["controls"] = native._run_scripted_controls(
            root, args.run_id, args.condition, guests, actor_keys,
            profiles, protocol, port, tuple(args.scenarios))
        outcomes = report["controls"]
        positive = outcomes.get("positive", {})
        negative = outcomes.get("negative", {})
        p = positive.get("oracle", {})
        n = negative.get("oracle", {})
        report["controls_pass"] = bool(
            (not positive or (p.get("joint_business_success")
                              and positive.get("actor_steps") == {"A": 6, "B": 7}
                              and positive.get("message_read_by_B")
                              and p.get("process_evidence", {}).get("review_opened_in_gui_by_B")))
            and (not negative or (not n.get("joint_business_success")
                                  and negative.get("actor_steps") == {"A": 6, "B": 4}
                                  and negative.get("message_read_by_B")
                                  and n.get("observed", {}).get("refund_count") == 0
                                  and n.get("protected_state_pass")))
        )
        report["status"] = "CONTROL_PASS" if report["controls_pass"] else "CONTROL_FAIL"
    except Exception as exc:
        report["status"] = "INFRA_FAIL"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc),
                             "traceback": traceback.format_exc()}
    finally:
        native._close_server(protocol, protocol_thread)
        native._close_server(case, case_thread)
        report["cleanup"] = close_guests(envs)
        report["cleanup_verified"] = all(
            not row["qemu_alive_after_close"]
            and not row["overlay_exists_after_close"]
            and row["overlay_cleanup_error"] is None
            and row["close_error_type"] is None
            for row in report["cleanup"])
        report["service_port_released"] = native._port_released(port) if port else None
        report["protocol_port_released"] = (
            native._port_released(protocol.server_port) if protocol else None)
        report["cleanup_verified"] = bool(
            report["cleanup_verified"] and report["service_port_released"]
            and report["protocol_port_released"])
        report["base_image_fingerprint_after"] = native._image_fingerprint()
        report["base_image_unchanged"] = (
            report["base_image_fingerprint_before"] == report["base_image_fingerprint_after"])
        report["elapsed_total_s"] = round(time.time() - report["started_unix"], 2)
        native._write_json(root / "result.json", report)
        print(json.dumps({"status": report["status"], "run_root": str(root),
                          "controls_pass": report.get("controls_pass"),
                          "cleanup_verified": report["cleanup_verified"]}), flush=True)
    return 0 if report.get("controls_pass") and report["cleanup_verified"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("controls", "model"), required=True)
    parser.add_argument("--condition", choices=("single_agent", "collaborative_isolated",
                                             "collaborative_shared"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--scenarios", nargs="+", choices=("positive", "negative"),
                        default=("positive", "negative"))
    parser.add_argument("--step-budget", type=int)
    parser.add_argument("--wall-seconds", type=int)
    parser.add_argument("--mitigation", choices=("none", "input-lock"), default="none")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--no-reset-after", dest="reset_after", action="store_false")
    parser.set_defaults(reset_after=True)
    args = parser.parse_args()
    if args.mode == "controls" and args.condition == "single_agent":
        parser.error("scripted controls need A and B roles")
    args.run_root = (args.run_root or RUNS / args.run_id).resolve()
    if args.run_root.exists() and any(args.run_root.iterdir()):
        raise FileExistsError("run root is not empty; use a fresh run ID")
    args.run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    patch_runtime(args.run_root, args.run_id)
    if args.mode == "controls":
        return run_controls(args)
    code = model.run_episode(args)
    result_path = args.run_root / "result.json"
    if result_path.is_file():
        result = json.loads(result_path.read_text())
        result.update({"provider": "docker-kvm", "acceleration": "KVM",
                       "base_image_hash_basis": "same-size pinned HealthCare image; fingerprint checked before and after"})
        native._write_json(result_path, result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
