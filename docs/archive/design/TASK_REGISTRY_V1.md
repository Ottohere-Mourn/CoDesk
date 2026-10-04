# CoDesk Task Registry V1

## Canonical catalog

- `tasks/codesk_task_registry_v1.json` has four retained tasks plus a separate `deferred_variants` list. Deferred candidates are not registered tasks, do not appear in the experiment config, and do not count toward benchmark size.
- `configs/task_suite_v1_offline_review.json` selects the retained tasks for offline review and explicitly disables Guest/model launch.
- `swcub/task_registry_v1.py` validates task contracts and condition backend bindings. It provides pure seed-copy, exact reset, exact oracle, interaction exposure/failure/recovery outcome, and event metrics helpers. It does not start an environment.
- `tests/test_task_registry_v1.py` validates schema and metric separation using local JSON and synthetic events.

Run the offline validation from the repository root:

```bash
python -m swcub.task_registry_v1 tasks/codesk_task_registry_v1.json \
  --config configs/task_suite_v1_offline_review.json
pytest -q tests/test_task_registry_v1.py
```

This is a data-contract check only. `scripts/run_codesk_experiment.py` still maps only its existing runner families; the review config cannot launch it.

## Evidence status

| Status | Meaning | Entries |
|---|---|---|
| `scripted_anchor` | Existing Writer/Calc app task with prior scripted Solo/MA-ID/MA-SD results in project history; not rerun in this phase. The old MA-ID used separate Guest/workspaces, so these results do not isolate the desktop-sharing effect. | `CODESK-TA-OFFICE-001` |
| `registered_anchor` | Existing GUI+CLI stale-merge protocol/evaluator reference; not rerun in this phase | `CODESK-TD-STALE-MERGE-001` |
| `design_only` | Spec only; no task-specific setup, Guest episode, or real app validation | `CODESK-TB-CLIPBOARD-001`, `CODESK-TC-MODAL-001` |

The previous Focus 002, Clipboard 002, Window 002, and Append 002 entries are not active tasks. Their deduplication decisions are recorded under `deferred_variants` and in `TASK_SUITE_V1.md`.

## Backend-control invariant

Every `conditions.{solo,ma_id,ma_sd}` entry must state `backend_binding`. For MA-ID and MA-SD, the registry validator requires identical bindings. This prevents the previous GUI+CLI contrast from changing both desktop and backend topology.

For desktop-only tasks, a common workspace/backend with non-overlapping output artifacts is preferred; the intended treatment is separate input/clipboard sessions versus one shared session. For backend-consistency tasks, MA-ID and MA-SD must connect to the same authoritative backend instance. If this cannot be provisioned, use a documented factorial study with desktop topology × backend topology and compare desktop levels only at a fixed backend level. Do not report the diagonal private-backend MA-ID versus shared-backend MA-SD as a desktop effect.

Solo controls start from clean clones of the same seed; they establish independent solvability, not a different task version. Task goals, budgets, ordering, evaluator, and app seed must remain fixed across conditions. The revised same-backend comparison for the existing Writer/Calc task has not been implemented or run; it does not rewrite or invalidate the historical episode outcomes, but it must precede a causal desktop-sharing claim.

## Outcome API

`summarize_episode_outcomes(evaluator, events)` returns three separate blocks:

- `exposure`: number of unique logged opportunities and opportunities with at least one `interference_exposure`, by `source` (`natural` or `scheduled_stress`), plus raw exposure-event counts. A scheduled opportunity without a measured resource change is not an exposure. Missing IDs and unsupported source labels are surfaced separately.
- `task_outcome`: per-actor success, actor failure count, and joint success/failure from the programmatic evaluator, independent of exposure.
- `recovery`: explicit conflict count, recovery-action count, and operational recovery success when a post-conflict recovery action is followed by exact joint success. No inference about internal model awareness.

Event producers should include unique opportunity IDs and source labels. A stress schedule is analyzed separately from naturally occurring exposure. Report primary task failure on all valid assigned episodes; conditional failure among actually exposed episodes is only a secondary, explicitly denominated statistic.

`interaction_metrics` additionally computes action counts, focus transitions, invalid actions, and revision-backed conflict candidates. A causal interference label still requires event and final-state evidence; missing instrumentation means unattributed, not “no conflict.”

## Clipboard 001 evaluator privacy and capability boundary

The registered clipboard design requires a private Guest-side observer for X selection owner/timestamp and payload digest/MIME targets, plus action-level active-window and focused-target evidence. Current code has active-window/action provenance but no clipboard observer. The generic evaluator helper must receive state through a private callback; clipboard metadata and goal oracle must not be placed in ActorContext or shown to models.

Logical payload ownership is attribution by a uniquely bracketed actor copy/cut action, not the X11 owner XID. If that linkage is ambiguous, leave owner actor unknown. The final saved Writer/Calc state remains the success oracle. The observer must pass observer-on/off scripted controls to show its reads do not alter clipboard state or timing before any task can be promoted.

## Adding or changing tasks

1. Select a distinct shared resource and define two actor-local goals with an exact jointly satisfiable end state.
2. Declare identical MA-ID/MA-SD backend bindings and explicitly identify the desktop resource that changes.
3. Define natural interaction, optional scheduled exposure opportunities, and causal evidence separately.
4. Define Solo controls, MA-ID, MA-SD, recovery positive control, exact evaluator, contamination checks, and reset oracle.
5. Run offline schema tests, then scripted app-level controls, then a limited real-Guest pilot. Change the evidence status only when artifacts and all failures are preserved.
