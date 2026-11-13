"""One owned OSWorld Guest readiness probe on HealthCare."""
from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import sys
import time
import traceback
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    run_id = root.name
    os.environ.update({
        "SWCUB_RUN_ID": run_id,
        "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
        "SWCUB_RESOURCE_LEDGER": str(root / "docker_ledger.jsonl"),
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": args.runtime,
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(root / "overlay"),
    })
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    os.chdir(args.provider)
    from desktop_env.desktop_env import DesktopEnv

    result = {"run_id": run_id, "provider": str(args.provider), "image": str(args.image),
              "runtime": args.runtime, "started_epoch": time.time()}
    env = None
    try:
        started = time.monotonic()
        env = DesktopEnv(provider_name="docker", path_to_vm=str(args.image),
                         cache_dir=str(root / "cache"), os_type="Ubuntu",
                         action_space="pyautogui", headless=False,
                         require_a11y_tree=False, require_terminal=False,
                         client_password="osworld-public-evaluation")
        result["boot_seconds"] = round(time.monotonic() - started, 2)
        container = env.provider.container
        container.reload()
        result["container_id"] = container.id
        labels = container.attrs.get("Config", {}).get("Labels") or {}
        result["container_labels"] = {k: v for k, v in labels.items()
                                      if k in {"org.swcub.project", "org.swcub.run-id"}}
        result["container_environment"] = [x for x in container.attrs.get("Config", {}).get("Env", [])
                                            if x.startswith(("KVM=", "RAM_SIZE=", "CPU_CORES="))]
        shot = env.controller.get_screenshot()
        if not shot:
            raise RuntimeError("empty Guest screenshot")
        from PIL import Image
        ready = False
        for attempt in range(1, 25):
            (root / f"desktop-{attempt:02d}.png").write_bytes(shot)
            with Image.open(io.BytesIO(shot)) as frame:
                gray = frame.convert("L")
                bright_fraction = sum(gray.histogram()[24:]) / (gray.width * gray.height)
            result.setdefault("screenshots", []).append({"attempt": attempt, "bytes": len(shot),
                                                          "bright_fraction": bright_fraction})
            if bright_fraction > 0.02:
                ready = True
                break
            time.sleep(10)
            shot = env.controller.get_screenshot()
        result["screenshot_bytes"] = len(shot)
        for name, script in (
            ("identity", "id; uname -a; ip route"),
            ("desktop_processes", "ps -eo pid,comm,args | grep -E 'gnome-shell|Xorg|Xwayland|gdm' | head -30"),
            ("localhost", "curl --noproxy '*' -sS -m 10 -o /tmp/case3-http-probe -w '%{http_code}' http://10.0.2.2:8766/health"),
        ):
            try:
                result[name] = env.controller.run_bash_script(script, timeout=20)
            except Exception as exc:
                result[name] = {"error_type": type(exc).__name__, "message": str(exc)[:500]}
        result["status"] = "PASS_VISIBLE_DESKTOP" if ready else "GUEST_HTTP_ONLY_BLACK_SCREEN"
    except Exception as exc:
        result["status"] = "INFRA_FAIL"
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:1000]
        result["traceback"] = traceback.format_exc()[-5000:]
    finally:
        if env is not None:
            try:
                env.close()
                result["guest_cleanup"] = "close_returned"
            except Exception as exc:
                result["guest_cleanup"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        result["finished_epoch"] = time.time()
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: result.get(k) for k in
                          ("run_id", "status", "boot_seconds", "screenshot_bytes", "error_type", "guest_cleanup")}))


if __name__ == "__main__":
    main()
