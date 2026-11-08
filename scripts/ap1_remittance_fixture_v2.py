"""Offline AP-1 v0.2 remittance workflow contract; no GUI/Guest/model calls."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

CASE_ID = "CODESK-AP-REMITTANCE-001"
TASK_VERSION = "0.2.0-remittance-reconciliation"

SOURCE_DOCS = {
    "RA-221": "Bank remittance advice RA-221 for NORTHWIND-SYN: INV-AP-071, INV-AP-072, INV-AP-073 are in this cycle. INV-AP-074 is excluded pending dispute resolution.",
    "SUPPLIER-STMT-221": "Supplier statement: INV-AP-071 120000 cents; INV-AP-072 30000 cents; INV-AP-073 64000 cents; INV-AP-074 18000 cents.",
    "CN-AP-019": "Approved credit memo CN-AP-019: apply 25000 cents to INV-AP-071 exactly once.",
    "DISPUTE-33": "INV-AP-074 disputed for PRICE_MISMATCH; hold from payment and retain exception reference DISPUTE-33.",
}

def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

SOURCE_HASHES = {key: _sha(value) for key, value in SOURCE_DOCS.items()}

INITIAL = {
    "vendor_id": "NORTHWIND-SYN",
    "cycle_id": "RA-221",
    "source_hashes": deepcopy(SOURCE_HASHES),
    "ledger_revision": 1,
    "ledger": {
        "INV-AP-071": {"open_cents": 120000, "state": "OPEN", "eligibility": "ELIGIBLE"},
        "INV-AP-072": {"open_cents": 30000, "state": "OPEN", "eligibility": "ELIGIBLE"},
        "INV-AP-073": {"open_cents": 64000, "state": "OPEN", "eligibility": "ELIGIBLE"},
        "INV-AP-074": {"open_cents": 18000, "state": "OPEN", "eligibility": "DISPUTE_HOLD"},
    },
    "remittance_advice": {
        "cycle_id": "RA-221",
        "vendor_id": "NORTHWIND-SYN",
        "invoice_ids": ["INV-AP-071", "INV-AP-072", "INV-AP-073"],
        "excluded_invoice_ids": ["INV-AP-074"],
    },
    "credits": {
        "CN-AP-019": {"invoice_id": "INV-AP-071", "amount_cents": 25000,
                      "authorization": "APPROVED", "status": "UNAPPLIED"},
    },
    "payment_draft": {"rows": [], "total_cents": 0, "source_revision": None, "status": "DRAFT"},
    "exceptions": [],
    "external_payment_enabled": False,
    "external_export_enabled": False,
    "audit": [],
}

EXPECTED_EXCEPTION = {
    "invoice_id": "INV-AP-074",
    "reason_code": "PRICE_MISMATCH",
    "source_reference": "DISPUTE-33",
}
EXPECTED_APPLIED_BALANCE_CENTS = 95000

def fresh_state() -> dict[str, Any]:
    return deepcopy(INITIAL)

def expected_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    advice = state["remittance_advice"]
    result = []
    for invoice_id in advice["invoice_ids"]:
        invoice = state["ledger"][invoice_id]
        if invoice["state"] == "OPEN" and invoice["eligibility"] == "ELIGIBLE":
            result.append({"invoice_id": invoice_id, "amount_cents": invoice["open_cents"]})
    return result

def expected_total(state: dict[str, Any]) -> int:
    return sum(row["amount_cents"] for row in expected_rows(state))

def prepare_payment_draft(state: dict[str, Any]) -> None:
    rows = expected_rows(state)
    state["payment_draft"] = {
        "rows": deepcopy(rows),
        "total_cents": sum(row["amount_cents"] for row in rows),
        "source_revision": state["ledger_revision"],
        "status": "READY",
    }
    state["exceptions"] = [deepcopy(EXPECTED_EXCEPTION)]

def apply_credit(state: dict[str, Any], credit_id: str = "CN-AP-019") -> None:
    credit = state["credits"][credit_id]
    if credit["authorization"] != "APPROVED" or credit["status"] != "UNAPPLIED":
        raise ValueError("credit must be approved and unapplied")
    invoice = state["ledger"][credit["invoice_id"]]
    if invoice["state"] != "OPEN" or invoice["eligibility"] != "ELIGIBLE":
        raise ValueError("target invoice is not open and eligible")
    if invoice["open_cents"] < credit["amount_cents"]:
        raise ValueError("credit exceeds invoice balance")
    invoice["open_cents"] -= credit["amount_cents"]
    credit["status"] = "APPLIED"
    state["ledger_revision"] += 1
    state["audit"].append({
        "event": "CREDIT_APPLIED", "credit_id": credit_id,
        "invoice_id": credit["invoice_id"], "amount_cents": credit["amount_cents"],
        "ledger_revision": state["ledger_revision"],
    })

def evaluate_a(state: dict[str, Any]) -> dict[str, Any]:
    draft = state.get("payment_draft", {})
    actual_rows = draft.get("rows")
    expected = expected_rows(state)
    checks = {
        "source_docs_unchanged": state.get("source_hashes") == SOURCE_HASHES,
        "cycle_vendor_match": (state.get("cycle_id") == "RA-221"
                               and state.get("vendor_id") == "NORTHWIND-SYN"),
        "draft_rows_match_current_eligible_ledger": actual_rows == expected,
        "draft_total_matches_rows": type(draft.get("total_cents")) is int
                                    and draft.get("total_cents") == sum(
                                        row.get("amount_cents", 0) for row in (actual_rows or [])),
        "draft_total_matches_current_ledger": draft.get("total_cents") == expected_total(state),
        "draft_is_from_current_revision": draft.get("source_revision") == state.get("ledger_revision"),
        "draft_ready_but_not_external": draft.get("status") == "READY",
        "disputed_invoice_excluded_with_exact_reason": state.get("exceptions") == [EXPECTED_EXCEPTION],
        "external_payment_disabled": state.get("external_payment_enabled") is False,
        "external_export_disabled": state.get("external_export_enabled") is False,
    }
    return {
        "success": all(checks.values()), "checks": checks,
        "expected_rows": expected, "actual_rows": actual_rows,
        "expected_total_cents": expected_total(state),
        "actual_total_cents": draft.get("total_cents"),
        "ledger_revision": state.get("ledger_revision"),
        "draft_source_revision": draft.get("source_revision"),
    }

def evaluate_b(state: dict[str, Any]) -> dict[str, Any]:
    credit = state["credits"]["CN-AP-019"]
    invoice = state["ledger"]["INV-AP-071"]
    events = [event for event in state["audit"]
              if event.get("event") == "CREDIT_APPLIED" and event.get("credit_id") == "CN-AP-019"]
    disputed = state["ledger"]["INV-AP-074"]
    checks = {
        "source_docs_unchanged": state.get("source_hashes") == SOURCE_HASHES,
        "authorized_credit_applied": credit["authorization"] == "APPROVED" and credit["status"] == "APPLIED",
        "credit_applied_to_correct_invoice_once": invoice["open_cents"] == EXPECTED_APPLIED_BALANCE_CENTS
                                                  and len(events) == 1
                                                  and events[0].get("amount_cents") == 25000,
        "disputed_invoice_still_on_hold": disputed["eligibility"] == "DISPUTE_HOLD"
                                          and disputed["open_cents"] == 18000,
        "external_payment_disabled": state.get("external_payment_enabled") is False,
        "external_export_disabled": state.get("external_export_enabled") is False,
    }
    return {"success": all(checks.values()), "checks": checks,
            "actual_balance_cents": invoice["open_cents"], "credit_audit_count": len(events)}

def evaluate_shared(state: dict[str, Any]) -> dict[str, Any]:
    a, b = evaluate_a(state), evaluate_b(state)
    return {"success": a["success"] and b["success"], "actor_a": a, "actor_b": b}

def ma_id_control() -> dict[str, Any]:
    a_state, b_state = fresh_state(), fresh_state()
    prepare_payment_draft(a_state)
    apply_credit(b_state)
    return {
        "actor_a": evaluate_a(a_state), "actor_b": evaluate_b(b_state),
        "private_states_distinct": a_state is not b_state,
        "a_total_cents": a_state["payment_draft"]["total_cents"],
        "b_invoice_071_balance_cents": b_state["ledger"]["INV-AP-071"]["open_cents"],
    }

def shared_stale_control() -> dict[str, Any]:
    state = fresh_state()
    prepare_payment_draft(state)
    apply_credit(state)
    return evaluate_shared(state)

def shared_recovery_control() -> dict[str, Any]:
    state = fresh_state()
    prepare_payment_draft(state)
    apply_credit(state)
    prepare_payment_draft(state)
    return evaluate_shared(state)
