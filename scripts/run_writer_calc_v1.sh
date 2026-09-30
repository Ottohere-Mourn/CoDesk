#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
IMAGE="${SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE:-${OSWORLD_DOCKER_RUNTIME_IMAGE:-swcub/osworld-v2.1-qemu-runtime:local}}"
GUEST_IMAGE="${SWCUB_OSWORLD_GUEST_IMAGE:-$V2_DIR/docker_vm_data/osworld-v2-ubuntu-x86.qcow2}"

export OSWORLD_V2_DIR="$V2_DIR"
export SWCUB_OSWORLD_GUEST_IMAGE="$GUEST_IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
cd "$ROOT"
# On the A6000 migration copy, use the already provisioned user-level OSWorld
# environment. `uv run` would recreate isolated build environments for external
# path dependencies and may require network access even though imports are ready.
if [[ -n "${CODESK_PYTHON:-}" && -x "$CODESK_PYTHON" ]]; then
  exec "$CODESK_PYTHON" "$ROOT/scripts/run_writer_calc_v1.py" "$@"
fi
uv --project "$V2_DIR" run --frozen python "$ROOT/scripts/run_writer_calc_v1.py" "$@"
