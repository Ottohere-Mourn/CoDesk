"""Concrete BC adapter for HealthCare's installed formal oscombo runner.

It launches two persistent host Codex subprocesses via ``oscombo --mode
parallel`` in the runner's one shared Guest. Guest snapshots are retrieved
through OSWorld's read-only file/HTTP controller immediately before the
formal ``env.close`` call. No Actor-specific container is created.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .episode_adapter import ActorCapture, EpisodeCapture
from .timeline import sanitize


def _atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    temp.write_text(json.dumps(sanitize(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _write_agent_specs(path: Path, specs: list[dict[str, Any]]) -> None:
    """Write operational Codex config preserving secret *variable names*.

    The specs contain only environment-variable names, never credential
    values. Generic evidence redaction is intentionally not used here because
    it would corrupt fields such as ``api_key_env`` and ``redact_env_keys``.
    """
    allowed_keys = {"api_key_env", "redact_env_keys"}
    for spec in specs:
        options = spec.get("options", {})
        if options.get("api_key_env") not in {"CODESK_A_RELAY_TOKEN", "CODESK_B_RELAY_TOKEN"}:
            raise ValueError("agent spec must reference an episode-local relay token variable")
        if not isinstance(options.get("redact_env_keys"), list) or not all(
            isinstance(value, str) and value in {"CODESK_A_RELAY_TOKEN", "CODESK_B_RELAY_TOKEN"}
            for value in options["redact_env_keys"]
        ):
            raise ValueError("agent spec must redact only the peer relay token variable")
        for key, value in options.items():
            if any(marker in key.lower() for marker in ("api_key", "token", "secret", "password")) and key not in allowed_keys:
                raise ValueError("agent spec contains an unexpected credential-like field")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    temp.write_text(json.dumps(specs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _wait_ready(path: Path, process: subprocess.Popen, timeout: float = 40) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("model relay process exited before becoming ready")
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and int(data.get("port", 0)) > 0:
                return data
        time.sleep(0.2)
    raise TimeoutError("model relay readiness timeout")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _append_timeline(actions: Path, target: Path, role: str) -> int:
    import datetime

    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with actions.open("r", encoding="utf-8", errors="replace") as src, target.open("w", encoding="utf-8") as out:
        for line_no, line in enumerate(src, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            timestamp = float(row.get("t", 0))
            duration = max(0.0, float(row.get("tool_elapsed_s", 0) or 0))
            end_ms = int(timestamp * 1000)
            start_ms = max(0, int((timestamp - duration) * 1000))
            tool = str(row.get("tool", "unknown"))
            server = "guest_cli" if tool == "guest_cli" else "desktop"
            window = row.get("window_before")
            event = {
                "timestamp_utc": datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat(),
                "start_wall_ms": start_ms, "end_wall_ms": end_ms,
                "duration_ms": round((end_ms - start_ms), 3), "role": role,
                "server": server, "tool": tool,
                "args": sanitize(row.get("args", {})),
                "window_before": {"window_title": window, "window_id": None, "mouse": None},
                "window_after": None, "window_changed": None,
                "mouse_moved": None, "clipboard_changed": None,
                "status": "error" if row.get("error") else "ok",
                "error_type": str(row.get("error", "")).split(":", 1)[0] if row.get("error") else None,
                "evidence_scope": "formal action log; window-after, mouse and clipboard telemetry unavailable",
                "source_line": line_no,
            }
            out.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _combine_codex_events(stdout: Path, codex_home: Path, target: Path) -> dict[str, int]:
    """Archive CLI JSON events plus actual Codex session event JSONL files."""
    sources: list[tuple[Path, str]] = []
    if stdout.is_file():
        sources.append((stdout, "codex-cli-stdout"))
    sessions = codex_home / "sessions"
    if sessions.is_dir():
        sources.extend((path, "codex-session") for path in sorted(sessions.rglob("*.jsonl")) if path.is_file())
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = {"sources": len(sources), "rows": 0, "turn_context_rows": 0}
    with target.open("w", encoding="utf-8", newline="\n") as out:
        for path, source_name in sources:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row.get("type") == "turn_context":
                    counts["turn_context_rows"] += 1
                row = {"_source": source_name, **row}
                out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts["rows"] += 1
    return counts


def _relay_summary(path: Path, target: Path, role: str) -> dict[str, Any]:
    rows = []
    statuses: list[int] = []
    if path.is_file():
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            status = row.get("upstream_status")
            if isinstance(status, int):
                statuses.append(status)
            elif isinstance(status, str) and status.isdigit():
                statuses.append(int(status))
            # Keep only non-secret event metadata. request_json and response
            # bodies are intentionally omitted; model usage/status remains.
            rows.append({
                "role": role, "line": line_no, "time": row.get("time"),
                "upstream_status": status, "model": row.get("model"),
                "tool_names": row.get("tool_names"),
                "input_image_parts": row.get("input_image_parts"),
                "stream_completed": row.get("stream_completed"),
                "stream_terminal_event": row.get("stream_terminal_event"),
                "stream_failure_type": row.get("stream_failure_type"),
                "usage": row.get("usage"), "elapsed_s": row.get("elapsed_s"),
            })
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(sanitize(row), ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"role": role, "request_count": len(rows), "http_200_count": sum(x == 200 for x in statuses),
            "non_200_statuses": [x for x in statuses if x != 200],
            "events_archive": str(target), "http_200": bool(statuses and all(x == 200 for x in statuses))}


def _captured_guest_file_map(snapshots: dict[str, Any], capture_root: Path) -> dict[str, Path]:
    """Map present evidence, preserving optional deliverable absence for scoring."""
    files = {}
    for row in snapshots.get("guest_files", []):
        # Missing task deliverables are a scored absence, not malformed
        # evidence. They intentionally have no captured_path.
        if row.get("missing") is True:
            if row.get("kind") != "deliverable":
                raise RuntimeError("Required non-deliverable snapshot is missing")
            continue
        if not row.get("guest_path") or not row.get("captured_path"):
            raise RuntimeError("Present Guest snapshot lacks path evidence")
        captured = Path(row["captured_path"]).resolve()
        if not captured.is_relative_to(capture_root.resolve()) or not captured.is_file():
            raise RuntimeError("Captured Guest evidence escaped capture root or is absent")
        files[str(row["guest_path"])] = captured
    return files

class FormalOsworldBackend:
    """Production backend with one Guest plus the formal two-process Codex harness."""

    def __init__(
        self, *, batch_root: str | Path, run_archive_root: str | Path,
        runner_python: str, runner_src: str, relay_script: str,
        codex_bin: str, mcp_python: str, overlay_host_root: str | Path,
        resource_ledger_root: str | Path, relay_upstream: str = "https://api.haogpt.net/v1",
        provider_env_file: str = "/home/mjh/.config/codesk/providers.env",
        upstream_key_env: str = "HAOGPT_API_KEY", runner_timeout_s: int = 7800,
    ) -> None:
        self.batch_root = Path(batch_root).resolve()
        self.run_archive_root = Path(run_archive_root).resolve()
        self.runner_python = runner_python
        self.runner_src = Path(runner_src)
        self.relay_script = relay_script
        self.codex_bin = codex_bin
        self.mcp_python = mcp_python
        self.overlay_host_root = Path(overlay_host_root)
        self.resource_ledger_root = Path(resource_ledger_root)
        self.relay_upstream = relay_upstream
        self.provider_env_file = provider_env_file
        self.upstream_key_env = upstream_key_env
        self.runner_timeout_s = max(7200, int(runner_timeout_s))
        self._capture_root: Path | None = None
        self._guest_files: dict[str, Path] = {}
        self._http_files: dict[str, tuple[int, Path]] = {}

    def prepare_shared_episode(self, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("mode") != "shared":
            raise ValueError("BC production backend accepts Shared-only episodes")
        run_root = Path(plan["argv"][plan["argv"].index("--out") + 1]).resolve()
        self._capture_root = run_root / "backend-capture"
        self._capture_root.mkdir(parents=True, exist_ok=False)
        self._guest_files.clear()
        self._http_files.clear()
        capture_plan = {
            "run_id": plan["run_id"], "capture_root": str(self._capture_root),
            "guest_assets_source": str(Path(plan["guest_assets"]).resolve(strict=True)),
            "guest_assets_sha256": plan["guest_assets_sha256"],
            "guest_workspace": plan["guest_workspace_root"],
            "guest_setup_command": plan.get("guest_setup_command"),
            "guest_services": plan["case_config"].get("guest_services", []),
            "host_snapshots": plan["case_config"].get("host_snapshots", []),
            "host_snapshot_directories": plan["case_config"].get("host_snapshot_directories", []),
            "host_http_snapshots": plan["case_config"].get("host_http_snapshots", []),
        }
        capture_plan_path = self._capture_root / "capture-plan.json"
        _atomic_json(capture_plan_path, capture_plan)
        plan["environment"].update({
            "CODEDESK_BC_CAPTURE_PLAN": str(capture_plan_path),
            "CODEDESK_BC_RW_CLI": "1",
            "CODEDESK_BC_GUEST_CLI_MODULE": "pipeline.guest_cli_rw_tools",
        })
        # No false setup-completion claim here. Guest reset/staging/setup is
        # executed and receipted inside the formal runner's setup callback.
        return {
            "assets_staged": True,
            "guest_assets_sha256": plan["guest_assets_sha256"],
            "guest_workspace": plan["guest_workspace_root"],
            "staging": "RAID episode staging; Guest copy is verified after formal reset",
            "guest_setup_completed": False,
        }

    def _start_relay(self, role: str, run_id: str, root: Path, run_env: dict[str, str], token: str):
        lower = role.lower()
        ready = root / f"relay-{lower}-ready.json"
        events = root / f"relay-{lower}-events.raw.jsonl"
        log_path = root / f"relay-{lower}.raw.log"
        key_var = f"CODESK_{role}_RELAY_TOKEN"
        relay_env = dict(run_env)
        relay_env[key_var] = token
        relay_env.pop("CODEDESK_BC_CAPTURE_PLAN", None)
        relay_env["CODEDESK_BC_RW_CLI"] = "0"
        cmd = [
            "bash", "-lc",
            "set +x; set -a; source " + str(self.provider_env_file)
            + "; test -n \"$" + self.upstream_key_env + "\" || { echo UPSTREAM_CREDENTIAL_MISSING >&2; exit 78; }; exec "
            + shlex_quote(self.runner_python) + " " + shlex_quote(self.relay_script)
            + " --upstream " + shlex_quote(self.relay_upstream)
            + " --api-key-env " + shlex_quote(self.upstream_key_env)
            + " --client-token-env " + key_var
            + " --host 127.0.0.1 --port 0 --ready-file " + shlex_quote(str(ready))
            + " --event-log " + shlex_quote(str(events)) + " --promote-tool-image",
        ]
        log = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(cmd, cwd=str(root), env=relay_env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            ready_data = _wait_ready(ready, process)
        except Exception:
            _terminate(process)
            log.close()
            raise
        return {"process": process, "log": log, "ready": ready_data, "events": events, "token_env": key_var}

    def run_shared_episode(self, plan: dict[str, Any]) -> EpisodeCapture:
        if self._capture_root is None:
            raise RuntimeError("prepare_shared_episode must run before the formal runner")
        run_id = str(plan["run_id"])
        run_root = Path(plan["argv"][plan["argv"].index("--out") + 1]).resolve()
        capture_root = self._capture_root
        self.overlay_host_root.mkdir(parents=True, exist_ok=True)
        self.resource_ledger_root.mkdir(parents=True, exist_ok=True)
        guest_overlay = self.overlay_host_root / run_id
        guest_overlay.mkdir(parents=True, exist_ok=False)
        guest_storage = self.batch_root / "docker-storage" / run_id
        guest_storage.mkdir(parents=True, exist_ok=False)
        ledger = self.resource_ledger_root / f"{run_id}.jsonl"
        owner_token = secrets.token_hex(32)
        agent_tokens = {role: secrets.token_urlsafe(32) for role in ("A", "B")}
        runner_env = dict(plan["environment"])
        runner_env.update({
            "SWCUB_RUN_ID": run_id,
            "SWCUB_OWNER_TOKEN": owner_token,
            "SWCUB_RESOURCE_LEDGER": str(ledger),
            "SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(guest_overlay),
            "SWCUB_OSWORLD_STORAGE_HOST_DIR": str(guest_storage),
            "CODESK_A_RELAY_TOKEN": agent_tokens["A"],
            "CODESK_B_RELAY_TOKEN": agent_tokens["B"],
        })
        relays: dict[str, dict[str, Any]] = {}
        runner_log_path = run_root / "formal-runner.stdout.log"
        runner_log = None
        runner = None
        try:
            for role in ("A", "B"):
                relays[role] = self._start_relay(role, run_id, run_root, runner_env, agent_tokens[role])

            specs = json.loads(Path(plan["agents_json"]).read_text(encoding="utf-8"))
            if len(specs) != 2:
                raise ValueError("formal runner requires exactly two Actor specs")
            ports = {}
            for role, spec in zip(("A", "B"), specs):
                options = spec["options"]
                ports[role] = int(relays[role]["ready"]["port"])
                options.update({
                    "base_url": f"http://127.0.0.1:{ports[role]}/v1",
                    "wire_api": "responses",
                    "auth_mode": "env", "api_key_env": f"CODESK_{role}_RELAY_TOKEN",
                    "redact_env_keys": [f"CODESK_{'B' if role == 'A' else 'A'}_RELAY_TOKEN"],
                    "timeout": 7200, "request_retries": 3, "stream_retries": 3,
                    "desktop_tool_timeout_sec": 300,
                    "desktop_screenshot_settle_sec": 0.3,
                    "guest_cli": {"root": plan["guest_workspace_root"],
                                  "max_timeout_sec": 30, "max_output_bytes": 1_000_000},
                    "mcp_env": {
                        **options.get("mcp_env", {}),
                        "OSCOMBO_ACTOR_ID": role,
                        "OSCOMBO_EPISODE_ID": run_id,
                        "OSCOMBO_GUEST_KEY": "shared",
                        "OSCOMBO_CONDITION": "shared",
                        "OSCOMBO_GUEST_WORKSPACE": plan["guest_workspace_root"],
                        "OSCOMBO_CLI_ROOT": plan["guest_workspace_root"],
                        "OSCOMBO_ACTOR_PRIVATE_PATH": plan["role_private_guest_paths"]["actor_" + role.lower()],
                    },
                })
            agents_json = capture_root / "agents.json"
            _write_agent_specs(agents_json, specs)
            argv = list(plan["argv"])
            argv[argv.index("--agents") + 1] = str(agents_json)
            # Existing command builder has one Guest and both Codex actors;
            # assert the exact run mode and no extra Guest is introduced.
            if argv[argv.index("--mode") + 1] != "parallel" or argv.count("--image") != 1:
                raise ValueError("formal runner invocation is not the expected shared one-Guest command")
            _atomic_json(capture_root / "formal-invocation.json", {
                "argv": argv, "cwd": plan["cwd"], "mode": "parallel",
                "actors": ["A", "B"], "max_steps": int(argv[argv.index("--max-steps") + 1]),
                "outer_timeout_s": self.runner_timeout_s,
                "guest_overlay_host_dir": str(guest_overlay),
                "runner_environment_keys": sorted(k for k in runner_env if not any(x in k.lower() for x in ("key", "token", "secret", "password"))),
            })
            runner_log = runner_log_path.open("w", encoding="utf-8")
            started = time.monotonic()
            runner = subprocess.Popen(argv, cwd=plan["cwd"], env=runner_env,
                                      stdin=subprocess.DEVNULL, stdout=runner_log,
                                      stderr=subprocess.STDOUT, start_new_session=True)
            timed_out = False
            while runner.poll() is None:
                if time.monotonic() - started > self.runner_timeout_s:
                    timed_out = True
                    os.killpg(runner.pid, signal.SIGTERM)
                    try:
                        runner.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(runner.pid, signal.SIGKILL)
                        runner.wait(timeout=10)
                    break
                time.sleep(2)
            if runner.poll() is None:
                runner.wait()
            duration_s = round(time.monotonic() - started, 2)
            runner_log.flush()
            runner_log.close()
            runner_log = None
            result_path = run_root / "result.json"
            if not result_path.is_file():
                raise RuntimeError("formal oscombo runner exited without result.json")
            result = json.loads(result_path.read_text(encoding="utf-8"))

            captured_container = {}
            entry_path = capture_root / "guest-container-entry.json"
            if entry_path.is_file():
                captured_container = json.loads(entry_path.read_text(encoding="utf-8"))
            teardown_path = capture_root / "teardown-receipt.json"
            teardown = json.loads(teardown_path.read_text(encoding="utf-8")) if teardown_path.is_file() else {}
            setup_path = capture_root / "guest-preparation-receipt.json"
            preparation_receipt = json.loads(setup_path.read_text(encoding="utf-8")) if setup_path.is_file() else None
            snapshot_path = capture_root / "snapshot-capture.json"
            snapshots = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.is_file() else {}
            self._guest_files.update(_captured_guest_file_map(snapshots, capture_root))
            for row in snapshots.get("http", []):
                self._http_files[str(row["url"])] = (int(row["status_code"]), Path(row["captured_path"]))

            guest_id = str(captured_container.get("container_id") or "")
            guest_facts = captured_container.get("facts", {})
            teardown_ok = teardown.get("teardown_verified") is True and bool(guest_id)
            actor_statuses: dict[str, str] = {}
            actors: dict[str, ActorCapture] = {}
            relay_http: dict[str, bool] = {}
            relay_summaries = {}
            for role, role_label in (("A", "actor_a"), ("B", "actor_b")):
                runner_name = "agent" + role
                actor_result = (result.get("agents") or {}).get(runner_name, {})
                status = str(actor_result.get("status", "missing"))
                actor_statuses[role] = "completed" if status == "done" else (
                    "declared_infeasible" if status == "fail" else status
                )
                relay_summary = _relay_summary(
                    relays[role]["events"], run_root / f"relay-{role.lower()}-events.redacted.jsonl", role
                )
                relay_summaries[role] = relay_summary
                relay_http[role] = relay_summary["http_200_count"] > 0 and not relay_summary["non_200_statuses"]

                actor_dir = run_root / runner_name
                actions = actor_dir / "actions.jsonl"
                stdout = actor_dir / "stdout.log"
                pid_file = capture_root / f"{runner_name}-process.json"
                if not pid_file.is_file() or not actions.is_file() or not stdout.is_file():
                    raise RuntimeError(f"formal runner did not capture required {role} action/process evidence")
                proc_meta = json.loads(pid_file.read_text(encoding="utf-8"))
                codex_home = Path(str(proc_meta.get("codex_home") or ""))
                # Codex's turn_context CWD is its per-Actor writable work
                # directory, distinct from the subprocess cwd recorded by the
                # formal harness (the agentA/agentB output directory).
                codex_workdir = codex_home.parent / "work"
                event_stream = capture_root / f"actor-{role}-codex-events.jsonl"
                event_counts = _combine_codex_events(stdout, codex_home, event_stream)
                timeline = capture_root / f"actor-{role}-timeline-events.jsonl"
                if _append_timeline(actions, timeline, role) == 0:
                    raise RuntimeError(f"Actor {role} has no action-log records")
                actors[role] = ActorCapture(
                    container_id=guest_id,
                    uid=int(proc_meta.get("uid") or os.getuid()),
                    gid=int(proc_meta.get("gid") or os.getgid()),
                    pid=int(proc_meta["pid"]), relay_port=ports[role],
                    private_guest_path=plan["role_private_guest_paths"][role_label],
                    actions_jsonl=actions, codex_events_jsonl=event_stream,
                    timeline_events_jsonl=timeline,
                    home=proc_meta.get("home"), codex_home=str(codex_home),
                    cwd=proc_meta.get("cwd"), codex_workdir=str(codex_workdir),
                    sandbox_mode="workspace-write",
                    approval_policy="never", tools_enabled=("desktop", "guest_cli"),
                    shell_tool=False, unified_exec=False,
                    guest_cli_shell=True, guest_cli_read_write=True, yolo_enabled=False,
                )
                relay_http[role] = relay_summary["http_200_count"] > 0 and not relay_summary["non_200_statuses"]
                _atomic_json(capture_root / f"actor-{role}-evidence-summary.json", {
                    "runner_status": status, "runner_steps": actor_result.get("steps"),
                    "turn_event_counts": event_counts, "relay": relay_summary,
                    "actor_process": {k: proc_meta.get(k) for k in ("pid", "uid", "gid", "home", "codex_home", "cwd")},
                })

            # Raw relay events can contain inline image-bearing request bodies.
            # Keep only the redacted event summaries in the archive, then
            # remove raw relay records/logs and runtime bearer-token env values.
            for info in relays.values():
                _terminate(info.get("process"))
                try:
                    info["log"].close()
                except Exception:
                    pass
                try:
                    info["events"].unlink(missing_ok=True)
                    (run_root / f"relay-{info['token_env'].split('_')[1].lower()}.raw.log").unlink(missing_ok=True)
                except OSError:
                    pass

            metadata = {
                "formal_runner": str(self.runner_src),
                "model_id": "gpt-6-sol",
                # The adapter reserves placeholder ports when it constructs
                # the plan; the formal backend binds each actor to a fresh
                # relay socket immediately before oscombo starts. Preserve the
                # observed binding so the post-run audit can validate the
                # endpoint actually used without comparing it to a placeholder.
                "relay_ports": {role: int(relays[role]["ready"]["port"])
                                for role in ("A", "B")},
                "shared_guest_container_id": guest_id,
                "shared_guest_facts": guest_facts,
                "guest_preparation_receipt": preparation_receipt,
                "captured_directory_items": snapshots.get("directory_items", []),
                "guest_teardown_receipt": teardown,
                "relay_summaries": relay_summaries,
                "runner_result_path": str(result_path),
                "runner_error": result.get("error"),
                "runner_duration_s": duration_s,
                "max_steps_value": result.get("max_steps"),
                "capture_schema": "shared-oscombo-two-host-codex-one-guest",
                "guest_overlay_host_dir": str(guest_overlay),
                "guest_storage_host_dir": str(guest_storage),
            }
            overlay_bytes = sum(p.stat().st_size for p in guest_overlay.rglob("*") if p.is_file()) if guest_overlay.is_dir() else 0
            metadata["guest_overlay_bytes_before_cleanup"] = overlay_bytes
            metadata["guest_overlay_cleanup"] = "not-removed-teardown-unverified"
            if teardown_ok and guest_overlay.resolve().parent == self.overlay_host_root.resolve() and guest_overlay.name == run_id:
                shutil.rmtree(guest_overlay)
                metadata["guest_overlay_cleanup"] = "removed-after-verified-container-teardown"
            _atomic_json(capture_root / "backend-capture-summary.json", metadata)
            runner_code = int(runner.returncode or 0)
            state = "completed" if result.get("error") is None and not timed_out and runner_code == 0 and teardown_ok else "failed"
            return EpisodeCapture(
                exit_code=runner_code, episode_state=state,
                relay_http_200=relay_http, actor_statuses=actor_statuses,
                actors=actors, teardown_verified=teardown_ok,
                timed_out=timed_out, duration_s=duration_s, metadata=metadata,
            )
        finally:
            if runner_log:
                runner_log.close()
            if runner and runner.poll() is None:
                _terminate(runner)
            for info in relays.values():
                _terminate(info.get("process"))
                try:
                    info["log"].close()
                except Exception:
                    pass
            for name in ("CODESK_A_RELAY_TOKEN", "CODESK_B_RELAY_TOKEN"):
                runner_env.pop(name, None)

    def read_guest_file(self, guest_path: str) -> bytes:
        path = self._guest_files.get(guest_path)
        if path is None or not path.is_file():
            raise FileNotFoundError(f"Guest path was not captured from the pre-teardown allowlist: {Path(guest_path).name}")
        return path.read_bytes()

    def read_guest_http(self, url: str) -> dict[str, Any]:
        pair = self._http_files.get(url)
        if pair is None:
            raise FileNotFoundError("Guest HTTP endpoint was not captured before teardown")
        status_code, path = pair
        return {"status_code": status_code, "body": path.read_bytes()}


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)
