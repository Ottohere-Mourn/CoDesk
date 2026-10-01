# CoDesk Task Instance Generation Plan

Status: generation plan for the frozen eight-template inventory in `WORKFLOW_SUITE_V1.md`; fixed-instance generation has **not** started. The eight workflows have real Guest feasibility evidence, but F-01 is legacy/model evidence and the remaining controls are scripted. C-02/F-02 each completed one bounded episode for Solo A/B, MA-ID, naive MA-SD and explicit recovery; one provider misconfiguration attempt is invalid infrastructure and retained. This is not a reliability estimate. Current production count under this plan: **0 fixed instances generated**.

## Hierarchy

Family → workflow template → fixed task instance → run.

- **Family** names the hidden shared desktop state: focus/input routing, clipboard state, or application context.
- **Workflow template** freezes the operation graph, actor roles, task environment, schedule, reset and evaluator semantics.
- **Fixed instance** freezes semantic task content, initial application files/server state, both actor goals, exact final-state oracle and a manifest hash.
- **Run** records condition, actor/model configuration, schedule realization, Guest, inference endpoint, actions, observations, screenshots and provenance.

A seed is only a reproducibility input to materialization. It does not establish a distinct task or workflow.

## Target inventory and per-template variation rules

The proposed minimum is 25 fixed instances per validated template (8 × 25 = 200). An upper production tier is 36 per template (8 × 36 = 288); stop at 200 unless additional variation passes de-duplication and solo-feasibility review.

| Template | Instance fields that may vary while preserving its operation graph | Required invariants and oracle |
|---|---|---|
| F-01 Writer + Calc direct edits | document scenario/title/body, exact cell address/value and sentinel contents | one Writer body edit + one Calc cell edit; exact ODF text and full cell matrix |
| F-04 Calc rectangular selection + Writer edit | source/target block values, row/column labels, guard cells; bounded rectangle dimensions only if action graph remains selection→entry | same two target objects and operation order; full-sheet oracle detects spills and omissions |
| F-02 Browser review form + Writer comment | case ID, decision value, anchor phrase and comment body | two-field Browser commit + anchored Writer annotation; exact form revision, comment text/anchor and untouched paragraph |
| C-01 plain text transfer | source string, destination paragraph/cell, unrelated guard content | copy→interruption→paste; exact payload and destination plus non-target integrity |
| C-03 rectangular table transfer | cell values, bounded rectangular range, destination and guard locations | source selection, clipboard copy, rectangle paste; full ODF matrix and observer digest |
| C-02 semantic hyperlink transfer | source URL, visible label, independent B URL/form target | visible link label and saved href checked separately; Browser form and Writer guard remain exact |
| A-01 Browser tab context | route/form semantics and distinct goal values per tab | one top-level window; two stable tabs; exact per-tab submissions, revisions and tab event stream |
| A-02 in-page record context | record IDs/types and values within one page | same window/tab/URL; exact per-record state and revision plus selected-record event stream |

A variation is an **instance** when each actor performs the same sequence of GUI operations against the same kinds of objects and the same hidden state mechanism, while the exact content, target data, scale or schema is fixed differently. A new selection model, extra app switch, different transaction boundary, different clipboard payload semantics or different recovery operation changes the workflow and requires a new template review.

## Changes that do not create instances

The following are run configuration or duplicate content, not task instances by themselves:

- random seed, task/case ID, serial number, or text token substitution;
- window size, coordinates, monitor arrangement, app theme or startup delay;
- actor order, pause length, repeat number or screenshot naming;
- identical goal text moved to a different filename with no task-relevant object change.

A new browser record, document section or table region qualifies only when the manifest names a distinct target object and both the saved-state oracle and actor instructions refer to it.

## Instance manifest and deterministic generation

Each generated instance must store:

1. family_id, template_id, template version, generator version, task_id, fixed instance_id, and deterministic materialization seed.
2. Full A/B goals, application setup, operation graph identifier, initial files/server state, expected final state, non-target integrity constraints and reset assertions.
3. Condition contract for Solo, MA-ID and MA-SD; task-relevant backend fixture digest; hidden evaluator identifier and version.
4. SHA-256 for every initial file and the canonical manifest; a regeneration command and its source commit.
5. Evidence status for template controls; instance generation cannot upgrade a design-only template to validated.

Materialization must be pure and offline. The same template version, generator version, semantic parameters and seed must reproduce byte-identical files and manifest hash. The runner consumes the fixed manifest; it does not invent content at episode time.

## Proposed 200-instance split

For each of eight validated templates, produce 25 instances:

- 5 public development instances for task setup, evaluator and actor integration.
- 5 public calibration instances, disjoint from the development set.
- 15 held-out evaluation instances with fixed manifests and private oracle parameters.

This gives 40/40/120 = 200 fixed instances. If variation quality supports expansion, add 11 instances per template (25 → 36) for 88 additional held-out instances, reaching 288. Preserve a family-balanced split and keep all instances from a single semantic scenario in one split to reduce leakage.

Do not expose the private oracle values, state files or evaluator paths through ActorContext. Public instructions can state the goal value; only the hidden implementation state remains private.

## Acceptance gate before batch generation

For each template:

1. Freeze operation graph, task version and exact evaluator after Solo A/B, MA-ID, naive MA-SD, recovery and reset are scripted-validated in the pinned Guest.
2. Materialize 3 hand-reviewed semantic candidates. Verify regeneration and hashes; run positive and negative evaluator controls.
3. Compare normalized operation graphs and semantic object roles against existing templates. Reject content-only duplicates.
4. Run one Guest Solo per actor on each candidate. Setup/readiness failures are environment-invalid, never actor failures.
5. Only then create the remainder of the 25-instance set. Save all generated manifests and validation output; do not launch a model batch.
6. A template with fragile GUI geometry, ambiguous anchor extraction or unstable observer remains prototype-only and contributes zero to the validated-template count.

Current production count: **0 instances generated by this plan**. The previously discussed Task Factory seed batches are not evidence for 200 distinct tasks and are not included in this count.
