# Local visual model validation

Date: 2026-09-27. All model trials used the pinned OSWorld V2.1 Guest and actual LibreOffice UI. No paid API, remote inference service, model training, or weight download was used.

## Local resources and loop

- GPUs: 8 × RTX 4090. Inference used free `cuda:0`; `cuda:1` was occupied by an unrelated process.
- Existing checkpoints: `/mnt/raid1/mjh/models/Qwen/Qwen2.5-VL-3B-Instruct` and `/mnt/raid1/mjh/models/Qwen3-VL-4B-Instruct`.
- The model worker uses `/opt/miniconda3/bin/python`, Transformers 5.5.0.dev0, CUDA, and `local_files_only=True`. It binds only to `127.0.0.1`; the OSWorld task runner starts/stops it per episode.
- Each inference request contains only the task prompt and a Guest screenshot. The worker has no evaluator interface or expected-state file. The host runner keeps final-state checks and task files outside the model process.
- The actor accepts one allowlisted JSON action at a time (`click`, `type`, `key`, `done`). Screenshot dimensions are recorded; current full-screen mapping is 1:1 (1920×1080 screenshot pixels to Guest PyAutoGUI pixels), with bounds checks. Raw text is preserved when JSON parsing or action validation fails.
- `model_trace.jsonl` records each prompt and response, parsed action, screenshot SHA-256, dimensions, observed revision, stale-image marker, inference time, and validation error. `events.jsonl` attributes the inference and Guest action to the actor.

## Scripted negative controls

Repeated on fresh Guests before model runs. All three expected failures were detected by exact programmatic evaluators, task files were absent after reset, and a new Guest container ID was observed.

| Condition | Expected evaluator finding | Event-log validation |
|---|---|---|
| GUI+GUI naive Writer/Calc focus interleaving | Writer remains draft; GUI text contaminates Calc | V1, 25 events |
| GUI+CLI stale browser save | CLI update is missing after GUI saves cached state | V1, 19 events |
| GUI+Human Replay naive focus | Human entry persists; GUI target is lost | V1, 19 events |

Reports and screenshots are under `outputs/osworld-v2.1/office/naive-interleaving-repeat-02/`, `outputs/osworld-v2.1/browser/gui-cli-stale-repeat-02/`, and `outputs/osworld-v2.1/browser/human-agent-naive-repeat-02/`.

## Real local-model solo trials

| Model/task | Observed action and final state | Evaluator/reset | Attribution |
|---|---|---|---|
| Qwen2.5-VL-3B, Writer | First output included an out-of-bounds click; then clicked Writer, but repeatedly chose `type` before `Ctrl+A`. The guarded actor stopped; Writer stayed `Quarterly status report`. Five inference records. | Evaluator rejected exact target; reset passed and removed task files. | Model task/instruction-following failure. No second actor was present. |
| Qwen2.5-VL-3B, Calc | Clicked A2, typed `Approved`, saved, then failed to finish the task. A2 became `Approved`; B2 remained `Draft`. Eight inference records. | Evaluator detected wrong-cell mutation; reset passed. | Model GUI grounding/task failure. No second actor was present. |
| Qwen3-VL-4B, Calc | Returned valid click/type/save/done JSON. Clicked `(116,230)`, which is A2 in this screenshot; A2 became `Approved`, B2 remained `Draft`. Four inference records. | Evaluator detected wrong-cell mutation; reset passed. | Model GUI grounding/task failure. No second actor was present. |

Per-episode raw evidence, including screenshots and full event logs:

- `outputs/osworld-v2.1/office/writer-model-solo-qwen2_5vl-3b-attempt-05/`
- `outputs/osworld-v2.1/office/calc-model-solo-qwen2_5vl-3b-attempt-01/`
- `outputs/osworld-v2.1/office/calc-model-solo-qwen3vl-4b-attempt-01/`

The Qwen2.5 runner initially used the coarse label `model_or_action_execution_failure` for the Writer and Calc guard aborts. Review of the raw traces shows their rejected actions were task-sequencing/target errors, so their final audit attribution is `model_task_failure`; the JSON report field was corrected while retaining the original value as `initial_failure_classification`. Qwen3 reports `model_task_failure` directly.

## Commands

```bash
scripts/run_osworld_v2_1_office.sh writer-model-solo
scripts/run_osworld_v2_1_office.sh calc-model-solo
SWCUB_LOCAL_VLM_PATH=/mnt/raid1/mjh/models/Qwen3-VL-4B-Instruct \
  scripts/run_osworld_v2_1_office.sh calc-model-solo
```

Set `OSWORLD_V2_RUN_DIR` for a distinct output directory. The command creates a fresh Guest; it does not use scripted actors for model actions.

## Current boundary

No local model passed the solo target reliably in these three trials. Therefore no model sequential, naive-shared, focus-aware, or model+Human comparison was run: such outcomes could not distinguish model task errors from shared-desktop effects. Existing successful scripted GUI+GUI and GUI+Human episodes are separate evidence and are not model results. The sample is an engineering smoke test, not a benchmark score or statistical conclusion.

Final repository regression after the Qwen3 worker-selection and failure-label edits: `python -m pytest -q` — **51 passed, 0 failed in 30.80s**. Task manifest/instances, compileall, shell syntax, whitespace, and all six scripted/model event logs validated successfully.
