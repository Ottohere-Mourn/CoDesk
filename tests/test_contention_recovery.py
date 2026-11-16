import json

from experiments.recover_contention import main_finished, recovery_jobs


def test_recovery_waits_until_all_main_workers_have_ended():
    assert not main_finished({"total": 2, "finished": 1, "active": [], "jobs": []})
    assert not main_finished({"total": 2, "finished": 2, "active": ["last"], "jobs": []})
    assert not main_finished({"total": 2, "finished": 2, "active": [], "jobs": [{"status": "running"}]})
    assert main_finished({"total": 2, "finished": 2, "active": [],
                          "jobs": [{"status": "finished"}, {"status": "error"}]})


def test_recovery_selects_bootstrap_failure_and_keeps_genuine_zero(tmp_path):
    jobs = [{"name": "startup"}, {"name": "model_zero"}]
    for job in jobs:
        directory = tmp_path / "runs" / job["name"]
        directory.mkdir(parents=True)
        agent = {"status": "error", "error": "upload failed"} if job["name"] == "startup" else {
            "status": "done", "model_requests": 5, "model_responses": 5}
        (directory / "result.json").write_text(json.dumps({"scores": {"a": 0, "b": 0}, "agents": {"agentA": agent}}))
    assert [job["name"] for job in recovery_jobs(tmp_path, jobs)] == ["startup"]
