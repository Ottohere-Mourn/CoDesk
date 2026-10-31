"""Real KVM, two-agent Case 4 Lite comparison on isolated or shared desktop."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tarfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from oscombo.collab.timeline_and_assets_lite_v1 import spec
from oscombo.collab.timeline_and_assets_lite_v1.runner import (
    configure_run, evaluate_run, prepare_run, reset_owned_run,
)
from oscombo.collab.data_to_deck.live_pilot import _start_codex_compat_relay
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.guest import Guest
from oscombo.harness.base import AgentContext
from oscombo.harness.external import CodexHarness

from .run_case3_lite_pair_pilot import boot_guest
from .run_case3_lite_single_pilot import guest_shell


MCP_PYTHON = ("/home/mjh/Projects/CoDesk-yuke-osworld-review/runs/"
              "data_to_deck_agent_pilot/cdd-agent-pilot-20261020T155434Z/"
              ".venv/bin/python")
CODEX_BIN = "/home/mjh/.local/share/codesk-case3-tools/codex"


def record(root: Path, name: str, value: dict) -> None:
    with (root / name).open("a", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def open_kdenlive(env, root: Path, key: str) -> None:
    archive_path = root / f"workspace-{key}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted((root / "workspace").rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(root / "workspace").as_posix())
    guest_archive = f"/tmp/case4-workspace-{key}.tar.gz"
    env.setup_controller._upload_file_setup(
        [{"local_path": str(archive_path), "path": guest_archive}])
    guest_shell(env, f"mkdir -p {spec.GUEST_ROOT}; tar -xzf {guest_archive} "
                     f"-C {spec.GUEST_ROOT}", 90)
    project = f"{spec.GUEST_ROOT}/{spec.PROJECT}"
    guest_shell(env, f"nohup kdenlive {project} >/tmp/case4-{key}-kdenlive.log "
                     "2>&1 </dev/null & sleep 2; true", 30)
    welcome_closed = False
    for attempt in range(1, 81):
        time.sleep(4)
        windows = guest_shell(env, "wmctrl -lpG; true", 20)
        record(root, "kdenlive_setup.jsonl", {"key": key, "attempt": attempt,
                                              "windows": windows, "time": time.time()})
        if "Welcome to Kdenlive" in windows and not welcome_closed:
            guest_shell(env, "wmctrl -a 'Welcome to Kdenlive'; xdotool key Return; true", 20)
            welcome_closed = True
            continue
        if "Incorrect project file" in windows:
            raise RuntimeError("native fixture rejected by Kdenlive")
        if "GreenLoop.kdenlive" in windows and "Kdenlive" in windows:
            break
    else:
        diagnostic = guest_shell(
            env, f"ps -C kdenlive -o pid,etime,pcpu,pmem,stat,cmd; "
                 f"tail -60 /tmp/case4-{key}-kdenlive.log; true", 20)
        record(root, "kdenlive_setup.jsonl", {"key": key, "event": "timeout",
                                              "diagnostic": diagnostic, "time": time.time()})
        (root / f"guest_{key}_kdenlive_timeout.png").write_bytes(
            env.controller.get_screenshot())
        raise RuntimeError(f"{key} Kdenlive project window did not appear")
    guest_shell(env, "wmctrl -r 'GreenLoop.kdenlive' -b add,maximized_vert,maximized_horz; "
                     "wmctrl -a 'GreenLoop.kdenlive'; true", 20)
    time.sleep(3)
    (root / f"guest_{key}_initial.png").write_bytes(env.controller.get_screenshot())
    data = env.controller.get_file(project)
    baseline = (root / "workspace" / spec.PROJECT).read_bytes()
    if data != baseline:
        raise RuntimeError(f"{key} Guest project does not match fixed native fixture")


def open_manifest_editor(env, root: Path, run_id: str) -> None:
    profile = f"/tmp/{run_id}-case4-code"
    manifest = f"{spec.GUEST_ROOT}/shot_manifest.txt"
    log = f"/tmp/{run_id}-case4-code.log"
    guest_shell(env, f"nohup code --user-data-dir={profile} --no-sandbox "
                     f"{manifest} >{log} 2>&1 </dev/null & sleep 2; true", 30)
    reopened = False
    for attempt in range(1, 41):
        time.sleep(3)
        windows = guest_shell(env, "wmctrl -lpG; true", 20)
        record(root, "manifest_editor_setup.jsonl", {"attempt": attempt,
                                                       "windows": windows,
                                                       "time": time.time()})
        if "shot_manifest.txt - Visual Studio Code" in windows:
            break
        if "Visual Studio Code" in windows and attempt >= 8 and not reopened:
            guest_shell(env, f"nohup code --reuse-window --user-data-dir={profile} "
                             f"--no-sandbox {manifest} >>{log} 2>&1 </dev/null & true", 30)
            reopened = True
    else:
        raise RuntimeError("A manifest GUI editor did not become ready")
    for _ in range(6):
        active = guest_shell(
            env,
            "for id in $(xdotool search --onlyvisible --name 'shot_manifest.txt' "
            "2>/dev/null); do xdotool windowminimize $id; done; "
            "sleep 1; wmctrl -a 'GreenLoop.kdenlive'; sleep 2; "
            "xdotool getactivewindow getwindowname; true", 20)
        if "GreenLoop.kdenlive" in active:
            break
    else:
        raise RuntimeError("could not leave Kdenlive active with manifest editor hidden")
    (root / "guest_A_manifest_editor_ready.png").write_bytes(
        env.controller.get_screenshot())
    data = env.controller.get_file(manifest)
    if data != (root / "workspace/shot_manifest.txt").read_bytes():
        raise RuntimeError("A Guest manifest does not match fixed fixture")


def make_harness(role: str, env, root: Path, relay_base: str,
                 collab_url: str, actor_timeout: int,
                 desktop_lock_file: Path | None) -> tuple[CodexHarness, AgentContext]:
    actor_relay = relay_base.removesuffix("/v1") + f"/actor/{role}/v1"
    options = {"base_url": actor_relay, "api_key_env": "CODESK_CASE4_RELAY_TOKEN",
               "auth_mode": "env", "codex_bin": CODEX_BIN, "mcp_python": MCP_PYTHON,
               "timeout": actor_timeout, "request_retries": 2, "stream_retries": 2,
               "type_text_mode": "paste", "collaboration": {
                   "actor": role, "url": collab_url,
                   "token_env": f"CODESK_CDD_COLLAB_TOKEN_{role}"}}
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
    parser.add_argument("--condition", required=True, choices=spec.CONDITIONS)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--api-base", default="https://docode.cc/v1")
    parser.add_argument("--actor-timeout", type=int, default=1800)
    parser.add_argument("--desktop-lock", action="store_true")
    parser.add_argument("--setup-only", action="store_true")
    args = parser.parse_args()
    if args.actor_timeout < 300:
        parser.error("--actor-timeout must be at least 300")
    root = args.run_root.resolve()
    run_id = root.name
    prepare_run(root, run_id)
    configure_run(root, args.condition)
    os.environ["SWCUB_OWNER_TOKEN"] = secrets.token_hex(32)
    sys.path.insert(0, str(args.provider))
    sys.path.insert(0, "/home/mjh/Projects/Shared-Workspace-Benchmark-V0")
    os.chdir(args.provider)
    envs = {}
    relay = None
    collab = None
    model_released = False
    result = {"run_id": run_id, "condition": args.condition,
              "status": "STARTED", "started_epoch": time.time(),
              "desktop_lock": args.desktop_lock, "image": str(args.image)}
    try:
        envs["A"] = boot_guest(root, args.overlay_root, run_id, "A",
                              args.image, args.runtime, args.provider)
        open_kdenlive(envs["A"], root, "A")
        if args.condition == "collaborative_isolated":
            envs["B"] = boot_guest(root, args.overlay_root, run_id, "B",
                                  args.image, args.runtime, args.provider)
            open_kdenlive(envs["B"], root, "B")
        else:
            envs["B"] = envs["A"]
        open_manifest_editor(envs["A"], root, run_id)
        result["guest_initial_hashes"] = {
            role: hashlib.sha256(envs[role].controller.get_file(
                f"{spec.GUEST_ROOT}/{spec.PROJECT}")).hexdigest()
            for role in ("A", "B")}
        result["guest_initial_manifest_sha256"] = hashlib.sha256(
            envs["A"].controller.get_file(
                f"{spec.GUEST_ROOT}/shot_manifest.txt")).hexdigest()
        if args.setup_only:
            result["status"] = "SETUP_PASS"
            return

        provider_env = "CODESK_CASE4_PROVIDER_KEY"
        relay_token_env = "CODESK_CASE4_RELAY_TOKEN"
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
            lock = root / f"desktop_{guest_key}.lock" if args.desktop_lock else None
            actors[role] = make_harness(role, envs[role], root, relay_base,
                                        collab_url, args.actor_timeout, lock)
        result["harness_versions"] = {role: pair[0].harness_version
                                       for role, pair in actors.items()}
        release = threading.Event()
        def run_role(role: str) -> dict:
            harness, ctx = actors[role]
            release.wait()
            started = time.time()
            try:
                outcome = harness.run(ctx)
                return {"status": outcome.status, "steps": outcome.steps,
                        "error": outcome.error, "started": started,
                        "ended": time.time()}
            except Exception as exc:
                return {"status": "error", "steps": None,
                        "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                        "traceback": traceback.format_exc()[-2000:],
                        "started": started, "ended": time.time()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {role: pool.submit(run_role, role) for role in ("A", "B")}
            start = time.time()
            for _, ctx in actors.values():
                ctx.t0 = start
            release.set()
            model_released = True
            result["actors"] = {role: future.result() for role, future in futures.items()}
        result["model_episode_status"] = {
            role: item["status"] for role, item in result["actors"].items()}
        result["model_episode_valid"] = all(
            item["status"] in {"done", "max_steps"} for item in result["actors"].values())
        result["status"] = "MODEL_COMPLETED"
        try:
            project = f"{spec.GUEST_ROOT}/{spec.PROJECT}"
            final = envs["B"].controller.get_file(project)
            if final is not None and len(final) <= 1_000_000:
                (root / "workspace" / spec.PROJECT).write_bytes(final)
                result["guest_final_sha256"] = hashlib.sha256(final).hexdigest()
            else:
                result["project_capture_missing_or_oversized"] = True
            manifest_data = envs["A"].controller.get_file(
                f"{spec.GUEST_ROOT}/shot_manifest.txt")
            if manifest_data is not None and len(manifest_data) <= 10_000:
                (root / "workspace/shot_manifest.txt").write_bytes(manifest_data)
                result["guest_final_manifest_sha256"] = hashlib.sha256(manifest_data).hexdigest()
            else:
                result["manifest_capture_missing_or_oversized"] = True
            for role in ("A", "B"):
                (root / f"guest_{role}_final.png").write_bytes(
                    envs[role].controller.get_screenshot())
        except Exception as exc:
            result["artifact_capture_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
            result["status"] = "EVIDENCE_ERROR"
        if result.get("project_capture_missing_or_oversized") or result.get(
                "manifest_capture_missing_or_oversized"):
            result["status"] = "EVIDENCE_ERROR"
        if result.get("guest_final_sha256") and result.get("guest_final_manifest_sha256"):
            try:
                result["oracle"] = evaluate_run(root)
                result["business_status"] = (
                    "PASS" if result["oracle"]["joint_business_success"] else "FAIL")
                if result["status"] == "MODEL_COMPLETED":
                    result["status"] = (result["business_status"] if result["model_episode_valid"]
                                        else "MODEL_INVALID")
            except Exception as exc:
                result["evaluation_error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
                result["status"] = "EVALUATION_ERROR"
    except Exception as exc:
        result.update({"status": "MODEL_OR_INFRA_ERROR" if model_released else "INFRA_FAIL",
                       "error_type": type(exc).__name__,
                       "error": str(exc)[:1000],
                       "traceback": traceback.format_exc()[-4000:]})
    finally:
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
                    f"{role}: {type(exc).__name__}: {str(exc)[:200]}")
        result["guest_cleanup_verified"] = not result.get("cleanup_errors")
        if result.get("oracle") is not None or result["status"] in {
                "EVALUATION_ERROR", "EVIDENCE_ERROR"}:
            try:
                result["reset"] = reset_owned_run(root)
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
