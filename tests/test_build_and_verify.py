from __future__ import annotations

import http.cookiejar
import json
import shutil
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
from oscombo.collab.build_and_verify import spec
from oscombo.collab.build_and_verify.integration import actor_ids, codex_collaboration_binding
from oscombo.collab.build_and_verify.oracle import evaluate
from oscombo.collab.build_and_verify.runner import (
    configure_run, evaluate_run, make_plan, prepare_run, reset_owned_run,
)
from oscombo.collab.build_and_verify.webapp import make_server as make_app_server


CORRECT_FILTER = '''from __future__ import annotations

def filter_orders(orders, query="", status="All"):
    q = str(query or "").strip().casefold()
    state = str(status or "All")
    return [row for row in orders
            if (state == "All" or row.get("status") == state)
            and (not q or any(q in str(row.get(key, "")).casefold()
                              for key in ("order_id", "customer", "region")))]
'''


def _prepare(root: Path, condition="collaborative_shared"):
    root.mkdir(parents=True, exist_ok=False)
    prepared = prepare_run(root, "bv-test-001")
    configure_run(root, condition, "http://127.0.0.1:8766/")
    return prepared, root / "workspace"


def _apply_correct_fix(workspace: Path):
    (workspace / "filtering.py").write_text(CORRECT_FILTER, encoding="utf-8")
    shutil.copyfile(Path(spec.__file__).parent / "template" / "correct_app.js",
                    workspace / "static" / "app.js")


def _start_app(root: Path):
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text())
    server = make_app_server(root / "workspace", credentials, root / "web_events.jsonl", "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, credentials, f"http://127.0.0.1:{server.server_port}"


def _browser_login(base_url: str, actor: str, password: str):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    data = urllib.parse.urlencode({"actor": actor, "password": password}).encode()
    response = opener.open(urllib.request.Request(base_url + "/login", data=data, method="POST"))
    assert response.status == 200
    return opener


def _browser_test(opener, base_url: str, actor: str, query: str, status: str, method: str):
    params = urllib.parse.urlencode({"query": query, "status": status})
    response = opener.open(base_url + "/api/orders?" + params)
    payload = json.loads(response.read())
    event = json.dumps({"method": method, "query": query, "status": status,
                        "visible_ids": [row["order_id"] for row in payload["orders"]]}).encode()
    request = urllib.request.Request(base_url + "/api/test-events", data=event,
                                     headers={"Content-Type": "application/json"}, method="POST")
    result = json.loads(opener.open(request).read())
    assert result["recorded"]
    return payload


def _record_browser_coverage(root: Path, workspace: Path):
    server, thread, credentials, base_url = _start_app(root)
    try:
        opener = _browser_login(base_url, "B", credentials["B"])
        assert urllib.request.urlopen(base_url + "/health").status == 200
        assert opener.open(base_url + "/").status == 200
        assert len(_browser_test(opener, base_url, "B", "", "Shipped", "button")["orders"]) == 2
        assert _browser_test(opener, base_url, "B", " Dana ", "Processing", "enter")["orders"]
        assert len(_browser_test(opener, base_url, "B", "west", "Processing", "button")["orders"]) == 3
        assert not _browser_test(opener, base_url, "B", "NW-2402", "Processing", "enter")["orders"]
        assert not _browser_test(opener, base_url, "B", "no-such-order", "All", "enter")["orders"]
        assert len(_browser_test(opener, base_url, "B", "", "All", "clear")["orders"]) == 8
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_deterministic_instance_and_equal_condition_backend_topology(tmp_path):
    p1, w1 = _prepare(tmp_path / "one", "single_agent")
    p2, w2 = _prepare(tmp_path / "two", "collaborative_isolated")
    p3, w3 = _prepare(tmp_path / "three", "collaborative_shared")
    hashes = [json.loads((root / "oracle" / "baseline_manifest.json").read_text())["orders_json_sha256"]
              for root in (tmp_path / "one", tmp_path / "two", tmp_path / "three")]
    assert len(set(hashes)) == 1
    plans = [make_plan(name, "same-fixture") for name in spec.CONDITIONS]
    assert len({plan["backend_topology"] for plan in plans}) == 1
    assert len({plan["application_service"] for plan in plans}) == 1
    assert len({json.dumps(plan["workspace"]) for plan in plans}) == 1
    assert [plan["desktop_count"] for plan in plans] == [1, 2, 1]
    assert [plan["budget"]["per_actor_steps"] for plan in plans] == [320, 160, 160]
    assert len({plan["browser_session_policy"] for plan in plans}) == 1
    configured = [json.loads((root / "run_config.json").read_text())
                  for root in (tmp_path / "one", tmp_path / "two", tmp_path / "three")]
    assert len({plan["fixture_sha256"] for plan in configured}) == 1
    assert len({json.dumps(plan["initial_workspace_sha256"], sort_keys=True) for plan in configured}) == 1
    assert actor_ids("single_agent") == ("S",)
    assert actor_ids("collaborative_isolated") == ("A", "B")
    assert (w1 / "filtering.py").read_bytes() == (w2 / "filtering.py").read_bytes() == (w3 / "filtering.py").read_bytes()
    assert json.loads((w1 / spec.DATA_FILE).read_text()) == list(spec.ORDERS)


def test_initial_defect_fails_positive_filter_and_keyboard_oracles(tmp_path):
    root = tmp_path / "episode"
    _, workspace = _prepare(root)
    result = evaluate(root)
    assert not result["checks"]["python_filter_acceptance_pass"]
    assert not result["checks"]["keyboard_ui_contract_pass"]
    assert not result["joint_business_success"]


def test_correct_fix_passes_code_ui_http_browser_retest_and_protected_state(tmp_path):
    root = tmp_path / "episode"
    _, workspace = _prepare(root)
    _apply_correct_fix(workspace)
    _record_browser_coverage(root, workspace)
    result = evaluate_run(root)
    assert result["checks"] == {
        "fixture_integrity_pass": True,
        "protected_files_pass": True,
        "python_filter_acceptance_pass": True,
        "keyboard_ui_contract_pass": True,
        "accessible_filter_markup_pass": True,
        "browser_retest_pass": True,
    }
    assert result["joint_business_success"]
    assert result["message_metrics"]["total_messages"] == 0
    assert result["browser_retest"]["tester_actor"] == "B"
    provenance = json.loads((root / "provenance.json").read_text())
    assert provenance["condition"] == "collaborative_shared"
    assert provenance["guest_gui_action_trace"].startswith("not provided")


def test_wrong_or_logic_and_fixture_tampering_fail_oracle(tmp_path):
    root = tmp_path / "episode"
    _, workspace = _prepare(root)
    (workspace / "filtering.py").write_text(
        'def filter_orders(orders, query="", status="All"):\n'
        ' q=str(query or "").strip().casefold(); s=str(status or "All")\n'
        ' return [r for r in orders if s == "All" or r["status"] == s or q in (r["customer"]+r["region"]+r["order_id"]).casefold()]\n',
        encoding="utf-8")
    (workspace / "data" / "orders.json").write_text("[]\n", encoding="utf-8")
    result = evaluate(root)
    assert not result["checks"]["fixture_integrity_pass"]
    assert not result["checks"]["python_filter_acceptance_pass"]
    assert not result["checks"]["protected_files_pass"]
    assert not result["joint_business_success"]


def test_collaboration_api_bidirectional_attachment_and_actor_binding(tmp_path):
    root = tmp_path / "episode"
    _prepare(root)
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text())
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    server = make_server(ProtocolStore(root / "collaboration", "bv-test-001"), tokens, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        a = CollaborationClient(f"http://127.0.0.1:{server.server_port}", "A", tokens["A"])
        b = CollaborationClient(f"http://127.0.0.1:{server.server_port}", "B", tokens["B"])
        attachment = a.send_attachment("browser-observation.txt", b"NW-2402 incorrectly remained visible under Processing")
        a.send_message("B", "I will check the combined predicate.", [attachment["attachment_id"]])
        assert b.read_messages()[0]["actor"] == "A"
        assert b.read_attachment(attachment["attachment_id"])["content"].startswith("NW-2402")
        b.send_message("A", "Please retest Enter after the predicate fix.")
        assert a.read_messages()[0]["actor"] == "B"
        options, env = codex_collaboration_binding(root, "A", f"http://127.0.0.1:{server.server_port}")
        assert options["collaboration"]["actor"] == "A"
        assert env["CODESK_BV_A_COLLAB_TOKEN"] == tokens["A"]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_reset_archives_old_workspace_events_and_collaboration(tmp_path):
    root = tmp_path / "episode"
    _, workspace = _prepare(root)
    _apply_correct_fix(workspace)
    _record_browser_coverage(root, workspace)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", "bv-test-001").send("A", "B", "fix applied; please retest", [])
    actions = json.loads((root / "oracle" / "baseline_manifest.json").read_text())["initial_files"]
    result = reset_owned_run(root, "bv-test-001")
    assert result["status"] == "RESET_VERIFIED"
    for name, digest in actions.items():
        import hashlib
        assert hashlib.sha256((workspace / name).read_bytes()).hexdigest() == digest
    archive = Path(result["archive"])
    assert (archive / "workspace" / "filtering.py").read_text() == CORRECT_FILTER
    assert (archive / "web_events.jsonl").is_file()
    assert (archive / "collaboration" / "events.jsonl").is_file()
    assert not (root / "web_events.jsonl").read_text()
