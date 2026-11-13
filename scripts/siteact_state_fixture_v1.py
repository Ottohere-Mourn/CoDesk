"""SITEACT-STATE1 offline contract for a synthetic site-activation workflow."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

CASE_ID = "SITEACT-STATE1"
TASK_VERSION = "0.1.0-hybrid-v2-site-readiness-handoff"
SITE_ID = "NE-14"
EVIDENCE = (
    {"kind": "protocol", "record_id": "PR-14-AMD-04", "status": "CURRENT", "detail": "Amendment 04 effective 2026-10-15"},
    {"kind": "irb", "record_id": "IRB-NE14-221", "status": "APPROVED", "detail": "Approval active through 2027-02-28"},
    {"kind": "training", "record_id": "TRN-NE14-2026-10", "status": "COMPLETE", "detail": "4 of 4 assigned staff trained"},
    {"kind": "calibration", "record_id": "CAL-55", "status": "CURRENT", "detail": "HPLC-4 calibration current through 2026-12-31"},
)
DEVIATION = {
    "deviation_id": "PD-2026-018",
    "reason_code": "MONITOR_REVIEW_REQUIRED",
    "summary": "Visit-window deviation recorded; monitor assessment pending.",
    "required_status": "HOLD",
    "notice_date": "2026-11-07",
}
EXPECTED_READY_SNAPSHOT = {
    "site_id": SITE_ID,
    "status": "READY",
    "source_revision": 1,
    "protocol_id": "PR-14-AMD-04",
    "irb_id": "IRB-NE14-221",
    "training_record_id": "TRN-NE14-2026-10",
    "training_complete": "4/4",
    "calibration_id": "CAL-55",
}
EXPECTED_HOLD_SNAPSHOT = {**EXPECTED_READY_SNAPSHOT, "status": "HOLD", "source_revision": 2}

def new_state() -> dict[str, Any]:
    return {
        "site_id": SITE_ID,
        "status": "READY",
        "revision": 1,
        "evidence": [dict(x) for x in EVIDENCE],
        "open_deviations": [],
        "snapshot": None,
        "events": [],
    }

def clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(state)

def create_snapshot(state: dict[str, Any], values: dict[str, str]) -> None:
    required = {
        "site_id": SITE_ID,
        "protocol_id": "PR-14-AMD-04",
        "irb_id": "IRB-NE14-221",
        "training_record_id": "TRN-NE14-2026-10",
        "training_complete": "4/4",
        "calibration_id": "CAL-55",
    }
    if any(values.get(k) != v for k, v in required.items()):
        raise ValueError("snapshot evidence fields do not match current source evidence")
    if values.get("status") != state["status"]:
        raise ValueError("snapshot status does not match the current site status")
    state["snapshot"] = {
        **required,
        "status": state["status"],
        "source_revision": state["revision"],
    }
    state["events"].append({"action": "SNAPSHOT_CREATED", "revision": state["revision"]})

def log_deviation_and_hold(state: dict[str, Any], deviation_id: str, reason_code: str) -> None:
    if deviation_id != DEVIATION["deviation_id"] or reason_code != DEVIATION["reason_code"]:
        raise ValueError("deviation notice ID/reason code mismatch")
    if any(x["deviation_id"] == deviation_id for x in state["open_deviations"]):
        raise ValueError("deviation already recorded")
    state["open_deviations"].append({**DEVIATION})
    state["status"] = "HOLD"
    state["revision"] += 1
    state["events"].append({"action": "DEVIATION_RECORDED", "deviation_id": deviation_id,
                            "status": "HOLD", "revision": state["revision"]})

def snapshot_is_current(state: dict[str, Any]) -> bool:
    snap = state.get("snapshot")
    return bool(snap and snap.get("status") == state.get("status")
                and snap.get("source_revision") == state.get("revision"))

def score_ready_actor(state: dict[str, Any]) -> bool:
    return (state.get("site_id") == SITE_ID
            and state.get("status") == "READY"
            and state.get("revision") == 1
            and state.get("evidence") == [dict(x) for x in EVIDENCE]
            and not state.get("open_deviations")
            and state.get("snapshot") == EXPECTED_READY_SNAPSHOT
            and snapshot_is_current(state))

def score_deviation_actor(state: dict[str, Any]) -> bool:
    expected_event = {"action": "DEVIATION_RECORDED", "deviation_id": DEVIATION["deviation_id"],
                      "status": "HOLD", "revision": 2}
    return (state.get("site_id") == SITE_ID
            and state.get("status") == "HOLD"
            and state.get("revision") == 2
            and state.get("evidence") == [dict(x) for x in EVIDENCE]
            and state.get("open_deviations") == [DEVIATION]
            and expected_event in state.get("events", []))

def score_shared_final(state: dict[str, Any]) -> bool:
    return score_deviation_actor(state) and snapshot_is_current(state) and state.get("snapshot") == EXPECTED_HOLD_SNAPSHOT

def expected_shared_stale_signature(state: dict[str, Any]) -> bool:
    return (score_deviation_actor(state)
            and state.get("snapshot") == EXPECTED_READY_SNAPSHOT
            and not snapshot_is_current(state))
