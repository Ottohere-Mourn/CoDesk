"""Durable matched official-task batch with bounded waits and isolated judging."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from experiments.professional_native_batch import validate_preflight
from experiments.professional_trajectories import command as infrastructure_command, hashes, save
from experiments.weavebench_pairs import PAIRS
from experiments.weavebench_judge import judge


def plan():
    core = [
        ("wvink", "codex", "parallel_shared"), ("wvink", "freehand", "sequential_ab"),
        ("wvink", "codex", "sequential_ab"), ("wvink", "freehand", "parallel_shared"),
        ("wvwriter", "freehand", "parallel_shared"), ("wvwriter", "codex", "sequential_ab"),
        ("wvwriter", "freehand", "sequential_ab"), ("wvwriter", "codex", "parallel_shared"),
    ]
    reverse = [(pair, harness, "sequential_ba") for pair in PAIRS for harness in ("freehand", "codex")]
    return [{"id": f"{pair}-{harness}-{condition}", "pair": pair, "harness": harness,
        "condition": condition, "status": "pending", "scores": {"a": None, "b": None}}
        for pair, harness, condition in core + reverse]


def write_progress(root, progress):
    progress["updated_at"] = time.time()
    save(root / "progress.json", progress)
    lines = ["# WeaveBench official-task pairs — adapted shared-desktop experiment", "",
        "One repetition: 2 software pairs × 2 harnesses × parallel / A→B / B→A = 12 conditions, 24 task attempts.",
        "Two original documents share one desktop/profile/clipboard/input stream; output names do not collide.",
        "Agent: gpt-6-astra/high, hybrid, 300 desktop actions / 90 responses / 1500 seconds each, 4 recent tool images.",
        "Judging: unchanged upstream trajectory-aware rubric, executed by isolated Codex/gpt-6-astra (not upstream OpenClaw).",
        "Original prompts/assets/ground truth are pinned; this is NOT an official WeaveBench leaderboard score.",
        "A missing score is a judge/infrastructure error or pending work, never silently a zero.", "",
        f"Batch status: {progress['status']}", "",
        "| Software | Harness | Condition | State | A score | B score |", "|---|---|---|---|---:|---:|"]
    for job in progress["conditions"]:
        scores = job.get("scores", {})
        lines.append(f"| {job['pair']} | {job['harness']} | {job['condition']} | {job['status']} | {scores.get('a')} | {scores.get('b')} |")
    lines += ["", "## Interpretation limits", "",
        "Parallel-vs-sequential score deltas alone do not prove a conflict. Inspect timeline.jsonl, screenshots, and concurrency.json.",
        "These are same-software, separate-document conflicts, not two agents modifying the same semantic object.",
        "Original WeaveBench specs have internal discrepancies (e.g. DES11 old GT thresholds vs stronger Prompt); raw scores are retained for audit.",
        "DOC2 includes implementation restrictions in hidden grading prose that are absent from the agent Prompt. Interpret related deductions cautiously.",
        "The equal 1500-second budget differs from original task metadata (1200–1800 seconds); compare only within this protocol."]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")


def resource_gate(root, stage, timeout=600):
    deadline = time.monotonic() + timeout
    while True:
        memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
        full = next(line for line in Path('/proc/pressure/io').read_text().splitlines() if line.startswith('full '))
        pressure = float(dict(part.split('=') for part in full.split()[1:])['avg10'])
        sample = {"stage": stage, "time": time.time(), "free_bytes": shutil.disk_usage(root).free,
            "mem_available_kib": memory['MemAvailable'], "io_full_avg10": pressure}
        sample['ready'] = sample['free_bytes'] >= 40 * 1024**3 and sample['mem_available_kib'] >= 12 * 1024**2 and pressure < 30
        save(root / "resource-status.json", sample)
        if sample['ready']:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(15)


def wait_for_previous(root, previous, timeout=7200):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not previous.exists():
            raise ValueError("Previous batch status unavailable; refusing to guess whether it is active")
        state = json.loads(previous.read_text())
        if state.get("status") != "running":
            save(root / "previous-batch.json", {"file": str(previous), "state": state, "checked_at": time.time()})
            return
        save(root / "waiting.json", {"reason": "previous synthetic batch still using the shared API; not a disk wait",
            "previous_status": str(previous), "checked_at": time.time(), "deadline": time.time() + deadline - time.monotonic()})
        time.sleep(30)
    raise TimeoutError("Previous batch still active after two hours; no old jobs were stopped")


def cleanup_interrupted(directory):
    manifest = directory / "manifest.json"
    if not manifest.exists():
        return
    state = json.loads(manifest.read_text())
    container = state.get('container', '')
    if not container.startswith('paragui-traj-wv'):
        return
    names = [container] + [container + '-' + task + '-' + state['harness'] for task in state['tasks']]
    infrastructure_command(['docker', 'rm', '-f', *names], check=False)
    infrastructure_command(['docker', 'network', 'rm', container + '-agents'], check=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "dataset", "credentials", "freehand-runtime", "codex-binary", "preflight-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--previous-status", type=Path)
    parser.add_argument("--image", default="paragui/weavebench-pairs:20261103")
    args = parser.parse_args(argv)
    for harness in ("codex", "freehand"):
        validate_preflight(args.preflight_root / ("preflight-" + harness), harness,
            "container-unrestricted", "hybrid", 4)
    args.root.mkdir(parents=True, exist_ok=True)
    path = args.root / "progress.json"
    progress = json.loads(path.read_text()) if path.exists() else {
        "status": "starting", "started_at": time.time(), "conditions": plan(),
        "input_hashes": hashes(args.dataset / "dataset"), "model": "gpt-6-astra", "reasoning_effort": "high"}
    if hashes(args.dataset / "dataset") != progress["input_hashes"]:
        raise ValueError("Frozen task inputs changed")
    progress["status"] = "waiting_for_previous_batch" if args.previous_status else "running"
    write_progress(args.root, progress)
    if args.previous_status:
        wait_for_previous(args.root, args.previous_status)
    progress["status"] = "running"
    write_progress(args.root, progress)
    for job in progress["conditions"]:
        if job['status'] in ("finished", "finished_with_errors", "run_error", "resource_skipped"):
            continue
        directory = args.root / job["id"]
        if not resource_gate(args.root, job['id']):
            job.update(status="resource_skipped", finished_at=time.time())
            write_progress(args.root, progress)
            continue
        if not (directory / "summary.json").exists():
            if directory.exists():
                cleanup_interrupted(directory)
                directory.rename(directory.with_name(directory.name + "-interrupted-" + str(int(time.time()))))
            job.update(status="running", started_at=time.time())
            write_progress(args.root, progress)
            command = [sys.executable, "-u", "-m", "experiments.weavebench_pairs", "--dataset", str(args.dataset),
                "--credentials", str(args.credentials), "--out", str(directory), "--harness", job['harness'],
                "--pair", job['pair'], "--condition", job['condition'], "--image", args.image,
                "--freehand-runtime", str(args.freehand_runtime), "--codex-binary", str(args.codex_binary)]
            with (args.root / (job['id'] + '.log')).open('a') as log:
                try:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
                    job['exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    cleanup_interrupted(directory)
                    job.update(exit_code=124, error='Outer 3600-second condition watchdog expired')
        summary = directory / "summary.json"
        if not summary.exists():
            job.update(status="run_error", finished_at=time.time())
            write_progress(args.root, progress)
            continue
        agents = json.loads(summary.read_text())
        job.update(status="judging", agent_statuses={agent['task'][-1]: agent['status'] for agent in agents},
            actions={agent['task'][-1]: agent['actions'] for agent in agents},
            responses={agent['task'][-1]: agent['model_responses'] for agent in agents})
        write_progress(args.root, progress)
        judge_states = {}
        for role in "ab":
            state_file = directory / "judging" / role / "status.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
            else:
                state = judge(directory, args.dataset, role, args.credentials, args.freehand_runtime,
                    args.codex_binary, args.image)
            judge_states[role] = state
            job['scores'][role] = state.get('score')
            job.setdefault('judge_statuses', {})[role] = state['status']
            write_progress(args.root, progress)
        for agent in agents:
            state = judge_states[agent['task'][-1]]
            agent.update(score=state.get('score'), rubric_evaluation=state,
                scoring_label='official-rubric-adapted-Codex-judge')
            save(directory / agent['task'] / 'judged-result.json', agent)
        save(directory / 'judged-summary.json', agents)
        good = all(state['status'] == 'scored' for state in judge_states.values()) and not job.get('exit_code')
        job.update(status="finished" if good else "finished_with_errors", finished_at=time.time())
        write_progress(args.root, progress)
    progress.update(status="finished" if all(job['status'] == 'finished' for job in progress['conditions']) else
        "finished_with_errors", finished_at=time.time())
    write_progress(args.root, progress)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
