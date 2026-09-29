# Real Application Track A: Writer + Calc Results

## Protocol

Task `CODESK-TA-OFFICE-001` version `1.0.0`, pinned OSWorld V2.1 Guest and LibreOffice 7.3.7.2. Scripted actors only; no model was loaded or run. The formal run configuration is [`configs/writer_calc_v1_validation.json`](configs/writer_calc_v1_validation.json): five repeats each for paired Solo, MA-ID, and MA-SD; two workers; four Guest slots; 15-second startup stagger. Artifacts are written to `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/writer-calc-v1-20260929/`.

Paired Solo consists of two independent single-actor Guest controls within each repeat: Writer alone on `writer_desktop`, Calc alone on `calc_desktop`. MA-ID runs both actors on separate Guests. MA-SD runs both on the same Guest using `writer_actor → calc_actor → writer_actor`.

## Preflight real-Guest pilots

These pilot episodes are preserved separately and are not included in the formal 5 × 3 repeat counts.

| Pilot | Outcome | Actor goals | Reset | Provenance / artifacts |
|---|---|---:|---:|---:|
| MA-SD, `writer-calc-v1-pilot-03` | Expected focus interference attributed | 0/2 final goals, as expected for negative control | Pass | Pass |
| Paired Solo, `writer-calc-v1-controls` | Both independent goals met | 2/2 | Pass | Pass |
| MA-ID, `writer-calc-v1-controls` | Both independent goals met | 2/2 | Pass | Pass |

MA-SD pilot routed Writer's Ctrl+A, replacement text, and save action to the active Calc window. The Calc B2 cell contained `Approved by GUI actor`, Writer remained at its initial text, and the exact ODF evaluator plus event log attributed the failure to shared focus/input. Resource lifecycle had create/destroy records for both task and reset Guests.

Two earlier MA-SD pilot attempts are also preserved: `writer-calc-v1-pilot` caught an ActorContext interface mismatch; `writer-calc-v1-pilot-02` caught the actor's `run()` versus `run_step()` dispatch mismatch. Neither is counted as a task interaction outcome. Both failures are in their own artifact roots with error logs and ownership ledgers; their Guests were closed through the runner lifecycle.

## Formal 15-episode validation

Completed on the real OSWorld V2.1 Guest pool. Artifacts, per-run logs, screenshots, resource ledgers, provenance, and the coordinator summary are under `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/writer-calc-v1-20260929/`. Each condition ran five episodes. Raw episode reports are unchanged; the corrected initial-state distinction and coordinator-verified integrity fields are captured in `posthoc_evaluation_audit.v2.json` beside the coordinator summary.

| Condition | Scenario outcomes | Writer goal | Calc goal | Reset | Median episode time |
|---|---:|---:|---:|---:|---:|
| Solo (paired single-actor controls) | 5/5 | 5/5 | 5/5 | 5/5 | 655.9 s |
| MA-ID (separate Guests) | 4/5 | 5/5 | 4/5 | 5/5 | 658.2 s |
| MA-SD (same desktop) | 4/5 focus-interference triggers | 0/5 | 0/5 | 5/5 | 402.4 s |

Overall, 13/15 condition scenarios met their expected outcome, all 15 resets passed, all 15 artifacts and provenance checks passed, and all current-run Guest containers had matching create/destroy ledger entries. The coordinator wall clock was 4,550.5 seconds (75.8 minutes), using two workers and at most four Guest slots. No model was loaded or run.

### Failure review

- **MA-ID repeat 2:** Writer goal passed; Calc B2 remained `Draft`, so Calc's goal failed. Both actors had independent desktops; the event log contains no misrouted or unknown input. The saved state supports a Calc scripted-action failure, not shared interference.
- **MA-SD repeat 2:** Writer and Calc files both stayed at their initial state. The saved screenshot and observed title show an empty `Untitled` Writer window instead of the seeded document. Three Writer inputs had unknown routes after the active-window tree disappeared. Because neither ODF change nor input route proves the intended cross-app contamination, this is an app-initialization / attribution failure, not a reproduced focus conflict.
- **MA-SD repeats 1, 3, 4, and 5:** Each had three Writer keyboard/text inputs routed to Calc, Calc contained `Approved by GUI actor`, Writer stayed at the initial text, and reset passed. These four repeats meet the frozen focus-interference trigger.

The 4/5 MA-SD result is a small scripted validation, not a statistical claim. It shows the mechanism is reproducible in this task instance while also exposing a document-open readiness gap. The current initial-state read is reliable at the ODF layer, but `seed_and_open()` only waits a fixed interval after launching Writer/Calc; it should verify visible document titles and seeded content before actor turns.

The original report's first contamination list also included baseline-preserving goal misses. `GuestLibreOfficeBindingEvaluator` now distinguishes a missed goal that leaves the initial value intact from an unexpected state mutation. The post-hoc audit applies that corrected rule to the exact final-state JSON already saved in all 15 reports, attaches artifact/provenance checks from the coordinator, and stores source SHA-256 hashes; no raw episode report was rewritten.

Run command:

```bash
python scripts/run_codesk_experiment.py configs/writer_calc_v1_validation.json
```

Recompute the separated goal/mutation view from preserved reports:

```bash
python scripts/audit_writer_calc_v1_results.py \
  /mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/writer-calc-v1-20260929 \
  --output /mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/writer-calc-v1-20260929/posthoc_evaluation_audit.v2.json
```

## Readiness-stable repeat set (post-hoc, separate from the formal 15)

After fixing visible-document readiness, the reset/check path, and serializing episodes after the 4-Guest initialization overload, five preserved episodes per condition were checked from the roots listed below. This is an additional repeat set; it does not replace or rewrite the formal table above. The selected records all have named Writer/Calc windows, verified initial state, exact ODF evaluation, passing reset, and ownership-ledger create/destroy records.

| Condition | Selected repeats | Expected outcome | Result |
|---|---|---|---:|
| Solo | `wc1-solo-smk` r1; `wc1-repeat3-a` r2; `wc1-solo3retry` r3; `wc1-repeat45-serial` r4–r5 | Both independent actor goals pass | 5/5 |
| MA-ID | `wc1-shared-smk` r1; `wc1-repeat2-parallel` r2; `wc1-repeat3-b` r3; `wc1-repeat45-serial` r4–r5 | Both actor goals pass on separate Guests | 5/5 |
| MA-SD | `wc1-shared-smk` r1; `wc1-repeat2-parallel` r2; `wc1-repeat3-a` r3; `wc1-repeat45-serial` r4–r5 | Shared-focus negative control is attributed | 5/5 |

All 15 selected episodes passed reset, final artifact checks, and resource lifecycle checks. Each MA-SD episode recorded three misrouted Writer keyboard/text actions and the expected cross-application contamination. The failed Solo readiness attempt from the overloaded 4-Guest run remains preserved and is excluded; its unique Solo r3 retry passed. These are engineering repeat checks on one task and one Guest image, not statistical evidence.

Serial repeat r4–r5 run config: `configs/writer_calc_v1_repeat45_serial.json`. Artifacts are in `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/`; the per-run IDs and raw results remain in each run root. The coordinator did not write the repeat45 summary on exit; `experiment_summary.json` there is explicitly marked as a post-run reconciliation from immutable episode reports and verified hashes.

## Local Qwen3-VL Solo smoke

The existing OSWorld V2.1 `Qwen3VLAgent` with local `Qwen3-VL-30B-A3B-Instruct` completed one paired Solo smoke: Writer and Calc each received their own real Guest, screenshot stream, action history, and 20-step budget. Each used 5 actions. Both exact goals passed; there was no contamination; both Guests reset to fresh IDs and all four task/reset containers have matching ledger entries. The complete trace, screenshots, report, and post-hoc provenance are preserved at `/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/qwen-solo-retry-20260929/ev1-wc1-qwen-solo-retry-20260929/`.

The first model start attempt is also retained under `qwen-solo-20260929`: the worker exceeded its 600-second startup deadline before either actor acted, so it is classified as model-runtime startup failure, not task/model capability failure. The retry loaded the local checkpoint successfully. Its actions and evaluator passed, but the process returned nonzero because provenance finalization rejected the external OSWorld source path. `error.json` and `provenance-error.txt` are retained; the later `provenance.json` sidecar explicitly records this reconciliation and hashes the original artifacts. Runner source now records the pinned checkout as `osworld-v2.1/<path>` and separates provenance finalization status from task outcome. See [`MODEL_SOLO_SMOKE_RESULTS.md`](MODEL_SOLO_SMOKE_RESULTS.md) for the exact command and action summary.

## Validation interpretation

The formal 15-episode results above validate their original run configuration and retain the observed readiness/Calc failures. Subsequent setup work added visible document identity, initial state, interactivity and persistence checks; the later readiness-stable repeat table records the separate outcomes after those checks. Neither set establishes broad generality across tasks or Guest images. The local model Solo smoke verifies the adapter and two goals once; no model shared condition was run.
