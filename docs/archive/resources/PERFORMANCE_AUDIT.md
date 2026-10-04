# CoDesk Track A Pipeline Performance Audit

## Scope and method

This is a read-only audit of the current Track A runner and the 20 counted, reset-verified real-Guest episodes. No task, evaluator, timing, or runner code was changed. Timings below were reconstructed from `report.json`, `events.jsonl`, `resource-events.jsonl`, the run matrix summaries, and the pinned OSWorld V2.1 `DesktopEnv` / Docker provider source.

`report.finished_utc` is assigned just before event/report serialization and provenance hashing. For episodes followed by another episode in the same run, the next episode's `started_utc` bounds the remaining report/hash/runner tail; this was typically 0.3–0.5 s. Phase times are therefore approximate. Event records are emitted after an operation completes, and there are no explicit evaluator-start, artifact-copy-start/end, or provider-reset-span events. Do not interpret these estimates as profiler-grade traces.

## Observed end-to-end timing

The table reports per-condition medians from the validated set. Guest startup is split into task Guest(s) and the clean Guest(s) created for reset verification. In MA-ID, two Guest instances are started and reset sequentially. Components are individual medians and will not add exactly to the episode median.

| Condition | Episode wall time p50 | Task Guest startup p50 | Application setup p50 | Actor execution p50 | Reset Guest startup p50 | Other / uninstrumented |
|---|---:|---:|---:|---:|---:|---|
| Solo — Document | 321 s (5.4 min) | 123 s (1 Guest) | 24 s | 22 s | 130 s (1 Guest) | 22 s |
| Solo — Chat | 318 s (5.3 min) | 120 s (1 Guest) | 24 s | 32 s | 122 s (1 Guest) | 20 s |
| MA-ID | 641 s (10.7 min) | 245 s (2 Guests) | 25 s | 52 s | 250 s (2 Guests) | 65 s |
| MA-SD | 346 s (5.8 min) | 124 s (1 Guest) | 25 s | 54 s | 123 s (1 Guest) | 23 s |

The five MA-SD wall times ranged from about 339 s to 914 s; the slowest successful episode was the repeat-5 retry. A previous reset attempt hit the provider's 300 s Guest-readiness timeout and was excluded from the valid set. The median is more representative of the normal episodes, but the tail delay is operationally significant.

## Cost by pipeline stage

### Guest initialization — primary bottleneck

The runner creates a clean task Guest and later a fresh clean-reset Guest for each desktop binding. Measured time from labeled container creation to the runner's nonblank-screen readiness event was typically 115–140 s per Guest. Thus Solo and MA-SD pay for two Guest boots per logical episode; MA-ID pays for four. Those boot intervals account for roughly 70–80% of the median wall time.

OSWorld V2.1's Docker provider also performs its own `/screenshot` readiness wait during `DesktopEnv.reset`; the Track A runner then applies a stricter nonblank-screen check, polling `/screenshot` every three seconds. The two checks enforce different predicates, but their cost and timeout budgets are not separately recorded. A failed Guest can spend up to the provider wait and then the runner wait if the HTTP endpoint responds while the desktop is still visually blank.

### Application startup

From the final task Guest's readiness event to the first actor observation is about 24–25 s. This includes launching two terminal fixtures, a fixed five-second delay, checking that both task streams exist, setting initial focus, and refreshing the observation. It is visible but small compared with Guest boot.

### Actor execution

The scripted GUI schedule takes about 22 s for Document Solo, 32 s for Chat Solo, and 52–54 s for either paired condition. Across 60 logged intervals from an actor observation or prior GUI action to the next GUI input, the median interval was about 10.7 s. Each call goes through OSWorld's GUI step and returns a fresh observation. The action count is part of the task trajectory, so collapsing actions or changing focus order would alter the experiment; neither is recommended as a protocol-preserving speed optimization.

### Evaluator and artifact saving

The hidden evaluator reads two short Guest files (four reads in MA-ID) and derives goal/focus/routing results. The runner copies task screenshots before reset, copies them again after actor execution, copies reset screenshots, writes the event/report files, and hashes the non-overlay artifacts into provenance. These stages lack dedicated timers. The combined interval from the final actor turn to task-Guest teardown was typically below one second; the report/provenance/runner tail was typically below half a second. They are not the current median bottleneck at this task scale.

The pre-actor and post-actor `copy_artifacts` calls write the same directory; later writes replace same-named screenshots. The first copy can retain setup evidence if an actor crashes, so removing it should be considered only after confirming exception-path artifact coverage. Provenance hashing excludes QEMU overlays, which avoids hashing the largest files.

### Reset

Reset verification is a full lifecycle, not just a file check. After actor completion the runner evaluates state, copies task artifacts, calls `DesktopEnv.reset(task_config=None)`, waits for the newly created Guest to become visually ready, checks task files are absent, saves reset screenshots, and closes the Guest. Median time from actor completion to clean-reset verification was about 137–145 s in Solo/MA-SD and 281 s in MA-ID. This closely tracks the extra one or two Guest boots, with provider teardown/recreation and verification making up the remainder.

## Main bottlenecks

1. **Cold QEMU Guest startup and reset:** two fresh Guests per Solo/MA-SD episode and four per MA-ID episode dominate runtime.
2. **MA-ID multiplicative lifecycle cost:** its two independent desktops are currently initialized and reset serially, approximately doubling the VM lifecycle component.
3. **Guest readiness tail latency:** the 300 s readiness timeout and second visual-readiness loop cause long outliers; a failed reset wastes most of a Guest cycle.
4. **GUI step latency:** roughly 10.7 s per scripted input operation is the next measurable task-time cost, but changing action count or action pauses risks changing the interaction condition.
5. **Artifacts, evaluator, and parent runner:** currently sub-second in normal episodes by indirect timing; preserve full evidence and provenance, and optimize only if a larger task suite makes these stages material.

The host was under substantial load during one timing snapshot (80 logical CPUs; load averages around 135/177/140; reported available memory around 209 GiB and 2 GiB swap fully used). This is a confound, not a controlled benchmark of machine capacity. The five-repeat timings are descriptive; they do not establish a stable saturation curve.

## Protocol-preserving optimization plan

No item below was implemented in this audit.

### P0 — Bound and unify readiness work

- Instrument provider reset, container creation, screenshot-HTTP-ready, nonblank-screen-ready, and reset verification as separate spans.
- Check whether the observation returned by `DesktopEnv.reset` can satisfy the runner's existing nonblank-screen predicate. If so, reuse that observation and avoid an immediate duplicate screenshot request; retain the same visible-screen condition and clean reset checks.
- Give provider readiness and visual readiness one documented total deadline, while preserving a sufficient boot budget. Record which predicate timed out. This avoids opaque stacked waits without relaxing what “ready” means.
- Run a small cold-start readiness calibration across clean resets before changing timeout handling; retain all failed-attempt evidence.

### P1 — Bounded episode-level worker processes

- Parallelize independent episodes, never actors that share an MA-SD desktop. Preserve the exact actor order, action granularity, seed, and evaluator within each episode.
- Use separate worker **processes**, each with unique run identity, resource ledger, overlay directory, and episode artifact path. The current runner mutates `os.environ` to assign ownership identity, so threading episodes inside one interpreter could race labels and ledgers.
- The pinned Docker provider uses a host-wide file lock while allocating ports and creating the container; that short startup section will serialize even with multiple workers. VM boot/readiness can still overlap after container creation, so measure throughput before adding more workers.
- Start with two concurrent episode workers for Solo/MA-SD, then compare throughput and p50/p95 Guest readiness against the serial baseline. Keep MA-ID at one worker until resource headroom is measured: one MA-ID episode maintains two active 4-vCPU / 4-GiB Guest VMs and resets them sequentially.
- Stop increasing concurrency if per-Guest readiness tail or reset failures rise. The sampled host load argues against assuming that more workers will always improve wall time.
- Let a parent process merge per-worker results in repeat order; avoid concurrent appends to one JSONL progress file unless writes are coordinated.

### P2 — Guest lifecycle management

- Keep the pinned OSWorld V2.1 base image immutable and continue using an isolated copy-on-write overlay per Guest. Measure base-image cache state and overlay storage latency before changing disk placement.
- Prototype a prewarmed pool of **pristine** Guests only if each episode still receives an isolated Guest/overlay and the existing reset oracle passes: new resource identity, task files absent, same release/image/display, and reset screenshot present. Count pool startup in total resource cost and report both cold end-to-end time and amortized throughput so warmup is not hidden.
- Do not reuse an episode's dirty Guest between trials. For MA-SD, both actors must continue sharing one live Guest for the full episode; for MA-ID, the two Guests remain isolated.
- Parallel Guest creation/reset inside one MA-ID worker is a later experiment. First verify Docker-provider port allocation, environment identity propagation, and ledger writes under parallel startup; otherwise keep the two desktop lifecycles sequential.

### P3 — Artifact and evaluator overhead

- Add timers around hidden-state reads, pure-Python scoring, both `copy_artifacts` calls, event/report writes, and provenance hashing. Current indirect evidence says these are low priority.
- Consider writing task screenshots once after actor execution and reset screenshots once after reset; retain exception-path captures and compare artifact hashes/counts before adopting.
- Keep the same artifacts and SHA-256 values. Avoid lossy image conversion or skipping evidence to improve a timing number.

### P4 — Runner scheduling and measurement

- Separate per-episode wall time from matrix throughput and report startup/warm-pool costs, worker count, Guest count, host load, and failures.
- Preserve deterministic repeat IDs and the Solo → MA-ID → MA-SD definitions, regardless of worker completion order.
- Before claiming speedup, compare serial and bounded-worker runs on the same pinned Guest image with identical task version, schedule, action pauses, evaluator, reset checks, and artifact policy. Report p50 and p95 latency, episodes/hour, timeout rate, and reset failure rate.

## Recommended order

1. Add phase spans and a readiness calibration; this changes observability, not task behavior.
2. Reuse a reset observation when it already passes the current readiness predicate, with unchanged failure checks.
3. Run a two-process independent-episode throughput trial under monitored host load.
4. Evaluate pristine prewarmed Guest overlays and MA-ID initialization parallelism only after ownership/port/ledger isolation is demonstrated.
5. Revisit screenshot/provenance writes only if new measurements show a meaningful fraction of wall time.

## Reproduction data

The episode set and aggregate results are listed in [`TRACK_A_RESULTS.md`](../experiments/TRACK_A_RESULTS.md). Source inspected for this audit: `scripts/run_track_a_v1.py`, `swcub/osworld_adapter.py`, `swcub/core.py`, `swcub/tasks/track_a.py`, and the pinned OSWorld V2.1 `desktop_env/desktop_env.py` and Docker provider. No pipeline or benchmark code was changed.
