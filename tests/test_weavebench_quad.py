import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from experiments.professional_native import execute_waves, task_schedule
from experiments.weavebench_quad import BINDINGS, PAIR, activity_levels, prepare_dataset, rules, wave_roles
from experiments.weavebench_quad_batch import plan
from experiments.weavebench_judge import stage_evidence


@pytest.mark.parametrize('width,expected', [(1, ['a', 'b', 'c', 'd']), (2, ['ab', 'cd']), (4, ['abcd'])])
def test_wave_schedule(width, expected):
    assert wave_roles(width) == expected
    assert task_schedule(SimpleNamespace(task_roles='abcd', task_waves=expected, mode='parallel')) == ('abcd', expected)


@pytest.mark.parametrize('roles', ['', 'aa', 'abcde', 'x', ['a', 'b']])
def test_bad_roles_rejected(roles):
    with pytest.raises(ValueError):
        task_schedule(SimpleNamespace(task_roles=roles, mode='parallel'))


@pytest.mark.parametrize('waves', [[], [''], ['abc'], ['ab', 'bc'], ['cd', 'ab']])
def test_bad_waves_rejected(waves):
    with pytest.raises(ValueError):
        task_schedule(SimpleNamespace(task_roles='abcd', task_waves=waves, mode='parallel'))


def test_legacy_pair_order_retained():
    assert task_schedule(SimpleNamespace(task_roles='ba', mode='sequential')) == ('ba', ['b', 'a'])
    assert task_schedule(SimpleNamespace(task_roles='ab', mode='parallel')) == ('ab', ['ab'])


@pytest.mark.parametrize('width', [1, 2, 4])
def test_real_concurrency_and_wave_completion(width):
    lock = threading.Lock()
    active = set()
    peak = 0
    events = []
    def execute(task, barrier):
        nonlocal peak
        barrier.wait(timeout=3)
        with lock:
            active.add(task)
            peak = max(peak, len(active))
            events.append(('start', task))
        time.sleep(.04)
        with lock:
            active.remove(task)
            events.append(('end', task))
        return task
    tasks = [PAIR + role for role in BINDINGS]
    assert execute_waves(tasks, wave_roles(width), execute) == tasks
    assert peak == width
    if width == 2:
        assert max(events.index(('end', task)) for task in tasks[:2]) < min(events.index(('start', task)) for task in tasks[2:])


def test_activity_counts_distinct_agents_not_duplicate_requests():
    result = activity_levels([('a', 0, 10), ('a', 2, 8), ('b', 1, 9), ('c', 3, 7), ('d', 4, 6)])
    assert result['peak_distinct_agents'] == 4
    assert result['seconds_at_exactly_n_agents'][4] == 2
    assert sum(result['seconds_at_exactly_n_agents'].values()) == 10


def test_balanced_fixed_workload_plan():
    jobs = plan()
    assert len(jobs) == 6
    assert {job['harness'] for job in jobs[:2]} == {'codex', 'freehand'}
    assert all(job['concurrency'] == 4 for job in jobs[:2])
    for harness in ('codex', 'freehand'):
        assert {job['concurrency'] for job in jobs if job['harness'] == harness} == {1, 2, 4}


def make_frozen(root):
    (root / 'private').mkdir(parents=True)
    (root / 'provenance.json').write_text('{}')
    for pair in ('wvink', 'wvwriter'):
        directory = root / 'dataset/pairs' / pair
        (directory / 'inputs/results').mkdir(parents=True)
        (directory / 'inputs/README.md').write_text('original-' + pair)
        (directory / ('inputs/' + pair + '.data')).write_text('pristine-' + pair)
        for role in 'ab':
            (directory / ('task_' + role + '.md')).write_text('prompt-' + pair + role)


def test_input_merge_only_renames_colliding_readmes(tmp_path):
    source, target = tmp_path / 'old', tmp_path / 'new'
    make_frozen(source)
    prepare_dataset(source, target)
    inputs = target / 'dataset/pairs/wvquad/inputs'
    for pair in ('wvink', 'wvwriter'):
        assert (inputs / 'task_readmes' / pair / 'README.md').read_text() == 'original-' + pair
        assert (inputs / (pair + '.data')).read_text() == 'pristine-' + pair
    for role, binding in BINDINGS.items():
        assert (target / 'dataset/pairs/wvquad' / ('task_' + role + '.md')).read_text() == 'prompt-' + binding['origin_pair'] + binding['origin_role']
    assert json.loads((target / 'provenance.json').read_text())['prompt_adaptations'] == []
    assert not (inputs / 'gt').exists()


def test_previous_outputs_cannot_enter_new_inputs(tmp_path):
    source = tmp_path / 'old'
    make_frozen(source)
    (source / 'dataset/pairs/wvink/inputs/results/answer.txt').write_text('not an input')
    with pytest.raises(ValueError, match='pristine'):
        prepare_dataset(source, tmp_path / 'new')


def test_prompt_grounded_judge_includes_all_four_traces_without_hidden_ban(tmp_path):
    root, dataset = tmp_path / 'run', tmp_path / 'dataset'
    (root / 'shared/workspace/results').mkdir(parents=True)
    (root / 'shared/workspace/results/report.odt').write_text('artifact')
    (root / 'manifest.json').write_text(json.dumps({'tasks': [PAIR + role for role in BINDINGS],
        'task_bindings': BINDINGS, 'judge_policy': 'agent-visible-hybrid-v2'}))
    for role, binding in BINDINGS.items():
        folder = root / (PAIR + role)
        folder.mkdir()
        (folder / 'actions.jsonl').write_text(json.dumps({'role': role}) + '\n')
        private = dataset / 'private' / binding['task_id']
        private.mkdir(parents=True)
        (private / 'original.md').write_text('## Prompt\nUse the app to fix the document.\n## Grading Criteria\nHIDDEN_UNO_BAN\n')
    target = tmp_path / 'evidence'
    task = stage_evidence(root, dataset, 'd', target)
    assert task == BINDINGS['d']['task_id']
    assert 'HIDDEN_UNO_BAN' not in (target / 'task.md').read_text()
    rows = [json.loads(line) for line in (target / 'chat.jsonl').read_text().splitlines()]
    assert {row['agent_role'] for row in rows} == set('abcd')
    assert all(row['own_task'] == (row['agent_role'] == 'd') for row in rows)
    assert json.loads((target / 'adaptation.json').read_text())['judge_policy'] == 'agent-visible-hybrid-v2'


def test_rules_preserve_hybrid_without_private_desktops():
    for width in (1, 2, 4):
        prompt = rules(width)
        assert f'At most {width}' in prompt
        assert 'ONE desktop' in prompt and 'NO cross-agent input lock' in prompt
        assert 'application APIs, XML and shell utilities are allowed' in prompt
