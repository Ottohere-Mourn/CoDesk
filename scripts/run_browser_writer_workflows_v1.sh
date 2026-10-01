#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/a6000_env.sh"
export PYTHONPATH="$OSWORLD_V2_DIR:$CODESK_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$CODESK_PYTHON" "$ROOT/scripts/run_browser_writer_workflows_v1.py" "$@"
