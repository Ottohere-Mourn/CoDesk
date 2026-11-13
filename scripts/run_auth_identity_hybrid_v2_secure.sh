#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/mjh/Projects/CoDesk-candidate-repair-20261104
PYTHON=/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python
export CODESK_SOL_ENDPOINT="${CODESK_SOL_ENDPOINT:-https://docode.cc/v1}"
if [[ -z "${SWCUB_SOL_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then echo "SWCUB_SOL_API_KEY absent; interactive hidden input required." >&2; exit 2; fi
  IFS= read -r -s -p "GPT-6-Sol API key (hidden; not saved): " SWCUB_SOL_API_KEY
  printf '\n'
  [[ -n "$SWCUB_SOL_API_KEY" ]] || { echo "Empty key; refusing to start." >&2; exit 2; }
  export SWCUB_SOL_API_KEY
fi
cd "$ROOT"
exec "$PYTHON" "$ROOT/scripts/run_auth_identity_hybrid_v2.py" "$@"
