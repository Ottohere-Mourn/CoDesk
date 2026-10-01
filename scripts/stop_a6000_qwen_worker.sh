#!/usr/bin/env bash
# Stop only a service whose run manifest and live command line agree.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a6000_env.sh"
if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Usage: $0 <service-run-id>" >&2; exit 2
fi
SERVICE_DIR="$CODESK_ARTIFACT_ROOT/qwen-inference-service/$1"
[[ -f "$SERVICE_DIR/owner.json" && -f "$SERVICE_DIR/worker.pid" ]] || {
  echo "Missing service ownership record: $SERVICE_DIR" >&2; exit 2;
}
PID="$(cat "$SERVICE_DIR/worker.pid")"
[[ "$PID" =~ ^[0-9]+$ ]]
python3 - "$SERVICE_DIR/owner.json" "$PID" <<'PY'
import json,sys
owner=json.load(open(sys.argv[1]))
assert owner.get('run_id') and owner.get('pid')==int(sys.argv[2])
assert owner.get('host')
PY
CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
[[ "$CMDLINE" == *"$CODESK_ROOT/scripts/local_qwen_worker.py"* && "$CMDLINE" == *"--port"* ]] || {
  echo "PID $PID no longer matches the recorded CoDesk worker; refusing to signal it" >&2; exit 3;
}
kill -TERM "$PID"
for _ in $(seq 1 30); do
  if ! kill -0 "$PID" 2>/dev/null; then echo "stopped run_id=$1 pid=$PID"; exit 0; fi
  sleep 1
done
echo "Owned worker PID $PID did not exit after SIGTERM; preserve its artifacts and investigate" >&2
exit 1
