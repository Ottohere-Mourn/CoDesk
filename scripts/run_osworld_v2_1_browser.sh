#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
OUT="${OSWORLD_V2_RUN_DIR:-$ROOT/outputs/osworld-v2.1/browser/${1:-unspecified}}"
IMAGE="${OSWORLD_DOCKER_RUNTIME_IMAGE:-swcub/osworld-v2.1-qemu-runtime:local}"
GUEST_IMAGE="${SWCUB_OSWORLD_GUEST_IMAGE:-$V2_DIR/docker_vm_data/osworld-v2-ubuntu-x86.qcow2}"
OVERLAY_DIR="${SWCUB_OSWORLD_OVERLAY_HOST_DIR:-/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/overlays}"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 {gui-cli-gui-solo|gui-cli-cli-solo|gui-cli-refresh|gui-cli-stale|human-solo|agent-solo|agent-qwen-solo|human-agent-focus-aware|human-agent-naive}" >&2
  exit 2
fi
mkdir -p "$OUT" "$OVERLAY_DIR"
python "$ROOT/scripts/patch_osworld_docker_runtime.py" "$V2_DIR"
export OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$OVERLAY_DIR"
export SWCUB_OSWORLD_GUEST_IMAGE="$GUEST_IMAGE"
export SWCUB_OSWORLD_RUN_DIR="$OUT"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
{
  echo "release=osworld-v2.1"
  echo "code_commit=$(git -C "$V2_DIR" rev-parse HEAD)"
  echo "runtime_image=$IMAGE"
  echo "guest_image=$V2_DIR/docker_vm_data/osworld-v2-ubuntu-x86.qcow2"
  echo "scenario=$1"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$ROOT"
  uv --project "$V2_DIR" run --frozen python "$ROOT/scripts/run_osworld_v2_1_browser.py" --scenario "$1"
} 2>&1 | tee "$OUT/run.log"
