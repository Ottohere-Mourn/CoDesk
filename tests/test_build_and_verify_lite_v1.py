from __future__ import annotations

import http.cookiejar
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from oscombo.collab.build_and_verify_lite_v1 import spec
from oscombo.collab.build_and_verify_lite_v1.oracle import evaluate
from oscombo.collab.build_and_verify_lite_v1.runner import (
    configure_run, make_plan, prepare_run, reset_owned_run,
)
from oscombo.collab.build_and_verify_lite_v1.webapp import make_server


CORRECT_FILTER = '''def filter_orders(orders, query="", status="All"):
    q = str(query or "").strip().casefold()
    s = str(status or "All")
    return [row for row in orders if (s == "All" or row["status"] == s)
            and (not q or any(q in str(row[key]).casefold()
                              for key in ("order_id", "customer", "region")))]
'''


def _prepare(tmp_path: Path, condition: str) -> Path:
    root = tmp_path / condition
    prepare_run(root, condition)
    configure_run(root, condition)
    return root


def _record_http_browser_tests(root: Path, cases) -> None:
    credentials = json.loads((root / "secrets/browser_credentials.json").read_text())
    server = make_server(root / "workspace", credentials, root / "web_events.jsonl", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        login = urllib.parse.urlencode({"actor": "B", "password": credentials["B"]}).encode()
        opener.open(urllib.request.Request(base + "/login", data=login)).read()
        for query, status, method, expected in cases:
            params = urllib.parse.urlencode({"query": query, "status": status})
            rows = json.loads(opener.open(base + "/api/orders?" + params).read())["orders"]
            assert [row["order_id"] for row in rows] == expected
            event = json.dumps({"query": query, "status": status, "method": method,
                                "visible_ids": expected}).encode()
            opener.open(urllib.request.Request(base + "/api/test-events", data=event,
                                               headers={"Content-Type": "application/json"})).read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_same_lite_fixture_and_original_case_separate(tmp_path: Path):
    roots = [_prepare(tmp_path, condition) for condition in spec.CONDITIONS]
    plans = [make_plan(condition, "same-run") for condition in spec.CONDITIONS]
    assert [plan["desktop_count"] for plan in plans] == [1, 2, 1]
    assert len({json.dumps(plan["backend_topology"]) for plan in plans}) == 1
    assert len({(root / "workspace/filtering.py").read_bytes() for root in roots}) == 1
    assert [plan["budget"]["per_actor_steps"] for plan in plans] == [40, 12, 12]
    result = evaluate(roots[1])
    assert result["case_id"] == "CDD-BV-LITE-001"
    assert not result["checks"]["python_filter_acceptance_pass"]
    assert result["checks"]["keyboard_ui_contract_pass"]
    assert not result["joint_business_success"]


def test_bootstrap_login_is_one_time_and_role_scoped(tmp_path: Path):
    root = _prepare(tmp_path, "collaborative_isolated")
    credentials = json.loads((root / "secrets/browser_credentials.json").read_text())
    tickets = json.loads((root / "secrets/browser_bootstrap.json").read_text())
    server = make_server(root / "workspace", credentials, root / "web_events.jsonl",
                         port=0, bootstrap_tickets=tickets)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for actor in ("A", "B"):
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            assert b"Northstar OrderDesk" in opener.open(
                base + "/bootstrap/" + tickets[actor]).read()
            assert b"orders" in opener.open(base + "/api/orders").read()
            with pytest.raises(urllib.error.HTTPError) as replay:
                urllib.request.urlopen(base + "/bootstrap/" + tickets[actor])
            assert replay.value.code == 404
        events = (root / "web_events.jsonl").read_text()
        assert tickets["A"] not in events and tickets["B"] not in events
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_invalid_gui_saved_python_scores_fail_instead_of_crashing(tmp_path: Path):
    root = _prepare(tmp_path, "single_agent")
    (root / "workspace/filtering.py").write_text("def filter_orders(orders):\n  return []\n    x\n")
    result = evaluate(root)
    assert not result["joint_business_success"]
    assert result["python_filter_tests"]["error_type"] == "IndentationError"


def test_all_status_is_unrestricted_in_hidden_acceptance(tmp_path: Path):
    root = _prepare(tmp_path, "single_agent")
    (root / "workspace/filtering.py").write_text(
        CORRECT_FILTER.replace('s == "All"', 's == "ALL"')
    )
    result = evaluate(root)
    assert not result["checks"]["python_filter_acceptance_pass"]
    all_cases = [case for case in result["python_filter_tests"]["cases"]
                 if case["status"] == "All"]
    assert len(all_cases) == 2
    assert all(not case["pass"] for case in all_cases)


@pytest.mark.parametrize("condition", ["collaborative_isolated", "collaborative_shared"])
def test_correct_revision_and_final_browser_retest_pass(tmp_path: Path, condition: str):
    root = _prepare(tmp_path, condition)
    _record_http_browser_tests(root, [("Dana", "Processing", "enter",
                                       ["NW-2402", "NW-2403", "NW-2406"])])
    (root / "workspace/filtering.py").write_text(CORRECT_FILTER)
    _record_http_browser_tests(root, [("NW-2402", "Processing", "button", [])])
    result = evaluate(root)
    assert result["joint_business_success"]
    assert all(result["checks"].values())
    assert result["browser_retest"]["tester_actor"] == "B"
    assert len(result["browser_retest"]["cases"]) == 1
    assert result["browser_baseline_repro"]["pass"]
    reset = reset_owned_run(root, condition)
    assert reset["status"] == "RESET_VERIFIED"
    assert (root / "workspace/filtering.py").read_text() != CORRECT_FILTER


def test_wrong_logic_tamper_and_stale_retest_fail(tmp_path: Path):
    root = _prepare(tmp_path, "collaborative_shared")
    _record_http_browser_tests(root, [("Dana", "Processing", "enter",
                                       ["NW-2402", "NW-2403", "NW-2406"])])
    (root / "workspace/filtering.py").write_text(CORRECT_FILTER)
    _record_http_browser_tests(root, [("NW-2402", "Processing", "button", [])])
    (root / "workspace/filtering.py").write_text(
        'def filter_orders(orders, query="", status="All"):\n'
        ' return [r for r in orders if r["status"] == status or query.casefold() in r["customer"].casefold()]\n')
    stale = evaluate(root)
    assert not stale["checks"]["browser_retest_pass"]
    assert not stale["checks"]["python_filter_acceptance_pass"]
    (root / "workspace/filtering.py").write_text(CORRECT_FILTER)
    (root / "workspace/static/app.js").write_text("// tampered\n")
    tampered = evaluate(root)
    assert not tampered["checks"]["protected_files_pass"]
    assert not tampered["checks"]["keyboard_ui_contract_pass"]
    assert not tampered["joint_business_success"]


def test_final_retest_without_initial_live_reproduction_fails(tmp_path: Path):
    root = _prepare(tmp_path, "collaborative_isolated")
    (root / "workspace/filtering.py").write_text(CORRECT_FILTER)
    _record_http_browser_tests(root, [("NW-2402", "Processing", "button", [])])
    result = evaluate(root)
    assert result["checks"]["browser_retest_pass"]
    assert not result["checks"]["browser_baseline_repro_pass"]
    assert not result["joint_business_success"]
