"""Launch exactly two four-agent Writer trials, with durable status and no extra model preflights."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from experiments.professional_trajectories import hashes, save
from experiments.weavebench_batch import cleanup_interrupted, resource_gate
from experiments.weavebench_quad import activity_levels
from experiments.weavebench_quad_batch import performance
from experiments.weavebench_writer_conflict import IMAGE


def plan():
    return [{'id': harness + '-c4-r1', 'harness': harness, 'concurrency': 4, 'waves': ['abcd'],
        'status': 'pending', 'scores': {role: None for role in 'abcd'}, 'joint_success': None}
        for harness in ('freehand', 'codex')]


def verify_validation(dataset, validation, source):
    report = json.loads(validation.read_text())
    if report.get('passed') is not True or report.get('LLM_rollouts') != 0:
        raise ValueError('Native feasibility validation must pass before model trials')
    for relative, digest in report['source_hashes'].items():
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != digest:
            raise ValueError('Validated source changed: ' + relative)
    if hashes(dataset) != report['dataset_hashes']:
        raise ValueError('Validated dataset changed')
    return report


def command_for(args, directory, harness):
    return [sys.executable, '-u', '-m', 'experiments.weavebench_writer_conflict',
        '--dataset', str(args.dataset), '--credentials', str(args.credentials), '--out', str(directory),
        '--harness', harness, '--freehand-runtime', str(args.freehand_runtime),
        '--codex-binary', str(args.codex_binary), '--image', args.image]


def write_progress(root, progress):
    progress['updated_at'] = time.time()
    save(root / 'progress.json', progress)
    lines = ['# Writer seed: two four-concurrent trials', '',
        'One repetition per harness; Freehand then Codex, with four agents simultaneously inside each trial.',
        'Same validated pristine inputs, separate fresh desktops; no 1/2-agent controls or extra model preflights.',
        'gpt-6-astra/high; hybrid GUI+CLI; each agent: 300 actions, 90 responses, 1500 seconds.',
        'Deterministic owned and joint checks run automatically after each trial. D depends on A/B/C.',
        'A completed process is not necessarily a successful task. API errors are not evidence of state conflict.', '',
        f"Status: {progress['status']}; stage: {progress.get('stage')}", '',
        '| Harness | State | A | B | C | D | Joint success |', '|---|---|---:|---:|---:|---:|---|']
    for job in progress['conditions']:
        scores = [str(job['scores'][role]) for role in 'abcd']
        lines.append('| ' + ' | '.join([job['harness'], job['status'], *scores, str(job['joint_success'])]) + ' |')
    (root / 'REPORT.md').write_text('\n'.join(lines) + '\n')


def collect_performance(directory):
    results = json.loads((directory / 'summary.json').read_text())
    metrics = json.loads((directory / 'concurrency.json').read_text())
    intervals = []
    for result in results:
        path = directory / result['task'] / 'requests.jsonl'
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                intervals.append((result['task'], row['started_at'], row['started_at'] + row['latency_s']))
    metrics['http_activity_levels'] = activity_levels(intervals)
    save(directory / 'concurrency.json', metrics)
    return performance(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'dataset', 'credentials', 'freehand-runtime', 'codex-binary', 'native-validation'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--image', default=IMAGE)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    validation = verify_validation(args.dataset, args.native_validation, source)
    config = json.loads(args.credentials.read_text())
    if config['model'] != 'gpt-6-astra' or config.get('reasoning_effort', 'high') != 'high':
        raise ValueError('Expected the same frozen gpt-6-astra/high model configuration')
    image_id = subprocess.run(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'],
        check=True, capture_output=True, text=True).stdout.strip()
    if image_id != validation['image_id']:
        raise ValueError('Image differs from native validation')
    args.root.mkdir(parents=True, exist_ok=False)
    progress = {'status': 'running', 'stage': 'starting', 'started_at': time.time(), 'conditions': plan(),
        'model': config['model'], 'reasoning_effort': 'high', 'image_id': image_id,
        'native_validation': str(args.native_validation), 'model_task_attempts_planned': 8,
        'sequential_harnesses': True, 'dataset_hashes': validation['dataset_hashes']}
    write_progress(args.root, progress)
    for job in progress['conditions']:
        directory = args.root / job['id']
        progress['stage'] = job['id']
        write_progress(args.root, progress)
        try:
            verify_validation(args.dataset, args.native_validation, source)
            if not resource_gate(args.root, job['id'], timeout=0):
                job['status'] = 'resource_skipped'
                continue
            job.update(status='running', started_at=time.time())
            write_progress(args.root, progress)
            with (args.root / (job['id'] + '.log')).open('wb') as log:
                try:
                    result = subprocess.run(command_for(args, directory, job['harness']),
                        stdout=log, stderr=subprocess.STDOUT, timeout=1950)
                    job['exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    cleanup_interrupted(directory)
                    job.update(exit_code=124, error='Outer trial watchdog expired')
            summary_path = directory / 'summary.json'
            grade_path = directory / 'shared/evaluation/grade.json'
            if not summary_path.exists():
                job['status'] = 'run_error'
                cleanup_interrupted(directory)
                continue
            job['performance'] = collect_performance(directory)
            if grade_path.exists():
                grade = json.loads(grade_path.read_text())
                job.update(scores={role: grade['roles'][role]['score'] for role in 'abcd'},
                    joint_success=grade['success'], joint_checks=grade['joint'],
                    status='finished' if job['exit_code'] == 0 else 'finished_with_errors')
            else:
                job['status'] = 'evaluation_error'
        except Exception as error:
            job.update(status='run_error', error=f'{type(error).__name__}: {error}')
        finally:
            job['finished_at'] = time.time()
            write_progress(args.root, progress)
    clean = all(job['status'] == 'finished' for job in progress['conditions'])
    progress.update(status='finished' if clean else 'finished_with_errors', stage='done', finished_at=time.time())
    write_progress(args.root, progress)
    return int(not clean)


if __name__ == '__main__':
    raise SystemExit(main())
