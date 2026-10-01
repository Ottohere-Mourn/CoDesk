#!/usr/bin/env bash
# Five bounded scripted A-01 controls; stops if a prerequisite or expected mechanism check fails.
set -euo pipefail
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
artifact_parent=/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/browser-context-v1
run_one() {
  local condition=$1
  local run_id=$2
  local expectation=$3
  shift 3
  "$CODESK_PYTHON" scripts/run_browser_context_v1.py \
    --condition "$condition" --run-id "$run_id" \
    --artifact-parent "$artifact_parent" "$@"
  "$CODESK_PYTHON" - "$artifact_parent/$run_id/report.json" "$expectation" <<'PY'
import json, sys
report=json.load(open(sys.argv[1]))
expect=sys.argv[2]
ledger=report.get("resource_lifecycle") or {}
assert report.get("status")=="completed", report.get("error")
assert report.get("task_version")=="1.0.0-rc4"
assert report.get("reset_success") is True
assert ledger.get("all_containers_have_destroy_record") is True
assert ledger.get("labels_consistent") is True
e=report["evaluation"]
if expect=="positive":
    assert report["condition_success"] is True, e
elif expect=="negative":
    assert report["condition_success"] is False, e
    assert e["application_context_evidence"]["application_context_evidence"]=="supported", e
    assert e["wrong_page_action_supported"] is True, e
elif expect=="recovery":
    assert report["condition_success"] is True, e
    assert e["recovery_supported"] is True, e
else:
    raise AssertionError(expect)
print("GATE_PASS", report["run_id"], expect, flush=True)
PY
}
run_one solo_a a01-soloa-20261001-r04 positive
run_one solo_b a01-solob-20261001-r03 positive
run_one ma_id a01-maid-20261001-r02 positive
run_one ma_sd a01-masd-20261001-r01 negative
run_one ma_sd a01-masd-recovery-20261001-r01 recovery --recovery
