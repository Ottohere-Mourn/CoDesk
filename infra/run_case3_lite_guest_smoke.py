"""One real Guest app/editor/browser setup smoke for Case 3 Lite v1."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import secrets
import shutil
import sys
import tarfile
import time
import traceback
from pathlib import Path

import docker
import requests
from PIL import Image, ImageChops

from oscombo.collab.build_and_verify_lite_v1.runner import prepare_run, configure_run


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
    args = parser.parse_args()
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, "collaborative_shared")
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
        ticket = json.loads((root / "secrets/browser_bootstrap.json").read_text())["B"]
        guest_shell(env, f"nohup google-chrome --no-first-run --no-default-browser-check --password-store=basic --disable-gpu --disable-dev-shm-usage --user-data-dir=/tmp/{run_id}-chrome-B {app_url}/bootstrap/{ticket} >/tmp/{run_id}-chrome.log 2>&1 </dev/null & sleep 3; true", 30)
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
        result["status"] = "PASS_APPS_READY" if "Northstar OrderDesk - Google Chrome" in result["login_window_list"] and "bootstrap_login_success" in events else "APP_WINDOWS_NOT_VERIFIED"
    except Exception as exc:
        result["status"] = "INFRA_FAIL"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:1000]
        result["traceback"] = traceback.format_exc()[-4000:]
    finally:
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
        result["finished_epoch"] = time.time()
        (root / "guest_smoke_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: result.get(k) for k in
                          ("run_id", "status", "guest_boot_seconds", "app_ip", "active_window", "error_type")}))


if __name__ == "__main__":
    main()
