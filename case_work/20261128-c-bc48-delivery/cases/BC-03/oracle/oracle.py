"""Host-side offline Oracle for BC-03. Never copy this directory into the Guest."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import yaml

from pipeline.grade import make_grade


WEBHOOK = "http://127.0.0.1:8080/hooks/ops-alerts"
LIMITS = {
    "/api/orders": {"requests_per_minute": 120, "burst": 20, "enabled": True},
    "/api/invoices": {"requests_per_minute": 45, "burst": 8, "enabled": True},
    "/api/export": {"requests_per_minute": 12, "burst": 3, "enabled": True},
}
ALERTS = {
    "LATENCY-P95": {"metric": "latency_p95_ms", "operator": ">", "threshold": 750.0, "severity": "warning", "enabled": True},
    "ERROR-RATE": {"metric": "error_rate_pct", "operator": ">", "threshold": 2.5, "severity": "critical", "enabled": True},
    "QUOTA-REJECTS": {"metric": "quota_rejects_per_min", "operator": ">", "threshold": 20.0, "severity": "warning", "enabled": True},
}


def _check(check_id, weight, passed, evidence, *, required=True, score=None):
    return {
        "id": check_id, "weight": weight, "passed": bool(passed),
        "score": float(bool(passed)) if score is None else max(0.0, min(1.0, float(score))),
        "required": required, "evidence": evidence,
    }


def _read_yaml(path: Path) -> tuple[dict, str | None]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return (value if isinstance(value, dict) else {}), None
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:180]}"


def _read_db(path: Path) -> tuple[dict, str | None]:
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            quotas = {row["route"]: dict(row) for row in connection.execute("SELECT route,requests_per_minute,burst,enabled,updated_at FROM rate_quotas")}
            alerts = {row["rule_id"]: dict(row) for row in connection.execute("SELECT rule_id,metric,operator,threshold,severity,enabled,webhook_url FROM alert_rules")}
        finally:
            connection.close()
        return {"rate_quotas": quotas, "alert_rules": alerts}, None
    except (OSError, sqlite3.Error, KeyError) as exc:
        return {"rate_quotas": {}, "alert_rules": {}}, f"{type(exc).__name__}: {str(exc)[:180]}"


def _json_file(path: Path) -> tuple[dict, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return (value if isinstance(value, dict) else {}), None
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:180]}"


def _check_limit(config: dict, db: dict, route: str, expected: dict) -> bool:
    limits = config.get("rate_limits", {})
    if not isinstance(limits, dict):
        limits = {}
    db_rows = db.get("rate_quotas", {})
    if not isinstance(db_rows, dict):
        db_rows = {}
    item = limits.get(route, {})
    row = db_rows.get(route, {})
    return (
        item.get("requests_per_minute") == expected["requests_per_minute"]
        and item.get("burst") == expected["burst"]
        and item.get("enabled") is True
        and row.get("requests_per_minute") == expected["requests_per_minute"]
        and row.get("burst") == expected["burst"]
        and row.get("enabled") == 1
    )


def _check_alert(config: dict, db: dict, rule_id: str, expected: dict) -> bool:
    section = config.get("alerts", {})
    rules = section.get("rules", {}) if isinstance(section, dict) else {}
    item = rules.get(rule_id, {}) if isinstance(rules, dict) else {}
    db_rows = db.get("alert_rules", {})
    row = db_rows.get(rule_id, {}) if isinstance(db_rows, dict) else {}
    return all(item.get(key) == value for key, value in expected.items()) and all(
        row.get(key) == value for key, value in expected.items()
    ) and row.get("webhook_url") == WEBHOOK


def grade_case(
    gateway_root: str | Path,
    loaded_state_snapshot: dict | None,
    run_id: str = "offline",
) -> dict:
    root = Path(gateway_root)
    config, yaml_error = _read_yaml(root / "config.yaml")
    database, db_error = _read_db(root / "metrics.db")
    a_verification, a_json_error = _json_file(root / "rate_limit_verification.json")
    b_verification, b_json_error = _json_file(root / "alert_verification.json")

    actor_a = []
    limit_hits = [_check_limit(config, database, route, target) for route, target in LIMITS.items()]
    for i, (route, passed) in enumerate(zip(LIMITS, limit_hits), 1):
        actor_a.append(_check(f"A{i:02d}", 0.12, passed, {"route": route, "matches_yaml_and_db": passed}))
    actor_a.append(_check("A04", 0.30, all(limit_hits), {"route_matches": dict(zip(LIMITS, limit_hits))}, score=sum(limit_hits) / 3))
    runtime_config = loaded_state_snapshot.get("config", {}) if isinstance(loaded_state_snapshot, dict) else {}
    if not isinstance(runtime_config, dict):
        runtime_config = {}
    endpoint_statuses = loaded_state_snapshot.get("endpoint_statuses", {}) if isinstance(loaded_state_snapshot, dict) else {}
    if not isinstance(endpoint_statuses, dict):
        endpoint_statuses = {}
    runtime_db_state = loaded_state_snapshot.get("database", {}) if isinstance(loaded_state_snapshot, dict) else {}
    if not isinstance(runtime_db_state, dict):
        runtime_db_state = {}
    runtime_db_rows = runtime_db_state.get("rate_quotas", [])
    if not isinstance(runtime_db_rows, list):
        runtime_db_rows = []
    runtime_db = {"rate_quotas": {row.get("route"): row for row in runtime_db_rows if isinstance(row, dict)}}
    runtime_limit_hits = [_check_limit(runtime_config, runtime_db, route, target) for route, target in LIMITS.items()]
    runtime_page_ok = bool(loaded_state_snapshot) and all(runtime_limit_hits) and loaded_state_snapshot.get("rate_limit_active") is True and endpoint_statuses.get("rate-limit") == 200
    actor_a.append(_check("A05", 0.12, runtime_page_ok, {"runtime_routes_ok": all(runtime_limit_hits), "runtime_page_active": bool(loaded_state_snapshot and loaded_state_snapshot.get("rate_limit_active")), "endpoint_status": endpoint_statuses.get("rate-limit")}))
    a_routes = a_verification.get('routes', a_verification.get('route_results',[]))
    if isinstance(a_routes,dict):a_routes=[dict(v,route=k) for k,v in a_routes.items() if isinstance(v,dict)]
    def record_ok(doc, rows, id_key, targets, url):
        by={x.get(id_key):x for x in rows if isinstance(x,dict)} if isinstance(rows,list) else {}
        page=''.join(x for x in str(doc.get('page_status','')).upper() if x.isalpha())
        return (doc.get('service_url')==url and bool(doc.get('checked_at_utc',doc.get('check_time'))) and
                page in ('GREENACTIVE','GREEN璺疉CTIVE') and doc.get('all_green') is True and set(by)==set(targets) and
                all(all(by[k].get(field)==v for field,v in target.items()) for k,target in targets.items()))
    a_record_matches = record_ok(a_verification,a_routes,'route',LIMITS,'http://127.0.0.1:8080/rate-limit')
    actor_a.append(_check("A06", 0.12, a_record_matches, {"json_error": a_json_error, "all_green": a_verification.get("all_green"), "route_count": len(a_routes) if isinstance(a_routes, list) else 0}))
    alerts_for_structure = config.get("alerts", {})
    untouched = (
        config.get("server") == {"bind": "127.0.0.1", "port": 8080}
        and isinstance(config.get("logging"), dict)
        and config.get("logging", {}).get("level") == "info"
        and isinstance(alerts_for_structure, dict)
        and isinstance(alerts_for_structure.get("rules"), dict)
        and isinstance(alerts_for_structure.get("webhook_url"), str)
    )
    actor_a.append(_check("A07", 0.10, untouched, {"server_and_logging_preserved": untouched}, required=False))

    actor_b = []
    alerts_section = config.get("alerts", {})
    if not isinstance(alerts_section, dict):
        alerts_section = {}
    b_webhook_ok = alerts_section.get("webhook_url") == WEBHOOK
    actor_b.append(_check("B01", 0.15, b_webhook_ok, {"webhook_url": alerts_section.get("webhook_url")}))
    alert_hits = [_check_alert(config, database, rule_id, target) for rule_id, target in ALERTS.items()]
    for i, (rule_id, passed) in enumerate(zip(ALERTS, alert_hits), 2):
        actor_b.append(_check(f"B{i:02d}", 0.12, passed, {"rule_id": rule_id, "matches_yaml_and_db": passed}))
    actor_b.append(_check("B05", 0.30, all(alert_hits), {"rule_matches": dict(zip(ALERTS, alert_hits))}, score=sum(alert_hits) / 3))
    runtime_alert_cfg = runtime_config.get("alerts", {}) if isinstance(runtime_config, dict) else {}
    if not isinstance(runtime_alert_cfg, dict):
        runtime_alert_cfg = {}
    runtime_alert_rows = runtime_db_state.get("alert_rules", [])
    if not isinstance(runtime_alert_rows, list):
        runtime_alert_rows = []
    runtime_alert_db = {"alert_rules": {row.get("rule_id"): row for row in runtime_alert_rows if isinstance(row, dict)}}
    runtime_alert_hits = [_check_alert(runtime_config, runtime_alert_db, rule_id, target) for rule_id, target in ALERTS.items()]
    runtime_webhook_ok = runtime_alert_cfg.get("webhook_url") == WEBHOOK
    runtime_alerts_ok = bool(loaded_state_snapshot) and runtime_webhook_ok and all(runtime_alert_hits) and loaded_state_snapshot.get("alerts_active") is True and endpoint_statuses.get("alerts") == 200
    actor_b.append(_check("B06", 0.09, runtime_alerts_ok, {"runtime_webhook_ok": runtime_webhook_ok, "runtime_rules_ok": all(runtime_alert_hits), "active": bool(loaded_state_snapshot and loaded_state_snapshot.get("alerts_active")), "endpoint_status": endpoint_statuses.get("alerts")}))
    b_rules = b_verification.get('rules', b_verification.get('rule_results',[]))
    if isinstance(b_rules,dict):b_rules=[dict(v,rule_id=k) for k,v in b_rules.items() if isinstance(v,dict)]
    b_record_matches = record_ok(b_verification,b_rules,'rule_id',ALERTS,'http://127.0.0.1:8080/alerts') and b_verification.get('webhook_url')==WEBHOOK
    actor_b.append(_check("B07", 0.10, b_record_matches, {"json_error": b_json_error, "all_green": b_verification.get("all_green"), "rule_count": len(b_rules) if isinstance(b_rules, list) else 0}))

    joint_config = (
        all(_check_limit(config, database, route, target) for route, target in LIMITS.items())
        and alerts_section.get("webhook_url") == WEBHOOK
        and all(_check_alert(config, database, rule_id, target) for rule_id, target in ALERTS.items())
        and yaml_error is None
    )
    db_full = len(database.get("rate_quotas", {})) == 3 and len(database.get("alert_rules", {})) == 3 and db_error is None
    runtime_joint = (
        runtime_limit_hits == [True, True, True] and runtime_alert_hits == [True, True, True]
        and loaded_state_snapshot is not None
        and loaded_state_snapshot.get("rate_limit_active") is True
        and loaded_state_snapshot.get("alerts_active") is True
        and endpoint_statuses.get("rate-limit") == 200
        and endpoint_statuses.get("alerts") == 200
    )
    joint = [
        _check("J01", 1.0, joint_config, {"yaml_parse_error": yaml_error, "both_sections_complete": joint_config}),
        _check("J02", 1.0, db_full, {"db_error": db_error, "quota_count": len(database.get("rate_quotas", {})), "alert_count": len(database.get("alert_rules", {}))}),
        _check("J03", 1.0, runtime_joint, {"loaded_snapshot_present": loaded_state_snapshot is not None, "runtime_consistent": runtime_joint}),
        _check("J04", 1.0, a_record_matches and b_record_matches, {"actor_a_record_ok": a_record_matches, "actor_b_record_ok": b_record_matches}),
    ]
    reasons = [message for message in (
        f"config.yaml could not be parsed: {yaml_error}" if yaml_error else "",
        f"metrics.db could not be read: {db_error}" if db_error else "",
        f"rate verification record is invalid: {a_json_error}" if a_json_error else "",
        f"alert verification record is invalid: {b_json_error}" if b_json_error else "",
        "The host-collected loaded-service snapshot is missing." if loaded_state_snapshot is None else "",
    ) if message]
    return make_grade(
        case_id="BC-03", run_id=run_id, actor_a_checks=actor_a, actor_b_checks=actor_b,
        joint_checks=joint, pass_threshold_a=0.80, pass_threshold_b=0.80,
        failure_reasons=reasons,
        run_metadata={"oracle": "BC-03 offline deterministic", "gateway_root": str(root)},
    )


def grade_episode(snapshot_root: Path, receipt: dict, run_id: str) -> dict:
    """Use host-fetched runtime and endpoint receipts plus recovered files."""
    endpoints = receipt.get("http_endpoints", {}) if isinstance(receipt, dict) else {}
    runtime_row = endpoints.get("runtime", {}) if isinstance(endpoints, dict) else {}
    runtime = runtime_row.get("body_json") if isinstance(runtime_row, dict) else None
    if isinstance(runtime, dict):
        rate = endpoints.get("rate_limit", {})
        alerts = endpoints.get("alerts", {})
        runtime = dict(runtime)
        runtime["endpoint_statuses"] = {
            "rate-limit": rate.get("status_code") if isinstance(rate, dict) else None,
            "alerts": alerts.get("status_code") if isinstance(alerts, dict) else None,
        }
    return grade_case(snapshot_root.parent / "guest-output" / "gateway", runtime, run_id)
