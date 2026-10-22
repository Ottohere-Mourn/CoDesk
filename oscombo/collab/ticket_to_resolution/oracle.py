"""Hidden-state oracle for business state, review provenance, and integrity."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from . import spec
from .database import business_snapshot, business_state_digest, connect, review_digest


def _asdicts(conn, query: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, args)]


def evaluate(db_path: str | Path, manifest_path: str | Path,
             condition: str = "collaborative_shared") -> dict[str, Any]:
    """Evaluate the final database independently of frontend success messages.

    Invalid operation attempts are retained as process evidence. They do not
    fail a later corrected final state; callers should report them separately.
    """
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    baseline = manifest.get("business_state")
    baseline_integrity = (
        manifest.get("case_id") == spec.CASE_ID
        and manifest.get("case_version") == spec.CASE_VERSION
        and manifest.get("business_state_sha256") == business_state_digest(baseline)
    )
    actual = business_snapshot(db_path)
    conn = connect(db_path)
    try:
        ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (spec.TICKET_ID,)).fetchone()
        order = conn.execute("SELECT * FROM orders WHERE id=?", (spec.ORDER_ID,)).fetchone()
        lines = _asdicts(conn, "SELECT * FROM order_lines WHERE order_id=? ORDER BY id", (spec.ORDER_ID,))
        reviews = _asdicts(conn, "SELECT * FROM reviews WHERE ticket_id=? ORDER BY version", (spec.TICKET_ID,))
        refunds = _asdicts(conn, "SELECT * FROM refunds WHERE ticket_id=? ORDER BY created_at,id", (spec.TICKET_ID,))
        audit = _asdicts(conn, "SELECT * FROM audit_events ORDER BY sequence")
    finally:
        conn.close()

    initial = baseline or {}
    initial_ticket = next((row for row in initial.get("tickets", []) if row["id"] == spec.TICKET_ID), None)
    initial_order = next((row for row in initial.get("orders", []) if row["id"] == spec.ORDER_ID), None)
    protected_rows_ok = baseline_integrity
    if baseline_integrity:
        # Customer, product-line, policy, evidence, and every non-target case
        # remain exactly as initialized. Only the designated order/ticket
        # status fields and append-only review/refund/audit tables may change.
        protected_rows_ok = all(actual.get(table) == initial.get(table) for table in
                                ("customers", "order_lines", "policies", "evidence"))
        for table, target_id in (("orders", spec.ORDER_ID), ("tickets", spec.TICKET_ID)):
            expected_rows = initial.get(table, [])
            actual_rows = actual.get(table, [])
            expected_non_target = [r for r in expected_rows if r["id"] != target_id]
            actual_non_target = [r for r in actual_rows if r["id"] != target_id]
            protected_rows_ok &= expected_non_target == actual_non_target
        target_line_snapshot = [r for r in initial.get("order_lines", []) if r["order_id"] == spec.ORDER_ID]
        protected_rows_ok &= lines == target_line_snapshot
        if initial_ticket and ticket:
            for field in ("id", "customer_id", "order_id", "issue_code", "subject", "body", "created_at"):
                protected_rows_ok &= ticket[field] == initial_ticket[field]
        else:
            protected_rows_ok = False
        if initial_order and order:
            for field in ("id", "customer_id", "total_cents", "placed_at", "delivered_at"):
                protected_rows_ok &= order[field] == initial_order[field]
        else:
            protected_rows_ok = False

    line = next((r for r in lines if r["id"] == spec.TARGET_LINE_ID), None)
    damage = next((r for r in initial.get("evidence", []) if r["id"] == spec.TARGET_EVIDENCE_ID), None)
    valid_reviews: list[dict[str, Any]] = []
    for review in reviews:
        try:
            integrity = review_digest(review) == review["content_sha256"]
        except (KeyError, ValueError, TypeError):
            integrity = False
        exact = (
            review["ticket_id"] == spec.TICKET_ID and review["order_id"] == spec.ORDER_ID
            and int(review["order_revision"]) == int(initial_order["revision"] if initial_order else -1)
            and review["decision"] == "ELIGIBLE" and review["line_id"] == spec.TARGET_LINE_ID
            and review["evidence_id"] == spec.TARGET_EVIDENCE_ID and review["policy_id"] == spec.POLICY_ID
            and int(review["principal_cents"]) == spec.TARGET_PRINCIPAL_CENTS
            and int(review["tax_cents"]) == spec.TARGET_TAX_CENTS
            and int(review["shipping_cents"]) == 0
            and int(review["refund_cents"]) == spec.TARGET_REVIEW_AMOUNT_CENTS
            and bool(review["rationale"].strip())
        )
        if integrity and exact and damage and line:
            valid_reviews.append(review)
    latest_review = max(reviews, key=lambda r: int(r["version"])) if reviews else None
    # A previous valid review is not sufficient once a newer version exists.
    latest_valid_review = next((r for r in valid_reviews
                                if latest_review and r["id"] == latest_review["id"]), None)

    expected_review_actor = "A" if condition != "single_agent" else "S"
    expected_processor_actor = "B" if condition != "single_agent" else "S"
    review_pass = bool(latest_valid_review and latest_valid_review["actor_id"] == expected_review_actor)
    expected_transaction_id = None
    try:
        db = connect(db_path)
        try:
            metadata_row = db.execute("SELECT value FROM metadata WHERE key='run_id'").fetchone()
            run_id = metadata_row["value"] if metadata_row else None
        finally:
            db.close()
        if run_id:
            expected_transaction_id = "RF-" + hashlib.sha256(
                f"{run_id}:{spec.IDEMPOTENCY_KEY}".encode()).hexdigest()[:16].upper()
    except Exception:
        expected_transaction_id = None
    exact_refunds = [r for r in refunds if (
        r["status"] == "SUCCEEDED" and r["order_id"] == spec.ORDER_ID
        and r["line_id"] == spec.TARGET_LINE_ID
        and int(r["principal_cents"]) == spec.TARGET_PRINCIPAL_CENTS
        and int(r["tax_cents"]) == spec.TARGET_TAX_CENTS
        and int(r["shipping_cents"]) == 0
        and int(r["amount_cents"]) == spec.TARGET_REVIEW_AMOUNT_CENTS
        and r["idempotency_key"] == spec.IDEMPOTENCY_KEY
        and r["id"] == expected_transaction_id
    )]
    refund = exact_refunds[0] if len(exact_refunds) == 1 else None
    refund_pass = bool(refund and len(refunds) == 1 and refund["actor_id"] == expected_processor_actor)
    cross_reference_pass = bool(
        refund and latest_valid_review
        and refund["review_id"] == latest_valid_review["id"]
        and refund["ticket_id"] == spec.TICKET_ID
    )
    order_pass = bool(order and order["status"] == "PARTIALLY_REFUNDED"
                      and int(order["remaining_cents"]) == spec.POST_REFUND_BALANCE_CENTS
                      and int(order["revision"]) == 2)
    ticket_pass = bool(ticket and ticket["status"] == "RESOLVED"
                        and ticket["resolution_code"] == spec.EXPECTED_RESOLUTION_CODE
                        and ticket["refund_id"] == (refund["id"] if refund else None)
                        and bool((ticket["resolution_notes"] or "").strip()))

    review_event = next((e for e in audit if e["event_type"] == "case_review_saved"
                         and latest_valid_review and e["target_id"] == latest_valid_review["id"]), None)
    refund_events = [e for e in audit if e["event_type"] == "refund_issued"
                     and refund and e["target_id"] == refund["id"]]
    resolved_events = [e for e in audit if e["event_type"] == "ticket_resolved"
                       and e["target_id"] == spec.TICKET_ID]
    review_audit_payload_pass = False
    refund_audit_payload_pass = False
    resolution_audit_payload_pass = False
    try:
        if review_event and latest_valid_review:
            review_details = json.loads(review_event["details_json"])
            review_audit_payload_pass = (
                review_event["actor_id"] == expected_review_actor
                and review_details.get("order_revision") == int(latest_valid_review["order_revision"])
                and review_details.get("content_sha256") == latest_valid_review["content_sha256"]
                and review_details.get("version") == int(latest_valid_review["version"]))
        if len(refund_events) == 1 and refund:
            refund_details = json.loads(refund_events[0]["details_json"])
            refund_audit_payload_pass = (
                refund_events[0]["actor_id"] == expected_processor_actor
                and refund_details.get("review_id") == refund["review_id"]
                and refund_details.get("line_id") == refund["line_id"]
                and refund_details.get("amount_cents") == int(refund["amount_cents"])
                and refund_details.get("idempotency_key") == spec.IDEMPOTENCY_KEY
                and refund_details.get("review_content_sha256") == latest_valid_review["content_sha256"]
                and refund_details.get("review_order_revision") == int(latest_valid_review["order_revision"]))
        if len(resolved_events) == 1 and refund:
            resolution_details = json.loads(resolved_events[0]["details_json"])
            resolution_audit_payload_pass = (
                resolved_events[0]["actor_id"] == expected_processor_actor
                and resolution_details.get("refund_id") == refund["id"]
                and resolution_details.get("resolution_code") == spec.EXPECTED_RESOLUTION_CODE)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    audit_payload_pass = bool(review_audit_payload_pass and refund_audit_payload_pass
                              and resolution_audit_payload_pass)
    sequence_pass = bool(review_event and len(refund_events) == 1 and len(resolved_events) == 1
                         and review_event["sequence"] < refund_events[0]["sequence"]
                         < resolved_events[0]["sequence"])
    expected_review_actor_ok = bool(latest_valid_review and latest_valid_review["actor_id"] == expected_review_actor)
    expected_refund_actor_ok = bool(refund and refund["actor_id"] == expected_processor_actor)
    joint = all((review_pass, refund_pass, cross_reference_pass, order_pass, ticket_pass,
                 sequence_pass, audit_payload_pass, protected_rows_ok))

    audit_types = [e["event_type"] for e in audit]
    retries = audit_types.count("refund_idempotent_replay")
    rejected = [e for e in audit if e["event_type"] in {"refund_rejected", "ticket_resolution_rejected"}]
    read_events = [e for e in audit if e["event_type"] == "page_view"]
    messages_path = Path(manifest_path).resolve().parent.parent / "collaboration" / "events.jsonl"
    message_events = []
    if messages_path.is_file():
        for raw in messages_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(raw)
                if event.get("type") == "message":
                    message_events.append(event)
            except json.JSONDecodeError:
                pass
    review_reads_by_b = [e for e in read_events if e["actor_id"] == "B"
                         and e["target_id"].startswith("/reviews/")]
    review_revision_count = max((int(r["version"]) for r in reviews), default=0)
    return {
        "case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
        "condition": condition,
        "review_pass": review_pass,
        "refund_pass": refund_pass,
        "order_state_pass": order_pass,
        "ticket_state_pass": ticket_pass,
        "cross_reference_pass": cross_reference_pass,
        "audit_sequence_pass": sequence_pass,
        "audit_payload_pass": audit_payload_pass,
        "protected_state_pass": protected_rows_ok,
        "joint_business_success": joint,
        "observed": {
            "review_count": len(reviews), "review_version_count": review_revision_count,
            "refund_count": len(refunds),
            "refund_transaction_id": refund["id"] if refund else None,
            "refund_amount_cents": refund["amount_cents"] if refund else None,
            "ticket_status": ticket["status"] if ticket else None,
            "order_status": order["status"] if order else None,
            "order_remaining_cents": order["remaining_cents"] if order else None,
            "review_author_role_ok": expected_review_actor_ok,
            "refund_actor_role_ok": expected_refund_actor_ok,
        },
        "process_evidence": {
            "page_view_event_count": len(read_events), "message_count": len(message_events),
            "messages_by_actor": {actor: sum(e.get("actor") == actor for e in message_events)
                                  for actor in ("A", "B", "S")},
            "review_opened_in_gui_by_B": bool(review_reads_by_b),
            "idempotent_retry_count": retries, "rejected_operation_count": len(rejected),
            "rejected_operations": rejected,
            "review_was_used": bool(cross_reference_pass),
            "message_feedback_observed": bool(message_events),
            "review_revision_evidence": review_revision_count > 1,
        },
        "checks": {"fixture_manifest_integrity": baseline_integrity,
                   "transaction_id_deterministic_for_run_and_idempotency_key": refund is not None,
                   "review_audit_payload_pass": review_audit_payload_pass,
                   "refund_audit_payload_pass": refund_audit_payload_pass,
                   "resolution_audit_payload_pass": resolution_audit_payload_pass,
                   "gold_line_present": line is not None,
                   "gold_damage_evidence_present": damage is not None},
    }
