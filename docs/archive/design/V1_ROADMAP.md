# CoDesk V1 Benchmark Roadmap

## Goal and guardrails

V1 should establish a compact, reproducible benchmark of independent Computer-Use actors sharing a non-exclusive desktop. The goal is mechanism coverage and defensible evaluation, not maximum task count. Keep existing V2.0.0 task definitions and evaluator rules frozen; add future work under new task and suite versions. Preserve existing artifacts and label model smoke results as diagnostic until the required experiments are complete.

## Core tracks

| Track | Question | Mechanisms | Minimum evidence before inclusion |
|---|---|---|---|
| GUI + GUI | Can two independent GUI agents complete separate goals through the same desktop session? | Focus/input ownership, observation invalidation, application/object context, clipboard/selection ownership | Solo success for both; same desktop identity; joint feasibility; reproducible interaction; programmatic checks for both goals, contamination and recovery. |
| GUI + CLI | What happens when the GUI and command-line actor access the same live application data? | Stale observations, conflicting updates, synchronization/durability | Same Guest/backend proven; GUI and CLI solo controls; exact authoritative-state evaluator; distinct stale-read and write-conflict signatures. |
| GUI + Human Replay | How does an independent human task or interruption affect an agent sharing its desktop? | Focus handoff, interruption/preemption, safe resumption | Human trajectory has its own goal; replay timing is deterministic; score both goals and preservation of human changes. |

Shared-file conflict remains a useful supporting condition. It should not stand in for GUI-specific interaction evidence.

## Future extensions

- Clipboard and selection ownership between actions.
- Application-object context (document, tab, record or file-picker target) distinct from OS window focus.
- Observation invalidation while focus remains stable.
- Human interruption followed by safe agent resumption.
- Asynchronous save, export and durability boundaries with explicit completion barriers.
- Optional broader application coverage only after each new mechanism has a distinct task and evaluator predicate.

These are candidate extensions, not completed tracks. Avoid adding a category if its failure is already explained by focus routing or stale whole-record overwrite without a new measurable predicate.

## Required experiments

For each task and each actor roster:

1. **Solo controls:** Run every actor independently against the same task version and initial fixture. Establish that each goal is achievable.
2. **Joint-feasibility control:** Demonstrate a valid schedule in which all actor goals and shared integrity constraints can pass together.
3. **Sequential condition:** Run actors one after another on the same environment state where task semantics require it, establishing an order/control comparison.
4. **Naive Shared condition:** Reproduce a deterministic opportunity for interaction while allowing actors to observe and recover naturally. Do not force invalid actions.
5. **Recovery-aware condition:** Apply one declared intervention and log it separately from actor actions.
6. **Negative control and reset:** Confirm the evaluator detects the intended failure signature, and verify a clean reset into a fresh initial state.
7. **Mechanism diagnosis:** Preserve step-level actions, screenshots/observations, focus and object context, state transitions, evaluator fields, recovery steps and reset proof. Classify actor capability, grounding, interaction conflict, scheduler and environment causes separately.
8. **Small repeated comparison:** Repeat only after deterministic scripted validation and actor solo gates. Report counts and uncertainty descriptively; do not turn a small smoke into a statistical claim.

## Proposed order

1. Freeze current prototype protocols and evidence; run no new model matrix as part of this renaming milestone.
2. Add one scripted GUI+GUI clipboard-ownership pilot with solo, joint, interference, recovery and reset checks.
3. Add one scripted application/object-context pilot if it isolates an outcome not explained by focus routing.
4. Validate one GUI+CLI observation-freshness task that separates stale choice from lost-write consistency.
5. Add a GUI+Human interruption/resumption pilot with independently valid human and agent goals.
6. Review category coverage and event-schema needs before limited model comparisons on the frozen task set.

## V1 release gate

Do not label a task V1-ready until its spec is versioned, each actor passes solo, joint completion is shown, the trigger is reproducible, the evaluator is hidden and deterministic, intended negative controls are detected, recovery is measurable, reset is verified, and provenance ties all artifacts to the exact code/task/environment versions. Do not claim benchmark-level conclusions until model comparisons cover the core tracks with adequate repeats and preserved failure evidence.
