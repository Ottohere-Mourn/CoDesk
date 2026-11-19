"""Deterministic actor scoring with mechanism evidence kept separate."""
from typing import Any

TARGETS = {
    "MECH-01": {"A": {"vendor": "Northwind Safety", "reference": "INV-48217", "amount": "1840.00"},
                "B": {"payee": "Riverside Testing", "reference": "ACH-77104", "amount": "965.50"}},
    "MECH-02": {"A": {"batch": "QX-144", "review": "RECHECK"},
                "B": {"batch": "QX-207", "result": "PASS", "signoff": "M. Chen"}},
    "MECH-03": {"A": {"cell": "Calc!D12", "value": "1250.00"},
                "B": {"document": "Writer", "text": "We have received your service request and will respond by 3 PM."}},
    "MECH-04": {"A": {"SMP-041": "RETEST", "SMP-058": "RETEST"},
                "B": {"SMP-033": "TRANSFERRED"}},
    "MECH-05": {"A": {"record": "CLM-8401", "principal": "Claims Reviewer", "status": "APPROVED"},
                "B": {"record": "PAY-2207", "principal": "Treasury Reviewer", "status": "CONFIRMED"}},
}

def _matches(actual: Any, expected: Any) -> bool:
    return " ".join(str(actual or "").split()).casefold() == " ".join(str(expected).split()).casefold()

def _score(want: dict, got: Any) -> dict:
    got = got if isinstance(got, dict) else {}
    fields = {k: _matches(got.get(k), v) for k, v in want.items()}
    return {"success": bool(fields) and all(fields.values()), "fields": fields}

def evaluate(case_id: str, state: dict) -> dict:
    if case_id not in TARGETS:
        raise ValueError(f"unknown case {case_id}")
    state = state if isinstance(state, dict) else {}
    want = TARGETS[case_id]
    if case_id == "MECH-01":
        rows = state.get("rows", {})
        actors = {r: _score(want[r], rows.get(r)) for r in ("A", "B")}
        mismatch = [e for e in state.get("clipboard_trace", []) if isinstance(e, dict)
                    and e.get("event") == "paste" and e.get("pasted_value") != e.get("source_value")]
        attributed = [e for e in mismatch if e.get("reason") == "clipboard_owner_changed"]
        evidence = {"clipboard_paste_mismatch_count": len(mismatch), "attributed": bool(attributed)}
    elif case_id == "MECH-02":
        rows = state.get("rows", {})
        actors = {r: _score(want[r], rows.get(r)) for r in ("A", "B")}
        displaced = [e for e in state.get("undo_trace", []) if isinstance(e, dict)
                     and e.get("event") == "undo" and e.get("undid_actor") not in (None, e.get("request_actor"))]
        evidence = {"cross_actor_undo_count": len(displaced), "attributed": bool(displaced)}
    elif case_id == "MECH-03":
        a = _score(want["A"], state.get("calc_result"))
        b = _score(want["B"], state.get("writer_result"))
        misroutes = [e for e in state.get("input_trace", []) if isinstance(e, dict)
                     and e.get("intended_window") and e.get("actual_window")
                     and e["intended_window"] != e["actual_window"]]
        actors = {"A": a, "B": b}
        evidence = {"misrouted_input_count": len(misroutes), "attributed": bool(misroutes)}
    elif case_id == "MECH-04":
        rows = state.get("rows_by_id", {})
        actors = {
            "A": _score(want["A"], {k: (rows.get(k) or {}).get("status") for k in want["A"]}),
            "B": _score(want["B"], {k: (rows.get(k) or {}).get("status") for k in want["B"]}),
        }
        wrong = [e for e in state.get("range_trace", []) if isinstance(e, dict)
                 and e.get("intended_record_id") and e.get("written_record_id")
                 and e["intended_record_id"] != e["written_record_id"]]
        evidence = {"wrong_record_write_count": len(wrong), "attributed": bool(wrong)}
    else:
        actors = {}
        events = state.get("audit_events", [])
        for r in ("A", "B"):
            target = want[r]
            found = [e for e in events if isinstance(e, dict) and e.get("record") == target["record"]]
            actors[r] = _score(target, found[-1] if found else {})
        wrong_role = [e for e in events if isinstance(e, dict)
                      and e.get("operation") in {"approve", "confirm"}
                      and e.get("principal") != e.get("intended_principal")]
        changed = [e for e in state.get("session_trace", []) if isinstance(e, dict)
                   and e.get("generation_before") != e.get("generation_after")]
        evidence = {"wrong_principal_action_count": len(wrong_role),
                    "session_generation_change_count": len(changed),
                    "attributed": bool(wrong_role and changed)}
    return {"actors": actors, "joint_success": all(a["success"] for a in actors.values()),
            "mechanism_evidence": evidence}
