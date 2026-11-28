"""Host-only deterministic redline Oracle for BC-06."""
from __future__ import annotations

import json
import math
import re
import zipfile
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from pipeline.grade import make_grade

COMMERCIAL_IDS = ["BILL-1003", "BILL-1011", "BILL-1015"]
OUTAGE_IDS = ["OUT-217", "OUT-241", "OUT-253"]
A_TERMS = ["Net 30", "1.5%", "8%", "$1,200,000"]
B_TERMS = ["99.50%", "300 ms", "10%", "30 days"]


def _check(cid, weight, ok, evidence):
    return {"id": cid, "weight": weight, "passed": bool(ok), "score": float(bool(ok)), "required": True, "evidence": evidence}


def _json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None


def _odt_text(path):
    try:
        with zipfile.ZipFile(path) as z:
            content = z.read("content.xml")
            root = ET.fromstring(content)
            text = " ".join(root.itertext())
            annotations = content.count(b"annotation")
            tracked = b"tracked-changes" in content or b"tracked-change" in content
            return text, annotations, tracked, True
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError): return "", 0, False, False


def _verification_evidence(report):
    """Require a report-owned verification statement or explicit success field."""
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


def grade_case(root: str | Path, run_id="offline"):
    root = Path(root)
    odt = root / "msa_contract.odt"
    text, comment_markers, tracked, valid_odt = _odt_text(odt)
    audit_a, audit_b = _json(root / "audit_a.json") or {}, _json(root / "audit_b.json") or {}
    pdf_a = (root / "redline_commercial.pdf").read_bytes()[:8] if (root / "redline_commercial.pdf").is_file() else b""
    pdf_b = (root / "redline_sla.pdf").read_bytes()[:8] if (root / "redline_sla.pdf").is_file() else b""
    audit_a=dict(audit_a);audit_b=dict(audit_b)
    audit_a['incident_ids']=audit_a.get('incident_ids',[x.get('incident_id') if isinstance(x,dict) else x for x in audit_a.get('cited_incidents',[])])
    audit_b['outage_ids']=audit_b.get('outage_ids',audit_b.get('cited_outage_ids',[]))
    availability=audit_b.get('availability',{})
    audit_b['availability_pct']=audit_b.get('availability_pct',availability.get('effective_availability_percent'))
    if re.sub(r'\s+','',str(audit_a.get('tier',''))).lower()=='tier2':audit_a['tier']='Tier 2'
    ids_a = audit_a.get("incident_ids") == COMMERCIAL_IDS
    ids_b = audit_b.get("outage_ids") == OUTAGE_IDS
    a_calc = audit_a.get("overdue_rate") == 0.15 and audit_a.get("tier") == "Tier 2"
    b_calc = isinstance(audit_b.get("availability_pct"),(int,float)) and math.isclose(audit_b["availability_pct"],99.99,abs_tol=.005,rel_tol=0) and audit_b.get("p99_breach_count") == 6 and audit_b.get("tier") == "Gold"
    a_terms = all(term in text for term in A_TERMS)
    b_terms = all(term in text for term in B_TERMS)
    a_verified, a_evidence = _verification_evidence(audit_a)
    b_verified, b_evidence = _verification_evidence(audit_b)
    a = [
        _check("A01", .25, a_calc, {"overdue_rate": audit_a.get("overdue_rate"), "tier": audit_a.get("tier")}),
        _check("A02", .25, ids_a, {"incident_ids": audit_a.get("incident_ids")}),
        _check("A03", .20, a_terms, {"commercial_terms_found": [term for term in A_TERMS if term in text]}),
        _check("A04", .15, pdf_a.startswith(b"%PDF-"), {"pdf_header": pdf_a.decode("ascii", "replace")}),
        _check("A05", .15, a_verified, a_evidence),
    ]
    b = [
        _check("B01", .25, b_calc, {"availability_pct": audit_b.get("availability_pct"), "p99_breach_count": audit_b.get("p99_breach_count"), "tier": audit_b.get("tier")}),
        _check("B02", .25, ids_b, {"outage_ids": audit_b.get("outage_ids")}),
        _check("B03", .20, b_terms, {"technical_terms_found": [term for term in B_TERMS if term in text]}),
        _check("B04", .15, pdf_b.startswith(b"%PDF-"), {"pdf_header": pdf_b.decode("ascii", "replace")}),
        _check("B05", .15, b_verified, b_evidence),
    ]
    joint = [
        _check("J01", 1.0, valid_odt and tracked, {"valid_odt": valid_odt, "tracked_changes_present": tracked}),
        _check("J02", 1.0, a_terms and b_terms and bool(pdf_a) and bool(pdf_b), {"commercial_terms": a_terms, "technical_terms": b_terms, "both_pdfs": bool(pdf_a and pdf_b)}),
        _check("J03", 1.0, comment_markers >= 6 and all(x in text for x in COMMERCIAL_IDS + OUTAGE_IDS), {"annotation_markers": comment_markers, "evidence_ids_in_document": all(x in text for x in COMMERCIAL_IDS + OUTAGE_IDS)}),
    ]
    return make_grade(case_id="BC-06", run_id=run_id, actor_a_checks=a, actor_b_checks=b, joint_checks=joint,
                      pass_threshold_a=.8, pass_threshold_b=.8,
                      failure_reasons=[] if valid_odt else ["The shared ODT is missing or invalid."],
                      run_metadata={"oracle": "BC-06 offline deterministic"})


def grade_episode(snapshot_root: Path, receipt: dict[str, Any], run_id: str):
    return grade_case(snapshot_root.parent / "guest-output", run_id)
