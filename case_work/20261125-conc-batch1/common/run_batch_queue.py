"""Dynamic, resource-gated shared Guest queue for the approved CONC batch.

Jobs are newline-delimited JSON in a manifest and may be appended while this
process is running.  The queue never deletes or reuses a run directory.  Before
each Guest launch it rechecks RAM, swap activity, /dev/shm, RAID/root disk,
Docker, and KVM; capacity is capped at eight and throttled under pressure.
API credentials are loaded only into memory from the server's private
providers.env and are never written to the queue state or run manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

GIB = 1024 ** 3
PRIMARY_BASE = "https://api.haogpt.net/v1"
FALLBACK_BASE = "https://sub2api-hk.ziplab.co/v1"


def read_private_env(path: Path, name: str) -> str | None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in (chr(34), chr(39)):
                value = value[1:-1]
            return value or None
    return None


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            out[key] = int(parts[0]) * 1024
    return out


def _vmstat() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/vmstat").read_text().splitlines():
        bits = line.split()
        if len(bits) == 2 and bits[0] in {"pswpin", "pswpout"} and bits[1].isdigit():
            values[bits[0]] = int(bits[1])
    return values.get("pswpin", 0), values.get("pswpout", 0)


def preflight(max_guests: int, previous_swap: tuple[int, int] | None) -> tuple[dict[str, Any], tuple[int, int]]:
    mem = _meminfo()
    root = shutil.disk_usage("/").free
    raid = shutil.disk_usage("/mnt/raid1").free
    shm = shutil.disk_usage("/dev/shm").free
    swap_used = mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)
    swap_in, swap_out = _vmstat()
    swap_active = previous_swap is not None and (swap_in > previous_swap[0] or swap_out > previous_swap[1])
    docker = subprocess.run(["docker", "info", "--format", "{{.DockerRootDir}}"],
                            capture_output=True, text=True, timeout=10)
    docker_ok = docker.returncode == 0 and bool(docker.stdout.strip())
    kvm = Path("/dev/kvm").exists()
    if not docker_ok or not kvm:
        capacity = 0
    else:
        caps = [
            (mem.get("MemAvailable", 0) - 32 * GIB) // (8 * GIB),
            (root - 16 * GIB) // (2 * GIB),
            (shm - 16 * GIB) // (10 * GIB),
            (raid - 100 * GIB) // (10 * GIB),
        ]
        capacity = max(0, min(max_guests, *(int(x) for x in caps)))
        if swap_used > mem.get("SwapTotal", 0) * 0.90:
            capacity = min(capacity, 1 if swap_active else 4)
    details = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mem_available_gib": round(mem.get("MemAvailable", 0) / GIB, 1),
        "swap_used_gib": round(swap_used / GIB, 2),
        "swap_total_gib": round(mem.get("SwapTotal", 0) / GIB, 2),
        "swap_io_active_since_prior_probe": bool(swap_active),
        "root_free_gib": round(root / GIB, 1),
        "raid_free_gib": round(raid / GIB, 1),
        "shm_free_gib": round(shm / GIB, 1),
        "docker_ok": docker_ok,
        "docker_root": docker.stdout.strip() if docker_ok else None,
        "kvm_exists": kvm,
        "capacity": capacity,
    }
    return details, (swap_in, swap_out)


def load_jobs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    jobs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue  # an in-progress append is retried on the next poll
        if isinstance(item, dict) and item.get("run_id") and item.get("tasks"):
            jobs.append(item)
    return jobs


def _redact(text: str, key: str) -> str:
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)


def _pump(proc: subprocess.Popen[str], log_path: Path, key: str) -> None:
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(_redact(line, key))
            log.flush()


def _safe_result(path: Path, key: str) -> dict[str, Any]:
    result_path = path / "result.json"
    if not result_path.is_file():
        return {"result_present": False}
    raw = result_path.read_text(encoding="utf-8", errors="replace")
    safe = _redact(raw, key)
    if safe != raw:
        result_path.write_text(safe, encoding="utf-8")
    try:
        data = json.loads(safe)
    except json.JSONDecodeError:
        return {"result_present": True, "result_json_valid": False}
    return {"result_present": True, "result_json_valid": True,
            "scores": data.get("scores"), "error": str(data.get("error") or "")[:300],
            "agents": {k: {"status": v.get("status"), "steps": v.get("steps")}
                       for k, v in (data.get("agents") or {}).items()}}


def _install_case_modules(runner_source: Path, osworld: Path) -> None:
    """Install only new, uniquely named case helpers; never overwrite a mismatch."""
    source = runner_source / "evaluation_examples" / "task_class"
    target = osworld / "evaluation_examples" / "task_class"
    target.mkdir(parents=True, exist_ok=True)
    for src in sorted(source.glob("*.py")):
        if src.name == "__init__.py":
            continue
        dst = target / src.name
        if dst.exists():
            src_hash = hashlib.sha256(src.read_bytes()).digest()
            dst_hash = hashlib.sha256(dst.read_bytes()).digest()
            if src_hash != dst_hash:
                raise FileExistsError(f"refusing to overwrite a different OSWorld module: {dst.name}")
            continue
        shutil.copyfile(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--queue-root", type=Path, required=True)
    ap.add_argument("--runner-root", type=Path, required=True)
    ap.add_argument("--osworld", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--max-guests", type=int, default=8)
    ap.add_argument("--poll-s", type=float, default=15)
    ap.add_argument("--idle-exit-s", type=float, default=4 * 60 * 60)
    args = ap.parse_args()

    manifest, root = args.manifest.resolve(), args.queue_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "queue_state.json"
    if state_path.exists():
        raise FileExistsError(f"queue state already exists: {state_path}")
    credential_file = Path("/home/mjh/.config/codesk/providers.env")
    key = read_private_env(credential_file, "SUB2API_API_KEY")
    if not key:
        raise RuntimeError("approved secondary provider credential is unavailable; value suppressed")
    endpoint = FALLBACK_BASE  # primary HaoGPT rejected the Responses computer tool (HTTP 400).
    pending: list[dict[str, Any]] = []
    seen: set[str] = set()
    active: dict[str, dict[str, Any]] = {}
    history: dict[str, Any] = {}
    previous_swap: tuple[int, int] | None = None
    last_new_job = time.monotonic()

    def save_state(preflight_record: dict[str, Any] | None = None) -> None:
        state = {"updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "endpoint_alias": "sub2api-hk", "model": "gpt-6-sol",
                 "max_guests": args.max_guests, "active": list(active),
                 "pending": [j["run_id"] for j in pending], "jobs": history,
                 "latest_preflight": preflight_record}
        tmp = state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(state_path)

    while True:
        for job in load_jobs(manifest):
            run_id = str(job["run_id"])
            if run_id in seen:
                continue
            seen.add(run_id)
            pending.append(job)
            history[run_id] = {"status": "queued", "case": job.get("case", "unknown")}
            last_new_job = time.monotonic()

        current, previous_swap = preflight(args.max_guests, previous_swap)
        # Persist each preflight, even if resources temporarily force the queue to wait.
        save_state(current)

        for run_id, item in list(active.items()):
            proc: subprocess.Popen[str] = item["proc"]
            if proc.poll() is None:
                continue
            if item.get("pump"):
                item["pump"].join(timeout=10)
            exit_code = proc.returncode
            summary = _safe_result(Path(item["out"]), key)
            status = "completed" if exit_code == 0 else "failed"
            history[run_id] = {"status": status, "exit_code": exit_code, **summary}
            del active[run_id]
            print(f"[{time.strftime('%H:%M:%S')}] {status} {run_id} exit={exit_code} agents={summary.get('agents')}", flush=True)

        if pending and len(active) < int(current["capacity"]):
            job = pending[0]
            run_id = str(job["run_id"])
            out = root / "runs" / run_id
            if out.exists():
                history[run_id] = {"status": "skipped_existing_output", "output": str(out)}
                pending.pop(0)
                save_state(current)
                continue
            runner_source = Path(job["runner_source"]).resolve()
            assets = Path(job["assets"]).resolve()
            base_url = str(job.get("base_url") or FALLBACK_BASE).rstrip("/")
            if base_url != endpoint:
                history[run_id] = {"status": "rejected_endpoint", "endpoint_alias": "suppressed"}
                pending.pop(0)
                save_state(current)
                continue
            _install_case_modules(runner_source, args.osworld.resolve())
            out.mkdir(parents=True)
            (out / "eval-artifacts").mkdir()
            wall_s = int(job.get("role_wall_s", 7200))
            agents = [{"harness": "step", "policy": "paragui_batch.stateless_cua:make",
                       "model": "gpt-6-sol", "base_url": endpoint, "effort": "medium",
                       "options": {"wall_s": wall_s, "step_pause": 0.5, "action_pause": 0.4,
                                   "chain_steps": 0, "save_screenshots": True}}
                      for _ in range(2)]
            spec_path = out / "agents.json"
            spec_path.write_text(json.dumps(agents, indent=2), encoding="utf-8")
            env = dict(os.environ)
            env.update({
                "OSWORLD_DIR": str(args.osworld.resolve()),
                "PARAGUI_TASK_ASSETS": str(assets),
                # The pre-existing OSWorld venv lacks the Debian-provided
                # `requests` module although that host package is already
                # present. A sitecustomize shim appends system dist-packages
                # after the active venv, preserving its compiled Pillow and
                # other packages. No package installation or network access.
                "PYTHONPATH": os.pathsep.join([
                    "/mnt/raid1/mjh/codesk-runs/conc-batch1-20261125/python-compat-v1",
                    str(runner_source), str(args.runner_root.resolve()), str(args.osworld.resolve())]),
                "OSCOMBO_BACKEND": "docker",
                "OSCOMBO_GUEST_IMAGE": args.image,
                "OPENAI_API_KEY": key,
                "OPENAI_BASE_URL": endpoint,
                "PYTHONUNBUFFERED": "1",
                "CONC01_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC02_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC03_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC04_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC05_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC06_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC07_EVAL_OUT": str(out / "eval-artifacts"),
                "CONC08_EVAL_OUT": str(out / "eval-artifacts"),
            })
            # Preserve the venv entrypoint symlink. Path.resolve() follows it
            # to the base interpreter and silently bypasses this venv's
            # site-packages (which produced false dependency failures).
            cmd = [str(args.python.expanduser()), "-m", "oscombo", "run", "--mode", "parallel",
                   "--tasks", *[str(x) for x in job["tasks"]], "--out", str(out),
                   "--agents", str(spec_path), "--image", args.image, "--max-steps", "0",
                   "--setup-settle", str(float(job.get("setup_settle_s", 20))),
                   "--label", f"case={job.get('case', 'unknown')}",
                   "--label", "run_mode=shared", "--label", "step_cap=none",
                   "--label", "endpoint_alias=sub2api-hk"]
            proc = subprocess.Popen(cmd, cwd=args.osworld.resolve(), env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    bufsize=1, start_new_session=True)
            pump = threading.Thread(target=_pump, args=(proc, out / "driver.log", key), daemon=True)
            pump.start()
            active[run_id] = {"proc": proc, "pump": pump, "out": out, "started": time.monotonic()}
            history[run_id] = {"status": "running", "pid": proc.pid, "case": job.get("case"),
                               "output": str(out), "preflight": current}
            pending.pop(0)
            print(f"[{time.strftime('%H:%M:%S')}] started {run_id} preflight_capacity={current['capacity']}", flush=True)
            save_state(current)
            continue

        if not pending and not active and time.monotonic() - last_new_job > args.idle_exit_s:
            history["queue"] = {"status": "idle_exit", "idle_s": args.idle_exit_s}
            save_state(current)
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
