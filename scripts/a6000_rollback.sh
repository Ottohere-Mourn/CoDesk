#!/usr/bin/env bash
# Non-destructive rollback reminder. This script never stops/deletes resources or artifacts.
set -euo pipefail
source "$(dirname "$0")/a6000_env.sh"
echo "A6000 copy retained at: $CODESK_A6000_ROOT"
echo "Original 4090 workspace remains at: /home/mjh/Projects/Shared-Workspace-Benchmark-V0"
echo "Rollback: stop scheduling on A6000; resume the frozen 4090 workspace and its original config."
echo "Do not delete this copy or sync over old artifacts. Review A6000 run ledgers before any future cleanup."
git -C "$CODESK_ROOT" status --short --branch
