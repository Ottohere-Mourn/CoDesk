import json
from pathlib import Path
import sys
import threading
import time

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "infra"))
import run_ticket_to_resolution_lite_model as model_runner  # noqa: E402


def _run_artifacts(root: Path) -> None:
    (root / "db").mkdir(parents=True)
    (root / "model_relays" / "S").mkdir(parents=True)
    (root / "db" / "case.sqlite3").write_bytes(b"seed")
    (root / "db" / "case.http.jsonl").write_text("", encoding="utf-8")
    (root / "desktop_requests.jsonl").write_text("", encoding="utf-8")
    (root / "model_relays" / "S" / "events.jsonl").write_text("", encoding="utf-8")


def test_quiescence_waits_for_a_late_case_post(tmp_path: Path):
    _run_artifacts(tmp_path)

    def finish_post() -> None:
        with (tmp_path / "db" / "case.http.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps({"method": "POST", "path": "/lite/reviews/save", "status": 303}) + "\n")
        (tmp_path / "db" / "case.sqlite3").write_bytes(b"seed+saved-review")

    timer = threading.Timer(0.04, finish_post)
    timer.start()
    started = time.monotonic()
    result = model_runner.wait_for_actor_side_effects(
        tmp_path, ("S",), minimum_wait_s=0.0, quiet_s=0.08, timeout_s=1.0)
    timer.join()

    assert result["settled"] is True
    assert result["completed_write_requests"] == 1
    assert time.monotonic() - started >= 0.10


def test_quiescence_times_out_if_write_requests_never_settle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _run_artifacts(tmp_path)
    # A growing POST count simulates ongoing mutating activity.
    reads = 0
    def changing_post_count(_path):
        nonlocal reads
        reads += 1
        return [{"method": "POST"}] * reads


    monkeypatch.setattr(model_runner, "read_jsonl", changing_post_count)
    result = model_runner.wait_for_actor_side_effects(
        tmp_path, ("S",), minimum_wait_s=0.0, quiet_s=0.04, timeout_s=0.12)
    assert result["settled"] is False
