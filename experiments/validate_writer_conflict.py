"""Deterministic native Writer feasibility and negative controls; zero LLM calls."""
import argparse
import json
from pathlib import Path
import shutil
import time

from experiments import professional_trajectories as collector
from experiments.weavebench_writer_conflict import IMAGE, SOURCE, WriterDesktop, grade_workspace
from tasks.weavebench_writer_conflict.spec import PAIR


def reference(desktop, statement):
    code = 'import sys,types\n'
    for package in ('tasks', 'tasks.weavebench_writer_conflict'):
        code += f'sys.modules[{package!r}]=types.ModuleType({package!r})\n'
    for name in ('observer', 'spec', 'reference'):
        module = 'tasks.weavebench_writer_conflict.' + name
        source = (SOURCE / 'tasks/weavebench_writer_conflict' / (name + '.py')).read_text()
        code += f'module=types.ModuleType({module!r}); sys.modules[{module!r}]=module; exec({source!r},module.__dict__)\n'
    code += 'from tasks.weavebench_writer_conflict.reference import *\ndocument=get_document()\n' + statement
    result = desktop.raw(['python3', '-c', code], timeout=90, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))


def run_case(root, dataset, roles, image, mutate=None):
    shared = root / 'shared'
    workspace = shared / 'workspace'
    shutil.copytree(dataset / 'dataset/pairs' / PAIR / 'inputs', workspace)
    desktop = WriterDesktop(shared, PAIR, image)
    try:
        desktop.start()
        for role in roles:
            reference(desktop, f'apply_role(document, {role!r}, "/workspace")')
            collector.save(root / ('after-' + role + '.json'), desktop.observe())
        if mutate:
            mutate(desktop, workspace)
    finally:
        desktop.stop()
    grade_workspace(shared, PAIR, dataset, image)
    return json.loads((shared / 'evaluation/grade.json').read_text())


def compact(result):
    return {'success': result['success'], 'scores': {role: row['score'] for role, row in result['roles'].items()},
        'failed': {role: [name for name, passed in row['checks'].items() if not passed] for role, row in result['roles'].items()},
        'joint': result['joint']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image', default=IMAGE)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    protected = [Path(__file__), SOURCE / 'experiments/weavebench_writer_conflict.py',
        *sorted((SOURCE / 'tasks/weavebench_writer_conflict').glob('*.py')),
        *sorted((SOURCE / 'tasks/weavebench_writer_conflict').glob('*.md'))]
    source_hashes = {str(path.relative_to(SOURCE)): collector.hashes(path.parent)[path.name] for path in protected}
    input_hashes = collector.hashes(args.dataset)
    report = {'passed': False, 'LLM_rollouts': 0, 'started_at': time.time(), 'cases': {}, 'negative_controls': {},
        'source_hashes': source_hashes, 'dataset_hashes': input_hashes,
        'image_id': collector.command(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).stdout.strip()}
    collector.save(args.out / 'validation.json', report)
    def record(group, name, result):
        report[group][name] = compact(result)
        collector.save(args.out / 'validation.json', report)
        print(json.dumps({name: compact(result)}), flush=True)
    cases = [('abcd', 'abcd')] if args.probe else [('pristine', ''), ('a_only', 'a'), ('abcd', 'abcd'), ('bcad', 'bcad')]
    for name, roles in cases:
        result = run_case(args.out / name, args.dataset, roles, args.image)
        record('cases', name, result)
        if not args.probe:
            assert result['success'] == (len(roles) == 4), (name, compact(result))
            assert result['roles']['a']['success'] == ('a' in roles), (name, compact(result))
    if args.probe:
        return
    def unsaved(desktop, workspace):
        reference(desktop, 'rename(document,"sec_03","Unsaved divergent title")')
    def stale_toc(desktop, workspace):
        reference(desktop, 'apply_role(document,"b","/workspace")\n'
            'import uno\ndocument.storeToURL(uno.systemPathToFileUrl("/workspace/results/report.pdf"),'
            '(prop("FilterName","writer_pdf_Export"),prop("Overwrite",True)))\nreceipt("/workspace")')
    def stale_pdf(desktop, workspace):
        earlier_pdf = (workspace / 'results/report.pdf').read_bytes()
        reference(desktop, 'apply_role(document,"c","/workspace")\napply_role(document,"d","/workspace")')
        (workspace / 'results/report.pdf').write_bytes(earlier_pdf)
        reference(desktop, 'receipt("/workspace")')
    def stale_overwrite(desktop, workspace):
        shutil.copy2(args.out / 'a_only/shared/workspace/report.odt', workspace / 'report.odt')
    for name, roles, mutate in [('unsaved_live', 'abcd', unsaved), ('stale_toc', 'acd', stale_toc),
            ('stale_pdf_valid_hashes', 'abd', stale_pdf), ('lost_updates', 'abcd', stale_overwrite)]:
        result = run_case(args.out / name, args.dataset, roles, args.image, mutate)
        record('negative_controls', name, result)
        assert not result['success'], name
        if name == 'unsaved_live':
            assert all(row['success'] for row in result['roles'].values()) and not result['joint']['live_saved_agreement']
        elif name == 'stale_toc':
            assert not result['roles']['d']['checks']['final_toc_entries_and_pages']
        elif name == 'stale_pdf_valid_hashes':
            assert result['roles']['d']['checks']['publication_receipt'] and not result['joint']['pdf_matches_native_export']
            assert all(result['roles'][role]['success'] for role in 'abc')
        elif name == 'lost_updates':
            assert not result['roles']['b']['success'] and not result['roles']['c']['success']
    assert input_hashes == collector.hashes(args.dataset)
    assert source_hashes == {str(path.relative_to(SOURCE)): collector.hashes(path.parent)[path.name] for path in protected}
    report.update(passed=True, finished_at=time.time())
    collector.save(args.out / 'validation.json', report)


if __name__ == '__main__':
    main()
