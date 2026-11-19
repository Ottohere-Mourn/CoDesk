#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
OSW=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1
SWC=/home/mjh/Projects/CoDesk-candidate-repair-20261104
PY=$OSW/.venv/bin/python
CODEX=/home/mjh/.local/share/codesk-hybrid-v2/codex-cli-0.155.0/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
IMAGE=$OSW/docker_vm_data/osworld-v2-ubuntu-x86.qcow2
RUNTIME=swcub/osworld-v2.1-qemu-runtime:local
ASSETS=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets
BASEGROUP=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/mech04-sol-triplet-20261118T121209Z-550215
OUT=$BASEGROUP/shared-lock
CODEXRT=/run/user/1002/codesk-mech04-sol-pilot-20261118
API_BASE=https://docode.cc/v1
[[ -x "$PY" && -x "$CODEX" && -f "$IMAGE" && -f "$ASSETS/mechanism_expansion_v1/mech04/manifest.json" ]] || { echo 'Pinned runtime, Guest image or fixture manifest missing.' >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo "Shared+Lock output already exists; refusing overwrite." >&2; exit 2; }
[[ -d "$BASEGROUP/ma-id" && -f "$BASEGROUP/ma-id/result.json" && -d "$BASEGROUP/shared" && -f "$BASEGROUP/shared/result.json" ]] || { echo 'Referenced MA-ID and Shared arms are missing.' >&2; exit 2; }
[[ ! -e "$OUT" ]] || { echo 'Shared+Lock output already exists; refusing overwrite.' >&2; exit 2; }
[[ $(df -P / | awk 'NR==2 {print $4}') -ge $((19*1024*1024)) ]] || { echo 'Root free space below 19 GiB.' >&2; exit 2; }
[[ $(df -P /mnt/raid1 | awk 'NR==2 {print $4}') -ge $((100*1024*1024)) ]] || { echo 'RAID free space below 100 GiB.' >&2; exit 2; }
docker image inspect "$RUNTIME" >/dev/null
if [[ -z "$(printenv SWCUB_SOL_API_KEY || true)" ]]; then
  if [[ ! -t 0 ]]; then echo 'SWCUB_SOL_API_KEY absent; hidden interactive input required.' >&2; exit 2; fi
  IFS= read -r -s -p 'GPT-6-Sol API key (hidden; not saved): ' SWCUB_SOL_API_KEY; printf '\n'
fi
export SWCUB_SOL_API_KEY OPENAI_BASE_URL=$API_BASE CODESK_SOL_ENDPOINT=$API_BASE
mkdir -p "$OUT/overlays" "$OUT/resources" "$CODEXRT"
RUNID=mech04-shared-lock-$(date -u +%Y%m%dT%H%M%SZ)-$$
"$CODEX" --version > "$OUT/codex-version.txt"
docker ps --format '{{.Names}} {{.Status}}' > "$OUT/containers-before.txt"
cp "$ASSETS/mechanism_expansion_v1/mech04/manifest.json" "$OUT/fixture-manifest.json"
HTTP=$(curl --silent --show-error --max-time 90 -o "$OUT/endpoint-probe.json" -w '%{http_code}' -H "Authorization: Bearer $SWCUB_SOL_API_KEY" -H 'Content-Type: application/json' -d '{"model":"gpt-6-sol","input":"Reply with exactly READY."}' "$API_BASE/responses" || true)
printf '%s\n' "$HTTP" > "$OUT/endpoint-http-status.txt"
[[ "$HTTP" == 200 ]] || { echo "GPT-6-Sol endpoint preflight failed (HTTP $HTTP); no Guest started." >&2; exit 3; }
export OSWORLD_DIR=$OSW PARAGUI_TASK_ASSETS=$ASSETS
export OSCOMBO_GUEST_IMAGE=$IMAGE SWCUB_OSWORLD_GUEST_IMAGE=$IMAGE
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE=$RUNTIME OSCOMBO_DOCKER_RUNTIME_IMAGE=$RUNTIME
export PYTHONPATH=$ROOT:$SWC:$OSW SWCUB_OSWORLD_VM_READY_TIMEOUT=600
export SWCUB_RUN_ID=$RUNID SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]')"
export SWCUB_RESOURCE_LEDGER=$OUT/resources/resource-events.jsonl SWCUB_OSWORLD_OVERLAY_HOST_DIR=$OUT/overlays
unset SWCUB_RESOURCE_IDENTITY_INITIALIZED
cd "$ROOT"
set +e
"$PY" -m oscombo run --action-lock --mode parallel \
 --tasks tasks/mechanism_expansion_v1/task_mech04a.py tasks/mechanism_expansion_v1/task_mech04b.py \
 --out "$OUT" --image "$IMAGE" --harness codex --model gpt-6-sol --effort medium \
 --max-steps 16 --setup-settle 25 --isolated-boot-stagger 35 \
 --opt codex_bin="$CODEX" --opt mcp_python="$PY" --opt timeout=600 \
 --opt base_url="$API_BASE" --opt auth_mode=env --opt api_key_env=SWCUB_SOL_API_KEY \
 --opt codex_runtime_root="$CODEXRT/$RUNID" \
 --label run="$RUNID" --label case=MECH-04 --label arm=shared-lock --label model=gpt-6-sol \
 --label task_version=0.1.0 --label control_version=0.1.0 --label gui_tool_call_budget=16 --label protocol_version=0.1.3 > "$OUT/driver.log" 2>&1
RC=$?
set -e
printf '%s\n' "$RC" > "$OUT/runner-exit-code.txt"
[[ -f "$OUT/result.json" ]] || { echo "Runner produced no result.json in $OUT"; exit 1; }
"$PY" - "$OUT/result.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
print(json.dumps({'mode':x.get('mode'),'action_lock':x.get('action_lock'),'scores':x.get('scores'),'agents':{k:{z:v.get(z) for z in ('status','steps','error')} for k,v in (x.get('agents') or {}).items()},'total_s':x.get('total_s'),'error':x.get('error')},ensure_ascii=False))
PY
docker ps --format '{{.Names}} {{.Status}}' > "$OUT/containers-after.txt"
printf '%s\n' "$CODEXRT/$RUNID" > "$OUT/codex-runtime-path.txt"
echo "$OUT"
unset SWCUB_SOL_API_KEY
