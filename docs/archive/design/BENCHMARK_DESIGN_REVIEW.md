# CoDesk Benchmark Design Review

Date: 2026-10-01  
Status: design review only. No Guest/model run or task implementation was performed for this review.

## 1. Research question and boundary

CoDesk studies how independently goal-directed computer-use actors affect one another when sharing the same live desktop control and application context. Both goals are scored; exposure, observed interference, outcome, and recovery are separate measures.

The literature sets clear boundaries: ParaGUIBench runs parallel GUI workers on separate desktops with shared-directory exchange; OSWorld-Noisy already covers recoverable disturbances including dialogs, popups and window changes; DeskCraft covers human-agent clarification and interruption turns. CoDesk should claim shared live GUI state with two independently scored goals, not generic parallel GUI work, popup robustness, or human interruption. See MECHANISM_EXPANSION_RESEARCH.md for sources and evidence boundaries.

MA-ID and MA-SD hold goals, task semantics, seeded state, model/prompt, budget, schedule, evaluator, and recovery opportunities constant; desktop isolation is the treatment. If persistent cross-actor file visibility is unnecessary, equivalent local fixtures are valid in both. If necessary, backend topology must be matched. Shared filesystem engineering is not the core definition.

## 2. Current families

| Family | Decision | Evidence limit | Scope |
|---|---|---|---|
| Focus/input routing | KEEP, core anchor | Qwen Writer+Calc Solo and two MA-ID pass; two MA-SD joint failures with Writer actions while Calc foreground. Exploratory n only. | Core; new templates need distinct operation/oracle. |
| Clipboard ownership | KEEP candidate | Scripted Guest Solo, MA-ID, MA-SD overwrite, observer, recovery; no Qwen result. One old logical-owner attribution remains unknown. | Extension candidate; genuine-agent validation remains future work. |
| Window/modal competition | Optional, feasibility only | Native Writer Save dialog observed; no paired task or full Solo/MA-ID/MA-SD. OSWorld-Noisy already includes dialogs as disturbances. | Keep only if independent transaction ownership adds evidence beyond focus routing. |
| Application-internal context | Optional, feasibility only | Scripted Browser page switch changed active page with constant top-level X11 window; stale action entered Page B. No full task controls/model trial. | Keep only if context changes while OS focus/window stay fixed; else merge with Focus. |
| Shared document transaction history | New exploratory candidate, unvalidated | Undo/redo contention is a research inference; no CoDesk task or GUI benchmark evidence in reviewed set. | Future candidate: H-01 undo ownership first; H-02 only if a distinct oracle exists. |

## 3. Literature-inspired candidates and exclusions

The one plausible new mechanism is Writer document undo/redo history: A and B make disjoint edits to the same document, then B's legitimate commit changes what A's subsequent undo would affect. It is distinct from Focus only if logs prove the correct window/target received the action and final ODF state identifies the affected transaction. It is distinct from Clipboard because no payload ownership is involved. This remains a hypothesis, not established novelty.

Account/project/session binding should remain a subcase of Application Context until a deterministic global-scope oracle proves an independent hidden variable. Do not add popup/noise, ordinary focus shifts, shared-directory conflicts, or interruption messages as new families: these overlap OSWorld-Noisy, Focus, CLI/shared-state work, or DeskCraft. GUI+Human is meaningful only when the human has an independently scored GUI goal in the same live session.

The research report contains detailed papers, artifact paths, and direct-evidence versus inference labels. WORKFLOW_MATRIX_V2.md contains task proposals and merge gates.

## 4. Workflow inventory and evidence

WORKFLOW_MATRIX_V2.md reports 18 provisional design candidates across five candidate families. A template changes the operation graph, target/resource semantics, hidden-state transition, or oracle; changing only text, seed, ID, layout, or coordinates is an instance/run variation.

Evidence counts:

- 1 model-validated workflow: F-01 Writer/Calc Focus anchor.
- 1 scripted end-to-end workflow: C-01 Clipboard with Solo, MA-ID, MA-SD, observer and recovery; not model evidence.
- 2 mechanism feasibility probes only: native modal dialog and same-window Browser context switch; neither is a registered task with full condition controls.
- 0 new workflows implemented or run in this design round.

Thus 18 is a design inventory, not a validated suite. Eight to twelve accepted templates is a planning ceiling after deduplication, not a quota. Do not scale toward 200-300 instances until templates pass Solo, joint feasibility, negative control, reset, observer, provenance, and matched MA-ID/MA-SD checks.

## 5. Recommended scope

- Core: Focus/input routing.
- Extension candidate: Clipboard ownership/transfer, pending genuine-agent validation.
- Optional, feasibility-gated: Modal and Application Context. Merge either with Focus when the measured effect is ordinary input routing.
- Future exploratory candidate: undo/redo transaction history, H-01 first.
- Auxiliary: GUI+CLI persistent-state consistency is a separate comparison, not the shared desktop core.

## 6. Next stage

BEGIN TASK EXPANSION, limited to Focus and Clipboard. Choose at most four candidates first: F-01 plus two materially different Focus workflows, and C-01 plus one Clipboard workflow. Begin with offline setup/oracle review. Modal and Application Context should not block expansion; keep H-01 in a short feasibility backlog. Do not run large experiments or generate bulk instances.

Accept a template only after both Solo goals pass, joint feasibility is proven, task-relevant state is equivalent across conditions, the hidden-state oracle is programmatic, actors can observe/recover autonomously, and exposure is distinguished from interference/outcome. This review does not alter historical artifacts or result classifications.
