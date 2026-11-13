"""One real Guest single-agent Codex pilot for Case 3 Lite v1."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import shutil
import sys
import tarfile
import threading
import time
import traceback
from pathlib import Path

import docker
import requests
from PIL import Image, ImageChops

from oscombo.collab.build_and_verify_lite_v1.runner import prepare_run, configure_run, evaluate_run
from oscombo.collab.build_and_verify_lite_v1 import spec
from oscombo.collab.data_to_deck.live_pilot import _start_codex_compat_relay
from oscombo.guest import Guest
from oscombo.harness.base import AgentContext
from oscombo.harness.external import CodexHarness


CONTROL_FILTER = '''"""Order query and status filter."""
from __future__ import annotations


def filter_orders(orders, query="", status="All"):
    query = str(query or "").strip().casefold()
    status = str(status or "All")
    return [row for row in orders
            if (status == "All" or row.get("status") == status)
            and (not query or query in " ".join((
                str(row.get("order_id", "")), str(row.get("customer", "")),
                str(row.get("region", "")),
            )).casefold())]
'''


def guest_shell(env, script: str, timeout: int = 60):
    result = env.controller.run_bash_script(script, timeout=timeout)
    if result.get("status") != "success" or result.get("returncode", 0) != 0:
        raise RuntimeError(f"Guest command failed: {result}")
    return result.get("output", "")


def install_workspace(env, workspace: Path, guest_root: str) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in sorted(workspace.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(workspace).as_posix())
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    guest_shell(env, f"set -e; mkdir -p {guest_root}; printf %s {encoded} | base64 -d | tar -xz -C {guest_root}; chmod a-w {guest_root}/data/orders.json {guest_root}/static/* {guest_root}/requirements.md {guest_root}/tests/public_test_plan.json", 90)


def wait_visible(env, root: Path) -> dict:
    observations = []
    for attempt in range(1, 26):
        shot = env.controller.get_screenshot()
        if shot:
            path = root / f"desktop-{attempt:02d}.png"
            path.write_bytes(shot)
            with Image.open(io.BytesIO(shot)) as image:
                hist = image.convert("L").histogram()
                bright = sum(hist[24:]) / (image.width * image.height)
            observations.append({"attempt": attempt, "bytes": len(shot), "bright_fraction": bright})
            if bright > 0.02:
                return {"ready": True, "observations": observations, "last_path": str(path)}
        time.sleep(10)
    return {"ready": False, "observations": observations}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--api-base", default="https://api.haogpt.net/v1")
    parser.add_argument("--control-paste", action="store_true")
    args = parser.parse_args()
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, "single_agent")
    (root / "app_events").mkdir()
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(root / "docker_ledger.jsonl"),
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": args.runtime,
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(args.overlay_root.resolve()),
    })
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    os.chdir(args.provider)
    from desktop_env.desktop_env import DesktopEnv

    docker_client = docker.from_env()
    app = None
    env = None
    relay = None
    sync_stop = threading.Event()
    sync_thread = None
    result = {"run_id": run_id, "status": "STARTED", "started_epoch": time.time()}
    try:
        service_dir = Path(__file__).resolve().parent
        app = docker_client.containers.run(
            "python:3.12-slim", ["python", "-B", "/app/serve.py"], detach=True,
            user="1002:1003", network="bridge", read_only=True,
            cap_drop=["ALL"], security_opt=["no-new-privileges"],
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            environment={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
            volumes={
                str(root / "workspace"): {"bind": "/episode/workspace", "mode": "rw"},
                str(root / "secrets/browser_credentials.json"): {"bind": "/episode/credentials.json", "mode": "ro"},
                str(root / "secrets/browser_bootstrap.json"): {"bind": "/episode/bootstrap.json", "mode": "ro"},
                str(root / "app_events"): {"bind": "/episode/events", "mode": "rw"},
                str(service_dir / "serve_case3_lite.py"): {"bind": "/app/serve.py", "mode": "ro"},
                str(service_dir.parent / "oscombo/collab/build_and_verify_lite_v1/webapp.py"):
                    {"bind": "/app/webapp.py", "mode": "ro"},
            },
            labels={"codesk.case3": "1", "codesk.run": run_id},
        )
        app.reload()
        app_id = app.id
        app_ip = app.attrs["NetworkSettings"]["Networks"]["bridge"]["IPAddress"]
        result["app_container_id"] = app_id
        result["app_ip"] = app_ip
        app_url = f"http://{app_ip}:8766"
        for _ in range(30):
            try:
                health = requests.get(app_url + "/health", timeout=2)
                if health.ok:
                    result["host_app_health"] = health.json()
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("app container did not pass host health")

        started = time.monotonic()
        env = DesktopEnv(provider_name="docker", path_to_vm=str(args.image),
                         cache_dir=str(root / "guest_cache"), os_type="Ubuntu",
                         action_space="pyautogui", headless=False, require_a11y_tree=False,
                         require_terminal=False, client_password="osworld-public-evaluation")
        result["guest_boot_seconds"] = round(time.monotonic() - started, 2)
        result["guest_container_id"] = env.provider.container.id
        result["desktop"] = wait_visible(env, root)
        if not result["desktop"]["ready"]:
            raise RuntimeError("Guest HTTP ready but desktop stayed black")
        result["guest_tools"] = guest_shell(env, "command -v code; command -v google-chrome; command -v xdotool; command -v wmctrl")
        result["guest_app_health"] = guest_shell(env, f"curl --noproxy '*' -sS -m 15 {app_url}/health")
        guest_root = "/home/user/codesk-case3-lite"
        install_workspace(env, root / "workspace", guest_root)
        result["guest_initial_filter_sha256"] = guest_shell(env, f"sha256sum {guest_root}/filtering.py")
        # Setup opens both task applications. These are pre-episode setup actions.
        guest_shell(env, f"nohup code --user-data-dir=/tmp/{run_id}-vscode --no-sandbox {guest_root}/filtering.py >/tmp/{run_id}-code.log 2>&1 </dev/null & sleep 2; true", 30)
        time.sleep(8)
        result["editor_window_list"] = guest_shell(env, "wmctrl -lpG; true")
        (root / "editor-open.png").write_bytes(env.controller.get_screenshot())
        ticket = json.loads((root / "secrets/browser_bootstrap.json").read_text())["S"]
        guest_shell(env, f"nohup google-chrome --no-first-run --no-default-browser-check --password-store=basic --disable-gpu --disable-dev-shm-usage --user-data-dir=/tmp/{run_id}-chrome-S {app_url}/bootstrap/{ticket} >/tmp/{run_id}-chrome.log 2>&1 </dev/null & sleep 3; true", 30)
        result["app_frames"] = []
        visible_frame = False
        with Image.open(result["desktop"]["last_path"]) as base_image:
            desktop_base = base_image.convert("RGB").copy()
        for attempt in range(1, 21):
            time.sleep(5)
            guest_shell(env, "wmctrl -a 'Google Chrome'; true", 15)
            window_list = guest_shell(env, "wmctrl -lpG; true")
            shot = env.controller.get_screenshot()
            path = root / f"apps-{attempt:02d}.png"
            path.write_bytes(shot)
            with Image.open(io.BytesIO(shot)) as frame:
                delta = ImageChops.difference(desktop_base, frame.convert("RGB")).convert("L")
                changed_fraction = sum(delta.histogram()[25:]) / (delta.width * delta.height)
            result["app_frames"].append({"attempt": attempt, "bytes": len(shot),
                                         "changed_fraction": changed_fraction,
                                         "windows": window_list, "path": str(path)})
            if changed_fraction > 0.05 and "Northstar OrderDesk - Google Chrome" in window_list:
                visible_frame = True
                break
        if not visible_frame:
            raise RuntimeError("Chrome OrderDesk page never became visibly ready")
        result["login_window_list"] = guest_shell(env, "wmctrl -lpG; true")
        (root / "browser-logged-in.png").write_bytes(env.controller.get_screenshot())
        guest_shell(env, "wmctrl -a 'Visual Studio Code'; true", 15)
        env.controller.execute_python_command("import pyautogui, time; pyautogui.hotkey('ctrl','w'); time.sleep(3)")
        result["editor_after_welcome_close"] = guest_shell(env, "wmctrl -lpG; true")
        (root / "editor-ready.png").write_bytes(env.controller.get_screenshot())
        result["active_window"] = guest_shell(env, "xdotool getactivewindow getwindowname; true")
        result["guest_gui_diagnostics"] = guest_shell(env,
            f"echo DISPLAY=$DISPLAY; tail -30 /tmp/{run_id}-code.log; tail -30 /tmp/{run_id}-chrome.log; ps -eo pid,comm,args | grep -E 'code|chrome' | head -25", 30)
        events = (root / "app_events/web_events.jsonl").read_text() if (root / "app_events/web_events.jsonl").exists() else ""
        if "Northstar OrderDesk - Google Chrome" not in result["login_window_list"] or "bootstrap_login_success" not in events:
            raise RuntimeError("browser S login failed; model was not launched")

        if args.control_paste:
            import oscombo.desktop_tools as desktop_tools
            def browser_filter(query, method, name):
                guest_shell(env, "wmctrl -a 'Northstar OrderDesk'; true", 15)
                action = ("import pyautogui, time; pyautogui.click(260,538); "
                          "pyautogui.hotkey('ctrl','a'); pyautogui.write(" + repr(query) + ", interval=0.04); "
                          "pyautogui.click(520,538); pyautogui.press('home'); "
                          "pyautogui.press('down'); pyautogui.press('enter'); "
                          + ("pyautogui.click(260,538); pyautogui.press('enter'); "
                             if method == "enter" else "pyautogui.click(700,538); ") +
                          "time.sleep(5)")
                env.controller.execute_python_command(action)
                (root / f"browser-{name}.png").write_bytes(env.controller.get_screenshot())
            browser_filter("Dana", "enter", "before-dana")
            browser_filter("NW-2402", "button", "before-nw2402")
            guest_shell(env, "wmctrl -a 'Visual Studio Code'; true", 15)
            env.controller.execute_python_command(
                "import pyautogui, time; pyautogui.click(900,530); pyautogui.hotkey('ctrl','a')")
            desktop_tools.TYPE_TEXT_MODE = "paste"
            paste = desktop_tools._code("type_text", {"text": CONTROL_FILTER}, [1.5, 1.5])
            env.controller.execute_python_command(desktop_tools.PREFIX.format(cmd=paste))
            env.controller.execute_python_command(
                "import pyautogui, time; pyautogui.hotkey('ctrl','s'); time.sleep(3)")
            (root / "editor-after-paste.png").write_bytes(env.controller.get_screenshot())
            source = env.controller.get_file(f"{guest_root}/filtering.py")
            result["paste_exact"] = source == CONTROL_FILTER.encode()
            result["paste_guest_sha256"] = hashlib.sha256(source or b"").hexdigest()
            if not result["paste_exact"]:
                raise RuntimeError("GUI paste did not preserve exact source bytes")
            host_file = root / "workspace/filtering.py"
            temporary = host_file.with_suffix(".py.bridge_tmp")
            temporary.write_bytes(source)
            os.replace(temporary, host_file)
            browser_filter("Dana", "enter", "after-dana")
            browser_filter("NW-2402", "button", "after-nw2402")
            result["status"] = "CONTROL_COMPLETED"
            return

        guest_file = f"{guest_root}/filtering.py"
        host_file = root / "workspace/filtering.py"
        sync_records = root / "workspace_sync.jsonl"
        def sync_once():
            data = env.controller.get_file(guest_file)
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
                with sync_records.open("a") as log:
                    log.write(json.dumps({"time": time.time(), "sha256": digest, "bytes": len(data)}) + "\n")
        def sync_loop():
            while not sync_stop.wait(2):
                try:
                    sync_once()
                except Exception as exc:
                    with sync_records.open("a") as log:
                        log.write(json.dumps({"time": time.time(), "error": type(exc).__name__}) + "\n")
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()

        provider_env = "CODESK_CASE3_PROVIDER_KEY"
        token_env = "CODESK_CASE3_RELAY_TOKEN"
        os.environ[provider_env] = Path("/home/mjh/.config/codesk/haogpt_case3.key").read_text().strip()
        os.environ[token_env] = secrets.token_urlsafe(32)
        relay, relay_base = _start_codex_compat_relay(root, args.api_base, provider_env,
                                                       os.environ[token_env], token_env)
        os.environ.pop(provider_env, None)
        result["relay_base"] = relay_base
        actor_root = root / "actor_runs/S"
        actor_root.mkdir(parents=True)
        instruction = spec.SINGLE_AGENT_INSTRUCTION
        options = {"base_url": relay_base, "api_key_env": token_env, "auth_mode": "env",
                   "codex_bin": "/home/mjh/.local/share/codesk-case3-tools/codex",
                   "mcp_python": "/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/.venv/bin/python",
                   "redact_env_keys": [provider_env], "timeout": 1200,
                   "request_retries": 2, "stream_retries": 2,
                   "type_text_mode": "paste"}
        actor_spec = {"harness": "codex", "model": "gpt-6.1-sol", "effort": "medium", "options": options}
        ctx = AgentContext(name="S", task_id=spec.CASE_ID, instruction=instruction,
                           guest=Guest(env), out=actor_root, max_steps=40,
                           spec=actor_spec, t0=time.time())
        harness = CodexHarness(actor_spec)
        harness.prepare(ctx)
        result["harness_version"] = harness.harness_version
        model_result = harness.run(ctx)
        result["actor"] = {"status": model_result.status, "steps": model_result.steps,
                           "error": model_result.error, "extra": model_result.extra}
        sync_stop.set()
        sync_thread.join(timeout=10)
        sync_once()
        result["guest_final_filter_sha256"] = guest_shell(env, f"sha256sum {guest_file}")
        result["host_final_filter_sha256"] = hashlib.sha256(host_file.read_bytes()).hexdigest()
        result["status"] = "MODEL_COMPLETED" if model_result.status in {"done", "max_steps"} else "MODEL_INVALID"
    except Exception as exc:
        result["status"] = "INFRA_FAIL"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:1000]
        result["traceback"] = traceback.format_exc()[-4000:]
    finally:
        sync_stop.set()
        if sync_thread is not None:
            sync_thread.join(timeout=10)
        if relay is not None:
            relay.terminate()
            try:
                relay.wait(timeout=10)
            except Exception:
                relay.kill()
        if env is not None:
            try:
                env.close()
                result["guest_closed"] = True
            except Exception as exc:
                result["guest_close_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        if app is not None:
            try:
                result["app_logs_tail"] = app.logs(tail=30).decode("utf-8", "replace")[-3000:]
                app.reload()
                labels = app.attrs.get("Config", {}).get("Labels") or {}
                if app.id == result.get("app_container_id") and labels.get("codesk.run") == run_id:
                    app.stop(timeout=10)
                    app.remove()
                    result["app_removed"] = True
                else:
                    result["app_cleanup_refused"] = True
            except Exception as exc:
                result["app_cleanup_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        event_file = root / "app_events/web_events.jsonl"
        if event_file.is_file():
            shutil.copy2(event_file, root / "web_events.jsonl")
        if result["status"] in {"MODEL_COMPLETED", "CONTROL_COMPLETED"}:
            try:
                result["oracle"] = evaluate_run(root)
                prefix = "CONTROL_" if result["status"] == "CONTROL_COMPLETED" else ""
                result["status"] = prefix + ("PASS" if result["oracle"]["joint_business_success"] else "FAIL")
            except Exception as exc:
                result["evaluation_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        result["finished_epoch"] = time.time()
        (root / "pilot_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: result.get(k) for k in
                          ("run_id", "status", "guest_boot_seconds", "app_ip", "active_window", "error_type")}))


if __name__ == "__main__":
    main()
