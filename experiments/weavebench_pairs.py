"""Pinned official WeaveBench inputs on a shared, hybrid desktop."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import time

from experiments import professional_native as native
from experiments import professional_shared as shared
from experiments import professional_trajectories as collector


PAIRS = {
    "wvink": {"app": "Inkscape", "tasks": ["DES_task_0_inkscape_vectorize_logo",
        "DES_task_11_inkscape_svgo_node_diet"],
        "documents": ["logo_raster.png", "svg/brand_traced.svg"]},
    "wvwriter": {"app": "LibreOffice Writer", "tasks": ["DOC_task_10_lo_writer_trackchanges_audit",
        "DOC_task_2_heading_style_normalize"],
        "documents": ["contract_project/contract_v3.docx", "report.odt"]},
}
UPSTREAM_COMMIT = "acf203ae24386aa9bcc0da950c533c8c796dc38e"
DATASET_COMMIT = "ec498fc530b685d2fea5823a64a0f7538c8bbf6a"
ORIGINAL_REPORT = native.report
ORIGINAL_DESKTOP = collector.Desktop


def section(text, name):
    matched = re.search(r"^## " + re.escape(name) + r"\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not matched:
        raise ValueError("Missing task section: " + name)
    return matched.group(1).strip()


def merge_inputs(source, destination):
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Unexpected input symlink: " + str(path))
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            if target.exists():
                raise ValueError("Official input filename collision: " + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def prepare_dataset(source, destination, upstream):
    destination.mkdir(parents=True, exist_ok=False)
    private = destination / "private"
    private.mkdir()
    manifest = {"upstream_commit": UPSTREAM_COMMIT, "dataset_commit": DATASET_COMMIT,
        "pairs": PAIRS, "prompt_adaptations": [], "workspace_alias": "/tmp_workspace -> /workspace",
        "output_collisions": [], "original_asset_hashes": {}, "original_prompt_hashes": {}}
    for pair, spec in PAIRS.items():
        target = destination / "dataset/pairs" / pair
        inputs = target / "inputs"
        inputs.mkdir(parents=True)
        for role, task_id in zip("ab", spec["tasks"]):
            category, short = task_id.split("_", 1)
            original = source / "tasks" / category / (task_id + ".md")
            task_private = private / task_id
            task_private.mkdir()
            shutil.copy2(original, task_private / "original.md")
            prompt = section(original.read_text(), "Prompt")
            (target / ("task_" + role + ".md")).write_text(prompt)
            manifest["original_prompt_hashes"][task_id] = hashlib.sha256(prompt.encode()).hexdigest()
            assets = source / "tasks/workspace" / category / short
            merge_inputs(assets / "exec", inputs)
            manifest["original_asset_hashes"][task_id] = collector.hashes(assets / "exec")
            if (assets / "gt").exists():
                shutil.copytree(assets / "gt", task_private / "gt")
            (task_private / "warmup.txt").write_text(section(original.read_text(), "Warmup"))
        (inputs / "results").mkdir()
    warmup = (private / PAIRS["wvink"]["tasks"][1] / "warmup.txt").read_text()
    fixture = re.search(r"python3 - <<'PY'\n(.*?)\nPY", warmup, re.S)
    if not fixture:
        raise ValueError("Official SVG warmup fixture not found")
    (private / "official_svg_fixture.py").write_text(fixture.group(1) + "\n")
    shutil.copy2(upstream / "weavebench/eval/agent_judge/prompt_template.txt", private / "judge_prompt.txt")
    for name in ("LICENSE", "NOTICE"):
        shutil.copy2(upstream / name, private / name)
    collector.save(destination / "provenance.json", manifest)


def pair_rules(interaction_mode):
    if interaction_mode != "hybrid":
        raise ValueError("This experiment is hybrid only")
    return """You operate a real application on a shared Linux desktop.
Another independent agent works in the SAME application
and /workspace. You have only your own official task. Preserve other work.
The two tasks have separate official documents, not one merged document.
Both documents, application profile, clipboard, dialogs, focus, keyboard and mouse
share ONE desktop session. There is no communication tool or cross-agent input lock.
Do not start a private desktop, display server, or separate GUI application profile.
Additional GUI documents/windows within the shared application session are allowed.
Both agents share the live project and filesystem.
Only your own task's files and deliverables should be changed; do not delete the
shared results directory, close the other task's document, or kill the application.
/tmp_workspace is an alias for /workspace. All original task paths work unchanged.
The target files exist ONLY in the desktop container. Your native shell runs in
the isolated harness /session, not the desktop. Use the desktop tool/bridge for
every target operation, including CLI. Example target command:
{"actions":[{"type":"shell","command":"pwd","timeout":30}]}
It runs as the desktop user in /workspace on the same DISPLAY and returns output
and a screenshot. Commands are bounded; their process-group children stop on return.
This is hybrid GUI+CLI: code, scripts, application APIs, and command-line utilities
are allowed, subject to any explicit constraints in your own task. Headless helper
processes are allowed. Real GUI evidence must come from this shared desktop.
Screenshots presented by the bridge use 1280x800 coordinates; the actual display is
1600x1000. Capture unmodified full-resolution screenshots for requested deliverables
using scrot on the target desktop. Do not fabricate UI screenshots or measurements.
Grader/reference files, infrastructure and host credentials are not accessible and
must not be sought. Only report work you actually completed and saved.
"""


class WeaveDesktop(ORIGINAL_DESKTOP):
    def start(self):
        collector.command(["docker", "run", "-d", "--name", self.name, "--network", "none",
            "--cpus", "4", "--memory", "8g", "--shm-size", "1g", "--pids-limit", "512",
            "--security-opt", "no-new-privileges", "--label", "paragui.kind=weavebench-pair",
            "-v", str(self.root / "workspace") + ":/workspace", self.image, "sleep", "infinity"], timeout=90)
        self.created = True
        collector.command(["docker", "exec", self.name, "bash", "-c",
            "useradd -m -u 1000 -s /bin/bash gui; mkdir /tmp/runtime-gui; "
            "chown 1000:1000 /tmp/runtime-gui; chmod 700 /tmp/runtime-gui; "
            "ln -s /workspace /tmp_workspace; chown -R 1000:1000 /workspace"])
        documents = ["/tmp_workspace/" + name for name in PAIRS[self.pair]["documents"]]
        opened = documents[1:] if self.pair == "wvink" else documents
        launch = (["inkscape", "--with-gui", *opened] if self.pair == "wvink" else
            ["libreoffice", "--writer", "--norestore", "--nologo", "--nofirststartwizard", *documents])
        script = "import subprocess,time; subprocess.Popen(['openbox'],stdout=open('/tmp/openbox.log','w'),stderr=subprocess.STDOUT); time.sleep(1); subprocess.run(" + repr(launch) + ",stdout=open('/tmp/app.log','w'),stderr=subprocess.STDOUT)"
        collector.command(["docker", "exec", "-d", "--user", "1000:1000", "-e", "HOME=/home/gui",
            "-e", "XDG_RUNTIME_DIR=/tmp/runtime-gui", "-e", "SAL_USE_VCLPLUGIN=gtk3",
            self.name, "bash", "-c",
            "Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & "
            "sleep 2; export DISPLAY=:99; exec dbus-run-session -- python3 -c " + shlex.quote(script)])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            titles = self.raw(["bash", "-c", "wmctrl -l"], check=False).stdout.decode(errors="replace")
            if all(Path(name).name in titles for name in opened):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Official starting documents did not open: " + titles)
        windows = self.raw(["wmctrl", "-lp"], check=False).stdout.decode(errors="replace")
        collector.save(self.root / "startup.json", {"documents": documents, "opened": opened, "windows": windows,
            "processes": self.raw(["ps", "-eo", "pid,ppid,args"]).stdout.decode(errors="replace"),
            "timestamp": time.time()})
        for title in opened:
            self.raw(["wmctrl", "-r", Path(title).name, "-b", "add,maximized_vert,maximized_horz"], check=False)
        self.raw(["wmctrl", "-a", Path(opened[0]).name], check=False)
        time.sleep(1)
        self.screenshot(self.root / "initial.png")

    def stop(self):
        if self.created:
            try:
                self.screenshot(self.root / "final.png")
            except Exception:
                pass
        super().stop()


def defer_evaluation(root, pair, dataset, image):
    return {role: {"score": None, "status": "judge_pending"} for role in "ab"}


def report(root, manifest, results):
    metrics = ORIGINAL_REPORT(root, manifest, results)
    manifest.update(official_tasks=PAIRS[manifest["tasks"][0][:-1]]["tasks"],
        original_prompt_unchanged=not manifest['smoke'], initial_documents=1 if manifest["tasks"][0].startswith("wvink") else 2,
        shared_gui_profile=True,
        scoring="official-rubric-separate-judge", leaderboard_comparable=False)
    collector.save(root / "manifest.json", manifest)
    lines = ["# Official WeaveBench paired run (adapted protocol)", "",
        f"{manifest['harness']} / {manifest['mode']}; one desktop, two separate official documents.",
        "Hybrid GUI+CLI; original prompts unchanged; /tmp_workspace aliases /workspace.",
        "Matched sequential and parallel controls use identical frozen inputs and budgets.",
        "Scores are populated by the separately isolated, trajectory-aware official-rubric judge.",
        "Not an official leaderboard result; one repetition does not estimate success probability.", "",
        "| Role | Stop | Responses | Desktop actions |", "|---|---|---:|---:|"]
    for result in results:
        lines.append(f"| {result['task']} | {result['status']} | {result['model_responses']} | {result['actions']} |")
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "credentials", "out", "freehand-runtime", "codex-binary"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pair", choices=PAIRS, required=True)
    parser.add_argument("--harness", choices=("codex", "freehand"), required=True)
    parser.add_argument("--condition", choices=("parallel_shared", "sequential_ab", "sequential_ba"), required=True)
    parser.add_argument("--image", default="paragui/weavebench-pairs:20261103")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(args.credentials.read_text())
    if config["model"] != "gpt-6-astra" or config.get("reasoning_effort", "high") != "high":
        raise ValueError("Expected gpt-6-astra / high")
    args.task_roles = "ba" if args.condition == "sequential_ba" else "ab"
    args.mode = "parallel" if args.condition == "parallel_shared" else "sequential"
    args.coagent_hint = args.mode == "parallel"
    args.interaction_mode, args.image_history_limit = "hybrid", 4
    args.codex_permissions = "container-unrestricted" if args.harness == "codex" else "reviewed"
    args.max_actions, args.max_turns, args.timeout = (10, 12, 360) if args.smoke else (300, 90, 1500)
    native.interaction_rules, native.report = pair_rules, report
    collector.Desktop, collector.evaluate = WeaveDesktop, defer_evaluation
    collector.APPS[args.pair] = (PAIRS[args.pair]["app"], "", "")
    return native.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
