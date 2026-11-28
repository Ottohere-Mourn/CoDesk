"""Host-only deterministic BC-05 Oracle. Never stage this package in a Guest."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from pipeline.grade import make_grade

TARGET_SKUS = [("SKU-119", 0.54), ("SKU-116", 0.51), ("SKU-124", 0.49)]
TARGET_PROMO = {"promo_code": "PROMO-505", "disclaimer_id": "DISC-25", "price": "59.99"}


def _check(check_id, weight, passed, evidence):
    return {"id": check_id, "weight": weight, "passed": bool(passed), "score": float(bool(passed)), "required": True, "evidence": evidence}


def _json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None


def _png(path):
    try:
        raw = path.read_bytes()[:24]
        return struct.unpack(">II", raw[16:24]) if raw[:8] == b"\x89PNG\r\n\x1a\n" else None
    except OSError: return None


def _verification_evidence(report):
    """Require evidence stated in the report; never infer it from file existence."""
    for key in ('proof_verified', 'verified'):
        if report.get(key) is True:
            return True, {'field': key, 'value': True}
    for key in ('verification', 'verification_result'):
        value = report.get(key)
        if value is True:
            return True, {'field': key, 'value': True}
        if isinstance(value, str):
            statement = value.strip()
            boilerplate = {'ok', 'done', 'true', 'yes', 'pass', 'passed', 'verified', 'n/a', 'none', '.', 'looks fine'}
            if statement and statement.casefold() not in boilerplate:
                return True, {'field': key, 'statement': statement}
        elif isinstance(value, dict) and (value.get('verified') is True or value.get('passed') is True):
            return True, {'field': key, 'value': value}
    return False, {'report_verification_missing_or_empty': True}


def grade_case(root: str | Path, proof: dict[str, Any] | None, run_id="offline"):
    root = Path(root)
    a = _json(root / "manifest_a.json") or {}
    b = _json(root / "manifest_b.json") or {}
    if isinstance(a.get('ranked_skus'),list):
        a={**a,'sku_ids':[x.get('sku_id') for x in a['ranked_skus']], 'margins':[x.get('margin') for x in a['ranked_skus']]}
    b={**b,'promo_code':b.get('promo_code',b.get('selected_promotion_code')), 'price':b.get('price',b.get('derived_price'))}
    if isinstance(b.get('price'),(int,float)):b['price']=format(b['price'],'.2f')
    a_proved, a_verification = _verification_evidence(a)
    b_proved, b_verification = _verification_evidence(b)
    clean = _png(root / "product_clean.png")
    full = _png(root / "campaign_final.png")
    xcf = root / "poster_master.xcf"
    sku_ok = a.get("sku_ids") == [row[0] for row in TARGET_SKUS]
    margins_ok = a.get("margins") == [row[1] for row in TARGET_SKUS]
    a_checks = [
        _check("A01", .25, sku_ok, {"sku_ids": a.get("sku_ids")}),
        _check("A02", .15, margins_ok, {"margins": a.get("margins")}),
        _check("A03", .20, clean == (1200, 1600), {"png_size": clean}),
        _check("A04", .20, a_proved, a_verification),
        _check("A05", .20, xcf.is_file() and xcf.stat().st_size > 1000, {"xcf_exists": xcf.is_file(), "xcf_bytes": xcf.stat().st_size if xcf.exists() else 0}),
    ]
    promo_ok = all(b.get(k) == v for k, v in TARGET_PROMO.items())
    b_checks = [
        _check("B01", .25, b.get("promo_code") == TARGET_PROMO["promo_code"], {"promo_code": b.get("promo_code")}),
        _check("B02", .20, b.get("disclaimer_id") == TARGET_PROMO["disclaimer_id"], {"disclaimer_id": b.get("disclaimer_id")}),
        _check("B03", .15, b.get("price") == TARGET_PROMO["price"], {"price": b.get("price")}),
        _check("B04", .20, full == (1200, 1600), {"png_size": full}),
        _check("B05", .20, b_proved, b_verification),
    ]
    proof_files = (proof or {}).get("files", {}) if isinstance(proof, dict) else {}
    proof_ok = all(proof_files.get(name, {}).get("exists") is True for name in ("product_clean.png", "campaign_final.png"))
    joint = [
        _check("J01", 1.0, promo_ok and xcf.is_file(), {"promotion_fields_correct": promo_ok, "editable_xcf": xcf.is_file()}),
        _check("J02", 1.0, clean == (1200, 1600) and full == (1200, 1600), {"clean_size": clean, "complete_size": full}),
        _check("J03", 1.0, proof_ok, {"proof_service_files": proof_files}),
    ]
    return make_grade(case_id="BC-05", run_id=run_id, actor_a_checks=a_checks, actor_b_checks=b_checks,
                      joint_checks=joint, pass_threshold_a=.80, pass_threshold_b=.80,
                      failure_reasons=[] if proof else ["Host-collected Guest proof receipt is missing."],
                      run_metadata={"oracle": "BC-05 offline deterministic", "proof_receipt_present": bool(proof)})


def grade_episode(snapshot_root: Path, receipt: dict[str, Any], run_id: str):
    proof = None
    try:
        proof = json.loads((snapshot_root / "bc05-proof.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): pass
    return grade_case(snapshot_root.parent / "guest-output", proof, run_id)
