"""Small opt-in hook that adapts the existing CodexHarness MCP config for BC.

The Codex process remains the project's formal persistent harness. The hook
does not enable a host shell; it changes only the Codex workspace sandbox
declaration and replaces the legacy read-only Guest CLI MCP server with the
BC Guest-only read/write proxy.
"""

from __future__ import annotations

import re


LEGACY_GUEST_CLI_MODULE = 'args = ["-m", "oscombo.guest_cli_tools"]'


def patch_codex_config_text(text: str, guest_cli_module: str = "pipeline.guest_cli_rw_tools") -> str:
    sandbox = 'sandbox_mode = "read-only"'
    if text.count(sandbox) != 1:
        raise ValueError("Expected one legacy read-only sandbox declaration from the formal CodexHarness")
    if text.count(LEGACY_GUEST_CLI_MODULE) != 1:
        raise ValueError("Expected exactly one legacy read-only guest_cli MCP server")
    text = text.replace(sandbox, 'sandbox_mode = "workspace-write"', 1)
    text = text.replace(LEGACY_GUEST_CLI_MODULE, f'args = ["-m", "{guest_cli_module}"]', 1)
    # The current formal Guest transport submits execute requests with a
    # 30-second VM-side timeout. Keep the MCP deadline slightly above it.
    marker = '[mcp_servers.guest_cli]'
    start = text.find(marker)
    if start < 0:
        raise ValueError("Patched Codex config lacks its guest_cli server section")
    end = text.find("\n[", start + len(marker))
    end = len(text) if end < 0 else end
    block = text[start:end]
    # The runner version used on HealthCare derives guest_cli MCP's timeout
    # from max_timeout_sec + 10 (40s for a 30s Guest command). Older builds
    # emitted 30s directly. Accept those two known formal layouts only, then
    # normalize both to the safe 40s MCP envelope.
    block, count = re.subn(r"(?m)^tool_timeout_sec\s*=\s*(?:30|40)\s*$", "tool_timeout_sec = 40", block, count=1)
    if count != 1:
        raise ValueError("Unexpected legacy guest_cli MCP timeout; refusing to patch config")
    block, count = re.subn(
        r'(?m)(OSCOMBO_CLI_MAX_TIMEOUT_SEC\s*=\s*)"(?:20|30)"',
        r'\g<1>"30"', block, count=1,
    )
    if count != 1:
        raise ValueError("Unexpected legacy Guest CLI timeout setting; refusing to patch config")
    # The formal CodexHarness serializes its legacy command-name allowlist
    # into the MCP environment. The BC proxy intentionally does not consult
    # that variable, but publish an explicit wildcard so config inspection
    # cannot imply that the Guest command surface remains allowlisted.
    block, count = re.subn(
        r'OSCOMBO_CLI_ALLOWED_COMMANDS\s*=\s*"[^"]*"',
        'OSCOMBO_CLI_ALLOWED_COMMANDS = "*"', block, count=1,
    )
    if count != 1:
        raise ValueError("Expected the formal Guest CLI allowlist field; refusing ambiguous writable CLI config")
    return text[:start] + block + text[end:]


def patch_hybrid_prompt(text: str) -> str:
    replacements = {
        "through the GUI MCP tools and a restricted Guest CLI MCP tool":
            "through desktop GUI tools and a Guest CLI MCP tool with read, write, and command-execution access inside the Guest workspace",
        "The guest_cli tool runs only allowlisted read-only argv directly inside the OSWorld Guest; it is not a host shell and does not accept shell syntax. Use only the documented safe option subset.":
            "The guest_cli tool executes shell commands inside the OSWorld Guest workspace. It is not a host shell; host-side Oracle, ground truth, and queue control remain outside the Guest.",
        "Use GUI or restricted Guest CLI only as useful": "Use GUI or Guest CLI as useful",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def install_codex_harness_hook() -> None:
    """Monkey-patch only the formal CodexHarness config method for opted-in BC runs."""
    import os

    if os.environ.get("CODEDESK_BC_RW_CLI") != "1":
        return
    from oscombo.harness.external import CodexHarness

    if getattr(CodexHarness, "_bc_rw_cli_hook_installed", False):
        return
    original = CodexHarness.config

    def config_with_bc_guest_cli(self, ctx):
        original_text = original(self, ctx)
        return patch_codex_config_text(
            original_text,
            guest_cli_module=os.environ.get("CODEDESK_BC_GUEST_CLI_MODULE", "pipeline.guest_cli_rw_tools"),
        )

    CodexHarness.config = config_with_bc_guest_cli
    original_prompt = CodexHarness.prompt

    def prompt_with_guest_rw(self, ctx):
        text = original_prompt(self, ctx)
        return patch_hybrid_prompt(text)

    CodexHarness.prompt = prompt_with_guest_rw
    CodexHarness._bc_rw_cli_hook_installed = True
