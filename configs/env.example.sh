# Copy to env.sh (git-ignored), fill in, and `source env.sh` before running oscombo.
# Nothing in here is required to be secret except API keys; keep keys out of git.

# --- OSWorld checkout + Guest image (infra/setup_osworld.sh) ---
export OSWORLD_DIR=/path/to/OSWorld-V2
export OSCOMBO_GUEST_IMAGE=/path/to/images/osworld-v2-ubuntu-x86.qcow2   # or the *.pngfast.qcow2 (no KVM)
export PATH="$OSWORLD_DIR/.venv/bin:$PATH"                               # python with desktop_env + oscombo

# --- docker provider (infra/patch_osworld.py) ---
# export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock    # rootless docker
# export OSCOMBO_RUNTIME_IMAGE=oscombo/qemu-runtime:local      # hosts without /dev/kvm (infra/build_runtime.sh)
# export OSCOMBO_OVERLAY_DIR=/path/to/fast/disk/overlays       # per-Guest qcow2 overlays (GBs each)
# export OSCOMBO_GUEST_CPUS=8 OSCOMBO_GUEST_RAM=8G             # 12 vCPUs for heavy apps (Blender) under TCG

# --- slow Guests (TCG) ---
# export OSCOMBO_SHOT_PATIENCE=300        # s to wait for a screenshot before declaring the Guest dead (INFRA)
# export OSCOMBO_EVAL_SETTLE_SECONDS=15   # s before evaluation, lets saves finish

# --- model endpoints ---
# OpenAI-compatible endpoint used by openai-cua / transports / codex and pi harnesses (any proxy or gateway works):
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=...                 # put the real key in env.sh only
# export OSCOMBO_RATE_LIMIT_RETRIES=60    # short randomized retries on HTTP 429 (shared deployments)

# --- OSWorld 2.0 task classes ---
# export HF_TOKEN=...                                   # task / asset downloads from Hugging Face
# export OSWORLD_FILE_BASE_URL=/path/to/osworld_v2_assets   # local snapshot of the task assets, if you have one
# export WEBSITE_HOST_SUFFIX=...                        # host suffix of the OSWorld web mock sites (OSWorld-V2 docs)
