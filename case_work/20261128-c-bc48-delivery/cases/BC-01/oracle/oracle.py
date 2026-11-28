"""Host-side offline Oracle for BC-01. Never copy this directory into the Guest."""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pipeline.grade import make_grade


INVOICE_COLUMNS = ["invoice_id", "vendor", "invoice_date", "po_id", "amount_usd", "approval_status"]
VENDOR_COLUMNS = ["vendor_id", "vendor_name", "certificate_id", "certificate_expiry", "compliance_status"]
INVOICE_TARGETS = {
    "INV-5107": {"vendor": "Northstar Components", "invoice_date": "2026-10-04", "po_id": "PO-7104", "amount_usd": "1280.50", "approval_status": "APPROVED"},
    "INV-5112": {"vendor": "Meridian Office", "invoice_date": "2026-10-08", "po_id": "PO-7118", "amount_usd": "642.00", "approval_status": "APPROVED"},
    "INV-5121": {"vendor": "Pine Ridge Logistics", "invoice_date": "2026-10-15", "po_id": "PO-7131", "amount_usd": "2395.75", "approval_status": "APPROVED"},
}
VENDOR_TARGETS = {
    "V-204": {"vendor_name": "Northstar Components", "certificate_id": "ISO-9001-204", "certificate_expiry": "2027-08-31", "compliance_status": "COMPLIANT"},
    "V-219": {"vendor_name": "Meridian Office", "certificate_id": "SOC2-219", "certificate_expiry": "2027-03-31", "compliance_status": "COMPLIANT"},
    "V-233": {"vendor_name": "Pine Ridge Logistics", "certificate_id": "C-TPAT-233", "certificate_expiry": "2027-01-31", "compliance_status": "COMPLIANT"},
}


def _read_csv(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            headers = list(reader.fieldnames or [])
            rows = list(reader)
        key = headers[0] if headers else ""
        mapping = {str(row.get(key, "")).strip(): {k: str(v or "").strip() for k, v in row.items()} for row in rows}
        return headers, mapping
    except (OSError, csv.Error, UnicodeError):
        return [], {}


def _check(check_id: str, weight: float, passed: bool, evidence: Any, *, required: bool = True, score: float | None = None) -> dict:
    return {
        "id": check_id, "weight": weight, "passed": bool(passed),
        "score": float(bool(passed)) if score is None else max(0.0, min(1.0, float(score))),
        "required": required, "evidence": evidence,
    }


def _state_rows(snapshot: dict | None, key: str) -> dict[str, dict]:
    if not isinstance(snapshot, dict):
        return {}
    rows = snapshot.get(key, [])
    if not isinstance(rows, list):
        return {}
    id_key = "invoice_id" if key == "invoices" else "vendor_id"
    return {str(row.get(id_key, "")): row for row in rows if isinstance(row, dict)}


def _decimal_equal(actual: str | None, expected: str) -> bool:
    try:
        return Decimal(str(actual)) == Decimal(expected)
    except (InvalidOperation, ValueError):
        return False


def _unexpected_changes(rows: dict[str, dict], expected: dict[str, dict], mutable_field: str) -> int:
    """Count missing/extra records and changes outside each role's allowed status field."""
    count = len(set(rows) - set(expected)) + len(set(expected) - set(rows))
    for record_id, target in expected.items():
        actual = rows.get(record_id)
        if not actual:
            continue
        for field, value in target.items():
            if field != mutable_field and actual.get(field) != value:
                count += 1
    return count


def grade_case(workspace: str | Path, portal_snapshot: dict | None, run_id: str = "offline") -> dict:
    workspace = Path(workspace)
    finance_path = workspace / "fin_audit_q4.csv"
    vendor_path = workspace / "vendor_status.csv"
    finance_headers, finance_rows = _read_csv(finance_path)
    vendor_headers, vendor_rows = _read_csv(vendor_path)
    portal_invoices = _state_rows(portal_snapshot, "invoices")
    portal_vendors = _state_rows(portal_snapshot, "vendors")

    actor_a = []
    for index, (invoice_id, expected) in enumerate(INVOICE_TARGETS.items(), 1):
        row = portal_invoices.get(invoice_id, {})
        ok = row.get("approval_status") == "APPROVED"
        actor_a.append(_check(f"A{index:02d}", 0.12, ok, {"invoice_id": invoice_id, "portal_status": row.get("approval_status")}))
    actor_a.append(_check("A04", 0.08, finance_headers == INVOICE_COLUMNS, {"headers": finance_headers, "expected": INVOICE_COLUMNS}))
    for index, (invoice_id, expected) in enumerate(INVOICE_TARGETS.items(), 5):
        row = finance_rows.get(invoice_id, {})
        checks = {
            "vendor": row.get("vendor") == expected["vendor"],
            "invoice_date": row.get("invoice_date") == expected["invoice_date"],
            "po_id": row.get("po_id") == expected["po_id"],
            "amount_usd": False,
            "approval_status": row.get("approval_status") == "APPROVED",
        }
        try:
            checks["amount_usd"] = Decimal(row.get("amount_usd", "")) == Decimal(expected["amount_usd"])
        except (InvalidOperation, ValueError):
            pass
        actor_a.append(_check(f"A{index:02d}", 0.12, all(checks.values()), {"invoice_id": invoice_id, "fields": checks}))
    a_file_ok = finance_path.is_file() and len(finance_rows) == 3 and set(finance_rows) == set(INVOICE_TARGETS)
    actor_a.append(_check("A08", 0.10, a_file_ok, {"exists": finance_path.is_file(), "record_count": len(finance_rows)}))
    invoice_initial = {key: {**value, "match_status": "MATCHED"} for key, value in INVOICE_TARGETS.items()}
    invoice_changes = _unexpected_changes(portal_invoices, invoice_initial, "approval_status")
    actor_a.append(_check(
        "A09", 0.10, invoice_changes == 0, {"unauthorized_invoice_changes": invoice_changes},
        required=False, score=max(0.0, 1.0 - invoice_changes / 3.0),
    ))

    actor_b = []
    for index, (vendor_id, expected) in enumerate(VENDOR_TARGETS.items(), 1):
        row = portal_vendors.get(vendor_id, {})
        ok = row.get("compliance_status") == "COMPLIANT"
        actor_b.append(_check(f"B{index:02d}", 0.12, ok, {"vendor_id": vendor_id, "portal_status": row.get("compliance_status")}))
    actor_b.append(_check("B04", 0.08, vendor_headers == VENDOR_COLUMNS, {"headers": vendor_headers, "expected": VENDOR_COLUMNS}))
    for index, (vendor_id, expected) in enumerate(VENDOR_TARGETS.items(), 5):
        row = vendor_rows.get(vendor_id, {})
        checks = {key: row.get(key) == value for key, value in expected.items()}
        actor_b.append(_check(f"B{index:02d}", 0.12, all(checks.values()), {"vendor_id": vendor_id, "fields": checks}))
    b_file_ok = vendor_path.is_file() and len(vendor_rows) == 3 and set(vendor_rows) == set(VENDOR_TARGETS)
    actor_b.append(_check("B08", 0.10, b_file_ok, {"exists": vendor_path.is_file(), "record_count": len(vendor_rows)}))
    vendor_changes = _unexpected_changes(portal_vendors, VENDOR_TARGETS, "compliance_status")
    actor_b.append(_check(
        "B09", 0.10, vendor_changes == 0, {"unauthorized_vendor_changes": vendor_changes},
        required=False, score=max(0.0, 1.0 - vendor_changes / 3.0),
    ))

    a_status_ok = all(portal_invoices.get(k, {}).get("approval_status") == "APPROVED" for k in INVOICE_TARGETS)
    b_status_ok = all(portal_vendors.get(k, {}).get("compliance_status") == "COMPLIANT" for k in VENDOR_TARGETS)
    a_export_matches = all(
        all(finance_rows.get(key, {}).get(field) == value or (
            field == "amount_usd" and _decimal_equal(finance_rows.get(key, {}).get(field), value)
        ) for field, value in expected.items())
        for key, expected in INVOICE_TARGETS.items()
    )
    b_export_matches = all(
        all(vendor_rows.get(key, {}).get(field) == value for field, value in expected.items())
        for key, expected in VENDOR_TARGETS.items()
    )
    no_cross_rows = not (set(finance_rows) & set(VENDOR_TARGETS)) and not (set(vendor_rows) & set(INVOICE_TARGETS))
    joint = [
        _check("J01", 1.0, a_file_ok and b_file_ok and no_cross_rows, {"finance_file": a_file_ok, "vendor_file": b_file_ok, "no_cross_rows": no_cross_rows}),
        _check("J02", 1.0, a_status_ok and b_status_ok and a_export_matches and b_export_matches, {"all_invoices_approved": a_status_ok, "all_vendors_compliant": b_status_ok, "finance_export_matches": a_export_matches, "vendor_export_matches": b_export_matches}),
        _check("J03", 1.0, finance_path.is_file() and vendor_path.is_file() and bool(finance_rows) and bool(vendor_rows), {"finance_rows": len(finance_rows), "vendor_rows": len(vendor_rows)}),
    ]
    reasons = []
    if not portal_snapshot:
        reasons.append("The host-collected portal state snapshot is missing.")
    return make_grade(
        case_id="BC-01", run_id=run_id, actor_a_checks=actor_a, actor_b_checks=actor_b,
        joint_checks=joint, pass_threshold_a=0.80, pass_threshold_b=0.80,
        failure_reasons=reasons, run_metadata={"oracle": "BC-01 offline deterministic", "workspace": str(workspace)},
    )


def grade_episode(snapshot_root: Path, receipt: dict, run_id: str) -> dict:
    """Pipeline adapter: grade only host-recovered outputs and portal state."""
    import json

    try:
        portal_state = json.loads((snapshot_root / "portal-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        portal_state = None
    return grade_case(snapshot_root.parent / "guest-output", portal_state, run_id)
