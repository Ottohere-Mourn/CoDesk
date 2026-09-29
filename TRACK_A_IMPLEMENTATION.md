# CoDesk Track A Implementation

## Scope

This implements the V1 **GUI Control Contention** core track as a new task instance, `CODESK-TA-GUI-FOCUS-001` version `1.0.0`. It uses two independently goal-directed scripted GUI actors on the pinned OSWorld V2.1 Ubuntu Guest. The Document actor must write exactly `Approved\n` to its terminal stream; the Chat actor must write exactly `Review note\n` to a separate terminal stream. Each goal is independently solvable. In MA-SD, Chat legitimately takes focus after Document has observed its window, then Document resumes from that earlier observation without silently refocusing.

No model is used. No existing task definition, evaluator, or result was edited. The new evaluator is `TrackAFocusEvaluatorV1`; it reads Guest files only after scheduled actors finish. Hidden expected values and the private Guest reader are not passed to either actor.

## Conditions

| Condition | Desktop topology | Schedule | Purpose |
|---|---|---|---|
| Solo | One clean Guest per active actor; the other actor is inactive | Document observe → Document type, or Chat click/type | Validate each independent goal |
| MA-ID | One clean Guest per actor | Document observe → Chat goal → Document goal | Preserve actor schedule while isolating desktop focus and input devices |
| MA-SD | One Guest shared by both actors | Document observe → Chat goal → Document resumes | Trigger focus/input routing contention without forcing an invalid action |

The Track A fixture has no persistent shared backend. MA-ID therefore isolates the desktop-session dimension and runs both independent goals on separate clean Guests. It is not a control for a shared application backend; that belongs to Track C.

The two visible application fixtures are titled Guest terminal windows (`Document` and `Chat`); their stdin streams provide exact final state for the oracle. This keeps focus and keyboard routing deterministic and verifiable. It is a real GUI interaction in a real QEMU Guest, but this implementation does not claim Writer, Calc, or production chat-app coverage.

## Task and evaluator

The machine-readable task contract is [`tasks/codesk_track_a_v1.json`](tasks/codesk_track_a_v1.json). The actors use the existing `ActorContext` and `OSWorldSharedEpisode` interfaces. The runner uses the pinned OSWorld V2.1 `DesktopEnv` with the existing QEMU runtime and Guest image.

After the actor schedule ends, the hidden evaluator records:

- exact per-actor goal success;
- final contents of the Document and Chat terminal streams for each desktop binding;
- focus transitions from the OSWorld accessibility tree;
- the focused window at each keyboard action;
- cross-window keyboard routing and final non-goal-window contamination.

In MA-SD, an expected scenario reproduction requires the Document actor's keyboard action to be routed to Chat and the joint final-state evaluator to reject the contaminated state. This expected negative task outcome counts as a successful validation run only when the contamination is trace-supported and reset/resource checks pass.

## Reproduction

From the project root:

```bash
scripts/run_track_a_v1.sh --run-id tracka-v1-full-YYYYMMDDTHHMMSSZ
```

The default run requests five repeats per condition and five Solo repeats per actor (20 logical episodes). A single condition may be run with `--only solo|solo_chat|ma_id|ma_sd`; `solo_chat` selects the Chat actor's Solo baseline without duplicating Document Solo episodes. `--start-repeat N --limit-episodes M` selects a repeat slice for retry without replacing prior artifacts. Use a fresh run ID each time. Do not delete prior run artifacts.

The completed validation was assembled from immutable run slices because a full invocation was interrupted during Solo. Counted artifact runs are listed in [`TRACK_A_RESULTS.md`](TRACK_A_RESULTS.md). MA-SD repeat 5 was rerun with:

```bash
scripts/run_track_a_v1.sh \
  --run-id tracka-ma-sd-repeat5-retry-20260928T141000Z \
  --only ma_sd --start-repeat 5 --limit-episodes 1
```

The initial repeat-5 attempt had a real focus conflict but failed clean-reset readiness; it is preserved and excluded from the five valid MA-SD episodes. The retry used a new Guest, passed reset verification, and has its own provenance and ownership ledger. A prior evaluator pilot with a harness error and interrupted attempts are retained but excluded.

Prerequisites are the project-pinned OSWorld V2.1 checkout at `../_deps/OSWorld-V2-osworld-v2.1`, its pinned Guest image and local QEMU runtime image. Large artifacts are written to `/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a/<run-id>` by default.

Each logical episode records `report.json`, `events.jsonl`, per-observation Guest screenshots, reset screenshots, provenance hashes, a resource ownership marker, and `resource-events.jsonl`. The reset check verifies that the OSWorld reset created a different Guest container and removed both task files. The resource ledger is checked for matching project ownership labels and a destroy record for every Guest container created in the episode. QEMU overlay files are retained with their episode; the runner does not prune images, containers, volumes, or artifacts outside its own ownership ledger.

For MA-SD a task-validation pass means a trace-supported keyboard-routing conflict occurred and the hidden-state evaluator rejected the contaminated final state. It is not a joint-goal success. Solo and MA-ID validation passes require exact goals and uncontaminated final state. No language model or mock environment is used.

## Files added

- `tasks/codesk_track_a_v1.json` — task specification and conditions.
- `swcub/tasks/track_a.py` — two scripted actors and the new hidden-state evaluator.
- `scripts/run_track_a_v1.py` — pinned OSWorld orchestration, lifecycle checks and provenance.
- `scripts/run_track_a_v1.sh` — project-local launcher.
- `TRACK_A_RESULTS.md` — run counts, observed outcomes and artifact location.
