from pathlib import Path

import pytest

from experiments.codesk_case_handoff import CASES, SOURCES, catalog, export_source, inspect_runner


def test_thirteen_cases_and_six_historical_single_triplets():
    assert len(CASES) == len({row[0] for row in CASES}) == 13
    assert sum(row[4] for row in CASES) == 6
    assert len([row for row in CASES if row[3]]) == 12
    assert all(len(revision) == 40 for _, revision in SOURCES.values())


def test_unavailable_runtime_and_design_only_are_not_model_failures(tmp_path):
    report = catalog(tmp_path)
    assert report['model_rollouts'] == 0
    assert all(row['new_model_score'] is None for row in report['cases'])
    assert all(row['new_model_run_status'] == 'not_started' for row in report['cases'])
    auth = next(row for row in report['cases'] if row['id'] == 'AUTH-1')
    assert 'design_only_no_runner' in auth['blockers']
    find = next(row for row in report['cases'] if row['id'] == 'FIND-1')
    assert 'known_contradictory_role_prompts_require_fix_and_new_baseline' in find['blockers']


def test_inspection_does_not_import_or_execute_a_runner(tmp_path):
    marker = tmp_path / 'must-not-exist'
    runner = tmp_path / 'runner.py'
    runner.write_text('from oscombo.harness.hybrid_v2 import MCP_PYTHON\n'
        'MODEL = "gpt-6-sol"\n'
        f'open({str(marker)!r}, "w").write("executed")\n')
    result = inspect_runner(runner)
    assert result['hybrid_imports'] == ['oscombo.harness.hybrid_v2']
    assert result['runtime_constants']['MODEL'] == '"gpt-6-sol"'
    assert not marker.exists()


def test_missing_helper_scripts_are_reported_without_hiding_hybrid_dependency(tmp_path):
    root = tmp_path / 'sources/mechanisms/scripts'
    root.mkdir(parents=True)
    (root / 'run_c03_hybrid_v2_retest.py').write_text(
        'from scripts import run_workflows_qwen_v1 as old\nfrom oscombo.harness.hybrid_v2 import MCP_PYTHON\n')
    report = catalog(tmp_path)
    case = next(row for row in report['cases'] if row['id'] == 'C-03')
    assert case['runner_inspection']['missing_script_dependencies'] == ['run_workflows_qwen_v1']
    assert 'upstream_script_dependencies_not_committed' in case['blockers']
    assert 'oscombo.harness.hybrid_v2_missing_from_all_supplied_sources' in case['blockers']


def test_archive_refuses_existing_destination(tmp_path):
    with pytest.raises(FileExistsError):
        export_source(Path('/unused'), 'not-used', tmp_path)
