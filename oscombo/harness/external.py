"""External-process harnesses: the agent is another program (an agent CLI, a different framework, ...).

``command``  run any program. ``options.command`` is an argv list (or one shell string) whose ``{placeholders}``
             are filled from: guest_url, instruction, instruction_file, agent_dir, action_log, max_steps, model,
             password, name, task_id. The same values are exported as ``OSCOMBO_*`` env vars. The program
             drives the Guest itself, e.g. through ``python -m oscombo.mcp_server`` (which honours
             OSCOMBO_GUEST_URL / OSCOMBO_ACTION_LOG / OSCOMBO_MAX_STEPS) or the Guest HTTP API directly.
``codex``    codex CLI with the ``oscombo.mcp_server`` desktop tools only (no shell, read-only sandbox).

Outcome: ``fail`` if ``<agent_dir>/INFEASIBLE`` exists (written by the MCP tool ``declare_infeasible``),
``done`` on exit code 0, ``timeout`` after ``options.timeout`` s (default 3600), ``error`` otherwise.
The action log (one json object per tool call) becomes the run trace.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..osworld import client_password
from ..policies.base import require_model
from .base import AgentContext, AgentResult, Harness

PROMPT = """You are operating an Ubuntu 22.04 GNOME desktop ONLY through the `desktop` MCP tools: screenshot,
click (clicks=2 for double click, button=right for context menu), type_text, key (key names like ctrl+s, Return,
Tab, alt+F4), scroll, drag, move, wait. Every action returns a fresh screenshot. You have no shell or file tools;
the desktop may be slow, so use `wait` when the UI is still loading. The user's password is `{password}`.
If the task is impossible as specified, call `declare_infeasible` instead.

Task: {instruction}

Start with a screenshot. Act step by step and verify results on screen. When done, stop and reply with one short
line."""


def fill(text: str, values: dict[str, str]) -> str:
    """Replace known ``{name}`` placeholders; other braces (e.g. inline code) stay as they are."""
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), text)


class CommandHarness(Harness):
    def prepare(self, ctx: AgentContext) -> None:
        self.opts = self.spec.get("options", {})
        self.dir = ctx.out / ctx.name
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "instruction.txt").write_text(ctx.instruction, encoding="utf-8")
        self.action_log = self.dir / "actions.jsonl"
        self.values = {"guest_url": ctx.guest.url, "instruction": ctx.instruction,
                       "instruction_file": str(self.dir / "instruction.txt"), "agent_dir": str(self.dir),
                       "action_log": str(self.action_log), "max_steps": str(ctx.max_steps),
                       "model": self.spec.get("model") or "", "password": client_password(), "name": ctx.name,
                       "task_id": ctx.task_id}

    def command(self, ctx: AgentContext) -> list[str]:
        cmd = self.opts.get("command")
        if not cmd:
            raise ValueError("command harness needs options.command")
        if isinstance(cmd, str):
            return ["bash", "-c", fill(cmd, {k: shlex.quote(v) for k, v in self.values.items()})]
        return [fill(str(part), self.values) for part in cmd]

    def env(self, ctx: AgentContext) -> dict[str, str]:
        return {**os.environ, **{f"OSCOMBO_{k.upper()}": v for k, v in self.values.items()}}

    def run(self, ctx: AgentContext) -> AgentResult:
        res = AgentResult(status="running")
        timeout = float(self.opts.get("timeout", 3600))
        started = time.monotonic()
        with open(self.dir / "stdout.log", "w") as out, open(self.dir / "stderr.log", "w") as err:
            proc = subprocess.Popen(self.command(ctx), env=self.env(ctx), cwd=self.dir, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
            while proc.poll() is None:
                if ctx.stop.is_set() or time.monotonic() - started > timeout:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    res.status = "timeout"
                    break
                time.sleep(2)
        res.extra["exit_code"] = proc.returncode
        res.extra["agent_s"] = round(time.monotonic() - started, 1)
        res.trace = self.trace(ctx)
        if (self.dir / "INFEASIBLE").exists():
            res.status = "fail"
        elif res.status != "timeout":
            res.status = "done" if proc.returncode == 0 else "error"
            if proc.returncode != 0:
                res.error = f"exit code {proc.returncode}"
        return res

    def trace(self, ctx: AgentContext) -> list[dict]:
        if not self.action_log.exists():
            return []
        recs = []
        for i, line in enumerate(self.action_log.read_text().splitlines(), 1):
            a = json.loads(line)
            t = round(a.pop("t", time.time()) - ctx.t0, 1)
            tool, before = a.pop("tool", "?"), a.pop("window_before", None)
            code = f"{tool}({', '.join(f'{k}={v!r}' for k, v in a.items())})"
            recs.append({"step": i, "t": t, "infer_s": None, "response": None,
                         "actions": [{"t": t, "window_before": before, "code": code[-300:]}],
                         "done": False, "fail": tool == "declare_infeasible"})
        return recs


class CodexHarness(CommandHarness):
    """codex CLI + desktop MCP tools. Options: ``codex_bin`` (default "codex"), ``base_url`` (default
    ``OPENAI_BASE_URL``), ``api_key_env`` (default "OPENAI_API_KEY"; if that variable is unset, no auth header),
    ``wire_api`` ("responses"), ``prompt_suffix``, ``extra_config`` (raw TOML appended to config.toml),
    ``timeout``. Reasoning effort comes from the spec's ``effort``."""

    def prepare(self, ctx: AgentContext) -> None:
        super().prepare(ctx)
        home = self.dir / "codex_home"
        home.mkdir(exist_ok=True)
        (self.dir / "work").mkdir(exist_ok=True)
        (home / "config.toml").write_text(self.config(ctx), encoding="utf-8")
        self.values["codex_home"] = str(home)

    def config(self, ctx: AgentContext) -> str:
        o = self.opts
        base_url = o.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        mcp_env = {"OSCOMBO_GUEST_URL": ctx.guest.url, "OSCOMBO_ACTION_LOG": str(self.action_log),
                   "OSCOMBO_MAX_STEPS": str(ctx.max_steps)}
        repo_root = str(Path(__file__).resolve().parents[2])
        mcp_env["PYTHONPATH"] = repo_root + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH")
                                             else "")
        env_toml = ", ".join(f"{k} = {json.dumps(v)}" for k, v in mcp_env.items())
        key_env = o.get("api_key_env", "OPENAI_API_KEY")
        auth = f"env_key = {json.dumps(key_env)}" if os.environ.get(key_env) else "requires_openai_auth = false"
        return f"""model = {json.dumps(require_model(self.spec))}
model_provider = "oscombo"
model_reasoning_effort = {json.dumps(self.spec.get("effort") or "medium")}
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"

[model_providers.oscombo]
name = "oscombo"
base_url = {json.dumps(base_url)}
{auth}
wire_api = {json.dumps(o.get("wire_api", "responses"))}
request_max_retries = 6
stream_max_retries = 6
stream_idle_timeout_ms = 300000

[features]
shell_tool = false
unified_exec = false
multi_agent = false
image_generation = false

[mcp_servers.desktop]
command = {json.dumps(sys.executable)}
args = ["-m", "oscombo.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 240
default_tools_approval_mode = "approve"
env = {{ {env_toml} }}
{o.get("extra_config", "")}
"""

    def command(self, ctx: AgentContext) -> list[str]:
        prompt = PROMPT.format(password=client_password(), instruction=ctx.instruction) + self.opts.get(
            "prompt_suffix", "")
        return [self.opts.get("codex_bin", "codex"), "exec", "--json", "--skip-git-repo-check",
                "-C", str(self.dir / "work"), prompt]

    def env(self, ctx: AgentContext) -> dict[str, str]:
        return {**super().env(ctx), "CODEX_HOME": self.values["codex_home"]}
