#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${OSWORLD_DOCKER_RUNTIME_IMAGE:-swcub/osworld-v2.1-qemu-runtime:local}"
docker image inspect ubuntu:22.04@sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751 >/dev/null
docker build --pull=false --platform linux/amd64 --tag "$IMAGE" \
  --file "$ROOT/infra/osworld-v2.1-qemu-runtime/Dockerfile" \
  "$ROOT/infra/osworld-v2.1-qemu-runtime"
docker image inspect --format '{{.Id}}' "$IMAGE"
