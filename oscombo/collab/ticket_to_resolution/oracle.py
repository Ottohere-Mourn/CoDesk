"""Hidden-state oracle for business state, review provenance, and integrity."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import spec
from .database import (business_snapshot, business_state_digest, connect,
                       processor_check_digest, review_digest)


def _epoch(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


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
        processor_checks = _asdicts(conn, "SELECT * FROM processor_checks WHERE ticket_id=? ORDER BY version", (spec.TICKET_ID,))
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

    latest_processor_check = processor_checks[-1] if processor_checks else None
    processor_check_exact = False
    processor_check_integrity = False
    if latest_processor_check:
        try:
            processor_check_integrity = (
                processor_check_digest(latest_processor_check) == latest_processor_check["content_sha256"]
            )
        except (KeyError, ValueError, TypeError):
            processor_check_integrity = False
        processor_check_exact = (
            latest_processor_check["ticket_id"] == spec.TICKET_ID
            and latest_processor_check["order_id"] == spec.ORDER_ID
            and int(latest_processor_check["order_revision"]) == int(initial_order["revision"] if initial_order else -1)
            and latest_processor_check["decision"] == "ELIGIBLE"
            and latest_processor_check["line_id"] == spec.TARGET_LINE_ID
            and latest_processor_check["evidence_id"] == spec.TARGET_EVIDENCE_ID
            and int(latest_processor_check["shipping_cents"]) == 0
            and int(latest_processor_check["refund_cents"]) == spec.TARGET_REVIEW_AMOUNT_CENTS
            and latest_processor_check["actor_id"] == "B"
        )
    processor_precheck_pass = (condition == "single_agent" or
                               bool(latest_processor_check and processor_check_integrity and processor_check_exact))

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
    processor_check_event = next((e for e in audit if e["event_type"] == "processor_precheck_saved"
                                  and latest_processor_check and e["target_id"] == latest_processor_check["id"]), None)
    processor_check_audit_pass = False
    if processor_check_event and latest_processor_check:
        try:
            check_details = json.loads(processor_check_event["details_json"])
            processor_check_audit_pass = (
                processor_check_event["actor_id"] == "B"
                and processor_check_event["sequence"] > 0
                and check_details.get("content_sha256") == latest_processor_check["content_sha256"]
                and check_details.get("version") == int(latest_processor_check["version"])
                and check_details.get("refund_cents") == int(latest_processor_check["refund_cents"])
                and check_details.get("line_id") == latest_processor_check["line_id"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    review_open_events = [e for e in audit if e["event_type"] == "case_review_gui_opened"
                          and e["actor_id"] == "B"]
    opened_latest_review = next((e for e in review_open_events if latest_valid_review
                                 and e["target_id"] == latest_valid_review["id"]), None)
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
                              and resolution_audit_payload_pass
                              and (condition == "single_agent" or processor_check_audit_pass))
    sequence_pass = bool(review_event and len(refund_events) == 1 and len(resolved_events) == 1
                         and review_event["sequence"] < refund_events[0]["sequence"]
                         < resolved_events[0]["sequence"])
    expected_review_actor_ok = bool(latest_valid_review and latest_valid_review["actor_id"] == expected_review_actor)
    expected_refund_actor_ok = bool(refund and refund["actor_id"] == expected_processor_actor)
    joint = all((review_pass, refund_pass, cross_reference_pass, order_pass, ticket_pass,
                 processor_precheck_pass, sequence_pass, audit_payload_pass, protected_rows_ok))

    audit_types = [e["event_type"] for e in audit]
    retries = audit_types.count("refund_idempotent_replay")
    rejected = [e for e in audit if e["event_type"].endswith("_rejected")]
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
    review_reads_by_b = [e for e in audit if e["event_type"] == "case_review_gui_opened"
                         and e["actor_id"] == "B"]
    collaboration_reads_path = Path(manifest_path).resolve().parent.parent / "collaboration_reads.jsonl"
    collaboration_reads = []
    if collaboration_reads_path.is_file():
        for raw in collaboration_reads_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(raw)
                if event.get("reader") == "B":
                    collaboration_reads.append(event)
            except json.JSONDecodeError:
                pass
    b_read_ids = {message_id for event in collaboration_reads for message_id in event.get("message_ids", [])}
    review_id = latest_valid_review["id"] if latest_valid_review else None
    matching_messages = [e for e in message_events if e.get("actor") == "A"
                         and e.get("recipient") in {"B", "all"} and review_id
                         and review_id in str(e.get("body", ""))]
    handoff_message = next((e for e in matching_messages if e.get("message_id") in b_read_ids), None)
    handoff_read = next((event for event in collaboration_reads if handoff_message
                         and handoff_message.get("message_id") in event.get("message_ids", [])), None)
    review_open_event = next((e for e in review_reads_by_b if review_id and e["target_id"] == review_id), None)
    resolved_event = resolved_events[0] if len(resolved_events) == 1 else None
    timeline = {
        "A_review_saved": review_event.get("timestamp") if review_event else None,
        "B_precheck_saved": processor_check_event.get("timestamp") if processor_check_event else None,
        "A_message_sent_with_review_id": handoff_message.get("timestamp") if handoff_message else None,
        "B_message_read": handoff_read.get("time_unix") if handoff_read else None,
        "B_gui_opened_review": review_open_event.get("timestamp") if review_open_event else None,
        "B_refund_issued": refund_events[0].get("timestamp") if len(refund_events) == 1 else None,
        "B_ticket_resolved": resolved_event.get("timestamp") if resolved_event else None,
    }
    review_saved_at = _epoch(timeline["A_review_saved"])
    check_saved_at = _epoch(timeline["B_precheck_saved"])
    message_sent_at = _epoch(timeline["A_message_sent_with_review_id"])
    message_read_at = _epoch(timeline["B_message_read"])
    gui_open_at = _epoch(timeline["B_gui_opened_review"])
    refund_at = _epoch(timeline["B_refund_issued"])
    resolved_at = _epoch(timeline["B_ticket_resolved"])
    strict_handoff_order = bool(
        condition == "single_agent" or (
            review_id and processor_precheck_pass and processor_check_audit_pass and handoff_message and handoff_read
            and review_open_event and review_open_event["target_id"] == review_id and refund
            and refund["review_id"] == review_id and all(value is not None for value in
                (review_saved_at, check_saved_at, message_sent_at, message_read_at, gui_open_at, refund_at, resolved_at))
            and review_saved_at <= message_sent_at <= message_read_at <= gui_open_at <= refund_at <= resolved_at
            and check_saved_at <= message_read_at and check_saved_at <= gui_open_at
        )
    )
    review_revision_count = max((int(r["version"]) for r in reviews), default=0)
    return {
        "case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
        "condition": condition,
        "review_pass": review_pass,
        "refund_pass": refund_pass,
        "order_state_pass": order_pass,
        "ticket_state_pass": ticket_pass,
        "cross_reference_pass": cross_reference_pass,
        "processor_precheck_pass": processor_precheck_pass,
        "audit_sequence_pass": sequence_pass,
        "audit_payload_pass": audit_payload_pass,
        "protected_state_pass": protected_rows_ok,
        "joint_business_success": joint,
        "observed": {
            "review_count": len(reviews), "review_version_count": review_revision_count,
            "processor_precheck_count": len(processor_checks),
            "processor_precheck_version_count": int(latest_processor_check["version"]) if latest_processor_check else 0,
            "refund_count": len(refunds),
            "refund_transaction_id": refund["id"] if refund else None,
            "refund_amount_cents": refund["amount_cents"] if refund else None,
            "ticket_status": ticket["status"] if ticket else None,
            "order_status": order["status"] if order else None,
            "order_remaining_cents": order["remaining_cents"] if order else None,
            "review_author_role_ok": expected_review_actor_ok,
            # Unlike review_author_role_ok, this records authorship even when
            # the latest review is intentionally invalid (negative controls).
            "review_recorded_by_expected_actor": bool(
                latest_review and latest_review["actor_id"] == expected_review_actor),
            "refund_actor_role_ok": expected_refund_actor_ok,
        },
        "process_evidence": {
            "page_view_event_count": len(read_events), "message_count": len(message_events),
            "messages_by_actor": {actor: sum(e.get("actor") == actor for e in message_events)
                                  for actor in ("A", "B", "S")},
            "review_opened_in_gui_by_B": bool(review_reads_by_b),
            "review_opened_review_id_by_B": review_open_event["target_id"] if review_open_event else None,
            "processor_precheck_recorded_by_expected_actor": bool(latest_processor_check and latest_processor_check["actor_id"] == "B"),
            "idempotent_retry_count": retries, "rejected_operation_count": len(rejected),
            "rejected_operations": rejected,
            "review_was_used": bool(cross_reference_pass),
            "handoff_timeline": timeline,
            "strict_handoff_timeline_pass": strict_handoff_order,
            "A_handoff_included_review_id": handoff_message is not None,
            "B_read_handoff_message": handoff_read is not None,
            "precheck_saved_before_B_read": bool(check_saved_at and message_read_at and check_saved_at <= message_read_at),
            "B_opened_same_review_as_handoff_and_refund": bool(review_open_event and refund
                and review_open_event["target_id"] == refund["review_id"]),
            "message_feedback_observed": bool(message_events),
            "review_revision_evidence": review_revision_count > 1,
        },
        "checks": {"fixture_manifest_integrity": baseline_integrity,
                   "transaction_id_deterministic_for_run_and_idempotency_key": refund is not None,
                   "review_audit_payload_pass": review_audit_payload_pass,
                   "refund_audit_payload_pass": refund_audit_payload_pass,
                   "resolution_audit_payload_pass": resolution_audit_payload_pass,
                   "processor_precheck_integrity_pass": processor_check_integrity,
                   "processor_precheck_exact_case_pass": processor_check_exact,
                   "processor_precheck_audit_payload_pass": processor_check_audit_pass,
                   "review_opened_id_matches_latest_review": bool(review_open_event and latest_valid_review
                       and review_open_event["target_id"] == latest_valid_review["id"]),
                   "gold_line_present": line is not None,
                   "gold_damage_evidence_present": damage is not None},
    }
