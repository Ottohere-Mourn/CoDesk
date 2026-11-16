#!/usr/bin/env bash
set -uo pipefail
REPO="/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112"
ROOT="/mnt/raid1/mjh/Projects/codesk-next5-20261115"
cd "$REPO"
export CO_DESK_ASSETS_ROOT="$ROOT/assets"
export CO_DESK_RUN_ROOT="$ROOT/runs/triplets"
export CO_DESK_OVERLAY_ROOT="$ROOT/overlays"
export CO_DESK_OVERLAY_ARCHIVE_ROOT="$ROOT/overlays"
export CO_DESK_CODEX_RUNTIME_ROOT="/home/mjh/.cache/codesk-next5-runtime"
export CO_DESK_API_BASE_URL="https://docode.cc/v1"
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  IFS= read -rs -p "GPT-6-Sol API key for docode.cc (hidden): " OPENAI_API_KEY || { echo "missing API key" >&2; exit 2; }
  printf '\n' >&2
fi
export OPENAI_API_KEY
status=0
for arm in ma-id shared shared-lock; do
  printf 'START v33 %s %s\n' "$arm" "$(date -u +%FT%TZ)"
  if ./scripts/run_new_case_arm.sh v33 "$arm"; then rc=0; else rc=$?; fi
  printf 'END v33 %s rc=%s %s\n' "$arm" "$rc" "$(date -u +%FT%TZ)"
  if (( rc != 0 )); then status=1; fi
done
exit "$status"
