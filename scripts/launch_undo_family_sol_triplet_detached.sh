#!/usr/bin/env bash
# Ask for the Sol credential on a hidden TTY, then detach the triplet so a lost
# SSH client cannot orphan an OSWorld Guest. The key is inherited only in the
# runner's environment and is never written to any file, log, or argv.
set -euo pipefail
set +x
umask 077
ROOT_OUT=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/undo-family
SCRIPT=/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112/scripts/run_undo_family_sol_triplet_secure.sh
case_id="${1:-}"
[[ "$case_id" =~ ^mech0[6-9]$ ]] || { echo 'usage: launch_undo_family_sol_triplet_detached.sh mech06|mech07|mech08|mech09' >&2; exit 2; }
[[ -t 0 ]] || { echo 'An interactive TTY is required for hidden key input.' >&2; exit 2; }
IFS= read -r -s -p 'GPT-6-Sol API key (hidden; not saved): ' SWCUB_SOL_API_KEY
printf '\n'
[[ -n "$SWCUB_SOL_API_KEY" ]] || { echo 'Empty key; refusing to launch.' >&2; exit 2; }
mkdir -p "$ROOT_OUT/launchers"
launcher="launcher-${case_id}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
launch_dir="$ROOT_OUT/launchers/$launcher"
mkdir "$launch_dir"
printf 'case=%s\nlaunched_utc=%s\nhost_pid=pending\n' "$case_id" "$(date -u +%FT%TZ)" > "$launch_dir/launcher.txt"
export SWCUB_SOL_API_KEY
nohup bash "$SCRIPT" "$case_id" > "$launch_dir/runner.log" 2>&1 < /dev/null &
pid=$!
printf 'host_pid=%s\n' "$pid" >> "$launch_dir/launcher.txt"
printf '%s\n' "$pid" > "$launch_dir/host.pid"
unset SWCUB_SOL_API_KEY
echo "Detached runner started: $launcher (PID $pid)"
echo "Log: $launch_dir/runner.log"
