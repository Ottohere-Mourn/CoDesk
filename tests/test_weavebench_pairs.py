import json

import pytest

from experiments.weavebench_pairs import PAIRS, merge_inputs, pair_rules, section
from experiments.weavebench_judge import DIMENSIONS, safe_copy_tree, stage_evidence, validate_score
from experiments.weavebench_batch import plan


def test_balanced_plan_has_both_orders_and_harnesses():
    jobs = plan()
    assert len(jobs) == 12
    assert len({job['id'] for job in jobs}) == 12
    for pair in PAIRS:
        for harness in ('codex', 'freehand'):
            assert {job['condition'] for job in jobs if job['pair'] == pair and job['harness'] == harness} == {
                'parallel_shared', 'sequential_ab', 'sequential_ba'}


def test_prompt_extraction_excludes_answers():
    text = "---\nid: task\n---\n## Prompt\nOriginal instructions\n### Subheading\nMore\n\n## Expected Behavior\nSECRET\n"
    assert section(text, "Prompt") == "Original instructions\n### Subheading\nMore"
    with pytest.raises(ValueError):
        section(text, "Warmup")


def test_colliding_inputs_fail_without_overwriting(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file").write_text("new")
    (target / "file").write_text("existing")
    with pytest.raises(ValueError, match="collision"):
        merge_inputs(source, target)
    assert (target / "file").read_text() == "existing"


def test_input_symlinks_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "escape").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="symlink"):
        merge_inputs(source, tmp_path / "target")


def test_evidence_copy_does_not_follow_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "escape").symlink_to("/etc/passwd")
    (source / "actual").write_text("evidence")
    target = tmp_path / "target"
    safe_copy_tree(source, target)
    assert not (target / "escape").exists()
    assert (target / "actual").read_text() == "evidence"


def test_rules_allow_separate_official_documents_and_hybrid():
    rules = pair_rules("hybrid")
    assert "separate official documents" in rules
    assert "Do not start a private desktop" in rules
    assert "/tmp_workspace is an alias" in rules
    assert "APIs" in rules
    with pytest.raises(ValueError):
        pair_rules("gui-only")


def valid_score():
    return {"is_hack": False, "final_score": .6,
        "dimensions": {key: {"score": .6} for key in DIMENSIONS},
        "artifact_checks": [{"clause_results": [{"satisfied": True, "evidence": "file"}]}]}


def test_upstream_score_formula_is_validated_not_replaced():
    value = valid_score()
    assert validate_score(value) == .6
    value["final_score"] = .99
    with pytest.raises(ValueError, match="formula"):
        validate_score(value)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -1, 1.1, True])
def test_invalid_judge_scores_rejected(number):
    value = valid_score()
    value["dimensions"]["task_completion"]["score"] = number
    with pytest.raises(ValueError):
        validate_score(value)


def test_hack_verdict_requires_quoted_evidence():
    value = valid_score()
    value.update(is_hack=True, final_score=0)
    with pytest.raises(ValueError, match="quoted"):
        validate_score(value)
    value["hack_evidence_quotes"] = ["actual offending command"]
    assert validate_score(value) == 0


def test_evidence_staging_keeps_both_roles_and_common_snapshot(tmp_path):
    run, dataset = tmp_path / "run", tmp_path / "dataset"
    workspace = run / "shared/workspace/results"
    workspace.mkdir(parents=True)
    (workspace / "final.txt").write_text("common final state")
    (run / "manifest.json").write_text(json.dumps({"tasks": ["wvinka", "wvinkb"]}))
    for role in "ab":
        agent = run / ("wvink" + role)
        agent.mkdir()
        (agent / "actions.jsonl").write_text(json.dumps({"action": role}) + "\n")
        private = dataset / "private" / PAIRS["wvink"]["tasks"]["ab".index(role)]
        private.mkdir(parents=True)
        (private / "original.md").write_text("original " + role)
    target = tmp_path / "evidence"
    stage_evidence(run, dataset, "a", target)
    lines = [json.loads(line) for line in (target / "chat.jsonl").read_text().splitlines()]
    assert {line["agent_role"] for line in lines} == {"a", "b"}
    assert all(line["own_task"] == (line["agent_role"] == "a") for line in lines)
    assert (target / "results/final.txt").read_text() == "common final state"
    assert (target / "task.md").read_text() == "original a"
