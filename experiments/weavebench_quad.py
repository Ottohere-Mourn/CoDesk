"""One fixed four-task WeaveBench workload, run at concurrency 1, 2 or 4."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import time

from experiments import professional_native as native
from experiments import professional_shared as shared
from experiments import professional_trajectories as collector
from experiments.weavebench_pairs import PAIRS


PAIR = "wvquad"
BINDINGS = {
    "a": {"task_id": PAIRS["wvink"]["tasks"][0], "origin_pair": "wvink", "origin_role": "a"},
    "b": {"task_id": PAIRS["wvink"]["tasks"][1], "origin_pair": "wvink", "origin_role": "b"},
    "c": {"task_id": PAIRS["wvwriter"]["tasks"][0], "origin_pair": "wvwriter", "origin_role": "a"},
    "d": {"task_id": PAIRS["wvwriter"]["tasks"][1], "origin_pair": "wvwriter", "origin_role": "b"},
}
ORIGINAL_REPORT = native.report


def prepare_dataset(frozen_pairs, destination):
    destination.mkdir(parents=True, exist_ok=False)
    pair_dir = destination / "dataset/pairs" / PAIR
    inputs = pair_dir / "inputs"
    inputs.mkdir(parents=True)
    adaptations = []
    for pair in ("wvink", "wvwriter"):
        source = frozen_pairs / "dataset/pairs" / pair / "inputs"
        if any((source / "results").iterdir()):
            raise ValueError("Expected pristine frozen inputs, not an earlier attempt's outputs")
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("Unexpected input symlink")
            relative = path.relative_to(source)
            if str(relative) == "README.md":
                relative = Path("task_readmes") / pair / "README.md"
                adaptations.append({"origin_pair": pair, "from": "README.md", "to": str(relative),
                    "reason": "Two different input README.md files; primary assets/prompts unchanged"})
            target = inputs / relative
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                if target.exists():
                    raise ValueError("Input filename collision: " + str(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    (inputs / "README.md").write_text("# Shared workstation inputs\n\n"
        "Original task readmes are under task_readmes/wvink/README.md and task_readmes/wvwriter/README.md.\n"
        "The raster logo, brand palette and svg/ files belong to Inkscape tasks.\n"
        "contract_project/contract_v3.docx and report.odt belong to Writer tasks.\n"
        "Follow only your assigned task. Preserve unowned documents and deliverables in the shared results/ directory.\n")
    for role, binding in BINDINGS.items():
        original = frozen_pairs / "dataset/pairs" / binding['origin_pair'] / ("task_" + binding['origin_role'] + ".md")
        shutil.copy2(original, pair_dir / ("task_" + role + ".md"))
    shutil.copytree(frozen_pairs / "private", destination / "private")
    collector.save(destination / "provenance.json", {"source": str(frozen_pairs),
        "source_provenance": json.loads((frozen_pairs / "provenance.json").read_text()),
        "task_bindings": BINDINGS, "prompt_adaptations": [], "input_readme_adaptations": adaptations,
        "inputs": collector.hashes(inputs),
        "prompts": {role: hashlib.sha256((pair_dir / ("task_" + role + ".md")).read_bytes()).hexdigest()
            for role in BINDINGS},
        "judge_policy": "agent-visible-hybrid-v2", "leaderboard_comparable": False})


def wave_roles(width):
    if width not in (1, 2, 4):
        raise ValueError("Concurrency must be 1, 2 or 4")
    return ["abcd"[offset:offset + width] for offset in range(0, 4, width)]


def rules(width):
    return f"""You work on one task on a shared Linux desktop containing Inkscape and LibreOffice Writer.
There are four separate official tasks/documents in this workload. At most {width}
task agents are active at once. Each receives only its own task, in a private harness
context. Other tasks may run concurrently or in later waves. Preserve their files.
All agents share ONE desktop, DISPLAY, application profiles, clipboard, keyboard,
mouse and filesystem. There is NO cross-agent input lock or communication tool.
Do not create a private desktop/display server or a separate GUI application profile.
Normal document windows in the shared application session and headless helpers are allowed.
Change only your assigned task's inputs/outputs. Do not clear the shared results/
directory, kill an application, or close another task's document.
/tmp_workspace aliases /workspace. Original task paths work unchanged. The two
original top-level README.md files are preserved under /workspace/task_readmes/.
The target files are only in the desktop container, not your harness /session.
For every target GUI or CLI operation, use the desktop tool/bridge. For example:
{{"actions":[{{"type":"shell","command":"pwd","timeout":30}}]}}
Commands run as the desktop user in /workspace with the shared DISPLAY and DBus
session, return stdout/stderr and a screenshot, and stop their process-group children
on return. Do not background commands. This is hybrid GUI+CLI: programming,
application APIs, XML and shell utilities are allowed unless your task explicitly
forbids them. Real UI evidence must come from this shared desktop; never fabricate it.
Tool screenshots use 1280x800 coordinates; the real display is 1600x1000. Use scrot
for unmodified full-resolution deliverable screenshots. Avoid stale coordinates;
the screen may change between observation and action.
Graders, reference answers, harness infrastructure and host credentials are not
available and must not be sought. Save actual work and honestly report partial results.
"""


class QuadDesktop(collector.Desktop):
    def raw(self, argv, **kwargs):
        return collector.command(["docker", "exec", "--user", "1000:1000", "-e", "DISPLAY=:99",
            "-e", "HOME=/home/gui", "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui",
            "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus", self.name, *argv], **kwargs)

    def start(self):
        collector.command(["docker", "run", "-d", "--name", self.name, "--network", "none", "--cpus", "4",
            "--memory", "8g", "--shm-size", "1g", "--pids-limit", "512", "--security-opt", "no-new-privileges",
            "--label", "paragui.kind=weavebench-four-task", "-v", str(self.root / "workspace") + ":/workspace",
            self.image, "sleep", "infinity"], timeout=90)
        self.created = True
        collector.command(["docker", "exec", self.name, "bash", "-c",
            "useradd -m -u 1000 -s /bin/bash gui; mkdir /tmp/runtime-gui; "
            "chown 1000:1000 /tmp/runtime-gui; chmod 700 /tmp/runtime-gui; "
            "ln -s /workspace /tmp_workspace; chown -R 1000:1000 /workspace"])
        script = """import subprocess,time
subprocess.Popen(['openbox'],stdout=open('/tmp/openbox.log','w'),stderr=subprocess.STDOUT)
time.sleep(1)
subprocess.Popen(['inkscape','--with-gui','/tmp_workspace/svg/brand_traced.svg'],stdout=open('/tmp/inkscape.log','w'),stderr=subprocess.STDOUT)
writer=subprocess.Popen(['libreoffice','--writer','--norestore','--nologo','--nofirststartwizard','/tmp_workspace/contract_project/contract_v3.docx','/tmp_workspace/report.odt'],stdout=open('/tmp/writer.log','w'),stderr=subprocess.STDOUT)
writer.wait()
"""
        collector.command(["docker", "exec", "-d", "--user", "1000:1000", "-e", "HOME=/home/gui",
            "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui", "-e", "SAL_USE_VCLPLUGIN=gtk3",
            "-e", "DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus", self.name, "bash", "-c",
            "Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 2; "
            "export DISPLAY=:99; dbus-daemon --session --fork --address=unix:path=/tmp/runtime-gui/bus; "
            "exec python3 -c " + shlex.quote(script)])
        documents = ["brand_traced.svg", "contract_v3.docx", "report.odt"]
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            windows = self.raw(["wmctrl", "-lp"], check=False).stdout.decode(errors="replace")
            if all(document in windows for document in documents):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Both applications and all starting documents must open: " + windows)
        for document in documents:
            self.raw(["wmctrl", "-r", document, "-b", "add,maximized_vert,maximized_horz"], check=False)
        self.raw(["wmctrl", "-a", "brand_traced.svg"], check=False)
        time.sleep(1)
        collector.save(self.root / "startup.json", {"windows": windows, "opened": documents,
            "initial_application_instances": 2, "desktop_count": 1,
            "processes": self.raw(["ps", "-eo", "pid,ppid,args"]).stdout.decode(errors="replace"),
            "dbus_session_address": "unix:path=/tmp/runtime-gui/bus", "timestamp": time.time()})
        self.screenshot(self.root / "initial.png")

    def stop(self):
        if self.created:
            try:
                self.screenshot(self.root / "final.png")
                self.raw(["bash", "-c", "cat /tmp/inkscape.log /tmp/writer.log > /tmp/app.log"], check=False)
            except Exception:
                pass
        super().stop()


def activity_levels(intervals):
    events = []
    for actor, start, end in intervals:
        if end > start:
            events.extend([(start, actor, 1), (end, actor, -1)])
    active = collections.Counter()
    seconds = collections.Counter()
    previous = None
    peak = 0
    for timestamp, actor, change in sorted(events):
        count = sum(value > 0 for value in active.values())
        if previous is not None:
            seconds[count] += timestamp - previous
        active[actor] += change
        peak = max(peak, sum(value > 0 for value in active.values()))
        previous = timestamp
    return {"peak_distinct_agents": peak, "seconds_at_exactly_n_agents": dict(seconds)}


def report(root, manifest, results):
    metrics = ORIGINAL_REPORT(root, manifest, results)
    lifetime = activity_levels([(result['task'], result['agent_started_at'], result['finished_at'])
        for result in results if 'agent_started_at' in result])
    requests = []
    for result in results:
        path = root / result['task'] / 'requests.jsonl'
        if path.exists():
            requests.extend((result['task'], row['started_at'], row['started_at'] + row['latency_s'])
                for row in (json.loads(line) for line in path.read_text().splitlines()))
    metrics.update(agent_activity_levels=lifetime, http_activity_levels=activity_levels(requests))
    collector.save(root / "concurrency.json", metrics)
    manifest.update(task_bindings=BINDINGS, original_prompt_unchanged=not manifest['smoke'],
        initial_application_instances=2, initial_document_windows=3, shared_gui_profiles=True,
        judge_policy="agent-visible-hybrid-v2", leaderboard_comparable=False,
        actual_peak_active_agents=lifetime['peak_distinct_agents'])
    source = Path(__file__)
    shutil.copy2(source, root / source.name)
    manifest['source_hashes'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    collector.save(root / "manifest.json", manifest)
    lines = ["# Four-task shared desktop workload", "",
        f"Harness: {manifest['harness']}; concurrency: {manifest['max_concurrent_agents']}; waves: {manifest['task_waves']}",
        "One desktop, two applications, four unchanged official task prompts and separate documents.",
        "Model gpt-6-astra/high; hybrid GUI+CLI; no cross-agent input lock or automatic refocusing.",
        "Original native permission/harness/image-history policies and per-agent budgets retained.",
        "Judge v2 uses only requirements actually shown to agents; no hidden UNO/XML prohibition. Not leaderboard-comparable.",
        "Quality scores remain pending until separate post-batch judging; completion is not success.", "",
        "| Role | Official task | Stop | Responses | Desktop actions |", "|---|---|---|---:|---:|"]
    for result in results:
        lines.append(f"| {result['task'][-1]} | {BINDINGS[result['task'][-1]]['task_id']} | {result['status']} | {result['model_responses']} | {result['actions']} |")
    lines.append("\nObserved peak distinct active agents: " + str(lifetime['peak_distinct_agents']))
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "credentials", "out", "freehand-runtime", "codex-binary"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--harness", choices=("codex", "freehand"), required=True)
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 4), required=True)
    parser.add_argument("--image", default="paragui/weavebench-pairs:20261103")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(args.credentials.read_text())
    if config['model'] != 'gpt-6-astra' or config.get('reasoning_effort', 'high') != 'high':
        raise ValueError("Model/effort mismatch")
    args.pair, args.task_roles, args.task_waves = PAIR, "abcd", wave_roles(args.concurrency)
    args.mode = "sequential" if args.concurrency == 1 else "parallel"
    args.coagent_hint = args.concurrency > 1
    args.interaction_mode, args.image_history_limit = "hybrid", 4
    args.codex_permissions = "container-unrestricted" if args.harness == "codex" else "reviewed"
    args.max_actions, args.max_turns, args.timeout = (10, 12, 360) if args.smoke else (300, 90, 1500)
    native.interaction_rules = lambda mode: rules(args.concurrency) if mode == "hybrid" else None
    native.report = report
    collector.Desktop = QuadDesktop
    collector.evaluate = lambda *unused: {role: {"score": None, "status": "judge_pending"} for role in BINDINGS}
    collector.APPS[PAIR] = ("Inkscape + LibreOffice Writer", "", "")
    return native.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
