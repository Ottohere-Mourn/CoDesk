"""Hidden-state and regression oracle for CDD-BV-LITE-001."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from . import CASE_ID, CASE_VERSION
from . import spec


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_candidate(path: Path):
    module_spec = importlib.util.spec_from_file_location(f"bv_candidate_{os.getpid()}", path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError("cannot load filter implementation")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if not callable(getattr(module, "filter_orders", None)):
        raise TypeError("missing callable filter_orders")
    return module


def _python_filter_check(workspace: Path) -> dict[str, Any]:
    rows = json.loads((workspace / spec.DATA_FILE).read_text(encoding="utf-8"))
    try:
        module = _load_candidate(workspace / spec.FILTER_FILE)
    except Exception as exc:
        return {"pass": False, "cases": [], "error_type": type(exc).__name__,
                "error": str(exc)[:500]}
    cases = []
    for test in spec.ORACLE_CASES:
        try:
            got = module.filter_orders(rows, test["query"], test["status"])
            ids = [row.get("order_id") for row in got]
        except Exception as exc:
            cases.append({"query": test["query"], "status": test["status"],
                          "expected_ids": list(test["ids"]), "actual_ids": None,
                          "pass": False})
            return {"pass": False, "cases": cases,
                    "error_type": type(exc).__name__, "error": str(exc)[:500]}
        cases.append({"query": test["query"], "status": test["status"],
                      "expected_ids": list(test["ids"]), "actual_ids": ids,
                      "pass": ids == list(test["ids"])})
    return {"pass": all(case["pass"] for case in cases), "cases": cases}


_NODE_UI_DRIVER = r'''const fs = require("fs");
const app = require(process.argv[2]);
const rows = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
function node(id) { return {id, value: id === "order-status" ? "All" : "", innerHTML: "", textContent: "", hidden: true,
  listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }}; }
const ids = ["filter-form", "order-query", "order-status", "order-results", "result-count", "empty-state", "apply-filters", "clear-filters"];
const nodes = Object.fromEntries(ids.map(id => [id, node(id)]));
const doc = {getElementById(id) { if (!nodes[id]) throw new Error("missing element " + id); return nodes[id]; }};
const telemetry = [];
const navigations = [];
function expectedFilter(query, status) {
  const q = String(query || "").trim().toLowerCase();
  return rows.filter(row => (!status || status === "All" || row.status === status) &&
    (!q || [row.order_id, row.customer, row.region].some(v => String(v).toLowerCase().includes(q))));
}
async function fetchImpl(url, options={}) {
  if (url.startsWith("/api/orders?")) {
    const u = new URL(url, "http://local");
    return {json: async () => ({orders: expectedFilter(u.searchParams.get("query"), u.searchParams.get("status"))})};
  }
  if (url === "/api/test-events") { telemetry.push(JSON.parse(options.body)); return {json: async () => ({recorded:true})}; }
  throw new Error("unexpected fetch " + url);
}
function evt(submitter) { let prevented = false; return {submitter, preventDefault(){prevented=true;}, wasPrevented(){return prevented;}}; }
(async()=>{
  if (!app || typeof app.mount !== "function") throw new Error("app.js must export mount for the UI contract harness");
  const controller = app.mount(doc, fetchImpl, url => navigations.push(url));
  await controller.ready;
  nodes["order-query"].value = " Dana "; nodes["order-status"].value = "Processing";
  nodes["order-query"].listeners.keydown({key:"Enter"});
  const enter = evt(nodes["apply-filters"]); await nodes["filter-form"].listeners.submit(enter);
  if (!enter.wasPrevented()) throw new Error("Enter submit did not prevent native document navigation");
  nodes["order-query"].value = "west"; nodes["order-status"].value = "Processing";
  nodes["apply-filters"].listeners.pointerdown();
  const button = evt(nodes["apply-filters"]); await nodes["filter-form"].listeners.submit(button);
  if (!button.wasPrevented()) throw new Error("button submit did not prevent navigation");
  if (telemetry.filter(e=>e.method==="enter").length !== 1 || telemetry.filter(e=>e.method==="button").length !== 1)
    throw new Error("Enter and button did not use the shared submit path");
  if (navigations.length) throw new Error("unexpected document navigation");
  if (!nodes["result-count"].textContent.includes("3 orders")) throw new Error("result count was not updated after button filtering");
  console.log(JSON.stringify({pass:true, telemetry, result_count:nodes["result-count"].textContent}));
})().catch(error=>{console.error(error.stack||String(error));process.exit(1);});
'''


def _ui_contract_check(workspace: Path) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return {"pass": False, "status": "UNAVAILABLE", "reason": "Node.js is required for the small UI event contract test"}
    rows = workspace / spec.DATA_FILE
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", encoding="utf-8", delete=False) as f:
        f.write(_NODE_UI_DRIVER)
        driver = Path(f.name)
    try:
        result = subprocess.run([node, str(driver), str(workspace / spec.APP_FILE), str(rows)],
                                cwd=workspace, capture_output=True, text=True, timeout=5,
                                env={"PATH": os.environ.get("PATH", ""), "NODE_NO_WARNINGS": "1"}, check=False)
        return {"pass": result.returncode == 0, "status": "PASS" if result.returncode == 0 else "FAIL",
                "stdout": result.stdout[-8000:], "stderr": result.stderr[-4000:],
                "method": "Node.js fake-DOM event contract; not a real browser"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"pass": False, "status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}
    finally:
        driver.unlink(missing_ok=True)


def _browser_retest(events: list[dict[str, Any]], condition: str, final_filter_hash: str) -> dict[str, Any]:
    tester = "S" if condition == "single_agent" else "B"
    target_cases = [("button", "NW-2402", "Processing", [])]
    if condition == "single_agent":
        target_cases.insert(0, ("enter", "dana", "Processing", ["NW-2403"]))
    tested = []
    for method, query, status, expected in target_cases:
        normalized_query = query.strip().casefold()
        # Keep latest matching result per test instance; events are time ordered.
        candidate = next((e for e in reversed(events) if e.get("event") == "browser_test"
                          and e.get("actor") == tester
                          and e.get("details", {}).get("method") == method
                          and str(e.get("details", {}).get("query", "")).strip().casefold() == normalized_query
                          and e.get("details", {}).get("status") == status
                          and e.get("details", {}).get("filter_source_sha256") == final_filter_hash), None)
        details = candidate.get("details", {}) if candidate else {}
        actual = details.get("visible_ids_server", [])
        passed = bool(candidate) and actual == expected and details.get("visible_ids_client") == expected \
            and details.get("client_server_match") is True
        tested.append({"method": method, "query": query, "status": status,
                       "expected_ids": expected, "actual_ids": actual, "pass": passed})
    return {"pass": all(row["pass"] for row in tested), "tester_actor": tester, "cases": tested}


def _baseline_repro(events: list[dict[str, Any]], condition: str,
                    initial_filter_hash: str) -> dict[str, Any]:
    if condition == "single_agent":
        return {"pass": True, "required": False}
    expected = ["NW-2402", "NW-2403", "NW-2406"]
    candidate = next((event for event in events if event.get("event") == "browser_test"
                      and event.get("actor") == "B"
                      and event.get("details", {}).get("method") == "enter"
                      and str(event.get("details", {}).get("query", "")).strip().casefold() == "dana"
                      and event.get("details", {}).get("status") == "Processing"
                      and event.get("details", {}).get("filter_source_sha256") == initial_filter_hash), None)
    details = candidate.get("details", {}) if candidate else {}
    passed = bool(candidate) and details.get("visible_ids_client") == expected \
        and details.get("visible_ids_server") == expected \
        and details.get("client_server_match") is True
    return {"pass": passed, "required": True, "expected_ids": expected,
            "actual_ids": details.get("visible_ids_server", [])}


def evaluate(run_root: str | Path, condition: str | None = None) -> dict[str, Any]:
    root = Path(run_root).resolve()
    baseline_path = root / "oracle" / "baseline_manifest.json"
    manifest = json.loads(baseline_path.read_text(encoding="utf-8"))
    config = json.loads((root / "run_config.json").read_text(encoding="utf-8"))
    condition = condition or config["condition"]
    workspace = root / "workspace"
    data_hash = _sha(workspace / spec.DATA_FILE)
    fixture_integrity = data_hash == manifest["orders_json_sha256"]
    protected = {name: {"expected": digest,
                        "actual": _sha(workspace / name) if (workspace / name).is_file() else None,
                        "pass": (workspace / name).is_file() and _sha(workspace / name) == digest}
                 for name, digest in manifest["protected_files"].items()}
    python_check = _python_filter_check(workspace)
    ui_check = _ui_contract_check(workspace)
    index_html = (workspace / "static" / "index.html").read_text(encoding="utf-8")
    markup_accessibility = all(token in index_html for token in (
        '<label for="order-query">', '<label for="order-status">',
        'role="status" aria-live="polite"', 'id="apply-filters" type="submit"',
    ))
    filter_path = workspace / spec.FILTER_FILE
    current_filter_hash = _sha(filter_path) if filter_path.is_file() else ""
    events = _jsonl(root / "web_events.jsonl")
    initial_filter_hash = json.loads((root / "run_config.template.json").read_text(
        encoding="utf-8"))["workspace_initial_sha256"][spec.FILTER_FILE]
    baseline = _baseline_repro(events, condition, initial_filter_hash)
    retest = _browser_retest(events, condition, current_filter_hash)
    protocol_events = _jsonl(root / "collaboration" / "events.jsonl")
    messages = [e for e in protocol_events if e.get("type") == "message"]
    message_metrics = {"total_messages": len(messages),
                       "A_to_B": sum(e.get("actor") == "A" and e.get("recipient") in ("B", "all") for e in messages),
                       "B_to_A": sum(e.get("actor") == "B" and e.get("recipient") in ("A", "all") for e in messages),
                       "attachments": sum(e.get("type") == "attachment" for e in protocol_events)}
    state_checks = {
        "fixture_integrity_pass": fixture_integrity,
        "protected_files_pass": all(row["pass"] for row in protected.values()),
        "python_filter_acceptance_pass": python_check["pass"],
        "keyboard_ui_contract_pass": ui_check["pass"],
        "accessible_filter_markup_pass": markup_accessibility,
        "browser_baseline_repro_pass": baseline["pass"],
        "browser_retest_pass": retest["pass"],
    }
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": config["run_id"],
        "condition": condition, "joint_business_success": all(state_checks.values()),
        "checks": state_checks,
        "code_revision": {"filtering.py": current_filter_hash,
                          "static/app.js": _sha(workspace / spec.APP_FILE)},
        "python_filter_tests": python_check, "ui_event_contract": ui_check,
        "accessible_filter_markup_pass": markup_accessibility,
        "browser_baseline_repro": baseline, "browser_retest": retest,
        "protected_files": protected,
        "message_metrics": message_metrics,
        "observed_interference": "NOT_INFERRED_BY_ORACLE; correlate external GUI action/focus traces before attribution",
        "limitations": ["Node fake-DOM contract is not a real browser/Guest run",
                        "web_events are application telemetry; pair with actual GUI action provenance",
                        "message counts do not establish substantive collaboration"],
    }
