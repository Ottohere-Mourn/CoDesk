"""External-process harnesses: the agent is another program (an agent CLI, a different framework, ...).

``command``  run any program. ``options.command`` is an argv list (or one shell string) whose ``{placeholders}``
             are filled from: guest_url, instruction, instruction_file, agent_dir, action_log, max_steps, model,
             password, name, task_id. The same values are exported as ``OSCOMBO_*`` env vars. The program
             drives the Guest itself, e.g. through ``oscombo.desktop_tools`` (which honours OSCOMBO_GUEST_URL /
             OSCOMBO_ACTION_LOG / OSCOMBO_MAX_STEPS) or the Guest HTTP API directly.
``codex``    unmodified codex CLI with the ``oscombo.desktop_tools`` MCP server only (no shell, read-only sandbox).
``pi``       unmodified pi coding agent with the same tools as a pi extension (no built-in tools).

codex and pi get the same tools, prompt and budget (``max_steps`` tool calls, screenshots included).
Outcome: ``fail`` if ``<agent_dir>/INFEASIBLE`` exists (tool ``declare_infeasible``), ``timeout`` after
``options.timeout`` s (default 2400), ``max_steps`` if the tool budget was used up, ``done`` on exit code 0,
``error`` otherwise. The action log (one json object per tool call) becomes the run trace.
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

PROMPT = """You are operating an Ubuntu 22.04 GNOME desktop (screenshots are 1280x720) ONLY through the desktop
tools: screenshot, click (clicks=2 for double click, button=right for context menu), type_text, key (key names like
ctrl+s, Return, Tab, alt+F4), scroll, drag, move, wait. Every action returns a fresh screenshot. You have no shell or
file tools; the computer is slow, so use `wait` when the UI is still loading. The user's password is
`{password}`. If the task is impossible as specified, call `declare_infeasible` instead.

Task: {instruction}

Start with a screenshot. Act step by step and verify results on screen. When done, stop and reply with one short line."""
REPO = str(Path(__file__).resolve().parents[2])


def fill(text: str, values: dict[str, str]) -> str:
    """Replace known ``{name}`` placeholders; other braces (e.g. inline code) stay as they are."""
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), text)


def _pythonpath() -> str:
    return REPO + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")


class CommandHarness(Harness):
    def prepare(self, ctx: AgentContext) -> None:
        self.opts = self.spec.get("options", {})
        self.dir = ctx.out / ctx.name
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "instruction.txt").write_text(ctx.instruction, encoding="utf-8")
        self.action_log = self.dir / "actions.jsonl"
        self.budget = ctx.max_steps
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
        env = {**os.environ, **{f"OSCOMBO_{k.upper()}": v for k, v in self.values.items()},
               "PYTHONPATH": _pythonpath()}
        if self.opts.get("node_bin"):  # agent CLIs installed outside PATH
            env["PATH"] = self.opts["node_bin"] + os.pathsep + env["PATH"]
        return env

    def run(self, ctx: AgentContext) -> AgentResult:
        res = AgentResult(status="running")
        timeout = float(self.opts.get("timeout", 2400))
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
        used = sum(1 for r in res.trace if r.get("tool") != "declare_infeasible")
        if (self.dir / "INFEASIBLE").exists():
            res.status = "fail"
        elif res.status == "timeout":
            pass
        elif used >= self.budget:
            res.status = "max_steps"
        elif proc.returncode == 0:
            res.status = "done"
        else:
            res.status = "error"
            res.error = f"exit code {proc.returncode}: " + (self.dir / "stderr.log").read_text()[-300:]
        return res

    def trace(self, ctx: AgentContext) -> list[dict]:
        """One trace record per tool call (``oscombo.desktop_tools`` log format)."""
        if not self.action_log.exists():
            return []
        recs = []
        for i, line in enumerate(self.action_log.read_text().splitlines(), 1):
            c = json.loads(line)
            t = round(c.get("t", time.time()) - ctx.t0, 1)
            recs.append({"step": c.get("n", i), "t": t, "tool": c.get("tool"), "args": c.get("args"),
                         "actions": ([{"t": t, "window_before": c.get("window_before"), "code": c["code"]}]
                                     if c.get("code") else []),
                         "done": False, "fail": c.get("tool") == "declare_infeasible"})
        return recs

    def version(self, binary: str) -> str | None:
        try:
            out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60,
                                 env=self.env_for_version()).stdout.strip()
            return out.splitlines()[-1] if out else None
        except Exception:
            return None

    def env_for_version(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.opts.get("node_bin"):
            env["PATH"] = self.opts["node_bin"] + os.pathsep + env["PATH"]
        return env

    def prompt(self, ctx: AgentContext) -> str:
        return PROMPT.format(password=client_password(), instruction=ctx.instruction) + self.opts.get(
            "prompt_suffix", "")


class CodexHarness(CommandHarness):
    """Options: ``codex_bin`` (default "codex"), ``node_bin`` (dir prepended to PATH), ``base_url`` (default
    ``OPENAI_BASE_URL``), ``api_key_env`` (default "OPENAI_API_KEY"; unset variable = no auth header),
    ``wire_api`` ("responses"), ``prompt_suffix``, ``extra_config`` (raw TOML appended), ``timeout``.
    Reasoning effort comes from the spec's ``effort``."""

    def prepare(self, ctx: AgentContext) -> None:
        super().prepare(ctx)
        home = self.dir / "codex_home"
        home.mkdir(exist_ok=True)
        (self.dir / "work").mkdir(exist_ok=True)
        (home / "config.toml").write_text(self.config(ctx), encoding="utf-8")
        self.values["codex_home"] = str(home)
        self.binary = self.opts.get("codex_bin", "codex")
        self.harness_version = self.version(self.binary)

    def config(self, ctx: AgentContext) -> str:
        o = self.opts
        base_url = o.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        mcp_env = {"OSCOMBO_GUEST_URL": ctx.guest.url, "OSCOMBO_ACTION_LOG": str(self.action_log),
                   "OSCOMBO_MAX_STEPS": str(ctx.max_steps), "PYTHONPATH": _pythonpath()}
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
args = ["-m", "oscombo.desktop_tools", "--mcp"]
startup_timeout_sec = 60
tool_timeout_sec = 300
default_tools_approval_mode = "approve"
env = {{ {env_toml} }}
{o.get("extra_config", "")}
"""

    def command(self, ctx: AgentContext) -> list[str]:
        return [self.binary, "exec", "--json", "--skip-git-repo-check", "-C", str(self.dir / "work"),
                self.prompt(ctx)]

    def env(self, ctx: AgentContext) -> dict[str, str]:
        return {**super().env(ctx), "CODEX_HOME": self.values["codex_home"]}

    def run(self, ctx: AgentContext) -> AgentResult:
        res = super().run(ctx)
        res.extra["harness_version"] = self.harness_version
        return res


class PiHarness(CommandHarness):
    """Options: ``pi_bin`` (default "pi"), ``node_bin``, ``base_url`` (default ``OPENAI_BASE_URL``), ``api``
    ("openai-responses"), ``api_key_env`` (default "OPENAI_API_KEY"), ``context_window`` (400000),
    ``max_tokens`` (32000), ``prompt_suffix``, ``timeout``. Thinking level comes from the spec's ``effort``."""

    def prepare(self, ctx: AgentContext) -> None:
        super().prepare(ctx)
        o = self.opts
        agent_dir = self.dir / "pi_agent"
        agent_dir.mkdir(exist_ok=True)
        base_url = o.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        key = os.environ.get(o.get("api_key_env", "OPENAI_API_KEY")) or "unused"
        provider = {"baseUrl": base_url, "api": o.get("api", "openai-responses"), "apiKey": key,
                    "models": [{"id": require_model(self.spec), "reasoning": True, "input": ["text", "image"],
                                "contextWindow": o.get("context_window", 400000),
                                "maxTokens": o.get("max_tokens", 32000)}]}
        (agent_dir / "models.json").write_text(json.dumps({"providers": {"oscombo": provider}}))
        os.chmod(agent_dir / "models.json", 0o600)  # holds the key
        self.values["pi_agent_dir"] = str(agent_dir)
        self.binary = o.get("pi_bin", "pi")
        self.harness_version = self.version(self.binary)

    def command(self, ctx: AgentContext) -> list[str]:
        ext = str(Path(__file__).resolve().parent / "pi_desktop.ts")
        return [self.binary, "-p", "--mode", "json", "--no-session", "--no-builtin-tools", "--no-extensions",
                "-e", ext, "--no-skills", "--no-context-files", "--no-prompt-templates",
                "--provider", "oscombo", "--model", require_model(self.spec),
                "--thinking", self.spec.get("effort") or "medium", self.prompt(ctx)]

    def env(self, ctx: AgentContext) -> dict[str, str]:
        return {**super().env(ctx), "PI_CODING_AGENT_DIR": self.values["pi_agent_dir"], "PI_OFFLINE": "1",
                "OSCOMBO_TOOLS_PY": sys.executable}

    def run(self, ctx: AgentContext) -> AgentResult:
        res = super().run(ctx)
        res.extra["harness_version"] = self.harness_version
        return res
