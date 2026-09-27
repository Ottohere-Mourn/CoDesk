# First Qwen3VLAgent Shared-Workspace Comparison

## Result status

This is a five-repeat exploratory comparison of one fixed Browser + Writer task pair on the real OSWorld V2.1 QEMU Guest. It is not a statistical result. Both solo controls and all sequential and focus-aware episodes passed their independent programmatic goals. Naive interleaving did not produce one joint success in five episodes.

| Condition | Qwen Browser goal | Scripted Writer goal | Joint success | Reset success |
|---|---:|---:|---:|---:|
| Qwen solo | 5/5 | not active | 5/5 | 5/5 |
| Writer solo | not active | 5/5 | 5/5 | 5/5 |
| Sequential shared | 5/5 | 5/5 | 5/5 | 5/5 |
| Naive shared interleaving | 2/5 | 0/5 | 0/5 | 5/5 |
| Focus-aware shared | 5/5 | 5/5 | 5/5 | 5/5 |

The six episode series used the same task specification and seeded initial state, but each episode used a newly launched Guest. Within each shared episode, both actors used the same Guest instance, desktop, applications, keyboard, and pointer. `report.json` records the shared environment/container identity for the actors, independent goals, evaluation, and reset check.

## Fixed setup

- OSWorld: pinned checkout `/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1`, release V2.1, code commit `3d778a3c9a34a079316f70df023b166700445792` (recorded in each `run.log`).
- GUI model agent: the existing OSWorld V2.1 `Qwen3VLAgent`; no planner, model, agent, task, or evaluator changes were made for this comparison.
- Model: local `Qwen3-VL-30B-A3B-Instruct` weights at `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`, loaded with local Transformers inference (`local_files_only`, device `auto`). No paid API or model download was used.
- Task: `SWCUB-BROWSER-WRITER-PAIR-001`; Qwen submits `Approved by GUI actor` in the visible Browser review form, and a scripted Writer actor replaces and saves the Writer document with the same text. Each actor has a separate evaluator goal.
- Shared conditions ran on one Guest per episode. The evaluator checked the Browser state and Writer file after the actor schedule. Evaluator-only state was not passed to Qwen; Qwen received its task instruction and OSWorld observations.
- Qwen sampling was deterministic (`do_sample=False`). The Browser actor retained its configured 20-step maximum. In Naive Shared, the scripted Writer turn was interleaved after each scheduled Qwen turn; the model could observe the resulting desktop and recover on later turns. No incorrect action was inserted by the scheduler.
- Solo controls were required by the runner before shared conditions. The Qwen Browser solo series passed 5/5. Five complete successful Writer solo attempts were selected from the preserved calibration artifacts; failed/incomplete calibration attempts remain available and are not counted in the 5/5 denominator.

Writer calibration had setup and interaction failures before the five valid successes: `run-03` reached evaluator success but lacked a completed reset record; `run-03-attempt-03`, `run-05`, and `run-05-attempt-02` failed Guest/browser preflight; `run-05-attempt-03` and `run-05-attempt-04` completed with the Writer document unchanged. The later `run-05-attempt-05` passed. These directories and logs are preserved; the shared runner only accepted complete success reports with successful resets as solo controls.

## Per-episode outcomes

`Q` is the Browser goal, `W` the Writer goal, `J` their conjunction. Qwen steps are the number recorded in the evaluator report. Focus and input counts use the project’s event-derived metrics in that report.

| Condition / run | Q | W | J | Qwen steps | Focus mismatch | Unintended focus | Mis-input | Reset |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen solo 01 | pass | n/a | pass | 5 | 0 | 0 | 0 | pass |
| Qwen solo 02 | pass | n/a | pass | 5 | 0 | 0 | 0 | pass |
| Qwen solo 03 | pass | n/a | pass | 5 | 0 | 0 | 0 | pass |
| Qwen solo 04 | pass | n/a | pass | 5 | 0 | 0 | 0 | pass |
| Qwen solo 05 | pass | n/a | pass | 4 | 0 | 0 | 0 | pass |
| Writer solo 01 | n/a | pass | pass | — | 1 | 0 | 0 | pass |
| Writer solo 02 | n/a | pass | pass | — | 1 | 0 | 0 | pass |
| Writer solo 03-attempt-02 | n/a | pass | pass | — | 1 | 0 | 0 | pass |
| Writer solo 04 | n/a | pass | pass | — | 1 | 0 | 0 | pass |
| Writer solo 05-attempt-05 | n/a | pass | pass | — | 0 | 0 | 0 | pass |
| Sequential 01 | pass | pass | pass | 5 | 1 | 0 | 0 | pass |
| Sequential 02 | pass | pass | pass | 4 | 1 | 0 | 0 | pass |
| Sequential 03 | pass | pass | pass | 4 | 1 | 0 | 0 | pass |
| Sequential 04 | pass | pass | pass | 4 | 1 | 0 | 0 | pass |
| Sequential 05 | pass | pass | pass | 5 | 1 | 0 | 0 | pass |
| Naive shared 01 | fail | fail | fail | 20 | 7 | 4 | 3 | pass |
| Naive shared 02 | fail | fail | fail | 20 | 20 | 19 | 0 | pass |
| Naive shared 03 | pass | fail | fail | 7 | 5 | 3 | 3 | pass |
| Naive shared 04 | pass | fail | fail | 7 | 5 | 3 | 3 | pass |
| Naive shared 05 | fail | fail | fail | 20 | 9 | 8 | 1 | pass |
| Focus-aware 01 | pass | pass | pass | 7 | 4 | 1 | 1 | pass |
| Focus-aware 02 | pass | pass | pass | 7 | 4 | 1 | 1 | pass |
| Focus-aware 03 | pass | pass | pass | 7 | 4 | 1 | 1 | pass |
| Focus-aware 04 | pass | pass | pass | 7 | 4 | 1 | 1 | pass |
| Focus-aware 05 | pass | pass | pass | 7 | 4 | 1 | 1 | pass |

The focus-aware `mis-input` counter is an event-derived proxy. In these five runs it counts a Writer `Ctrl+A` action whose recorded active-window transition starts on Chrome and ends on Writer; the action was later recovered and the final document passed. It should not be read as five unrecovered corruptions. Conversely, the Naive counts align with independently verified failures: for example, run-01 records Writer text/save input while Chrome is active, and run-05 leaves `Ved by GUI actorQuarterly status report` in Writer.

## Failure and interaction reading

- **Solo/model baseline:** Qwen succeeded on the same Browser goal in all five selected solo episodes. The two Naive runs where it exhausted the 20-step limit are therefore not explained by a general inability to perform this calibrated Browser task. This does not prove the shared desktop alone caused each failure; action traces still need to be considered per episode.
- **Naive shared:** the model succeeded in Browser in runs 03 and 04, while Writer failed in all five. Runs 01 and 02 exhausted the model step budget; run 05 also exhausted it and left corrupted Writer text. The event logs show focus mismatch, mis-input, or both in every run. This is direct evidence of observed cross-actor desktop/focus effects in this task, not an estimate of their frequency beyond this setup.
- **Sequential shared:** both goals passed in all five episodes. The task scheduler ran the Qwen Browser segment before the two Writer turns. The one focus mismatch per episode is the Writer’s explicit Alt+Tab handoff from Chrome to Writer, and it was later recovered. No mis-input was recorded.
- **Focus-aware shared:** both goals passed in all five episodes; the pre-turn app activation succeeded in all recorded actor turns (9/9 per episode). One event-derived mis-input proxy was recorded in each run and later recovered without affecting final artifacts. This supports the utility of this particular focus-aware policy on this task; it does not show that all concurrent multi-agent workflows can be solved by focus activation.
- **Reset/reproducibility:** all 25 selected formal episodes and both actors’ five-repeat solo controls have successful reset checks (`task_files_absent=true`). Each report also points to the episode resource ledger. Failed and incomplete Writer calibration attempts were preserved separately; they were not deleted or silently counted as successful repeats.

These are small deterministic exploratory runs on one task and one local model. They do not establish statistical significance, generalize to different task types/models, or isolate all causal mechanisms. Naive’s model step-budget failures and the Writer’s focus/input failures should remain separate outcome categories in subsequent experiments.

## Artifacts and reproduction

Artifact root (on RAID1):

`/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/first-model-comparison/active-window-v2/runs`

Each episode directory contains the programmatic `report.json`, unified `events.jsonl`, `resource-events.jsonl`, screenshots/observations, and (for Qwen episodes) `model_trace.jsonl` plus the local model worker log. The failed Naive episodes’ screenshots and action trajectories are retained alongside successful runs.

The shared-condition batch command was:

```bash
python scripts/run_first_model_comparison.py \
  --artifact-root /mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/first-model-comparison/active-window-v2/runs \
  --repeats 5 \
  --conditions sequential naive-shared focus-aware
```

The driver verified and reused complete successful solo controls before launching shared episodes. The final repository regression command was `python -m pytest -q`: **60 passed in 141.12s**. `git diff --check` is also run before checkpointing this report.

## Checkpoint and next step

The experiment used project checkpoint `46fef5a` plus the completed artifacts above. This report will be committed as the comparison checkpoint. The next experiment should retain the same Qwen, task, and evaluator while adding a different GUI application task pair or a carefully controlled recovery variant. It should continue logging actor-level goal success separately from joint success, focus transitions, and post-interaction file/application integrity. Do not treat these five-repeat observations as benchmark validation or a general policy result.
