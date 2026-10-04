# CoDesk Phase 10: Two-worker Parallel Pilot

## Scope and protocol

This pilot compares the existing scripted Track A `ma_sd` episode under sequential execution and two independent worker processes. Both modes ran the same two repeat indices (1 and 2), with task version `1.0.0`, the existing evaluator, and the unchanged actor schedule `document_actor → chat_actor → document_actor`. No model was used. Each job had a unique run ID and artifact root; the workers created independent OSWorld V2.1 Guest containers. The coordinator did not alter the task, actor ordering, or evaluator.

Coordinator: [`scripts/run_track_a_parallel_pilot.py`](../../../scripts/run_track_a_parallel_pilot.py)

Reproduction command:

```bash
python scripts/run_track_a_parallel_pilot.py \
  --pilot-id tracka-p10-20260928-2315 \
  --condition ma_sd --episodes 2 --workers 2
```

A completed-run artifact recheck, which does not start Guests, is:

```bash
python scripts/run_track_a_parallel_pilot.py \
  --recheck-summary /mnt/raid1/mjh/CoDesk-V1-artifacts/parallel-pilot/tracka-p10-20260928-2315/pilot_summary.json
```

The full `pilot_summary.json`, worker logs, per-episode screenshots, events, reports, provenance, reset screenshots, overlays, and resource ledgers are under:

`/mnt/raid1/mjh/CoDesk-V1-artifacts/parallel-pilot/tracka-p10-20260928-2315/`

## Results

| Measure | Sequential (2 episodes) | Two workers (2 episodes) |
|---|---:|---:|
| Batch wall time | 700.261 s | 436.970 s |
| Throughput in this run | 10.28 episodes/hour | 16.48 episodes/hour |
| Wall-time reduction | — | 37.60% |
| Sequential / parallel speed ratio | — | 1.603× |
| Episode latency, each | 361.240 s; 332.233 s | 433.421 s; 333.201 s |
| Median episode latency | 346.736 s | 383.311 s |
| Guest readiness samples (task and reset Guests) | 141.558, 121.704, 122.163, 113.423 s | 118.622, 117.564, 125.428, 120.736 s |
| Median Guest readiness | 121.934 s | 119.680 s |
| Reset checks | 2/2 passed | 2/2 passed |
| Artifact integrity (metadata, provenance, SHA-256, required files) | 2/2 passed | 2/2 passed |
| Expected MA-SD focus-conflict outcome | 2/2 reproduced | 1/2 reproduced |

The batch wall time includes both episode processes and their reset lifecycle. Guest readiness is measured from the resource ledger's container creation timestamp to the corresponding `guest.desktop_ready` event; it includes both task and reset Guests. Episode latency uses the task report's start and finish timestamps. Artifact integrity is reported independently of whether the task outcome matched the expected scenario.

## Failure evidence

Parallel repeat 1 completed both scripted actors and passed reset, report/provenance checks, and every recorded artifact hash. Its task report did **not** validate the expected focus-conflict mechanism:

- OSWorld repeatedly returned accessibility-tree HTTP 500 errors in that worker's log.
- The final observation had no accessibility tree and no active-window title. The evaluator therefore could not attribute the keyboard destinations (`routed_window: null` for all four keyboard actions), and recorded no focus transitions or contamination events.
- The final hidden state contained `Review note\nApproved\n` in Chat and an empty Document. Both actor goals failed; the runner marked `expected_shared_focus_conflict_not_detected` and exited with status 1.

The evidence is consistent with an observation/window-attribution failure during this concurrent run. It does not establish whether the trigger was host scheduling, Guest/OSWorld service contention, or another transient environment issue. Parallel repeat 2 reproduced the expected conflict. Sequential repeats 1 and 2 both reproduced it.

## Resource and provenance audit

Each worker had a unique run ID, run-owner marker, artifact directory, owner token, and ledger. Across the four jobs, ledgers show 8 Guest containers created and all 8 destroyed (4 task Guests and 4 reset Guests). All container records had the project ownership label, and each per-episode report verified its lifecycle. `docker ps` showed no active containers after the pilot. Artifacts and overlays are retained under the RAID artifact root; nothing was pruned or removed.

The post-run recheck verifies the files referenced by each provenance SHA-256 manifest. All four episodes have complete and matching hashes, reports, screenshots, event logs, resource ledgers, and reset artifacts.

## Interpretation

This small run demonstrates that two worker processes can execute isolated Track A episodes against separate real Guests and reduce batch wall time: measured batch time fell by 263.291 seconds (37.60%). Guest readiness medians were similar in this sample. The slowest parallel episode took 433.421 seconds and coincided with HTTP 500 accessibility failures; therefore per-episode latency did not improve uniformly.

The pilot is **not sufficient to declare two-worker mode stable or recommend it as the default**. One of two parallel episodes failed to reproduce the expected, attributable interaction outcome, despite having complete artifacts and a successful reset. The 1.603× speed ratio is descriptive for this two-episode run only. It is not a benchmark performance claim or a statistically reliable estimate.

The host had 80 logical CPUs and roughly 211 GiB available memory. The one-minute load average was low at start (1.83), rose between modes (4.23), and was 2.61 at end; the start 5/15-minute averages were elevated (73.96/111.54), consistent with earlier host load. Swap was nearly fully occupied throughout. These conditions and the fixed sequential-then-parallel order are potential confounds.

## Pilot conclusion and next step

- **Prototype:** passed for dispatching two independent worker processes with unique run IDs and isolated artifacts.
- **Reset/provenance/artifact integrity:** passed for all four episodes; all eight Guests were ledgered and destroyed.
- **Throughput:** promising in this run (37.60% lower batch wall time), but based on `n=2` per mode.
- **Task reliability:** not yet acceptable as a default parallel setting (expected conflict reproduced in 1/2 parallel episodes, 2/2 sequential episodes).

Before increasing worker count or using parallel runs for benchmark results, run a bounded stability check with the same pinned task and evaluator, capture OSWorld service/observation health per worker, and require repeated task-outcome validity as well as artifact/reset validity. Keep worker count at two until that check passes.
