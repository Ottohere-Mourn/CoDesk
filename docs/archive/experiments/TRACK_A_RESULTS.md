# CoDesk Track A Results

## Validation outcome

**The scripted Track A suite passed its 20-episode validation quota on real OSWorld V2.1 QEMU Guests.** Each active goal passed in Solo and MA-ID. All five MA-SD trials reproduced the scheduled focus/input conflict, the hidden-state evaluator rejected the contaminated joint state, and reset verification passed.

| Condition | Validated episodes | Actor/joint goals | Expected mechanism | Reset |
|---|---:|---|---|---:|
| Solo — Document actor | 5 | 5/5 passed | No partner; exact Document state | 5/5 passed |
| Solo — Chat actor | 5 | 5/5 passed | No partner; exact Chat state | 5/5 passed |
| MA-ID | 5 | Both actors pass in all 5 | No shared desktop; separate Guests | 5/5 passed |
| MA-SD | 5 | Joint goals fail in all 5 by design | Focus conflict detected in all 5 | 5/5 passed |

For MA-SD, each episode recorded one focus transition from Document to Chat and two keyboard actions from the Document actor routed to Chat. The final state contained `Review note\nApproved\n` in Chat while Document remained empty. Both actor goal checks failed; `scenario_success=true` means the intended interference was reproduced and detected. It does not mean the actors jointly completed their goals.

The combined audit covered 400 event records, 185 saved screenshots, and 50 Guest container lifecycles. All 20 task reports passed their condition-specific scenario checks; all reset and resource-ledger checks passed. The aggregate validator found no missing artifacts or SHA-256 mismatches. The five MA-SD episodes contain five focus transitions and ten misrouted keyboard actions in total.

These are deterministic scripted-mechanism results, not model performance or statistical claims.

The windows are titled Guest terminal fixtures, not Writer/Calc or a production chat client; terminal input streams are used as the exact oracle state. This phase validates real focus and keyboard routing on the shared QEMU desktop. Follow-up Track A design should replace or complement these fixtures with realistic applications before claiming office-workflow coverage. MA-ID uses one Guest per actor and therefore isolates the shared-desktop dimension only; it is not a shared-backend control.

## Artifacts and provenance

All large artifacts are on RAID1. Every validated episode has a `report.json`, `events.jsonl`, `provenance.json`, resource ownership marker, ownership ledger, Guest screenshots, reset screenshot, and retained QEMU overlay files.

- Solo Document and initial pilot: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-v1-full-20260928T112000Z/`
- Solo Chat, five retries: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-chat-solo-retry-20260928T120500Z/`
- MA-ID: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-ma-id-20260928T123500Z/`
- MA-SD repeats 1–4 and first repeat-5 attempt: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-ma-sd-20260928T132000Z/`
- MA-SD repeat-5 reset-verified retry: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-ma-sd-repeat5-retry-20260928T141000Z/`
- Aggregated per-episode index and metrics: `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/tracka-v1-full-20260928T112000Z/track_a_aggregate.json`

The first MA-SD repeat-5 attempt reproduced the interaction but its fresh reset Guest timed out. It is retained as an environment-reset failure and excluded from the 20 validated episodes; a separate repeat-5 retry passed. Earlier pilot/setup attempts also exposed and preserved two harness issues: shell arguments accidentally passed to `cat`, then a readiness probe that treated transient file absence as an exception. Both were fixed before the counted runs. A user-interrupted Solo Chat attempt is preserved and excluded.

## Reproduction commands

```bash
# Full matrix (20 logical episodes; five Solo repeats per actor)
scripts/run_track_a_v1.sh --run-id <unique-run-id>

# Reproduce each completed slice
scripts/run_track_a_v1.sh --run-id <unique-id> --only solo
scripts/run_track_a_v1.sh --run-id <unique-id> --only solo_chat
scripts/run_track_a_v1.sh --run-id <unique-id> --only ma_id
scripts/run_track_a_v1.sh --run-id <unique-id> --only ma_sd

# Retry only repeat 5 without overwriting prior evidence
scripts/run_track_a_v1.sh --run-id <unique-id> --only ma_sd --start-repeat 5 --limit-episodes 1
```

The runner uses the existing pinned OSWorld V2.1 Guest/runtime, `OSWorldSharedEpisode`, scripted actors, and the new `TrackAFocusEvaluatorV1`. It does not use a model. The optional OSWorld proxy-config warning was printed during startup but did not prevent these episodes from running.
