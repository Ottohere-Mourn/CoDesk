#!/usr/bin/env bash
# Build the QEMU runtime image (needed on hosts without /dev/kvm; optional otherwise).
#   bash infra/build_runtime.sh            -> image oscombo/qemu-runtime:local
# Then: export OSCOMBO_RUNTIME_IMAGE=oscombo/qemu-runtime:local
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${OSCOMBO_RUNTIME_IMAGE:-oscombo/qemu-runtime:local}"
docker build --platform linux/amd64 --tag "$IMAGE" "$ROOT/infra/qemu-runtime"
docker image inspect --format '{{.Id}}' "$IMAGE"
