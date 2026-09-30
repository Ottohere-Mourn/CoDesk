#!/usr/bin/env bash
# Local, non-secret CoDesk paths for the A6000 project copy.
set -euo pipefail
export CODESK_A6000_ROOT=/home1/mjh/Projects/CoDesk-V0-A6000
export CODESK_ROOT="$CODESK_A6000_ROOT/CoDesk"
export CODESK_PYTHON="$CODESK_A6000_ROOT/envs/osworld-v2.1/bin/python"
export UV_PROJECT_ENVIRONMENT="$CODESK_A6000_ROOT/envs/osworld-v2.1"
export UV_PYTHON=/usr/bin/python3
export PATH="$CODESK_A6000_ROOT/tools:$PATH"
export OSWORLD_V2_DIR="$CODESK_A6000_ROOT/external/OSWorld-V2-osworld-v2.1"
export SWCUB_OSWORLD_GUEST_IMAGE="$CODESK_A6000_ROOT/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2"
export SWCUB_OSWORLD_CACHE_DIR="$CODESK_A6000_ROOT/assets/osworld-v2.1/task-cache"
export SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE=swcub/osworld-v2.1-qemu-runtime:a6000
export SWCUB_MODEL_PYTHON="$CODESK_A6000_ROOT/envs/qwen/bin/python"
export SWCUB_LOCAL_VLM_PATH="$CODESK_A6000_ROOT/models/Qwen/Qwen3-VL-30B-A3B-Instruct"
# Fail closed: model runs must explicitly choose a GPU set after scheduling approval.
export CUDA_VISIBLE_DEVICES="${CODESK_CUDA_VISIBLE_DEVICES:-}"
export CODESK_ARTIFACT_ROOT="$CODESK_A6000_ROOT/artifacts"
