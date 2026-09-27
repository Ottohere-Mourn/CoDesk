# OSWorld V2.1 Qwen3VLAgent Baseline Calibration

**Status:** 15/15 real Guest episodes complete. Solo baseline does not meet the entry gate for shared experiments.

## Fixed baseline

- OSWorld V2.1 checkout: commit `3d778a3c9a34a079316f70df023b166700445792`.
- Agent: the release's `mm_agents/qwen3vl_agent.py::Qwen3VLAgent`, with its existing prompt construction, visual history, action parser, relative-coordinate conversion, and PyAutoGUI actions.
- Weights: local `Qwen3-VL-30B-A3B-Instruct`, loaded offline from `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`; model config SHA-256 `6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912`.
- Inference: existing loopback-only Transformers worker, `do_sample=False`, local files only. No paid endpoint, new model weights, or training.
- Guest: the existing OSWorld V2.1 Ubuntu image and local runtime image `swcub/osworld-v2.1-qemu-runtime:local` (image ID `sha256:002d09fa7cc4e08ce5321c3d0a261e336a2c17651726f8538bca4dcf991e82ec`).
- Evaluators and task instances are unchanged. Each run starts from the task's existing initial state; the independent evaluator reads authoritative Guest state after the actor stops. A Guest reset check runs after each episode.

The only Browser addition is a Qwen actor invocation of the already-defined solo goal `agent_goal = "Approved by GUI actor"`; its expected state and `GuestWebStateEvaluator` remain unchanged. The first Browser preflight exposed an empty screenshot returned after a real click. That preflight is preserved under the artifact root but excluded from the formal five runs. The adapter now retries a transient empty screenshot up to three times and logs/saves refreshed frames.

## Tasks and success criteria

| Task | Fixed solo goal | Evaluator success |
|---|---|---|
| Writer | Replace the existing paragraph with exactly `Approved by GUI actor`, then save; do not edit the spreadsheet. | Exact Writer document text and unchanged Calc sheet |
| Calc | Change cell B2 from `Draft` to `Approved`, save, and preserve other cells. | Exact Calc cell grid and unchanged Writer document |
| Browser | Enter exactly `Approved by GUI actor` in the GUI Agent Goal field and submit. | Exact `agent_goal` value in the local Guest backend |

Success rate uses `evaluation.success`; reset success is reported separately. Each of the three tasks has five fresh Guest episodes scheduled. Five repeats are an engineering calibration set, not a statistical performance claim.

## Results

| Task | Successful evaluator runs | Runs | Success rate | Reset checks | Status |
|---|---:|---:|---:|---:|---|
| Writer | 2 | 5 | 40% | 5/5 passed | complete |
| Calc | 0 | 5 | 0% | 5/5 passed | complete |
| Browser | 5 | 5 | 100% | 5/5 passed | complete |

Per-run step counts, failure classes, exact final states, action responses, native actions, and screenshots are stored with each report and summarized below.

### Completed Writer trials

| Run | Evaluator | Steps | Observed outcome | Reset |
|---|---|---:|---|---|
| 01 | fail | 5 | Used Ctrl+V after Ctrl+A; Writer remained unchanged. | pass |
| 02 | pass | 5 | Typed the requested text, saved, and terminated. | pass |
| 03 | fail | 5 | Used Ctrl+V after Ctrl+A; Writer remained unchanged. | pass |
| 04 | pass | 5 | Typed the requested text, saved, and terminated. | pass |
| 05 | fail | 20 | Repeated Ctrl+A/Ctrl+V through the actor step budget; Writer remained unchanged. | pass |

### Completed Calc trials

| Run | Evaluator | Steps | Observed outcome | Reset |
|---|---|---:|---|---|
| 01 | fail | 8 | B2 became `DrafApproved` after the agent deleted only the final character of `Draft` and typed the new value. | pass |
| 02 | fail | 8 | Repeated B2 clicks and backspaces left the value `Approvedft` rather than exactly `Approved`. | pass |
| 03 | fail | 8 | F2/edit mode and Backspace removed only the last character before the agent appended `Approved`, again leaving `DrafApproved`. | pass |
| 04 | fail | 7 | F2/edit mode and Backspace again left `DrafApproved` instead of replacing the full cell value. | pass |
| 05 | fail | 8 | Entered edit mode and appended `Approved` after deleting only the last character, leaving `DrafApproved`. | pass |

### Completed Browser trials

| Run | Evaluator | Steps | Observed outcome | Reset |
|---|---|---:|---|---|
| 01 | pass | 4 | Clicked the GUI Agent Goal field, typed the exact value, submitted, and terminated successfully. | pass |
| 02 | pass | 5 | First dismissed a lower-right overlay, then clicked the goal field, typed the exact value, submitted, and terminated. | pass |
| 03 | pass | 5 | Dismissed a lower-right overlay, entered the exact goal, submitted, and terminated. | pass |
| 04 | pass | 4 | Clicked the goal field, entered the exact value, submitted, and terminated. | pass |
| 05 | pass | 5 | Dismissed a lower-right overlay, entered the exact goal, submitted, and terminated. | pass |

## Failure taxonomy

- `model_task_failure`: agent completed or exhausted its step budget but the exact evaluator state was wrong.
- `model_or_action_execution_failure` / `environment_or_action_execution_failure`: native action execution or usable observation failed before the task could be completed.
- `none`: evaluator passed. Reset failures are recorded separately and do not change the task success-rate numerator.
- A wrong value in another application is also recorded as a cross-application integrity failure by the unchanged office evaluator.

## Turn scheduler

`swcub.turn_scheduler.TurnScheduler` provides round-robin one-step turns, a per-actor step budget, pause/resume, one-turn yield, and reset. `OSWorldAgentActor.run_step` performs one native OSWorld observe/predict/action batch and keeps the official agent's history across turns. Its `max_steps=20` budget bounds each episode. The environment adapter refresh path is used only to recover transient empty frames; it adds no action selection or task logic. Scheduler pause/resume/yield/reset and budget behavior have unit coverage in `tests/test_turn_scheduler.py`.

## Entry gate for shared-workspace experiments

Proceed to sequential/shared experiments only if **each** solo task achieves at least 4/5 evaluator successes, all five reset checks pass, the existing regression suite passes, and each successful/failed episode has its report, event log, action trace, and screenshots. This is a conservative engineering gate, not a significance test. If any task misses it, do not interpret shared-condition failures until the solo task or environment reliability is addressed without changing the task or evaluator.

**Decision: do not enter sequential/shared experiments.** Browser passes 5/5 and every reset passes, but Writer reaches only 2/5 and Calc 0/5. All 10 Writer/Calc failures are `model_task_failure` with the evaluator's exact state mismatch; none are reset failures. Browser's five successes demonstrate that this baseline can complete the simple local form, not that it is reliable across office tasks. The office result is insufficient to attribute later joint-task failures to interaction effects.

## Final failure taxonomy and outcome

- Writer failed 3/5. Runs 01 and 03 used Ctrl+V after selecting all text, which left the original paragraph unchanged. Run 05 repeated Ctrl+A/Ctrl+V until exhausting its 20-step budget; the document remained unchanged. The two passes typed the exact text, saved, and terminated in five steps.
- Calc failed 5/5. Four runs left `DrafApproved`; one left `Approvedft`. The trace shows edit-mode/backspace or repeated cell-edit actions that failed to replace the exact original value. Writer remained unchanged, so this was a task-state failure rather than cross-application contamination.
- Browser passed 5/5 in 4–5 steps. Runs 02, 03, and 05 first dismissed a lower-right overlay, then all trials entered the exact goal, submitted, and observed the success state.
- All 15 Guest reset checks passed and confirmed task files absent from the replacement Guest. The preflight Browser observation failure is excluded from the 15 formal trials and remains separately preserved.

Aggregate: **7/15 evaluator successes (46.7%)** across these three fixed, non-equivalent tasks. This pooled value is descriptive only; per-task rates govern the entry gate. Browser success must not mask the Writer and Calc deficits.

## Reproduction

From the repository root:

```bash
python scripts/calibrate_qwen_baseline.py --repeat 5 --resume
```

The script uses the existing local OSWorld checkout, Guest image, runtime image, and local model. It resumes only from complete reports and writes all large artifacts to:

`/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/{office,browser}/baseline-calibration/`

Each task run directory contains `report.json`, `events.jsonl`, `model_trace.jsonl`, captured observation screenshots, `model_worker.log`, and `console.log`. `model_trace.jsonl` records step index, screenshot hash and size, response text, native action strings, inference time, and screenshot refresh count.

The machine-readable 15-run aggregate is `/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/baseline-calibration/summary.json`; per-task episode artifacts are under the task paths listed above.

## Operational incident

During environment diagnosis, an older stopped/created Docker container named `focused_curran` (`easyr1:latest`, creation time reported as 2026-01-09) was mistakenly removed. It predated this calibration and was not created by these runs. Its container metadata cannot be reconstructed from the available record. No image or other container was removed.
