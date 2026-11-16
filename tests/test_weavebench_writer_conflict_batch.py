import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.weavebench_writer_conflict_batch import command_for, plan, verify_validation


def test_exactly_two_trials_with_four_roles_each():
    jobs = plan()
    assert [job['harness'] for job in jobs] == ['freehand', 'codex']
    assert all(job['concurrency'] == 4 and job['waves'] == ['abcd'] for job in jobs)
    assert len(jobs) == 2


def test_full_task_command_not_extra_model_preflight():
    args = SimpleNamespace(dataset=Path('/data/dataset'), credentials=Path('/private/api.json'),
        freehand_runtime=Path('/runtime'), codex_binary=Path('/runtime/codex/codex'), image='frozen-image')
    command = command_for(args, Path('/out/freehand-c4-r1'), 'freehand')
    assert command[command.index('-m') + 1] == 'experiments.weavebench_writer_conflict'
    assert '--smoke' not in command and '--concurrency' not in command
    assert command[command.index('--harness') + 1] == 'freehand'


def test_validation_rejects_changed_source_or_inputs(tmp_path):
    source, dataset = tmp_path / 'source', tmp_path / 'dataset'
    source.mkdir()
    dataset.mkdir()
    (source / 'task.py').write_text('frozen code')
    (dataset / 'report.odt').write_bytes(b'frozen input')
    validation = tmp_path / 'validation.json'
    validation.write_text(json.dumps({'passed': True, 'LLM_rollouts': 0,
        'source_hashes': {'task.py': hashlib.sha256(b'frozen code').hexdigest()},
        'dataset_hashes': {'report.odt': hashlib.sha256(b'frozen input').hexdigest()}}))
    assert verify_validation(dataset, validation, source)['passed']
    (source / 'task.py').write_text('changed')
    with pytest.raises(ValueError, match='source changed'):
        verify_validation(dataset, validation, source)
    (source / 'task.py').write_text('frozen code')
    (dataset / 'report.odt').write_bytes(b'changed')
    with pytest.raises(ValueError, match='dataset changed'):
        verify_validation(dataset, validation, source)
