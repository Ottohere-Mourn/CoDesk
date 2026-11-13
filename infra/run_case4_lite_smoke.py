"""Real KVM Guest gate for the native Case 4 Lite Kdenlive project."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tarfile
import time
import traceback
from pathlib import Path

from oscombo.collab.timeline_and_assets_lite_v1.runner import configure_run, prepare_run
from infra.run_case3_lite_single_pilot import guest_shell, wait_visible


GUEST_ROOT = "/home/user/codesk-case4-smoke"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--hold-seconds", type=int, default=1800)
    args = parser.parse_args()
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, "collaborative_shared")
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(root / "docker_ledger.jsonl"),
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": args.runtime,
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(args.overlay_root.resolve()),
    })
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    from desktop_env.desktop_env import DesktopEnv

    result = {"run_id": run_id, "status": "INFRA_FAIL", "started_epoch": time.time(),
              "image": str(args.image), "overlay_root": str(args.overlay_root)}
    env = None
    try:
        env = DesktopEnv(provider_name="docker", path_to_vm=str(args.image),
                         cache_dir=str(root / "guest_cache"), os_type="Ubuntu",
                         action_space="pyautogui", headless=False,
                         require_a11y_tree=False, require_terminal=False,
                         client_password="osworld-public-evaluation")
        (root / "screenshots").mkdir()
        ready = wait_visible(env, root / "screenshots")
        result["desktop_readiness"] = ready
        if not ready["ready"]:
            raise RuntimeError("Guest desktop did not become visible")
        container = env.provider.container
        container.reload()
        result["guest_container_id"] = container.id
        labels = container.attrs.get("Config", {}).get("Labels") or {}
        if labels.get("org.swcub.run-id") != run_id or labels.get("org.swcub.owner-token") != os.environ["SWCUB_OWNER_TOKEN"]:
            raise RuntimeError("Guest ownership labels differ from this run")
        tar_path = root / "workspace.tar.gz"
        with tarfile.open(tar_path, "w:gz") as archive:
            for path in sorted((root / "workspace").rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(root / "workspace").as_posix())
        env.setup_controller._upload_file_setup(
            [{"local_path": str(tar_path), "path": "/tmp/case4-workspace.tar.gz"}])
        result["guest_initial_project_sha256"] = guest_shell(
            env, f"mkdir -p {GUEST_ROOT}; tar -xzf /tmp/case4-workspace.tar.gz -C {GUEST_ROOT}; "
                 f"sha256sum {GUEST_ROOT}/project/GreenLoop.kdenlive", 60)
        result["kdenlive_version"] = guest_shell(env, "kdenlive --version; melt --version | head -1", 30)
        project_arg = "" if args.interactive else f"{GUEST_ROOT}/project/GreenLoop.kdenlive"
        guest_shell(env, f"nohup kdenlive {project_arg} "
                         ">/tmp/case4-kdenlive.log 2>&1 </dev/null & sleep 2; true", 30)
        windows = ""
        welcome_closed = False
        for attempt in range(1, 49):
            time.sleep(5)
            windows = guest_shell(env, "wmctrl -lpG; true", 20)
            (root / f"kdenlive-{attempt:02d}.png").write_bytes(env.controller.get_screenshot())
            with (root / "window_checks.jsonl").open("a") as stream:
                stream.write(json.dumps({"attempt": attempt, "windows": windows,
                                         "time": time.time()}) + "\n")
            if "Welcome to Kdenlive" in windows and not welcome_closed:
                guest_shell(env, "wmctrl -a 'Welcome to Kdenlive'; xdotool key Return; true", 20)
                welcome_closed = True
                continue
            if args.interactive and "Kdenlive" in windows and "Welcome to Kdenlive" not in windows:
                break
            if "GreenLoop" in windows and "Kdenlive" in windows:
                break
        else:
            raise RuntimeError("GreenLoop project did not become visible in Kdenlive")
        time.sleep(10)
        (root / "kdenlive-settled.png").write_bytes(env.controller.get_screenshot())
        windows = guest_shell(env, "wmctrl -lpG; true", 20)
        result["windows"] = windows
        result["app_log_tail"] = guest_shell(env, "tail -80 /tmp/case4-kdenlive.log; true", 20)
        data = env.controller.get_file(f"{GUEST_ROOT}/project/GreenLoop.kdenlive")
        if data != (root / "workspace/project/GreenLoop.kdenlive").read_bytes():
            raise RuntimeError("Guest project differs from the native starter")
        result["guest_project_bytes"] = len(data)
        result["status"] = "INTERACTIVE_READY" if args.interactive else "NATIVE_PROJECT_WINDOW_VISIBLE"
        if args.interactive:
            (root / "interactive_ready").write_text(str(time.time()))
            deadline = time.monotonic() + args.hold_seconds
            while time.monotonic() < deadline and not (root / "interactive_stop").exists():
                time.sleep(2)
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)[:1000],
                       "traceback": traceback.format_exc()[-4000:]})
    finally:
        if env is not None:
            try:
                env.close()
                result["guest_cleanup"] = "close_returned"
            except Exception as exc:
                result["guest_cleanup"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        result["finished_epoch"] = time.time()
        (root / "smoke_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: result.get(k) for k in
                          ("run_id", "status", "kdenlive_version", "error_type", "guest_cleanup")}))


if __name__ == "__main__":
    main()
