#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: run_new_case_arm.sh <s1|k1|k2|q1|e1|v1|v2|v3|v4|v5|v6|v7|v8|v9|v10|v11|v12|v13|v14|v15|v16|v17|v18|v19|v20|v21|v22|v23|v24|v25|v26|v27> <ma-id|shared|shared-lock>" >&2
  exit 2
fi
CASE_ID="$1"; ARM="$2"
case "$CASE_ID" in
  s1) TASK_A="v2/pgs1intake"; TASK_B="v2/pgs1facilities" ;;
  k1) TASK_A="v2/pgk1filing"; TASK_B="v2/pgk1service" ;;
  k2) TASK_A="v2/pgk2route"; TASK_B="v2/pgk2defer" ;;
  q1) TASK_A="v2/pgq1route"; TASK_B="v2/pgq1defer" ;;
  e1) TASK_A="v2/pge1insert"; TASK_B="v2/pge1code" ;;
  v1) TASK_A="v2/pgv1safety"; TASK_B="v2/pgv1maint" ;;
  v2) TASK_A="v2/pgv2bins"; TASK_B="v2/pgv2cartons" ;;
  v3) TASK_A="v2/pgv3shift"; TASK_B="v2/pgv3mileage" ;;
  v4) TASK_A="v2/pgv4rooms"; TASK_B="v2/pgv4facilities" ;;
  v5) TASK_A="v2/pgv5invoices"; TASK_B="v2/pgv5expenses" ;;
  v6) TASK_A="v2/pgv6accommodations"; TASK_B="v2/pgv6seating" ;;
  v7) TASK_A="v2/pgv7labcustody"; TASK_B="v2/pgv7benchreview" ;;
  v8) TASK_A="v2/pgv8permitreview"; TASK_B="v2/pgv8permitfees" ;;
  v9) TASK_A="v2/pgv9dispatch"; TASK_B="v2/pgv9parts" ;;
  v10) TASK_A="v2/pgv10followup"; TASK_B="v2/pgv10equipment" ;;
  v11) TASK_A="v2/pgv11holds"; TASK_B="v2/pgv11returns" ;;
  v12) TASK_A="v2/pgv12review"; TASK_B="v2/pgv12intake" ;;
  v13) TASK_A="v2/pgv13catalog"; TASK_B="v2/pgv13access" ;;
  v14) TASK_A="v2/pgv14disposition"; TASK_B="v2/pgv14rework" ;;
  v15) TASK_A="v2/pgv15badge"; TASK_B="v2/pgv15induction" ;;
  v16) TASK_A="v2/pgv16temp"; TASK_B="v2/pgv16lot" ;;
  v17) TASK_A="v2/pgv17condition"; TASK_B="v2/pgv17exhibit" ;;
  v18) TASK_A="v2/pgv18commission"; TASK_B="v2/pgv18utility" ;;
  v19) TASK_A="v2/pgv19housekeeping"; TASK_B="v2/pgv19arrival" ;;
  v20) TASK_A="v2/pgv20exportdocs"; TASK_B="v2/pgv20loadplan" ;;
  v21) TASK_A="v2/pgv21accession"; TASK_B="v2/pgv21pickup" ;;
  v22) TASK_A="v2/pgv22turnover"; TASK_B="v2/pgv22techcall" ;;
  v23) TASK_A="v2/pgv23claimreview"; TASK_B="v2/pgv23repairdispatch" ;;
  v24) TASK_A="v2/pgv24advisory"; TASK_B="v2/pgv24dispatch" ;;
  v25) TASK_A="v2/pgv25containment"; TASK_B="v2/pgv25recovery" ;;
  v26) TASK_A="v2/pgv26clearance"; TASK_B="v2/pgv26release" ;;
  v27) TASK_A="v2/pgv27awardreview"; TASK_B="v2/pgv27disbursement" ;;
  *) echo "unknown case: $CASE_ID" >&2; exit 2 ;;
esac
case "$ARM" in
  ma-id) MODE="isolated"; LOCK_ARGS=() ;;
  shared) MODE="parallel"; LOCK_ARGS=() ;;
  shared-lock) MODE="parallel"; LOCK_ARGS=(--action-lock) ;;
  *) echo "unknown arm: $ARM" >&2; exit 2 ;;
esac
REPO="/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112"
OSW="/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1"
SWC="/home/mjh/Projects/CoDesk-candidate-repair-20261104"
EXTRA_CASE_SOURCE=()
if [[ "$CASE_ID" == v4 || "$CASE_ID" == v5 || "$CASE_ID" == v6 || "$CASE_ID" == v7 || "$CASE_ID" == v8 || "$CASE_ID" == v9 || "$CASE_ID" == v10 || "$CASE_ID" == v11 || "$CASE_ID" == v12 || "$CASE_ID" == v13 || "$CASE_ID" == v14 || "$CASE_ID" == v15 || "$CASE_ID" == v16 || "$CASE_ID" == v17 || "$CASE_ID" == v18 || "$CASE_ID" == v19 || "$CASE_ID" == v20 || "$CASE_ID" == v21 || "$CASE_ID" == v22 || "$CASE_ID" == v23 || "$CASE_ID" == v24 || "$CASE_ID" == v25 || "$CASE_ID" == v26 || "$CASE_ID" == v27 ]]; then
  EXTRA_CASE_SOURCE=(tasks/paragui/build_v456.py tasks/paragui/app_v456_template.py tasks/paragui/v456_data.json scripts/run_v456_guest_control.py)
fi
case "$CASE_ID" in
  s1) TASK_MODULES="pg_common.py pg_shelter1_oracle.py pg_s1.py task_pgs1intake.py task_pgs1facilities.py" ;;
  k1) TASK_MODULES="pg_common.py pg_k1_oracle.py pg_k1.py task_pgk1filing.py task_pgk1service.py" ;;
  k2) TASK_MODULES="pg_common.py pg_k2_oracle.py pg_k2.py task_pgk2route.py task_pgk2defer.py" ;;
  q1) TASK_MODULES="pg_common.py pg_q1_oracle.py pg_q1.py task_pgq1route.py task_pgq1defer.py" ;;
  e1) TASK_MODULES="pg_common.py pg_e1_oracle.py pg_e1.py task_pge1insert.py task_pge1code.py" ;;
  v1) TASK_MODULES="pg_common.py pg_v1_oracle.py pg_v1.py task_pgv1safety.py task_pgv1maint.py" ;;
  v2) TASK_MODULES="pg_common.py pg_v2_oracle.py pg_v2.py task_pgv2bins.py task_pgv2cartons.py" ;;
  v3) TASK_MODULES="pg_common.py pg_v3_oracle.py pg_v3.py task_pgv3shift.py task_pgv3mileage.py" ;;
  v4) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v4.py task_pgv4rooms.py task_pgv4facilities.py" ;;
  v5) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v5.py task_pgv5invoices.py task_pgv5expenses.py" ;;
  v6) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v6.py task_pgv6accommodations.py task_pgv6seating.py" ;;
  v7) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v7.py task_pgv7labcustody.py task_pgv7benchreview.py" ;;
  v8) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v8.py task_pgv8permitreview.py task_pgv8permitfees.py" ;;
  v9) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v9.py task_pgv9dispatch.py task_pgv9parts.py" ;;
  v10) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v10.py task_pgv10followup.py task_pgv10equipment.py" ;;
  v11) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v11.py task_pgv11holds.py task_pgv11returns.py" ;;
  v12) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v12.py task_pgv12review.py task_pgv12intake.py" ;;
  v13) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v13.py task_pgv13catalog.py task_pgv13access.py" ;;
  v14) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v14.py task_pgv14disposition.py task_pgv14rework.py" ;;
  v15) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v15.py task_pgv15badge.py task_pgv15induction.py" ;;
  v16) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v16.py task_pgv16temp.py task_pgv16lot.py" ;;
  v17) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v17.py task_pgv17condition.py task_pgv17exhibit.py" ;;
  v18) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v18.py task_pgv18commission.py task_pgv18utility.py" ;;
  v19) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v19.py task_pgv19housekeeping.py task_pgv19arrival.py" ;;
  v20) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v20.py task_pgv20exportdocs.py task_pgv20loadplan.py" ;;
  v21) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v21.py task_pgv21accession.py task_pgv21pickup.py" ;;
  v22) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v22.py task_pgv22turnover.py task_pgv22techcall.py" ;;
  v23) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v23.py task_pgv23claimreview.py task_pgv23repairdispatch.py" ;;
  v24) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v24.py task_pgv24advisory.py task_pgv24dispatch.py" ;;
  v25) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v25.py task_pgv25containment.py task_pgv25recovery.py" ;;
  v26) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v26.py task_pgv26clearance.py task_pgv26release.py" ;;
  v27) TASK_MODULES="pg_common.py pg_v456_oracle.py pg_v27.py task_pgv27awardreview.py task_pgv27disbursement.py" ;;
esac
for module in $TASK_MODULES; do
  source_module="$REPO/tasks/paragui/$module"
  runtime_module="$OSW/evaluation_examples/task_class/$module"
  if [[ ! -f "$source_module" || ! -f "$runtime_module" ]] || ! cmp -s "$source_module" "$runtime_module"; then
    echo "task module drift: $module (source/runtime missing or different); refusing to start Guest/model run" >&2
    exit 3
  fi
done
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  IFS= read -r OPENAI_API_KEY || { echo "missing API key on stdin" >&2; exit 2; }
fi
OPENAI_API_KEY="$(printf '%s' "$OPENAI_API_KEY" | tr -d '\r')"
if [[ -z "$OPENAI_API_KEY" ]]; then echo "empty API key" >&2; exit 2; fi
API_BASE_URL="${CO_DESK_API_BASE_URL:-https://api.haogpt.net/v1}"
export OPENAI_API_KEY OPENAI_BASE_URL="$API_BASE_URL"
ASSETS="${CO_DESK_ASSETS_ROOT:-/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets}"
BASE="/dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2"
OVERLAY_TMP_ROOT="${CO_DESK_OVERLAY_ROOT:-/dev/shm/codesk-next3/overlays}"
OVERLAY_ARCHIVE_ROOT="${CO_DESK_OVERLAY_ARCHIVE_ROOT:-/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays}"
SWCUB_OSWORLD_VM_READY_TIMEOUT=600
export SWCUB_OSWORLD_VM_READY_TIMEOUT
OUT_ROOT="${CO_DESK_RUN_ROOT:-/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets}"
RUN_ID="cdesk3-"$CASE_ID"-"$ARM"-$(date -u +%Y%m%dT%H%M%SZ)-"$$
OUT="$OUT_ROOT/$RUN_ID"
OVERLAYS="$OVERLAY_TMP_ROOT/$RUN_ID"
OVERLAY_ARCHIVE="$OVERLAY_ARCHIVE_ROOT/$RUN_ID"
mkdir -p "$OUT/resources" "$OVERLAYS"
test -r "$BASE" || { echo "staged tmpfs Guest image missing: $BASE" >&2; exit 2; }
(
  cd "$ASSETS/$CASE_ID"
  find . -type f -print0 | sort -z | xargs -0 sha256sum > "$OUT/fixture.sha256"
)
(
  cd "$REPO"
  sha256sum oscombo/cli.py oscombo/runner.py oscombo/desktop_tools.py oscombo/harness/external.py scripts/run_new_case_arm.sh tasks/paragui/task_pg*.py tasks/paragui/pg_*.py "${EXTRA_CASE_SOURCE[@]}" > "$OUT/source.sha256"
)
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS" OSCOMBO_GUEST_IMAGE="$BASE"
export PYTHONPATH="$REPO:$SWC:$OSW"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="swcub/osworld-v2.1-qemu-runtime:local"
export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$OVERLAYS"
export SWCUB_RUN_ID="$RUN_ID" SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
export SWCUB_RESOURCE_LEDGER="$OUT/resources/resource_ledger.jsonl"
cd "$REPO"
CMD=("$OSW/.venv/bin/python" -m oscombo run \
  --mode "$MODE" --tasks "$TASK_A" "$TASK_B" --out "$OUT" \
  --harness codex --model gpt-6-sol --effort high --max-steps 60 --setup-settle 25 \
  --opt codex_bin=/home/mjh/.local/share/codesk-case3-tools/codex \
  --opt base_url="$API_BASE_URL" --opt timeout=2400 \
  --opt codex_runtime_root=/home/mjh/.cache/codesk-next3-runtime/$RUN_ID \
  --label run="$RUN_ID" --label case="$CASE_ID" --label arm="$ARM" \
  --label gui_tool_call_budget=60 --label model=gpt-6-sol --label endpoint="$API_BASE_URL")
if [[ "$ARM" == "shared-lock" ]]; then CMD+=(--action-lock); fi
set +e
"${CMD[@]}"
RUN_STATUS=$?
set -e
mkdir -p "$OVERLAY_ARCHIVE"
if [[ "$OVERLAYS" != "$OVERLAY_ARCHIVE" ]]; then mkdir -p "$OVERLAY_ARCHIVE"; cp -r --sparse=auto --no-preserve=all "$OVERLAYS"/. "$OVERLAY_ARCHIVE"/ || echo "warning: could not archive overlay" >&2; fi
exit "$RUN_STATUS"
