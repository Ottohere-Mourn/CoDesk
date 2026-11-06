#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/mjh/Projects/CoDesk-candidate-repair-20261104
PYTHON=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python
RUNNER="$ROOT/scripts/run_pay1_timesheet_completion_order_hybrid_v1.py"
export CODESK_SOL_ENDPOINT="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then echo "SWCUB_SOL_API_KEY absent; run in interactive SSH session for hidden input." >&2; exit 2; fi
  IFS= read -r -s -p "GPT-6-Sol API key (hidden; not saved): " SWCUB_SOL_API_KEY
  printf '\n'
  if [[ -z "$SWCUB_SOL_API_KEY" ]]; then echo "Empty key; refusing to start." >&2; exit 2; fi
  export SWCUB_SOL_API_KEY
fi
cd "$ROOT"
exec "$PYTHON" "$RUNNER" "$@"
