"""Validated profile for new Shared-only episodes; this module starts no runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RunnerProfile:
    model_id: str = "gpt-6-sol"
    mode: str = "shared"
    max_cua_calls: int | None = None
    actor_timeout_s: int = 7200
    runner_timeout_s: int = 7200
    sandbox_mode: str = "workspace-write"
    approval_policy: str = "never"
    shell_tool: bool = True
    unified_exec: bool = False
    tools_enabled: tuple[str, ...] = ("desktop", "guest_cli")
    guest_cli_workspace: str = "/home/user/workspace"
    expose_host_shell: bool = False
    expose_host_oracle: bool = False
    yolo_enabled: bool = False
    countdown_injected: bool = False
    no_new_privileges: bool = True
    xvfb_auth_file: str = "/run/codesk/x99.auth"
    xvfb_extra_args: tuple[str, ...] = (
        "-screen", "0", "1920x1080x24", "+extension", "GLX",
        "+render", "-noreset", "-nolisten", "tcp",
    )

    def validate(self) -> "RunnerProfile":
        if self.mode != "shared":
            raise ValueError("This scaffold supports Shared A+B episodes only")
        if self.max_cua_calls is not None:
            raise ValueError("Step/tool-call caps are not allowed")
        if self.actor_timeout_s < 7200 or self.runner_timeout_s < 7200:
            raise ValueError("Actor and runner timeouts must each be at least 7200 seconds")
        if self.sandbox_mode != "workspace-write":
            raise ValueError("Guest work requires the workspace-write sandbox")
        if self.approval_policy != "never":
            raise ValueError("Unattended workspace-scoped runs require the audited never-approval policy")
        if not self.shell_tool or "guest_cli" not in self.tools_enabled or "desktop" not in self.tools_enabled:
            raise ValueError("Both desktop and Guest CLI tools must be enabled")
        if self.unified_exec:
            raise ValueError("Host/container unified_exec is outside this Guest CLI profile")
        if self.expose_host_shell or self.expose_host_oracle:
            raise ValueError("Host shell and host Oracle must remain outside the Guest")
        if self.yolo_enabled or not self.no_new_privileges:
            raise ValueError("Non-YOLO and no-new-privileges requirements must remain enabled")
        if self.countdown_injected:
            raise ValueError("Countdown injection is not allowed")
        if not self.xvfb_auth_file:
            raise ValueError("Xvfb authorization file is required")
        if "-ac" in self.xvfb_extra_args:
            raise ValueError("Xvfb -ac is forbidden; use -auth")
        return self

    def xvfb_command(self) -> list[str]:
        self.validate()
        return ["Xvfb", ":99", "-auth", self.xvfb_auth_file, *self.xvfb_extra_args]

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
