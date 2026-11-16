"""One shared Writer document; four concurrent native agents, never 1/2-agent waves."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shlex
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from experiments import professional_native as native
from experiments import professional_trajectories as collector
from tasks.weavebench_writer_conflict.spec import NOTE, NS, PAIR, section_rows, tag


SOURCE = Path(__file__).resolve().parents[1]
IMAGE = 'paragui/weavebench-pairs:20261103'
ORIGINAL_REPORT = native.report


class WriterDesktop(collector.Desktop):
    def raw(self, argv, **kwargs):
        return collector.command(['docker', 'exec', '--user', '1000:1000', '-e', 'DISPLAY=:99',
            '-e', 'HOME=/home/gui', '-e', 'XDG_RUNTIME_DIR=/tmp/runtime-gui',
            '-e', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus', self.name, *argv], **kwargs)

    def observe(self):
        code = (SOURCE / 'tasks/weavebench_writer_conflict/observer.py').read_text()
        return json.loads(self.raw(['python3', '-c', code], timeout=45).stdout)

    def start(self):
        collector.command(['docker', 'run', '-d', '--name', self.name, '--network', 'none', '--cpus', '4',
            '--memory', '8g', '--shm-size', '1g', '--pids-limit', '512', '--security-opt', 'no-new-privileges',
            '--label', 'paragui.kind=writer-seeded-conflict', '-v', str(self.root / 'workspace') + ':/workspace',
            self.image, 'sleep', 'infinity'], timeout=90)
        self.created = True
        collector.command(['docker', 'exec', self.name, 'bash', '-c',
            'useradd -m -u 1000 -s /bin/bash gui; mkdir /tmp/runtime-gui; '
            'chown 1000:1000 /tmp/runtime-gui; chmod 700 /tmp/runtime-gui; '
            'ln -s /workspace /tmp_workspace; chown -R 1000:1000 /workspace'])
        script = """import subprocess,time
subprocess.Popen(['openbox'],stdout=open('/tmp/openbox.log','w'),stderr=subprocess.STDOUT)
time.sleep(1)
subprocess.call(['libreoffice','--writer','--norestore','--nologo','--nofirststartwizard',
    '--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager','/workspace/report.odt'],
    stdout=open('/tmp/app.log','w'),stderr=subprocess.STDOUT)
"""
        collector.command(['docker', 'exec', '-d', '--user', '1000:1000', '-e', 'HOME=/home/gui',
            '-e', 'XDG_RUNTIME_DIR=/tmp/runtime-gui', '-e', 'SAL_USE_VCLPLUGIN=gtk3',
            '-e', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/runtime-gui/bus', self.name, 'bash', '-c',
            'Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & sleep 2; '
            'export DISPLAY=:99; dbus-daemon --session --fork --address=unix:path=/tmp/runtime-gui/bus; '
            'exec python3 -c ' + shlex.quote(script)])
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            windows = self.raw(['wmctrl', '-lp'], check=False).stdout.decode(errors='replace')
            if 'report.odt' in windows:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Canonical Writer window did not open: ' + windows)
        self.raw(['wmctrl', '-r', 'report.odt', '-b', 'add,maximized_vert,maximized_horz'], check=False)
        state = self.observe()
        collector.save(self.root / 'initial-live.json', state)
        self.screenshot(self.root / 'initial.png')
        collector.save(self.root / 'startup.json', {'windows': windows, 'writer_documents': state['writer_document_count'],
            'desktop_count': 1, 'timestamp': time.time(), 'observer_read_only': True})
        self.version_stop = threading.Event()
        self.version_thread = threading.Thread(target=self.watch_versions, daemon=True)
        self.version_thread.start()

    def watch_versions(self):
        versions = self.root / 'saved-versions'
        versions.mkdir(exist_ok=True)
        previous = None
        while not self.version_stop.is_set():
            try:
                blob = (self.root / 'workspace/report.odt').read_bytes()
                digest = hashlib.sha256(blob).hexdigest()
                if digest != previous:
                    with ZipFile(io.BytesIO(blob)) as archive:
                        archive.read('content.xml')
                    (versions / (digest + '.odt')).write_bytes(blob)
                    collector.append(self.root / 'saved-versions.jsonl', {'timestamp': time.time(), 'sha256': digest})
                    previous = digest
            except Exception as error:
                collector.append(self.root / 'observer-errors.jsonl', {'timestamp': time.time(), 'error': type(error).__name__})
            self.version_stop.wait(.5)

    def stop(self):
        if hasattr(self, 'version_stop'):
            self.version_stop.set()
            self.version_thread.join(timeout=10)
        if self.created:
            try:
                collector.save(self.root / 'final-live.json', self.observe())
                self.screenshot(self.root / 'final.png')
            except Exception as error:
                collector.save(self.root / 'final-live.json', {'error': str(error)})
        super().stop()


def grade_workspace(root, pair, dataset, image):
    evaluation = root / 'evaluation'
    evaluation.mkdir(exist_ok=False)
    arguments = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '4', '--memory', '4g',
        '-v', str(SOURCE) + ':/code:ro', '-v', str(root / 'workspace') + ':/work:ro',
        '-v', str(dataset / 'private') + ':/trusted:ro', '-v', str(root / 'final-live.json') + ':/live.json:ro',
        '-v', str(evaluation) + ':/evaluation', '-e', 'PYTHONPATH=/code', '-e', 'PYTHONDONTWRITEBYTECODE=1',
        image, 'python3', '-m', 'tasks.weavebench_writer_conflict.evaluate', '--workspace', '/work',
        '--baseline', '/trusted/baseline.json', '--live', '/live.json', '--out', '/evaluation']
    result = collector.command(arguments, timeout=240, check=False)
    (evaluation / 'stdout.log').write_bytes(result.stdout)
    (evaluation / 'stderr.log').write_bytes(result.stderr)
    result.check_returncode()
    grades = json.loads((evaluation / 'grade.json').read_text())
    return {role: {**grades['roles'][role], 'joint_success': grades['success'],
        'joint_checks': grades['joint'], 'evaluation_path': str(evaluation / 'grade.json')} for role in 'abcd'}


def rules():
    return """Four concurrent agents share ONE LibreOffice Writer session, one already-open
/workspace/report.odt, one DISPLAY, profile, clipboard, keyboard/mouse and filesystem.
Read /workspace/PROJECT_BRIEF.md and ACCEPTANCE.md. Work only on your assigned role;
preserve other roles' changes. No private desktops/profiles, stale wholesale document
replacement or killing the shared app. Shared-file coordination and critical sections
are allowed, but the harness supplies no lock and no separate chat tool.
Hybrid GUI+CLI is allowed, including Python, UNO and XML. The current Writer UNO
listener is socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext.
The desktop tool/bridge is the only route to target files. Native shell in your
harness is NOT the desktop. For example:
{"actions":[{"type":"shell","command":"pwd","timeout":30}]}
Desktop commands run in /workspace with the shared DISPLAY, return output and a
screenshot, and terminate their process-group children on return; do not background.
/tmp_workspace aliases /workspace. Tool screenshots use 1280x800 coordinates;
the actual desktop is 1600x1000. Recheck before acting; screen state can change.
Never access private graders/references, host credentials or harness infrastructure.
Save actual work and honestly report partial results; never fabricate evidence.
"""


def saved_signals(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('content.xml'))
    sections = {}
    for paragraph in root.iter():
        if paragraph.tag not in (tag('text', 'h'), tag('text', 'p')):
            continue
        for bookmark in paragraph.findall('text:bookmark-start', NS):
            sections[bookmark.get(tag('text', 'name'))] = paragraph
    expected = section_rows()
    complete = all(row['id'] in sections for row in expected)
    return {'a_outline_levels': complete and all(sections[row['id']].tag == tag('text', 'h') and
        sections[row['id']].get(tag('text', 'outline-level')) == '1' for row in expected),
        'b_title_text': complete and all(''.join(sections[row['id']].itertext()) == row['final_title'] for row in expected),
        'c_note_presence': sum(''.join(node.itertext()) == NOTE for node in root.findall('.//text:p', NS)) == 1}


def version_review(root):
    path = root / 'saved-versions.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    previous, observations, regressions = None, [], []
    for row in rows:
        try:
            current = saved_signals(root / 'saved-versions' / (row['sha256'] + '.odt'))
            observations.append({**row, 'signals': current})
            if previous:
                for name, passed in current.items():
                    if previous['signals'][name] and not passed:
                        regressions.append({'signal': name, 'before': previous['sha256'],
                            'after': row['sha256'], 'timestamp': row['timestamp']})
            previous = observations[-1]
        except Exception as error:
            observations.append({**row, 'error': type(error).__name__})
    return {'sample_interval_s': .5, 'observations': observations, 'possible_regressions': regressions,
        'interpretation': 'Read-only saved-state samples, selected structural signals only; lower bound on observed regressions, not causal proof. '
            'No observed regression does not establish absence of transient, live-buffer or unsampled conflicts.'}


def report(root, manifest, results):
    from experiments.weavebench_quad import activity_levels
    metrics = ORIGINAL_REPORT(root, manifest, results)
    metrics['agent_activity_levels'] = activity_levels([(row['task'], row['agent_started_at'], row['finished_at'])
        for row in results if 'agent_started_at' in row])
    versions = version_review(root / 'shared')
    collector.save(root / 'saved-version-review.json', versions)
    collector.save(root / 'concurrency.json', metrics)
    manifest.update(workload='WeaveBench-seeded shared Writer conflict', official_score=False,
        initial_document_windows=1, task_dependencies={'d': ['a', 'b', 'c']}, grading_policy='public-deterministic-v1',
        actual_peak_active_agents=metrics['agent_activity_levels']['peak_distinct_agents'])
    protected = [Path(__file__), *sorted((SOURCE / 'tasks/weavebench_writer_conflict').glob('*.py')),
        *sorted((SOURCE / 'tasks/weavebench_writer_conflict').glob('*.md'))]
    for path in protected:
        relative = path.relative_to(SOURCE)
        destination = root / 'workload-source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        manifest['source_hashes'][str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    collector.save(root / 'manifest.json', manifest)
    lines = ['# Shared Writer four-agent workload', '',
        f"Harness: {manifest['harness']}; four concurrent agents; one live document.",
        'Seed: DOC_task_2_heading_style_normalize. Derived workload, not an official WeaveBench score.',
        'Hybrid GUI+CLI, including UNO/XML; no harness input lock or auto-refocus.',
        'Artifact checks and joint consistency are deterministic; ownership/evidence authenticity still need trajectory review.',
        'D depends on A/B/C; role scores are not four independent success trials.', '',
        '| Role | Stop | Owned score | Actions | Responses |', '|---|---|---:|---:|---:|']
    for row in results:
        lines.append(f"| {row['task'][-1]} | {row['status']} | {row.get('score', 'pending')} | {row['actions']} | {row['model_responses']} |")
    lines.extend(['', 'Full check vectors, dependencies and joint result: shared/evaluation/grade.json.',
        'Frozen saved artifacts are compared with the pre-teardown live snapshot and an independent private PDF export.',
        'Saved-state regressions: saved-version-review.json. Sampling misses transient changes and does not prove causation.',
        'Wall time, GUI/CLI counts, token usage and action overlap: concurrency.json and native request/action logs.',
        'Single runs are not success-rate estimates. No 1/2-agent model trials were requested or scheduled.'])
    (root / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'credentials', 'out', 'freehand-runtime', 'codex-binary'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--harness', choices=('codex', 'freehand'), required=True)
    parser.add_argument('--image', default=IMAGE)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(argv)
    args.pair, args.task_roles, args.task_waves, args.mode = PAIR, 'abcd', ['abcd'], 'parallel'
    args.coagent_hint, args.interaction_mode, args.image_history_limit = True, 'hybrid', 4
    args.codex_permissions = 'container-unrestricted' if args.harness == 'codex' else 'reviewed'
    args.max_actions, args.max_turns, args.timeout = (10, 12, 360) if args.smoke else (300, 90, 1500)
    native.interaction_rules = lambda mode: rules()
    native.report = report
    collector.Desktop = WriterDesktop
    collector.evaluate = grade_workspace
    collector.APPS[PAIR] = ('LibreOffice Writer', '', '')
    return native.run(args)


if __name__ == '__main__':
    raise SystemExit(main())
