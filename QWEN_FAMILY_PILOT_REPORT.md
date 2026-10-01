# CoDesk Qwen Family Pilot Report

Date: 2026-10-01. Canonical repository: A6000 `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`. This report records the pilot gate and implementation state; it does not claim new model episodes.

## Outcome

**Pilot execution is blocked before valid episode startup.** No Qwen worker, Guest, or new task episode was started in this round. The Qwen endpoint on 4090 (`127.0.0.1:15485`) was not listening. Starting the 30B worker was deferred because the inference host showed sustained severe contention: load average 167.22 (1 min), CPU PSI `some avg10=62.22%`, and only 96 KiB swap free. Available RAM was about 176 GiB. GPU 0 and 2 were idle; the other 4090 GPUs had allocations and were not touched. Existing weights/config were readable at the previously configured path, but that did not make inference safe under the observed CPU pressure.

No Guest was launched just to produce an unusable result. Therefore there are **zero valid new C-01/A-01 model episodes and zero INVALID_INFRA episodes**; this is a blocked preflight, not a model failure.

## Family evidence

| Family / task | Existing Qwen evidence verified | New Qwen evidence this round | Status |
|---|---|---|---|
| Focus / F-01 | `focus-solo-qwen-r01-20260930`: both goals pass; `focus-maid-qwen-r03-20260930` and `focus-maid-qwen-valid-r02-20260930`: both actors pass; `focus-masd-qwen-r01-20260930` and `focus-masd-qwen-r02-20260930`: joint evaluator fails. Reports identify active Writer actions while Calc is foreground and preserve real model traces. All list inference host `supermicr-EG840G-G20` (4090). | None; the existing five episodes satisfy the current Round-1 anchor/control requirement. | **Model evidence exists.** Small historical sample; MA-SD has supported focus/input-routing interference, but no reliable successful autonomous recovery was demonstrated. |
| Clipboard / C-01 | Real-Guest scripted Solo A/B, MA-ID, MA-SD overwrite, observer and scripted recopy controls exist under `artifacts/mechanism-validation-round1/clipboard/`. No Qwen trial. | None. | **Scripted only; model closure not met.** |
| Application Context / A-01 | Real-Guest scripted Solo A/B, MA-ID, MA-SD and scripted reacquisition controls exist for task `CODESK-TE-APP-CONTEXT-00000000`, version `1.0.0-rc4`. No Qwen trial. | None. | **Scripted only; model closure not met.** |

For F-01, the raw five run reports were inspected. The shared outcomes were not inferred from the scripted fixture: both MA-SD reports have `joint_success=false`; one has 20 focus/input mismatch actions, the other 4. The established task-level evidence is bounded to this task and schedule.

## Pilot runner preparation

Added `scripts/run_qwen_family_pilot.py`, a thin task runner that reuses the pinned `Qwen3VLAgent`, existing `OSWorldAgentActor`, `ActorContext`, clipboard task setup/observer/evaluator, A-01 browser setup/private evaluator, and the existing OSWorld Guest creator/reset/provenance ledger. It keeps per-Actor agent history, prompts, screenshots, action traces and a 20-decision budget; MA-ID and MA-SD use the same alternating actor-turn policy. It does not change task data or evaluator code. The runner has only been syntax/import/CLI checked offline; it has **not** been exercised against a Guest, model endpoint, or live task.

Planned invocation after 4090 pressure recovers and the existing inference service is available:

```bash
source scripts/a6000_env.sh
export SWCUB_QWEN_INFERENCE_URL=http://127.0.0.1:15485
export SWCUB_QWEN_INFERENCE_HOST=supermicr-EG840G-G20
$CODESK_PYTHON scripts/run_qwen_family_pilot.py \
  --family clipboard --condition solo_a --run-id clipboard-soloa-qwen-r01-20261001 \
  --artifact-parent "$CODESK_ARTIFACT_ROOT/qwen-family-pilot"
```

For `C-01`, run `solo_a`, `solo_b`, `ma_id`, `ma_sd`; for `A-01`, use the same conditions with `--family app_context`. Run each valid condition twice, stop if consistent, add at most a third repeat only for conflicting outcomes. Do not start a family’s shared conditions unless both Solo goals pass. Keep any readiness/inference/reset failures as `INVALID_INFRA` artifacts, outside the model denominator.

Known gate before reuse: worker health must identify `Qwen3-VL-30B-A3B-Instruct`; the reverse SSH loopback tunnel must be active; use only the already idle 4090 GPUs 0 and 2 if inference startup is explicitly safe. Do not place model inference on A6000 or touch other users’ GPUs.

## Offline validation and limits

- `python -m py_compile scripts/run_qwen_family_pilot.py`: PASS.
- `scripts/run_qwen_family_pilot.py --help`: PASS (OSWorld emits a non-fatal missing optional `dataimpulse.json` proxy-config warning during import).
- Existing offline regression set: **32 passed** (`test_clipboard_observer.py`, `test_prototype_tasks_v1.py`, `test_task_factory_v1.py`).
- `git diff --check`: PASS.
- No Guest, Docker, model worker, task episode, or evaluator semantics were changed/run.

## Decision

Do **not** begin instance generation yet. F-01 has real Qwen evidence, but both C-01 and A-01 still have no model evidence. Resume with the C-01/A-01 Solo gate after 4090 inference pressure and the Qwen endpoint are healthy; then run MA-ID and MA-SD with the frozen tasks and evaluator. Decision: **CONTINUE PILOT**.
