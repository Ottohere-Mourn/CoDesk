#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
IMAGE="${OSWORLD_DOCKER_RUNTIME_IMAGE:-swcub/osworld-v2.1-qemu-runtime:local}"
GUEST_IMAGE="${SWCUB_OSWORLD_GUEST_IMAGE:-$V2_DIR/docker_vm_data/osworld-v2-ubuntu-x86.qcow2}"
ARTIFACT_PARENT="${CODESK_TRACK_A_ARTIFACT_PARENT:-/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a}"

export OSWORLD_V2_DIR="$V2_DIR"
export CODESK_TRACK_A_ARTIFACT_PARENT="$ARTIFACT_PARENT"
export SWCUB_OSWORLD_GUEST_IMAGE="$GUEST_IMAGE"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
export OSWORLD_DOCKER_RUNTIME_IMAGE="$IMAGE"
cd "$ROOT"
uv --project "$V2_DIR" run --frozen python "$ROOT/scripts/run_track_a_v1.py" "$@"
