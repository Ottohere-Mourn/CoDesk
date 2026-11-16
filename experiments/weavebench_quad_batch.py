"""Durable 1/2/4-agent pilot; publish efficiency before separate quality judging."""
import argparse
import collections
import json
from pathlib import Path
import subprocess
import sys
import time

from experiments.professional_codex_entry import permissions
from experiments.professional_native import hybrid_smoke_passed
from experiments.professional_trajectories import hashes, save
from experiments.responses_relay import image_history_policy
from experiments.weavebench_batch import resource_gate, cleanup_interrupted
from experiments.weavebench_judge import judge
from experiments.weavebench_quad import BINDINGS, PAIR, wave_roles


def plan():
    order = [("freehand", 4), ("codex", 4), ("codex", 2), ("freehand", 2), ("freehand", 1), ("codex", 1)]
    return [{"id": f"{harness}-c{width}-r1", "harness": harness, "concurrency": width,
        "waves": wave_roles(width), "status": "pending", "scores": {role: None for role in BINDINGS}}
        for harness, width in order]


def preflight_ready(root, harness):
    manifest = json.loads((root / "manifest.json").read_text())
    validation = json.loads((root / "validation.json").read_text())
    results = json.loads((root / "summary.json").read_text())
    assert manifest["tasks"] == [PAIR + role for role in BINDINGS]
    assert manifest['harness'] == harness and manifest['smoke']
    assert manifest['max_concurrent_agents'] == 4 and manifest['actual_peak_active_agents'] == 4
    assert manifest['image_history_policy'] == image_history_policy(4)
    assert manifest['interaction_mode'] == 'hybrid' and not validation['integrity_errors']
    assert all(result['model_responses'] > 0 and hybrid_smoke_passed(root / result['task']) for result in results)
    if harness == 'codex':
        assert manifest['codex_permissions'] == permissions('container-unrestricted', 'hybrid')
        assert all(result.get('permission_audit') for result in results)
    return {"ready_for_execution": True, "native_validation_passed": validation['passed'],
        "agent_statuses": {result['task'][-1]: result['status'] for result in results},
        "basis": "Four overlapping agents each got successful model output and performed real screenshot plus target CLI; terminal API failures remain separately visible."}


def performance(directory):
    results = json.loads((directory / 'summary.json').read_text())
    metrics = json.loads((directory / 'concurrency.json').read_text())
    agents = []
    for result in results:
        request_file = directory / result['task'] / 'requests.jsonl'
        requests = [json.loads(line) for line in request_file.read_text().splitlines()] if request_file.exists() else []
        usage = collections.Counter()
        failed = collections.Counter()
        missing = 0
        for row in requests:
            if not row['ok']:
                failed[str(row['http_status'])] += 1
            data = row.get('usage')
            if not data:
                missing += 1
                continue
            for name in ('input_tokens', 'output_tokens', 'total_tokens'):
                usage[name] += data.get(name, 0)
            usage['cached_tokens'] += data.get('input_tokens_details', {}).get('cached_tokens', 0) or 0
            usage['reasoning_tokens'] += data.get('output_tokens_details', {}).get('reasoning_tokens', 0) or 0
        meta = directory / result['task'] / 'runtime/.state/meta.json'
        backoff = json.loads(meta.read_text()).get('throttle_wait_s') if meta.exists() else None
        agents.append({"role": result['task'][-1], "status": result['status'],
            "wall_s": result.get('finished_at', 0) - result.get('agent_started_at', result.get('finished_at', 0)),
            "started_at": result.get('agent_started_at'), "finished_at": result.get('finished_at'),
            "model_responses": result['model_responses'], "actions": result['actions'],
            "broker_action_counts": result.get('broker_action_counts'), "tokens": dict(usage),
            "request_errors": dict(failed), "requests_missing_usage": missing, "explicit_retry_sleep_s": backoff})
    started = [agent['started_at'] for agent in agents if agent['started_at'] is not None]
    finished = [agent['finished_at'] for agent in agents if agent['finished_at'] is not None]
    result = {"agents": agents, "all_agents_completed": all(agent['status'] == 'completed' for agent in agents),
        "pair_makespan_s": max(finished) - min(started) if started and finished else None,
        "agent_wall_sum_s": sum(agent['wall_s'] for agent in agents),
        "total_tokens": sum(agent['tokens'].get('total_tokens', 0) for agent in agents),
        "input_tokens": sum(agent['tokens'].get('input_tokens', 0) for agent in agents),
        "output_tokens": sum(agent['tokens'].get('output_tokens', 0) for agent in agents),
        "cached_tokens": sum(agent['tokens'].get('cached_tokens', 0) for agent in agents),
        "requests_missing_usage": sum(agent['requests_missing_usage'] for agent in agents),
        "http_429": sum(agent['request_errors'].get('429', 0) for agent in agents),
        "activity_levels": metrics['agent_activity_levels'], "http_activity_levels": metrics['http_activity_levels'],
        "scope": "All four execution agents; includes retry/tool time, excludes setup/preflight/judge; unknown token usage is missing, never a zero-cost assertion."}
    save(directory / 'performance.json', result)
    return result


def write_progress(root, progress):
    progress['updated_at'] = time.time()
    save(root / 'progress.json', progress)
    lines = ["# Four tasks on one desktop: concurrency 1 / 2 / 4", "",
        "Four unchanged official tasks: two Inkscape and two Writer, separate documents on one shared desktop.",
        "Six conditions = two harnesses × three concurrency levels; 24 task attempts, one repetition per condition.",
        "Priority order starts with four agents; not randomized. Width 2 uses same-software waves ab, cd; width 1 uses a,b,c,d.",
        "gpt-6-astra/high; hybrid; 300 actions / 90 successful responses / 1500 seconds per agent; 4 recent tool images.",
        "Desktop fixed at 4 CPUs / 8 GiB; no cross-agent input lock, automatic refocusing or API concurrency limiter.",
        "Judge v2 is grounded only in the agent-visible Prompt, so no undisclosed UNO/XML ban. Old scores remain unchanged.",
        "Efficiency publishes as attempts end; all task runs finish before judging starts, to avoid judge traffic contamination.",
        "API/infrastructure failure is not GUI failure; missing score is not zero. Completed is not task success.",
        "Only compare matched new conditions; previous two-task runs are not identical four-task controls.", "",
        f"Status: {progress['status']}; stage: {progress.get('stage')}", "",
        "| Harness | Width | Stage | Peak actors | Four-task minutes | Agent-minutes | Reported tokens | 429 | Quality |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|"]
    for job in progress['conditions']:
        perf = job.get('performance', {})
        duration = perf.get('pair_makespan_s')
        minutes = '—' if duration is None else f"{duration/60:.2f}"
        agent_time = '—' if not perf else f"{perf['agent_wall_sum_s']/60:.2f}"
        quality = ', '.join(role + ':' + ('pending/error' if score is None else f'{score:.3f}') for role, score in job['scores'].items())
        lines.append(f"| {job['harness']} | {job['concurrency']} | {job['status']} | {perf.get('activity_levels', {}).get('peak_distinct_agents', '—')} | {minutes} | {agent_time} | {perf.get('total_tokens', '—')} | {perf.get('http_429', '—')} | {quality} |")
    lines.extend(["", "Times include retries and provider latency; token totals include repeated context and cached inputs.",
        "One repetition, unequal retry delays and pending quality checks prevent causal efficiency claims."])
    (root / 'REPORT.md').write_text('\n'.join(lines) + '\n')


def command_for(args, out, harness, width, smoke=False):
    command = [sys.executable, '-u', '-m', 'experiments.weavebench_quad', '--dataset', str(args.dataset),
        '--credentials', str(args.credentials), '--out', str(out), '--harness', harness, '--concurrency', str(width),
        '--freehand-runtime', str(args.freehand_runtime), '--codex-binary', str(args.codex_binary), '--image', args.image]
    return command + (['--smoke'] if smoke else [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'dataset', 'credentials', 'freehand-runtime', 'codex-binary'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--image', default='paragui/weavebench-pairs:20261103')
    args = parser.parse_args(argv)
    args.root.mkdir(parents=True, exist_ok=True)
    checkpoint = args.root / 'progress.json'
    progress = json.loads(checkpoint.read_text()) if checkpoint.exists() else {
        'status': 'running', 'stage': 'preflight', 'started_at': time.time(), 'conditions': plan(),
        'preflights': {}, 'input_hashes': hashes(args.dataset / 'dataset'),
        'judge_policy': 'agent-visible-hybrid-v2', 'judge_timeout_s': 900}
    if hashes(args.dataset / 'dataset') != progress['input_hashes']:
        raise ValueError('Frozen workload changed')
    write_progress(args.root, progress)
    for harness in ('freehand', 'codex'):
        if progress['preflights'].get(harness, {}).get('ready_for_execution'):
            continue
        for attempt in range(1, 3):
            progress.update(stage=f'preflight-{harness}-{attempt}')
            write_progress(args.root, progress)
            directory = args.root / f'preflight-{harness}-{attempt}'
            if not directory.exists():
                with (args.root / f'preflight-{harness}-{attempt}.log').open('w') as log:
                    try:
                        subprocess.run(command_for(args, directory, harness, 4, True), stdout=log,
                            stderr=subprocess.STDOUT, timeout=600)
                    except subprocess.TimeoutExpired:
                        cleanup_interrupted(directory)
            try:
                state = preflight_ready(directory, harness)
            except Exception as error:
                state = {'ready_for_execution': False, 'error': f'{type(error).__name__}: {error}'}
            state['directory'] = str(directory)
            progress['preflights'][harness] = state
            write_progress(args.root, progress)
            if state['ready_for_execution']:
                break
            if attempt == 1:
                time.sleep(60)
    progress.update(stage='task-runs', status='running')
    write_progress(args.root, progress)
    for job in progress['conditions']:
        if job['status'] in ('executed', 'run_error', 'resource_skipped', 'preflight_failed', 'graded', 'graded_with_errors'):
            continue
        if not progress['preflights'].get(job['harness'], {}).get('ready_for_execution'):
            job['status'] = 'preflight_failed'
            write_progress(args.root, progress)
            continue
        if not resource_gate(args.root, job['id']):
            job['status'] = 'resource_skipped'
            write_progress(args.root, progress)
            continue
        directory = args.root / job['id']
        if not (directory / 'summary.json').exists():
            if directory.exists():
                cleanup_interrupted(directory)
                directory.rename(directory.with_name(directory.name + '-interrupted-' + str(int(time.time()))))
            job.update(status='running', started_at=time.time())
            write_progress(args.root, progress)
            with (args.root / (job['id'] + '.log')).open('a') as log:
                try:
                    result = subprocess.run(command_for(args, directory, job['harness'], job['concurrency']),
                        stdout=log, stderr=subprocess.STDOUT, timeout=1500 * len(job['waves']) + 300)
                    job['exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    cleanup_interrupted(directory)
                    job.update(exit_code=124, error='Outer run watchdog expired')
        if (directory / 'summary.json').exists():
            try:
                job['performance'] = performance(directory)
                job.update(status='executed', execution_finished_at=time.time())
            except Exception as error:
                job.update(status='run_error', error=f'{type(error).__name__}: {error}')
        else:
            job['status'] = 'run_error'
        write_progress(args.root, progress)
    progress.update(stage='quality-judging', execution_finished_at=time.time())
    write_progress(args.root, progress)
    for job in progress['conditions']:
        if job['status'] != 'executed':
            continue
        directory = args.root / job['id']
        for role in BINDINGS:
            if not resource_gate(args.root, job['id'] + '-judge-' + role):
                job.setdefault('judge_errors', {})[role] = 'resource gate'
                continue
            state_file = directory / 'judging' / role / 'status.json'
            try:
                state = json.loads(state_file.read_text()) if state_file.exists() else judge(directory,
                    args.dataset, role, args.credentials, args.freehand_runtime, args.codex_binary, args.image, timeout=900)
            except Exception as error:
                state = {'status': 'judge_error', 'score': None, 'error': f'{type(error).__name__}: {error}'}
                state_file.parent.mkdir(parents=True, exist_ok=True)
                save(state_file, state)
            job['scores'][role] = state.get('score')
            job.setdefault('judge_statuses', {})[role] = state['status']
            write_progress(args.root, progress)
        good = all(score is not None for score in job['scores'].values()) and job['performance']['all_agents_completed']
        job.update(status='graded' if good else 'graded_with_errors', finished_at=time.time())
        write_progress(args.root, progress)
    progress.update(status='finished' if all(job['status'] == 'graded' for job in progress['conditions']) else
        'finished_with_errors', stage='done', finished_at=time.time())
    write_progress(args.root, progress)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
