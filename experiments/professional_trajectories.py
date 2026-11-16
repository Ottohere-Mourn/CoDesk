"""Collect real screenshot/action trajectories against the professional pilot inputs.

The model receives one task and desktop tools. Each solo trial has a fresh Docker
desktop with only its input directory mounted. Credentials, graders and reference
solutions remain on the host. This is a Responses tool loop, not the Codex CLI.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

import requests

WIDTH, HEIGHT = 1280, 800
APPS = {
    "p1": ("Blender", "AsterLamp.blend", "blender"),
    "p2": ("FreeCAD", "SurveyFixture.FCStd", "freecad"),
    "p3": ("QGIS", "HarborDrainage.qgz", "qgis"),
}
TOOLS = [{
    "type": "function", "name": "desktop", "strict": False,
    "description": "Perform up to 12 ordered desktop actions, then see a fresh screenshot. "
                   "Each primitive is also recorded with its own screenshot. Only use coordinates you observed. "
                   "Action types: click (x,y,button=left|middle|right,clicks=1|2,modifiers=[ctrl,shift,alt]), move (x,y), "
                   "drag (x,y,x2,y2), key (keys, X11 notation e.g. ctrl+s, Return, Tab, Escape, KP_0), "
                   "type (text, literal typing), scroll (x,y,direction=up|down,amount), "
                   "wait (seconds<=10), screenshot. Multiple key chords can be separated by spaces.",
    "parameters": {"type": "object", "properties": {"actions": {"type": "array", "maxItems": 12,
        "items": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["click", "move", "drag", "key", "type", "scroll", "wait", "screenshot"]},
            "x": {"type": "number"}, "y": {"type": "number"},
            "x2": {"type": "number"}, "y2": {"type": "number"},
            "button": {"type": "string"}, "clicks": {"type": "integer"},
            "modifiers": {"type": "array", "items": {"type": "string", "enum": ["ctrl", "shift", "alt"]}},
            "keys": {"type": "string"}, "text": {"type": "string"},
            "direction": {"type": "string"}, "amount": {"type": "integer"},
            "seconds": {"type": "number"}}, "required": ["type"]}}}, "required": ["actions"]},
}, {
    "type": "function", "name": "finish", "strict": True,
    "description": "Stop the trial. Report what you actually saved and any unfinished requirements. Completion is graded separately.",
    "parameters": {"type": "object", "properties": {"summary": {"type": "string"},
        "complete": {"type": "boolean"}}, "required": ["summary", "complete"], "additionalProperties": False},
}]


def save(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def append(path, data):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(data, ensure_ascii=False) + "\n")


def command(argv, *, timeout=40, check=True, **kwargs):
    return subprocess.run(argv, capture_output=True, timeout=timeout, check=check, **kwargs)


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def action_commands(action):
    """Return argument vectors, never a model-authored shell command."""
    kind = action["type"]
    def xy(suffix=""):
        x, y = float(action["x" + suffix]), float(action["y" + suffix])
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise ValueError("Coordinates outside the screenshot")
        return [str(round(x * 1.25)), str(round(y * 1.25))]
    move = lambda: ["xdotool", "mousemove", "--sync", *xy()]
    if kind == "click":
        button = {"left": "1", "middle": "2", "right": "3"}[action.get("button", "left")]
        clicks = action.get("clicks", 1)
        if clicks not in (1, 2):
            raise ValueError("clicks must be 1 or 2")
        modifiers = action.get("modifiers", [])
        if not isinstance(modifiers, list) or any(k not in ("ctrl", "shift", "alt") for k in modifiers):
            raise ValueError("Unsupported mouse modifier")
        return ([move()] + ([["xdotool", "keydown", *modifiers]] if modifiers else [])
                + [["xdotool", "click", "--repeat", str(clicks), "--delay", "120", button]]
                + ([["xdotool", "keyup", *modifiers]] if modifiers else []))
    if kind == "move":
        return [move()]
    if kind == "drag":
        return [move(), ["xdotool", "mousedown", "1"],
                ["xdotool", "mousemove", "--sync", *xy("2")], ["xdotool", "mouseup", "1"]]
    if kind == "key":
        keys = action["keys"].split()
        if not keys or any(not re.fullmatch(r"[A-Za-z0-9_+]+", k) or len(k) > 80 for k in keys):
            raise ValueError("Invalid X11 key chord")
        return [["xdotool", "key", "--clearmodifiers", *keys]]
    if kind == "type":
        text = action["text"]
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("Text exceeds 20000 characters")
        return [["xdotool", "type", "--clearmodifiers", "--delay", "1", "--", text]]
    if kind == "scroll":
        count = int(action.get("amount", 3))
        if not 1 <= count <= 20:
            raise ValueError("Scroll count outside 1..20")
        button = {"up": "4", "down": "5"}[action.get("direction", "down")]
        return [move(), ["xdotool", "click", "--repeat", str(count), "--delay", "80", button]]
    if kind in ("wait", "screenshot"):
        return []
    raise ValueError("Unknown action type")


def image_history(history, keep=3):
    """Keep tool call/result pairs intact while retaining only recent images."""
    result = copy.deepcopy(history)
    images = [part for item in result for part in item.get("content", [])
              if isinstance(part, dict) and part.get("type") == "input_image"]
    for part in images[:-keep] if keep else images:
        path = part.get("image_url", "")
        part.clear()
        part.update(type="input_text", text="[Earlier screenshot archived at " + path + "]")
    return result


def encode_images(history, root):
    history = copy.deepcopy(history)
    for item in history:
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "input_image":
                part["image_url"] = "data:image/png;base64," + base64.b64encode((root / part["image_url"]).read_bytes()).decode()
    return history


class Desktop:
    def __init__(self, root, pair, image):
        self.root, self.pair = root, pair
        self.name = "paragui-traj-" + pair + "-" + uuid.uuid4().hex[:10]
        self.image = image
        self.created = False

    def raw(self, argv, **kwargs):
        return command(["docker", "exec", "--user", "1000:1000", "-e", "DISPLAY=:99",
                        "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
                        self.name, *argv], **kwargs)

    def start(self):
        command(["docker", "run", "-d", "--name", self.name, "--network", "none",
                 "--cpus", "4", "--memory", "8g", "--shm-size", "1g",
                 "--security-opt", "no-new-privileges", "--label", "paragui.kind=professional-trajectory",
                 "-v", str(self.root / "workspace") + ":/workspace",
                 self.image, "sleep", "infinity"], timeout=90)
        self.created = True
        script = """import os,subprocess
subprocess.run(['useradd','-m','-u','1000','-s','/bin/bash','gui'],check=True)
os.makedirs('/tmp/runtime-gui'); os.chown('/tmp/runtime-gui',1000,1000); os.chmod('/tmp/runtime-gui',0o700)
for root,dirs,files in os.walk('/workspace'):
    for name in ['']+dirs+files: os.chown(os.path.join(root,name),1000,1000)
"""
        command(["docker", "exec", self.name, "python3", "-c", script])
        command(["docker", "exec", "-d", "--user", "1000:1000", "-e", "HOME=/home/gui",
                 "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui", self.name, "bash", "-c",
                 "Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp > /tmp/xvfb.log 2>&1 & "
                 "sleep 1; DISPLAY=:99 openbox > /tmp/openbox.log 2>&1 & wait"])
        time.sleep(3)
        app, native, binary = APPS[self.pair]
        if self.pair == "p2":
            config = '<FCParameters><FCParamGroup Name="Root"><FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences"><FCParamGroup Name="General"><FCText Name="AutoloadModule">PartWorkbench</FCText></FCParamGroup></FCParamGroup></FCParamGroup></FCParamGroup></FCParameters>'
            self.raw(["python3", "-c", "from pathlib import Path; import sys; Path('/home/gui/freecad.cfg').write_text(sys.argv[1])", config])
            argv = [binary, "-u", "/home/gui/freecad.cfg", "/workspace/" + native]
        elif self.pair == "p3":
            argv = [binary, "--nologo", "/workspace/" + native]
        else:
            argv = [binary, "-t", "4", "/workspace/" + native]
        # App startup changes only UI preferences, never the task's native data.
        self.raw(["python3", "-c", "import subprocess,sys; f=open('/tmp/app.log','w'); subprocess.Popen(sys.argv[1:],stdout=f,stderr=f,start_new_session=True)", *argv])
        time.sleep(12)
        probe = self.raw(["xdotool", "search", "--onlyvisible", "--name", app], check=False).stdout.decode().split()
        if not probe:
            raise RuntimeError("Application did not open a visible window: " + app)
        self.raw(["xdotool", "windowactivate", "--sync", probe[-1]], check=False)
        self.raw(["xdotool", "key", "alt+F10"], check=False)
        time.sleep(1)

    def focus(self):
        return self.raw(["xdotool", "getactivewindow", "getwindowname"], check=False).stdout.decode(errors="replace").strip()

    def screenshot(self, path):
        script = "import subprocess,sys; from PIL import Image; subprocess.run(['scrot','--overwrite','/tmp/trajectory.png'],check=True); Image.open('/tmp/trajectory.png').convert('RGB').resize((1280,800),Image.Resampling.LANCZOS).save(sys.stdout.buffer,format='PNG')"
        Path(path).write_bytes(self.raw(["python3", "-c", script]).stdout)

    def stop(self):
        if self.created:
            logs = self.raw(["cat", "/tmp/app.log"], check=False).stdout
            (self.root / "application.log").write_bytes(logs)
            command(["docker", "rm", "-f", self.name], timeout=30, check=False)


def call_model(config, payload, root, turn, deadline):
    """Retry inference transport only; never retry any desktop action."""
    save(root / "requests" / f"{turn:03d}.json", payload)
    body = dict(payload, input=encode_images(payload["input"], root))
    with requests.Session() as session:
        session.trust_env = False
        for attempt in range(1, 7):
            started = time.time()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Agent wall clock budget exhausted")
            event = {"turn": turn, "attempt": attempt, "started_at": started}
            retry_after = 5 * attempt
            try:
                response = session.post(config["base_url"].rstrip("/") + "/responses", json=body,
                    headers={"Authorization": "Bearer " + config["api_key"]}, timeout=(15, min(180, remaining)))
                event["http_status"] = response.status_code
                if response.status_code != 200:
                    try:
                        message = str(response.json().get("error", {}).get("message", ""))
                        event["error_message"] = message.replace(config["api_key"], "[redacted]")[:2000]
                    except (ValueError, AttributeError):
                        pass
                    if response.status_code == 429:
                        retry_after = max(30, min(60, 15 * attempt))
                    try:
                        retry_after = max(retry_after, min(60, float(response.headers.get("Retry-After", 0))))
                    except ValueError:
                        pass
                    raise RuntimeError("Model endpoint HTTP " + str(response.status_code))
                data = response.json()
                save(root / "responses" / f"{turn:03d}-attempt-{attempt}.json", data)
                if data.get("status") != "completed":
                    raise RuntimeError("Model response " + str(data.get("status")))
                event.update(ok=True, latency_s=round(time.time() - started, 3), usage=data.get("usage"))
                append(root / "requests.jsonl", event)
                save(root / "responses" / f"{turn:03d}.json", data)
                return data
            except (requests.RequestException, ValueError, RuntimeError) as error:
                event.update(ok=False, latency_s=round(time.time() - started, 3),
                             error_type=type(error).__name__, retry_after_s=retry_after)
                append(root / "requests.jsonl", event)
                if attempt == 6 or event.get("http_status", 500) in (400, 401, 403, 404):
                    raise RuntimeError("Inference failed; see requests.jsonl") from None
                time.sleep(min(retry_after, max(0, deadline - time.monotonic())))


def evaluate(root, pair, dataset, image):
    """Inspect a frozen copy in a different container after all agent actions stop."""
    inspection = root / "evaluation"
    inspection.mkdir()
    shutil.copytree(root / "workspace", inspection / "workspace")
    code = ("import sys,json; from pathlib import Path; sys.path.insert(0,'/dataset/src'); "
            "import pack; print(json.dumps(pack.scores(" + repr(pair) + ",Path('/evaluation/workspace'),"
            "Path('/evaluation/native.json')),indent=2))")
    result = command(["docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "8g",
        "-v", str(dataset) + ":/dataset:ro", "-v", str(inspection) + ":/evaluation",
        image, "python3", "-c", code], timeout=240)
    (inspection / "stderr.log").write_bytes(result.stderr)
    scores = json.loads(result.stdout)
    save(inspection / "scores.json", scores)
    return scores


def render_trial(root):
    events = [json.loads(line) for line in (root / "actions.jsonl").read_text().splitlines()] if (root / "actions.jsonl").exists() else []
    data = json.dumps(events, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><meta charset="utf-8"><title>paraGUI trajectory</title>
<style>body{font:16px system-ui;background:#15202b;color:#e8edf2;max-width:1320px;margin:24px auto}img{width:100%;border:1px solid #789}pre{white-space:pre-wrap}input{width:70%}button{padding:6px 18px}a{color:#8dd7ff}</style>
<h1>''' + html.escape(root.name) + '''</h1><a href="result.json">Result and evaluator scores</a>
<p><button id="prev">Previous</button> <input type="range" id="step" min="0"> <button id="next">Next</button> <span id="count"></span></p>
<pre id="caption"></pre><img id="screen"><script>const events=''' + data + ''';
const slider=document.getElementById('step');slider.max=events.length;
function show(){const n=+slider.value,e=events[n-1];document.getElementById('count').textContent=n+'/'+events.length;
document.getElementById('caption').textContent=e?JSON.stringify({action:e.action,status:e.status,window:e.window_before,elapsed_s:e.elapsed_s},null,2):'Initial desktop';
document.getElementById('screen').src=e?e.screenshot_after:'screenshots/0000.png';}
slider.oninput=show;document.getElementById('prev').onclick=()=>{slider.value=Math.max(0,+slider.value-1);show()};
document.getElementById('next').onclick=()=>{slider.value=Math.min(events.length,+slider.value+1);show()};show();</script>'''
    (root / "trajectory.html").write_text(page)


def trial(args, task, config, *, desktop=None, barrier=None, observe=None):
    pair, side = task[:2], task[2:]
    if pair not in APPS or side not in ("a", "b"):
        raise ValueError("Invalid task " + task)
    root = args.out / task
    root.mkdir()
    for name in ("screenshots", "requests", "responses"):
        (root / name).mkdir()
    source = args.dataset / "dataset/pairs" / pair
    shutil.copytree(source / "inputs", root / "workspace")
    instruction = (source / f"task_{side}.md").read_text()
    (root / "instruction.txt").write_text(instruction)
    rule = ("Use only normal GUI controls, keyboard shortcuts, and application expression fields. "
            "Do not open a terminal, shell, Python/JavaScript console, macro editor, or execute scripts. "
            "QGIS field calculator and FreeCAD parameter expressions are allowed." if args.access == "gui"
            else "You may use the application's own Python console through the visible GUI. "
                 "No terminal, external shell or access outside /workspace. Keep evidence of the visible result.")
    shared = desktop is not None
    emit = observe or (lambda kind, event: None)
    system = ("You are operating a real Linux desktop to carry out one professional software task. "
        f"The screenshot is {WIDTH}x{HEIGHT}; coordinates use these pixels. The application is already open. "
        "Your input files and output destination are /workspace. Only your task's input files are available. "
        + rule + " Follow the task, save the editable project and requested exports, and verify via the visible UI. "
        "Do not invent success. Use finish to report partial work if blocked. Every action costs budget; "
        "batch predictable entry/shortcuts but inspect after navigation. Take care with focus and modal dialogs. "
        "The desktop has no network. You cannot access any grader or reference solution.")
    if shared:
        system += (" Another independent agent is assigned work in the SAME application and /workspace. "
                   "You only receive your own task. The screen and shared project may change between observations. "
                   "Preserve others' work and re-observe when necessary. There is no direct communication tool.")
    result = {"schema_version": 1, "task": task, "mode": args.mode if shared else "solo", "software": APPS[pair][0],
        "harness": "Responses desktop tool loop", "access": args.access,
        "access_enforcement": "desktop-only tool surface; console restriction is a prompt rule",
        "model": config["model"], "reasoning_effort": config.get("reasoning_effort", "high"),
        "codex_cli": False, "yolo_enabled": False, "image": args.image,
        "max_actions": args.max_actions, "max_turns": args.max_turns, "timeout_s": args.timeout,
        "input_hashes": hashes(root / "workspace"), "status": "starting", "actions": 0,
        "model_responses": 0, "usage": {}, "started_at": time.time()}
    save(root / "result.json", result)
    save(root / "prompt.json", {"instructions": system, "task": instruction, "tools": TOOLS})
    desktop = desktop if shared else Desktop(root, pair, args.image)
    started = time.monotonic()
    try:
        if not shared:
            desktop.start()
        result["container"] = desktop.name
        if barrier is not None:
            barrier.wait(timeout=120)
        result["agent_started_at"] = time.time()
        deadline = time.monotonic() + args.timeout
        desktop.screenshot(root / "screenshots/0000.png")
        history = [{"role": "user", "content": [{"type": "input_text", "text": instruction},
                   {"type": "input_image", "image_url": "screenshots/0000.png", "detail": "original"}]}]
        result["status"] = "running"
        save(root / "result.json", result)
        finished = False
        for turn in range(1, args.max_turns + 1):
            if time.monotonic() >= deadline:
                result["status"] = "timeout"
                break
            payload = {"model": config["model"], "instructions": system, "input": image_history(history),
                "tools": TOOLS, "parallel_tool_calls": False, "store": False,
                "reasoning": {"effort": config.get("reasoning_effort", "high")},
                "include": ["reasoning.encrypted_content"], "max_output_tokens": 8192}
            emit("model_request", {"turn": turn})
            response = call_model(config, payload, root, turn, deadline)
            emit("model_response", {"turn": turn})
            result["model_responses"] += 1
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                result["usage"][key] = result["usage"].get(key, 0) + (response.get("usage") or {}).get(key, 0)
            output = response.get("output", [])
            history.extend(output)
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                message = "\n".join(part.get("text", "") for item in output for part in item.get("content", []) if part.get("type") == "output_text")
                result.update(status="completed", agent_summary=message, agent_claimed_complete=None)
                break
            for call in calls:
                try:
                    arguments = json.loads(call["arguments"])
                    if call["name"] == "finish":
                        result.update(status="completed", agent_summary=arguments["summary"], agent_claimed_complete=arguments["complete"])
                        finished = True
                        break
                    if call["name"] != "desktop":
                        raise ValueError("Unknown tool")
                    actions = arguments["actions"]
                    if not isinstance(actions, list) or not 1 <= len(actions) <= 12:
                        raise ValueError("Provide 1..12 actions")
                    # Validate the complete batch before making any changes.
                    prepared = [(action, action_commands(action)) for action in actions]
                    feedback = []
                    for action, commands in prepared:
                        if time.monotonic() >= deadline or result["actions"] >= args.max_actions:
                            result["status"] = "timeout" if time.monotonic() >= deadline else "max_actions"
                            finished = True
                            break
                        n = result["actions"] + 1
                        event = {"step": n, "turn": turn, "call_id": call["call_id"], "action": action,
                            "started_at": time.time(), "elapsed_s": round(time.monotonic() - started, 3),
                            "window_before": desktop.focus(), "screenshot_before": f"screenshots/{n-1:04d}.png",
                            "screenshot_after": f"screenshots/{n:04d}.png", "status": "ok"}
                        emit("action_start", event)
                        try:
                            for argv in commands:
                                desktop.raw(argv)
                        except Exception as error:
                            event.update(status="error", error_type=type(error).__name__)
                            desktop.raw(["xdotool", "keyup", "ctrl", "shift", "alt"], check=False)
                        finally:
                            emit("input_end", event)
                        time.sleep(min(10, max(0, float(action.get("seconds", 0.35)))) if action["type"] == "wait" else .35)
                        event["window_after"] = desktop.focus()
                        desktop.screenshot(root / event["screenshot_after"])
                        event["duration_s"] = round(time.time() - event["started_at"], 3)
                        emit("action_end", event)
                        append(root / "actions.jsonl", event)
                        result["actions"] = n
                        feedback.append({"step": n, "action": action, "status": event["status"]})
                        save(root / "result.json", result)
                        if event["status"] != "ok":
                            break  # An uncertain action is never replayed automatically.
                    history.append({"type": "function_call_output", "call_id": call["call_id"],
                        "output": json.dumps({"actions": feedback, "actions_remaining": args.max_actions-result["actions"],
                            "seconds_remaining": max(0, round(deadline-time.monotonic()))})})
                    history.append({"role": "user", "content": [{"type": "input_text", "text": "Desktop after the tool call:"},
                        {"type": "input_image", "image_url": f"screenshots/{result['actions']:04d}.png", "detail": "original"}]})
                except (ValueError, KeyError, TypeError) as error:
                    history.append({"type": "function_call_output", "call_id": call["call_id"], "output": "Invalid arguments: " + str(error)})
            save(root / "result.json", result)
            if finished:
                break
        else:
            result["status"] = "max_turns"
    except Exception as error:
        result.update(status="timeout" if isinstance(error, TimeoutError) else "error", error_type=type(error).__name__,
                      error="See application.log and requests.jsonl; infrastructure error retained")
    finally:
        result.update(finished_at=time.time(), wall_s=round(time.monotonic()-started, 3))
        emit("agent_stopped", {"status": result["status"], "actions": result["actions"]})
        if shared:
            result["pending_shared_evaluation"] = True
        else:
            try:
                desktop.stop()
            except Exception as error:
                result["cleanup_error"] = type(error).__name__
            result["output_hashes"] = hashes(root / "workspace")
            try:
                result["evaluation"] = evaluate(root, pair, args.dataset, args.image)
                result["score"] = result["evaluation"][side]["score"]
            except Exception as error:
                result["evaluation_error"] = type(error).__name__
        save(root / "result.json", result)
        render_trial(root)
    print(json.dumps({key: result.get(key) for key in ("task", "status", "actions", "model_responses", "score", "wall_s")}), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tasks", nargs="+", default=["p1a", "p2a", "p3a"])
    parser.add_argument("--image", default="paragui/professional-authoring:20261030")
    parser.add_argument("--access", choices=["gui", "app-console"], default="gui")
    parser.add_argument("--max-actions", type=int, default=180)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    args.dataset, args.out = args.dataset.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.credentials.read_text())
    shutil.copy2(__file__, args.out / "collector.py")
    save(args.out / "manifest.json", {"tasks": args.tasks, "model": config["model"], "access": args.access,
        "dataset": str(args.dataset), "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": command(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).stdout.strip(),
        "started_at": time.time(), "mode": "solo", "reference_exposed": False, "yolo_enabled": False})
    results = []
    for task in args.tasks:
        results.append(trial(args, task, config))
        save(args.out / "summary.json", results)
    return int(any(r["status"] == "error" or r.get("evaluation_error") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
