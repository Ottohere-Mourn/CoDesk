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


---

## Follow-up: 2026-10-02 remote Qwen pilot

This section supersedes the current-status conclusion above; the earlier preflight remains historical. Task definitions, Qwen3VLAgent implementation, prompts, budgets, and evaluators were not changed.

### Inference endpoint and end-to-end smoke

- 4090 inference host: **supermicr-EG840G-G20**.
- Selected physical GPUs: **4 and 5 only**. Immediately before launch both had no compute PID and about 48.5 GiB free. GPUs used by others were left alone.
- Model: **Qwen3-VL-30B-A3B-Instruct**, checkpoint /mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct, BF16, no quantization, two-GPU device_map=auto; config SHA-256 6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912. Worker PID during these runs: 3960076; CUDA visibility 4,5; mapped logical devices 0,1.
- A6000 Guest/coordinator: **admin123-Super-Server**; remote inference endpoint was reached over the established SSH reverse tunnel at loopback port 15485.
- **Endpoint smoke: PASS.** A genuine 1504x832 screenshot from an earlier A6000 OSWorld Writer run was sent through the live endpoint. Qwen returned text in 9.997 seconds; the pinned Qwen3VLAgent parser produced pyautogui.click(575, 288). The smoke did not execute that action. Artifacts: /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/remote-inference-endpoint-smoke/20261002-r01/.
- Pilot request/response latency was generally about 5-17 seconds per inference call. OSWorld printed a nonfatal missing optional dataimpulse.json warning at runner startup.
- The worker and its run-specific reverse tunnel were stopped after collection. The endpoint no longer listens. Per-episode inference events, model traces and screenshots are saved; worker stdout was attached to the execution session and is not a separate artifact file.

### C-01 Clipboard

Raw reports are under /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/qwen-family-pilot/.

| Condition | Attempts / effective runs | Goal outcome | Reset | Finding |
|---|---:|---:|---:|---|
| Solo A / Writer | 3 attempts / 2 effective | 0/2 pass | 2/2 effective runs pass | Both valid runs failed exact Writer placement. Final text was REF-7319REF-7319\n and REF-7319\nREF-7319\n, instead of REF-7319\nREF-7319. No recopy recovery. |
| Solo A r01 | 1 invalid repeat | evaluator failed | reset verification absent | Kept as c01-solo-a-r01-20261002; runner artifact-copy bug raised before reset verification. Ledger confirms the run-owned Guest was destroyed. Append-only audit: posthoc/runner-reset-audit.json. Not counted as an effective repeat. |
| Solo B / Calc | 2 / 2 | 2/2 pass | 2/2 pass | Exact Calc target state; no non-goal contamination. |
| MA-ID / MA-SD | not run | — | — | Frozen pilot gate requires both Solo goals to pass before shared conditions. Solo A failed both effective repeats, so shared conditions were withheld. |

C-01 observer initialization reported status ok, but its idle Solo A sample had no X11 owner/payload (owner_xid=null, payload_read=false, generation 0). Since no shared episode ran, Qwen clipboard overwrite, wrong paste caused by another actor, and autonomous recopy remain unobserved. C-01 is not model-level closed.

### A-01 Application Context

Task CODESK-TE-APP-CONTEXT-00000000, version 1.0.0-rc4. Reports, screenshots, server events and model traces are saved under their run IDs below.

| Condition | Runs | Goal-state outcome | Runner completion / reset | Finding |
|---|---|---|---|---|
| Solo A | r01, r02 | 2/2 pass | completed, reset 2/2 | A entered CTX-A-04100 on tab-a; tab-b remained unchanged. |
| Solo B | r01, r02, r03 | 2/3 pass | reset 3/3 | r02 entered B's CTX-B-08200 into tab-a and left tab-b empty; r01/r03 passed. A third repeat followed the conflicting first two outcomes. |
| MA-ID | r01, r02, r03 | Evaluator joint goals pass 1/3; fail 2/3 | runner status model_task_failure 3/3; reset 3/3 | r01: A passed, B wrote to tab-a. r02: both oracle goals and non-target checks passed, but B used all 20 steps without terminating, so the runner marked the episode failure. r03: A passed, B failed. This is variable performance under isolation, not evidence of shared-desktop interference. |
| MA-SD | r01, r02 | joint goal pass 0/2 | runner status model_task_failure 2/2; reset 2/2 | Both actors' values ended up on tab-a; tab-b stayed empty. Every sampled active tab stayed tab-a (tab_change_count=0). No cross-tab context change, supported stale observation, or autonomous recovery was observed. |

Both MA-SD reports set condition-level scheduled_exposure=true, but the task evaluator reports cross_tab_contention_exposure=false because no tab activation was observed. Scheduled condition is not observed exposure. Final states support wrong-target placement, but do not establish that the other actor changed context before the action; these failures are task/grounding failures, not proven Application Context interference.

Preserve one evaluator diagnostic inconsistency for follow-up: each MA-SD timeline contains only one window ID (window_id_count=1), while the derived same_top_level_window field is false. The evaluator was not changed; use the raw timeline, not this derived field.

### F-01 anchor and family-level decision

F-01 was not rerun, as requested. Reused historical Qwen evidence: Solo pass; MA-ID joint pass 2/2; MA-SD joint fail 2/2 with supported focus/input-routing interference. This is prior evidence, not a new run.

| Family | Authentic Qwen evidence | Exposure / interference | Recovery | Closure |
|---|---|---|---|---|
| Focus / F-01 | Historical evidence | Historical MA-SD focus/input-routing interference supported | No reliable successful autonomous recovery established | Anchor evidence retained |
| Clipboard / C-01 | Solo only | No shared condition; overwrite/interference unknown | No recopy recovery; Writer Solo goal not solved | **Not closed** |
| Application Context / A-01 | Solo, MA-ID, MA-SD | MA-SD scheduled, but no active-tab change observed; interference unsupported | No successful return-to-tab recovery | **Not closed as a mechanism** |

**Decision: CONTINUE PILOT. Do not begin instance generation.** C-01 is gated by repeated Solo A failure. A-01 has real model condition data, but MA-SD did not expose a context change and its evaluator has an inconsistent derived field; it does not yet demonstrate the proposed mechanism. This small pilot is not a performance estimate.

### Implementation and validation record

- Fixed the runner's post-evaluation artifact-copy loop to unpack each (episode, desktop) binding. Before the fix, C-01 r01 already had an evaluator failure but raised before reset verification. The original report and artifacts remain intact; task, model, prompt, schedule, and evaluator are unchanged.
- Every A-01 run has reset_success=true. The two effective C-01 Solo A runs and both Solo B runs also have reset verified.
- Transient screenshot-service timeouts occurred during A-01 MA-SD r01. The runner recovered and produced a complete report with reset true; these are environment warnings, not model failures. C-01 r01 remains excluded above.
- There were 15 C-01/A-01 run attempts. One C-01 attempt is invalid for missing reset verification; all remaining runs preserve model traces and reports. No scripted actor was used. F-01 remains historical and separate.
- No evaluator semantics, task definitions, model weights, quantization, prompt protocol, or other users' processes/resources were changed. No push was performed.
