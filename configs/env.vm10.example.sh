# VM10 profile. Copy to env.sh, fill in the model settings, then source it on VM10.
# Deployment and storage: docs/SERVER_PLAN.md. This file only exports configuration.

export OSCOMBO_ROOT="${OSCOMBO_ROOT:-/data/yuke/paraGUI}"
export OSWORLD_DIR="${OSWORLD_DIR:-$OSCOMBO_ROOT/OSWorld-V2}"
export OSWORLD_IMAGE_DIR="${OSWORLD_IMAGE_DIR:-$OSCOMBO_ROOT/images}"
export OSCOMBO_GUEST_IMAGE="${OSCOMBO_GUEST_IMAGE:-$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.qcow2}"
export OSCOMBO_OVERLAY_DIR="${OSCOMBO_OVERLAY_DIR:-$OSCOMBO_ROOT/overlays}"
export PARAGUI_TASK_ASSETS="${PARAGUI_TASK_ASSETS:-$OSCOMBO_ROOT/assets}"
export PARAGUI_TB_BASE="${PARAGUI_TB_BASE:-$OSCOMBO_ROOT/base/thunderbird-profile.tar.gz}"

# Local block storage on VM10. Archives here still need an off-host copy.
export OSCOMBO_RUNS_ROOT="${OSCOMBO_RUNS_ROOT:-$OSCOMBO_ROOT/runs}"
export OSCOMBO_ARCHIVE_DIR="${OSCOMBO_ARCHIVE_DIR:-$OSCOMBO_ROOT/archives}"

# Build with infra/build_runtime.sh. Prefer KVM after the container probe passes.
export OSCOMBO_RUNTIME_IMAGE="${OSCOMBO_RUNTIME_IMAGE:-oscombo/qemu-runtime:local}"
export OSCOMBO_GUEST_CPUS="${OSCOMBO_GUEST_CPUS:-8}"
export OSCOMBO_GUEST_RAM="${OSCOMBO_GUEST_RAM:-8G}"
export OSCOMBO_VM_READY_TIMEOUT="${OSCOMBO_VM_READY_TIMEOUT:-1800}"
export OSCOMBO_SHOT_PATIENCE="${OSCOMBO_SHOT_PATIENCE:-300}"
export OSCOMBO_DESKTOP_PATIENCE="${OSCOMBO_DESKTOP_PATIENCE:-240}"
export OSCOMBO_EVAL_SETTLE_SECONDS="${OSCOMBO_EVAL_SETTLE_SECONDS:-15}"

# Shell conveniences: oscombo does NOT read these three variables automatically.
# Pass them as queue --lanes / --stagger / --run-timeout (see the server plan).
export OSCOMBO_QUEUE_LANES="${OSCOMBO_QUEUE_LANES:-1}"
export OSCOMBO_QUEUE_STAGGER="${OSCOMBO_QUEUE_STAGGER:-60}"
export OSCOMBO_RUN_TIMEOUT="${OSCOMBO_RUN_TIMEOUT:-21600}"

export PATH="$OSWORLD_DIR/.venv/bin:$OSCOMBO_ROOT/bootstrap/bin:$PATH"

# Set in your private env.sh or in the calling environment. The endpoint must be
# reachable FROM VM10; localhost refers to VM10, not the development machine.
# export OPENAI_BASE_URL=https://your-model-endpoint/v1
# export OPENAI_API_KEY=...
# export OSCOMBO_MODEL=...
# export OSCOMBO_POLICY=openai-cua        # or chat-pyautogui for a compatible VLM

# Only when using the gated official OSWorld 2.0 task classes / assets:
# export HF_TOKEN=...
# export WEBSITE_HOST_SUFFIX=...

# TCG path only after establishing that the container cannot use /dev/kvm;
# setting this image path alone does not disable KVM device passthrough.
# export OSCOMBO_GUEST_IMAGE="$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.pngfast.qcow2"
