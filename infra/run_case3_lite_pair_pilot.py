"""Paired real-Guest Case 3 Lite pilot; same model and harness in both conditions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import docker
import requests

from oscombo.collab.build_and_verify_lite_v1 import spec
from oscombo.collab.build_and_verify_lite_v1.runner import (
    configure_run, evaluate_run, prepare_run, reset_owned_run,
)
from oscombo.collab.data_to_deck.live_pilot import _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.guest import Guest
from oscombo.harness.base import AgentContext
from oscombo.harness.external import CodexHarness

from .run_case3_lite_single_pilot import guest_shell, install_workspace, wait_visible


GUEST_ROOT = "/home/user/codesk-case3-lite"
MCP_PYTHON = ("/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/"
              "data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/"
              ".venv/bin/python")
CODEX_BIN = "/home/mjh/.local/share/codesk-case3-tools/codex"


def record(root: Path, name: str, value: dict) -> None:
    with (root / name).open("a", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def boot_guest(root: Path, overlay_root: Path, run_id: str, key: str,
               image: Path, runtime: str, provider: Path):
    from desktop_env.desktop_env import DesktopEnv
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": runtime,
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str((overlay_root / key).resolve()),
        "SWCUB_RESOURCE_LEDGER": str(root / "docker_ledger.jsonl"),
    })
    started = time.monotonic()
    env = DesktopEnv(provider_name="docker", path_to_vm=str(image),
                     cache_dir=str(root / "guest_cache" / key), os_type="Ubuntu",
                     action_space="pyautogui", headless=False,
                     require_a11y_tree=False, require_terminal=False,
                     client_password="osworld-public-evaluation")
    shot_root = root / "screenshots" / key
    shot_root.mkdir(parents=True)
    ready = wait_visible(env, shot_root)
    if not ready["ready"]:
        raise RuntimeError(f"{key} Guest desktop did not become visible")
    container = env.provider.container
    container.reload()
    labels = container.attrs.get("Config", {}).get("Labels") or {}
    if labels.get("org.swcub.run-id") != run_id or \
            labels.get("org.swcub.owner-token") != os.environ["SWCUB_OWNER_TOKEN"]:
        raise RuntimeError(f"{key} Guest ownership labels do not match this run")
    base_mount = next((mount for mount in container.attrs.get("Mounts", [])
                       if mount.get("Destination") == "/System.qcow2"), None)
    if not base_mount or base_mount.get("RW") is not False or \
            base_mount.get("Source") != str(image):
        raise RuntimeError(f"{key} Guest base image is not mounted read-only")
    result = {"key": key, "container_id": container.id,
              "boot_seconds": round(time.monotonic() - started, 2),
              "readiness": ready, "mounts": container.attrs.get("Mounts", [])}
    (root / f"guest_{key}_boot.json").write_text(json.dumps(result, indent=2))
    return env


def open_editor(env, root: Path, run_id: str, key: str) -> None:
    install_workspace(env, root / "workspace", GUEST_ROOT)
    profile = f"/tmp/{run_id}-{key}-vscode"
    log = f"/tmp/{run_id}-{key}-code.log"
    guest_shell(env, f"nohup code --user-data-dir={profile} --no-sandbox "
                    f"{GUEST_ROOT}/filtering.py >{log} 2>&1 </dev/null & sleep 2; true", 30)
    welcome_closed = False
    file_reopened = False
    for attempt in range(1, 61):
        time.sleep(3)
        windows = guest_shell(env, "wmctrl -lpG; true")
        record(root, "editor_setup.jsonl", {"key": key, "attempt": attempt,
                                             "windows": windows, "time": time.time()})
        if "filtering.py - Visual Studio Code" in windows:
            break
        if ("Visual Studio Code" in windows and attempt >= 8
                and not file_reopened):
            guest_shell(env, f"nohup code --reuse-window --user-data-dir={profile} "
                             f"--no-sandbox {GUEST_ROOT}/filtering.py "
                             f">>{log} 2>&1 </dev/null & true", 30)
            record(root, "editor_setup.jsonl", {"key": key, "attempt": attempt,
                                                 "event": "reopen_file", "time": time.time()})
            file_reopened = True
        if "Welcome - Visual Studio Code" in windows and not welcome_closed:
            guest_shell(env, "wmctrl -a 'Visual Studio Code'; true", 15)
            env.controller.execute_python_command(
                "import pyautogui, time; pyautogui.hotkey('ctrl','w'); time.sleep(3)")
            welcome_closed = True
    else:
        diagnostic = guest_shell(env, f"tail -80 {log}; true", 15)
        record(root, "editor_setup.jsonl", {"key": key, "event": "timeout",
                                             "diagnostic": diagnostic, "time": time.time()})
        raise RuntimeError(f"{key} editor file did not become visible")
    (root / f"guest_{key}_editor.png").write_bytes(env.controller.get_screenshot())


def open_browser(env, root: Path, run_id: str, key: str, role: str,
                 app_url: str, ticket: str, minimize: bool = False,
                 expected_windows: int = 1) -> None:
    guest_shell(env, f"nohup google-chrome --no-first-run --no-default-browser-check "
                    f"--password-store=basic --disable-gpu --disable-dev-shm-usage "
                    f"--user-data-dir=/tmp/{run_id}-{key}-chrome-{role} "
                    f"{app_url}/bootstrap/{ticket} >/tmp/{run_id}-{key}-chrome-{role}.log "
                    "2>&1 </dev/null & sleep 3; true", 30)
    for attempt in range(1, 21):
        time.sleep(5)
        windows = guest_shell(env, "wmctrl -lpG; true")
        shot = env.controller.get_screenshot()
        (root / f"guest_{key}_{role}_browser_{attempt:02d}.png").write_bytes(shot)
        events_path = root / "app_events/web_events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()] \
            if events_path.is_file() else []
        role_logged_in = any(event.get("event") == "bootstrap_login_success" and
                             event.get("actor") == role for event in events)
        if role_logged_in and windows.count("Northstar OrderDesk - Google Chrome") >= expected_windows:
            break
    else:
        raise RuntimeError(f"{key}/{role} Chrome OrderDesk window did not become ready")
    if minimize:
        guest_shell(env, "wmctrl -a 'Northstar OrderDesk'; true", 15)
        active = guest_shell(env, "xdotool getactivewindow getwindowname; true", 15)
        if "Northstar OrderDesk" not in active:
            raise RuntimeError(f"{key}/{role} browser was not active before minimizing")
        guest_shell(env, "xdotool getactivewindow windowminimize; true", 15)
        guest_shell(env, "wmctrl -a 'Visual Studio Code'; true", 15)
    record(root, "browser_setup.jsonl", {"key": key, "role": role,
                                          "windows": windows, "minimized": minimize,
                                          "time": time.time()})


def stabilize_editor(env, root: Path, run_id: str, key: str,
                     restore_browser: bool = False) -> None:
    """Leave A's source file open after delayed VS Code startup settles."""
    browser_id = None
    if restore_browser:
        active = guest_shell(env, "xdotool getactivewindow getwindowname; true", 15)
        if "Northstar OrderDesk" not in active:
            raise RuntimeError("B browser is not active before editor stabilization")
        browser_id = guest_shell(env, "xdotool getactivewindow; true", 15).strip()
        if not browser_id.isdecimal():
            raise RuntimeError("could not capture B browser window ID")
    profile = f"/tmp/{run_id}-{key}-vscode"
    file_path = f"{GUEST_ROOT}/filtering.py"
    log = f"/tmp/{run_id}-{key}-code.log"
    guest_shell(env, f"nohup code --reuse-window --user-data-dir={profile} "
                     f"--no-sandbox {file_path} >>{log} 2>&1 </dev/null & true", 30)
    for attempt in range(1, 21):
        time.sleep(3)
        windows = guest_shell(env, "wmctrl -lpG; true", 20)
        record(root, "editor_stabilization.jsonl", {"key": key, "attempt": attempt,
                                                    "windows": windows, "time": time.time()})
        if "filtering.py - Visual Studio Code" in windows:
            break
    else:
        raise RuntimeError(f"{key} source file not visible after browser setup")
    guest_shell(env, "wmctrl -l | awk '/Welcome - Visual Studio Code/{print $1}' "
                     "| while read id; do wmctrl -ic \"$id\"; done; true", 20)
    windows = guest_shell(env, "sleep 1; wmctrl -lpG; true", 20)
    if "filtering.py - Visual Studio Code" not in windows or \
            "Welcome - Visual Studio Code" in windows:
        raise RuntimeError(f"{key} editor did not settle on filtering.py")
    if restore_browser:
        active = guest_shell(env, f"wmctrl -ia {browser_id}; sleep 1; "
                             "xdotool getactivewindow getwindowname; true", 20)
        if "Northstar OrderDesk" not in active:
            raise RuntimeError("B browser focus was not restored after editor stabilization")
    else:
        active = guest_shell(env, "wmctrl -a 'filtering.py - Visual Studio Code'; "
                             "sleep 1; xdotool getactivewindow getwindowname; true", 20)
        if "filtering.py - Visual Studio Code" not in active:
            raise RuntimeError("A editor focus was not restored after stabilization")
    (root / f"guest_{key}_stabilized.png").write_bytes(env.controller.get_screenshot())


def make_harness(role: str, env, root: Path, relay_base: str,
                 collab_url: str, actor_timeout: int,
                 desktop_lock_file: Path | None = None) -> tuple[CodexHarness, AgentContext]:
    token_env = f"CODESK_CDD_COLLAB_TOKEN_{role}"
    actor_relay = relay_base.removesuffix("/v1") + f"/actor/{role}/v1"
    options = {"base_url": actor_relay, "api_key_env": "CODESK_CASE3_RELAY_TOKEN",
               "auth_mode": "env", "codex_bin": CODEX_BIN, "mcp_python": MCP_PYTHON,
               "timeout": actor_timeout, "request_retries": 2, "stream_retries": 2,
               "type_text_mode": "paste", "collaboration": {
                   "actor": role, "url": collab_url, "token_env": token_env}}
    if desktop_lock_file is not None:
        options["desktop_lock_file"] = str(desktop_lock_file)
    actor_spec = {"harness": "codex", "model": "gpt-6.1-sol",
                  "effort": "medium", "options": options}
    actor_root = root / "actor_runs" / role
    actor_root.mkdir(parents=True)
    instruction = spec.ACTOR_A_INSTRUCTION if role == "A" else spec.ACTOR_B_INSTRUCTION
    ctx = AgentContext(name=role, task_id=spec.CASE_ID, instruction=instruction,
                       guest=Guest(env), out=actor_root, max_steps=spec.PAIR_MAX_STEPS,
                       spec=actor_spec, t0=0)
    harness = CodexHarness(actor_spec)
    harness.prepare(ctx)
    return harness, ctx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True,
                        choices=("collaborative_isolated", "collaborative_shared"))
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--api-base", default="https://docode.cc/v1")
    parser.add_argument("--actor-timeout", type=int, default=1800)
    parser.add_argument("--desktop-lock", action="store_true",
                        help="serialize each tool action plus screenshot on its Guest desktop")
    parser.add_argument("--setup-only", action="store_true")
    args = parser.parse_args()
    if args.actor_timeout < 300:
        parser.error("--actor-timeout must be at least 300 seconds")
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, args.condition)
    (root / "app_events").mkdir()
    os.environ["SWCUB_OWNER_TOKEN"] = secrets.token_hex(32)
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    os.chdir(args.provider)
    client = docker.from_env()
    envs = {}
    app = None
    relay = None
    collab = None
    collab_thread = None
    bridge_stop = threading.Event()
    bridge_thread = None
    result = {"run_id": run_id, "condition": args.condition,
              "status": "STARTED", "started_epoch": time.time(),
              "actor_timeout_sec": args.actor_timeout,
              "desktop_lock": args.desktop_lock}
    try:
        service_dir = Path(__file__).resolve().parent
        app = client.containers.run(
            "python:3.12-slim", ["python", "-B", "/app/serve.py"], detach=True,
            user="1002:1003", network="bridge", read_only=True,
            cap_drop=["ALL"], security_opt=["no-new-privileges"],
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            environment={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
            volumes={
                str(root / "workspace"): {"bind": "/episode/workspace", "mode": "rw"},
                str(root / "secrets/browser_credentials.json"):
                    {"bind": "/episode/credentials.json", "mode": "ro"},
                str(root / "secrets/browser_bootstrap.json"):
                    {"bind": "/episode/bootstrap.json", "mode": "ro"},
                str(root / "app_events"): {"bind": "/episode/events", "mode": "rw"},
                str(service_dir / "serve_case3_lite.py"):
                    {"bind": "/app/serve.py", "mode": "ro"},
                str(service_dir.parent / "oscombo/collab/build_and_verify_lite_v1/webapp.py"):
                    {"bind": "/app/webapp.py", "mode": "ro"},
            }, labels={"codesk.case3": "1", "codesk.run": run_id},
        )
        app.reload()
        result["app_container_id"] = app.id
        app_ip = app.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]
        app_url = f"http://{app_ip}:8766"
        result["app_url"] = app_url
        for _ in range(30):
            try:
                if requests.get(app_url + "/health", timeout=2).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("OrderDesk service did not pass health")

        envs["A"] = boot_guest(root, args.overlay_root, run_id, "A", args.image,
                               args.runtime, args.provider)
        if args.condition == "collaborative_isolated":
            envs["B"] = boot_guest(root, args.overlay_root, run_id, "B", args.image,
                                   args.runtime, args.provider)
        else:
            envs["B"] = envs["A"]
        tickets = json.loads((root / "secrets/browser_bootstrap.json").read_text())
        open_editor(envs["A"], root, run_id, "A")
        open_browser(envs["A"], root, run_id, "A", "A", app_url,
                     tickets["A"], minimize=True)
        if args.condition == "collaborative_isolated":
            open_editor(envs["B"], root, run_id, "B")
        open_browser(envs["B"], root, run_id, "B", "B", app_url, tickets["B"],
                     expected_windows=2 if args.condition == "collaborative_shared" else 1)
        stabilize_editor(envs["A"], root, run_id, "A",
                         restore_browser=args.condition == "collaborative_shared")
        result["guest_initial_hashes"] = {
            role: guest_shell(envs[role], f"sha256sum {GUEST_ROOT}/filtering.py")
            for role in ("A", "B")}
        events = (root / "app_events/web_events.jsonl").read_text()
        if events.count("bootstrap_login_success") != 2:
            raise RuntimeError("both role-scoped browser sessions were not established")
        if args.setup_only:
            result["status"] = "SETUP_PASS"
            return

        guest_file = f"{GUEST_ROOT}/filtering.py"
        host_file = root / "workspace/filtering.py"
        def bridge_once():
            data = envs["A"].controller.get_file(guest_file)
            if not data or len(data) > 100_000:
                return
            try:
                compile(data, guest_file, "exec")
            except (SyntaxError, UnicodeError):
                return
            digest = hashlib.sha256(data).hexdigest()
            if digest != hashlib.sha256(host_file.read_bytes()).hexdigest():
                temporary = host_file.with_suffix(".py.bridge_tmp")
                temporary.write_bytes(data)
                os.replace(temporary, host_file)
                record(root, "workspace_sync.jsonl", {"time": time.time(),
                                                        "sha256": digest, "bytes": len(data)})
        def bridge_loop():
            while not bridge_stop.wait(2):
                try:
                    bridge_once()
                except Exception as exc:
                    record(root, "workspace_sync.jsonl", {"time": time.time(),
                        "error_type": type(exc).__name__})
        bridge_thread = threading.Thread(target=bridge_loop, daemon=True)
        bridge_thread.start()

        provider_env = "CODESK_CASE3_PROVIDER_KEY"
        relay_token_env = "CODESK_CASE3_RELAY_TOKEN"
        os.environ[provider_env] = Path(
            "/home/mjh/.config/codesk/haogpt_case3.key").read_text().strip()
        os.environ[relay_token_env] = secrets.token_urlsafe(32)
        relay, relay_base = _start_codex_compat_relay(
            root, args.api_base, provider_env, os.environ[relay_token_env], relay_token_env)
        os.environ.pop(provider_env, None)
        tokens = json.loads((root / "secrets/collaboration_tokens.json").read_text())
        for role in ("A", "B"):
            os.environ[f"CODESK_CDD_COLLAB_TOKEN_{role}"] = tokens[role]
        store = ProtocolStore(root / "collaboration", run_id)
        collab = make_server(store, tokens, port=0)
        collab_thread = threading.Thread(target=collab.serve_forever, daemon=True)
        collab_thread.start()
        collab_url = f"http://127.0.0.1:{collab.server_port}"
        actors = {}
        for role in ("A", "B"):
            guest_key = role if args.condition == "collaborative_isolated" else "A"
            lock_file = root / f"desktop_{guest_key}.lock" if args.desktop_lock else None
            actors[role] = make_harness(role, envs[role], root, relay_base, collab_url,
                                        args.actor_timeout, lock_file)
        result["harness_versions"] = {role: pair[0].harness_version
                                       for role, pair in actors.items()}
        released = threading.Event()
        def run_role(role):
            harness, ctx = actors[role]
            released.wait()
            started = time.time()
            outcome = harness.run(ctx)
            return {"result": outcome, "started": started, "ended": time.time()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {role: pool.submit(run_role, role) for role in ("A", "B")}
            phase_start = time.time()
            for _, ctx in actors.values():
                ctx.t0 = phase_start
            released.set()
            outcomes = {role: future.result() for role, future in futures.items()}
        protocol_log = root / "collaboration/events.jsonl"
        protocol_events = [json.loads(line) for line in protocol_log.read_text().splitlines()] \
            if protocol_log.is_file() else []
        saved_notice = any(event.get("type") == "message" and
                           event.get("actor") == "A" and
                           event.get("recipient") in ("B", "all") and
                           "saved" in str(event.get("body", "")).casefold()
                           for event in protocol_events)
        bridge_once()
        current_hash = hashlib.sha256(host_file.read_bytes()).hexdigest()
        event_path = root / "app_events/web_events.jsonl"
        web_events = [json.loads(line) for line in event_path.read_text().splitlines()] \
            if event_path.is_file() else []
        final_test_recorded = any(event.get("event") == "browser_test" and
                                  event.get("actor") == "B" and
                                  event.get("filter_source_sha256") == current_hash and
                                  event.get("details", {}).get("method") == "button" and
                                  event.get("details", {}).get("query") == "NW-2402" and
                                  event.get("details", {}).get("status") == "Processing"
                                  for event in web_events)
        b_first = outcomes["B"]["result"]
        if (b_first.status == "done" and b_first.steps < spec.PAIR_MAX_STEPS and
                saved_notice and not final_test_recorded):
            harness_b, ctx_b = actors["B"]
            prompt = ("A's saved revision is available, but the final browser submission "
                      "was not recorded before your prior turn ended. Read project collaboration "
                      "messages, then continue your original browser QA task. "
                      "Use Apply for the staged NW-2402 plus Processing query "
                      "after A's saved change. Your desktop-call budget is unchanged.")
            command = [harness_b.binary, "exec", "resume", "--last", "--all", "--json",
                       "--skip-git-repo-check", prompt]
            resumed = harness_b._run_command(ctx_b, command, timeout=600, append=True)
            record(root, "actor_lifecycle.jsonl", {"actor": "B", "event": "resumed_missing_final_browser_event",
                                                   "time": time.time(), "first_steps": b_first.steps,
                                                   "final_steps": resumed.steps})
            outcomes["B"] = {"result": resumed, "started": outcomes["B"]["started"],
                             "ended": time.time()}
        bridge_stop.set()
        bridge_thread.join(timeout=10)
        bridge_once()
        result["actors"] = {role: {"status": item["result"].status,
                                   "steps": item["result"].steps,
                                   "error": item["result"].error,
                                   "started": item["started"], "ended": item["ended"]}
                            for role, item in outcomes.items()}
        result["guest_final_hash"] = guest_shell(envs["A"], f"sha256sum {guest_file}")
        result["host_final_hash"] = hashlib.sha256(host_file.read_bytes()).hexdigest()
        result["final_screenshots"] = {}
        for role in ("A", "B"):
            path = root / f"guest_{role}_final.png"
            path.write_bytes(envs[role].controller.get_screenshot())
            result["final_screenshots"][role] = str(path)
        result["status"] = "MODEL_COMPLETED" if all(
            item["result"].status in {"done", "max_steps"} for item in outcomes.values()) else "MODEL_INVALID"
    except Exception as exc:
        result["status"] = "INFRA_FAIL"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:1000]
        result["traceback"] = traceback.format_exc()[-4000:]
    finally:
        bridge_stop.set()
        if bridge_thread is not None:
            bridge_thread.join(timeout=10)
        if collab is not None:
            collab.shutdown()
            collab.server_close()
        if relay is not None:
            relay.terminate()
            try:
                relay.wait(timeout=10)
            except Exception:
                relay.kill()
        closed = set()
        for role, env in envs.items():
            if id(env) in closed:
                continue
            closed.add(id(env))
            try:
                env.close()
            except Exception as exc:
                result.setdefault("cleanup_errors", []).append(
                    f"{role} Guest: {type(exc).__name__}: {str(exc)[:200]}")
        if app is not None:
            try:
                app.reload()
                labels = app.attrs.get("Config", {}).get("Labels") or {}
                if app.id == result.get("app_container_id") and labels.get("codesk.run") == run_id:
                    result["app_logs_tail"] = app.logs(tail=30).decode("utf-8", "replace")[-2000:]
                    app.stop(timeout=10)
                    app.remove()
                    result["app_removed"] = True
                else:
                    result["app_cleanup_refused"] = True
            except Exception as exc:
                result.setdefault("cleanup_errors", []).append(
                    f"app: {type(exc).__name__}: {str(exc)[:200]}")
        event_file = root / "app_events/web_events.jsonl"
        if event_file.is_file():
            shutil.copy2(event_file, root / "web_events.jsonl")
        if result["status"] == "MODEL_COMPLETED":
            try:
                result["oracle"] = evaluate_run(root)
                result["status"] = "PASS" if result["oracle"]["joint_business_success"] else "FAIL"
            except Exception as exc:
                result["evaluation_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
                result["status"] = "EVALUATION_ERROR"
            try:
                result["reset"] = reset_owned_run(root, run_id)
            except Exception as exc:
                result["reset_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        result["finished_epoch"] = time.time()
        (root / "pair_pilot_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({key: result.get(key) for key in
                          ("run_id", "condition", "status", "actors", "error_type")},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
