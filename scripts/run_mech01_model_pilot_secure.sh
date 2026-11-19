#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
OSW=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1
SWC=/home/mjh/Projects/CoDesk-candidate-repair-20261104
PY="$OSW/.venv/bin/python"
CODEX=/home/mjh/.local/share/codesk-hybrid-v2/codex-cli-0.155.0/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
IMAGE="$OSW/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"
RUNTIME=swcub/osworld-v2.1-qemu-runtime:local
ASSETS=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets
ARTROOT=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot
CODEX_RUNTIME_ROOT=/home/mjh/.cache/codesk-mech01-model-pilot
CONTINUE_PATH=""
if [[ $# -eq 2 && "$1" == "--continue" ]]; then CONTINUE_PATH="$2"; elif [[ $# -ne 0 ]]; then echo "usage: $0 [--continue <existing-pilot-dir>]" >&2; exit 2; fi
API_BASE="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
export CODESK_SOL_ENDPOINT="$API_BASE" OPENAI_BASE_URL="$API_BASE"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then echo "SWCUB_SOL_API_KEY absent; hidden interactive input required." >&2; exit 2; fi
  IFS= read -r -s -p "GPT-6-Sol API key (hidden; not saved): " SWCUB_SOL_API_KEY
  printf '\n'
fi
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then echo "Empty key; refusing to call endpoint." >&2; exit 2; fi
export SWCUB_SOL_API_KEY
mkdir -p "$ARTROOT"
if [[ -n "$CONTINUE_PATH" ]]; then
  ROOT_OUT=$(realpath -e "$CONTINUE_PATH")
  case "$ROOT_OUT" in "$ARTROOT"/*) ;; *) echo "Continuation path must stay under $ARTROOT" >&2; exit 2 ;; esac
  RUN_GROUP=$(basename "$ROOT_OUT")
  [[ -f "$ROOT_OUT/endpoint-http-status.txt" && $(cat "$ROOT_OUT/endpoint-http-status.txt") == 200 ]] || { echo "No valid recorded endpoint preflight in continuation directory" >&2; exit 2; }
  [[ -f "$ROOT_OUT/ma-id/result.json" ]] || { echo "Continuation needs a saved MA-ID result" >&2; exit 2; }
else
  RUN_GROUP="mech01-sol-triplet-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  ROOT_OUT="$ARTROOT/$RUN_GROUP"
  mkdir "$ROOT_OUT"
fi
if [[ ! -x "$CODEX" || ! -f "$IMAGE" ]]; then echo "Pinned Codex/Guest image preflight failed" >&2; exit 2; fi
if [[ ! -d "$OSW/.venv" || ! -f "$ASSETS/mechanism_expansion_v1/mech01/app.py" ]]; then echo "OSWorld venv or built RAID fixture missing" >&2; exit 2; fi
if [[ $(df -P / | awk 'NR==2 {print $4}') -lt 20971520 ]]; then echo "Root free space below 20 GiB; refusing guest start" >&2; exit 2; fi
if [[ $(df -P /mnt/raid1 | awk 'NR==2 {print $4}') -lt 104857600 ]]; then echo "RAID free space below 100 GiB; refusing guest start" >&2; exit 2; fi
docker image inspect "$RUNTIME" >/dev/null
CURRENT_CODEX_VERSION=$("$CODEX" --version)
if [[ -z "$CONTINUE_PATH" ]]; then
  printf '%s\n' "$CURRENT_CODEX_VERSION" > "$ROOT_OUT/codex-version.txt"
  docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-before.txt"
elif [[ -f "$ROOT_OUT/codex-version.txt" ]] && [[ "$(cat "$ROOT_OUT/codex-version.txt")" != "$CURRENT_CODEX_VERSION" ]]; then
  echo "Codex CLI version changed since saved MA-ID; refusing continuation" >&2; exit 2
fi
if [[ -z "$CONTINUE_PATH" ]]; then
  PROBE_BODY='{"model":"gpt-6-sol","input":"Reply with exactly READY."}'
  HTTP_CODE=$(curl --silent --show-error --max-time 90 -o "$ROOT_OUT/endpoint-probe.json" -w '%{http_code}' \
    -H "Authorization: Bearer $SWCUB_SOL_API_KEY" -H 'Content-Type: application/json' \
    -d "$PROBE_BODY" "$API_BASE/responses" || true)
  printf '%s\n' "$HTTP_CODE" > "$ROOT_OUT/endpoint-http-status.txt"
  if [[ "$HTTP_CODE" != 200 ]]; then
    echo "GPT-6-Sol endpoint preflight failed (HTTP $HTTP_CODE); no Guest started. See $ROOT_OUT/endpoint-probe.json"
    exit 3
  fi
  echo "Endpoint probe passed; starting MA-ID."
else
  echo "Using saved MA-ID and endpoint preflight from $ROOT_OUT"
fi
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS"
export OSCOMBO_GUEST_IMAGE="$IMAGE"
export SWCUB_OSWORLD_GUEST_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$RUNTIME" OSCOMBO_DOCKER_RUNTIME_IMAGE="$RUNTIME"
export PYTHONPATH="$ROOT:$SWC:$OSW"
export SWCUB_OSWORLD_VM_READY_TIMEOUT=600
cd "$ROOT"
run_arm() {
  local arm="$1" mode="$2"
  local runid="mech01-${arm}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  local out="$ROOT_OUT/$arm"
  local codexrt="$CODEX_RUNTIME_ROOT/$runid"
  mkdir -p "$out"
  mkdir -p "$out/overlays" "$out/resources" "$codexrt"
  docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-before.txt"
  export SWCUB_RUN_ID="$runid"
  export SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
  export SWCUB_RESOURCE_LEDGER="$out/resources/resource-events.jsonl"
  export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$out/overlays"
  unset SWCUB_RESOURCE_IDENTITY_INITIALIZED
  local args=()
  if [[ "$arm" == shared-lock ]]; then args+=(--action-lock); fi
  set +e
  "$PY" -m oscombo run --mode "$mode" \
    --tasks tasks/mechanism_expansion_v1/task_mech01a.py tasks/mechanism_expansion_v1/task_mech01b.py \
    --out "$out" --image "$IMAGE" --harness codex --model gpt-6-sol --effort medium \
    --max-steps 18 --setup-settle 18 --isolated-boot-stagger 40 \
    --opt codex_bin="$CODEX" --opt mcp_python="$PY" --opt timeout=1200 \
    --opt base_url="$API_BASE" --opt auth_mode=env --opt api_key_env=SWCUB_SOL_API_KEY \
    --opt codex_runtime_root="$codexrt" \
    --label run="$runid" --label case=MECH-01 --label arm="$arm" \
    --label model=gpt-6-sol --label task_version=0.1.4 --label control_version=0.1.5 \
    --label gui_tool_call_budget=18 "${args[@]}" > "$out/driver.log" 2>&1
  local rc=$?
  set -e
  printf '%s\n' "$rc" > "$out/runner-exit-code.txt"
  if [[ ! -f "$out/result.json" ]]; then echo "Runner produced no result.json in $out"; return 1; fi
  "$PY" - "$out/result.json" "$arm" <<'PY'
import json,sys
p,arm=sys.argv[1:]
d=json.load(open(p))
scores=d.get("scores") or {}
agents=d.get("agents") or {}
out={"arm":arm,"mode":d.get("mode"),"scores":scores,
     "agents":{k:{x:v.get(x) for x in ("status","steps","error")} for k,v in agents.items()},
     "total_s":d.get("total_s"),"error":d.get("error")}
print(json.dumps(out,ensure_ascii=False))
PY
  printf '%s\n' "$codexrt" > "$out/codex-runtime-path.txt"
  docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-after.txt"
}
if [[ -z "$CONTINUE_PATH" ]]; then run_arm ma-id isolated; fi
if ! "$PY" - "$ROOT_OUT/ma-id/result.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));s=d.get("scores") or {}
raise SystemExit(0 if s.get("mech01a")==1 and s.get("mech01b")==1 else 1)
PY
then
  echo "MA-ID did not score 1/1; preserved it and stopping before shared runs."
  exit 4
fi
echo "MA-ID passed both actor oracles; proceeding to Shared."
if [[ ! -f "$ROOT_OUT/shared/result.json" ]]; then run_arm shared parallel; else echo "Shared result already present; preserving and skipping."; fi
echo "Proceeding to Shared+Lock with same task/model/budget."
if [[ -f "$ROOT_OUT/shared-lock/result.json" ]]; then echo "Shared+Lock result already present; refusing to overwrite."; exit 5; fi
run_arm shared-lock parallel
echo "$ROOT_OUT"
unset SWCUB_SOL_API_KEY
