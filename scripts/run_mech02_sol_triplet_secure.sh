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
CODEX_RUNTIME_ROOT="${MECH02_CODEX_RUNTIME_ROOT:-/home/mjh/.cache/codesk-mech02-sol-pilot}"
API_BASE="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
export CODESK_SOL_ENDPOINT="$API_BASE" OPENAI_BASE_URL="$API_BASE"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then echo "SWCUB_SOL_API_KEY absent; hidden interactive input required." >&2; exit 2; fi
  IFS= read -r -s -p "GPT-6-Sol API key (hidden; not saved): " SWCUB_SOL_API_KEY
  printf '\n'
fi
[[ -n "${SWCUB_SOL_API_KEY:-}" ]] || { echo "Empty key; refusing endpoint call." >&2; exit 2; }
export SWCUB_SOL_API_KEY
mkdir -p "$ARTROOT"
if [[ "${MECH02_ONLY_ARM:-}" == shared-lock ]]; then
 RUN_GROUP="mech02-sol-shared-lock-$(date -u +%Y%m%dT%H%M%SZ)-$$"
else
 RUN_GROUP="mech02-sol-triplet-$(date -u +%Y%m%dT%H%M%SZ)-$$"
fi
ROOT_OUT="$ARTROOT/$RUN_GROUP"; mkdir "$ROOT_OUT"
if [[ ! -x "$CODEX" || ! -f "$IMAGE" || ! -f "$ASSETS/mechanism_expansion_v1/mech02/manifest.json" ]]; then
 echo "Pinned Codex, Guest image or MECH-02 RAID assets missing." >&2; exit 2
fi
if [[ $(df -P / | awk 'NR==2 {print $4}') -lt $((19*1024*1024)) ]]; then echo "Root free space below 19 GiB; refusing Guest start" >&2; exit 2; fi
if [[ $(df -P /mnt/raid1 | awk 'NR==2 {print $4}') -lt 104857600 ]]; then echo "RAID free space below 100 GiB; refusing Guest start" >&2; exit 2; fi
docker image inspect "$RUNTIME" >/dev/null
"$CODEX" --version > "$ROOT_OUT/codex-version.txt"
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-before.txt"
printf '%s\n' "$(cat "$ASSETS/mechanism_expansion_v1/mech02/manifest.json")" > "$ROOT_OUT/fixture-manifest.json"
PROBE_BODY='{"model":"gpt-6-sol","input":"Reply with exactly READY."}'
HTTP_CODE=$(curl --silent --show-error --max-time 90 -o "$ROOT_OUT/endpoint-probe.json" -w '%{http_code}' \
  -H "Authorization: Bearer $SWCUB_SOL_API_KEY" -H 'Content-Type: application/json' \
  -d "$PROBE_BODY" "$API_BASE/responses" || true)
printf '%s\n' "$HTTP_CODE" > "$ROOT_OUT/endpoint-http-status.txt"
if [[ "$HTTP_CODE" != 200 ]]; then
 echo "GPT-6-Sol endpoint preflight failed (HTTP $HTTP_CODE); no Guest started. See $ROOT_OUT/endpoint-probe.json" >&2
 exit 3
fi
echo "Endpoint probe passed; starting MA-ID."
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS"
export OSCOMBO_GUEST_IMAGE="$IMAGE" SWCUB_OSWORLD_GUEST_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$RUNTIME" OSCOMBO_DOCKER_RUNTIME_IMAGE="$RUNTIME"
export PYTHONPATH="$ROOT:$SWC:$OSW"
export SWCUB_OSWORLD_VM_READY_TIMEOUT=600
cd "$ROOT"
run_arm() {
 local arm="$1" mode="$2"
 local runid="mech02-$arm-$(date -u +%Y%m%dT%H%M%SZ)-$$"
 local out="$ROOT_OUT/$arm" codexrt="$CODEX_RUNTIME_ROOT/$runid"
 mkdir -p "$out" "$out/overlays" "$out/resources" "$codexrt"
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-before.txt"
 export SWCUB_RUN_ID="$runid" SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]')"
 export SWCUB_RESOURCE_LEDGER="$out/resources/resource-events.jsonl" SWCUB_OSWORLD_OVERLAY_HOST_DIR="$out/overlays"
 unset SWCUB_RESOURCE_IDENTITY_INITIALIZED
 local args=(); [[ "$arm" == shared-lock ]] && args+=(--action-lock)
 set +e
 "$PY" -m oscombo run "${args[@]}" --mode "$mode" \
  --tasks tasks/mechanism_expansion_v1/task_mech02a.py tasks/mechanism_expansion_v1/task_mech02b.py \
  --out "$out" --image "$IMAGE" --harness codex --model gpt-6-sol --effort medium \
  --max-steps 18 --setup-settle 25 --isolated-boot-stagger 35 \
  --opt codex_bin="$CODEX" --opt mcp_python="$PY" --opt timeout=900 \
  --opt base_url="$API_BASE" --opt auth_mode=env --opt api_key_env=SWCUB_SOL_API_KEY \
  --opt codex_runtime_root="$codexrt" \
  --label run="$runid" --label case=MECH-02 --label arm="$arm" \
  --label model=gpt-6-sol --label task_version=0.1.1 --label control_version=0.1.2 \
  --label gui_tool_call_budget=18 --label actor_timeout_s=900 --label protocol_version=0.1.3 > "$out/driver.log" 2>&1
 local rc=$?; set -e
 printf '%s\n' "$rc" > "$out/runner-exit-code.txt"
 [[ -f "$out/result.json" ]] || { echo "Runner produced no result.json in $out"; return 1; }
 "$PY" - "$out/result.json" "$arm" <<'PY'
import json,sys
p,arm=sys.argv[1:];d=json.load(open(p))
print(json.dumps({"arm":arm,"mode":d.get("mode"),"action_lock":d.get("action_lock"),"mediation":d.get("mediation"),"scores":d.get("scores"),
 "agents":{k:{x:v.get(x) for x in ("status","steps","error")} for k,v in (d.get("agents") or {}).items()},
 "total_s":d.get("total_s"),"error":d.get("error")},ensure_ascii=False))
PY
 if [[ "$arm" == shared-lock ]]; then
  "$PY" - "$out/result.json" <<'PY'
import json,sys
if not json.load(open(sys.argv[1])).get("action_lock",False):
 print("ERROR: requested Shared+Lock run did not enable action_lock",file=sys.stderr)
 raise SystemExit(1)
PY
 fi
 printf '%s\n' "$codexrt" > "$out/codex-runtime-path.txt"
 if [[ $(df -P / | awk 'NR==2 {print $4}') -lt $((19*1024*1024)) ]]; then echo "Root free space fell below 19 GiB after arm $arm; stopping further arms" >&2; return 1; fi
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-after.txt"
}
if [[ "${MECH02_ONLY_ARM:-}" == shared-lock ]]; then
 echo "Running only the Shared+Lock arm (MECH-02 task version 0.1.1)."
 run_arm shared-lock parallel
 docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-after.txt"
 echo "$ROOT_OUT"
 unset SWCUB_SOL_API_KEY
 exit 0
fi
run_arm ma-id isolated
if ! "$PY" - "$ROOT_OUT/ma-id/result.json" "$ROOT_OUT/ma-id" <<'PY'
import json,sys,pathlib
r=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2]); s=r.get('scores') or {}
def terminal(name):
 a=(r.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps','fail'} or a.get('error') is not None: return False
 try: ev=[json.loads(z) for z in (root/name/'stdout.log').read_text(errors='replace').splitlines() if z.strip()]
 except Exception:return False
 msgs=[e.get('item',{}).get('text','').strip() for e in ev if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(ev and ev[-1].get('type')=='turn.completed' and any(msgs))
valid=s.get('mech02a')==1 and s.get('mech02b')==1 and all(terminal(k) for k in ('agentA','agentB'))
raise SystemExit(0 if valid else 1)
PY
then echo "MA-ID lacked two Oracle PASSes with terminal responses; retained it and stopped before Shared."; exit 4; fi
run_arm shared parallel
if ! "$PY" - "$ROOT_OUT/shared/result.json" "$ROOT_OUT/shared" <<'PY'
import json,sys,pathlib
r=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2])
def terminal(name):
 a=(r.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps','fail'} or a.get('error') is not None:return False
 try:ev=[json.loads(z) for z in (root/name/'stdout.log').read_text(errors='replace').splitlines() if z.strip()]
 except Exception:return False
 msgs=[e.get('item',{}).get('text','').strip() for e in ev if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(ev and ev[-1].get('type')=='turn.completed' and any(msgs))
valid=r.get('action_lock') is False and all(terminal(k) for k in ('agentA','agentB'))
raise SystemExit(0 if valid else 1)
PY
then echo "Shared lacks terminal responses or action_lock=false; retained evidence and stopped before lock."; exit 5; fi
run_arm shared-lock parallel
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-after.txt"
echo "$ROOT_OUT"
unset SWCUB_SOL_API_KEY
