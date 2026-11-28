"""Fail-closed command/config builder for the project's formal OSWorld runner.

This module builds the invocation and actor specs but does not launch a Guest,
container, relay, model request or queue.  The producer/queue adapter must use
the approved project runner to execute this plan and provide its callbacks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .profile import RunnerProfile


EFFECTIVE_UNLIMITED_STEPS = 2_147_483_647


def build_actor_specs(
    *, profile: RunnerProfile,
    codex_bin: str,
    node_bin: str,
    mcp_python: str,
    private_runtime_root: str,
    relay_ports: dict[str, int],
    mcp_pythonpath: str,
    guest_workspace: str = "/home/user/workspace",
) -> list[dict[str, Any]]:
    profile.validate()
    if set(relay_ports) != {"A", "B"} or any(not 1 <= int(port) <= 65535 for port in relay_ports.values()):
        raise ValueError("separate valid relay ports are required for A and B")
    result = []
    for role in ("A", "B"):
        result.append({
            "harness": "codex",
            "model": profile.model_id,
            "effort": "high",
            "options": {
                # oscombo's external harness defaults to 2400 seconds unless
                # each actor's own options.timeout is supplied.
                "timeout": profile.actor_timeout_s,
                "codex_bin": codex_bin,
                "node_bin": node_bin,
                "mcp_python": mcp_python,
                "private_runtime_dir": str(Path(private_runtime_root) / role),
                "base_url": f"http://127.0.0.1:{int(relay_ports[role])}/v1",
                "guest_cli": {
                    "root": guest_workspace,
                    # Do not install a command allowlist: this is the BC
                    # writable Guest shell. The host Oracle/control plane is
                    # excluded by the Guest VM boundary, not by this list.
                    "max_timeout_sec": 30,
                    "max_output_bytes": 1_000_000,
                },
                "mcp_env": {
                    "PYTHONPATH": os.pathsep.join((str(Path(__file__).resolve().parents[1]), mcp_pythonpath)),
                    "OSCOMBO_ACTOR_ID": role,
                    "OSCOMBO_CONDITION": "shared",
                    "OSCOMBO_GUEST_WORKSPACE": guest_workspace,
                    "OSCOMBO_CLI_ROOT": guest_workspace,
                },
            },
        })
    return result


def build_oscombo_invocation(
    *, python: str,
    task_a: str,
    task_b: str,
    run_root: str,
    agents_json: str,
    guest_image: str,
    run_id: str,
    profile: RunnerProfile | None = None,
) -> list[str]:
    selected = (profile or RunnerProfile()).validate()
    if not all((task_a, task_b, run_root, agents_json, guest_image, run_id)):
        raise ValueError("both task modules and all formal-runner paths are required")
    return [
        python, "-m", "oscombo", "run", "--mode", "parallel",
        "--tasks", task_a, task_b,
        "--out", run_root, "--agents", agents_json,
        "--image", guest_image,
        "--max-steps", str(EFFECTIVE_UNLIMITED_STEPS),
        "--setup-settle", "30", "--label", "run=" + run_id,
    ]


def build_runner_environment(
    *, base_environment: dict[str, str], neutral_cwd: str,
    staged_runner_source: str, runner_overlay: str, runner_src: str,
    compatibility_root: str, osworld_source: str,
    task_asset_root: str, guest_image: str, run_id: str, temp_root: str,
) -> tuple[str, dict[str, str]]:
    """Set import precedence and route subprocess scratch away from /tmp.

    ``temp_root`` must be a per-run private path prepared on a filesystem that
    honors POSIX directory permissions.  Bulk staging/output remains on RAID;
    temp_root is intentionally separate because the current RAID export does
    not preserve private directory modes.
    """
    search = [staged_runner_source, runner_overlay, runner_src, compatibility_root, osworld_source]
    pythonpath = os.pathsep.join(search)
    if not temp_root:
        raise ValueError("A dedicated non-/tmp temporary root is required")
    env = dict(base_environment)
    env.update({
        "PYTHONPATH": pythonpath,
        "OSWORLD_DIR": osworld_source,
        "PARAGUI_TASK_ASSETS": task_asset_root,
        "OSCOMBO_BACKEND": "docker",
        "OSCOMBO_GUEST_IMAGE": guest_image,
        "PYTHONUNBUFFERED": "1",
        "OSCOMBO_RUN_LABEL": run_id,
        "CODEDESK_BC_RW_CLI": "1",
        "CODEDESK_BC_GUEST_CLI_MODULE": "pipeline.guest_cli_rw_tools",
        "TMPDIR": temp_root,
        "TMP": temp_root,
        "TEMP": temp_root,
    })
    return neutral_cwd, env


def validate_plan(*, argv: list[str], actors: list[dict], env: dict[str, str], profile: RunnerProfile | None = None) -> None:
    selected = (profile or RunnerProfile()).validate()
    if "--mode" not in argv or argv[argv.index("--mode") + 1] != "parallel":
        raise ValueError("Shared A+B must run on one Guest using parallel mode")
    if "--max-steps" not in argv or int(argv[argv.index("--max-steps") + 1]) < EFFECTIVE_UNLIMITED_STEPS:
        raise ValueError("OSWorld compatibility step integer must be effectively unlimited")
    if len(actors) != 2 or any(actor.get("harness") != "codex" for actor in actors):
        raise ValueError("exactly two formal Codex actors are required")
    if {actor.get("options", {}).get("mcp_env", {}).get("OSCOMBO_ACTOR_ID") for actor in actors} != {"A", "B"}:
        raise ValueError("independent actor identities are required")
    for actor in actors:
        options = actor.get("options", {})
        if options.get("api_key") or options.get("OPENAI_API_KEY"):
            raise ValueError("API credentials must be injected by environment, never serialized in actor specs")
        if not options.get("private_runtime_dir") or not options.get("base_url"):
            raise ValueError("isolated runtime and local relay endpoint must be supplied")
        if os.name == "posix" and os.path.commonpath(("/tmp", os.path.abspath(options["private_runtime_dir"]))) == "/tmp":
            raise ValueError("Codex private runtime must not use the exhausted /tmp mount")
        cli = options.get("guest_cli")
        if not isinstance(cli, dict) or not cli.get("root"):
            raise ValueError("Guest read/write CLI MCP must be enabled for both actors")
    paths = env.get("PYTHONPATH", "").split(os.pathsep)
    if not paths or not env.get("OSWORLD_DIR") or not env.get("PARAGUI_TASK_ASSETS"):
        raise ValueError("staged import path, OSWorld path and task asset root are mandatory")
    if env.get("CODEDESK_BC_RW_CLI") != "1" or env.get("CODEDESK_BC_GUEST_CLI_MODULE") != "pipeline.guest_cli_rw_tools":
        raise ValueError("the staged Guest read/write CLI Codex config hook is not enabled")
    if paths[0] == env.get("OSWORLD_DIR"):
        raise ValueError("staging source must precede the OSWorld source on PYTHONPATH")
    temp_root = env.get("TMPDIR", "")
    if not temp_root or env.get("TMP") != temp_root or env.get("TEMP") != temp_root:
        raise ValueError("all process temp variables must point to the dedicated BC temp root")
    if os.name == "posix" and os.path.commonpath(("/tmp", os.path.abspath(temp_root))) == "/tmp":
        raise ValueError("the exhausted /tmp mount is forbidden for BC process scratch")
