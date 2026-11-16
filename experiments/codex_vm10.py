"""The installed official Codex CLI, running inside the same kind of task VM as Freehand."""
from __future__ import annotations

import io
import json
from pathlib import Path
import secrets
import shlex
import tarfile
import threading
import time
from types import SimpleNamespace

from oscombo.harness.base import AgentContext, AgentResult, Harness
from experiments.freehand_vm10 import load_module, read_trace, save
from experiments.responses_relay import ResponsesRelay


def config_text(model, effort, base_url):
    return f'''model = {json.dumps(model)}
model_provider = "paragui"
model_reasoning_effort = {json.dumps(effort)}
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"

[sandbox_workspace_write]
network_access = true

[model_providers.paragui]
name = "paraGUI experiment"
base_url = {json.dumps(base_url)}
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 3
stream_max_retries = 3
stream_idle_timeout_ms = 300000

[features]
multi_agent = false
image_generation = false
memories = false
shell_tool = true

[history]
persistence = "none"
'''


class CodexGuestHarness(Harness):
    def prepare(self, ctx: AgentContext):
        preparation_started = time.time()
        options = self.spec["options"]
        self.project = Path(options["project"])
        self.options = options
        module = load_module("paragui_mini_osworld_agent", Path(options["agent_path"]))
        self.module = module
        self.directory = ctx.out / ctx.name
        self.directory.mkdir(parents=True, exist_ok=True)
        save(self.directory / "prepare.json", {"status": "preparing", "started_at": preparation_started,
             "bootstrap_revision": "runtime-upload-300s", "runtime_upload_timeout_s": 300})
        (self.directory / "instruction.txt").write_text(ctx.instruction)
        self.rpc = module.FreehandOSWorldAgent()
        self.rpc.env = SimpleNamespace(controller=ctx.guest.env.controller,
                                       provider=ctx.guest.env.provider, user_simulator=None,
                                       action_history=[])
        from experiments.guest_rpc import protect_guest_reads
        protect_guest_reads(self.rpc, self.directory)
        self.info = json.loads(self.rpc._bash("python3 -c 'import json,os,pwd;from pathlib import Path;print(json.dumps({\"home\":str(Path.home()),\"user\":pwd.getpwuid(os.getuid()).pw_name,\"uid\":os.getuid()}))'"))
        self.root = self.info["home"] + "/.paragui-codex/" + ctx.name + "-" + secrets.token_hex(6)
        self.binary_dir = self.info["home"] + "/.local/lib/paragui-codex-0.163.0"
        installed = self.rpc._bash("test -x " + shlex.quote(self.binary_dir + "/codex") + " && echo ready || true").strip()
        if installed != "ready":
            archive = self.project / "runtime/codex.tar.gz"
            target = self.info["home"] + "/.paragui-codex-runtime.tar.gz"
            # The CLI archive is much larger than task files. Concurrent VM
            # uploads can exceed the adapter's ordinary 60-second socket limit.
            with archive.open("rb") as data:
                response = self.rpc.session.post(self.rpc.env.controller.http_server + "/setup/upload",
                    data={"file_path": target}, files={"file_data": (archive.name, data)}, timeout=300)
                response.raise_for_status()
            self.rpc._bash("mkdir -p " + shlex.quote(self.binary_dir) + " && tar -xzf " + shlex.quote(target)
                           + " -C " + shlex.quote(self.binary_dir), timeout=120)
        self.version = self.rpc._bash(shlex.quote(self.binary_dir + "/codex") + " --version").strip()
        save(self.directory / "prepare.json", {"status": "ready", "started_at": preparation_started,
             "finished_at": time.time(), "bootstrap_revision": "runtime-upload-300s",
             "runtime_upload_timeout_s": 300, "harness_version": self.version})

    def run(self, ctx: AgentContext):
        from freehand.gateway import provider_settings
        timeout = float(self.options.get("timeout", 1800))
        phase = self.directory / "codex/phase-01"
        phase.mkdir(parents=True, exist_ok=True)
        gateway = ResponsesRelay((ctx.guest.env.provider.network_config["gateway"], 0),
            phase / "gateway-trace", model=self.spec["model"], provider=provider_settings())
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
        started = time.time()
        state = {"agent": ctx.name, "task": ctx.task_id, "model": self.spec["model"],
                 "status": "running", "started_at": started, "guest_harness": self.root}
        save(self.directory / "state.json", state)
        status, error, native, summary = "error", None, {}, ""
        q = shlex.quote
        try:
            note = self.module.DESKTOP_NOTE
            begin = note.index("Screenshots and view-image attach")
            note = (note[:begin] + "Use Codex's built-in view_image tool on the PNG path returned by screenshot or view-image to see the actual image. Coordinates refer to original screenshot pixels.\n"
                    + "Finish with a short final response when the task is complete.\n")
            task = (f'<environment>\ncwd: {self.info["home"]}\nuser: {self.info["user"]}\n'
                    f'agent budget: {timeout} seconds\n</environment>\n\n' + ctx.instruction + "\n" + note)
            configuration = config_text(self.spec["model"], self.spec.get("effort") or "high", gateway.api_base)
            run_script = ("#!/bin/bash\nset -euo pipefail\n"
                + "export CODEX_HOME=" + q(self.root + "/codex-home") + "\n"
                + "export FREEHAND_HARNESS=" + q(self.root) + "\n"
                + "export PATH=" + q(self.binary_dir) + ':"$PATH"\n'
                + "cd " + q(self.info["home"]) + "\n"
                + "exec " + q(self.binary_dir + "/codex")
                + " exec --json --strict-config --ignore-rules --skip-git-repo-check -C " + q(self.info["home"])
                + " --output-last-message " + q(self.root + "/final.txt") + " - < " + q(self.root + "/task.md") + "\n")
            files = {"task.md": task.encode(), "codex-home/config.toml": configuration.encode(),
                "src/run.sh": run_script.encode(),
                "desktop.py": (Path(self.options["agent_path"]).parent / "desktop.py").read_bytes(),
                "runner.py": (self.project / "runtime/freehand/lifecycle.py").read_bytes()}
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
                for name, data in files.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o755 if name.endswith(".sh") else 0o644
                    bundle.addfile(info, io.BytesIO(data))
            self.rpc._bash("mkdir -p " + q(self.root + "/.state") + " " + q(self.root + "/log"))
            self.rpc._upload(archive.getvalue(), self.root + ".tar.gz")
            self.rpc._bash("tar -xzf " + q(self.root + ".tar.gz") + " -C " + q(self.root))
            self.rpc._bash("nohup setsid env -u API_KEY -u HF_TOKEN -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "
                + "python3 " + q(self.root + "/runner.py") + " " + q(self.root)
                + " > " + q(self.root + "/log/codex.jsonl") + " 2> " + q(self.root + "/log/runner.stderr")
                + " < /dev/null &")
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not ctx.stop.is_set():
                native = self.rpc._json_file(self.root + "/.state/runner-result.json")
                if native is not None:
                    status = "done" if native.get("exit_code") == 0 else "error"
                    if status == "error":
                        error = f"Codex exit code {native.get('exit_code')}"
                    break
                time.sleep(3)
            else:
                self.rpc._bash("python3 " + q(self.root + "/runner.py") + " " + q(self.root) + " --stop", timeout=20)
                status = "timeout"
            raw = self.rpc._file(self.root + "/final.txt")
            summary = raw.decode(errors="replace") if raw else ""
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
            try:
                self.rpc._bash("python3 " + q(self.root + "/runner.py") + " " + q(self.root) + " --stop", timeout=20)
            except Exception:
                pass
        finally:
            try:
                parent, name = self.root.rsplit("/", 1)
                self.rpc._bash("tar -czf " + q(self.root + ".collected.tar.gz") + " -C " + q(parent) + " " + q(name), timeout=120)
                data = self.rpc._file(self.root + ".collected.tar.gz", timeout=120)
                if data is None:
                    raise RuntimeError("Missing Codex guest trajectory archive")
                (phase / "guest-harness.tar.gz").write_bytes(data)
                screenshot = ctx.guest.env.controller.get_screenshot()
                if screenshot:
                    (phase / "final-screen.png").write_bytes(screenshot)
            except Exception as exc:
                (phase / "collection-error.txt").write_text(f"{type(exc).__name__}: {exc}")
            gateway.shutdown()
            gateway.server_close()
            thread.join(timeout=2)
        trace, metrics = read_trace(phase / "gateway-trace", ctx.t0)
        outcome = {"status": status, "error": error, "summary": summary,
                   "guest_harness": self.root, "guest_user": self.info["user"],
                   "native_result": native, "harness_version": self.version}
        save(phase / "outcome.json", outcome)
        save(self.directory / "state.json", state | {"status": status, "error": error,
            "finished_at": time.time(), **metrics})
        return AgentResult(status=status, error=error, trace=trace,
            extra={"agent_s": round(time.time() - started, 3), **metrics,
                   "codex_outcome": outcome, "harness_version": self.version,
                   "wall_timeout_s": timeout, "bootstrap_revision": "runtime-upload-300s"})
