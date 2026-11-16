"""Stage actual case implementations and fixtures, with an explicit Sol 6.1 model patch."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

from experiments.codesk_case_handoff import CASES, SOURCES, inspect_runner, save, source_hashes


MODEL = 'gpt-6.1-sol'
ROOTS = {'case2': ['oscombo', 'infra', 'tests', 'pyproject.toml'],
    'case3': ['oscombo', 'infra', 'tests', 'pyproject.toml'],
    'case4': ['oscombo', 'infra', 'tests', 'pyproject.toml'],
    'mechanisms': ['swcub', 'scripts', 'tasks', 'tests', 'pyproject.toml', 'AGENTS.md']}
OLD_VERSIONS = {'EDIT-1': '0.4.0-hybrid-v2', 'VIEW-1': '0.2.0-hybrid-v2', 'FIND-1': '0.2.0-hybrid-v2'}


def model_replacement(source):
    tree = ast.parse(source.decode('utf-8'))
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    locations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 'gpt-6-sol':
            locations.append((offsets[node.lineno - 1] + node.col_offset,
                offsets[node.end_lineno - 1] + node.end_col_offset, node.lineno))
    updated = source
    for start, end, line in sorted(locations, reverse=True):
        updated = updated[:start] + repr(MODEL).encode() + updated[end:]
    ast.parse(updated.decode('utf-8'))
    return updated, sorted(line for start, end, line in locations)


def patch_model(path, root):
    original = path.read_bytes()
    updated, lines = model_replacement(original)
    if original == updated:
        return None
    relative = str(path.relative_to(root))
    before, after = original.decode().splitlines(), updated.decode().splitlines()
    patch = '\n'.join(['*** Begin Patch', '*** Update File: ' + relative, '@@',
        *['-' + line for line in before], *['+' + line for line in after], '*** End Patch', ''])
    subprocess.run(['apply_patch'], input=patch, text=True, cwd=root, capture_output=True, check=True)
    return {'file': relative, 'lines': lines, 'old_model': 'gpt-6-sol', 'new_model': MODEL,
        'original_sha256': hashlib.sha256(original).hexdigest(), 'adapted_sha256': hashlib.sha256(updated).hexdigest()}


def stage(repo, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    provenance = {'created_at': time.time(), 'model': MODEL, 'sources': {}, 'model_patches': []}
    for name, roots in ROOTS.items():
        branch, expected = SOURCES[name]
        revision = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'refs/remotes/origin/' + branch],
            capture_output=True, text=True, check=True).stdout.strip()
        if revision != expected:
            raise ValueError('Source branch advanced; inspect its new implementation before staging: ' + branch)
        data = subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', revision, *roots],
            capture_output=True, check=True).stdout
        target = output / 'sources' / name
        target.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(target, filter='data')
        original_hashes = source_hashes(target)
        selected = {runner for identifier, title, source, runner, achieved, previous in CASES if source == name and runner}
        if name == 'mechanisms':
            selected.add('swcub/sol_osworld_agent.py')
        for relative in sorted(selected):
            patch = patch_model(target / relative, output)
            if patch:
                provenance['model_patches'].append(patch)
        provenance['sources'][name] = {'branch': branch, 'revision': revision,
            'included_roots': roots, 'original_hashes': original_hashes, 'adapted_hashes': source_hashes(target)}
    cases = []
    for identifier, title, source, runner, achieved, previous in CASES:
        target = output / 'sources' / source
        path = target / runner if runner else None
        available = bool(path and path.is_file())
        inspection = inspect_runner(path) if available else None
        missing = []
        if inspection:
            missing = [name for name in inspection['script_dependencies'] if not (target / 'scripts' / (name + '.py')).exists()]
        row = {'id': identifier, 'title': title, 'source': source, 'runner': runner,
            'entry_exists': available, 'model': MODEL, 'requested_harness': 'codex',
            'roles': ['A', 'B'], 'conditions': ['isolated', 'shared', 'shared_per_action_lock'],
            'missing_script_dependencies': missing,
            'missing_hybrid_adapter': bool(inspection and inspection['hybrid_imports']),
            'model_episodes_started': 0, 'score': None}
        if identifier in OLD_VERSIONS:
            row.update(available_source_version=OLD_VERSIONS[identifier], newest_reported_implementation_present=False,
                source_status='older_implementation_only')
        elif identifier == 'AUTH-1':
            row.update(source_status='implementation_not_found_in_published_branches',
                newest_reported_implementation_present=False)
        else:
            row['source_status'] = 'entry_present'
        if identifier == 'CWD-1':
            row['harness_migration_required'] = 'Existing SolOSWorldAgent uses Chat Completions; route through Codex/Responses before running Sol 6.1.'
        cases.append(row)
    manifest = {'model': MODEL, 'requested_harness': 'codex', 'cases': cases,
        'source_entries_found': sum(row['entry_exists'] for row in cases),
        'unique_runner_files': len({(row['source'], row['runner']) for row in cases if row['entry_exists']}),
        'model_episodes_started': 0, 'input_permissions_changed': False,
        'topology_changed': False, 'historical_results_imported_as_new_results': False,
        'excluded_roots': ['runs', 'outputs', 'audits', 'docs', 'benchmarks'],
        'notes': ['Source modules, their templates/fixtures, and tests only; no historical result bundle.',
            'Source entries with missing dependencies are not marked runnable.',
            'The model override does not solve missing source files, Guest setup, or harness/transport migration.']}
    save(output / 'source-index.json', manifest)
    save(output / 'source-provenance.json', provenance)
    save(output / 'experiment-config.json', {'model': MODEL, 'reasoning_effort': 'medium', 'harness': 'codex',
        'roles': ['A', 'B'], 'conditions': ['isolated', 'shared', 'shared_per_action_lock'],
        'shared_requires_new_valid_isolated_pass': True, 'budgets': 'retain case-specific original budgets',
        'tool_permissions': 'retain case-specific original permissions', 'model_fallbacks': []})
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.repo, args.out)
    print(json.dumps({key: result[key] for key in ('model', 'source_entries_found', 'unique_runner_files', 'model_episodes_started')}))
