import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAIR = REPO / "tasks" / "paragui"
sys.path.insert(0, str(PAIR))
from build_v1 import build
from pg_v1_oracle import safety_checks, maintenance_checks

def _expected(tmp):
    build(str(tmp))
    return json.loads((tmp / "expected.json").read_text())

def _markers(expected, key):
    category = expected[key]["category"]
    return [{"category": category, "frame_no": item["frame"], "timecode": item["timecode"],
             "note": "Recorded visible issue for follow-up"} for item in expected[key]["frames"]]

def test_jointly_feasible_exact_end_state_scores_both_full(tmp_path):
    expected = _expected(tmp_path)
    state = {"markers": _markers(expected, "safety") + _markers(expected, "maintenance")}
    assert safety_checks(state, expected)[1] == 1.0
    assert maintenance_checks(state, expected)[1] == 1.0

def test_missing_or_wrong_clip_position_fails_only_target_checks(tmp_path):
    expected = _expected(tmp_path)
    safety = _markers(expected, "safety")
    safety[0]["frame_no"] = 3
    safety[0]["timecode"] = "00:24"
    checks, score = safety_checks({"markers": safety}, expected)
    assert checks["frame_2_logged_at_expected_time"] is False
    assert score == 0.75

def test_other_worklist_marker_does_not_satisfy_actor_oracle(tmp_path):
    expected = _expected(tmp_path)
    markers = _markers(expected, "safety")
    for row in markers:
        row["category"] = "Maintenance"
    assert safety_checks({"markers": markers}, expected)[1] == 0.0

def test_unrelated_extra_markers_do_not_block_common_pass(tmp_path):
    expected = _expected(tmp_path)
    markers = _markers(expected, "safety") + _markers(expected, "maintenance")
    markers.append({"category": "Safety follow-up", "frame_no": 1, "timecode": "00:00", "note": "Routine start"})
    assert safety_checks({"markers": markers}, expected)[1] == 1.0
    assert maintenance_checks({"markers": markers}, expected)[1] == 1.0

def test_app_records_shared_visible_playhead_at_submission(tmp_path):
    import socket
    _expected(tmp_path)
    db = tmp_path / "seed.db"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, str(PAIR / "app_v1.py"), "--db", str(db), "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/health", timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        # Actor A views frame 2. Another normal reviewer moves the single browser playhead to frame 3.
        urllib.request.urlopen(base + "/review?frame=2", timeout=3).read()
        urllib.request.urlopen(base + "/review?frame=3", timeout=3).read()
        data = urllib.parse.urlencode({"category":"Safety follow-up","note":"Forklift crosses marked route"}).encode()
        req = urllib.request.Request(base + "/mark", data=data)
        urllib.request.urlopen(req, timeout=3).read()
        con = sqlite3.connect(db)
        row = con.execute("SELECT frame_no,timecode FROM markers ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        assert row == (3, "00:24")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
