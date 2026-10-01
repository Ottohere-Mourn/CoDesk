#!/usr/bin/env bash
# Fail-closed two-A6000 BF16 service launcher. GPUs must be selected explicitly and idle.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a6000_env.sh"
: "${CODESK_CUDA_VISIBLE_DEVICES:?Set two explicit, idle physical GPU indices in CODESK_CUDA_VISIBLE_DEVICES}"
IFS=',' read -r -a GPU_IDS <<< "$CODESK_CUDA_VISIBLE_DEVICES"
if [[ "${#GPU_IDS[@]}" -ne 2 || "${GPU_IDS[0]}" == "${GPU_IDS[1]}" ]]; then
  echo "CODESK_CUDA_VISIBLE_DEVICES must contain exactly two distinct indices" >&2; exit 2
fi
for id in "${GPU_IDS[@]}"; do
  [[ "$id" =~ ^[0-9]+$ ]] || { echo "Invalid physical GPU index: $id" >&2; exit 2; }
done
SNAPSHOT="$(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits)"
for id in "${GPU_IDS[@]}"; do
  row="$(awk -F, -v wanted="$id" '($1+0)==wanted {print $1 "," $2 "," $3}' <<< "$SNAPSHOT")"
  [[ -n "$row" ]] || { echo "GPU $id is not present" >&2; exit 2; }
  IFS=',' read -r found used util <<< "$row"
  used="${used//[[:space:]]/}"; util="${util//[[:space:]]/}"
  if (( used > 1024 || util > 5 )); then
    echo "Refusing GPU $id: ${used}MiB allocated, ${util}% busy; no active workload will be displaced" >&2
    exit 3
  fi
done
RUN_ID="${SWCUB_QWEN_SERVICE_RUN_ID:-a6000-qwen-dual-bf16-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid service run id" >&2; exit 2; }
SERVICE_DIR="$CODESK_ARTIFACT_ROOT/qwen-inference-service/$RUN_ID"
mkdir -p "$(dirname "$SERVICE_DIR")"
if [[ -e "$SERVICE_DIR" ]]; then echo "Service artifact already exists: $SERVICE_DIR" >&2; exit 2; fi
mkdir "$SERVICE_DIR"
PORT="${SWCUB_QWEN_PORT:-15485}"
printf '{"run_id":"%s","host":"%s","physical_gpus":"%s","port":%s,"dtype":"bfloat16","quantization":null,"attention":"eager","max_memory_gpu_each":"45GiB","max_memory_cpu":"1GiB","require_no_offload":true}\n' \
  "$RUN_ID" "$(hostname)" "$CODESK_CUDA_VISIBLE_DEVICES" "$PORT" > "$SERVICE_DIR/owner.json"
cd "$CODESK_ROOT"
nohup env CUDA_VISIBLE_DEVICES="$CODESK_CUDA_VISIBLE_DEVICES" OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  "$SWCUB_MODEL_PYTHON" "$CODESK_ROOT/scripts/local_qwen_worker.py" \
  --model "$SWCUB_LOCAL_VLM_PATH" --device auto --port "$PORT" \
  --max-memory-gpu 45GiB --max-memory-cpu 1GiB --attn-implementation eager \
  --expected-gpu-count 2 --require-no-offload \
  > "$SERVICE_DIR/worker.log" 2>&1 < /dev/null &
PID=$!
printf '%s\n' "$PID" > "$SERVICE_DIR/worker.pid"
python3 - "$SERVICE_DIR/owner.json" "$PID" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); d=json.loads(p.read_text()); d['pid']=int(sys.argv[2]); p.write_text(json.dumps(d,indent=2)+'\n')
PY
for _ in $(seq 1 300); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Qwen worker exited during startup; see $SERVICE_DIR/worker.log" >&2; exit 1
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" > "$SERVICE_DIR/health.json" 2>/dev/null; then
    if python3 - "$SERVICE_DIR/health.json" <<'PY'
import json,sys
h=json.load(open(sys.argv[1]))
assert h.get('ready') is True and h.get('dtype')=='bfloat16'
assert h.get('expected_gpu_count')==2 and h.get('require_no_offload') is True
assert not h.get('non_gpu_devices')
assert h.get('cuda_device_ids')==[0,1], h
PY
    then
      echo "ready run_id=$RUN_ID pid=$PID endpoint=http://127.0.0.1:$PORT/health service_dir=$SERVICE_DIR"
      exit 0
    else
      echo "Worker health failed the pinned topology checks; stopping owned PID $PID" >&2
      kill -TERM "$PID" || true
      exit 1
    fi
  fi
  sleep 2
done
echo "Qwen worker readiness timed out after 600 seconds; stopping owned PID $PID and preserving $SERVICE_DIR" >&2
kill -TERM "$PID" 2>/dev/null || true
exit 1
