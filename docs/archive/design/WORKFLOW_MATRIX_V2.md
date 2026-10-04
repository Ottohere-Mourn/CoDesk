# CoDesk Workflow Matrix V2

Status: design-only candidate matrix. No task instances were generated or registered. This matrix is based on the current protocol, positioning, Round-1 report and Workflow Expansion V1 at canonical A6000 HEAD `a1baba93e1020ffbf9d7060b0bbbf8079215f865`.

## Design objective and counting rule

A workflow template fixes actor operation graphs, target/resource type, interaction point and oracle predicates. An instance supplies task-specific initial content and expected state. A run supplies condition, schedule, model, budgets, Guest identities, coordinates and repeat.

A new template must change a substantive dimension: operation sequence or transaction semantics, target/control type, hidden-state transition, or oracle/integrity predicate. Text, seed, record ID, coordinates, theme and repeat do not create workflows. Replacing one office document with another while preserving the operation and oracle is an instance.

All proposals require independently valid actor goals, individual Solo solvability, joint feasibility, a deterministic hidden-state oracle, and matched task-relevant initial state across MA-ID and MA-SD. MA-ID may use independently initialized local filesystems when neither actor needs to see the other's persistent edits. For each run, report scheduled exposure, observed interference, final outcome and recovery separately. Actors retain the right to observe and recover.

## Family candidates and evidence boundary

| Family candidate | Round-1 evidence/status | V2 role |
|---|---|---|
| Focus / input routing | KEEP; Qwen evidence on Writer+Calc anchor | Core. Vary operation class and target ambiguity only when operation/oracle differs materially. |
| Clipboard ownership / transfer | KEEP candidate; scripted real-Guest Solo, MA-ID, MA-SD, observer and recovery | Extension candidate; no Qwen clipboard evidence. |
| Window / modal ownership | Optional; native Writer dialog observable in scripted probes, no two-actor task outcome | Optional, feasibility-gated. Merge with Focus if the only measurable outcome is ordinary wrong-window input. |
| Application-internal context | Optional; scripted same-Chrome-window page switch and stale action, no task controls | Optional, feasibility-gated. Keep distinct only if top-level window is unchanged while internal target context changes. |

This is a four-family initial matrix plus one unvalidated fifth-family candidate (document transaction history) described below. It has no CoDesk Guest or task-control evidence.

## Workflow template matrix

Difficulty is a relative implementation estimate: Low = current setup/oracle likely reusable; Medium = new deterministic setup or richer parsing; High = fragile native UI or additional instrumentation.

### A. Focus / input routing (Core)

| Template | Apps and independent goals | Shared hidden state / scheduled exposure | Expected interference | Oracle idea | Difficulty |
|---|---|---|---|---|---|
| F-01 Office cross-window direct entry (anchor) | Writer A enters/saves a sentence in document A. Calc B edits/saves a designated cell in workbook B. | Active top-level window, keyboard and pointer; partner legitimately activates its app between the other actor's observation and action. | Valid text/shortcut reaches the foreground partner app; goals remain incomplete or unrelated state changes. | Exact ODF text/cell plus non-target integrity; join action target with active-window events. | Low; already model-smoked. |
| F-02 Browser form transaction vs Writer comment | Browser A completes/submits a local multi-field form. Writer B inserts a comment at a specified phrase and saves. | Foreground window and keyboard target during multi-step form/comment workflows. | Form text/submit action lands in Writer, or comment input/confirmation lands in Browser. | Exact submitted record and comment anchor/text; detect cross-app leakage. | Medium. |
| F-03 Same-application two-document edit | Writer A adds a comment to document A. Writer B edits a named heading in document B; both are separate top-level windows. | Active document/window identity within one process. | Edit reaches the wrong Writer document despite correct app/process. | Inspect both ODF files for exact target state and untouched counterpart; log window/document identity. | Medium; requires reliably distinct window IDs. |
| F-04 Spreadsheet range transaction vs prose edit | Calc A selects a rectangle, fills a formula/value pattern and saves. Writer B replaces a specified paragraph and saves. | Foreground window, active range and keyboard routing across a multi-action edit. | Formula/fill reaches wrong app/range or spills into neighbors. | Exact matrix/formula addresses, neighbor-cell integrity and exact Writer paragraph. | Medium; operation/oracle differ from single-cell anchor. |
| F-05 Pointer drag/reorder vs app edit | Calc A reorders named rows/columns by drag. Writer B edits a specified paragraph. | Pointer capture, selection and window ownership during press–move–release. | Drag starts/ends in a different target, selection is lost, or wrong object changes. | Exact order and preserved row data plus Writer output; log pointer down/move/up and window identity. | High; promote only if drag and oracle are deterministic. |
| F-06 Browser record navigation/commit vs Calc edit | Browser A navigates/filter-selects a local record, changes its status and commits. Calc B edits a separate cell. | Foreground window and target control during navigation followed by commit. | Action lands in Calc or commits the wrong Browser record after context change. | Exact target record status and Calc cell; adjacent records/cells unchanged. | Medium; differs from form submission/comment workflow. |

### B. Clipboard ownership / transfer (Extension candidate)

| Template | Apps and independent goals | Shared hidden state / scheduled exposure | Expected interference | Oracle idea | Difficulty |
|---|---|---|---|---|---|
| C-01 Plain paragraph transfer (prototype) | Writer A copies a source paragraph and pastes to a destination. Calc B copies its own token and pastes to a separate cell. | Session clipboard owner/generation/payload between copy and paste. | B replaces A payload; A pastes B text into the intended target or detects and recopies. | Exact destination paragraph/cell and source integrity; observer joins generation/payload, paste target and final state. | Low; scripted evidence exists. |
| C-02 URL-to-hyperlink transaction | Browser A copies a local page URL and creates a hyperlink with specified display text in Writer. B transfers a distinct value to its own destination. | Clipboard replaced between URL copy and hyperlink insertion; target URL and display text have separate semantics. | Wrong URL becomes hyperlink target, or plain text appears instead of the required link. | Inspect ODF href and visible text exactly; check B destination and clipboard trace. | Medium. |
| C-03 Rectangular spreadsheet-range transfer | Calc A copies a multi-cell rectangle and pastes to a declared range. Writer B copies/pastes a separate paragraph. | Structured tab/newline clipboard payload and generation. | Payload is replaced, flattened, shifted or overwrites cells. | Exact dimensions, values/formulas, offsets and untouched neighbors; digest alone is insufficient. | Medium–High. |
| C-04 Rich-text transfer with formatting | Writer A copies a formatted list or linked phrase to a target location. Writer B copies distinct content to a separate destination. | MIME alternatives (text, HTML/RTF) and paste-format negotiation. | Payload replacement or format loss/wrong representation. | Exact text plus ODF style/list/link structure, with no extra object. | High; requires reliable MIME and ODF inspection. |
| C-05 Cut-and-move transaction | Writer A moves a paragraph from source to destination via cut/paste. B performs a separate clipboard transfer between removal and confirmation. | Clipboard replacement during a destructive two-phase move. | Content is lost/duplicated or B payload is inserted; recovery may require undo or recopy. | Source absent only after destination exact match; no duplicates; validate both goals and recovery state. | High; transaction oracle must distinguish transient and final loss. |
| C-06 Image payload transfer | Writer A copies an existing local image through GUI and pastes at a specified document location. B copies text to its own separate target. | Clipboard MIME/payload changes between image and text. | Wrong representation is pasted, image is absent, or text appears in the image target. | Extract ODF image, compare bytes/hash and location; exact B output and no unintended objects. | High; retain only if image transfer is stable. |

### C. Window / modal ownership (Optional)

| Template | Apps and independent goals | Shared hidden state / scheduled exposure | Expected interference | Oracle idea | Difficulty |
|---|---|---|---|---|---|
| M-01 Save As dialog ownership | Writer A saves its document to an exact new path. Calc B updates/saves a designated cell. | Native Save chooser is modal/transient to Writer and can block or own keyboard/pointer while B acts. | B action is blocked/routed to chooser, A receives B input, or actors detect and recover. | Exact path/content and Calc cell; dialog closed; event records modal flag, transient parent and active window. | Medium–High; dialog observable, two-actor outcome untested. |
| M-02 Overwrite-confirmation decision | Writer A replaces a seeded output and confirms. Calc B independently changes/saves a cell. | Confirmation modal owns input and presents a destructive decision between observation and action. | B confirmation/cancel input resolves A dialog incorrectly or A decision interferes with B. | Exact new Writer version, protected sentinel unchanged, exact Calc cell; modal owner/decision logged. | High; requires deterministic, disposable fixture. |

### D. Application-internal context (Optional)

| Template | Apps and independent goals | Shared hidden state / scheduled exposure | Expected interference | Oracle idea | Difficulty |
|---|---|---|---|---|---|
| A-01 Same-window browser tabs with forms | Browser A fills/submits local form on tab A. Browser B fills/submits independent form on tab B in the same Chrome window. | Active tab/page target changes while top-level X11 window ID stays constant. | A action based on tab A observation modifies tab B or submits wrong form without OS focus change. | Per-tab exact records, page/target identity, constant X11 ID, no cross-form contamination. | Medium; scripted signature exists, task controls do not. |
| A-02 Single-tab route/record context switch | Browser A edits record X in a local single-page app. Browser B navigates the same tab to record Y or changes selected record and edits its goal. | Internal route/selected-record changes in same tab and same top-level window. | A stale action is applied to Y/wrong detail panel after B changes route or selection. | Exact X/Y and neighboring-record states, stable X11 ID, distinct app route/record IDs. | High; reject if route identity or no-window-change evidence is unavailable. |

## Family summary and quality recommendation

| Family | Candidate count | Evidence | Recommendation |
|---|---:|---|---|
| Focus / input routing | 6 | Anchor has model Solo/MA-ID/MA-SD evidence; remaining proposals | Start with F-01 and at most two of F-02/F-03/F-04 after feasibility and deduplication. F-05 is stretch. |
| Clipboard | 6 | C-01 has scripted real-Guest Solo/MA-ID/MA-SD, observer and recovery; no Qwen | Start with C-01, then C-02/C-03 if link/range oracle is exact. C-04–C-06 are stretch pending MIME/transaction feasibility. |
| Modal ownership | 2 | Native dialog observable; no paired task | Test M-01 before M-02. Merge with Focus if modal state adds no distinct oracle or recovery measure. |
| Application-internal context | 2 | One scripted same-window page-switch probe; no registered controls | Test A-01 first. A-02 needs objective route identity without window/focus change. |
| Shared document transaction history | 2 | New research-derived inference only; no CoDesk task evidence | Feasibility-check H-01 only; defer H-02 unless it has a separate observable redo oracle. |

The four initial families contain 16 candidates; H-01 and H-02 add two unvalidated transaction-history candidates, for 18 design candidates across five candidate families. They are not implemented or validated workflows. A 15–20 candidate design inventory is feasible, but an executable suite of that size is not yet justified. Treat **8–12 accepted templates** as a planning ceiling, not a quota; report fewer if candidates merge or fail feasibility.

## Instance production boundary

After a template passes, instances may vary semantic content while preserving its operation graph and oracle class. Such instances add coverage within a template, not template count. Each fixed instance manifest should identify family/template/version, actor goals, fixture hashes, exact expected states, invariants, Solo and joint-feasibility status, oracle version and provenance. Condition, schedule and runtime configuration belong to the run record.

Only templates passing Solo, joint-feasibility, negative-control, reset, observer and MA-ID/MA-SD topology checks should be expanded toward 200–300 instances. Report accepted template count, verified instances per template, generation cost and evaluator-audit cost separately; seed count is not evidence of workflow diversity.

## Promotion gates

1. Compare operation graphs and oracle against accepted templates; merge proposals differing only in content or app branding.
2. Verify each actor goal in Solo with the intended application version and evaluator.
3. Prove joint feasibility and negative-state detection using scripted actors without hard-coded wrong routes/actions.
4. Match task-relevant initial state across MA-ID and MA-SD; hold backend topology constant if actors need cross-agent persistent visibility.
5. Verify exposure/event evidence independently from outcome; hidden observer state must not reach actors.
6. Keep Modal/App Context optional unless they have a distinct trace signature and evaluator beyond Focus/Clipboard.
7. Generate only a small fixed-instance set after template acceptance; defer bulk expansion.



## Explicit candidate count and workflow-difference audit

| Evidence count | Meaning |
|---:|---|
| 18 | Design candidates across five proposed families with provisionally distinct operation graphs/oracles; inventory only. |
| 1 | Existing model-validated workflow: F-01 Writer/Calc focus anchor. |
| 1 | Existing scripted end-to-end workflow with Solo, MA-ID, MA-SD, observer and recovery: C-01. This is not model evidence. |
| 2 | Mechanism feasibility probes only: a native dialog observation and same-window page-context change. Neither is a registered task with full condition controls. |
| 0 | Workflows implemented or run by this matrix. |

The operation/oracle differences and deduplication gates are:

| Candidates | Difference from nearest proposal | Merge/drop gate |
|---|---|---|
| F-01 | Direct cross-app text/cell entry; existing anchor. | Keep as anchor. |
| F-02 / F-06 | Multi-field form plus Writer comment versus record discovery/filter/navigation plus status commit; different operation graph and oracle object. | Merge F-06 if it reduces to the same form-fill/submit workflow. |
| F-03 | Two top-level Writer documents in one process; oracle identifies two ODF documents, not just application identity. | Drop if stable document/window identity is unavailable. |
| F-04 | Multi-cell formula/fill with range and neighbor-integrity oracle, not single-cell edit. | Merge if range behavior adds no measurable invariant. |
| F-05 | Pointer drag lifecycle and row-order permutation oracle, not keyboard entry. | Drop if drag is not reproducible or evidence is only focus loss. |
| C-01 | Plain paragraph transfer; existing clipboard anchor. | Keep as baseline. |
| C-02 | URL becomes a semantic hyperlink with separate href/display-text checks. | Merge if link target cannot be reliably inspected. |
| C-03 | Rectangular payload must preserve dimensions, offsets and formulas, not scalar text. | Merge/drop if shape is not checkable or it becomes plain text. |
| C-04 | Rich-text MIME/paste negotiation with formatting/list/link oracle. | Merge/drop if format differences are not reliable. |
| C-05 | Destructive two-phase move; source removal must pair with one destination copy, adding loss/duplication/recovery invariants. | Merge if source integrity adds no distinct measurement over C-01. |
| C-06 | Binary image transfer with embedded-object hash/location oracle, not text oracle. | Drop if image transfer or placement is unstable. |
| M-01 / M-02 | New Save As path selection versus overwrite confirmation against a seeded sentinel; different decision and preservation oracle. | Merge if both measure only generic modal blocking/focus. |
| A-01 / A-02 | Switch open tabs/page targets versus change route/selected record in one tab; page-target versus route/record oracle. | Merge if both reduce to page switching; drop A-02 if route identity is unavailable. |
| H-01 | Undo-stack ownership across two disjoint edits to the same Writer document; oracle checks whether a partner edit was undone despite correct focus/target. | Candidate only if history scope can be observed and joint goals are feasible without forcing a wrong action. |
| H-02 | Redo-branch invalidation after a partner commit; oracle checks restoration of A draft plus B committed edit. Operation and recovery predicate differ from H-01. | Merge with H-01 unless the redo transition has a distinct observable signature. |

The evidence-backed task count is two only if scripted C-01 is counted alongside model-validated F-01; only F-01 has model evidence. Modal and App Context probes do not count as task templates. The candidate target of 15–20 is feasible as a design inventory, not yet justified as an executable suite. An initial suite should accept only candidates passing the gates above; 8–12 is a planning ceiling, not a quota. If proposals merge or fail feasibility, publish the lower count.

## E. Shared document transaction history (new family candidate; unvalidated inference)

This candidate was suggested by a separate mechanism review. It is an unvalidated inference: no CoDesk Guest workflow, evaluator or MA-ID/MA-SD controls currently establish it. The hidden state is the document-scoped undo/redo history. It may be orthogonal to Focus and Clipboard: actors can edit the intended document/target while a partner operation changes the semantic effect or availability of Undo/Redo.

| Template | Apps and independent goals | Shared state / exposure | Expected interference | Oracle | Difficulty |
|---|---|---|---|---|---|
| H-01 Shared undo-stack ownership | Two actors edit disjoint sections of one Writer document. A performs an operation it intends to undo; B commits a disjoint edit before A acts. Each goal requires its own section state and preservation of the partner edit. | Document undo history; B operation occurs after A operation but before A undo decision. | A's otherwise valid undo removes B's last operation while focus and target remain correct. | Parse ODF section text/styles; verify both goals and partner-edit preservation; correlate undo event and final state. | High; undo granularity/history scope must be checked. |
| H-02 Redo-branch invalidation | A edits a draft, undoes it, and intends to redo it. B commits a disjoint edit before A redo. | Partner transaction may invalidate A redo branch. | A cannot restore its draft through redo although B change remains valid and focus is correct. | Exact A draft and B content; inspect redo availability if observable, else cause remains unknown. | High; defer unless distinct from H-01. |

Condition sketch and limits:
- Solo: each actor runs its own edit/undo or edit/undo/redo path on a seeded document; exact state must pass.
- MA-ID: equivalent document fixtures on independent desktops; each actor runs its workflow on its own copy and each replica is evaluated. This is an isolation control, not shared-file access.
- MA-SD: both actors use the same live Writer document/window and shared application history. Goals target disjoint sections and remain jointly satisfiable. Do not instruct an actor to issue an intentionally wrong Undo/Redo; permit observation and recovery.
- A failed goal alone does not establish history contention. Require action trace plus final ODF state and, if possible, non-invasive undo/redo-state observation. Otherwise label cause unknown.
- Recommendation: fifth optional candidate family; feasibility-check H-01 first. Add H-02 only if its redo transition/oracle stays distinct after review.

