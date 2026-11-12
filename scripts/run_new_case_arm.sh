#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: run_new_case_arm.sh <s1|k1|k2> <ma-id|shared|shared-lock>" >&2
  exit 2
fi
CASE_ID="$1"; ARM="$2"
case "$CASE_ID" in
  s1) TASK_A="v2/pgs1intake"; TASK_B="v2/pgs1facilities" ;;
  k1) TASK_A="v2/pgk1filing"; TASK_B="v2/pgk1service" ;;
  k2) TASK_A="v2/pgk2route"; TASK_B="v2/pgk2defer" ;;
  *) echo "unknown case: $CASE_ID" >&2; exit 2 ;;
esac
case "$ARM" in
  ma-id) MODE="isolated"; LOCK_ARGS=() ;;
  shared) MODE="parallel"; LOCK_ARGS=() ;;
  shared-lock) MODE="parallel"; LOCK_ARGS=(--action-lock) ;;
  *) echo "unknown arm: $ARM" >&2; exit 2 ;;
esac
IFS= read -r OPENAI_API_KEY || { echo "missing API key on stdin" >&2; exit 2; }
OPENAI_API_KEY="$(printf '%s' "$OPENAI_API_KEY" | tr -d '\r')"
if [[ -z "$OPENAI_API_KEY" ]]; then echo "empty API key" >&2; exit 2; fi
export OPENAI_API_KEY OPENAI_BASE_URL="https://docode.cc/v1"
REPO="/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112"
OSW="/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1"
SWC="/home/mjh/Projects/CoDesk-candidate-repair-20261104"
ASSETS="/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets"
BASE="/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"
OVERLAYS="/mnt/raid1/mjh/Projects/codesk-next3-20261112/overlays"
OUT_ROOT="/mnt/raid1/mjh/Projects/codesk-next3-20261112/runs/triplets"
RUN_ID="cdesk3-"$CASE_ID"-"$ARM"-$(date -u +%Y%m%dT%H%M%SZ)-"$$
OUT="$OUT_ROOT/$RUN_ID"
mkdir -p "$OUT/resources" "$OVERLAYS"
(
  cd "$ASSETS/$CASE_ID"
  sha256sum app_*.py seed.db expected.json > "$OUT/fixture.sha256"
)
(
  cd "$REPO"
  sha256sum oscombo/cli.py oscombo/runner.py oscombo/desktop_tools.py oscombo/harness/external.py tasks/paragui/task_pg*.py tasks/paragui/pg_*.py > "$OUT/source.sha256"
)
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS" OSCOMBO_GUEST_IMAGE="$BASE"
export PYTHONPATH="$REPO:$SWC:$OSW"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="swcub/osworld-v2.1-qemu-runtime:local"
export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$OVERLAYS"
export SWCUB_RUN_ID="$RUN_ID" SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
export SWCUB_RESOURCE_LEDGER="$OUT/resources/resource_ledger.jsonl"
cd "$REPO"
exec "$OSW/.venv/bin/python" -m oscombo run \
  --mode "$MODE" --tasks "$TASK_A" "$TASK_B" --out "$OUT" \
  --harness codex --model gpt-6-sol --effort high --max-steps 45 --setup-settle 25 \
  --opt codex_bin=/home/mjh/.local/share/codesk-case3-tools/codex \
  --opt base_url=https://docode.cc/v1 --opt timeout=2400 \
  --label run="$RUN_ID" --label case="$CASE_ID" --label arm="$ARM" \
  --label gui_tool_call_budget=45 --label model=gpt-6-sol --label endpoint=https://docode.cc/v1 \
  "$LOCK_ARGS[@]"
