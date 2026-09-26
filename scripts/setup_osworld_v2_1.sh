#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V2_DIR="${OSWORLD_V2_DIR:-$(cd "$ROOT/.." && pwd)/_deps/OSWorld-V2-osworld-v2.1}"
CACHE_DIR="${OSWORLD_VM_CACHE_DIR:-/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data}"
RELEASE="osworld-v2.1"
TAG_COMMIT="3d778a3c9a34a079316f70df023b166700445792"
ARTIFACT_COMMIT="6e16459a2feb5a8f1ed65babcfe7a2a6205d049d"
ARTIFACT_NAME="osworld-v2-ubuntu-x86.qcow2.zip"
ARTIFACT_SIZE="14891811084"
ARTIFACT_SHA256="14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3"

if ! command -v git >/dev/null || ! command -v uv >/dev/null || ! command -v curl >/dev/null; then
  echo "Required host tools: git, uv, curl" >&2
  exit 2
fi

if [[ ! -d "$V2_DIR/.git" ]]; then
  mkdir -p "$(dirname "$V2_DIR")"
  git clone --depth 1 --branch "$RELEASE" https://github.com/xlang-ai/OSWorld-V2.git "$V2_DIR"
fi

actual_commit="$(git -C "$V2_DIR" rev-parse HEAD)"
if [[ "$actual_commit" != "$TAG_COMMIT" ]]; then
  echo "OSWorld checkout mismatch: expected $TAG_COMMIT, got $actual_commit" >&2
  exit 3
fi
python - "$V2_DIR/benchmark_releases/$RELEASE.json" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
assert manifest["release"] == "osworld-v2.1"
assert manifest["status"] == "active"
assert manifest["osworld_code"]["tag"] == "osworld-v2.1"
assert manifest["provider_images"]["docker"]["ubuntu"]["artifact_sha256"] == (
    "sha256:14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3"
)
print("release manifest: osworld-v2.1; pinned code/tasks/assets/website/provider refs present")
PY

mkdir -p "$CACHE_DIR"
zip_path="$CACHE_DIR/$ARTIFACT_NAME"
qcow_path="$CACHE_DIR/osworld-v2-ubuntu-x86.qcow2"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
if [[ ! -f "$zip_path" ]]; then
  artifact_url="$HF_ENDPOINT/datasets/xlangai/v2-image/resolve/$ARTIFACT_COMMIT/$ARTIFACT_NAME"
  curl --fail --location --retry 5 --retry-delay 5 --retry-all-errors \
    --connect-timeout 20 --max-filesize "$ARTIFACT_SIZE" --continue-at - \
    --output "$zip_path" "$artifact_url"
fi
actual_size="$(stat -c %s "$zip_path")"
if [[ "$actual_size" != "$ARTIFACT_SIZE" ]]; then
  echo "OSWorld archive size mismatch: expected $ARTIFACT_SIZE, got $actual_size" >&2
  exit 5
fi
echo "$ARTIFACT_SHA256  $zip_path" | sha256sum --check --status || {
  echo "OSWorld archive SHA256 mismatch" >&2
  exit 6
}
if [[ ! -s "$qcow_path" ]]; then
  unzip -o "$zip_path" -d "$CACHE_DIR"
fi

if [[ ! -s "$qcow_path" ]]; then
  echo "Pinned OSWorld qcow2 was not extracted to $qcow_path" >&2
  exit 7
fi

link="$V2_DIR/docker_vm_data"
if [[ -e "$link" && ! -L "$link" ]]; then
  echo "Refusing to replace a non-symlink OSWorld docker_vm_data path: $link" >&2
  exit 8
fi
ln -sfn "$CACHE_DIR" "$link"

echo "OSWorld code: $actual_commit"
echo "OSWorld Ubuntu Guest: $qcow_path"
echo "Guest archive SHA256: $ARTIFACT_SHA256"
echo "Installing pinned OSWorld host dependencies in its local .venv..."
(cd "$V2_DIR" && uv sync --frozen --no-dev)

if [[ "${OSWORLD_V2_DOWNLOAD_GATED_ASSETS:-0}" == "1" ]]; then
  if ! hf auth whoami >/dev/null 2>&1; then
    echo "Gated task/assets download skipped: run 'hf auth login' and accept the OSWorld datasets first." >&2
    exit 9
  fi
  (cd "$V2_DIR" && uv run --frozen scripts/tools/download_osworld_v2_tasks.py --benchmark-release "$RELEASE")
  (cd "$V2_DIR" && uv run --frozen scripts/tools/download_osworld_v2_assets.py \
    --benchmark-release "$RELEASE" --target-dir "cache/osworld_v2_assets_v2.1")
fi

echo "OSWorld V2.1 environment assets and host dependencies are ready."
