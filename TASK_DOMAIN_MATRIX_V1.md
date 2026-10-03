# CoDesk Task-Domain Matrix V1

Date: 2026-10-03  
Canonical repo: A6000 /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk, branch v0.  
Status: matrix and scaling plan remain design material. A P1 prototype addendum records the five new workflow contracts and the one real Guest Solo A smoke; see `MATRIX_WORKFLOW_IMPLEMENTATION_V1.md`.

## 1. Task-domain axes

The matrix uses four domains with direct evidence in the pinned OSWorld V2.1 Guest setup or current CoDesk fixtures.

| Axis | Domain | Evidence in this project | Boundary |
|---|---|---|---|
| W | Writer / document editing | Writer files are opened, saved, parsed and evaluated in the office runner; F-01/F-02/F-04 and Qwen office solo evidence exist. | GUI document editing. |
| C | Calc / spreadsheet editing | Calc files and full cell grids are set up, saved, parsed and evaluated; F-01/F-04/C-03/S-01/U-01 evidence exists. | GUI spreadsheet editing. |
| B | Browser / web application | Chromium local forms, tabs, routes, records and submissions have Guest runners and private programmatic oracles; A-01 and F-02/C-02 evidence exists. | Browser page, tab, record and form state. |
| T | Desktop Terminal | OSWorld Guest has visible GNOME Terminal windows controlled by GUI PyAutoGUI in scripted probes; task state has exact checks. | Actor is a GUI agent operating the visible Terminal window. This is not a CLI actor or CLI adapter. Qwen workflow feasibility is unverified. |

**Excluded from V1 axes:** File Manager and Slides. The current project evidence does not establish deterministic readiness, reusable fixture/reset, task-specific evaluator, and stable Qwen GUI operation for either. File Manager would invite filesystem/object-lifecycle scope; Slides lacks a tested presentation oracle. This is a CoDesk evidence boundary, not a claim that upstream OSWorld cannot run them.

### Ordered-cell convention

Each cell is Actor A task domain × Actor B task domain. A is the stale-state consumer; B has an independent ordinary goal that may change family state. Same-app cells assume compatible shared app/session/document where required.

- VALID: natural independent goals can produce the mechanism.
- CONDITIONAL: requires a particular topology, instrumentation, or separation from another family.
- INVALID: the family state is not naturally shared by these domains.
- REDUNDANT: feasible but not materially different from a better-covered cell.

Status means mechanism feasibility, not prior evidence. A cell is not itself a task or instance.

## 2. Family matrices

### Focus / Input Routing

B's normal GUI turn activates a different foreground window/input target before A resumes. A same-domain cell needs distinct top-level windows; a tab/sheet/selection change alone belongs to another family.

| A \ B | W | C | B | T |
|---|---|---|---|---|
| W | CONDITIONAL — requires two Writer windows; a tab or selected text alone is another family. | VALID — B's Calc window becomes foreground before A continues Writer input. F-01. | VALID — Browser form work activates Chromium during A's Writer task. F-02. | VALID — Terminal becomes foreground during Writer work; goals can be separate. |
| C | VALID — Writer is foreground when A resumes Calc entry. F-04. | CONDITIONAL — requires separate Calc windows; sheet/cell switching alone is not OS focus. | VALID — Browser form interaction changes foreground before Calc input. | VALID — Terminal can take foreground before A resumes Calc. |
| B | VALID — Writer editing activates its window before Browser actor resumes. | VALID — Calc work activates its window before Browser actor resumes. | CONDITIONAL — requires separate Browser windows; tab switching in one window is Application Context. | VALID — Terminal interaction steals foreground from Browser. |
| T | VALID — Writer becomes foreground while A has an earlier Terminal target. | VALID — Calc becomes foreground before A's Terminal input. | VALID — Browser becomes foreground before A resumes Terminal. | CONDITIONAL — needs separate Terminal windows; same shell/window state can become context or selection contention. |

Counts: **12 VALID, 4 CONDITIONAL, 0 INVALID, 0 REDUNDANT.** Cross-app cells are broad; select workflows by operation and oracle diversity, not by filling every pair.

### Clipboard State

A copies a payload for its own destination; B's legitimate copy/cut changes clipboard generation before A pastes. Outcome must distinguish clipboard overwrite from wrong focus/target. A is classified by primary destination domain; a task may use another app as A's source.

| A \ B | W | C | B | T |
|---|---|---|---|---|
| W | VALID — separate Writer docs can copy distinct text; A pastes into its own document. | VALID — Calc copy can overwrite A's pending Writer text. C-01. | VALID — Browser produces URL/snippet that overwrites A's pending Writer payload. C-02 is a hybrid source/target workflow. | CONDITIONAL — Terminal selection/copy is possible, but shortcuts and payload attribution need calibration. |
| C | VALID — Writer copy can replace A's pending Calc range/cell payload. C-03. | VALID — two Calc tasks can copy different ranges into distinct destinations. | VALID — Browser text/table/URL copy can overwrite pending Calc paste. | CONDITIONAL — Terminal selection to Calc is possible; MIME and paste shape need an oracle. |
| B | VALID — Writer text copy can replace A's pending Browser-form payload. | VALID — Calc range copy can replace A's pending Browser-form payload. | VALID — two Browser tasks can copy separate values; preserve distinction from tab-context effects. | CONDITIONAL — Terminal output to Browser is plausible; constrain payloads to safe non-command text. |
| T | CONDITIONAL — Writer copy into Terminal input needs safe command semantics and a task-local oracle. | CONDITIONAL — Calc data into a Terminal command is possible but can devolve into a generic shell task. | CONDITIONAL — Browser text into terminal input has weak naturalness and command-safety concerns. | CONDITIONAL — terminal copy/paste shortcuts differ; needs a verified terminal-only clipboard oracle. |

Counts: **9 VALID, 7 CONDITIONAL, 0 INVALID, 0 REDUNDANT.** Evidence is concentrated in W↔C and W×B/B×W; other cells remain candidates.

### Application Context

B changes in-app context while the relevant OS window remains the same. A then acts under its earlier page/sheet/document/session assumption. Cross-domain cells are invalid unless both actors can change the same app context; app switching is Focus.

| A \ B | W | C | B | T |
|---|---|---|---|---|
| W | CONDITIONAL — Writer usually opens separate top-level document windows; same-window document context must be proven. | INVALID — Calc cannot switch Writer's active document context. | INVALID — Browser navigation cannot change Writer's document context. | INVALID — Terminal cannot change Writer's document context. |
| C | INVALID — Writer cannot switch Calc's active sheet/workbook. | VALID — B switches active sheet/workbook in the same Calc window; A's stale sheet assumption can target another sheet. | INVALID — Browser state does not change Calc's active sheet. | INVALID — Terminal does not change Calc's sheet. |
| B | INVALID — Writer cannot change Browser route/tab. | INVALID — Calc cannot change Browser route/tab. | VALID — tab, SPA route or page context changes inside Chromium. A-01; A-02 is better classified as Selection. | INVALID — Terminal cannot change Browser page context. |
| T | INVALID — Writer cannot change shared shell cwd/environment. | INVALID — Calc cannot change shared shell cwd/environment. | INVALID — Browser cannot change shared shell cwd/environment. | CONDITIONAL — B changes cwd/environment in the same visible shell session; observe session identity without making shared filesystem the treatment. |

Counts: **2 VALID, 2 CONDITIONAL, 12 INVALID, 0 REDUNDANT.** T×T is lower priority and concerns one visible Terminal session, not shared-backend engineering.

### Selection / Active Object

B changes selected object/range/caret in an unchanged app context; A's later edit applies to the stale target. Different domains cannot share one selection object.

| A \ B | W | C | B | T |
|---|---|---|---|---|
| W | VALID — two goals in one Writer doc move selected text/object while app/window stay fixed. | INVALID — Calc selection cannot alter Writer selection. | INVALID — Browser selection is not Writer document selection. | INVALID — Terminal caret does not alter Writer selection. |
| C | INVALID — Writer selection cannot alter Calc active cell/range. | VALID — B selects another cell/range in the same Calc sheet before A writes. S-01. | INVALID — Browser selection cannot alter Calc object. | INVALID — Terminal caret does not alter Calc selection. |
| B | INVALID — Writer selection cannot alter Browser row/object selection. | INVALID — Calc selection cannot alter Browser object. | CONDITIONAL — record/row/form selection is possible, but must be distinct from page/tab context and focus. A-02 candidate. | INVALID — Terminal caret does not alter Browser selection. |
| T | INVALID — Writer selection does not change Terminal caret/selection. | INVALID — Calc selection does not change Terminal caret/selection. | INVALID — Browser selection does not change Terminal caret/selection. | CONDITIONAL — shared terminal-buffer selection is observable but overlaps focus/caret and has weak distinct task value. |

Counts: **2 VALID, 2 CONDITIONAL, 12 INVALID, 0 REDUNDANT.** Prioritize W×W and C×C; keep B×B only when selection changes while route/tab/window do not.

### Undo / Redo History

A and B must make undoable edits on the same document/history stack. App switching cannot expose another application's history.

| A \ B | W | C | B | T |
|---|---|---|---|---|
| W | VALID — both edit the same Writer doc; B's later edit is the top undo item A encounters. Candidate U-W. | INVALID — Calc has a separate undo manager. | INVALID — ordinary Browser submit is outside Writer history. | INVALID — Terminal commands are outside Writer history. |
| C | INVALID — Writer edits are outside Calc history. | VALID — same Calc doc; B's later commit becomes A's next Undo target. U-01. | INVALID — ordinary Browser form state is outside Calc history. | INVALID — Terminal commands are outside Calc history. |
| B | INVALID — Writer history does not affect Browser state. | INVALID — Calc history does not affect Browser state. | CONDITIONAL — only a measured in-page editor undo stack qualifies; forms/navigation do not. | INVALID — terminal recall is not document Undo/Redo. |
| T | INVALID — Writer history does not affect Terminal commands. | INVALID — Calc history does not affect Terminal commands. | INVALID — Browser history does not affect Terminal commands. | INVALID — shell command recall is not Undo/Redo of shared document state. |

Counts: **2 VALID, 1 CONDITIONAL, 13 INVALID, 0 REDUNDANT.** Do not count command recall or browser back-navigation as document history.

## 3. Existing anchor mapping

An anchor is one fixed realization of its workflow. The operation graph, not the numeric/text value, determines the workflow count.

| Anchor | Actor A × Actor B task | Matrix cell | Coverage / same-cell distinction | Evidence |
|---|---|---|---|---|
| F-01 | Writer body edit × Calc cell edit / Focus | W×C | Cross-app focus; single target cell. | Historical Qwen Solo pass; MA-ID 2/2 pass; MA-SD 2/2 fail with focus/input-routing traces; scripted history. |
| F-04 | Calc 2×2 cell visits × Writer paragraph replacement / Focus | C×W | Reverse direction from F-01; multi-cell action graph. | Scripted Solo A/B, MA-ID, MA-SD interference and recovery. No Qwen. |
| F-02 | Writer anchored comment × Browser form submit / Focus | W×B | Different app/object graph from F-01/F-04. | Scripted Guest bounded controls and recovery. No Qwen. |
| C-01 | Writer text transfer × Calc text transfer / Clipboard | W×C, A classified by Writer destination | Same domain cell as F-01 but copy/overwrite/paste graph and clipboard oracle differ. | Scripted; Qwen event-gated MA-ID 2/2 and MA-SD overwrite exposure 2/2; outcomes mixed with focus/grounding. |
| C-03 | Calc rectangle transfer × Writer paragraph copy / Clipboard | C×W | Same pair as F-04 but distinct payload and paste operation. | Scripted Solo/MA-ID/MA-SD overwrite/recovery. No Qwen. |
| C-02 | Writer hyperlink target with Browser URL source × Browser URL submit / Clipboard | W×B, hybrid A workflow | Primary scored target is Writer; A also uses Browser. Semantic link dialog differs from plain paste. | Scripted Guest Solo/MA-ID/MA-SD/recovery. No Qwen. |
| A-01 | Browser tab-A submit × tab-B submit / App Context | B×B | Active tab/page changes inside one top-level window. | Scripted and Qwen; Solo stable, MA-ID 2/2 pass, MA-SD 2/2 fail with tab exposure/no autonomous recovery. |
| A-02 | Browser record A edit/commit × record B edit/commit | B×B; recommend **Selection / Active Object** | Different graph from A-01. Hidden state is selected active record in one unchanged page, more directly Selection. Keep task/evidence; change only taxonomy label. | Scripted Guest Solo/MA-ID/MA-SD/recovery. No Qwen. |
| S-01 | Calc B2 edit × C3 edit / Selection | C×C | Active-cell target changes; distinct from Undo history. | Scripted and Qwen; Solo A/B 2/2, MA-ID 2/2, MA-SD exposure 3/3, 1 fail/2 recovered. |
| U-01 | Calc temporary edit+Undo × Calc independent edit / Undo | C×C | Same app/cell type as S-01, but shared history stack and Undo are the treatment. | Scripted and Qwen; Solo A/B 2/2, MA-ID 2/2, MA-SD exposure/interference 2/2, no recovery. |

**Current anchor count remains 10 workflows.** With A-02 reclassified: Focus 3, Clipboard 3, Application Context 1, Selection 2, Undo 1. No existing evidence is changed. A-02's operation workflow is distinct; the recommendation moves its family because the controlled state is a selected record, not a page/tab route.

## 4. New high-value workflow candidates

Proposals only. B's action must be part of B's own valid goal. Recovery and evaluation are to be tested later.

| Candidate / family | A × B | Independent goals and mechanism path | Stale assumption / expected interference | Recovery and oracle | Duplicate check | Cost / priority |
|---|---|---|---|---|---|---|
| F-N1 Focus | W×W | A edits paragraph in doc A; B adds a comment in doc B. B activates doc B. | A types under doc A foreground assumption; edit can land in doc B. | Reopen/focus doc A; exact path-bound ODF text/comment plus untouched guards. | Revives deferred F-03 only if document identity and comment operation are verified. | MEDIUM / P1 |
| C-N1 Clipboard | W×B | A copies formatted HTML snippet/table from Browser into Writer; B copies valid URL/text for own Browser task. | A assumes rich MIME payload remains; paste may flatten or use B payload. | Recopy; check ODF table/text/style, clipboard generation/MIME/digest and guards. | Distinct from C-02 only if formatting structure is part of oracle, not just different string. | HIGH / P1 |
| A-N1 App Context | B×B | A edits a field on Browser route A; B completes normal SPA route/record navigation in same tab/window. | A submits under stale route assumption into route B. | Reacquire route A; exact route-keyed values/revisions and same X11 window/tab. | Distinct from A-01 tab activation; reject if it opens another window. | MEDIUM / P1 |
| A-N2 App Context | C×C | A edits a target on Calc Sheet A; B switches sheet and edits its independent Sheet B target. | A's cell address is interpreted on Sheet B. | Re-select/verify sheet; multi-sheet ODF oracle plus sheet/window event. | Not S-01 if active sheet is observed separately from active cell. | MEDIUM / P1 |
| A-N3 App Context | T×T | A runs a valid relative-path task in shared visible shell; B changes cwd to complete its own command. | A assumes old cwd; action reads/writes wrong relative target. | Observe pwd and reacquire directory; command/result log and task-local output oracle. | Not filesystem-backend treatment; keep only with independent goals and local isolated outputs. | HIGH / P2 |
| S-N1 Selection | W×W | A selects sentence A for comment/style; B selects sentence B for independent annotation/style in same Writer doc. | A applies edit to B's current range. | Re-select exact range; UNO range plus ODF annotation/style/text oracle, X11 window held constant. | Distinct from focus only if range changes while window/document remain fixed. | MEDIUM / P1 |
| S-N2 Selection | C×C | A changes Chart A title; B selects Chart B and changes its title in one sheet. | A edits stale selected chart. | Re-select chart A; object IDs/title oracle and selected-object observer. | Not a cell-coordinate variant; requires reliable chart identity observation. | HIGH / P2 |
| U-N1 Undo | W×W | A makes a temporary Writer edit intended for Undo; B adds independent formatting/comment to same doc; A uses ordinary Undo. | A assumes its edit is top history item; Undo removes B's edit. | Detect/reapply both; exact ODF text/annotation/style and history snapshots. | Cross-app extension of U-01 with a different operation/object. | MEDIUM / P1 |
| U-N2 Undo | C×C | A makes a two-action Calc transaction; B commits an independent cell change between A's steps; A performs Undo. | A assumes Undo corresponds to its transaction. | Inspect/reapply formula/value/style; full grid/formula/style oracle and history event order. | Distinct only if transaction grouping is part of the task, not a new value in U-01. | HIGH / P2 |
| U-N3 Undo | B×B | A edits a local Browser rich-text document and plans Ctrl+Z; B edits the same editor first. | A assumes own edit is top undo item. | Reapply under observation; deterministic editor state/history event and final DOM/text/style oracle. | Conditional: invalid if only form inputs or browser navigation are changed. | HIGH / P2 |

High-value cell mapping: all 12 Focus off-diagonal cells are mechanically VALID but do not each justify a workflow; current anchors cover W×C, C×W and W×B. Representative new focus cell W×W is F-N1. Clipboard's 9 GUI-only VALID cells are covered by C-01/C-03/C-02 in W×C/C×W/W×B; C-N1 adds rich-object semantics. Application Context valid cells B×B/C×C are A-01/A-N1/A-N2. Selection valid cells W×W/C×C are S-N1/S-01; S-N2 is a higher-cost extension of C×C. Undo valid cells W×W/C×C are U-N1/U-01; U-N2 changes the Calc history graph. These are selections from the matrix, not an exhaustive implementation list.

### Broad-tier reserve pool

Promote only after initial candidates show stable oracles:

- Focus: Browser form × Terminal window; Calc document A × separate Calc document B with explicit window identity.
- Clipboard: Browser TSV × Calc table; safe Terminal selected output × Writer quote/code block.
- Application Context: Browser project/workspace selector in one SPA; Terminal environment/profile change within one session.
- Selection: Browser row/object selection with route fixed; Writer image/drawing selection with object-ID oracle.
- Undo/Redo: Writer tracked-change accept/reject history; Calc formula dependency/group undo.

These are not validated tasks.

## 5. Consolidated workflow index

This index makes the selected domain cells actionable. Existing means there is a current fixed anchor; new means a design proposal only. P1/P2 are design priorities, not authorization to run episodes.

| Family | Task A | Task B | Candidate workflow | Existing/New | Difficulty | Oracle | Priority |
|---|---|---|---|---|---|---|---|
| Focus | Writer body edit | Calc cell edit | F-01 direct edit pair | Existing | LOW | Saved ODF body + exact cell/guard state | Anchor |
| Focus | Calc 2×2 fill | Writer paragraph replace | F-04 block + paragraph | Existing | MEDIUM | Full Calc grid + Writer paragraph/guards | Anchor |
| Focus | Writer anchored comment | Browser case submission | F-02 annotation + form | Existing | MEDIUM | ODF annotation + exact Browser payload/revision | Anchor |
| Focus | Writer doc A paragraph | Writer doc B comment | F-N1 two-document focus | New | MEDIUM | Path-bound ODF body/comment + active window ID | P1 |
| Clipboard | Writer text copy/paste | Calc text copy/paste | C-01 plain text transfer | Existing | MEDIUM | Exact saved ODF + clipboard owner/generation/digest | Anchor |
| Clipboard | Calc rectangle paste | Writer paragraph copy | C-03 structured range transfer | Existing | MEDIUM | Full cell matrix + Writer text + payload digest | Anchor |
| Clipboard | Browser URL to Writer hyperlink | Browser URL submission | C-02 semantic hyperlink transfer | Existing | MEDIUM | ODF visible label/href + Browser payload/revision | Anchor |
| Clipboard | Browser rich snippet to Writer | Browser URL/text copy | C-N1 rich MIME transfer | New | HIGH | ODF table/text/style + clipboard MIME/digest + guards | P1 |
| App Context | Browser tab A form | Browser tab B form | A-01 tab context | Existing | LOW–MEDIUM | Per-tab state/revisions + same top-level window/tab events | Anchor |
| App Context | Browser route A field | Browser SPA route B goal | A-N1 route context | New | MEDIUM | Route-keyed state + same window/tab + route events | P1 |
| App Context | Calc Sheet A cell | Calc Sheet B cell | A-N2 active sheet | New | MEDIUM | Multi-sheet ODF + active-sheet events | P1 |
| App Context | Terminal relative-path task | Terminal cwd-changing task | A-N3 shell session context | New | HIGH | Session identity + pwd/command events + exact local output | P2 |
| Selection | Calc B2 target | Calc C3 target | S-01 active cell | Existing | LOW–MEDIUM | Full grid + UNO selection observer | Anchor |
| Selection | Browser record A | Browser record B | A-02 selected record (reclassify) | Existing | MEDIUM | Per-record value/revision + selected-record event | Reclassify |
| Selection | Writer range A annotation/style | Writer range B annotation/style | S-N1 text range | New | MEDIUM | UNO range + ODF anchor/style/text + fixed window | P1 |
| Selection | Calc Chart A title | Calc Chart B title | S-N2 active chart object | New | HIGH | ODF chart object IDs/titles + selected-object observer | P2 |
| Undo/Redo | Calc temporary B2 edit + Undo | Calc C3 edit | U-01 history top entry | Existing | MEDIUM | Exact cells + history snapshots | Anchor |
| Undo/Redo | Writer temporary text edit + Undo | Writer comment/style | U-N1 shared Writer history | New | MEDIUM | ODF text/comment/style + undo event sequence | P1 |
| Undo/Redo | Calc grouped formula/format transaction | Calc independent cell commit | U-N2 grouped history | New | HIGH | Formula/value/style oracle + history order | P2 |
| Undo/Redo | Browser rich-text edit + Undo | Browser independent editor edit | U-N3 web editor history | New | HIGH | Deterministic editor state/history + final DOM | P2 |

## 6. Workflow de-duplication

- Reclassify A-02 to Selection / Active Object. It is not a seed variation of A-01: one changes selected record in one page, the other activates another tab. Keep its workflow ID, code, runs and evidence.
- Keep C-01/C-03/C-02 separate: scalar text, rectangular table, semantic hyperlink have different action/payload/oracle paths.
- Keep F-01/F-04/F-02 separate: single-object entry, multi-cell traversal, Browser transaction plus anchored annotation.
- Keep S-01/U-01 separate: selected-cell pointer versus document-history stack.
- An ordered app pair is not automatically a workflow. A second workflow in a cell must differ in operation graph, object/oracle, or recovery—not only direction, value, coordinate or text.

## 7. Suite-size tiers

| Tier | Count | Composition | Use |
|---|---:|---|---|
| MINIMAL | **15** | Focus 4; Clipboard 4; App Context 2; Selection 3; Undo 2. Current anchors plus F-N1/C-N1/A-N1/S-N1/U-N1. | First implementation set; adds support to thin families and app-context coverage. |
| BALANCED | **20** | Four workflows per family. Minimal set plus A-N2/A-N3/S-N2/U-N2/U-N3. | **Recommended V1 target**, conditional on each proposal passing setup/oracle and scripted controls. |
| BROAD | **30** | Balanced suite plus ten reserve workflows selected by evidence, two per family. | Later extension; do not fill all cells or implement reserve candidates by default. |

The five-family scope is unchanged. Proposed workflow count is not validated workflow count.

## 8. N=3 / N=4 scaling subset

Do not enumerate all D³ or D⁴ app combinations. Add actors to a small set of proven workflows while holding task semantics, app, shared state, evaluator and budgets explicit.

- N=3: **5 representatives**, one per family: F-01 with a third independent GUI target; C-01 with a third legitimate copy source; A-01 with a third Browser route/tab; S-01 or S-N1 with a third distinct object; U-01 with a third same-document edit before A's Undo.
- N=4: **2–3 only** after N=3: C-01 (clipboard overwrite chain), A-01 (tab-context chain), U-01 (history-stack depth). Retain only if extra Actor changes exposure/cascade rather than adding an independent goal.
- Metrics: actor/joint success, distinct state-generation changes, affected actors, contamination cascade, detection latency, recovery actions/outcome, and turn/action budget. Treat as scaling study, not core matrix.

## 9. Estimate for 600–700 fixed tasks

A fixed instance freezes meaningful goals, initial state, target objects and oracle parameters while preserving workflow graph. Seed, text token, case number, coordinates, filename and repeat number do not suffice.

The 20-workflow Balanced suite has a **planning-only 650-instance allocation**:

| Family | Workflow | Proposed count | Diversity rationale |
|---|---|---:|---|
| Focus | F-01 | 20 | Single-cell/direct-entry graph; cap value substitutions. |
| Focus | F-04 | 35 | Table schema/layout and guards. |
| Focus | F-02 | 35 | Review/case/anchor semantics with exact annotation/form checks. |
| Focus | F-N1 | 35 | Distinct Writer documents/comment role if window identity is reliable. |
| Clipboard | C-01 | 20 | Bound plain-string variants. |
| Clipboard | C-03 | 40 | Matrix shape, values, source/destination and guards. |
| Clipboard | C-02 | 35 | Link-label/href semantics and Browser cases. |
| Clipboard | C-N1 | 40 | Rich structure only if the oracle checks it. |
| App Context | A-01 | 35 | Two-tab route/form semantics. |
| App Context | A-N1 | 35 | SPA route changes in one tab. |
| App Context | A-N2 | 35 | Sheet identity/content while active-sheet treatment stays fixed. |
| App Context | A-N3 | 30 | Terminal session context, conditional. |
| Selection | S-01 | 25 | Cap single-cell anchor variants. |
| Selection | A-02 | 25 | Record selection; family relabel only. |
| Selection | S-N1 | 40 | Range/anchor roles and annotation/style. |
| Selection | S-N2 | 35 | Chart object identities, conditional on observer. |
| Undo/Redo | U-01 | 25 | Cap one Calc history path. |
| Undo/Redo | U-N1 | 40 | Writer text/comment/style operation classes. |
| Undo/Redo | U-N2 | 30 | Small quota until grouped history is stable. |
| Undo/Redo | U-N3 | 35 | Conditional on deterministic Browser editor history. |
| **Total** | **20 workflows** | **650** | Target after production gates, not generated. |

Higher diversity workflows receive 35–40; narrow anchors receive 20–25. Reduce the total if conditional workflows fail. Current fixed-instance count under this plan is zero.

## 10. Production gate and recommendation

**Gate: NEEDS_SMALL_DESIGN; not ready for instance generation.**

1. Accept the four axes, with Terminal remaining scripted-only until a GUI-agent Solo task passes.
2. Approve the A-02 classification under Selection without rewriting historical artifacts.
3. Design-check the five MINIMAL additions F-N1/C-N1/A-N1/S-N1/U-N1; reject any that differ only by values or UI coordinates.
4. Each must have independent Solo A/B, an exact oracle and reset contract, then scripted MA-ID/MA-SD and recovery controls. Model pilot comes later.
5. Only after that define typed semantic parameters and produce three reviewed instances per workflow with regeneration/hash and evaluator positive/negative checks.

**Implementation status:** the five matrix workflows now have code contracts; see `MATRIX_WORKFLOW_IMPLEMENTATION_V1.md`. A-02 is reclassified under Selection / Active Object without rewriting old evidence. Do not implement all 20 at once or generate the planning-only 650 tasks.

## Evidence sources

Environment: ENV_SETUP.md, README.md, pinned OSWorld V2.1 setup scripts and existing outputs/osworld-v2.1 reports.  
Workflow code: swcub/tasks/workflows_v1.py, browser_writer_workflows_v1.py, clipboard_v1.py, browser_context_v1.py, browser_record_context_v1.py; scripts/run_writer_calc_v1.py, run_clipboard_v1_round1.py, run_browser_writer_workflows_v1.py, probe_selection_active_object_v1.py, probe_undo_history_v1.py.  
Reports: WORKFLOW_SUITE_V1.md, WORKFLOW_IMPLEMENTATION_V1.md, QWEN_FAMILY_PILOT_REPORT.md, FAMILY_EXPANSION_V1_REPORT.md.  
This round used repo sources/reports only. No private external project was inspected. No Guest, Docker, or Qwen resource was started or modified.


## 11. P1 minimal-suite realization status (2026-10-03)

The domain matrix remains the feasibility map; implementation is tracked separately. The frozen five-family count stays unchanged. A-02 is now mapped under Selection / Active Object while its original workflow ID, code, runs and historical evidence are preserved. The five proposed additions are F-N1 (W×W), C-N1 (Browser rich payload→Writer), A-N1 (Browser SPA route), S-N1 (Writer range), and U-N1 (Writer history).

Only F-N1 Solo A and Solo B have completed real Guest episodes in this round, including Writer readiness, saved target state, evaluator, ownership ledger, and fresh-Guest reset. It is one successful side of one condition, not workflow validation. Offline evaluator tests passed; C-N1 rich clipboard MIME, other Solo sides, MA-ID, MA-SD and recovery remain unverified. Qwen was not run because the 4090 inference host SSH connection timed out and A6000 inference is frozen. See the implementation report for all condition states and resource evidence. The 15-workflow count remains a target, not 15 validated workflows.
