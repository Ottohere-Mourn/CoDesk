# CoDesk Workflow Suite V1

Status: **five-family scope frozen; 10 historical anchor templates plus five P1 prototypes are mapped** as of 2026-10-03. The five P1 additions are prototypes, not all validated. Evidence remains bounded mechanism evidence, not a reliability estimate. See `FAMILY_TAXONOMY_V1.md` and `FAMILY_EXPANSION_V1_REPORT.md`.

## Protocol boundary

CoDesk evaluates independent computer-use Actors operating under one shared, non-exclusive desktop state. Conditions are:

- **Solo:** one Actor and one fresh Guest.
- **MA-ID:** two independently controlled Guest desktops initialized from byte-identical task-relevant fixtures. These workflows do not require one Actor to read another Actor's persistent file changes.
- **MA-SD:** both Actors take turns on the same Guest, desktop and relevant ephemeral GUI state.

Hold task version, fixture, goals, schedule, action budget, evaluator and reset contract fixed. Record scheduled exposure, observed state/target interference, goal outcome and recovery separately. The private evaluator reads final application state; Actors receive GUI observations only. An exposure or state change alone is not a task failure.

## Workflow mappings and evidence status

| ID | Family / mechanism | Apps and distinct operation graph | Actor A goal | Actor B goal | Objective oracle | Recovery | Evidence status |
|---|---|---|---|---|---|---|---|
| F-01 | Focus / input routing | Writer + Calc; direct text entry plus single-cell edit | Save the assigned Writer content | Save the assigned Calc cell value | Path-bound ODF content/cell checks and untouched-state checks | Reobserve and reactivate the intended app/target | **Legacy validated**: historical Qwen Solo, MA-ID 2/2 pass, MA-SD 2/2 fail; older task/runner evidence, not a fresh V1 protocol run. See `MECHANISM_VALIDATION_ROUND1.md`, `REAL_DUAL_AGENT_EVAL_REPORT.md`. |
| F-04 | Focus / input routing | Calc rectangular-cell visits plus Writer paragraph replacement | Fill B2:C3 and preserve guard cells | Replace the assigned Writer paragraph only | Exact full Calc matrix plus Writer content/guard oracle | Refocus, reselect the rectangle, continue | **Scripted validated**: prior Solo A/B, MA-ID, naive MA-SD and refocus recovery evidence in `WORKFLOW_IMPLEMENTATION_V1.md`; no model evidence. |
| F-02 | Focus / input routing | Browser review form plus Writer anchored comment; select anchor → form transaction → add comment | Add `Review note 482` to the selected `Review anchor` and save | Submit case `CASE-901` with decision `APPROVE` exactly once | Saved FODT annotation text/name/end and intact anchor/guard; private Browser payload and revision=1 | Reacquire Writer, reselect anchor, then add comment | **Scripted Guest validated (one bounded run/control):** Solo A/B PASS, MA-ID joint PASS, naive MA-SD FAIL with A's comment keystrokes routed while Chrome was active and Browser revision 3, recovery MA-SD joint PASS. Artifacts `f02-{solo*,maid,masd*}-20261001-r01`; MA-ID is the one matching `r01`. Repeated Browser revisions after A's wrong-target actions are observed; the exact triggering key is not isolated. |
| C-01 | Clipboard state | Writer + Calc; plain-text copy → interruption → paste | Transfer exact assigned text | Independently transfer B's text to its target | Exact saved destination content, guard integrity and clipboard observer sequence | Reacquire source, recopy and paste | **Scripted validated** under historical fixed fixture; no Qwen evidence. See `CLIPBOARD_001_STATUS.md`, `MECHANISM_VALIDATION_ROUND1.md`. |
| C-03 | Clipboard state | Calc rectangular range copy/paste plus Writer paragraph copy | Transfer the exact 2×2 table range | Duplicate the assigned Writer paragraph | Full Calc matrix, Writer content/guards, clipboard payload digest and GUI target | Reacquire Calc source and recopy range | **Scripted validated**: Solo A/B, MA-ID, naive MA-SD and recopy recovery in `WORKFLOW_IMPLEMENTATION_V1.md`; no Qwen evidence. |
| C-02 | Clipboard state | Browser → Writer hyperlink; Browser URL selection/copy → Writer link dialog, while B copies/submits another URL | Set visible label `Reference link` to exact href A and save | Submit exact URL B in Browser exactly once | Saved ODF `<text:a>` label and `xlink:href` checked independently; Browser payload/revision and guard exact | Recopy Source A and replace hyperlink href | **Scripted Guest validated (one bounded run/control):** Solo A/B PASS, MA-ID joint PASS, naive MA-SD A fails/B passes with clipboard digest changing A→B before paste into Hyperlink URL field, recovery MA-SD joint PASS after recopy. Artifacts `c02-{soloa,solob,maid-r02,masd,masd-recovery}-20261001-r01` except MA-ID is `c02-maid-20261001-r02`. `c02-maid-...-r01` is an infrastructure-invalid attempt (wrong provider image), preserved and excluded. |
| A-01 | Application Context | One Chromium top-level window, two tabs/forms; switch page context inside same app | Submit the exact value to tab A | Submit the distinct exact value to tab B | Per-tab private submission/revision and tab-target event stream; stable top-level X11 window ID | Re-select own tab, observe, submit | **Scripted Guest validated**: Solo A/B, MA-ID, naive MA-SD and tab-recovery evidence in `MECHANISM_VALIDATION_ROUND1.md` / `WORKFLOW_SUITE_V2.md`; no Qwen evidence. Keep only as distinct from Focus while same-window/tab evidence remains reproducible. |
| A-02 | Selection / Active Object (reclassified; historical evidence retained) | One Chromium tab and URL; select in-page record → edit → commit | Change record A only | Change record B only | Per-record values/revisions, selected-record events; stable X11 window/tab/URL | Reselect own record, observe, commit | **Scripted Guest validated**: five bounded Guest runs (Solo A/B, MA-ID, naive MA-SD, recovery), with same window/tab/URL and a misapplied commit to B; see `WORKFLOW_SUITE_V2.md` A-02 report section. No Qwen evidence. |
| S-01 | Selection / Active Object | LibreOffice Calc, one sheet/document/window | Set B2 to `A-7319` | Set C3 to `B-2042` | Exact full-grid ODF oracle plus read-only UNO current-selection observation; preserve guard cells | Reobserve and explicitly reselect the intended cell, then finish | **Scripted and Qwen validated:** scripted Solo A/B and MA-ID pass, MA-SD exposure/failure, recovery pass; Qwen Solo A/B 2/2, MA-ID 2/2, MA-SD exposure 3/3 (1 joint failure, 2 recovered). See `FAMILY_EXPANSION_V1_REPORT.md`. |
| U-01 | Undo / Redo History | LibreOffice Calc, one sheet/document/window and document undo stack | Enter temporary `A-TEMP` in B2, then Undo once to restore `B2 seed` | Set C3 to `B-2042` | Exact full-grid ODF oracle; hidden observer snapshots B2/C3, window ID and clipboard digest around undo | Detect the reverted peer edit, reapply B goal, and restore A goal; verify both final cells | **Scripted and Qwen validated:** Solo A/B pass; MA-ID pass; MA-SD shared Undo exposure and failure; scripted recovery pass. Qwen Solo A/B 2/2, MA-ID 2/2 valid, MA-SD exposure/interference 2/2 with no recovery. See `FAMILY_EXPANSION_V1_REPORT.md`. |

| F-N1 | Focus / Input Routing | LibreOffice Writer ×2, distinct files and top-level windows | Replace doc-A with `A-FINAL-731` | Replace doc-B with `B-FINAL-204` | Path-bound saved FODT paragraphs and other-document integrity | A refocuses doc-A by window identity; B goal remains intact | **Prototype; real Guest Solo A/B PASS (one episode each)** (readiness, save, evaluator, fresh-Guest reset, ownership ledger). Solo B/MA-ID/MA-SD/recovery not run. See `MATRIX_WORKFLOW_IMPLEMENTATION_V1.md`. |
| C-N1 | Clipboard State | Chromium rich HTML table → Writer table; Browser URL copy/submit | Paste the exact 2×2 data table as Writer table structure | Copy and submit the assigned URL | ODF table row/cell structure and Browser exact URL/revision; clipboard X11 targets/digest | Reacquire table in Browser, recopy rich payload, paste in Writer | **Prototype; offline oracle only.** Guest MIME and rich-table round trip not verified; Solo/MA-ID/MA-SD/recovery not run. |
| A-N1 | Application Context | One Chromium window/tab, SPA route A/B | Submit route-A token | Submit route-B token | Route-keyed exact values/revisions and route-change event stream; same X11 window ID | Reopen route A, reobserve, submit | **Prototype; offline oracle only.** No Guest conditions run. |
| S-N1 | Selection / Active Object | One Writer document/window; exact text ranges | Bold only `ALPHA` | Bold only `BETA` | Saved ODF span styles, unchanged text/guard; read-only UNO selection snapshots | A reselects ALPHA before formatting; B reapplies its own range after exposure | **Prototype; offline oracle only.** UNO selection and real shared-range transition not Guest verified. |
| U-N1 | Undo / Redo History | One Writer document/window and undo stack | Make a temporary first-line edit, then Undo to restore seed | Change second line to `B-LINE: final` | Exact saved ODF paragraphs plus before/after history-state snapshots and unchanged guard | Restore A seed and reapply B's line after cross-Actor Undo | **Prototype; offline oracle only.** Writer Undo grouping and shared-history effect not Guest verified. |

## Counts and evidence boundary

- Historical inventory: **10 anchor templates** across 5 families, with A-02 reclassified (Focus 3, Clipboard 3, Application Context 1, Selection / Active Object 2, Undo / Redo History 1). The suite map now contains 15 IDs after five P1 additions (Focus 4, Clipboard 4, Application Context 2, Selection 3, Undo/Redo 2); this does not mean 15 validated templates.
- Fresh real-Guest C-02/F-02 controls this phase: 11 episode attempts, including one invalid C-02 MA-ID startup attempt. Ten valid runs completed with reset and provenance; C-02 MA-ID r02 is valid, r01 is retained as infrastructure invalid. All outcome counts above are per single episode, not aggregate performance claims.
- Scripted outcomes remain separate from model outcomes. Qwen family-level mechanism evidence now exists for F-01, C-01, A-01, S-01 and U-01; only F-01 is legacy evidence. The new families have model evidence only for their one Calc anchor each.
- Modal remains paused. No shared filesystem/backend mechanism is in V1 core. MA-ID and MA-SD task-relevant fixtures are equivalent; physical filesystem sharing is not a requirement.

## Task instance expansion gate

Use `TASK_INSTANCE_GENERATION_PLAN.md`. An instance must freeze meaningfully different task content, target objects, initial state and oracle under the same operation graph. Seed, filename, text token, layout, coordinates, schedule and repeats alone do not count. Generate only after a template's setup, Solo A/B, MA-ID, naive MA-SD, explicit recovery, reset and provenance controls pass. Start with three reviewed fixed instances per template and oracle positive/negative tests; then decide whether the remaining 25/template expansion is justified. The target 200–300 fixed instances remains a production plan; the bulk production batch has not been generated. Existing Task Factory candidates and anchor artifacts are not counted as hundreds of diverse workflows.

## Qwen pilot

The bounded family pilot results and limitations are recorded in `QWEN_FAMILY_PILOT_REPORT.md` (original three families) and `FAMILY_EXPANSION_V1_REPORT.md` (Selection and Undo History). Qwen3VLAgent + Qwen3-VL-30B-A3B remained fixed; A6000 hosted Guest/coordinator and the existing 4090 BF16 service handled inference. Per-condition repeats are small mechanism probes, not stable performance estimates.

## Reproduction and artifact index

Canonical code: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk` on branch `v0`. A6000 original C-02/F-02 artifacts: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-expansion-v1/`. Family-expansion artifacts: `artifacts/family-expansion/{selection,selection-qwen,undo-history,undo-history-qwen}/`. Each episode has `report.json`, `events.jsonl`, `provenance.json`, `resource-events.jsonl`, screenshots, saved final state and reset result. C-02/F-02 command form:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
scripts/run_browser_writer_workflows_v1.sh \
  --template C-02 --condition ma_sd --run-id UNIQUE_RUN_ID \
  --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-expansion-v1
```

Condition choices: `solo_a`, `solo_b`, `ma_id`, `ma_sd`; add `--recovery` only for explicit MA-SD recovery. Always use a new run ID. Use the wrapper: it sources `scripts/a6000_env.sh` and supplies the pinned A6000 provider/Guest paths. A direct invocation that omits that environment selects the wrong upstream default provider image and yields an invalid infrastructure timeout; the failed C-02 MA-ID attempt is retained as `c02-maid-20261001-r01`.


## P1 prototype gate status

`MATRIX_WORKFLOW_IMPLEMENTATION_V1.md` is the source of truth for the 5 P1 additions. Offline evaluator positive/negative controls and Python compilation passed. The single real Guest F-N1 Solo A result is valid but does not satisfy Solo A/B + MA-ID + MA-SD + recovery. A6000 host CPU pressure rose during the smoke, so additional Guest runs were paused. No Qwen smoke was run: 4090 SSH timed out; A6000 Qwen remains frozen. Therefore `MINIMAL_15_WORKFLOW_SUITE_READY` is **not established**.

## Benchmark production status (2026-10-03)

The V1 production candidate suite is materialized at `benchmarks/codesk_v1/`: 15 workflow templates × 40 fixed semantic profiles = 600 manifest rows; a separate `validation_45/` contains three offline hand-check instances per workflow, and `smoke_suite.jsonl` selects five representative rows. Generated rows preserve each workflow's current evidence level. F-N1 remains Guest Solo-only; C-N1/A-N1/S-N1/U-N1 remain offline/runtime-incomplete.

`INSTANCE_SCHEMA_V1.md`, `INSTANCE_GENERATION_V1.md`, and `INSTANCE_DIVERSITY_AUDIT.md` define the production contract. This does not retroactively satisfy the old full scripted validation gates. The generated evaluator is a normalized offline state oracle; Guest-specific app adapters are not registered. Consequently `run_benchmark.py --execute` fails closed: runtime adapters/reset/provenance validation remain before batch model execution. See `BATCH_RUNNER_V1.md` and `BENCHMARK_HANDOFF.md`.
