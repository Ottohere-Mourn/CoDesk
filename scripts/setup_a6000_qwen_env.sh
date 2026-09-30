#!/usr/bin/env bash
# User-local model environment setup. Does not load model weights or touch GPUs.
set -euo pipefail
source "$(dirname "$0")/a6000_env.sh"
export UV_CACHE_DIR="$CODESK_A6000_ROOT/cache/uv"
export UV_CONCURRENT_DOWNLOADS=1
export UV_CONCURRENT_BUILDS=1
export UV_HTTP_TIMEOUT=300
export UV_HTTP_RETRIES=2
MODEL_ENV="$CODESK_A6000_ROOT/envs/qwen"
PYTHON_DIR="$CODESK_A6000_ROOT/tools/python"
if [[ -x "$MODEL_ENV/bin/python" ]]; then
  PYTHON_BIN="$MODEL_ENV/bin/python"
else
  PYTHON_BIN="$PYTHON_DIR/cpython-3.13.2-linux-x86_64-gnu/bin/python3.13"
  if [[ ! -x "$PYTHON_BIN" ]]; then
    if timeout 120 "$CODESK_A6000_ROOT/tools/uv" python install 3.13.2 --install-dir "$PYTHON_DIR"; then
      :
    else
      echo "Pinned CPython download failed or timed out; falling back to system Python 3.12.3." >&2
      PYTHON_BIN="$(command -v python3.12)"
    fi
  fi
  "$CODESK_A6000_ROOT/tools/uv" venv --python "$PYTHON_BIN" "$MODEL_ENV"
fi
timeout 1200 "$CODESK_A6000_ROOT/tools/uv" pip install --python "$MODEL_ENV/bin/python" \
  --index-url https://download.pytorch.org/whl/cu128 \
  --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --index-strategy unsafe-best-match \
  torch==2.7.0+cu128 torchvision==0.22.0+cu128
timeout 600 "$CODESK_A6000_ROOT/tools/uv" pip install --python "$MODEL_ENV/bin/python" \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  -r "$CODESK_A6000_ROOT/snapshots/qwen3vl-runtime/requirements.pypi.lock.txt"
SITE_PACKAGES="$("$MODEL_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
PINNED_SOURCE="$CODESK_A6000_ROOT/snapshots/qwen3vl-runtime/transformers-pinned"
if [[ ! -d "$SITE_PACKAGES/transformers" ]]; then
  test -d "$PINNED_SOURCE/transformers"
  test -d "$PINNED_SOURCE/transformers-5.5.0.dev0.dist-info"
  cp -a "$PINNED_SOURCE/transformers" "$SITE_PACKAGES/"
  cp -a "$PINNED_SOURCE/transformers-5.5.0.dev0.dist-info" "$SITE_PACKAGES/"
fi
"$MODEL_ENV/bin/python" - <<'PY'
import importlib.metadata as md
import json
from pathlib import Path
import torch, transformers, accelerate, qwen_vl_utils
d = md.distribution("transformers")
direct = json.loads((Path(d._path) / "direct_url.json").read_text())
assert direct["vcs_info"]["commit_id"] == "abc417a4b6cf05e474921449641f2ff0cc93d3dd"
print("python", __import__("sys").version.split()[0])
print("torch", torch.__version__, "CUDA build", torch.version.cuda)
print("transformers", transformers.__version__, "commit", direct["vcs_info"]["commit_id"])
print("accelerate", accelerate.__version__)
print("qwen_vl_utils", qwen_vl_utils.__version__ if hasattr(qwen_vl_utils, "__version__") else "import-ok")
PY
