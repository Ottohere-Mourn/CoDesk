"""Run native Codex or Freehand pairs through a shared GUI/CLI desktop broker."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time

from experiments import professional_shared as shared
from experiments import professional_trajectories as collector
from experiments.professional_codex_entry import INTERACTION_MODES, PERMISSION_MODES, permissions
from experiments.codesk_container_codex import codex_requirements_mount
from experiments.professional_tools import action_commands, tool_schema
from experiments.responses_relay import ResponsesRelay, image_history_policy


RULES = """You are operating a real professional application on a shared Linux desktop.
Only your own task is provided. Another independent agent works in the SAME application
and /workspace. Preserve its work; the screen can change between observations.
There is no communication tool or input lock. Coordinates refer to a 1280x800 screenshot.
The target files are only in the desktop container, not in this harness container.
The only route to that desktop is the desktop tool/bridge. Graders and references are unavailable.
Save the editable project and requested exports. Report partial work honestly; do not invent success.
"""


def interaction_rules(interaction_mode):
    if interaction_mode not in INTERACTION_MODES:
        raise ValueError("Unknown interaction mode")
    if interaction_mode == "gui-only":
        return RULES + ("This is the GUI-only ablation. Use normal GUI controls and expression fields only. "
            "Do not open terminals, Python/JavaScript consoles or script/macro editors, or execute scripts.\n")
    return RULES + ("This is the hybrid GUI+CLI condition. Programming is allowed: use shell commands, "
        "scripts, application APIs (such as bpy/PyQGIS), consoles and GUI tools as useful. "
        "Your native shell runs in the isolated harness /session, not the target desktop. "
        "For target CLI execution, call the desktop tool with a single shell action: "
        '{"actions":[{"type":"shell","command":"pwd","timeout":30}]}. '
        "It runs in /workspace as the desktop user with the same DISPLAY, and returns output and a screenshot. "
        "Do not background commands; process-group children are stopped on return. "
        "Both agents share the live project and filesystem. Keep code edits scoped to your own objects; "
        "do not replace the live document with an outdated offline copy or erase the other agent's work. "
        "Auxiliary CLI processes are allowed, but separate private final projects are not a substitute "
        "for the common final artifact. Check that saved files and the visible application agree. "
        "Do not access graders, reference answers, harness infrastructure or host files.\n")


def codex_config(model, effort, api_base, interaction_mode="gui-only"):
    interaction_rules(interaction_mode)
    return f'''model = {json.dumps(model)}
model_provider = "paragui"
model_reasoning_effort = {json.dumps(effort)}
approval_policy = "on-request"
sandbox_mode = "workspace-write"
web_search = "disabled"

[model_providers.paragui]
name = "paraGUI host relay"
base_url = {json.dumps(api_base)}
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 3
stream_max_retries = 3
stream_idle_timeout_ms = 180000

[features]
shell_tool = {str(interaction_mode == "hybrid").lower()}
multi_agent = false
image_generation = false
memories = false

[sandbox_workspace_write]
writable_roots = ["/session", "/tmp"]
network_access = true

[mcp_servers.desktop]
command = "python3"
args = ["/bridge/client.py", "--mcp"]
env_vars = ["PARAGUI_DESKTOP_URL"]
startup_timeout_sec = 30
tool_timeout_sec = 180
default_tools_approval_mode = "approve"

[history]
persistence = "none"
'''


def validate_actions(payload, remaining, interaction_mode="gui-only"):
    actions = payload.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 12:
        raise ValueError("Supply 1 to 12 desktop actions")
    if len(actions) > remaining:
        raise ValueError("Desktop action budget exceeded")
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Each action must be an object")
        action_commands(action, interaction_mode)
    if any(action["type"] == "shell" for action in actions) and len(actions) != 1:
        raise ValueError("A shell command must be the only action in its call")
    return actions


class DesktopSession:
    def __init__(self, desktop, timeline, root, task, args):
        self.root, self.task, self.args = root, task, args
        self.desktop = shared.AgentDesktop(desktop, task, timeline)
        self.timeline = timeline
        self.lock = threading.Lock()
        self.actions = 0
        self.action_counts = Counter()
        self.responses = 0
        self.turn = 0
        self.closed = False
        self.deadline = float("inf")
        (root / "screenshots").mkdir(parents=True)
        self.desktop.screenshot(root / "screenshots/0000.png")
        self.timeline.model_observations[task] = dict(self.timeline.observations[task])

    def perform(self, payload):
        if not self.lock.acquire(blocking=False):
            return {"error": "This agent already has an outstanding desktop call"}
        try:
            if self.closed or time.monotonic() >= self.deadline:
                return {"error": "Agent session has ended"}
            actions = validate_actions(payload, self.args.max_actions - self.actions, self.args.interaction_mode)
            feedback = []
            for action in actions:
                if self.closed or time.monotonic() >= self.deadline:
                    break
                commands = action_commands(action, self.args.interaction_mode)
                channel = "cli" if action["type"] == "shell" else (
                    "observation" if action["type"] in ("screenshot", "wait") else "gui")
                step = self.actions + 1
                event = {"step": step, "turn": self.turn, "call_id": f"{self.task}-batch-{self.actions}",
                    "action": action, "commands": commands, "channel": channel, "started_at": time.time(),
                    "elapsed_s": round(time.time() - self.started_at, 3),
                    "window_before": self.desktop.focus(), "screenshot_before": f"screenshots/{step-1:04d}.png",
                    "screenshot_after": f"screenshots/{step:04d}.png", "status": "ok"}
                self.timeline.record(self.task, "action_start", event)
                try:
                    for argv in commands:
                        if channel == "cli":
                            timeout = min(float(argv[-1]), max(.001, self.deadline - time.monotonic()))
                            argv[-1] = str(timeout)
                            response = self.desktop.raw(argv, timeout=timeout + 10)
                            event["shell_result"] = json.loads(response.stdout)
                            if event["shell_result"]["exit_code"] or event["shell_result"]["timed_out"]:
                                event["status"] = "error"
                        else:
                            self.desktop.raw(argv)
                except Exception as error:
                    event.update(status="error", error_type=type(error).__name__)
                    self.desktop.raw(["xdotool", "keyup", "ctrl", "shift", "alt"], check=False)
                finally:
                    self.timeline.record(self.task, "input_end", event)
                time.sleep(min(10, max(0, float(action.get("seconds", .35)))) if action["type"] == "wait" else .35)
                event["window_after"] = self.desktop.focus()
                self.desktop.screenshot(self.root / event["screenshot_after"])
                event["duration_s"] = round(time.time() - event["started_at"], 3)
                self.timeline.record(self.task, "action_end", event)
                collector.append(self.root / "actions.jsonl", event)
                self.actions = step
                self.action_counts[channel] += 1
                feedback.append({key: event[key] for key in
                    ("step", "status", "action", "channel", "shell_result", "error_type") if key in event})
                if event["status"] != "ok":
                    break
            return {"actions": feedback, "actions_remaining": self.args.max_actions - self.actions,
                "seconds_remaining": max(0, round(self.deadline - time.monotonic())),
                "image": base64.b64encode((self.root / f"screenshots/{self.actions:04d}.png").read_bytes()).decode()}
        except (ValueError, KeyError, TypeError) as error:
            return {"error": str(error)}
        finally:
            self.lock.release()


class DesktopHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if not secrets.compare_digest(self.path, "/" + self.server.capability):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 131072:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            result = self.server.session.perform(payload)
        except (ValueError, TypeError) as error:
            result = {"error": str(error)}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class NativeTrace:
    def __init__(self, root, session):
        from freehand.harness.calltrace import Trace
        self.trace = Trace(root / "gateway-trace")
        self.root, self.session = root, session
        self.starts = {}
        self.models = {}
        self.image_histories = {}

    def request(self, body, key, turn):
        number = self.trace.request(body, key, turn)
        self.starts[number] = time.time()
        self.models[number] = body.get("model")
        self.session.turn = number
        self.session.timeline.record(self.session.task, "model_request", {"turn": number})
        return number

    def note(self, number, kind, **fields):
        self.trace.note(number, kind, **fields)
        if kind == "image_history":
            self.image_histories[number] = {key: fields[key] for key in
                ("original_images", "sent_images", "omitted_images", "pinned_images", "latest_tool_images")}

    def response(self, number, ok, **fields):
        self.trace.response(number, ok, **fields)
        self.session.responses += int(ok)
        record = {"turn": number, "started_at": self.starts[number], "ok": ok,
            "http_status": fields.get("status"), "latency_s": fields["latency_s"], "usage": fields.get("usage"),
            "requested_model": self.models[number]}
        if number in self.image_histories:
            record["image_history"] = self.image_histories[number]
        collector.append(self.root / "requests.jsonl", record)
        self.session.timeline.record(self.session.task, "model_response", record)


def start_server(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def create_network(name):
    identifiers = collector.command(["docker", "network", "ls", "-q"], text=True).stdout.split()
    networks = json.loads(collector.command(["docker", "network", "inspect", *identifiers], text=True).stdout)
    used = [ipaddress.ip_network(entry["Subnet"]) for network in networks
        for entry in (network.get("IPAM", {}).get("Config") or []) if entry.get("Subnet")]
    routes = json.loads(collector.command(["ip", "-j", "-4", "route"], text=True).stdout)
    used.extend(ipaddress.ip_network(route["dst"], strict=False) for route in routes
        if route.get("dst") and route["dst"] != "default")
    for candidate in ipaddress.ip_network("10.252.240.0/24").subnets(new_prefix=28):
        if any(candidate.overlaps(existing) for existing in used if existing.version == 4):
            continue
        collector.command(["docker", "network", "create", "--internal", "--subnet", str(candidate), name])
        return str(next(candidate.hosts()))
    raise RuntimeError("No unused subnet in the experiment's private network range")


def prepare_native(root, args, config, api_base, instruction):
    session = root / "runtime"
    session.mkdir()
    rules = interaction_rules(args.interaction_mode)
    if not getattr(args, "coagent_hint", True):
        rules = rules.replace("Another independent agent works in the SAME application\nand /workspace.",
            "You are the only active agent in this condition; keep unowned project content unchanged.")
        rules = rules.replace("Both agents share the live project and filesystem.",
            "Preserve the current live project and its unowned filesystem content.")
    prompt = rules + "\n" + instruction
    collector.save(root / "prompt.json", {"instructions": rules, "task": instruction,
        "interaction_mode": args.interaction_mode})
    if args.harness == "codex":
        home = session / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text(codex_config(config["model"], config.get("reasoning_effort", "high"), api_base,
            args.interaction_mode))
        (session / "task.md").write_text(prompt + "\nStart by calling the desktop MCP tool with a screenshot action.")
        command = ["python3", "/bridge/codex_entry.py", "--permissions", args.codex_permissions,
            "--interaction-mode", args.interaction_mode]
    else:
        from freehand.harness.agent import DEFAULT_CONFIG
        shutil.copytree(args.freehand_runtime / "freehand/harness", session / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        original = (args.freehand_runtime / "freehand/prompt.md").read_text().replace("/freehand/harness", "/session")
        (session / "prompt.md").write_text(original + "\n\n" + rules)
        instructions = ("\nYour bash tool runs in your isolated harness container, NOT the target desktop. "
            "You may manage your own harness/context there. For ALL target task actions, call:\n"
            "python3 /bridge/client.py '{\"actions\":[{\"type\":\"screenshot\"}]}'\n"
            "The bridge automatically attaches the resulting screenshot. Other action types:\n" +
            tool_schema(args.interaction_mode)["description"] + "\nStart with a screenshot. Do not try to find target files locally.")
        (session / "task.md").write_text(prompt + instructions)
        collector.save(session / "config.json", dict(DEFAULT_CONFIG, model=config["model"],
            reasoning_effort=config.get("reasoning_effort", "high"), api_base=api_base.removesuffix("/v1"),
            max_turns=args.max_turns, workdir="/session", image_history_limit=args.image_history_limit))
        command = ["bash", "/session/src/run.sh"]
    return session, command


def container_launch(args, runtime, container, network, broker_url, command):
    launch = ["docker", "run", "-i", "--rm", "--name", container, "--network", network,
        "--cpus", "2", "--memory", "2g", "--pids-limit", "128", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--user", f"{os.getuid()}:{os.getgid()}", "-v", str(runtime) + ":/session",
        "-v", str(args.out / "bridge") + ":/bridge:ro", "-w", "/session",
        "-e", "HOME=/session", "-e", "CODEX_HOME=/session/codex-home",
        "-e", "FREEHAND_HARNESS=/session", "-e", "FREEHAND_TRACE=/session/native-trace",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", f"PARAGUI_DESKTOP_URL={broker_url}"]
    if args.harness == "codex":
        launch += codex_requirements_mount()
        launch += ["-v", str(args.codex_binary.parent) + ":/codex:ro"]
    return launch + [args.image, *command]


def audit_codex_permissions(runtime, mode, model, interaction_mode="gui-only"):
    expected = permissions(mode, interaction_mode)
    audit = json.loads((runtime / "permission-audit.json").read_text())
    if any(audit.get(key) != value for key, value in expected.items()):
        raise ValueError("Container entry permission audit does not match the requested policy")
    if audit.get("docker_marker") is not True or audit.get("uid", 0) <= 0:
        raise ValueError("Missing non-root Docker entry evidence")
    if audit.get("codex_home") != "/session/codex-home" or audit.get("home") != "/session" or audit.get("cwd") != "/session":
        raise ValueError("Codex entry used a non-isolated home or working directory")
    contexts = []
    for path in (runtime / "codex-home/sessions").rglob("*.jsonl"):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            context = event.get("payload", {})
            if event.get("type") != "turn_context":
                continue
            if (context.get("permission_profile") or {}).get("type") == "disabled":
                raise ValueError("Native Codex turn permissions disable the sandbox")
            effective = {"approval": context.get("approval_policy"),
                "sandbox": context.get("sandbox_policy", {}).get("type"), "cwd": context.get("cwd")}
            if context.get("model") != model or effective != {"approval": expected["configured_approval"], "sandbox": expected["sandbox"], "cwd": "/session"}:
                raise ValueError("Native Codex turn permissions do not match the container-only policy")
            if effective not in contexts:
                contexts.append(effective)
    if not contexts:
        raise ValueError("No native Codex task turn context available to verify permissions")
    return {"entry": audit, "effective_turn_contexts": contexts}


def run_agent(args, config, desktop, timeline, task, gateway, network, barrier):
    root = args.out / task
    source = args.dataset / "dataset/pairs" / args.pair
    instruction = (source / f"task_{task[-1]}.md").read_text()
    if args.smoke:
        instruction = "Preflight only: obtain a screenshot with the desktop bridge, report the visible application's title, then finish. Do not modify the project."
        if args.interaction_mode == "hybrid":
            instruction += (' Also call the desktop tool with {"actions":[{"type":"shell",'
                '"command":"printf paragui-hybrid-ok; pwd; id -u","timeout":10}]} '
                "to verify target-container CLI access before finishing.")
    session = DesktopSession(desktop, timeline, root, task, args)
    (root / "instruction.txt").write_text(instruction)
    broker = ThreadingHTTPServer((gateway, 0), DesktopHandler)
    broker.capability = secrets.token_urlsafe(32)
    broker.session = session
    start_server(broker)
    trace = NativeTrace(root, session)
    provider = {"url": config["base_url"].rstrip("/") + "/responses",
        "headers": {"Authorization": "Bearer " + config["api_key"], "Content-Type": "application/json"}}
    relay = start_server(ResponsesRelay((gateway, 0), root / "gateway-trace",
        model=config["model"], provider=provider, trace=trace, upstream_timeout=180,
        image_history_limit=args.image_history_limit,
        allowed_models=["codex-auto-review"] if args.harness == "codex" and args.codex_permissions == "reviewed" else []))
    runtime, command = prepare_native(root, args, config, relay.api_base, instruction)
    container = desktop.name + "-" + task + "-" + args.harness
    result = {"task": task, "mode": args.mode, "harness": args.harness, "container": desktop.name,
        "harness_container": container, "model": config["model"], "reasoning_effort": config.get("reasoning_effort", "high"),
        "access": "gui-cli-via-broker" if args.interaction_mode == "hybrid" else "gui-via-broker",
        "interaction_mode": args.interaction_mode, "codex_cli": args.harness == "codex",
        "image_history_policy": image_history_policy(args.image_history_limit),
        "yolo_enabled": args.harness == "codex" and permissions(args.codex_permissions)["yolo_equivalent"],
        "yolo_flag_used": False,
        "codex_permissions": permissions(args.codex_permissions, args.interaction_mode) if args.harness == "codex" else None,
        "status": "starting", "input_hashes": collector.hashes(source / "inputs")}
    collector.save(root / "result.json", result)
    launch = container_launch(args, runtime, container, network,
        f"http://{gateway}:{broker.server_port}/{broker.capability}", command)
    process = None
    try:
        barrier.wait(timeout=120)
        session.started_at = time.time()
        session.deadline = time.monotonic() + args.timeout
        result.update(status="running", agent_started_at=session.started_at)
        collector.save(root / "result.json", result)
        timeline.record(task, "agent_started", {})
        with (root / "native.stdout").open("wb") as stdout, (root / "native.stderr").open("wb") as stderr:
            process = subprocess.Popen(launch, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            process.stdin.write((runtime / "task.md").read_bytes() if args.harness == "codex" else b"")
            process.stdin.close()
            reason = None
            while process.poll() is None:
                if time.monotonic() >= session.deadline:
                    reason = "timeout"
                elif session.actions >= args.max_actions:
                    reason = "action_budget"
                elif session.responses >= args.max_turns:
                    reason = "response_budget"
                if reason:
                    collector.command(["docker", "stop", "-t", "2", container], timeout=15, check=False)
                    break
                time.sleep(1)
            result.update(exit_code=process.wait(timeout=20), status=reason or "completed")
            if not reason and result["exit_code"]:
                result["status"] = "error"
        if args.harness == "freehand" and (runtime / ".state/meta.json").exists():
            native = json.loads((runtime / ".state/meta.json").read_text())
            result.update(native_status=native.get("status"), agent_summary=native.get("finish_summary"))
            if result["status"] == "completed" and native.get("status") != "done":
                result["status"] = native.get("status", "error")
        elif (runtime / "last-message.txt").exists():
            result["agent_summary"] = (runtime / "last-message.txt").read_text()
        if args.harness == "codex":
            result["permission_audit"] = audit_codex_permissions(runtime, args.codex_permissions, config["model"], args.interaction_mode)
    except Exception as error:
        barrier.abort()
        result.update(status="error", error=f"{type(error).__name__}: {error}")
    finally:
        session.closed = True
        collector.command(["docker", "rm", "-f", container], check=False)
        if process and process.poll() is None:
            process.wait(timeout=20)
        with session.lock:
            pass
        broker.shutdown()
        broker.server_close()
        relay.shutdown()
        relay.server_close()
        result.update(finished_at=time.time(), actions=session.actions, model_responses=session.responses,
            broker_action_counts=dict(session.action_counts))
        if not session.responses:
            result.update(status="infrastructure_error", error="No successful model response was collected")
        timeline.record(task, "agent_finished", {"status": result["status"]})
        collector.save(root / "result.json", result)
        collector.render_trial(root)
    return result


def report(root, manifest, results):
    metrics, actions = shared.analyze(root, results)
    collector.save(root / "concurrency.json", metrics)
    lines = ["# Native harness / professional shared desktop", "",
        f"Harness: {manifest['harness']}; mode: {manifest['mode']}; smoke: {manifest['smoke']}", "",
        "Codex permission policy (container only): " + json.dumps(manifest["codex_permissions"]),
        "No host or VM Codex configuration is changed. Interaction mode: " + manifest["interaction_mode"],
        "Outbound image-history policy: " + json.dumps(manifest["image_history_policy"]),
        "Freehand retains its original loop, Bash, context editing and restart supervisor in an isolated harness container.",
        "Both reach task files via the same desktop broker. Hybrid allows CLI/code; GUI-only is an explicit ablation.",
        "Broker CLI calls, GUI input and observations are counted separately. Native harness shell calls remain in native logs.",
        "No task workspace, Docker socket, host home, grader, reference or upstream credential is mounted into either harness.",
        "No cross-agent input lock, refocusing or communication. Per-agent overlapping calls are refused.", "",
        "| Task | Stop | Score | Actions | Responses |", "|---|---|---:|---:|---:|"]
    for result in results:
        lines.append(f"| {result['task']} | {result['status']} | {result.get('score', 'not evaluated')} | {result['actions']} | {result['model_responses']} |")
    lines += ["", "Both scores use the common frozen final files after both agents and the desktop stop.",
        "Single runs are not success-rate estimates. No matched sequential control is included in this pilot.",
        "Native context management/tool packaging differ; this is not a pure model comparison.",
        "Raw grader limitations (FreeCAD SVG representation, QGIS note wording) remain unchanged.",
        "", "```json", json.dumps(metrics, indent=2), "```"]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    frames = [{"task": event["task"], "step": event["step"], "action": event["action"],
        "channel": event.get("channel", "gui"), "shell_result": event.get("shell_result"),
        "image": event["task"] + "/" + event["screenshot_after"]} for event in actions]
    data = json.dumps(frames).replace("<", "\\u003c")
    (root / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>Native shared replay</title>'
        '<h1>Native shared desktop replay</h1><a href="REPORT.md">Report</a>'
        '<input id="step" type="range" min="0" value="0"><pre id="info"></pre><img id="image" width="1000">'
        '<script>const frames=' + data + ';const slider=document.getElementById("step");'
        'slider.max=Math.max(0,frames.length-1);function show(){const frame=frames[+slider.value];'
        'document.getElementById("info").textContent=JSON.stringify(frame,null,2);'
        'if(frame)document.getElementById("image").src=frame.image;}slider.oninput=show;show();</script>')
    return metrics


def validate_freehand_runtime(root):
    root = root.resolve()
    if not (root / "freehand/harness/calltrace.py").is_file():
        raise ValueError("--freehand-runtime must be the parent directory containing freehand/harness/calltrace.py")
    return root


def task_schedule(args):
    roles = getattr(args, "task_roles", "ab")
    if not isinstance(roles, str) or not roles or any(role not in "abcd" for role in roles) or len(set(roles)) != len(roles):
        raise ValueError("Task roles must be unique letters from a through d")
    waves = getattr(args, "task_waves", None)
    if waves is None:
        waves = [roles] if getattr(args, "mode", "parallel") == "parallel" else list(roles)
    if not isinstance(waves, (list, tuple)) or not waves or any(not isinstance(wave, str) or not wave for wave in waves):
        raise ValueError("Task waves must be nonempty role strings")
    if "".join(waves) != roles:
        raise ValueError("Task waves must cover the selected roles exactly once, in order")
    return roles, list(waves)


def execute_waves(tasks, waves, execute):
    results = []
    for wave in waves:
        selected = [task for task in tasks if task[-1] in wave]
        barrier = threading.Barrier(len(selected))
        if len(selected) == 1:
            results.append(execute(selected[0], barrier))
        else:
            with ThreadPoolExecutor(max_workers=len(selected)) as executor:
                futures = [executor.submit(execute, task, barrier) for task in selected]
                results.extend(future.result() for future in futures)
    return results


def run(args):
    task_roles, waves = task_schedule(args)
    args.freehand_runtime = validate_freehand_runtime(args.freehand_runtime)
    args.out, args.dataset = args.out.resolve(), args.dataset.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.credentials.read_text())
    sys.path.insert(0, str(args.freehand_runtime))
    bridge = args.out / "bridge"
    bridge.mkdir()
    shutil.copy2(Path(__file__).with_name("professional_bridge.py"), bridge / "client.py")
    shutil.copy2(Path(__file__).with_name("professional_codex_entry.py"), bridge / "codex_entry.py")
    collector.save(bridge / "schema.json", tool_schema(args.interaction_mode))
    target = args.out / "shared"
    target.mkdir()
    shutil.copytree(args.dataset / "dataset/pairs" / args.pair / "inputs", target / "workspace")
    desktop = collector.Desktop(target, args.pair, args.image)
    network = desktop.name + "-agents"
    tasks = [args.pair + side for side in task_roles]
    manifest = {"harness": args.harness, "tasks": tasks, "mode": args.mode, "smoke": args.smoke,
        "task_waves": waves, "max_concurrent_agents": max(map(len, waves)),
        "interaction_mode": args.interaction_mode,
        "image_history_policy": image_history_policy(args.image_history_limit),
        "model": config["model"], "reasoning_effort": config.get("reasoning_effort", "high"),
        "started_at": time.time(), "status": "starting",
        "yolo_enabled": args.harness == "codex" and permissions(args.codex_permissions)["yolo_equivalent"],
        "yolo_flag_used": False, "codex_cli": args.harness == "codex",
        "codex_permissions": permissions(args.codex_permissions, args.interaction_mode) if args.harness == "codex" else None,
        "dataset": str(args.dataset), "desktop_count": 1, "initial_application_instances": 1,
        "auxiliary_cli_processes_allowed": args.interaction_mode == "hybrid",
        "max_actions_per_agent": args.max_actions, "max_turns_per_agent": args.max_turns,
        "timeout_per_agent_s": args.timeout, "input_mediation": "none across agents",
        "coagent_hint": getattr(args, "coagent_hint", True), "reference_exposed": False, "source_hashes": {}}
    manifest["image"] = args.image
    manifest["image_id"] = collector.command(["docker", "image", "inspect", args.image,
        "--format", "{{.Id}}"], text=True).stdout.strip()
    for filename in ("professional_native.py", "professional_bridge.py", "professional_codex_entry.py", "professional_shared.py",
                     "professional_trajectories.py", "professional_tools.py", "professional_shell.py", "responses_relay.py"):
        source = Path(__file__).with_name(filename)
        shutil.copy2(source, args.out / filename)
        manifest["source_hashes"][filename] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest["freehand_source_hashes"] = collector.hashes(args.freehand_runtime / "freehand/harness")
    if args.harness == "codex":
        manifest["codex_version"] = collector.command([str(args.codex_binary), "--version"], text=True).stdout.strip()
        manifest["codex_binary_sha256"] = hashlib.sha256(args.codex_binary.read_bytes()).hexdigest()
    collector.save(args.out / "manifest.json", manifest)
    results = []
    try:
        gateway = create_network(network)
        desktop.start()
        manifest.update(status="running", container=desktop.name)
        collector.save(args.out / "manifest.json", manifest)
        timeline = shared.Timeline(args.out)
        results = execute_waves(tasks, waves, lambda task, barrier:
            run_agent(args, config, desktop, timeline, task, gateway, network, barrier))
    except Exception as error:
        manifest.update(status="error", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        desktop.stop()
        collector.command(["docker", "network", "rm", network], check=False)
        manifest["desktop_stopped_at"] = time.time()
        collector.save(args.out / "manifest.json", manifest)
    scores = None
    if not args.smoke:
        try:
            scores = collector.evaluate(target, args.pair, args.dataset, args.image)
        except Exception as error:
            manifest["evaluation_error"] = f"{type(error).__name__}: {error}"
    final_hashes = collector.hashes(target / "workspace")
    for result in results:
        result.update(output_hashes=final_hashes, frozen_at=manifest["desktop_stopped_at"],
            evaluation_scope="common final state after both agents stop")
        if scores:
            result.update(score=scores[result["task"][-1]]["score"], evaluation=scores)
        collector.save(args.out / result["task"] / "result.json", result)
    manifest.update(status="finished", finished_at=time.time(), output_hashes=final_hashes)
    collector.save(args.out / "manifest.json", manifest)
    collector.save(args.out / "summary.json", results)
    metrics = report(args.out, manifest, results)
    passed = not metrics["integrity_errors"] and not manifest.get("evaluation_error") and all(
        result["status"] not in ("error", "infrastructure_error") for result in results)
    if args.smoke:
        passed = passed and all(result["actions"] > 0 and result["model_responses"] > 0 and result["status"] == "completed" for result in results)
        if args.interaction_mode == "hybrid":
            passed = passed and all(hybrid_smoke_passed(args.out / result["task"]) for result in results)
    collector.save(args.out / "validation.json", {"passed": passed, "integrity_errors": metrics["integrity_errors"],
        "interaction_mode": args.interaction_mode})
    print(json.dumps({"out": str(args.out), "passed": passed, "results": results}), flush=True)
    return int(not passed)


def hybrid_smoke_passed(root):
    path = root / "actions.jsonl"
    if not path.is_file():
        return False
    events = [json.loads(line) for line in path.read_text().splitlines()]
    observed = any(event["action"]["type"] == "screenshot" and event["status"] == "ok" for event in events)
    executed = any(event["action"]["type"] == "shell" and event["status"] == "ok"
        and not event.get("shell_result", {}).get("timed_out", True)
        and event.get("shell_result", {}).get("exit_code") == 0
        and event.get("shell_result", {}).get("stdout", "").splitlines() == ["paragui-hybrid-ok/workspace", "1000"]
        for event in events)
    return observed and executed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--harness", choices=["codex", "freehand"], required=True)
    parser.add_argument("--freehand-runtime", type=Path, required=True,
        help="Parent directory containing freehand/harness/calltrace.py (also needed for Codex tracing)")
    parser.add_argument("--codex-binary", type=Path)
    parser.add_argument("--codex-permissions", choices=PERMISSION_MODES, default="reviewed",
        help="Explicit permission policy for the isolated Codex harness container only")
    parser.add_argument("--interaction-mode", choices=INTERACTION_MODES, default="hybrid",
        help="GUI+CLI/code by default; gui-only is a separately labelled ablation")
    parser.add_argument("--image-history-limit", type=int, default=4,
        help="Recent tool images sent upstream; reference images and the latest tool output are preserved")
    parser.add_argument("--pair", choices=["p1", "p2", "p3"], default="p3")
    parser.add_argument("--mode", choices=["parallel", "sequential"], default="parallel")
    parser.add_argument("--image", default="paragui/professional-authoring:20261030")
    parser.add_argument("--max-actions", type=int, default=300)
    parser.add_argument("--max-turns", type=int, default=90)
    parser.add_argument("--timeout", type=int, default=1500)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.harness == "codex" and not args.codex_binary:
        parser.error("--codex-binary is required for Codex")
    if args.harness != "codex" and args.codex_permissions != "reviewed":
        parser.error("--codex-permissions only applies to the Codex harness")
    if min(args.max_actions, args.max_turns, args.timeout) <= 0:
        parser.error("Budgets must be positive")
    if not 1 <= args.image_history_limit <= 50:
        parser.error("--image-history-limit must be between 1 and this provider's 50-image request budget")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
