#!/usr/bin/env bash
set -uo pipefail
REPO="/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112"
ROOT="/mnt/raid1/mjh/Projects/codesk-next5-20261115"
cd "$REPO"
export CO_DESK_ASSETS_ROOT="$ROOT/assets"
export CO_DESK_RUN_ROOT="$ROOT/runs/triplets"
# Keep the transient QEMU overlays on RAID too; /dev/shm is nearly full of preserved older overlays.
export CO_DESK_OVERLAY_ROOT="$ROOT/overlays"
export CO_DESK_OVERLAY_ARCHIVE_ROOT="$ROOT/overlays"
# Codex writes/chmods config.toml, which the RAID FUSE mount does not permit reliably.
# This small private runtime metadata lives on local ext4; all experiment evidence stays on RAID.
export CO_DESK_CODEX_RUNTIME_ROOT="/home/mjh/.cache/codesk-next5-runtime"
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  IFS= read -rs -p "GPT-6-Sol API key (hidden): " OPENAI_API_KEY || { echo "missing API key" >&2; exit 2; }
  printf '\n' >&2
fi
export OPENAI_API_KEY
status=0
while read -r case_id arm; do
  [[ -z "$case_id" ]] && continue
  printf 'START %s %s %s\n' "$case_id" "$arm" "$(date -u +%FT%TZ)"
  if ./scripts/run_new_case_arm.sh "$case_id" "$arm"; then rc=0; else rc=$?; fi
  printf 'END %s %s rc=%s %s\n' "$case_id" "$arm" "$rc" "$(date -u +%FT%TZ)"
  if (( rc != 0 )); then status=1; fi
done <<'ARMS'
v31 shared
v31 shared-lock
v32 ma-id
v32 shared
v32 shared-lock
v33 ma-id
v33 shared
v33 shared-lock
ARMS
exit "$status"
