#!/usr/bin/env bash
# One-time setup on the machine that runs the Guests:
#   1. clone OSWorld-V2 at the pinned osworld-v2.1 release into $OSWORLD_DIR
#   2. download + verify the pinned Ubuntu Guest image into $OSWORLD_IMAGE_DIR
#   3. create the OSWorld venv (uv) and install oscombo into it
#   4. patch the docker provider (infra/patch_osworld.py)
# Re-running is safe; finished steps are skipped.
#
#   OSWORLD_DIR=/path/OSWorld-V2 OSWORLD_IMAGE_DIR=/path/images bash infra/setup_osworld.sh [--with-mcp]
#
# OSWORLD_SKIP_FFMPEG=1: do not build OSWorld's bundled-ffmpeg package (its build downloads a static ffmpeg from
# a single upstream host that is sometimes unreachable). Then put a system ffmpeg/ffprobe on PATH; only
# recording and video-related evaluators use them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${OSWORLD_DIR:?set OSWORLD_DIR (where to clone OSWorld-V2)}"
: "${OSWORLD_IMAGE_DIR:?set OSWORLD_IMAGE_DIR (where to store the ~15 GB Guest image)}"
RELEASE="osworld-v2.1"
TAG_COMMIT="3d778a3c9a34a079316f70df023b166700445792"
ARTIFACT_COMMIT="6e16459a2feb5a8f1ed65babcfe7a2a6205d049d"
ARTIFACT_NAME="osworld-v2-ubuntu-x86.qcow2.zip"
ARTIFACT_SIZE="14891811084"
ARTIFACT_SHA256="14b08aa7ba6c023ecb91d46de8df5de32af4d1d6bd75ea925519caf9677fc8b3"
HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"

for tool in git uv curl unzip; do
  command -v "$tool" >/dev/null || { echo "missing host tool: $tool" >&2; exit 2; }
done

if [[ ! -d "$OSWORLD_DIR/.git" ]]; then
  git clone --depth 1 --branch "$RELEASE" https://github.com/xlang-ai/OSWorld-V2.git "$OSWORLD_DIR"
fi
actual="$(git -C "$OSWORLD_DIR" rev-parse HEAD)"
[[ "$actual" == "$TAG_COMMIT" ]] || { echo "OSWorld checkout is $actual, expected $TAG_COMMIT" >&2; exit 3; }

mkdir -p "$OSWORLD_IMAGE_DIR"
zip_path="$OSWORLD_IMAGE_DIR/$ARTIFACT_NAME"
qcow_path="$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.qcow2"
if [[ ! -s "$qcow_path" ]]; then
  if [[ ! -f "$zip_path" || "$(stat -c %s "$zip_path")" != "$ARTIFACT_SIZE" ]]; then
    curl --fail --location --retry 5 --retry-delay 5 --retry-all-errors --connect-timeout 20 \
      --continue-at - --output "$zip_path" \
      "$HF_ENDPOINT/datasets/xlangai/v2-image/resolve/$ARTIFACT_COMMIT/$ARTIFACT_NAME"
  fi
  [[ "$(stat -c %s "$zip_path")" == "$ARTIFACT_SIZE" ]] || { echo "Guest archive size mismatch" >&2; exit 5; }
  echo "$ARTIFACT_SHA256  $zip_path" | sha256sum --check --status || { echo "Guest archive SHA256 mismatch" >&2; exit 6; }
  unzip -o "$zip_path" -d "$OSWORLD_IMAGE_DIR"
fi
[[ -s "$qcow_path" ]] || { echo "no Guest image at $qcow_path" >&2; exit 7; }

sync_args=(--frozen --no-dev)
[[ "${OSWORLD_SKIP_FFMPEG:-0}" == "1" ]] && sync_args+=(--no-install-package osworld-ffmpeg)
(cd "$OSWORLD_DIR" && uv sync "${sync_args[@]}") || {
  echo "uv sync failed; if the osworld-ffmpeg build could not download ffmpeg, rerun with OSWORLD_SKIP_FFMPEG=1" >&2
  exit 4
}
extras=""
[[ "${1:-}" == "--with-mcp" ]] && extras="[mcp]"
uv pip install --python "$OSWORLD_DIR/.venv/bin/python" -e "$ROOT$extras"
"$OSWORLD_DIR/.venv/bin/python" "$ROOT/infra/patch_osworld.py" "$OSWORLD_DIR"

echo "OSWorld code:  $OSWORLD_DIR ($actual)"
echo "Guest image:   $qcow_path"
echo "Python:        $OSWORLD_DIR/.venv/bin/python   (python -m oscombo ...)"
