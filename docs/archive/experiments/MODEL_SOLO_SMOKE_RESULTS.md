# CoDesk Writer + Calc: local Qwen3-VL Solo smoke

## Scope

One real model smoke of the frozen Writer/Calc V1 task on the OSWorld V2.1 Guest. It uses the existing OSWorld `Qwen3VLAgent` and local checkpoint `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`. There are two independent Solo controls in the episode: Writer and Calc each operate on a distinct Guest and pursue their existing task goal. No task, prompt, model weights, or evaluator rules were changed. No paid API or remote inference was used.

## Result

| Actor | Guest target | Steps | Goal | Contamination |
|---|---|---:|---|---|
| Writer | `document.fodt` | 5 / 20 | Pass: `Approved by GUI actor` | None |
| Calc | `table.fods`, Sheet1 B2 | 5 / 20 | Pass: B2=`Approved`, other cells unchanged | None |

The hidden evaluator returned `success=true`. Both application windows were ready on their named documents; setup validation confirmed initial ODF state, interactivity, and persistence. Both environments reset to new Guest IDs, task files were absent after reset, and all task/reset containers had matching create/destroy entries under this run's ownership labels. The model produced real screenshot-conditioned actions; this was not scripted or mock inference.

Artifacts (20 screenshots, 10 model steps, raw model responses, native actions, worker log, reports, event and resource ledgers):

`/mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/qwen-solo-retry-20260929/ev1-wc1-qwen-solo-retry-20260929/`

## Action trace summary

- Writer clicked the text, selected the paragraph, entered the requested replacement, saved, and returned `DONE`.
- Calc selected B2, entered cell edit mode, removed the existing text, typed `Approved`, saved, and returned `DONE`.
- The model's processed screenshot size was 1504×832 from a 1920×1080 Guest display. OSWorld's native parser handled coordinate scaling and action execution.
- Observed inference times ranged from 8.4 to 24.5 seconds for Writer and 6.1 to 35.3 seconds for Calc. These are single-episode timings, not throughput estimates.

## Startup/finalization failures retained

The first attempt at `qwen-solo-20260929` reached model-worker startup but timed out at the 600-second health deadline before the actor loop. Initial application setup had passed; there are no model action steps in that attempt. It is classified as worker startup/runtime failure and excluded from model capability scoring. The retry increased only the service startup deadline to 1,800 seconds and started from the existing local weights/cache.

The successful episode itself completed both goals, evaluator, and reset. Its original process exit was nonzero because provenance finalization used `Path.relative_to()` on the pinned OSWorld checkout outside the CoDesk repository. The original `error.json` and `provenance-error.txt` remain unchanged. A `provenance.json` sidecar was added with `provenance_origin=posthoc_reconciliation_from_immutable_episode_report`, hashes of the preserved files, and an explanation. The runner now records such pinned external source files with an explicit `external:` path key. The report's task score was not edited.

## Reproduction

```bash
bash scripts/run_writer_calc_v1.sh \
  --condition solo \
  --repeat 1 \
  --run-id ev1-wc1-qwen-solo-retry-20260929 \
  --artifact-parent /mnt/raid1/mjh/CoDesk-V1-artifacts/real-app-track-a/qwen-solo-retry-20260929 \
  --actor-implementation qwen3vl
```

The exact command above will refuse to reuse the already occupied run directory. Choose a new unique `--run-id` and artifact parent for another run; this smoke should not be repeated merely to overwrite its evidence.

## Gate and next step

Both required independent Solo goals passed on the real Guest, so the interface-level Solo gate is met once. This only establishes that the adapter can drive these two task instances. Before running any model shared condition, first verify the fixed adapter/provenance changes with non-destructive regression checks, then obtain a separately named Solo repeat for stability. If either Actor misses its Solo target on a repeat, preserve it and stop model shared-condition expansion. No Qwen sequential/shared/focus-aware episode was run in this phase.
