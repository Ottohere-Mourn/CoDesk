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
CODEX_RUNTIME_ROOT="${MECH04_CODEX_RUNTIME_ROOT:-/home/mjh/.cache/codesk-mech04-sol-pilot}"
API_BASE="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
export CODESK_SOL_ENDPOINT="$API_BASE" OPENAI_BASE_URL="$API_BASE"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then echo "SWCUB_SOL_API_KEY absent; hidden interactive input required." >&2; exit 2; fi
  IFS= read -r -s -p "GPT-6-Sol API key (hidden; not saved): " SWCUB_SOL_API_KEY; printf '\n'
fi
[[ -n "${SWCUB_SOL_API_KEY:-}" ]] || { echo "Empty key; refusing endpoint call." >&2; exit 2; }
export SWCUB_SOL_API_KEY
mkdir -p "$ARTROOT"
RUN_GROUP="mech04-sol-triplet-$(date -u +%Y%m%dT%H%M%SZ)-$$"
ROOT_OUT="$ARTROOT/$RUN_GROUP"; mkdir "$ROOT_OUT"
if [[ ! -x "$CODEX" || ! -f "$IMAGE" || ! -f "$ASSETS/mechanism_expansion_v1/mech04/manifest.json" ]]; then echo "Pinned Codex, Guest image or MECH-04 RAID assets missing." >&2; exit 2; fi
if [[ $(df -P / | awk 'NR==2 {print $4}') -lt $((19*1024*1024)) ]]; then echo "Root free space below 19 GiB; refusing Guest start" >&2; exit 2; fi
if [[ $(df -P /mnt/raid1 | awk 'NR==2 {print $4}') -lt 104857600 ]]; then echo "RAID free space below 100 GiB; refusing Guest start" >&2; exit 2; fi
docker image inspect "$RUNTIME" >/dev/null
"$CODEX" --version > "$ROOT_OUT/codex-version.txt"
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-before.txt"
cp "$ASSETS/mechanism_expansion_v1/mech04/manifest.json" "$ROOT_OUT/fixture-manifest.json"
PROBE_BODY='{"model":"gpt-6-sol","input":"Reply with exactly READY."}'
HTTP_CODE=$(curl --silent --show-error --max-time 90 -o "$ROOT_OUT/endpoint-probe.json" -w '%{http_code}' -H "Authorization: Bearer $SWCUB_SOL_API_KEY" -H 'Content-Type: application/json' -d "$PROBE_BODY" "$API_BASE/responses" || true)
printf '%s\n' "$HTTP_CODE" > "$ROOT_OUT/endpoint-http-status.txt"
if [[ "$HTTP_CODE" != 200 ]]; then echo "GPT-6-Sol endpoint preflight failed (HTTP $HTTP_CODE); no Guest started. See endpoint-probe.json" >&2; exit 3; fi
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS"
export OSCOMBO_GUEST_IMAGE="$IMAGE" SWCUB_OSWORLD_GUEST_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$RUNTIME" OSCOMBO_DOCKER_RUNTIME_IMAGE="$RUNTIME"
export PYTHONPATH="$ROOT:$SWC:$OSW" SWCUB_OSWORLD_VM_READY_TIMEOUT=600
cd "$ROOT"
run_arm() {
 local arm="$1" mode="$2"
 local runid="mech04-$arm-$(date -u +%Y%m%dT%H%M%SZ)-$$"
 local out="$ROOT_OUT/$arm"
 local codexrt="$CODEX_RUNTIME_ROOT/$runid"
 mkdir -p "$out" "$out/overlays" "$out/resources" "$codexrt"
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-before.txt"
 export SWCUB_RUN_ID="$runid" SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]')"
 export SWCUB_RESOURCE_LEDGER="$out/resources/resource-events.jsonl" SWCUB_OSWORLD_OVERLAY_HOST_DIR="$out/overlays"
 unset SWCUB_RESOURCE_IDENTITY_INITIALIZED
 local args=(); [[ "$arm" == shared-lock ]] && args+=(--action-lock)
 set +e
 "$PY" -m oscombo run "${args[@]}" --mode "$mode" \
  --tasks tasks/mechanism_expansion_v1/task_mech04a.py tasks/mechanism_expansion_v1/task_mech04b.py \
  --out "$out" --image "$IMAGE" --harness codex --model gpt-6-sol --effort medium \
  --max-steps 16 --setup-settle 25 --isolated-boot-stagger 35 \
  --opt codex_bin="$CODEX" --opt mcp_python="$PY" --opt timeout=600 \
  --opt base_url="$API_BASE" --opt auth_mode=env --opt api_key_env=SWCUB_SOL_API_KEY \
  --opt codex_runtime_root="$codexrt" \
  --label run="$runid" --label case=MECH-04 --label arm="$arm" --label model=gpt-6-sol --label task_version=0.1.0 --label control_version=0.1.0 --label gui_tool_call_budget=16 --label protocol_version=0.1.2 > "$out/driver.log" 2>&1
 local rc=$?; set -e; printf '%s\n' "$rc" > "$out/runner-exit-code.txt"
 [[ -f "$out/result.json" ]] || { echo "Runner produced no result.json in $out"; return 1; }
 "$PY" - "$out/result.json" "$arm" <<'PY'
import json,sys
p,arm=sys.argv[1:];d=json.load(open(p));print(json.dumps({'arm':arm,'mode':d.get('mode'),'action_lock':d.get('action_lock'),'scores':d.get('scores'),'agents':{k:{x:v.get(x) for x in ('status','steps','error')} for k,v in (d.get('agents') or {}).items()},'total_s':d.get('total_s'),'error':d.get('error')},ensure_ascii=False))
PY
 if [[ "$arm" == shared-lock ]]; then "$PY" - "$out/result.json" "$out" <<'PY'
import json,sys,pathlib
x=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2])
def terminal(name):
 a=(x.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps'} or a.get('error') is not None: return False
 p=root/name/'stdout.log'
 try: events=[json.loads(z) for z in p.read_text(errors='replace').splitlines() if z.strip()]
 except Exception: return False
 msgs=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(events and events[-1].get('type')=='turn.completed' and any(m.strip() for m in msgs))
if not x.get('action_lock',False): print('ERROR: Shared+Lock was requested but action_lock=false',file=sys.stderr); raise SystemExit(1)
if not all(terminal(k) for k in ('agentA','agentB')): print('ERROR: Shared+Lock actor lacked terminal response; treat run as incomplete',file=sys.stderr); raise SystemExit(1)
PY
 fi
 printf '%s\\n' "$codexrt" > "$out/codex-runtime-path.txt"
 if [[ $(df -P / | awk 'NR==2 {print $4}') -lt $((19*1024*1024)) ]]; then echo "Root free space fell below 19 GiB after arm $arm; stopping further arms" >&2; return 1; fi
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-after.txt"
}
if [[ -n "$(printenv MECH04_REUSE_MA_ID || true)" ]]; then
 reused="$(printenv MECH04_REUSE_MA_ID)"
 "$PY" - "$reused" "$ARTROOT" "$ROOT_OUT/ma-id-reference.json" <<'PY'
import json,sys,pathlib
src=pathlib.Path(sys.argv[1]).resolve(); art=pathlib.Path(sys.argv[2]).resolve(); out=pathlib.Path(sys.argv[3])
if art not in src.parents: raise SystemExit('MA-ID reference must reside under the configured RAID artifact root')
x=json.loads(src.read_text()); root=src.parent
assert x.get('mode')=='isolated' and x.get('action_lock') is False
assert x.get('model')=='gpt-6-sol' and x.get('task_version')=='0.1.0'
assert x.get('max_steps')==16 and x.get('gui_tool_call_budget')==16
assert (x.get('scores') or {}).get('mech04a')==1 and (x.get('scores') or {}).get('mech04b')==1
def terminal(name):
 a=(x.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps'} or a.get('error') is not None: return False
 try: events=[json.loads(z) for z in (root/name/'stdout.log').read_text(errors='replace').splitlines() if z.strip()]
 except Exception: return False
 msgs=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(events and events[-1].get('type')=='turn.completed' and any(m.strip() for m in msgs))
assert all(terminal(k) for k in ('agentA','agentB'))
out.write_text(json.dumps({'source_result':str(src),'run':x.get('run'),'mode':x.get('mode'),'action_lock':x.get('action_lock'),'task_version':x.get('task_version'),'model':x.get('model'),'max_steps':x.get('max_steps'),'scores':x.get('scores'),'agents':{k:{'status':v.get('status'),'steps':v.get('steps'),'error':v.get('error')} for k,v in x.get('agents',{}).items()},'completion_rule':'Oracle score=1 plus terminal turn.completed; max_steps is accepted only with explicit completed response'},indent=2)+'\n')
print(f"Using prevalidated MA-ID reference: {src}")
PY
else
 run_arm ma-id isolated
 if ! "$PY" - "$ROOT_OUT/ma-id/result.json" "$ROOT_OUT/ma-id" <<'PY'
import json,sys,pathlib
x=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2]); s=x.get('scores') or {}
def terminal(name):
 a=(x.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps'} or a.get('error') is not None: return False
 p=root/name/'stdout.log'
 try: events=[json.loads(z) for z in p.read_text(errors='replace').splitlines() if z.strip()]
 except Exception: return False
 msgs=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(events and events[-1].get('type')=='turn.completed' and any(m.strip() for m in msgs))
ok=s.get('mech04a')==1 and s.get('mech04b')==1 and all(terminal(k) for k in ('agentA','agentB'))
raise SystemExit(0 if ok else 1)
PY
 then echo "MA-ID did not have two Oracle PASSes with terminal agent responses; retained evidence and stopped before Shared."; exit 4; fi
fi
run_arm shared parallel
if ! "$PY" - "$ROOT_OUT/shared/result.json" "$ROOT_OUT/shared" <<'PY'
import json,sys,pathlib
x=json.load(open(sys.argv[1]));root=pathlib.Path(sys.argv[2])
def terminal(name):
 a=(x.get('agents') or {}).get(name,{})
 if a.get('status') not in {'done','max_steps'} or a.get('error') is not None: return False
 p=root/name/'stdout.log'
 try: events=[json.loads(z) for z in p.read_text(errors='replace').splitlines() if z.strip()]
 except Exception: return False
 msgs=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
 return bool(events and events[-1].get('type')=='turn.completed' and any(m.strip() for m in msgs))
ok=x.get('action_lock') is False and all(terminal(k) for k in ('agentA','agentB'))
raise SystemExit(0 if ok else 1)
PY
then echo "Shared lacked terminal agent responses or action_lock=false; retained evidence and stopped before Shared+Lock."; exit 5; fi
run_arm shared-lock parallel
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-after.txt"
echo "$ROOT_OUT"
unset SWCUB_SOL_API_KEY
