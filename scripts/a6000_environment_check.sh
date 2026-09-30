#!/usr/bin/env bash
# Read-only A6000 readiness checks. Does not create containers or change permissions.
set -uo pipefail
source "$(dirname "$0")/a6000_env.sh"
failed=0
show() { printf '%-28s %s\n' "$1" "$2"; }
show hostname "$(hostname)"
show user "$(id -un) uid=$(id -u)"
show project_root "$CODESK_ROOT"
show guest_image "$SWCUB_OSWORLD_GUEST_IMAGE"
if [[ -x "$CODESK_PYTHON" ]]; then pyver=$("$CODESK_PYTHON" --version 2>&1); else pyver=$(python3 --version 2>&1); fi
show python "$pyver"
show uv "$(command -v uv || echo not-installed)"
show docker_cli "$(docker --version 2>&1 || echo unavailable)"
if docker info >/dev/null 2>&1; then
  show docker_daemon access-ok
  if docker image inspect "$SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE" >/dev/null 2>&1; then show runtime_image present; else show runtime_image missing; failed=1; fi
else
  show docker_daemon permission-or-daemon-failure
  show runtime_image uncheckable
  failed=1
fi
if [[ -r /dev/kvm && -w /dev/kvm ]]; then show kvm access-ok; else show kvm inaccessible; failed=1; fi
if [[ -r "$SWCUB_OSWORLD_GUEST_IMAGE" ]]; then show qcow readable; else show qcow missing; failed=1; fi
if [[ -d "$OSWORLD_V2_DIR" ]]; then show osworld_checkout present; else show osworld_checkout missing; failed=1; fi
if [[ -x "$OSWORLD_V2_DIR/.venv/bin/python" ]]; then show copied_venv snapshot-present-but-not-used; else show copied_venv nonportable-rebuild-required; fi
if [[ -x "$CODESK_PYTHON" ]]; then show isolated_osworld_python present; else show isolated_osworld_python not-built; fi
if [[ -x "$SWCUB_MODEL_PYTHON" ]]; then show model_python present; else show model_python not-configured; fi
if [[ -f "$SWCUB_LOCAL_VLM_PATH/config.json" ]]; then show qwen_config present; else show qwen_config missing-or-not-transferred; fi
shard_count=$(find "$SWCUB_LOCAL_VLM_PATH" -maxdepth 1 -type f -name "model-*-of-*.safetensors" 2>/dev/null | wc -l)
if [[ -f "$SWCUB_LOCAL_VLM_PATH/model.safetensors.index.json" && "$shard_count" -eq 13 ]]; then show qwen_weights complete-13-shards; else show qwen_weights incomplete-or-not-transferred; fi
df -h "$CODESK_A6000_ROOT" 2>&1 | tail -1
exit "$failed"
