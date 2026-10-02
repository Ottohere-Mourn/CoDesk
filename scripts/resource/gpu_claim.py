#!/usr/bin/env python3
"""Fail-closed GPU idle watcher and owner-tracked workload launcher.

Adapted from sibling project scripts/gpu_watcher.py. Uses only Python stdlib
and nvidia-smi. Only the explicit watch command can launch a workload.
"""
from __future__ import annotations
import argparse, hashlib, json, os, signal, subprocess, time, uuid
from pathlib import Path
from typing import Any

TOOL_ID = "codesk-gpu-claim-v1"
DEFAULT_WAIT_S, DEFAULT_POLL_S = 120.0, 10.0
DEFAULT_MAX_MEM_MIB, DEFAULT_MAX_UTIL_PCT = 512, 5
_CHILD: subprocess.Popen[Any] | None = None
_STATE: Path | None = None
_OWNER: dict[str, Any] | None = None

def _nvidia_csv(query: str) -> list[list[str]]:
    result = subprocess.run(
        ["nvidia-smi", f"--query-{query}", "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    return [[x.strip() for x in line.split(",")] for line in result.stdout.splitlines() if line.strip()]

def snapshot() -> list[dict[str, Any]]:
    """Return GPU stats with compute PIDs; query/schema errors fail closed."""
    gpu_rows = _nvidia_csv("gpu=index,uuid,memory.used,memory.total,utilization.gpu")
    app_rows = _nvidia_csv("compute-apps=gpu_uuid,pid,used_memory,process_name")
    apps: dict[str, list[dict[str, Any]]] = {}
    for row in app_rows:
        if len(row) != 4:
            raise RuntimeError(f"unexpected compute-apps row shape: {row!r}")
        gpu_uuid, pid, used, name = row
        if pid.isdigit():
            apps.setdefault(gpu_uuid, []).append(
                {"pid": int(pid), "used_memory_mib": int(float(used)), "process_name": name})
    result = []
    for row in gpu_rows:
        if len(row) != 5:
            raise RuntimeError(f"unexpected GPU row shape: {row!r}")
        index, gpu_uuid, used, total, util = row
        result.append({
            "index": int(index), "uuid": gpu_uuid,
            "memory_used_mib": int(float(used)), "memory_total_mib": int(float(total)),
            "utilization_gpu_pct": int(float(util)),
            "compute_processes": apps.get(gpu_uuid, []),
        })
    if not result:
        raise RuntimeError("nvidia-smi returned no GPU rows")
    return result

def is_eligible(gpu: dict[str, Any], max_mem_mib: int = DEFAULT_MAX_MEM_MIB,
                max_util_pct: int = DEFAULT_MAX_UTIL_PCT) -> bool:
    """Zero-utilization compute PIDs still block eligibility."""
    return (not gpu.get("compute_processes")
            and int(gpu["memory_used_mib"]) <= max_mem_mib
            and int(gpu["utilization_gpu_pct"]) <= max_util_pct)

def _boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()

def _start_ticks(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        tail = raw[raw.rfind(")") + 2:].split()
        return int(tail[19])  # proc stat field 22, starttime
    except (OSError, ValueError, IndexError):
        return None

def _has_token(pid: int, token: str) -> bool:
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        return f"CODESK_GPU_CLAIM_ID={token}".encode() in env
    except OSError:
        return False

def _owned(pid: int, start: int, token: str, pgid: int) -> bool:
    try:
        return (pid > 1 and pgid == pid and os.getpgid(pid) == pgid
                and _start_ticks(pid) == start and _has_token(pid, token))
    except (ProcessLookupError, PermissionError, OSError):
        return False

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)

def _terminate_child() -> None:
    global _CHILD, _OWNER
    if _CHILD is None or _OWNER is None:
        return
    pid, token = int(_OWNER["worker_pid"]), str(_OWNER["owner_token"])
    start, pgid = int(_OWNER["worker_start_ticks"]), int(_OWNER["worker_pgid"])
    try:
        if _owned(pid, start, token, pgid):
            os.killpg(pgid, signal.SIGTERM)
            try:
                _CHILD.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if _owned(pid, start, token, pgid):
                    os.killpg(pgid, signal.SIGKILL)
                _CHILD.wait(timeout=5)
    except (ProcessLookupError, PermissionError, OSError):
        pass

def _handle_stop(signum: int, _frame: Any) -> None:
    _terminate_child()
    if _STATE is not None and _OWNER is not None:
        _OWNER["status"] = "stopped"
        _OWNER["stopped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _write_json(_STATE, _OWNER)
    raise SystemExit(128 + signum)

def _indices(raw: str, known: set[int]) -> list[int]:
    try:
        values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError as exc:
        raise SystemExit("--gpu-indices must be comma-separated integers") from exc
    if not values or len(set(values)) != len(values):
        raise SystemExit("--gpu-indices must contain unique IDs")
    missing = sorted(set(values) - known)
    if missing:
        raise SystemExit(f"requested GPU IDs absent from nvidia-smi: {missing}")
    return values

def do_watch(args: argparse.Namespace) -> int:
    global _CHILD, _STATE, _OWNER
    if not args.command:
        raise SystemExit("watch requires a command after --")
    if args.wait_seconds < 120:
        raise SystemExit("--wait-seconds cannot be less than 120 seconds")
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    state_path = run_dir / "ownership.json"
    first = snapshot()
    indices = _indices(args.gpu_indices, {int(x["index"]) for x in first})
    selected = set(indices)
    token = str(uuid.uuid4())
    _STATE = state_path
    _OWNER = {
        "tool": TOOL_ID, "status": "waiting", "owner_token": token,
        "owner_uid": os.getuid(), "boot_id": _boot_id(),
        "watcher_pid": os.getpid(), "watcher_start_ticks": _start_ticks(os.getpid()),
        "gpu_indices": indices,
        "gpu_uuids": [x["uuid"] for x in first if int(x["index"]) in selected],
        "wait_seconds": args.wait_seconds, "poll_interval_seconds": args.poll_interval,
        "thresholds": {"max_memory_used_mib": args.max_memory_mib,
                       "max_utilization_gpu_pct": args.max_util_pct,
                       "require_zero_compute_pids": True},
        "command_sha256": hashlib.sha256("\0".join(args.command).encode()).hexdigest(),
        "command_executable": Path(args.command[0]).name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    os.environ["CODESK_GPU_CLAIM_ID"] = token
    _write_json(state_path, _OWNER)
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    print(f"watching GPUs {indices}; continuous eligible window={args.wait_seconds:.0f}s", flush=True)
    eligible_since: float | None = None
    while True:
        now = time.monotonic()
        rows = snapshot()
        chosen = [x for x in rows if int(x["index"]) in selected]
        good = len(chosen) == len(indices) and all(
            is_eligible(x, args.max_memory_mib, args.max_util_pct) for x in chosen)
        if good:
            if eligible_since is None:
                eligible_since = now
            print(f"eligible continuously {now-eligible_since:.0f}/{args.wait_seconds:.0f}s", flush=True)
        else:
            eligible_since = None
            reasons = []
            for x in chosen:
                if x["compute_processes"]:
                    reasons.append(f"GPU{x['index']}: compute PID present")
                elif x["memory_used_mib"] > args.max_memory_mib:
                    reasons.append(f"GPU{x['index']}: {x['memory_used_mib']} MiB used")
                elif x["utilization_gpu_pct"] > args.max_util_pct:
                    reasons.append(f"GPU{x['index']}: {x['utilization_gpu_pct']}% utilization")
            print("eligibility reset" + (": " + "; ".join(reasons) if reasons else ""), flush=True)
        if good and eligible_since is not None and now - eligible_since >= args.wait_seconds:
            final = [x for x in snapshot() if int(x["index"]) in selected]
            if len(final) != len(indices) or not all(
                is_eligible(x, args.max_memory_mib, args.max_util_pct) for x in final):
                eligible_since = None
                print("final pre-launch sample failed; restarting window", flush=True)
                continue
            env = os.environ.copy()
            env.update({"CUDA_VISIBLE_DEVICES": ",".join(str(x) for x in indices),
                        "CODESK_GPU_CLAIM_ID": token,
                        "CODESK_GPU_CLAIM_OWNER_PID": str(os.getpid()),
                        "PYTHONUNBUFFERED": "1"})
            log_path = run_dir / "worker.log"
            with log_path.open("ab", buffering=0) as log:
                _CHILD = subprocess.Popen(args.command, cwd=args.cwd, env=env,
                                          stdout=log, stderr=subprocess.STDOUT,
                                          start_new_session=True)
            started = _start_ticks(_CHILD.pid)
            if started is None:
                _terminate_child()
                raise RuntimeError("cannot verify worker identity; stopped owned worker")
            _OWNER.update({"status": "running", "worker_pid": _CHILD.pid,
                           "worker_pgid": _CHILD.pid, "worker_start_ticks": started,
                           "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "log": str(log_path)})
            _write_json(state_path, _OWNER)
            print(f"launched owned PID {_CHILD.pid} on {indices}; ledger={state_path}", flush=True)
            rc = _CHILD.wait()
            _OWNER.update({"status": "completed" if rc == 0 else "failed",
                           "returncode": int(rc),
                           "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
            _write_json(state_path, _OWNER)
            return int(rc != 0)
        _OWNER["status"] = "waiting"
        _OWNER["last_sample_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _OWNER["last_gpu_sample"] = [
            {k: v for k, v in x.items() if k != "compute_processes"}
            | {"compute_pid_count": len(x["compute_processes"])} for x in chosen]
        _write_json(state_path, _OWNER)
        time.sleep(max(1.0, args.poll_interval))

def do_stop(args: argparse.Namespace) -> int:
    path = args.state_file.resolve()
    payload = json.loads(path.read_text())
    if payload.get("tool") != TOOL_ID or int(payload.get("owner_uid", -1)) != os.getuid():
        raise SystemExit("refusing stop: owner tool or UID mismatch")
    if payload.get("boot_id") != _boot_id():
        raise SystemExit("refusing stop: machine boot ID mismatch")
    watcher = int(payload.get("watcher_pid", -1))
    if _start_ticks(watcher) != payload.get("watcher_start_ticks"):
        raise SystemExit("refusing stop: watcher PID/start time mismatch")
    token = str(payload.get("owner_token", ""))
    worker = payload.get("worker_pid")
    if worker is not None:
        if not _owned(int(worker), int(payload["worker_start_ticks"]), token,
                      int(payload["worker_pgid"])):
            raise SystemExit("refusing stop: worker PID/start time/token/group mismatch")
        if not _has_token(watcher, token):
            raise SystemExit("refusing stop: watcher owner token mismatch")
    elif not _has_token(watcher, token):
        raise SystemExit("refusing stop: watcher owner token mismatch")
    os.kill(watcher, signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and _start_ticks(watcher) is not None:
        time.sleep(0.2)
    if _start_ticks(watcher) is not None:
        raise SystemExit("owned watcher did not exit; no other process was signaled")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    w = sub.add_parser("watch", help="wait safely, then launch one owned command")
    w.add_argument("--gpu-indices", required=True)
    w.add_argument("--run-dir", type=Path, required=True, help="must be a new path")
    w.add_argument("--wait-seconds", type=float, default=DEFAULT_WAIT_S)
    w.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_S)
    w.add_argument("--max-memory-mib", type=int, default=DEFAULT_MAX_MEM_MIB)
    w.add_argument("--max-util-pct", type=int, default=DEFAULT_MAX_UTIL_PCT)
    w.add_argument("--cwd", default=None)
    w.add_argument("command", nargs=argparse.REMAINDER)
    w.set_defaults(func=do_watch)
    s = sub.add_parser("stop")
    s.add_argument("state_file", type=Path)
    s.set_defaults(func=do_stop)
    st = sub.add_parser("status")
    st.add_argument("state_file", type=Path)
    st.set_defaults(func=lambda a: (print(a.state_file.read_text()), 0)[1])
    args = parser.parse_args()
    if args.action == "watch":
        args.command = list(args.command)
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        if not args.command:
            parser.error("watch requires COMMAND after --")
        args.cwd = args.cwd or os.getcwd()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
