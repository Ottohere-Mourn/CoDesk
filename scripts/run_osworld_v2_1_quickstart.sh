#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
OUT="${OSWORLD_V2_RUN_DIR:-$ROOT/outputs/osworld-v2.1/quickstart}"
OVERLAY_DIR="${SWCUB_OSWORLD_OVERLAY_HOST_DIR:-/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/overlays}"
IMAGE="${OSWORLD_DOCKER_RUNTIME_IMAGE:-swcub/osworld-v2.1-qemu-runtime:local}"
mkdir -p "$OUT"
mkdir -p "$OVERLAY_DIR"
python "$ROOT/scripts/patch_osworld_docker_runtime.py" "$V2_DIR"
export OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export SWCUB_OSWORLD_OVERLAY_HOST_DIR="$OVERLAY_DIR"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
{
  echo "release=osworld-v2.1"
  echo "code_commit=$(git -C "$V2_DIR" rev-parse HEAD)"
  echo "runtime_image=$IMAGE"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$V2_DIR"
  uv run --frozen python quickstart.py --provider_name docker --os_type Ubuntu
} 2>&1 | tee "$OUT/run.log"
