#!/usr/bin/env bash
# Imports the project-owned, checksum-verified runtime archive and builds a project-tagged overlay.
# It does not remove or overwrite images and is intentionally not run during migration prep.
set -euo pipefail
source "$(dirname "$0")/a6000_env.sh"
ARCHIVE="$CODESK_A6000_ROOT/snapshots/osworld-v2.1-qemu-runtime-local.tar"
EXPECTED_ARCHIVE_SHA256=fca808b4ae7029f702b7c02957d89b6fb0bde0c1a3a7704f96308b0db1de41b5
EXPECTED_BASE_ID=sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec
BASE_TAG=swcub/osworld-v2.1-qemu-runtime:local
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon access is unavailable; refusing to load/build." >&2
  exit 20
fi
if ! [[ -r "$ARCHIVE" ]]; then
  echo "Runtime archive is missing: $ARCHIVE" >&2
  exit 21
fi
archive_sha=$(sha256sum "$ARCHIVE" | awk '{print $1}')
if [[ "$archive_sha" != "$EXPECTED_ARCHIVE_SHA256" ]]; then
  echo "Runtime archive checksum mismatch; refusing docker load." >&2
  exit 24
fi
if ! docker image inspect "$BASE_TAG" >/dev/null 2>&1; then
  docker load --input "$ARCHIVE"
fi
actual=$(docker image inspect --format '{{.Id}}' "$BASE_TAG")
if [[ "$actual" != "$EXPECTED_BASE_ID" ]]; then
  echo "Base image ID mismatch: expected $EXPECTED_BASE_ID, got $actual" >&2
  exit 22
fi
if docker image inspect "$SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE" >/dev/null 2>&1; then
  project=$(docker image inspect --format '{{index .Config.Labels "org.swcub.project"}}' "$SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE")
  if [[ "$project" == CoDesk ]]; then
    echo "Project runtime image already exists; leaving it unchanged: $SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"
    exit 0
  fi
  echo "Target image tag exists without CoDesk ownership label; refusing to overwrite." >&2
  exit 23
fi
docker build --pull=false \
  --label org.swcub.project=CoDesk \
  --label org.swcub.runtime=osworld-v2.1-qemu-a6000 \
  --tag "$SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE" \
  --file "$CODESK_ROOT/infra/osworld-v2.1-qemu-runtime/Dockerfile.a6000" \
  "$CODESK_ROOT/infra/osworld-v2.1-qemu-runtime"
