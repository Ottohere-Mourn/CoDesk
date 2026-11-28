"""Deterministic, host-only grader for BC-08."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from pipeline.grade import make_grade


RANGES = (
    ("2026-10-01", "2026-10-10"),
    ("2026-10-11", "2026-10-20"),
    ("2026-10-21", "2026-10-31"),
)
CSV_HEADER = ["incident_id", "service", "severity", "status", "created_at"]


def _expected_metrics(start: str, end: str) -> dict[str, float | int]:
    days = [d for d in range(1, 32) if start <= f"2026-10-{d:02d}" <= end and d not in {7, 19, 29}]
    latency = [140 + ((d * 37) % 260) for d in days]
    requests = [900 + d * 37 for d in days]
    errors = [(d * 13) % 41 for d in days]
    return {
        "avg_latency_ms": round(sum(latency) / len(latency), 2) if latency else 0,
        "total_requests": sum(requests),
        "error_rate_pct": round(sum(errors) / sum(requests) * 100, 2) if sum(requests) else 0,
    }


def _expected_incidents(severity: str) -> list[dict[str, str]]:
    rows = []
    for i in range(1, 31):
        level = "CRITICAL" if i % 6 == 0 else "HIGH" if i % 3 == 0 else "MEDIUM" if i % 2 == 0 else "LOW"
        if level != severity:
            continue
        rows.append({
            "incident_id": f"INC-{3000+i}",
            "service": f"svc-{(i % 5) + 1}",
            "severity": level,
            "status": "OPEN" if i % 4 else "ACKNOWLEDGED",
            "created_at": f"2026-10-{(i % 27) + 1:02d}T{(i * 3) % 24:02d}:00:00Z",
        })
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _endpoint(receipt: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
    endpoints = receipt.get("http_endpoints", {})
    item = endpoints.get(endpoint_id, {}) if isinstance(endpoints, dict) else {}
    return item if isinstance(item, dict) else {}


def _archived_endpoint_csv(snapshot_root: Path, receipt: dict[str, Any], endpoint_id: str) -> list[dict[str, str]]:
    row = _endpoint(receipt, endpoint_id)
    rel = PurePosixPath(str(row.get("archive_path", "")))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return []
    path = snapshot_root.joinpath(*rel.parts[1:]) if rel.parts[0] == "host-snapshots" else snapshot_root.joinpath(*rel.parts)
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != CSV_HEADER:
                return []
            return [dict(r) for r in reader]
    except OSError:
        return []


def _verify_payload(root: Path, filename: str) -> dict[str, Any]:
    return _read_json(root / filename)


def grade_episode(snapshot_root: Path, receipt: dict[str, Any], run_id: str) -> dict[str, Any]:
    snapshot_root = Path(snapshot_root)
    a_record = _verify_payload(snapshot_root.parent / "guest-output", "verify_metrics.json")
    b_record = _verify_payload(snapshot_root.parent / "guest-output", "verify_triage.json")
    app = (snapshot_root / "app.py").read_text(encoding="utf-8", errors="replace") if (snapshot_root / "app.py").is_file() else ""
    layout = (snapshot_root / "layout.html").read_text(encoding="utf-8", errors="replace") if (snapshot_root / "layout.html").is_file() else ""
    js = (snapshot_root / "app.js").read_text(encoding="utf-8", errors="replace") if (snapshot_root / "app.js").is_file() else ""
    head = (snapshot_root / "git-HEAD").read_text(encoding="utf-8", errors="replace").strip() if (snapshot_root / "git-HEAD").is_file() else ""
    log = (snapshot_root / "git-log-HEAD").read_text(encoding="utf-8", errors="replace") if (snapshot_root / "git-log-HEAD").is_file() else ""
    commit_hashes = {line.split()[1] for line in log.splitlines() if len(line.split()) >= 2 and re.fullmatch(r"[0-9a-f]{40}", line.split()[1])}

    metrics_results = a_record.get("ranges", [])
    if not isinstance(metrics_results, list):
        metrics_results = []
    a_range_ok = True
    a_live_ok = True
    a_observed = []
    for n, (start, end) in enumerate(RANGES, 1):
        expected = _expected_metrics(start, end)
        observed = _endpoint(receipt, f"metrics_r{n}")
        body = observed.get("body_json")
        http_ok = observed.get("status_code") == 200 and isinstance(body, dict)
        body_ok = http_ok and all(body.get(k) == v for k, v in expected.items())
        saved = next((r for r in metrics_results if isinstance(r, dict) and r.get("start") == start and r.get("end") == end), {})
        saved_values=saved.get('result',saved)
        saved_ok = all(saved_values.get(k) == v for k, v in expected.items())
        a_range_ok = a_range_ok and saved_ok
        a_live_ok = a_live_ok and body_ok
        a_observed.append({"range": [start, end], "expected": expected, "live_status": observed.get("status_code"), "live_body": body, "saved_record_match": saved_ok})

    api_a = '"/api/metrics/summary"' in app or "/api/metrics/summary" in app
    ui_a = "Metrics" in layout and "metrics/summary" in js and all(x in js for x in ("avg_latency_ms", "total_requests", "error_rate_pct"))
    hash_a = str(a_record.get("commit_hash", ""))
    commit_a = bool(re.fullmatch(r"[0-9a-f]{40}", hash_a)) and hash_a in commit_hashes

    b_saved = b_record.get("filters", b_record.get('verification_results',{}).get('filters',[]))
    if isinstance(b_saved,dict):b_saved=[dict(v,severity=k) for k,v in b_saved.items()]
    if not isinstance(b_saved, list):
        b_saved = []
    b_csv_ok = True
    b_counts_ok = True
    b_observed = []
    for severity, endpoint_id in (("CRITICAL", "triage_critical"), ("HIGH", "triage_high")):
        expected = _expected_incidents(severity)
        endpoint = _endpoint(receipt, endpoint_id)
        observed_rows = _archived_endpoint_csv(snapshot_root, receipt, endpoint_id)
        live_ok = endpoint.get("status_code") == 200 and observed_rows == expected
        saved = next((r for r in b_saved if isinstance(r, dict) and str(r.get("severity", "")).upper() == severity), {})
        download=saved.get('browser_download',{})
        saved_count=saved.get('row_count',saved.get('count',download.get('row_count')))
        verified=saved.get('verified') is True or (download.get('matches') is True or download.get('downloaded_csv_matches_live_api') is True)
        saved_ok = saved_count == len(expected) and verified and live_ok
        b_csv_ok = b_csv_ok and live_ok
        b_counts_ok = b_counts_ok and saved_ok
        b_observed.append({"severity": severity, "expected_count": len(expected), "observed_count": len(observed_rows), "live_status": endpoint.get("status_code"), "saved_record_match": saved_ok})

    api_b = "/api/incidents/export" in app and all(x in app for x in ("incident_id", "created_at"))
    ui_b = "Triage" in layout and "incidents/export" in js and "severity" in js.lower()
    hash_b = str(b_record.get("commit_hash", ""))
    commit_b = bool(re.fullmatch(r"[0-9a-f]{40}", hash_b)) and hash_b in commit_hashes

    root = _endpoint(receipt, "portal_root")
    health = _endpoint(receipt, "portal_health")
    root_page = snapshot_root / "portal-root.html"
    root_html = root_page.read_text(encoding="utf-8", errors="replace") if root_page.is_file() else ""
    root_ok = root.get("status_code") == 200 and "Operations Portal" in root_html
    health_ok = health.get("status_code") == 200 and (health.get("body_json") or {}).get("status") == "ok"
    main_branch = head == "ref: refs/heads/main"
    features_retained = api_a and api_b and ui_a and ui_b
    no_conflict_markers = not any(token in app + layout + js for token in ("<<<<<<<", ">>>>>>>", "======="))

    def check(cid: str, weight: float, ok: bool, evidence: Any) -> dict[str, Any]:
        return {"id": cid, "weight": weight, "passed": bool(ok), "score": float(bool(ok)), "required": True, "evidence": evidence}

    a_checks = [
        check("A01", .25, a_live_ok, a_observed),
        check("A02", .20, api_a, {"metrics_endpoint_source": api_a}),
        check("A03", .20, ui_a, {"metrics_frontend": ui_a}),
        check("A04", .20, commit_a, {"commit_hash_recorded": bool(hash_a), "commit_present_in_HEAD_log": commit_a}),
        check("A05", .15, a_range_ok, {"saved_range_results_match": a_range_ok}),
    ]
    b_checks = [
        check("B01", .25, b_csv_ok, b_observed),
        check("B02", .20, api_b, {"triage_endpoint_source": api_b}),
        check("B03", .20, ui_b, {"triage_frontend": ui_b}),
        check("B04", .20, commit_b, {"commit_hash_recorded": bool(hash_b), "commit_present_in_HEAD_log": commit_b}),
        check("B05", .15, b_counts_ok, {"saved_filter_counts_match": b_counts_ok}),
    ]
    joint = [
        check("J01", 1.0, root_ok and health_ok, {"root_http_200": root_ok, "health_http_200": health_ok}),
        check("J02", 1.0, features_retained, {"both_backend_and_frontend_features_retained": features_retained}),
        check("J03", 1.0, main_branch and no_conflict_markers and commit_a and commit_b,
              {"main_branch": main_branch, "no_conflict_markers": no_conflict_markers, "both_feature_commits_in_HEAD_log": commit_a and commit_b}),
    ]
    return make_grade(
        case_id="BC-08", run_id=run_id, actor_a_checks=a_checks, actor_b_checks=b_checks,
        joint_checks=joint, pass_threshold_a=.8, pass_threshold_b=.8,
        failure_reasons=[] if (snapshot_root / "portal.db").is_file() else ["Host-side portal database snapshot is missing."],
        run_metadata={"oracle": "BC-08 deterministic host-side evidence grader", "clean_worktree_independently_observed": False},
    )
