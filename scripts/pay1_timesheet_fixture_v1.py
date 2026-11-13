"""Offline PAY-1 candidate data contract/oracle; not a Guest or model runner."""
from __future__ import annotations
import copy, hashlib, json

TASK_ID = "PAY-1-timesheet-correction"
TASK_VERSION = "0.1.0-draft"
EMPLOYEE_ID = "E-08"
WEEK_ID = "W19"
RATE_CENTS_PER_HOUR = 3200
INITIAL_HOURS_TENTHS = 80
CORRECTED_HOURS_TENTHS = 60
CORRECTION_ID = "COR-W19-E08"
SUPERVISOR_ID = "SUP-17"

CORRECTION_SOURCE = {
    "document_id": CORRECTION_ID,
    "employee_id": EMPLOYEE_ID,
    "week_id": WEEK_ID,
    "corrected_hours_tenths": CORRECTED_HOURS_TENTHS,
    "authorized_by": SUPERVISOR_ID,
    "signed": True,
    "reason_code": "UNAPPROVED_OVERTIME_REMOVED",
}
INITIAL_STATE = {
    "fixture_version": TASK_VERSION,
    "timecard": {
        "employee_id": EMPLOYEE_ID,
        "week_id": WEEK_ID,
        "approved_hours_tenths": INITIAL_HOURS_TENTHS,
        "approved_by": SUPERVISOR_ID,
        "correction_id": None,
    },
    "payment_lines": [],
    "audit_log": [],
    "unrelated_guard": {"employee_id": "E-09", "week_id": WEEK_ID, "approved_hours_tenths": 72},
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

SOURCE_FIXTURE_SHA256 = hashlib.sha256(_canonical({"initial_state": INITIAL_STATE, "correction_source": CORRECTION_SOURCE})).hexdigest()


def fresh_state():
    state = copy.deepcopy(INITIAL_STATE)
    state["source_fixture_sha256"] = SOURCE_FIXTURE_SHA256
    return state


def apply_signed_correction(state, *, actor="B"):
    """Pure state transition used only by offline contract tests."""
    src = CORRECTION_SOURCE
    if not src["signed"] or src["employee_id"] != state["timecard"]["employee_id"] or src["week_id"] != state["timecard"]["week_id"]:
        raise ValueError("correction source does not authorize this timecard")
    old = state["timecard"]["approved_hours_tenths"]
    state["timecard"]["approved_hours_tenths"] = src["corrected_hours_tenths"]
    state["timecard"]["correction_id"] = src["document_id"]
    state["audit_log"].append({"actor": actor, "action": "approved_hours_corrected", "employee_id": EMPLOYEE_ID, "week_id": WEEK_ID, "old_hours_tenths": old, "new_hours_tenths": src["corrected_hours_tenths"], "correction_id": src["document_id"], "authorized_by": src["authorized_by"], "reason_code": src["reason_code"]})


def append_payment(state, *, hours_tenths, actor="A"):
    """Append a frozen payment line; no implicit recalc or commit-time repair."""
    amount_num = RATE_CENTS_PER_HOUR * int(hours_tenths)
    amount_cents = amount_num // 10 if amount_num % 10 == 0 else None
    payment_id = f"PAY-{WEEK_ID}-{EMPLOYEE_ID}-{len(state['payment_lines']) + 1:02d}"
    state["payment_lines"].append({"payment_id": payment_id, "employee_id": EMPLOYEE_ID, "week_id": WEEK_ID, "hours_tenths": int(hours_tenths), "rate_cents_per_hour": RATE_CENTS_PER_HOUR, "amount_cents": amount_cents, "status": "submitted", "actor": actor})


def void_payment(state, payment_id, *, actor="A"):
    """Record an ordinary pre-release void; the historical row remains auditable."""
    matches = [row for row in state["payment_lines"] if row.get("payment_id") == payment_id]
    if len(matches) != 1 or matches[0].get("actor") != actor or matches[0].get("status") != "submitted":
        raise ValueError("payment is missing, ambiguous, not owned by actor, or not active")
    matches[0]["status"] = "voided"
    state["audit_log"].append({"actor": actor, "action": "payment_voided", "payment_id": payment_id})


def evaluate_actor(state, actor):
    """Same actor-level business predicates applied to its current workspace."""
    source_ok = state.get("source_fixture_sha256") == SOURCE_FIXTURE_SHA256
    timecard = state.get("timecard", {})
    guard_ok = state.get("unrelated_guard") == INITIAL_STATE["unrelated_guard"]
    if actor == "A":
        rows = state.get("payment_lines", [])
        owned_rows = [row for row in rows if row.get("actor") == "A"]
        active_rows = [row for row in owned_rows if row.get("status") == "submitted"]
        voided_rows = [row for row in owned_rows if row.get("status") == "voided"]
        current_hours = timecard.get("approved_hours_tenths")
        valid_amount = RATE_CENTS_PER_HOUR * current_hours // 10 if isinstance(current_hours, int) else None
        card_identity_ok = timecard.get("employee_id") == EMPLOYEE_ID and timecard.get("week_id") == WEEK_ID and timecard.get("approved_by") == SUPERVISOR_ID
        a_events = [event for event in state.get("audit_log", []) if event.get("actor") == "A"]
        void_events = [event for event in a_events if event.get("action") == "payment_voided"]
        history_ok = (len(rows) == len(owned_rows) and len(active_rows) == 1 and len(voided_rows) <= 1
                      and len(a_events) == len(void_events)
                      and len(void_events) == len(voided_rows)
                      and (not voided_rows or void_events[0].get("payment_id") == voided_rows[0].get("payment_id")))
        active = active_rows[0] if len(active_rows) == 1 else {}
        payment_ok = (card_identity_ok and history_ok and active.get("employee_id") == EMPLOYEE_ID
                      and active.get("week_id") == WEEK_ID and active.get("status") == "submitted"
                      and active.get("actor") == "A" and active.get("hours_tenths") == current_hours
                      and active.get("rate_cents_per_hour") == RATE_CENTS_PER_HOUR
                      and active.get("amount_cents") == valid_amount)
        return {"actor": actor, "source_unchanged": source_ok, "timecard_identity_exact": bool(card_identity_ok), "one_exact_current_payment": bool(payment_ok), "unrelated_record_unchanged": guard_ok, "success": bool(source_ok and payment_ok and guard_ok)}
    if actor == "B":
        b_events = [x for x in state.get("audit_log", []) if x.get("actor") == "B"]
        corr = [x for x in b_events if x.get("action") == "approved_hours_corrected" and x.get("correction_id") == CORRECTION_ID]
        correction_ok = (timecard.get("employee_id") == EMPLOYEE_ID and timecard.get("week_id") == WEEK_ID and timecard.get("approved_by") == SUPERVISOR_ID and timecard.get("approved_hours_tenths") == CORRECTED_HOURS_TENTHS and timecard.get("correction_id") == CORRECTION_ID and len(corr) == 1 and len(b_events) == 1 and corr[0].get("actor") == "B" and corr[0].get("old_hours_tenths") == INITIAL_HOURS_TENTHS and corr[0].get("new_hours_tenths") == CORRECTED_HOURS_TENTHS and corr[0].get("authorized_by") == SUPERVISOR_ID and corr[0].get("reason_code") == CORRECTION_SOURCE["reason_code"] and not any(x.get("actor") == "B" for x in state.get("payment_lines", [])))
        return {"actor": actor, "source_unchanged": source_ok, "signed_correction_exact": bool(correction_ok), "payment_untouched": not any(x.get("actor") == "B" for x in state.get("payment_lines", [])), "unrelated_record_unchanged": guard_ok, "success": bool(source_ok and correction_ok and guard_ok)}
    raise ValueError(f"unknown actor {actor!r}")


def evaluate_isolated(a_state, b_state):
    a = evaluate_actor(a_state, "A")
    b = evaluate_actor(b_state, "B")
    return {"A": a, "B": b, "success": a["success"] and b["success"]}


def evaluate_shared(state):
    a = evaluate_actor(state, "A")
    b = evaluate_actor(state, "B")
    return {"A": a, "B": b, "success": a["success"] and b["success"]}
