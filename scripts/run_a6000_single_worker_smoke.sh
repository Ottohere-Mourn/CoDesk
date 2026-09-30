#!/usr/bin/env bash
# Explicit, bounded startup. It refuses to run until Docker/KVM and assets are ready.
set -euo pipefail
source "$(dirname "$0")/a6000_env.sh"
"$CODESK_ROOT/scripts/a6000_environment_check.sh"
existing=$(docker ps -aq --filter label=org.swcub.project=shared-workspace-benchmark-v0)
if [[ -n "$existing" ]]; then
  echo "Refusing smoke: existing project-labelled container IDs require ownership/ledger review first:" >&2
  echo "$existing" >&2
  exit 42
fi
"$CODESK_PYTHON" "$CODESK_ROOT/scripts/run_codesk_experiment.py" \
  "$CODESK_ROOT/configs/a6000_writer_calc_solo_smoke.json"
