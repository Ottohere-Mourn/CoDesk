#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
OUT="${OSWORLD_V2_RUN_DIR:-$ROOT/outputs/osworld-v2.1/quickstart}"
IMAGE="${OSWORLD_DOCKER_RUNTIME_IMAGE:-happysixd/osworld-docker@sha256:0e6497a9295647cf05bf2b2af522fdd79bdeba2737595259cab310a3bcf6baa9}"
mkdir -p "$OUT"
python "$ROOT/scripts/patch_osworld_docker_runtime.py" "$V2_DIR"
export OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
{
  echo "release=osworld-v2.1"
  echo "code_commit=$(git -C "$V2_DIR" rev-parse HEAD)"
  echo "runtime_image=$IMAGE"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$V2_DIR"
  uv run --frozen python quickstart.py --provider_name docker --os_type Ubuntu
} 2>&1 | tee "$OUT/run.log"
