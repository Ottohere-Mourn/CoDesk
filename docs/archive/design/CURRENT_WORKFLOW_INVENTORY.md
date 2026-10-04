# Current Workflow Inventory and Instance-Space Audit

Date: 2026-10-03  
Canonical repository: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`.  
Audited baseline: commit `d5510420ced39523761da0c85f0e4b342a5301d0`.  
Scope: read-only audit of the frozen five-family suite. No Guest, Docker, or model experiment was run; no instances were generated.

## Executive finding

The current suite has **10 named, implemented anchor workflows**: Focus 3, Clipboard 3, Application Context 2, Selection / Active Object 1, Undo / Redo History 1. These are not ten equally mature generators.

- **9 are structurally distinct workflow templates** under the operation-graph/object/oracle criteria used here.
- **A-02 is a boundary case**: it is a distinct browser workflow from A-01 (single tab, record selection and commit rather than tab switching), but its hidden state is “currently selected record,” which can also be described as Selection / Active Object. Count it as a workflow only if the family boundary is defined by the browser record-context transaction and record-level oracle, not by selection state alone. A strict mechanism-diversity count is therefore **9 firm + 1 conditional**, not an unqualified 10.
- **No current anchor has a reusable, semantically rich fixed-instance generator.** A-01 has a seed-taking manifest builder, but its seed changes the two goal strings while preserving the same routes, fields, actions, and evaluator. This is one template, not evidence of hundreds of distinct instances.
- **The current production-ready count is 0.** Existing Guest evidence validates fixed anchors. The previous Task Factory seed IDs are not fixed instances of these ten workflows.
- Recommendation: **ADD WORKFLOWS before batch generation**, keeping the five-family scope frozen. Add at most one cross-application Selection workflow and one cross-application Undo workflow; settle A-02's boundary during that design. Then make a semantic instance schema and begin with a small batch.

## Counting rules and evidence levels

A workflow is counted when its task structure changes materially: actor operation graph/goals, mechanism trigger path, target object/evaluator, or recovery action. Text/value/ID/filename/coordinates/layout-only substitutions remain instances or run configuration, not workflows.

- **GUEST SCRIPTED**: recorded real Guest task execution by scripted actors.
- **QWEN**: recorded real Qwen3VLAgent episode(s); small mechanism evidence, not a reliability estimate.
- **OFFLINE**: source, fixtures, evaluator, or unit tests checked without asserting Guest execution.
- **PARTIAL**: runner or actor contract exists but a required condition/evaluator path is incomplete.

Historical reports and artifacts are evidence; this audit did not rerun them.

## Inventory

| ID | Family | Apps / object | Actor A goal | Actor B goal | Shared treatment and operation graph | Solo / MA-ID / MA-SD | Scripted / Qwen evidence | Evaluator and parameterization | Status |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | Focus / Input Routing | Writer + Calc; document body and one cell | Save assigned Writer content | Save assigned Calc cell value | A enters direct text in one app, B edits another; foreground app can change before A's next input | All implemented historically | **QWEN**: Solo pass; MA-ID 2/2 joint pass; MA-SD 2/2 joint fail with Writer input while Calc foreground. **GUEST SCRIPTED** historical | Exact saved Writer/Calc state and non-target checks. Fixed anchor values/objects; no general manifest generator. | IMPLEMENTED |
| F-04 | Focus / Input Routing | Calc rectangle + Writer paragraph | Fill B2:C3 and preserve guards | Replace one Writer paragraph | A performs four cell visits; B edits Writer; focus can move between apps before A resumes | All implemented | **GUEST SCRIPTED** Solo A/B, MA-ID, MA-SD interference, refocus recovery. No Qwen for this workflow. | Full Calc matrix + Writer text/guard oracle. Fixed 2×2 range and fixed text; immutable fixture constants. | IMPLEMENTED |
| F-02 | Focus / Input Routing | Chromium form + Writer anchored comment | Add exact comment to selected anchor | Submit case/decision once | B commits a form transaction while A must reacquire Writer and insert an anchored comment | All implemented | **GUEST SCRIPTED** bounded Solo A/B, MA-ID, MA-SD wrong-target contamination, recovery; no Qwen. | Browser revision/payload + ODF annotation/body/anchor integrity. Constants in `browser_writer_workflows_v1.py`; anchor/layout schema still needed. | IMPLEMENTED |
| C-01 | Clipboard State | Writer + Calc; plain text | Copy Writer source into destination paragraph | Copy Calc A1 into A2 | B overwrites shared clipboard between A copy and A paste; recovery is recopy | Solo A/B, MA-ID, MA-SD and recovery implemented | **GUEST SCRIPTED** controls and observer. **QWEN** event-gated MA-ID 2/2; MA-SD overwrite exposure 2/2. Outcomes mixed with focus/grounding; no clipboard-only failure claim. | Exact saved ODF state + hidden clipboard owner/generation/digest and action sequence. Values are constants (evaluator accepts sources); no semantic generator. | IMPLEMENTED |
| C-03 | Clipboard State | Calc + Writer; rectangular range and paragraph | Copy 2×2 Calc range to target range | Duplicate Writer paragraph | B's text copy overwrites A's matrix payload; A resumes with range-paste semantics; recopy is recovery | All implemented | **GUEST SCRIPTED** Solo A/B, MA-ID, MA-SD overwrite and recopy recovery. No Qwen. | Full ODF matrix, guard cells, payload digest/target. Fixed source/destination range and table shape; not a generalized range generator. | IMPLEMENTED |
| C-02 | Clipboard State | Chromium + Writer; hyperlink object | Copy URL A and save labeled hyperlink with exact href | Copy/submit URL B once | B's clipboard transaction can replace A's URL before Writer hyperlink-dialog paste | All implemented | **GUEST SCRIPTED** bounded Solo A/B, MA-ID, MA-SD overwrite, recovery. No Qwen. | ODF link label/href separately, Browser submission/revision, guard integrity. URLs/label are constants; exact link-object oracle is implemented. | IMPLEMENTED |
| A-01 | Application Context | Chromium; two tabs/forms in one top-level window | Submit tab-A goal | Submit tab-B goal | B changes active tab/page inside the same browser window while A has an earlier page observation | All implemented | **GUEST SCRIPTED**. **QWEN** Solo A/B stable, MA-ID 2/2 joint pass, MA-SD 2/2 joint fail; both MA-SD runs had tab-a→tab-b exposure in one Chrome window and no autonomous recovery. | Per-tab exact payload/revision plus tab/window event evidence. Seed changes goal strings; routes, two-tab graph, objects and oracle structure stay fixed. | IMPLEMENTED |
| A-02 | Application Context (boundary with Selection) | Chromium; one tab/page, two records | Edit/commit record A | Edit/commit record B | B changes selected record inside an unchanged page; A can commit using stale record context | All implemented in task code | **GUEST SCRIPTED** Solo A/B, MA-ID, MA-SD wrong-record commit, recovery in `WORKFLOW_SUITE_V2.md`; no Qwen. | Per-record values/revisions and selected-record event stream, same window/tab/URL. Values, IDs, coordinates are constants. Mechanism overlaps Selection / Active Object unless scoped as record-context transaction. | IMPLEMENTED; BOUNDARY REVIEW |
| S-01 | Selection / Active Object | LibreOffice Calc; selected cell in same document/window | Set B2 to assigned value | Set C3 to assigned value | B changes active-cell selection; A resumes with an earlier cell target | Solo A/B, MA-ID, MA-SD and recovery implemented | **GUEST SCRIPTED**. **QWEN** Solo A/B 2/2, MA-ID 2/2; MA-SD actual selection exposure 3/3, one joint failure and two autonomous recoveries. | Exact full-grid ODF + hidden UNO selection/X11/clipboard observer. Current target cells and values are constants; no instance API. | IMPLEMENTED |
| U-01 | Undo / Redo History | LibreOffice Calc; one document undo stack | Make temporary B2 edit, then Undo to restore seed | Set C3 to assigned value | B commits after A; A's ordinary Undo removes B's latest history entry rather than only A's temporary edit | Solo A/B, MA-ID, MA-SD and scripted recovery implemented | **GUEST SCRIPTED**. **QWEN** Solo A/B 2/2, MA-ID 2/2; MA-SD valid history exposure/interference 2/2, joint fail 2/2, no autonomous recovery. | Exact final cell grid plus snapshots around Undo; fixed cells/action depth. No general history-graph generator. | IMPLEMENTED |

Evidence detail is in `WORKFLOW_SUITE_V1.md`, `WORKFLOW_IMPLEMENTATION_V1.md`, `QWEN_FAMILY_PILOT_REPORT.md`, and `FAMILY_EXPANSION_V1_REPORT.md`. Their raw run artifacts remain the primary source.

## Deduplication and effective count

| Relationship | Audit decision | Why |
|---|---|---|
| F-01 vs F-04 | Keep both | Single-cell direct edit vs four-cell rectangular traversal; different goal granularity, action count and full-matrix oracle. |
| F-01 vs F-02 | Keep both | Cross-app text/cell entry vs form transaction plus anchored Writer annotation; different app graph, object and recovery. |
| C-01 vs C-03 | Keep both | Scalar/plain-text paste vs rectangular matrix selection and range paste; different payload shape, operation path and oracle. |
| C-01 vs C-02 | Keep both | Plain text into a text target vs URL payload converted to a semantic ODF hyperlink through a link dialog; href/label oracle and recovery differ. |
| A-01 vs A-02 | Keep as two workflows, flag family boundary | Tab/page switch vs in-page record select/commit; different action graph and state oracle. A-02's state is also a selected active record, so independence from Selection is not cleanly demonstrated. |
| S-01 vs U-01 | Keep both | Active-cell pointer changes target of the next edit vs document history stack changes what Undo reverses; separate hidden state, action and oracle. |
| Historical F-03, C-05, Modal M-01, other matrix candidates | Exclude | Deferred/design-only or paused; no promotion evidence and not in the frozen ten-row inventory. |

**Counts:** 10 raw current named anchors; 0 merged/rejected rows among those ten; 9 firm workflow distinctions + A-02 conditional boundary; 9 firm mechanisms/workflows if strict cross-family independence is required. Historical generated task IDs and run IDs do not change these counts.

The committed `tasks/generated_v1/office_writer_calc/index.json` lists 8 IDs in one `office_writer_calc` family. These IDs are not the ten workflows above and do not demonstrate eight operation graphs. Earlier 250-seed dry-run references likewise represent repeated materializations of the same workflow unless manifests prove structural changes; they must not be counted as workflow templates or as the current suite's fixed instances.

## Generation-space audit

“Combination space” is the plausible count after enumerating meaningful semantic axes, not the Cartesian product of arbitrary strings. “Recommended” is a ceiling for reviewed fixed instances after generator validation, not a claim that they already exist. Diversity rates semantic variation, not mathematical combinations.

| Workflow | Fixed structure that preserves the mechanism | Candidate parameters and constraints | Plausible semantic space | Diversity | Recommended instances |
|---|---|---|---|---|---:|
| F-01 | Two independent direct-edit goals; one Writer target and one Calc cell; focus moves between apps | Document purpose/body; table schema, row/column labels, target address/value; A/B targets distinct; valid ODF; guards untouched; no no-op | Medium (20–50) | **WEAK–MEDIUM**: many values, little action-graph variation | 45 |
| F-04 | One rectangular Calc fill plus one Writer paragraph replacement; shared focus is treatment | Table schema, row/column labels, target block content; bounded rectangle; no overlap with guards; Writer target uniquely anchored; current four-visit graph fixed unless versioned | Medium (20–50) | **MEDIUM**: matrix dimensions/content can change semantics, but current actor is fixed to B2:C3 | 50 |
| F-02 | One Browser multi-field commit and one anchored Writer comment | Case type/decision pair; anchor text/paragraph; comment purpose/content; unique stable anchor; exactly one commit/revision; comment must not alter body/guard | Medium (20–50) | **MEDIUM**: review semantics vary, but transaction stays fixed and anchor oracle needs robustness | 45 |
| C-01 | Plain-text copy from one app, B overwrites clipboard, A later pastes into one designated text target | Payload category/length, source/destination object, surrounding guard; A/B payloads nonidentical; unique destination; same copy/paste and recopy semantics | Medium (20–50) | **WEAK–MEDIUM**: one paragraph + one Calc cell and fixed graph; strings alone are weak | 45 |
| C-03 | Copy rectangular Calc range, B copies text, A pastes range into nonoverlapping destination | Table schema, cell types/content, source/destination range positions and bounded shape; ranges disjoint, destination empty, guards surrounding ranges, shape-compatible paste | Large (50–100+) in principle | **MEDIUM**: structural dimensions/positions matter, but current code supports one fixed 2×2 graph | 55 |
| C-02 | Copy URL A, use Writer link dialog to bind exact label/href; B copies/submits URL B | URL domain/path semantics, visible label, Browser target form; A URL != B URL; href and label individually checked; no malformed/redirect URLs | Small–Medium (20–50) | **MEDIUM**: semantic object differs from C-01, but one link-dialog transaction limits diversity | 45 |
| A-01 | Two stable routes in one top-level Browser window; actors commit to own tab | Page/form semantics, distinct tab goals, field/value, tab order; one window and two identifiable tabs; separate oracle key per tab | Medium (20–50) | **MEDIUM**: current seed changes values only; more semantics need a fixture schema | 50 |
| A-02 | One Browser tab/URL with two records; select, edit, commit | Record type/labels, values, record ordering; A/B records distinct; one selected record at a time; revisions start at zero; retain one-page/no-tab-switch invariant | Small–Medium (20–50) | **WEAK–MEDIUM**: two fixed records and values; expanding record count risks changing graph/schedule | 35 |
| S-01 | Same Calc document/window; two distinct cells; B changes selection between A's selection and write | Sheet layout, target cell roles, values, guard geometry; targets distinct; same sheet/document/window; observer decodes targets | Small (<20) as implemented; Medium if schema expands | **WEAK**: B2/C3, one sheet/app and same type-in operation; value substitutions dominate | 25 |
| U-01 | One shared document history; B's commit becomes top entry before A's Undo | Operation class, history depth, target object, actor order; A Undo valid solo; B operation independently valid; in MA-SD B's action top undoable entry; exact final states | Small (<20) as implemented; Medium after operation-class design | **WEAK**: one Calc history order and one Undo action; one trigger path | 25 |

Current code-level parameterization is weaker than the candidate schemas above: F-04/C-03 use immutable fixture constants; C-01 setup is fixed; F-02/C-02 use fixed dataclass constants; A-01's seed affects goal strings only; A-02/S-01/U-01 are fixed. Therefore recommended counts are contingent on building and validating semantic instance schemas. Do not multiply present fixtures by these numbers yet.

## Coverage and additions

| Family | Current templates | Coverage judgement | Cross-application coverage | Smallest useful addition |
|---|---:|---|---|---|
| Focus / Input Routing | 3 | Best covered; reasonable to expand after schema work | Writer, Calc, Chromium | No immediate addition required |
| Clipboard State | 3 | Good anchor breadth, but semantic variation and instance generator remain weak | Writer, Calc, Chromium | No immediate addition required; prioritize payload-object schemas |
| Application Context | 2 (A-02 conditional) | Tab and record paths exist; record context collides with Selection boundary | Chromium only | Decide whether A-02 is context or selection before production; no extra browser-tab variant |
| Selection / Active Object | 1 | Thin: one Calc cell-selection anchor | Calc only | Add one cross-application object/range-selection workflow with distinct action and exact object oracle |
| Undo / Redo History | 1 | Thin: one Calc cell edit/Undo path | Calc only | Add one Writer document-operation history workflow with exact ODF oracle |

Keep five-family scope frozen. These are at most two workflows within existing families, not new families. A Writer history task must change undoable operation/object, not only coordinates or strings. A Selection addition must be separated from Focus and A-02 by instrumentation and oracle.

## Provisional instance quotas

Quotas assume A-02 is retained as distinct and proposed S-02/U-02 pass validation. These are planning numbers, not generated instances.

### Plan A — conservative, 570 total

| Family | Workflow | Diversity | Instances | Reason |
|---|---|---|---:|---|
| Focus | F-01 | Weak–Medium | 60 | Anchor/control coverage; cap string-driven variation |
| Focus | F-04 | Medium | 60 | More target/layout variation than F-01 |
| Focus | F-02 | Medium | 55 | Distinct review transaction and annotation oracle |
| Clipboard | C-01 | Weak–Medium | 45 | Keep payload-only variants limited |
| Clipboard | C-03 | Medium | 60 | Table structure gives more semantic variation |
| Clipboard | C-02 | Medium | 50 | Semantic link object; moderate scenario set |
| Application Context | A-01 | Medium | 55 | Two-tab task families; cap same-form variations |
| Application Context | A-02 | Weak–Medium | 45 | Smaller cap; conditional on boundary decision |
| Selection | S-01 | Weak | 35 | Anchor coverage until another operation graph exists |
| Selection | S-02 proposed | Medium | 35 | Conditional on distinct object-selection graph/oracle |
| Undo / Redo | U-01 | Weak | 35 | Anchor coverage only |
| Undo / Redo | U-02 proposed | Medium | 35 | Conditional on distinct Writer history semantics |
| **Total** | **12 workflow rows** |  | **570** | Small additions before medium-scale production |

Family totals: Focus 175 (31%); Clipboard 155 (27%); Application Context 100 (18%); Selection 70 (12%); Undo/Redo 70 (12%). Better-covered families get more; single-anchor families are not inflated until they gain another operation graph.

### Plan B — target scale, 675 total

| Family | Workflow | Diversity | Instances | Reason |
|---|---|---|---:|---|
| Focus | F-01 | Weak–Medium | 70 | Keep below 11% of total |
| Focus | F-04 | Medium | 65 | Broader target-object/layout space |
| Focus | F-02 | Medium | 55 | Avoid multiplying one annotation transaction |
| Clipboard | C-01 | Weak–Medium | 55 | Moderate payload/destination classes |
| Clipboard | C-03 | Medium | 65 | More shapes after schema generalization |
| Clipboard | C-02 | Medium | 55 | Hyperlink semantics, not just URL substitutions |
| Application Context | A-01 | Medium | 60 | Page/form semantics with stable two-tab topology |
| Application Context | A-02 | Weak–Medium | 50 | Conditional on family-boundary decision |
| Selection | S-01 | Weak | 45 | Modest until cross-app workflow exists |
| Selection | S-02 proposed | Medium | 55 | Conditional on a new object/action schema |
| Undo / Redo | U-01 | Weak | 45 | Modest until new history workflow exists |
| Undo / Redo | U-02 proposed | Medium | 55 | Conditional on distinct Writer undo semantics |
| **Total** | **12 workflow rows** |  | **675** | No workflow exceeds 10.4% of suite |

Family totals: Focus 190 (28%); Clipboard 175 (26%); Application Context 110 (16%); Selection 100 (15%); Undo/Redo 100 (15%). If either proposed workflow fails, do not redistribute its quota mechanically; lower the total or design a distinct replacement within that family.

## Production gate

**Current gate: NEEDS_NEW_WORKFLOW + NEEDS_SMALL_DESIGN.**

- Existing anchors: 10 implemented workflow contracts; 9 strong distinctions plus A-02 conditional.
- Reusable instance generators: 0 ready for batch production.
- Fixed instances generated under the current plan: 0.
- Before a pilot batch:
  1. Decide A-02's family boundary and scope it as browser record-context, or revise category accounting without changing historical evidence.
  2. Design S-02 and U-02; reject either if it differs only by values/coordinates.
  3. For each retained workflow, implement typed semantic parameters, constraints, exact initial/final oracle, deterministic manifest and hash regeneration.
  4. Generate three hand-reviewed candidates per template; test regeneration, hashes, oracle positive/negative controls and one scripted Solo per actor.
  5. Keep family/template/instance/run counts separate.

**Recommendation: ADD WORKFLOWS (at most S-02 and U-02), then BEGIN SMALL-BATCH GENERATION.** Do not start the 600–700 batch from today's fixed anchors. If S-02/U-02 cannot be made distinct quickly, freeze at nine firm workflows plus an explicit A-02 decision and lower the target rather than inflate weak families.

## Sources checked

- Scope and prior plan: `FAMILY_TAXONOMY_V1.md`, `WORKFLOW_SUITE_V1.md`, `TASK_INSTANCE_GENERATION_PLAN.md`.
- Implementation/evaluator: `swcub/tasks/workflows_v1.py`, `browser_writer_workflows_v1.py`, `clipboard_v1.py`, `browser_context_v1.py`, `browser_record_context_v1.py`; `scripts/run_writer_calc_v1.py`, `run_clipboard_v1_round1.py`, `run_browser_writer_workflows_v1.py`, `probe_selection_active_object_v1.py`, `probe_undo_history_v1.py`.
- Offline tests: `tests/test_workflows_v1.py`, `test_browser_writer_workflows_v1.py`, `test_browser_context_workflow_v1.py`, `test_browser_record_context_v1.py`, `test_clipboard_observer.py`.
- Execution evidence: `WORKFLOW_IMPLEMENTATION_V1.md`, `QWEN_FAMILY_PILOT_REPORT.md`, `FAMILY_EXPANSION_V1_REPORT.md` and their linked run artifacts.
- Working-tree status was checked before edits: only pre-existing untracked `artifacts/` was present. It was not modified or staged.
