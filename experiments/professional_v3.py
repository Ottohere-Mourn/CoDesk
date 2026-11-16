"""p10-only native adapter; retains separate legacy p1-p3 task definitions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading
import time

from experiments import professional_native as native
from experiments import professional_shared as shared
from experiments import professional_trajectories as collector


SOURCE = Path(__file__).resolve().parents[1] / "tasks/professional_v3"
ORIGINAL_REPORT = native.report
ORIGINAL_DESKTOP = collector.Desktop
ORIGINAL_AGENT_DESKTOP = shared.AgentDesktop


class P10Desktop(ORIGINAL_DESKTOP):
    def __init__(self, root, pair, image):
        super().__init__(root, pair, image)
        self.record_lock = threading.Lock()

    def start(self):
        collector.command(["docker", "run", "-d", "--name", self.name, "--network", "none", "--cpus", "4",
            "--memory", "8g", "--shm-size", "1g", "--security-opt", "no-new-privileges",
            "--label", "paragui.kind=p10-calibration", "-v", str(self.root / "workspace") + ":/workspace",
            "-v", str(SOURCE / "p10_observer.py") + ":/opt/p10_observer.py:ro", self.image, "sleep", "infinity"], timeout=90)
        self.created = True
        collector.command(["docker", "exec", self.name, "bash", "-c",
            "useradd -m -u 1000 -s /bin/bash gui; mkdir /tmp/runtime-gui; chown 1000:1000 /tmp/runtime-gui; chmod 700 /tmp/runtime-gui; chown -R 1000:1000 /workspace"])
        collector.command(["docker", "exec", "-d", "--user", "1000:1000", "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
            self.name, "bash", "-c", "Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp > /tmp/xvfb.log 2>&1 & sleep 1; DISPLAY=:99 openbox >/tmp/openbox.log 2>&1 & wait"])
        time.sleep(3)
        self.raw(["python3", "-c", "import subprocess; stream=open('/tmp/app.log','w'); subprocess.Popen(['qgis','--nologo','--code','/opt/p10_observer.py','/workspace/RivertonReview.qgz'],stdout=stream,stderr=stream,start_new_session=True)"])
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            try:
                state = self.state()
                if state.get("project", "").endswith("RivertonReview.qgz") and "error" not in state:
                    window = self.raw(["xdotool", "search", "--onlyvisible", "--name", "RivertonReview"], check=False).stdout.decode().split()
                    if window:
                        self.raw(["xdotool", "windowactivate", "--sync", window[-1]], check=False)
                        self.raw(["xdotool", "key", "alt+F10"], check=False)
                        time.sleep(1)
                        return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError("QGIS observer did not become ready: " + str(self.raw(["tail", "-n", "12", "/tmp/app.log"], check=False).stdout))

    def state(self):
        return json.loads(self.raw(["python3", "-c", "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18763',timeout=3).read().decode())"], timeout=10).stdout)

    def capture(self, path, task):
        started = time.time()
        try:
            state = self.state()
            window = self.raw(["xdotool", "getactivewindow"], check=False).stdout.decode().strip()
            properties = self.raw(["xprop", "-id", window, "_NET_WM_PID"], check=False).stdout.decode()
            process_id = re.search(r"=\s*(\d+)", properties)
            verified = bool(process_id and int(process_id.group(1)) == state.get("pid") and time.time() - state.get("timestamp", 0) < 2)
            record = {"task": task, "timestamp": time.time(), "started_at": started, "state": state,
                "qgis_window_verified": verified, "window_id": window,
                "screenshot": str(Path(path).relative_to(self.root.parent)),
                "screenshot_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        except Exception as error:
            record = {"task": task, "timestamp": time.time(), "error": str(error), "qgis_window_verified": False}
        with self.record_lock:
            collector.append(self.root.parent / "native-observations.jsonl", record)


class P10AgentDesktop(ORIGINAL_AGENT_DESKTOP):
    def screenshot(self, path):
        super().screenshot(path)
        self.desktop.capture(path, self.task)


def evaluate(root, pair, dataset, image):
    inspection = root / "evaluation"
    inspection.mkdir()
    shutil.copytree(root / "workspace", inspection / "workspace")
    observations = root.parent / "native-observations.jsonl"
    if observations.exists():
        shutil.copy2(observations, inspection / "native-observations.jsonl")
    else:
        (inspection / "native-observations.jsonl").touch()
    command = ["docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "4g",
        "-v", str(SOURCE.parent.parent) + ":/code:ro", "-v", str(dataset / "private") + ":/trusted:ro",
        "-v", str(inspection) + ":/evaluation", "-e", "PYTHONPATH=/code", "-e", "PYTHONDONTWRITEBYTECODE=1",
        image, "python3", "-m", "tasks.professional_v3.p10_native", "grade", "--workspace", "/evaluation/workspace",
        "--trusted", "/trusted", "--observations", "/evaluation/native-observations.jsonl", "--out", "/evaluation/inspection"]
    result = collector.command(command, timeout=240)
    (inspection / "stderr.log").write_bytes(result.stderr)
    scores = json.loads(result.stdout)
    collector.save(inspection / "scores.json", scores)
    return scores


def report(root, manifest, results):
    metrics = ORIGINAL_REPORT(root, manifest, results)
    lines = ["# p10 native hybrid calibration", "", f"Harness: {manifest['harness']}; roles: {manifest['tasks']}; mode: {manifest['mode']}",
        "", "One shared desktop and native project; independent native/file grading after all selected agents stop.",
        "Observer outputs are host-recorded, not agent reports; in-process introspection is not hardened against a malicious QGIS process.",
        "", "| Task | Stop | Progress | Full success |", "|---|---|---:|---|"]
    for result in results:
        evaluation = result.get("evaluation", {}).get(result["task"][-1], {})
        lines.append(f"| {result['task']} | {result['status']} | {result.get('score')} | {evaluation.get('success')} |")
    lines.extend(["", "This is calibration, not a claim of validated hard-task difficulty or a success-rate estimate.",
                  "Scored preservation is zero: immutable input/native integrity is a separate gate."])
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "credentials", "out", "freehand-runtime", "codex-binary"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--harness", choices=("codex", "freehand"), required=True)
    parser.add_argument("--condition", choices=("solo_a", "solo_b", "sequential_ab", "sequential_ba", "parallel_shared"), required=True)
    parser.add_argument("--image", default="paragui/professional-rootless:20261103")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    args.pair = "p10"
    args.task_roles = {"solo_a": "a", "solo_b": "b", "sequential_ab": "ab", "sequential_ba": "ba", "parallel_shared": "ab"}[args.condition]
    args.coagent_hint = args.condition == "parallel_shared"
    args.mode = "parallel" if args.condition == "parallel_shared" else "sequential"
    args.interaction_mode, args.image_history_limit = "hybrid", 4
    args.codex_permissions = "container-unrestricted" if args.harness == "codex" else "reviewed"
    args.max_actions, args.max_turns, args.timeout = (10, 12, 360) if args.smoke else (300, 90, 1500)
    collector.APPS["p10"] = ("QGIS", "RivertonReview.qgz", "qgis")
    collector.Desktop, shared.AgentDesktop = P10Desktop, P10AgentDesktop
    collector.evaluate, native.report = evaluate, report
    return native.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
