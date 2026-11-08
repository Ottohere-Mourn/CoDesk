"""CRM-LU1 explicit legacy full-record form contract; synthetic Guest-local data."""
from __future__ import annotations
from copy import deepcopy
import time

CASE_ID = "CRM-LU1"
TASK_VERSION = "0.1.1-legacy-full-record-form-role-tabs"
CUSTOMER = "C-014"
INITIAL = {"customer_id": CUSTOMER, "renewal_contact": "Riley Park",
           "billing_email": "billing-old@northwind.example", "record_version": 1}
SOURCES = {
    "A": {"document": "Signed renewal addendum RN-014", "renewal_contact": "Jordan Lee"},
    "B": {"document": "Verified billing-contact notice BN-014", "billing_email": "ap@northwind.example"},
}
EXPECTED = {"A": ("renewal_contact", "Jordan Lee"),
            "B": ("billing_email", "ap@northwind.example")}

def new_state():
    return {"record": dict(INITIAL), "events": []}

def clone_state(state):
    return deepcopy(state)

def save_full_record(state, actor, customer_id, values, loaded_version):
    if actor not in SOURCES or customer_id != CUSTOMER:
        raise ValueError("unknown actor/customer")
    field, expected = EXPECTED[actor]
    if values.get(field) != expected:
        raise ValueError("owner field does not match the authorized source")
    rec = state["record"]
    before = dict(rec)
    # Explicit legacy full-form Save contract: all form fields replace the
    # stored record; there is no row-version check or field-level PATCH.
    new_record = {"customer_id": customer_id,
                  "renewal_contact": values.get("renewal_contact", ""),
                  "billing_email": values.get("billing_email", ""),
                  "record_version": rec["record_version"] + 1}
    state["record"] = new_record
    event = {"action": "FULL_RECORD_SAVE", "actor": actor,
             "customer_id": customer_id, "loaded_version": int(loaded_version),
             "committed_version": new_record["record_version"],
             "committed_unix": time.time(),
             "submitted": dict(values), "before": before, "after": dict(new_record)}
    state["events"].append(event)
    return event

def actor_success(state, actor):
    field, expected = EXPECTED[actor]
    rec = state.get("record", {})
    return rec.get("customer_id") == CUSTOMER and rec.get(field) == expected

def joint_success(state):
    return actor_success(state, "A") and actor_success(state, "B")

def lost_update_signature(state):
    events = state.get("events", [])
    if len(events) < 2: return False
    first, last = events[-2:]
    return (first.get("actor") == "B" and last.get("actor") == "A"
            and first.get("after", {}).get("billing_email") == SOURCES["B"]["billing_email"]
            and last.get("before", {}).get("billing_email") == SOURCES["B"]["billing_email"]
            and last.get("submitted", {}).get("billing_email") == INITIAL["billing_email"]
            and last.get("after", {}).get("billing_email") == INITIAL["billing_email"]
            and last.get("loaded_version") < last.get("committed_version"))

def recovery_save_after_reload(state):
    """Restore B's email and keep A's contact; reload/merge is always available."""
    record = state["record"]
    values = {"renewal_contact": EXPECTED["A"][1],
              "billing_email": EXPECTED["B"][1]}
    return save_full_record(state, "A", CUSTOMER, values, record["record_version"])

