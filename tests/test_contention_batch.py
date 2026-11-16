import json

from experiments.contention_batch import jobs_for, make_report, trial_summary


def test_each_pair_has_all_four_conditions_without_duplication():
    cases = [{"name": "first"}, {"name": "second"}]
    jobs = jobs_for({"cases": cases})
    assert len({job["name"] for job in jobs}) == 8
    for case in cases:
        assert {(j["harness"], j["mode"]) for j in jobs if j["pair"] == case["name"]} == {
            ("codex", "parallel"), ("codex", "sequential"),
            ("freehand", "parallel"), ("freehand", "sequential")}
    assert jobs[0]["harness"] != jobs[4]["harness"]


def test_missing_score_stays_missing_in_paired_comparison(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"scores": {"a": 1, "b": None},
        "eval_errors": {"b": "download failed"}, "agents": {}}))
    summary = trial_summary(tmp_path)
    assert summary["mean_score"] is None and summary["joint_pass"] is None
    assert summary["valid_scores"] == 1
    assert summary["usage"] is None


def test_real_zero_score_is_counted_and_agent_errors_remain_visible(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"scores": {"a": 1, "b": 0},
        "agents": {"agentB": {"status": "error", "error": "transport failed", "model_requests": 2,
                               "model_responses": 1, "api_errors": [{"status": 500}]}}}))
    summary = trial_summary(tmp_path)
    assert summary["mean_score"] == 0.5 and summary["joint_pass"] is False
    assert summary["api_errors"] == 1 and summary["agent_errors"]


def test_bootstrap_failure_is_not_a_model_zero(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"scores": {"a": 0, "b": 0},
        "agents": {"agentA": {"status": "error", "error": "upload timed out", "steps": 0}}}))
    summary = trial_summary(tmp_path)
    assert summary["mean_score"] is None and not summary["measurement_valid"]
    assert summary["invalid_reason"] == "preparation_error_before_model"
    assert summary["scores"] == {"a": 0, "b": 0}


def test_recovery_is_explicit_and_preserves_original_results(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"model": "gpt-6-astra",
        "cases": [{"name": "one", "resource": "settings.json"}]}))
    jobs = jobs_for(json.loads((tmp_path / "manifest.json").read_text()))
    job = jobs[0]
    job["status"] = "error"
    original = tmp_path / "runs" / job["name"]
    original.mkdir(parents=True)
    raw = json.dumps({"scores": {"a": 0, "b": 0}, "agents": {
        "agentA": {"status": "error", "error": "upload timed out"}}})
    (original / "result.json").write_text(raw)
    recovery = tmp_path / "recoveries" / job["name"]
    recovery.mkdir(parents=True)
    (recovery / "result.json").write_text(json.dumps({"scores": {"a": 1, "b": 1}, "agents": {
        "agentA": {"status": "done", "model_requests": 4},
        "agentB": {"status": "done", "model_requests": 5}}}))
    (tmp_path / "effective_attempts.json").write_text(json.dumps({job["name"]: {
        "directory": str(recovery.relative_to(tmp_path)), "reason": "bootstrap repair"}}))
    report = make_report(tmp_path, jobs)
    assert report["records"][job["name"]]["mean_score"] == 1
    assert report["recovered_conditions"] == 1
    assert report["records"][job["name"]]["original_attempt"]["mean_score"] is None
    assert (original / "result.json").read_text() == raw
