#!/usr/bin/env bash
set -euo pipefail
umask 077
cleanup_current_owned_guest() {
  local token="${SWCUB_OWNER_TOKEN:-}"
  [[ -n "$token" ]] || return 0
  local ids id observed
  ids="$(docker ps -aq --filter "label=org.swcub.owner-token=$token" 2>/dev/null || true)"
  for id in $ids; do
    observed="$(docker inspect --format='{{index .Config.Labels "org.swcub.owner-token"}}' "$id" 2>/dev/null || true)"
    if [[ "$observed" == "$token" ]]; then docker rm -f "$id" >/dev/null 2>&1 || true; fi
  done
}
trap cleanup_current_owned_guest EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
ROOT=/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112
OSW=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1
SWC=/home/mjh/Projects/CoDesk-candidate-repair-20261104
PY="$OSW/.venv/bin/python"
CODEX=/home/mjh/.local/share/codesk-hybrid-v2/codex-cli-0.155.0/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex
IMAGE="$OSW/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"
RUNTIME=swcub/osworld-v2.1-qemu-runtime:local
ASSETS="$ROOT/task_assets"
ARTROOT=/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/runs/model-pilot/undo-family
CODEX_RUNTIME_ROOT=/run/user/1002/codesk-undo-family-sol
API_BASE="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
case_id="${1:-}"
[[ "$case_id" =~ ^mech0[6-9]$ ]] || { echo 'usage: $0 mech06|mech07|mech08|mech09' >&2; exit 2; }
export CODESK_SOL_ENDPOINT="$API_BASE" OPENAI_BASE_URL="$API_BASE"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  [[ -t 0 ]] || { echo 'SWCUB_SOL_API_KEY absent; hidden interactive input required.' >&2; exit 2; }
  IFS= read -r -s -p 'GPT-6-Sol API key (hidden; not saved): ' SWCUB_SOL_API_KEY; printf '\n'
fi
[[ -n "${SWCUB_SOL_API_KEY:-}" ]] || { echo 'Empty key; refusing endpoint call.' >&2; exit 2; }
export SWCUB_SOL_API_KEY
[[ -x "$PY" && -x "$CODEX" && -f "$IMAGE" && -f "$ASSETS/mechanism_expansion_v1/$case_id/manifest.json" ]] || { echo 'Pinned runtime, Guest image or case assets missing.' >&2; exit 2; }
[[ $(df -P / | awk 'NR==2 {print $4}') -ge $((19*1024*1024)) ]] || { echo 'Root free space below 19 GiB; refusing Guest start.' >&2; exit 2; }
[[ $(df -P /mnt/raid1 | awk 'NR==2 {print $4}') -ge 104857600 ]] || { echo 'RAID free space below 100 GiB; refusing Guest start.' >&2; exit 2; }
docker image inspect "$RUNTIME" >/dev/null
mkdir -p "$ARTROOT"
RUN_GROUP="${case_id}-sol-triplet-$(date -u +%Y%m%dT%H%M%SZ)-$$"; ROOT_OUT="$ARTROOT/$RUN_GROUP"; mkdir "$ROOT_OUT"
"$CODEX" --version > "$ROOT_OUT/codex-version.txt"
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-before.txt"
cp "$ASSETS/mechanism_expansion_v1/$case_id/manifest.json" "$ROOT_OUT/fixture-manifest.json"
HTTP_CODE=$(curl --silent --show-error --max-time 90 -o "$ROOT_OUT/endpoint-probe.json" -w '%{http_code}' \
 -H "Authorization: Bearer $SWCUB_SOL_API_KEY" -H 'Content-Type: application/json' \
 -d '{"model":"gpt-6-sol","input":"Reply with exactly READY."}' "$API_BASE/responses" || true)
printf '%s\n' "$HTTP_CODE" > "$ROOT_OUT/endpoint-http-status.txt"
[[ "$HTTP_CODE" == 200 ]] || { echo "GPT-6-Sol endpoint preflight failed (HTTP $HTTP_CODE); no Guest started." >&2; exit 3; }
export OSWORLD_DIR="$OSW" PARAGUI_TASK_ASSETS="$ASSETS"
export OSCOMBO_GUEST_IMAGE="$IMAGE" SWCUB_OSWORLD_GUEST_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$RUNTIME" OSCOMBO_DOCKER_RUNTIME_IMAGE="$RUNTIME"
export PYTHONPATH="$ROOT:$SWC:$OSW" SWCUB_OSWORLD_VM_READY_TIMEOUT=600
cd "$ROOT"
TASK_A="tasks/mechanism_expansion_v1/task_${case_id}a.py"
TASK_B="tasks/mechanism_expansion_v1/task_${case_id}b.py"
run_arm() {
 local arm="$1" mode="$2"
 local runid="${case_id}-$arm-$(date -u +%Y%m%dT%H%M%SZ)-$$"
 local out="$ROOT_OUT/$arm" codexrt="$CODEX_RUNTIME_ROOT/$runid"
 mkdir -p "$out" "$out/overlays" "$out/resources" "$codexrt"
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-before.txt"
 export SWCUB_RUN_ID="$runid" SWCUB_OWNER_TOKEN="$(od -An -N32 -tx1 /dev/urandom | tr -d '[:space:]')"
 export SWCUB_RESOURCE_LEDGER="$out/resources/resource-events.jsonl" SWCUB_OSWORLD_OVERLAY_HOST_DIR="$out/overlays"
 unset SWCUB_RESOURCE_IDENTITY_INITIALIZED
 local args=(); [[ "$arm" == shared-lock ]] && args+=(--action-lock)
 set +e
 timeout --signal=TERM --kill-after=60s 3000s "$PY" -m oscombo run "${args[@]}" --mode "$mode" \
  --tasks "$TASK_A" "$TASK_B" --out "$out" --image "$IMAGE" --harness codex --model gpt-6-sol --effort medium \
  --max-steps 22 --setup-settle 25 --isolated-boot-stagger 35 \
  --opt codex_bin="$CODEX" --opt mcp_python="$PY" --opt timeout=1200 \
  --opt base_url="$API_BASE" --opt auth_mode=env --opt api_key_env=SWCUB_SOL_API_KEY \
  --opt codex_runtime_root="$codexrt" \
  --label run="$runid" --label case="${case_id^^}" --label arm="$arm" --label model=gpt-6-sol \
  --label task_version=0.5.0 --label gui_tool_call_budget=22 --label actor_timeout_s=1200 --label protocol_version=0.1.3 \
  > "$out/driver.log" 2>&1
 local rc=$?; set -e; printf '%s\n' "$rc" > "$out/runner-exit-code.txt"
 [[ -f "$out/result.json" ]] || { echo "Runner produced no result.json in $out" >&2; return 1; }
 "$PY" - "$out/result.json" "$arm" <<'PY'
import json,sys
p,arm=sys.argv[1:];d=json.load(open(p));print(json.dumps({'arm':arm,'mode':d.get('mode'),'action_lock':d.get('action_lock'),'scores':d.get('scores'),'agents':{k:{x:v.get(x) for x in ('status','steps','error')} for k,v in (d.get('agents') or {}).items()},'total_s':d.get('total_s'),'error':d.get('error')},ensure_ascii=False))
PY
 if [[ "$arm" == shared-lock ]]; then "$PY" - "$out/result.json" <<'PY'
import json,sys
if not json.load(open(sys.argv[1])).get('action_lock',False): print('ERROR: action_lock=false in requested Shared+Lock arm',file=sys.stderr);raise SystemExit(1)
PY
 fi
 printf '%s\n' "$codexrt" > "$out/codex-runtime-path.txt"
 [[ $(df -P / | awk 'NR==2 {print $4}') -ge $((19*1024*1024)) ]] || { echo "Root free space below 19 GiB after $arm; retained evidence and stopping." >&2; return 1; }
 docker ps --format '{{.Names}} {{.Status}}' > "$out/containers-after.txt"
}
# Always attempt the complete triplet; do not discard non-target or unexpected outcomes.
run_arm ma-id isolated
run_arm shared parallel
run_arm shared-lock parallel
"$PY" - "$ROOT_OUT" "$case_id" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1]);cid=sys.argv[2]
def terminal(path):
 d=json.load(open(path/'result.json')); data={}
 for actor in ('agentA','agentB'):
  a=(d.get('agents') or {}).get(actor,{})
  try: ev=[json.loads(x) for x in (path/actor/'stdout.log').read_text(errors='replace').splitlines() if x.strip()]
  except Exception: ev=[]
  msgs=[e.get('item',{}).get('text','').strip() for e in ev if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
  data[actor]={'terminal':a.get('status') in {'done','max_steps','fail'} and a.get('error') is None and bool(ev) and ev[-1].get('type')=='turn.completed' and any(msgs),'status':a.get('status'),'error':a.get('error')}
 return d,data
arms={a:terminal(root/a) for a in ('ma-id','shared','shared-lock')}
results={}
for arm,(d,t) in arms.items():
 scores=d.get('scores') or {};result={'scores':scores,'agents':t,'total_s':d.get('total_s'),'action_lock':d.get('action_lock')};
 result['valid_terminal']=all(x['terminal'] for x in t.values())
 result['both_pass']=scores.get(cid+'a')==1 and scores.get(cid+'b')==1
 result['both_fail']=scores.get(cid+'a')==0 and scores.get(cid+'b')==0
 result['any_task_fail']=any(scores.get(cid+x)==0 for x in ('a','b'))
 results[arm]=result
valid=results['ma-id']['valid_terminal'] and results['shared']['valid_terminal'] and results['shared-lock']['valid_terminal'] and results['shared-lock']['action_lock'] is True and arms['shared'][0].get('action_lock') is False
results['target_pattern']={'ma_id_both_pass':results['ma-id']['both_pass'],'shared_any_task_fail':results['shared']['any_task_fail'],'shared_lock_any_task_fail':results['shared-lock']['any_task_fail'],
 'shared_both_fail':results['shared']['both_fail'],'shared_lock_both_fail':results['shared-lock']['both_fail'],'all_arms_valid':valid,
 'meets_target':valid and results['ma-id']['both_pass'] and results['shared']['any_task_fail'] and results['shared-lock']['any_task_fail']}
(root/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'case_id':cid,'results':results,'artifacts':str(root)},ensure_ascii=False))
PY
docker ps --format '{{.Names}} {{.Status}}' > "$ROOT_OUT/containers-after.txt"
echo "$ROOT_OUT"
unset SWCUB_SOL_API_KEY
