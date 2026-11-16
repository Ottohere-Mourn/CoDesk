"""Import the thirteen-case handoff without merging unrelated source branches or starting models."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET


SOURCES = {
    'handoff': ('codex/13-case-handoff-20261104', '1549126399c0be41b6bbc34d1b9b611381591b04'),
    'case2': ('codex/case2-v12', '953d68418e35864e176c8b5c54f3bd497c60b7d3'),
    'case3': ('codex/case3-followup', 'c6bcb56d9bd65bc37891d58a7f9e7d991349eaf2'),
    'case4': ('codex/case4-hardening', '3462672b50b73d08183528ba2148304b83438a89'),
    'mechanisms': ('codex/focus-clipboard-pilot-20261102', 'c866975460faa24db38c4722fafc8c6ddc367963'),
    'hybrid_dependency_candidate': ('codex/case2-healthcare', 'b5745cd5bfbc15e645301b1118ae43299740050b'),
}
CASES = [
    ('case2', '双人商品工单核验与退款', 'case2', 'infra/run_ticket_to_resolution_lite_healthcare.py', False, 'neutral_success_control'),
    ('case3', 'VS Code修复与浏览器重测', 'case3', 'infra/run_case3_lite_pair_pilot.py', True, 'single_triplet_only'),
    ('case4', 'Kdenlive时间线与清单交付', 'case4', 'infra/run_case4_lite_pair_pilot.py', False, 'lock_arm_passed'),
    ('F-01', '焦点与输入路由', 'mechanisms', 'scripts/run_f01_hybrid_v2_retest.py', False, 'shared_arm_recovered'),
    ('C-03', '共享剪贴板覆盖', 'mechanisms', 'scripts/run_c03_hybrid_v2_retest.py', True, 'single_triplet_only'),
    ('A-01', '浏览器活动标签页', 'mechanisms', 'scripts/run_a01_hybrid_v2_retest.py', True, 'single_triplet_only'),
    ('S-01', 'Calc活动单元格与选区', 'mechanisms', 'scripts/run_calc_hybrid_v2_retest.py', True, 'single_triplet_only'),
    ('U-01', '共享撤销栈', 'mechanisms', 'scripts/run_calc_hybrid_v2_retest.py', True, 'single_triplet_only'),
    ('CWD-1', '持久终端当前工作目录', 'mechanisms', 'scripts/run_sol_cwd_bundle_v2.py', True, 'single_triplet_only'),
    ('EDIT-1', 'Writer插入与覆盖模式', 'mechanisms', 'scripts/run_edit_overwrite_hybrid_v2_retest.py', False, 'lock_arm_recovered'),
    ('VIEW-1', '滚动后陈旧屏幕坐标', 'mechanisms', 'scripts/run_viewport_scroll_hybrid_v2.py', False, 'lock_pass_and_weak_attribution'),
    ('FIND-1', '查找替换Match Case持久状态', 'mechanisms', 'scripts/run_find_replace_hybrid_v2.py', False, 'prompt_conflict_requires_revision'),
    ('AUTH-1', '浏览器会话身份变化', 'mechanisms', None, False, 'design_only_no_model_runner'),
]
TESTS = {
    'case2': ['tests/test_ticket_to_resolution_lite.py', 'tests/test_ticket_to_resolution_lite_model_runner.py',
        'tests/test_ticket_to_resolution_lite_native_diagnostics.py'],
    'case3': ['tests/test_build_and_verify_lite_v1.py'],
    'case4': ['tests/test_timeline_and_assets_lite.py'],
    'mechanisms': ['tests/test_workflows_v1.py', 'tests/test_browser_context_workflow_v1.py',
        'tests/test_cwd_bundle_oracle_v1.py', 'tests/test_cwd_bundle_schedule_v1.py',
        'tests/test_cwd_bundle_materialize_v1.py', 'tests/test_probe_writer_insert_overwrite_v1.py',
        'tests/test_writer_calc_evaluator.py', 'tests/test_clipboard_observer.py', 'tests/test_resource_safety.py'],
}


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes(root):
    return {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob('*'))
        if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts}


def export_source(repo, revision, target):
    if target.exists():
        raise FileExistsError(target)
    archive = subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', revision],
        check=True, capture_output=True).stdout
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe source archive path')
        source.extractall(target, filter='data')


def inspect_runner(path):
    text = path.read_text()
    tree = ast.parse(text)
    assignments = {}
    hybrid_imports = []
    script_dependencies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('MODEL', 'ROOT', 'HYBRID', 'OSWORLD', 'IMAGE', 'MCP_PYTHON', 'CODEX_BIN'):
                    assignments[target.id] = ast.get_source_segment(text, node.value)
        if isinstance(node, ast.ImportFrom) and node.module and 'hybrid_v2' in node.module:
            hybrid_imports.append(node.module)
        if isinstance(node, ast.ImportFrom) and node.module == 'scripts':
            script_dependencies.extend(alias.name for alias in node.names)
    return {'syntax_valid': True, 'sha256': digest(path), 'runtime_constants': assignments,
        'hybrid_imports': hybrid_imports, 'script_dependencies': script_dependencies}


def catalog(root):
    sources = root / 'sources'
    hybrid_locations = [str(path.relative_to(root)) for path in sources.glob('*/oscombo/harness/hybrid_v2.py')]
    rows = []
    for identifier, title, source, runner, achieved, prior_status in CASES:
        path = sources / source / runner if runner else None
        inspection = inspect_runner(path) if path and path.is_file() else None
        blockers = ['execution_protocol_not_selected', 'guest_runtime_not_deployed', 'freehand_adapter_not_present']
        if runner is None:
            blockers.append('design_only_no_runner')
        elif inspection is None:
            blockers.append('runner_missing')
        elif inspection['hybrid_imports'] and not hybrid_locations:
            blockers.append('oscombo.harness.hybrid_v2_missing_from_all_supplied_sources')
        if inspection:
            inspection['missing_script_dependencies'] = [name for name in inspection['script_dependencies']
                if not (sources / source / 'scripts' / (name + '.py')).exists()]
            if inspection['missing_script_dependencies']:
                blockers.append('upstream_script_dependencies_not_committed')
        if identifier == 'FIND-1':
            blockers.append('known_contradictory_role_prompts_require_fix_and_new_baseline')
        rows.append({'id': identifier, 'title': title, 'source': source, 'source_revision': SOURCES[source][1],
            'runner': runner, 'runner_inspection': inspection, 'original_roles': ['A', 'B'],
            'original_conditions': ['isolated', 'shared', 'shared_per_action_lock'],
            'historical_goal_triplet_once': achieved, 'historical_status': prior_status,
            'new_model_run_status': 'not_started', 'new_model_score': None, 'blockers': blockers})
    return {'version': 1, 'source_handoff_revision': SOURCES['handoff'][1], 'case_count': len(rows),
        'historical_single_triplet_achievers': sum(row['historical_goal_triplet_once'] for row in rows),
        'historical_results_are_new_results': False, 'model_rollouts': 0, 'cases': rows,
        'hybrid_dependency_locations': hybrid_locations,
        'execution_scope': 'Imported definitions and offline tests only; no automatic original or adapted model runs.',
        'protocol_decision': 'Original two-role three-arm studies vs current four-role writable-CLI natural concurrency must be explicit.'}


def offline_tests(root, python, output_name='offline-tests'):
    output = root / output_name
    output.mkdir(exist_ok=False)
    owner = {'project': 'codesk-13case-import', 'run_id': root.name, 'owner_token': uuid.uuid4().hex}
    save(output / 'ownership.json', owner)
    ledger = output / 'resource-events.jsonl'
    results = {}
    for name, files in TESTS.items():
        directory = output / name
        directory.mkdir()
        with ledger.open('a') as stream:
            stream.write(json.dumps({**owner, 'event': 'create', 'kind': 'temporary_test_root',
                'path': str(directory), 'timestamp': time.time()}) + '\n')
        source = root / 'sources' / name
        command = [str(python), '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            '--basetemp', str(directory / 'temporary'), '--junitxml', str(directory / 'junit.xml'), *files]
        env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1',
            PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OPENAI_API_KEY='', SWCUB_SOL_API_KEY='',
            OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
        with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
            try:
                completed = subprocess.run(command, cwd=source, env=env, stdout=stdout, stderr=stderr, timeout=180)
                status = 'passed' if completed.returncode == 0 else 'failed_or_collection_error'
                result = {'status': status, 'exit_code': completed.returncode, 'command': command}
            except subprocess.TimeoutExpired:
                result = {'status': 'timeout', 'command': command}
        junit = directory / 'junit.xml'
        if junit.exists():
            tree = ET.parse(junit)
            suites = list(tree.getroot().iter('testsuite'))
            result['counts'] = {key: sum(int(suite.get(key, '0')) for suite in suites)
                for key in ('tests', 'failures', 'errors', 'skipped')}
        results[name] = result
        save(output / 'summary.json', {'model_rollouts': 0, 'guest_runs': 0, 'groups': results})
        print(json.dumps({name: result}, ensure_ascii=False), flush=True)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--offline-tests', action='store_true')
    args = parser.parse_args(argv)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    provenance = {'created_at': time.time(), 'sources': {}}
    for name, (branch, revision) in SOURCES.items():
        target = args.out / 'sources' / name
        export_source(args.repo, revision, target)
        provenance['sources'][name] = {'branch': branch, 'commit': revision, 'files': source_hashes(target)}
    save(args.out / 'provenance.json', provenance)
    report = catalog(args.out)
    save(args.out / 'catalog.json', report)
    if args.offline_tests:
        report['offline_tests'] = offline_tests(args.out, args.python.absolute())
        report['frozen_sources_unchanged'] = all(source_hashes(args.out / 'sources' / name) == entry['files']
            for name, entry in provenance['sources'].items())
        if not report['frozen_sources_unchanged']:
            raise RuntimeError('Offline tests modified a frozen source snapshot')
        save(args.out / 'catalog.json', report)
    print(json.dumps({'out': str(args.out), 'cases': len(report['cases']), 'model_rollouts': 0}), flush=True)


if __name__ == '__main__':
    main()
