# CPU15 profile: source on cpu15. No sudo or processes are launched by this file.
# Active deployment notes: docs/SERVER_PLAN.md. Do not source the VM10 profile first.
export OSCOMBO_ROOT="${OSCOMBO_ROOT:-$HOME/data/paraGUI}"
export OSWORLD_DIR="${OSWORLD_DIR:-$OSCOMBO_ROOT/OSWorld-V2}"
export OSWORLD_IMAGE_DIR="${OSWORLD_IMAGE_DIR:-$OSCOMBO_ROOT/images}"
export OSCOMBO_GUEST_IMAGE="${OSCOMBO_GUEST_IMAGE:-$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.qcow2}"
export OSCOMBO_OVERLAY_DIR="${OSCOMBO_OVERLAY_DIR:-$OSCOMBO_ROOT/overlays}"
export PARAGUI_TASK_ASSETS="${PARAGUI_TASK_ASSETS:-$OSCOMBO_ROOT/assets}"
export PARAGUI_TB_BASE="${PARAGUI_TB_BASE:-$OSCOMBO_ROOT/base/thunderbird-profile.tar.gz}"
export OSCOMBO_RUNS_ROOT="${OSCOMBO_RUNS_ROOT:-$OSCOMBO_ROOT/runs}"
export OSCOMBO_ARCHIVE_DIR="${OSCOMBO_ARCHIVE_DIR:-$OSCOMBO_ROOT/archives}"

# Build/restore images before a run. Verify container KVM separately.
export OSCOMBO_RUNTIME_IMAGE="${OSCOMBO_RUNTIME_IMAGE:-oscombo/qemu-runtime:local}"
export OSCOMBO_GUEST_CPUS="${OSCOMBO_GUEST_CPUS:-8}"
export OSCOMBO_GUEST_RAM="${OSCOMBO_GUEST_RAM:-8G}"
export OSCOMBO_VM_READY_TIMEOUT="${OSCOMBO_VM_READY_TIMEOUT:-1800}"
export OSCOMBO_SHOT_PATIENCE="${OSCOMBO_SHOT_PATIENCE:-300}"
export OSCOMBO_DESKTOP_PATIENCE="${OSCOMBO_DESKTOP_PATIENCE:-240}"
export OSCOMBO_EVAL_SETTLE_SECONDS="${OSCOMBO_EVAL_SETTLE_SECONDS:-15}"

# Shell conveniences only: pass explicitly to oscombo queue.
export OSCOMBO_QUEUE_LANES="${OSCOMBO_QUEUE_LANES:-1}"
export OSCOMBO_QUEUE_STAGGER="${OSCOMBO_QUEUE_STAGGER:-60}"
export OSCOMBO_RUN_TIMEOUT="${OSCOMBO_RUN_TIMEOUT:-21600}"
export PATH="$OSWORLD_DIR/.venv/bin:$OSCOMBO_ROOT/bootstrap/bin:$PATH"

# Configure API credentials privately on the host. Never copy them into snapshots.
# export OPENAI_BASE_URL=https://your-model-endpoint/v1
# export OPENAI_API_KEY=...
# export OSCOMBO_MODEL=...
# export OSCOMBO_POLICY=openai-cua
# Professional/Astra runners require explicit --api-json and --codex-bin;
# they do not consume these OSWorld model defaults. See docs/SERVER_PLAN.md.
