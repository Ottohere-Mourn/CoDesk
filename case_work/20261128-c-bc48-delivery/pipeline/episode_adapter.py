"""Shared-only BC episode orchestration and fail-closed archive adapter.

This module owns the BC artifact contract.  It delegates the actual Guest,
Codex, Docker and relay lifecycle to an injected formal OSWorld backend; it
does not create a second harness or start an episode when imported.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from .archive import write_manifest, validate_batch
from .host_snapshots import SnapshotItem, collect_completed_episode_snapshots, merge_directory_snapshot_items
from .osworld_contract import (
    build_actor_specs, build_oscombo_invocation, build_runner_environment,
    validate_plan,
)
from .permission_audit import build_entry_audit, verify_episode_permissions, write_verified_certificate
from .profile import RunnerProfile
from .redact_codex_events import redact_events_file
from .role_paths import actor_private_path, merge_path_audits, path_reference_audit
from .scan_sensitive import scan_paths
from .timeline import merge_shared_timeline, sanitize, write_shared_timeline
from .temp_storage import ensure_private_directory, free_bytes, remove_private_run_tree


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_CASE_ID = re.compile(r"^BC-[0-9]{2}$")


@dataclass(frozen=True)
class ActorCapture:
    container_id: str
    uid: int
    gid: int
    pid: int
    relay_port: int
    private_guest_path: str
    actions_jsonl: Path
    codex_events_jsonl: Path
    timeline_events_jsonl: Path
    home: str | None = None
    codex_home: str | None = None
    cwd: str | None = None
    codex_workdir: str | None = None
    sandbox_mode: str = "workspace-write"
    approval_policy: str = "never"
    tools_enabled: tuple[str, ...] = ("desktop", "guest_cli")
    shell_tool: bool = False
    unified_exec: bool = False
    guest_cli_shell: bool = True
    guest_cli_read_write: bool = True
    yolo_enabled: bool = False


@dataclass(frozen=True)
class EpisodeCapture:
    exit_code: int
    episode_state: str
    relay_http_200: dict[str, bool]
    actor_statuses: dict[str, str]
    actors: dict[str, ActorCapture]
    teardown_verified: bool
    timed_out: bool
    duration_s: float
    metadata: dict[str, Any]


def _verify_actor_relay_binding(actor: ActorCapture, role: str, metadata: dict[str, Any]) -> None:
    """Compare an Actor's relay port with the backend's observed ephemeral binding."""
    ports = metadata.get("relay_ports")
    expected = ports.get(role) if isinstance(ports, dict) else None
    if not isinstance(expected, int) or actor.relay_port != expected:
        raise RuntimeError(f"Actor {role} relay-port evidence does not match the observed relay binding")


class FormalOsworldBackend(Protocol):
    """Adapter surface implemented by the existing formal OSWorld runner.

    Implementations reuse oscombo's two host Codex subprocesses and one
    shared Guest, stage path-level role folders, collect allowlisted Guest
    evidence before env.close(), and expose read-only archived snapshots.
    """

    def prepare_shared_episode(self, plan: dict[str, Any]) -> dict[str, Any]: ...

    def run_shared_episode(self, plan: dict[str, Any]) -> EpisodeCapture: ...

    def read_guest_file(self, guest_path: str) -> bytes: ...

    def read_guest_http(self, url: str) -> dict[str, Any]: ...


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _safe_jsonl_copy(source: Path, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source.open("r", encoding="utf-8", errors="replace") as inp, target.open("w", encoding="utf-8", newline="\n") as out:
        for n, line in enumerate(inp, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL source {source}:{n}") from exc
            out.write(json.dumps(sanitize(row), ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Expected directory: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if any(part in {"__pycache__", ".git", ".venv", "venv"} for part in relative.parts) or item.suffix in {".pyc", ".pyo"}:
            continue
        destination = target / relative
        if item.is_symlink():
            raise ValueError(f"Symlinks are not admitted in staged case input: {item}")
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            # RAID staging does not support preserving POSIX metadata. Copy
            # bytes only; case inputs are data, not executable host scripts.
            shutil.copyfile(item, destination)


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = item.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _copy_role_private_inputs(case_root: Path, target_root: Path, config: dict[str, Any]) -> dict[str, Path]:
    """Stage role-specific inputs into named directories in the shared Guest.

    This is path-level organization only and does not claim physical ACL
    isolation. A case may omit the source trees
    (the first four BC prototypes have no private source tree yet), but when a
    role path is declared it must remain inside the Case directory and may not
    point into the host Oracle.
    """
    declared = config.get("role_private_assets", {})
    if not isinstance(declared, dict) or set(declared) - {"actor_a", "actor_b"}:
        raise ValueError("role_private_assets must map actor_a/actor_b to Case-relative directories")
    result: dict[str, Path] = {}
    for role in ("actor_a", "actor_b"):
        destination = target_root / role
        destination.mkdir(parents=True, exist_ok=True)
        relative = declared.get(role)
        if relative is not None:
            source = (case_root / str(relative)).resolve(strict=True)
            if not source.is_relative_to(case_root.resolve()) or not source.is_dir():
                raise ValueError(f"{role} private assets must be a directory inside the Case source")
            if any(part.lower() == "oracle" for part in source.relative_to(case_root.resolve()).parts):
                raise ValueError("Oracle files cannot be staged as role-private inputs")
            _copy_tree(source, destination)
        result[role] = destination
    return result


def _guest_workspace(config: dict[str, Any]) -> str:
    raw = str(config.get("guest_workspace", "/home/user/workspace"))
    if raw == "~" or raw.startswith("~/"):
        raw = "/home/user/" + raw[2:] if raw != "~" else "/home/user"
    path = PurePosixPath(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("guest_workspace must resolve to an absolute traversal-free Guest path")
    return path.as_posix()


def _load_grader(case_root: Path) -> Callable[..., dict[str, Any]]:
    oracle_path = (case_root / "oracle" / "oracle.py").resolve(strict=True)
    module_name = f"bc_oracle_{case_root.name.lower().replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, oracle_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load host Oracle: {oracle_path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    grader = getattr(module, "grade_episode", None)
    if not callable(grader):
        raise ValueError(f"{oracle_path} must export grade_episode(snapshot_root, receipt, run_id)")
    return grader


def _load_profile(config: dict[str, Any]) -> RunnerProfile:
    values = config.get("runner_profile", {})
    required = {
        "mode": "shared", "max_cua_calls": None, "countdown_injected": False,
        "xvfb_auth": True, "yolo": False, "gui_enabled": True,
        "guest_cli_read_write": True,
    }
    for key, expected in required.items():
        if values.get(key) is not expected and values.get(key) != expected:
            raise ValueError(f"case runner_profile.{key} must be {expected!r}")
    if int(values.get("outer_timeout_s", 0)) < 7200:
        raise ValueError("case runner_profile.outer_timeout_s must be at least 7200")
    # The adapter intentionally accepts the scaffold's approved defaults only;
    # any future profile change needs an explicit review rather than silent drift.
    profile = RunnerProfile(
        model_id=str(values.get("model_id", "gpt-6-sol")),
        actor_timeout_s=int(values.get("actor_timeout_s", values.get("outer_timeout_s", 7200))),
        runner_timeout_s=int(values.get("runner_timeout_s", values.get("outer_timeout_s", 7200))),
    )
    profile.validate()
    return profile


def _case_snapshot_items(config: dict[str, Any]) -> list[SnapshotItem]:
    items = []
    for row in config.get("host_snapshots", []):
        items.append(SnapshotItem(
            guest_path=str(row["guest_path"]),
            archive_path=str(row["archive_path"]),
            kind=str(row["kind"]),
        ))
    return items


class EpisodeAdapter:
    """Execute/collect/grade one BC Shared episode through a formal backend.

    `run_episode` is deliberately fail-closed: a stale run directory, an
    isolated mode, missing relay 200, unverified teardown, missing required
    evidence or non-clean security scan prevents a success receipt. Role
    privacy is path-level and audited from each actor's recorded actions.
    """

    def __init__(
        self, *, batch_root: str | Path, backend: FormalOsworldBackend,
        guest_image: str, python: str, codex_bin: str, node_bin: str,
        mcp_python: str, mcp_pythonpath: str, runner_paths: dict[str, str],
        relay_ports: dict[str, int], base_environment: dict[str, str] | None = None,
        private_runtime_root: str | Path | None = None,
        private_temp_root: str | Path | None = None,
    ) -> None:
        self.batch_root = Path(batch_root).resolve()
        self.backend = backend
        self.guest_image = guest_image
        self.python = python
        self.codex_bin = codex_bin
        self.node_bin = node_bin
        self.mcp_python = mcp_python
        self.mcp_pythonpath = mcp_pythonpath
        self.runner_paths = dict(runner_paths)
        self.relay_ports = dict(relay_ports)
        self.base_environment = dict(base_environment or os.environ)
        home = Path.home()
        self.private_runtime_root = Path(private_runtime_root or home / ".local/state/codesk-bc-runtime").expanduser()
        self.private_temp_root = Path(private_temp_root or "/dev/shm/codesk-bc-temp").expanduser()

    def run_episode(self, case_id: str, run_id: str) -> dict[str, Any]:
        if not _CASE_ID.fullmatch(case_id) or not _RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid Case ID or run ID")
        case_root = (self.batch_root / "cases" / case_id).resolve(strict=True)
        if not case_root.is_relative_to((self.batch_root / "cases").resolve()):
            raise ValueError("Case path escaped batch root")
        config = _json(case_root / "case.json")
        if config.get("case_id") != case_id or config.get("mode") != "shared" or config.get("track") != "blind_concurrency":
            raise ValueError("Only valid blind Shared BC case definitions are admitted")
        profile = _load_profile(config)
        guest_workspace = _guest_workspace(config)
        run_dir = self.batch_root / "trajectories" / case_id / run_id
        if run_dir.exists():
            raise FileExistsError(f"Refusing to overwrite an existing episode archive: {run_dir}")
        run_dir.mkdir(parents=True)
        if self.private_runtime_root.resolve().is_relative_to(self.batch_root):
            raise ValueError("Codex runtime must be outside RAID batch staging/archive")
        if self.private_temp_root.resolve().is_relative_to(self.batch_root):
            raise ValueError("process temp root must be outside RAID batch staging/archive")
        runtime_parent = ensure_private_directory(self.private_runtime_root)
        temp_parent = ensure_private_directory(self.private_temp_root)
        runtime_run_root = ensure_private_directory(runtime_parent / case_id / run_id)
        temp_run_root = ensure_private_directory(temp_parent / case_id / run_id)
        if free_bytes(temp_run_root) < 2 * 1024**3:
            raise RuntimeError("Dedicated BC temp filesystem has less than 2 GiB free")
        staging = run_dir / "episode-staging"
        guest_root = staging / "guest"
        _copy_tree(case_root / "guest", guest_root)
        actors = staging / "actors"
        private_root = staging / "role-private"
        task_root = staging / "tasks"
        task_root.mkdir(parents=True, exist_ok=True)
        private_roots = _copy_role_private_inputs(case_root, private_root, config)
        staged_private = guest_root / "role-private"
        staged_private.mkdir(parents=True, exist_ok=True)
        for role in ("actor_a", "actor_b"):
            _copy_tree(private_roots[role], staged_private / role)
        task_paths: dict[str, str] = {}
        task_specs: dict[str, dict[str, Any]] = {}
        for role in ("actor_a", "actor_b"):
            (private_root / role).mkdir(parents=True, exist_ok=True)
            (actors / role).mkdir(parents=True, exist_ok=True)
            prompt = case_root / "prompts" / f"{role}.md"
            if not prompt.is_file():
                raise ValueError(f"Missing actor prompt: {prompt}")
            (actors / role / "prompt.md").write_bytes(prompt.read_bytes())
            task_id = f"{case_id.lower().replace('-', '_')}_{role}_{run_id}"
            task = {
                "id": task_id,
                "instruction": prompt.read_text(encoding="utf-8"),
                "config": config.get("osworld_setup_steps", []),
                "evaluator": {},
            }
            task_path = task_root / f"{role}.json"
            task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            task_paths[role] = str(task_path.resolve())
            task_specs[role] = task

        actor_specs = build_actor_specs(
            profile=profile, codex_bin=self.codex_bin, node_bin=self.node_bin,
            mcp_python=self.mcp_python, private_runtime_root=str(runtime_run_root),
            relay_ports=self.relay_ports, mcp_pythonpath=self.mcp_pythonpath,
            guest_workspace=guest_workspace,
        )
        for role, spec_row in zip(("actor_a", "actor_b"), actor_specs):
            spec_row["prompt_path"] = str((actors / role / "prompt.md").resolve())
            spec_row["options"]["mcp_env"]["OSCOMBO_ACTOR_PRIVATE_PATH"] = actor_private_path(role)
        agents_json = staging / "agents.json"
        agents_json.write_text(json.dumps(actor_specs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        argv = build_oscombo_invocation(
            python=self.python, task_a=task_paths["actor_a"], task_b=task_paths["actor_b"],
            run_root=str(run_dir), agents_json=str(agents_json),
            guest_image=self.guest_image, run_id=run_id, profile=profile,
        )
        task_assets = str(guest_root.resolve())
        runner_hook = staging / "runner-hook"
        runner_hook.mkdir(parents=True, exist_ok=True)
        hook_source = Path(__file__).resolve().parent / "runner_hooks" / "sitecustomize.py"
        shutil.copyfile(hook_source, runner_hook / "sitecustomize.py")
        runner_env = None
        cwd, runner_env = build_runner_environment(
            base_environment=self.base_environment,
            neutral_cwd=self.runner_paths["neutral_cwd"],
            staged_runner_source=str(runner_hook),
            runner_overlay=os.pathsep.join((
                self.runner_paths["staged_runner_source"],
                self.runner_paths["runner_overlay"],
            )),
            runner_src=self.runner_paths["runner_src"],
            compatibility_root=self.runner_paths["compatibility_root"],
            osworld_source=self.runner_paths["osworld_source"],
            task_asset_root=task_assets, guest_image=self.guest_image, run_id=run_id,
            temp_root=str(temp_run_root),
        )
        runner_env["PYTHONPATH"] = os.pathsep.join((str(self.batch_root), runner_env["PYTHONPATH"]))
        plan = {
            "mode": "shared", "argv": argv, "cwd": cwd,
            "environment": runner_env, "agents_json": str(agents_json),
            "actor_specs": actor_specs, "guest_assets": str(guest_root),
            "guest_workspace_root": guest_workspace,
            "guest_setup_script": str((guest_root / "setup.py").resolve()) if (guest_root / "setup.py").is_file() else None,
            "role_private_roots": {role: str(path.resolve()) for role, path in private_roots.items()},
            "role_private_guest_paths": {role: actor_private_path(role) for role in ("actor_a", "actor_b")},
            "task_specs": task_specs, "case_config": config, "run_id": run_id,
            "private_runtime_root": str(runtime_run_root),
            "private_temp_root": str(temp_run_root),
        }
        setup = config.get("guest_setup", {})
        if setup and (not isinstance(setup, dict) or not isinstance(setup.get("args", []), list)):
            raise ValueError("guest_setup must be an object with an argument list")
        staged_guest_assets = f"{guest_workspace}/.bc-case-assets"
        plan["guest_assets_sha256"] = _tree_sha256(guest_root)
        plan["guest_assets_target"] = staged_guest_assets
        plan["guest_setup_command"] = (
            ["python3", f"{staged_guest_assets}/setup.py", "--source-dir", staged_guest_assets,
             *[str(x) for x in setup.get("args", [])]] if setup else None
        )
        plan["guest_setup_cleanup"] = {
            "path": staged_guest_assets,
            "remove_after_setup": True,
            "wait_for_http_200": [str(row["url"]) for row in config.get("guest_services", [])],
        }
        validate_plan(argv=argv, actors=actor_specs, env=runner_env, profile=profile)
        preparation = self.backend.prepare_shared_episode(plan)
        required_preparation = {
            "assets_staged": True,
            "guest_assets_sha256": plan["guest_assets_sha256"],
            "guest_workspace": guest_workspace,
        }
        if not isinstance(preparation, dict) or any(preparation.get(key) != value for key, value in required_preparation.items()):
            raise RuntimeError("Formal OSWorld backend did not stage the exact Guest asset payload")
        plan["preparation_receipt"] = sanitize(preparation)
        capture = self.backend.run_shared_episode(plan)
        preparation_receipt = capture.metadata.get("guest_preparation_receipt")
        required_setup_receipt = {
            "setup_completed": bool(setup),
            "guest_assets_sha256": plan["guest_assets_sha256"],
            "guest_workspace": guest_workspace,
            "setup_payload_removed": True,
        }
        if not isinstance(preparation_receipt, dict) or any(
            preparation_receipt.get(key) != value for key, value in required_setup_receipt.items()
        ):
            raise RuntimeError("Runner did not prove Guest setup, service readiness, and setup-payload removal")
        if capture.exit_code != 0 or capture.episode_state != "completed":
            raise RuntimeError(f"Formal Shared episode did not complete (exit={capture.exit_code}, state={capture.episode_state})")
        if capture.timed_out or capture.duration_s > profile.runner_timeout_s:
            raise RuntimeError("Formal Shared episode exceeded the approved outer timeout")
        if not capture.teardown_verified:
            raise RuntimeError("Formal backend did not verify Guest/container teardown")
        if set(capture.actors) != {"A", "B"}:
            raise RuntimeError("Formal runner did not capture both Actor records")
        if set(capture.relay_http_200) != {"A", "B"} or not all(capture.relay_http_200.values()):
            raise RuntimeError("Both Actor relays must have verified successful upstream HTTP 200 responses")
        if capture.actors["A"].container_id != capture.actors["B"].container_id:
            raise RuntimeError("Both Actors must be recorded against the same shared Guest container")
        if capture.actors["A"].pid == capture.actors["B"].pid:
            raise RuntimeError("Actor A and B must be distinct host Codex subprocesses")
        if any(capture.actor_statuses.get(role) not in {"completed", "declared_infeasible"} for role in ("A", "B")):
            raise RuntimeError("Both Actors must reach a terminal Codex result before grading")

        actor_archive: dict[str, Path] = {}
        actor_raw_events: dict[str, Path] = {}
        redact_summaries: dict[str, dict[str, Any]] = {}
        for role, capture_key in (("actor_a", "A"), ("actor_b", "B")):
            actor = capture.actors[capture_key]
            if actor.sandbox_mode != profile.sandbox_mode or actor.approval_policy != profile.approval_policy:
                raise RuntimeError(f"Actor {capture_key} observed sandbox/approval policy differs from the approved profile")
            if set(actor.tools_enabled) != set(profile.tools_enabled) or actor.shell_tool or actor.unified_exec:
                raise RuntimeError(f"Actor {capture_key} observed tool/shell policy differs from the approved profile")
            if actor.yolo_enabled:
                raise RuntimeError(f"Actor {capture_key} did not satisfy Non-YOLO policy")
            if not actor.guest_cli_shell or not actor.guest_cli_read_write:
                raise RuntimeError(f"Actor {capture_key} did not receive writable Guest CLI")
            if not actor.home or not actor.codex_home or not actor.cwd:
                raise RuntimeError(f"Actor {capture_key} is missing observed HOME/CODEX_HOME/CWD audit evidence")
            # Actor specs initially contain placeholder ports; validate the
            # ephemeral binding captured by the formal backend instead.
            _verify_actor_relay_binding(actor, capture_key, capture.metadata)
            out = run_dir / role
            out.mkdir(parents=True, exist_ok=True)
            redact_summaries[role] = {}
            for source, name in (
                (actor.actions_jsonl, "actions.jsonl"),
                (actor.codex_events_jsonl, "codex_events.jsonl"),
                (actor.timeline_events_jsonl, "timeline-events.jsonl"),
            ):
                raw_copy = out / ("." + name + ".raw")
                _safe_jsonl_copy(source, raw_copy)
                redacted = redact_events_file(raw_copy, out / name)
                raw_copy.unlink()
                redact_summaries[role][name] = {
                    key: redacted[key] for key in
                    ("redactor_version", "payloads_redacted", "base64_chars_omitted", "events_processed")
                }
            # Preserve every desktop step screenshot from the formal harness.
            screenshot_source = actor.actions_jsonl.parent / "shots"
            if screenshot_source.is_dir():
                _copy_tree(screenshot_source, out / "screenshots")
            raw_events = out / ".codex_events.jsonl.raw"
            _safe_jsonl_copy(actor.codex_events_jsonl, raw_events)
            audit = build_entry_audit(
                container_id=actor.container_id, uid=actor.uid, gid=actor.gid,
                actor_pid=actor.pid, actor_role=role,
                role_private_path=actor.private_guest_path,
                model_id=profile.model_id, sandbox_mode=profile.sandbox_mode,
                approval_policy=profile.approval_policy, tools_enabled=profile.tools_enabled,
                shell_tool=actor.shell_tool, unified_exec=actor.unified_exec,
                guest_cli_shell=actor.guest_cli_shell,
                guest_cli_read_write=actor.guest_cli_read_write,
                guest_workspace=guest_workspace,
                home=actor.home,
                codex_home=actor.codex_home,
                cwd=actor.cwd, codex_workdir=actor.codex_workdir,
                relay_port=actor.relay_port,
                host_shell_exposed=False, host_oracle_exposed=False,
                yolo_flag_used=False, yolo_enabled=actor.yolo_enabled,
            )
            cert = verify_episode_permissions(audit, session_event_files=[raw_events], expected_model=profile.model_id)
            raw_events.unlink()
            # The archive event stream is the redacted copy; turn_context policy
            # is verified against the original capture before that temporary copy
            # is removed.
            for context in cert["turn_contexts"]:
                context["source"] = "actor/codex_events.jsonl (redacted archive of verified source)"
            write_verified_certificate(out / "permission-audit-verified.json", cert)
            actor_archive[role] = out
            actor_raw_events[role] = actor.codex_events_jsonl

        timeline = merge_shared_timeline([
            run_dir / "actor_a" / "timeline-events.jsonl",
            run_dir / "actor_b" / "timeline-events.jsonl",
        ])
        write_shared_timeline(run_dir / "shared_timeline.json", timeline)

        path_audits = {
            role: path_reference_audit(
                actor=role, action_files=[run_dir / role / "actions.jsonl"]
            ) for role in ("actor_a", "actor_b")
        }
        blind_audit = merge_path_audits(path_audits)
        (run_dir / "blind-path-audit.json").write_text(
            json.dumps(blind_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        items = merge_directory_snapshot_items(
            _case_snapshot_items(config), config.get("host_snapshot_directories", []),
            capture.metadata.get("captured_directory_items", []))
        receipt = collect_completed_episode_snapshots(
            episode_state=capture.episode_state, items=items,
            destination_root=run_dir,
            read_guest_file=self.backend.read_guest_file,
        )
        endpoint_receipts: dict[str, dict[str, Any]] = {}
        for endpoint in config.get("host_http_snapshots", []):
            endpoint_id = str(endpoint["id"])
            parsed = urlparse(str(endpoint["url"]))
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", endpoint_id):
                raise ValueError("host HTTP snapshot IDs must be simple identifiers")
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise ValueError("host HTTP snapshots may only target loopback Guest services")
            archive_relative = Path(str(endpoint["archive_path"]))
            target = (run_dir / archive_relative).resolve()
            if (archive_relative.is_absolute() or not archive_relative.parts
                    or archive_relative.parts[0] != "host-snapshots"
                    or not target.is_relative_to(run_dir.resolve()) or ".." in archive_relative.parts):
                raise ValueError("host HTTP snapshot path escaped the episode archive")
            response = self.backend.read_guest_http(str(endpoint["url"]))
            if not isinstance(response, dict) or not isinstance(response.get("body"), bytes):
                raise RuntimeError("Guest service snapshot callback must return status metadata and response bytes")
            status_code = int(response.get("status_code", 0))
            body = response["body"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            body_json = None
            try:
                body_json = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            endpoint_receipts[endpoint_id] = {
                "url": str(endpoint["url"]), "status_code": status_code,
                "archive_path": archive_relative.as_posix(),
                "sha256": hashlib.sha256(body).hexdigest(),
                "body_json": sanitize(body_json) if body_json is not None else None,
            }
        receipt["http_endpoints"] = endpoint_receipts
        (run_dir / "snapshot-receipt.json").write_text(
            json.dumps(sanitize(receipt), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        grader = _load_grader(case_root)
        grade = grader(run_dir / "host-snapshots", receipt, run_id)
        from .grade import validate_grade, write_grade
        validate_grade(grade)
        write_grade(run_dir / "grade.json", grade)

        report = {
            "schema_version": "paragui.episode-report/v1",
            "case_id": case_id, "run_id": run_id, "mode": "shared",
            "runner_exit_code": capture.exit_code,
            "episode_state": capture.episode_state,
            "duration_s": capture.duration_s,
            "actor_statuses": capture.actor_statuses,
            "relay_http_200": capture.relay_http_200,
            "teardown_verified": capture.teardown_verified,
            "snapshot_receipt": receipt,
            "preparation_receipt": sanitize(preparation_receipt),
            "blind_path_audit": blind_audit,
            "redaction": redact_summaries,
            "backend_metadata": sanitize(capture.metadata),
            "grade_summary": {key: grade[key] for key in ("score_a", "score_b", "mean_score", "pass_a", "pass_b", "joint_pass")},
        }
        (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # A credential finding blocks archive completion; the summary itself is
        # value-free and retained for audit.
        # Original turn_contexts have already been verified. Minimize the
        # transient backend streams too; never weaken the secret scanner.
        backend_redactions = []
        for raw in sorted((run_dir / "backend-capture").glob("*.jsonl")):
            if "codex-events" not in raw.name and "sessions" not in raw.name:
                continue
            temporary = raw.with_name(raw.name + ".minimized")
            backend_redactions.append(redact_events_file(raw, temporary))
            os.replace(temporary, raw)
        (run_dir / "backend-redaction-summary.json").write_text(
            json.dumps(backend_redactions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scan = scan_paths([run_dir])
        (run_dir / "sensitive-scan-summary.json").write_text(json.dumps(scan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if scan["finding_count"]:
            raise RuntimeError(f"Sensitive scan failed with {scan['finding_count']} finding(s)")
        # All required logs/events have now been copied into the RAID archive,
        # and the backend has verified Guest teardown. Remove per-run Codex
        # homes and transient files from the bounded private host locations.
        remove_private_run_tree(runtime_run_root, runtime_parent)
        remove_private_run_tree(temp_run_root, temp_parent)
        # Manifest covers the whole batch and the current run. The Case definitions
        # are immutable inputs and are included in its file hashes.
        required_episode_files = [
            run_dir / "grade.json", run_dir / "report.json", run_dir / "shared_timeline.json",
            *[run_dir / role / name for role in ("actor_a", "actor_b")
              for name in ("actions.jsonl", "codex_events.jsonl", "permission-audit-verified.json")],
        ]
        missing_episode_files = [str(path.relative_to(run_dir)) for path in required_episode_files if not path.is_file()]
        if missing_episode_files:
            raise ValueError("Current episode archive is incomplete: " + ", ".join(missing_episode_files))
        validation = validate_batch(self.batch_root, ignore_incomplete_attempts=True)
        if not validation["ok"]:
            raise ValueError("Batch manifest validation failed: " + "; ".join(validation["errors"]))
        manifest_path = write_manifest(self.batch_root, ignore_incomplete_attempts=True)
        return {
            "case_id": case_id, "run_id": run_id, "run_dir": str(run_dir),
            "grade": grade, "manifest": str(manifest_path),
            "sensitive_scan": {"files_scanned": scan["files_scanned"], "finding_count": scan["finding_count"]},
        }
