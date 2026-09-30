#!/usr/bin/env bash
# Read-only checksum verification for the A6000 migration payload.
set -euo pipefail
source "$(dirname "$0")/a6000_env.sh"
BASE_MANIFEST="$CODESK_A6000_ROOT/snapshots/migration-assets.sha256"
QWEN_MANIFEST="$CODESK_A6000_ROOT/snapshots/qwen3vl-runtime/qwen-model.sha256"
for manifest in "$BASE_MANIFEST" "$QWEN_MANIFEST"; do
  if [[ ! -r "$manifest" ]]; then
    echo "Required checksum manifest is missing: $manifest" >&2
    exit 2
  fi
done
(
  cd "$CODESK_A6000_ROOT"
  sha256sum --check "$BASE_MANIFEST"
  sha256sum --check "$QWEN_MANIFEST"
)
(
  cd "$CODESK_A6000_ROOT/snapshots/qwen3vl-runtime/transformers-pinned"
  sha256sum --check source-files.sha256
)
