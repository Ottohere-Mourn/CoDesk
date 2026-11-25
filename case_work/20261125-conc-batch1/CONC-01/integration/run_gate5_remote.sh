#!/usr/bin/env bash
set -euo pipefail

OUT=${1:?provide a new output directory}
STAGE=${2:?provide the versioned staging directory}
REPO=/mnt/raid1/mjh/Projects/CoDesk-food-recall-pilot-20261124
OSWORLD=/home/mjh/.cache/codesk-food-recall-setup-20261124/osworld-source
PY=/home/mjh/.cache/codesk-food-recall-setup-20261124/osworld-venv/bin/python
TASK="$STAGE/runner-source/case_work/20261125-conc-batch1/CONC-01/integration/task_conc01gate5.py"
ASSETS="$STAGE/task-assets"
IMAGE=/dev/shm/codesk-next3/osworld-v2-ubuntu-x86.qcow2

mkdir -p "$OUT/eval-artifacts"
cat > "$OUT/agents.json" <<'JSON'
[{"harness":"step","policy":"scripted","options":{"actions":["DONE"]}}]
JSON

export OSWORLD_DIR="$OSWORLD"
export PARAGUI_TASK_ASSETS="$ASSETS"
export PYTHONPATH="$STAGE/runner-source:$REPO:$OSWORLD${PYTHONPATH:+:$PYTHONPATH}"
export OSCOMBO_BACKEND=docker
export CONC01_EVAL_OUT="$OUT/eval-artifacts"

unset OPENAI_API_KEY OPENAI_BASE_URL HAOGPT_API_KEY SUB2API_API_KEY
exec "$PY" -m oscombo run --mode solo --tasks "$TASK" --out "$OUT" \
  --agents "$OUT/agents.json" --image "$IMAGE" --max-steps 2 --setup-settle 5 \
  --label case=CONC-01 --label purpose=gate5-reference-no-model
