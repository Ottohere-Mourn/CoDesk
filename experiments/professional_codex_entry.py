"""Start the experimental Codex process only inside its isolated Docker harness."""
import argparse
import json
import os
from pathlib import Path


PERMISSION_MODES = ("reviewed", "container-unrestricted")
INTERACTION_MODES = ("hybrid", "gui-only")


def permissions(mode, interaction_mode="gui-only"):
    if mode not in PERMISSION_MODES:
        raise ValueError("Unknown Codex permission mode")
    if interaction_mode not in INTERACTION_MODES:
        raise ValueError("Unknown interaction mode")
    unrestricted = mode == "container-unrestricted"
    return {"mode": mode, "scope": "harness-container-only",
        "sandbox": "workspace-write",
        "configured_approval": "never" if unrestricted else "on-request",
        "native_approval_review": None if unrestricted else "--approve-for-me",
        "review_model_requested_by_cli": None if unrestricted else "codex-auto-review",
        "shell_tool": interaction_mode == "hybrid", "yolo_flag_used": False, "yolo_equivalent": False}


def codex_command(mode, interaction_mode="gui-only"):
    policy = permissions(mode, interaction_mode)
    command = ["/codex/codex", "exec"]
    command += ["-c", 'sandbox_mode="workspace-write"',
        "-c", 'approval_policy=' + json.dumps(policy["configured_approval"])]
    if mode == "reviewed":
        command += ["--approve-for-me"]
    return command + ["-c", "features.shell_tool=" + str(policy["shell_tool"]).lower(),
        "--skip-git-repo-check", "--json", "--color", "never",
        "--output-last-message", "/session/last-message.txt", "-C", "/session", "-"]


def require_container():
    if not Path("/.dockerenv").is_file():
        raise RuntimeError("Refusing to start experimental Codex outside Docker")
    if os.environ.get("CODEX_HOME") != "/session/codex-home" or os.environ.get("HOME") != "/session":
        raise RuntimeError("Refusing to use a host or non-isolated Codex home")
    if Path.cwd() != Path("/session") or os.getuid() == 0:
        raise RuntimeError("Expected the non-root isolated /session working directory")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permissions", choices=PERMISSION_MODES, default="reviewed")
    parser.add_argument("--interaction-mode", choices=INTERACTION_MODES, default="gui-only")
    args = parser.parse_args(argv)
    require_container()
    audit = dict(permissions(args.permissions, args.interaction_mode), docker_marker=True, uid=os.getuid(),
        codex_home=os.environ["CODEX_HOME"], home=os.environ["HOME"], cwd=str(Path.cwd()))
    Path("/session/permission-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    command = codex_command(args.permissions, args.interaction_mode)
    os.execv(command[0], command)


if __name__ == "__main__":
    main()
