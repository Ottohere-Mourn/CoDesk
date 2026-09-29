# CoDesk Parallel Stability Report

## Scope

This report covers (1) a read-only analysis of the preceding two-worker failure and (2) a bounded regression after readiness/retry changes. Both runs use the pinned OSWorld V2.1 Guest and unchanged Track A `ma_sd` task `CODESK-TA-GUI-FOCUS-001` version `1.0.0`, scripted actors, and the existing evaluator. Each mode uses repeats 1 and 2. Actor order remains `document_actor → chat_actor → document_actor`; worker parallelism is episode-level only.

Regression run ID: `tracka-p10-stab-2357`

Artifacts, host samples, worker logs, per-episode traces/screenshots/reports/provenance, and ownership ledgers are retained under:

`/mnt/raid1/mjh/CoDesk-V1-artifacts/parallel-pilot/tracka-p10-stab-2357/`

Reproduction command:

```bash
python scripts/run_track_a_parallel_pilot.py \
  --pilot-id tracka-p10-stab-2357 \
  --condition ma_sd --episodes 2 --workers 2 \
  --startup-stagger-seconds 15
```

## Analysis of the preceding HTTP 500 episode

The failed job was parallel repeat 1 from pilot `tracka-p10-20260928-2315`. Its per-episode trace and resource ledger show:

- The two workers started Guest creation about 0.8 seconds apart. Both Guests passed the runner's previous readiness gate, which only required a nonblank screenshot. Their `guest.desktop_ready` events were about six seconds apart.
- The failing episode's `osworld.refresh_observation` event occurred about 50 seconds after its screenshot-only ready event. The other worker refreshed about 24 seconds after readiness and had a usable accessibility tree. The failed worker logged repeated accessibility endpoint HTTP 500 responses at refresh; its observation stored `accessibility_tree: null` and no active-window title.
- The scheduler continued the declared actor turns with that observation. The evaluator found both target goals missing and text appended in Chat, but all keyboard destinations were `null`, so it could not attribute the input to a focused window. It correctly reported the expected MA-SD conflict as not detected; the task runner exited 1 after preserving evidence and completing reset.
- The old coordinator took only start, between-mode, and end host snapshots. At the failure time it has no direct short-interval host sample. Available host samples show 80 logical CPUs and high historical load averages at run start (1/5/15 min: 1.83/73.96/111.54), while available memory stayed around 211 GiB and swap was nearly full. These measurements do not establish that host pressure caused the HTTP 500.
- Container creation was briefly serialized by the OSWorld Docker provider's shared port/container-start lock, but the workers then booted separate Guests. The prior pilot had unique run IDs, overlays, event roots, provenance, and ownership ledgers. All Guest/reset Guest create/destroy records matched; no active container remained afterward.

**Finding:** the immediate trigger is confirmed as accessibility data unavailable during post-setup observation, after a screenshot-only readiness pass. The exact underlying cause (Guest service timing, synchronized application setup, host scheduling, or another transient) remains unproven. The previous runner allowed actors to proceed with unknown input routing, which converted an infrastructure/observation problem into an un-attributable task result.

## Stability changes

The changes are limited to environment health, scheduling, and result collection:

1. Guest readiness now requires both a visibly rendered screenshot and a nonempty accessibility tree when the pinned OSWorld configuration requires one. Readiness events record attempts, accessibility availability, and timing.
2. `OSWorldSharedEpisode.refresh_observation` makes at most three bounded attempts when required observation data is missing. If the tree remains unavailable, the episode fails before actors consume an unattributable observation. The task evaluator and its predicates are unchanged.
3. A readiness failure preserves any partial artifacts and closes the exact episode Guest through the existing ownership-verified provider path. The current-run resource ledger remains authoritative.
4. The two-worker coordinator now staggers job submission by 15 seconds by default, samples host load/memory every five seconds during parallel mode, and stores per-worker start/end host snapshots.
5. Aggregation separates task/scenario success, reset success, artifact/provenance integrity, accessibility/observation failures, and ordinary blank-screen boot polling. The boot poll counter is not counted as an accessibility-service failure.

## Bounded regression results

| Measure | Sequential, 2 episodes | Two workers, 2 episodes |
|---|---:|---:|
| Batch wall time | 709.798 s | 352.348 s |
| Episode latency | 352.406 s; 350.460 s | 346.673 s; 333.877 s |
| Median Guest readiness, task and reset Guests | 125.680 s | 120.929 s |
| Expected MA-SD interaction outcome | 2/2 detected | 2/2 detected |
| Reset success | 2/2 | 2/2 |
| Artifact/provenance/hash integrity | 2/2 | 2/2 |
| Accessibility/readiness observation failures | 0 | 0 |
| Blank-screen boot retries | 15 across episodes | 14 across episodes |
| Worker startup stagger | n/a | 15 s |

Each episode created one task Guest and one reset Guest. The two parallel jobs passed accessibility readiness before task setup, their actor routing remained attributable, and both reproduced `shared_focus_conflict_detected`. The retry count above refers to normal blank-screen polling while the desktop booted; all eight task/reset Guest accessibility readiness probes succeeded. No transient accessibility or post-readiness observation failure occurred in this four-episode regression.

Measured batch time fell by 357.450 seconds (50.36%) in this sample, a 2.014× sequential-to-parallel ratio. Descriptive throughput was 10.14 episodes/hour sequential and 20.43 episodes/hour at two workers. The sequential and parallel modes ran in a fixed order, and this is only two repeats per mode; do not treat the ratio as a stable capacity estimate.

Host measurements during this pilot:

| Snapshot | Load average (1/5/15 min) | Available memory |
|---|---:|---:|
| Start | 0.36 / 1.22 / 8.44 | about 213 GiB |
| Between modes | 2.12 / 2.05 / 5.08 | about 213 GiB |
| End | 5.03 / 3.78 / 4.87 | about 213 GiB |
| Parallel mode | 72 samples, one every 5 s | worker start/end snapshots also recorded |

Swap remained almost entirely occupied at start and end. This may affect longer or higher-concurrency runs; no attempt was made to change host swap or other system settings.

## Resource and artifact audit

All four episodes passed report contract and provenance verification; referenced artifact SHA-256 hashes matched. Eight containers (four task Guests and four reset Guests) have create/destroy pairs in their per-episode ledgers and matching project/run/owner labels. After the pilot there were no active containers. No existing artifact was deleted and no broad Docker cleanup was run. Pilot artifacts and QCOW2 overlays remain preserved on `/mnt/raid1/mjh`.

## Conclusion and next step

The new readiness gate and fail-closed observation retry passed this bounded Track A regression: both parallel episodes retained attributable focus events, expected interaction outcomes, resets, and artifacts. Two workers are suitable for a **controlled prototype** on this task, with a 15-second startup stagger and the current Guest-slot limit. This does not establish reliability across task families, high host load, or more than two workers.

Keep the default ceiling at two workers/four simultaneous Guest slots. Before using parallel throughput for formal benchmark results, repeat the stability check across another clean run and require zero service-attribution failures. Keep Runner V1 as a thin, config-driven dispatcher to the existing task-family runner; do not refactor the evaluator or actor schedule.

## Coordinator real-Guest integration smoke

The config-driven Runner V1 coordinator was exercised end-to-end after this regression, using one MA-SD episode of the same task and a fresh experiment root. The first attempt (`track-a-v1-smoke`) failed in reset verification with `NameError: name 'requests' is not defined`; the exact episode error, screenshots, and ownership ledger are preserved. The current-run Guest had matching project/run/owner labels and a destroy record. No task/evaluator change was made. `requests` was imported in the episode runner and the test was repeated under a new experiment ID.

The retry command was:

```bash
python scripts/run_codesk_experiment.py configs/track_a_smoke_v1_retry.json
```

`track-a-v1-smoke-retry-01` completed in 351.915 seconds (episode latency 348.280 seconds). The expected `shared_focus_conflict_detected` outcome passed 1/1; clean reset passed 1/1; report contract, provenance, ownership lifecycle, and all referenced artifact hashes passed 1/1; readiness/accessibility and observation transient failure counters were zero. Seven normal blank-screen readiness retries occurred across the two Guest startups; they were not counted as service failures. The full report, event trace, screenshots, two Guest overlay images, provenance, and resource ledger are retained under `/mnt/raid1/mjh/CoDesk-V1-artifacts/experiments/track-a-v1-smoke-retry-01/`.

This smoke verifies the current Track A coordinator-to-runner integration path only. It is one successful episode, not evidence of general reliability. The initial failure is kept in `/mnt/raid1/mjh/CoDesk-V1-artifacts/experiments/track-a-v1-smoke/` and has not been rewritten or deleted.
