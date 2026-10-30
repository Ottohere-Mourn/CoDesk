from __future__ import annotations

import json
import sqlite3
import threading
import urllib.parse
import urllib.request

import pytest

from oscombo.collab.data_to_deck.collab_tools import CollaborationClient
from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server as make_collab_server
from oscombo.collab.ticket_to_resolution import spec
from oscombo.collab.ticket_to_resolution.database import (
    BusinessRuleError,
    CaseStore,
    business_snapshot,
    create_database,
)
from oscombo.collab.ticket_to_resolution.integration import (
    codex_collaboration_binding,
    condition_actor_ids,
)
from oscombo.collab.ticket_to_resolution.oracle import evaluate
from oscombo.collab.ticket_to_resolution.runner import (
    hidden_manifest_path,
    make_plan,
    prepare_run,
    reset_owned_run,
)
from oscombo.collab.ticket_to_resolution.webapp import make_server as make_web_server, parse_money


def _prepare(root, run_id="ttr-test"):
    result = prepare_run(root, run_id)
    return result, CaseStore(result["database"])


def _review(store: CaseStore, actor="A", **overrides):
    fields = {
        "ticket_id": spec.TICKET_ID,
        "order_id": spec.ORDER_ID,
        "order_revision": 1,
        "decision": "ELIGIBLE",
        "line_id": spec.TARGET_LINE_ID,
        "evidence_id": spec.TARGET_EVIDENCE_ID,
        "policy_id": spec.POLICY_ID,
        "principal_cents": 8000,
        "tax_cents": 800,
        "shipping_cents": 0,
        "refund_cents": 8800,
        "rationale": "The delivery evidence matches the dock line; policy permits line price plus tax, not shipping.",
    }
    fields.update(overrides)
    return store.save_review(actor, fields)


def _refund(store: CaseStore, review, *, actor="B", key=None, **overrides):
    request = {
        "ticket_id": spec.TICKET_ID,
        "order_id": spec.ORDER_ID,
        "review_id": review["id"],
        "line_id": spec.TARGET_LINE_ID,
        "principal_cents": 8000,
        "tax_cents": 800,
        "shipping_cents": 0,
        "amount_cents": 8800,
        "idempotency_key": key or spec.IDEMPOTENCY_KEY,
    }
    request.update(overrides)
    return store.issue_refund(actor, **request)


def _finish(store: CaseStore, review, *, actor="B"):
    refund = _refund(store, review, actor=actor)
    store.resolve_ticket(actor, ticket_id=spec.TICKET_ID, refund_id=refund["id"],
                         resolution_code=spec.EXPECTED_RESOLUTION_CODE,
                         notes="Verified damaged dock partial refund and customer notification.")
    return refund


def _oracle(root, condition="collaborative_shared"):
    return evaluate(root / "db" / spec.FIXTURE_DB, hidden_manifest_path(root), condition)


def test_fixture_is_deterministic_and_has_negative_controls(tmp_path):
    first = tmp_path / "one.sqlite3"
    second = tmp_path / "two.sqlite3"
    m1 = create_database(first, "one")
    m2 = create_database(second, "two")
    assert m1["business_state_sha256"] == m2["business_state_sha256"]
    assert first.stat().st_mode & 0o777 == 0o600
    state = business_snapshot(first)
    assert {r["id"] for r in state["tickets"]} >= {"T-1042", "T-1043", "T-1044"}
    assert {r["id"] for r in state["orders"]} >= {"O-2048", "O-2049", "O-2050"}
    assert state["tickets"][0]["status"] == "OPEN"
    with sqlite3.connect(first) as conn:
        assert conn.execute("select count(*) from reviews").fetchone()[0] == 0
        assert conn.execute("select count(*) from refunds").fetchone()[0] == 0


def test_positive_transaction_and_oracle_and_recovery_after_refund(tmp_path):
    result, store = _prepare(tmp_path / "episode")
    review = _review(store)
    valid, message = store.validate_review(review["id"])
    assert valid, message
    store.record_view("B", "/reviews/current", review["id"])
    refund = _refund(store, review)
    assert refund["amount_cents"] == 8800
    assert refund["id"].startswith("RF-")
    mid = _oracle(tmp_path / "episode")
    assert mid["refund_pass"]
    assert not mid["ticket_state_pass"]
    assert not mid["joint_business_success"]
    # Resolution can recover independently; it must not issue another refund.
    store.resolve_ticket("B", ticket_id=spec.TICKET_ID, refund_id=refund["id"],
                         resolution_code=spec.EXPECTED_RESOLUTION_CODE, notes="Resolved after transaction check.")
    result = _oracle(tmp_path / "episode")
    assert result["joint_business_success"]
    assert result["process_evidence"]["review_was_used"]
    assert result["process_evidence"]["review_opened_in_gui_by_B"]
    assert result["audit_payload_pass"]
    assert result["observed"]["refund_count"] == 1
    assert result["observed"]["order_remaining_cents"] == 14700


def test_single_agent_can_complete_same_business_workflow_with_combined_role(tmp_path):
    root = tmp_path / "single"
    _, store = _prepare(root)
    review = _review(store, actor="S")
    _finish(store, review, actor="S")
    result = _oracle(root, "single_agent")
    assert result["joint_business_success"]
    assert result["observed"]["review_author_role_ok"]
    assert result["observed"]["refund_actor_role_ok"]


def test_corrected_review_is_latest_transaction_basis_and_revision_evidence(tmp_path):
    root = tmp_path / "revised"
    _, store = _prepare(root)
    _review(store, refund_cents=9500)
    corrected = _review(store)
    assert corrected["version"] == 2
    _finish(store, corrected)
    result = _oracle(root)
    assert result["joint_business_success"]
    assert result["observed"]["review_count"] == 2
    assert result["process_evidence"]["review_revision_evidence"]


@pytest.mark.parametrize("amounts", [
    (8000, 0, 0, 8000),       # $80, omitted line tax
    (8000, 1500, 0, 9500),    # $95, unsupported extra tax
    (22000, 1500, 0, 23500),  # $235, whole order
])
def test_wrong_refund_amounts_are_rejected_and_not_success(tmp_path, amounts):
    root = tmp_path / ("bad-" + str(amounts[0]) + "-" + str(amounts[-1]))
    _, store = _prepare(root)
    review = _review(store)
    with pytest.raises(BusinessRuleError):
        _refund(store, review, principal_cents=amounts[0], tax_cents=amounts[1],
                shipping_cents=amounts[2], amount_cents=amounts[3])
    with sqlite3.connect(root / "db" / spec.FIXTURE_DB) as conn:
        assert conn.execute("select count(*) from refunds").fetchone()[0] == 0
    score = _oracle(root)
    assert not score["refund_pass"]
    assert not score["joint_business_success"]
    assert score["process_evidence"]["rejected_operation_count"] == 1


def test_wrong_line_duplicate_refund_and_idempotent_replay(tmp_path):
    root = tmp_path / "episode"
    _, store = _prepare(root)
    review = _review(store)
    refund = _refund(store, review)
    replay = _refund(store, review)
    assert replay["id"] == refund["id"]
    assert store.get_order()["remaining_cents"] == 14700
    with pytest.raises(BusinessRuleError, match="already been refunded"):
        _refund(store, review, key="different-refund-key")
    assert store.get_order()["remaining_cents"] == 14700
    assert sum(e["event_type"] == "refund_issued" for e in store.list_audit()) == 1
    assert sum(e["event_type"] == "refund_idempotent_replay" for e in store.list_audit()) == 1


def test_missing_expired_tampered_and_superseded_review_are_rejected(tmp_path):
    root = tmp_path / "episode"
    _, store = _prepare(root)
    with pytest.raises(BusinessRuleError) as missing:
        _refund(store, {"id": "missing"})
    assert missing.value.code == "CASE_NOT_READY"

    review = _review(store)
    with sqlite3.connect(root / "db" / spec.FIXTURE_DB) as conn:
        conn.execute("update orders set revision=revision+1 where id=?", (spec.ORDER_ID,))
    with pytest.raises(BusinessRuleError):
        _refund(store, review)

    root2 = tmp_path / "tampered"
    _, store2 = _prepare(root2)
    review2 = _review(store2)
    with sqlite3.connect(root2 / "db" / spec.FIXTURE_DB) as conn:
        conn.execute("update reviews set refund_cents=9500 where id=?", (review2["id"],))
    with pytest.raises(BusinessRuleError):
        _refund(store2, review2)

    root3 = tmp_path / "superseded"
    _, store3 = _prepare(root3)
    old = _review(store3)
    _review(store3, shipping_cents=1500, refund_cents=10300)
    with pytest.raises(BusinessRuleError):
        _refund(store3, old)


def test_rejects_review_refund_mismatch_and_wrong_resolution_code(tmp_path):
    root = tmp_path / "episode"
    _, store = _prepare(root)
    review = _review(store)
    with pytest.raises(BusinessRuleError):
        _refund(store, review, line_id="O-2048-L1")
    refund = _refund(store, review)
    with pytest.raises(BusinessRuleError):
        store.resolve_ticket("B", ticket_id=spec.TICKET_ID, refund_id=refund["id"],
                             resolution_code="FULL_REFUND", notes="wrong code")
    assert store.get_ticket()["status"] == "REFUND_PENDING"
    store.resolve_ticket("B", ticket_id=spec.TICKET_ID, refund_id=refund["id"],
                         resolution_code=spec.EXPECTED_RESOLUTION_CODE, notes="fixed code")
    score = _oracle(root)
    assert score["joint_business_success"]
    assert score["process_evidence"]["rejected_operation_count"] == 2


def test_oracle_detects_corrupted_terminal_state_and_non_target_pollution(tmp_path):
    root = tmp_path / "episode"
    _, store = _prepare(root)
    review = _review(store)
    _finish(store, review)
    with sqlite3.connect(root / "db" / spec.FIXTURE_DB) as conn:
        conn.execute("update orders set status='PAID',remaining_cents=15500 where id='O-2048'")
        conn.execute("update tickets set resolution_code='FULL_REFUND' where id='T-1042'")
        conn.execute("update tickets set status='RESOLVED' where id='T-1043'")
        conn.execute("update customers set display_name='polluted' where id='C-552'")
    score = _oracle(root)
    assert not score["order_state_pass"]
    assert not score["ticket_state_pass"]
    assert not score["protected_state_pass"]
    assert not score["joint_business_success"]


def test_oracle_rejects_wrong_transaction_id_even_if_linked_from_ticket(tmp_path):
    root = tmp_path / "episode"
    _, store = _prepare(root)
    review = _review(store)
    refund = _finish(store, review)
    with sqlite3.connect(root / "db" / spec.FIXTURE_DB) as conn:
        conn.execute("update refunds set id='RF-WRONG-ID' where id=?", (refund["id"],))
        conn.execute("update tickets set refund_id='RF-WRONG-ID' where id='T-1042'")
    score = _oracle(root)
    assert not score["refund_pass"]
    assert not score["cross_reference_pass"]
    assert not score["joint_business_success"]


def test_audit_is_append_only_and_records_rejections(tmp_path):
    _, store = _prepare(tmp_path / "episode")
    with pytest.raises(BusinessRuleError):
        store.save_review("B", {})
    with pytest.raises(BusinessRuleError) as forbidden:
        _refund(store, {"id": "forbidden"}, actor="A")
    assert forbidden.value.code == "ROLE_FORBIDDEN"
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("delete from audit_events")
    assert [e["event_type"] for e in store.list_audit()] == ["case_review_rejected", "refund_rejected"]


def test_reset_ownership_restores_business_state_and_preserves_snapshot(tmp_path):
    root = tmp_path / "episode"
    prepared, store = _prepare(root, "reset-run")
    initial_hash = prepared["business_state_sha256"]
    review = _review(store)
    _finish(store, review)
    result = reset_owned_run(root, "reset-run")
    assert result["business_state_sha256"] == initial_hash
    assert (root / "db" / spec.FIXTURE_DB).stat().st_mode & 0o777 == 0o600
    assert hidden_manifest_path(root).stat().st_mode & 0o777 == 0o600
    assert business_state_digest_for_test(business_snapshot(root / "db" / spec.FIXTURE_DB)) == initial_hash
    assert len(list((root / "pre_reset").glob("case-before-reset-*.sqlite3"))) == 1
    assert not store.list_audit()


def business_state_digest_for_test(snapshot):
    from oscombo.collab.ticket_to_resolution.database import business_state_digest
    return business_state_digest(snapshot)


def test_condition_topology_and_codex_collaboration_binding(tmp_path):
    root = tmp_path / "episode"
    prepare_run(root, "topology-run")
    plans = {c: make_plan(c, "topology-run") for c in spec.CONDITIONS}
    assert plans["single_agent"]["guest_count"] == 1
    assert plans["collaborative_isolated"]["guest_count"] == 2
    assert plans["collaborative_shared"]["guest_count"] == 1
    assert len({p["backend_topology"] for p in plans.values()}) == 1
    assert condition_actor_ids("single_agent") == ("S",)
    assert condition_actor_ids("collaborative_shared") == ("A", "B")
    opts, env = codex_collaboration_binding(root, "B", "http://127.0.0.1:4123")
    assert opts["collaboration"] == {"actor": "B", "url": "http://127.0.0.1:4123",
                                     "token_env": "CODESK_TTR_B_COLLAB_TOKEN"}
    assert env["CODESK_TTR_B_COLLAB_TOKEN"]


def test_existing_message_and_attachment_protocol_is_exposed_bidirectionally(tmp_path):
    root = tmp_path / "episode"
    prepared = prepare_run(root, "protocol-run")
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text())
    store = ProtocolStore(root / "collaboration", "protocol-run")
    server = make_collab_server(store, tokens)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        a = CollaborationClient(base, "A", tokens["A"])
        b = CollaborationClient(base, "B", tokens["B"])
        attachment = a.send_attachment("review.txt", b"Verified line L2; 80.00 + 8.00 tax = 88.00")
        sent = a.send_message("B", "Please check the saved Review values and cited rule.",
                              [attachment["attachment_id"]])
        assert b.read_messages()[0]["message_id"] == sent["message_id"]
        assert b.read_attachment(attachment["attachment_id"])["content"].startswith("Verified line")
        reply = b.send_message("A", "Confirmed the review against the order evidence.")
        assert a.read_messages()[0]["message_id"] == reply["message_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_readiness_login_and_review_visibility(tmp_path):
    root = tmp_path / "episode"
    prepared, store = _prepare(root)
    review = _review(store)
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text())
    server = make_web_server(prepared["database"], credentials)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/health") as response:
            assert json.loads(response.read())["ready"] is True
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        login = urllib.parse.urlencode({"actor": "B", "password": credentials["B"]}).encode()
        opener.open(urllib.request.Request(base + "/login", data=login, method="POST"))
        with opener.open(base + f"/reviews/{review['id']}") as response:
            html = response.read().decode()
        assert "Current and consistent" in html
        assert "$80.00 / $8.00 / $0.00" in html
        assert "Order revision" in html
        assert any(e["actor_id"] == "B" and e["target_id"] == f"/reviews/{review['id']}"
                   for e in store.list_audit())
    finally:
        server.shutdown()
        server.server_close()
        server.access_log.close()
        thread.join(timeout=2)


@pytest.mark.parametrize(("text", "cents"), [("88.00", 8800), ("80", 8000), ("95.00", 9500), ("235.00", 23500)])
def test_money_parser_uses_integer_cents(text, cents):
    assert parse_money(text) == cents


def test_money_parser_rejects_subcent_and_negative_amounts():
    with pytest.raises(BusinessRuleError):
        parse_money("88.001")
    with pytest.raises(BusinessRuleError):
        parse_money("-1.00")


def test_guest_smoke_resource_block_does_not_start_guest(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import oscombo.collab.ticket_to_resolution.guest_smoke as smoke

    root = tmp_path / "blocked-run"
    prepare_run(root, "blocked-run-1")
    cfg = make_plan("collaborative_shared", "blocked-run-1")
    (root / "run_config.json").write_text(json.dumps(cfg))
    monkeypatch.setattr(smoke, "_resource_preflight", lambda *_: {
        "ready": False, "checks": {"kvm_read_write": False, "cpu_psi_avg10_below_10_percent": False}})
    args = SimpleNamespace(run_root=root, run_id="blocked-run-1",
                           base_image=tmp_path / "missing.qcow2", provider=tmp_path / "provider",
                           runtime_image="not-started")
    result = smoke.run_guest_smoke(args)
    assert result["status"] == "BLOCKED_RESOURCE"
    assert result["gates"]["gate_1_guest_web_readiness"] == "BLOCKED_RESOURCE"
    assert not (root / "provenance.json").exists()
    assert not (root / "overlay").exists()


def test_oracle_reports_expected_author_for_an_intentionally_invalid_review(tmp_path):
    root = tmp_path / "invalid-review-author"
    _, store = _prepare(root)
    review = _review(store, refund_cents=8000)
    assert review["actor_id"] == "A"
    result = _oracle(root)
    assert not result["review_pass"]
    assert result["observed"]["review_count"] == 1
    assert result["observed"]["review_author_role_ok"] is False
    assert result["observed"]["review_recorded_by_expected_actor"] is True
