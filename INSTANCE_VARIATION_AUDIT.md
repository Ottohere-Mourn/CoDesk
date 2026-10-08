# Instance Variation Audit

## Scope and method

Updated audit after the bounded diversity refresh. The pre-refresh 11-workflow rows and their complete evaluator/fixture provenance are preserved under benchmarks/codesk_v1_final_history/pre_diversity_refresh_20261008/. The current final suite still contains 600 rows: 30 workflow IDs × 20 instances. Only the approved 11 workflows were regenerated; the other 19 manifest rows remain byte-identical.

For each workflow, I compared actor instructions and goal payloads; target object/entity IDs; source/destination roles; cell/range/route/section/selection profiles; fixture file sets and structure; domain/context and initial state; treatment/shared-state target; evaluator expected state; and operation/schedule metadata. Fixture byte hashes were not treated as diversity evidence by themselves. I compared JSON/HTML/XML/ODF structure with literal content values excluded where possible, and inspected the semantic profile fields. The fixture-shape count below is the number of distinct aggregate structural signatures across a workflow's public fixture files; it is evidence about structure, not a score of task quality.

**Legend:** I = distinct exact A+B goal-text pairs (includes changing values); T = distinct A/B target-object pairs; P = distinct meaningful profile/context classes; F = distinct aggregate fixture-structure signatures; IS = distinct evaluator initial-state records; X/E = distinct treatment-state / evaluator expected-state records. S→D describes source/destination variation. For the 11 refreshed workflows, context spans 4 domains × 5 rendered task-state profiles; all 30 workflows retain one operation graph and one schedule policy (Trace 1/1).

## Per-workflow audit

| Workflow | I / T / P | S→D | F | IS / X / E | Level and reason |
|---|---:|---|---:|---:|---|
| A-01 | 5 / 5 / 5 | — | 1 | 5 / 5 / 20 | **STATE_DIVERSE** — five tab/form contexts (inventory, release, review, safety, supplier) and four domain schemas; Browser fixture structure and two-submit trace stay fixed. |
| A-02 | 1 / 5 / 5 | — | 5 | 5 / 5 / 5 | **STATE_DIVERSE** — Browser record pages now vary table context and distractor count across supplier, asset, inspection, allocation and release layouts; selection/update operation is unchanged. |
| A-03 | 20 / 5 / 5 | — | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — paired Calc sheets vary used-range dimensions, occupied neighborhoods, headers and formula neighbors; target-cell edit remains fixed. |
| A-04 | 20 / 5 / 5 | — | 1 | 5 / 5 / 20 | **STATE_DIVERSE** — five filter/result contexts select different records and targets; the browser page structure and filter-edit-submit trace remain fixed. |
| A-05 | 20 / 5 / 5 | — | 6 | 20 / 5 / 20 | **STRUCTURALLY_DIVERSE** — five Writer section profiles change the target sections and document structure; the Navigator edit sequence is shared. |
| A-N1 | 1 / 5 / 5 | — | 1 | 5 / 5 / 20 | **STATE_DIVERSE** — five SPA route pairs and route-specific fields vary within one fixed browser fixture/route-edit graph. |
| C-01 | 20 / 5 / 5 | Writer→Calc; same plain-text copy/paste roles | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — source paragraphs carry different section/style context and Calc destinations vary among sparse, labeled, populated and formula-neighbor layouts; copy/paste graph is unchanged. |
| C-02 | 5 / 5 / 5 | 5 profiles; same Browser→Writer link transfer | 3 | 20 / 5 / 20 | **STATE_DIVERSE** — evidence/policy/reference/source/ticket link types and destination fields differ, but the semantic link-copy workflow remains the same. |
| C-03 | 5 / 5 / 5 | 5 range pairs; same Calc→Calc and Writer→Writer roles | 16 | 5 / 5 / 20 | **STRUCTURALLY_DIVERSE** — source/destination matrix dimensions span 2×2 through 3×3, changing actual range and workbook structure. |
| C-04 | 20 / 5 / 5 | 5 profiles; same Browser URL→Calc and Calc range-copy roles | 6 | 5 / 5 / 20 | **PARAMETRIC** — destination ranges move and URL payloads change, but range shape and two-part action graph stay fixed. |
| C-05 | 20 / 5 / 5 | 5 profiles; same Calc→Writer table and Writer→Writer roles | 20 | 5 / 5 / 20 | **STRUCTURALLY_DIVERSE** — Calc source and Writer destination table shapes vary across five 2×2–3×3 profiles, changing fixture structure. |
| C-06 | 20 / 5 / 5 | Terminal→Browser; same token transfer roles | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — terminal evidence appears as line, grouped, CSV, key/value or tree output with matched Browser result/distractor context; copy/search/paste graph is unchanged. |
| C-N1 | 20 / 1 / 5 | 5 table profiles; same Browser→Writer plus URL form roles | 15 | 5 / 5 / 20 | **STRUCTURALLY_DIVERSE** — rich HTML table dimensions vary from 2×2 to 4×2; the workflow tests table shape, not just text payload. |
| F-01 | 1 / 5 / 5 | — | 6 | 20 / 5 / 20 | **STATE_DIVERSE** — initial Writer files vary report/list/section/table context, while Calc neighborhoods vary density, formulas, subtotals and guard margins; full-document replace plus cell edit is unchanged. |
| F-02 | 5 / 5 / 5 | — | 5 | 20 / 5 / 20 | **STATE_DIVERSE** — five Writer comment anchors and Browser field pairs alter the task-relevant app state, with the same comment/form transaction graph. |
| F-04 | 17 / 5 / 5 | — | 19 | 20 / 5 / 20 | **STRUCTURALLY_DIVERSE** — Calc target ranges vary in location and 2×2/2×3 shape, with corresponding Writer content and fixture changes. |
| F-05 | 20 / 5 / 5 | — | 4 | 20 / 5 / 20 | **STATE_DIVERSE** — five phrase contexts and formula/value targets vary across domains; find/replace followed by formula entry is fixed. |
| F-06 | 20 / 5 / 5 | — | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — Browser form context and nearby dossier/record distractors vary with terminal artifact surroundings; two-field submit and command-edit execution remain the same. |
| F-07 | 20 / 5 / 5 | — | 4 | 20 / 5 / 20 | **STRUCTURALLY_DIVERSE** — formatting targets span heading/list/phrase/sentence/word contexts alongside a fixed 2×2 Calc fill; Writer target structure differs. |
| F-N1 | 1 / 5 / 5 | — | 3 | 20 / 5 / 20 | **STATE_DIVERSE** — five semantic paragraph targets (action/decision/owner/status/summary) change the two-document content state; edit sequence is fixed. |
| S-01 | 1 / 5 / 5 | — | 6 | 6 / 1 / 20 | **STATE_DIVERSE** — selection targets sit in sparse, dense, formula-bearing, boundary and subtotal neighborhoods; coordinate changes are not the diversity basis. |
| S-02 | 20 / 5 / 5 | — | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — fixed 2×3 target rectangles now occur in isolated, dense, formula-edge, header-boundary and subtotal/guard workbook contexts. |
| S-03 | 20 / 5 / 5 | — | 4 | 20 / 5 / 20 | **STATE_DIVERSE** — selected text contexts cover alpha/code/date/name/title content, while both actors use the same select-and-replace procedure. |
| S-04 | 20 / 5 / 5 | — | 5 | 5 / 5 / 20 | **STATE_DIVERSE** — the live multirow table varies from compact to 11-row vendor/priority/inventory/release contexts, with additional selectable distractors preserved in initial state. |
| S-N1 | 1 / 5 / 5 | — | 14 | 5 / 5 / 5 | **STRUCTURALLY_DIVERSE** — target ranges differ by heading/list-item/phrase/sentence/word structure; the formatting action itself is constant. |
| U-01 | 5 / 5 / 5 | — | 16 | 5 / 5 / 5 | **STATE_DIVERSE** — audit/formula/inventory/release/status profiles change edited cell state and history entries; the commit-then-undo sequence remains fixed. |
| U-02 | 4 / 5 / 5 | — | 4 | 20 / 5 / 20 | **STATE_DIVERSE** — style target/content profiles differ across documents, while the temporary-style/peer-edit/undo interaction graph is constant. |
| U-03 | 5 / 5 / 5 | — | 5 | 5 / 5 / 5 | **STATE_DIVERSE** — formula/value edits occur in sparse, dense, cross-column, blank-gap and guarded reconciliation neighborhoods; edit→peer edit→undo recovery stays fixed. |
| U-04 | 4 / 5 / 5 | — | 1 | 5 / 5 / 20 | **STATE_DIVERSE** — five editor/business contexts and phrase payloads vary; rich-editor structure and shared undo sequence are fixed. |
| U-N1 | 5 / 5 / 5 | — | 5 | 5 / 1 / 5 | **STATE_DIVERSE** — the same target paragraphs are embedded in named sections and receive distinct body/list/decision/quote/mixed paragraph styles; replacement/peer edit/undo graph stays fixed. |

## Findings

### 1. Are any 20-instance sets lexical-only?

No workflow is classified strictly LEXICAL_ONLY. No refreshed target remains primarily lexical/coordinate variation. One untouched workflow, C-04, remains PARAMETRIC; the other 18 untouched workflow classifications are unchanged from the prior audit.

### 2. Nominal 20-task sets with low effective diversity

- The 11 refreshed workflows now each have five rendered task-state/context profiles crossed with four domains. Static fixture-shape comparison finds 5–6 distinct aggregate shapes per workflow, with operation graph and schedule fixed.
- Coordinate/range variation remains part of some instance definitions, but refreshed S-01, S-02 and F-01 also vary surrounding spreadsheet/document state; C-04 remains the main position-heavy legacy case.
- **Clear structural coverage:** C-03, C-05, C-N1, F-04, A-05 and S-N1 retain their existing matrix/table/range/section diversity. The 11 refreshed workflows additionally show five distinct task-state fixture contexts each, while keeping one operation graph.

### 3. Release implications

The suite has 600 fixed instances across 30 workflows. The 11 previously low-diversity workflows now reach STATE_DIVERSE through task-relevant fixture/context variation; their operation traces remain unchanged. This is 30 workflow templates × 20 fixed instances, not 600 workflows. No Guest solvability or model robustness is established by this static/offline refresh.

Static fixture signatures support variation in initial state/context; they do not establish real-GUI solvability, model difficulty or improved model behavior.

## Diversity refresh validation

- Final manifest: **600 fixed instances / 30 workflows / 20 per workflow**.
- Regenerated only: A-02, A-03, C-01, C-06, F-01, F-06, S-01, S-02, S-04, U-03, U-N1 (**220 new instance IDs**).
- Old 220 target rows, instance manifests, evaluator files, fixture files, workflow definitions and compiled plans are preserved in benchmarks/codesk_v1_final_history/pre_diversity_refresh_20261008/. Snapshot metadata records the base manifest SHA-256 and old IDs/hashes.
- The other 19 workflow manifest rows are byte-identical to the pre-refresh manifest. Workflow operation graph and schedule policy IDs are unchanged for all 11 refreshed workflows.
- Each refreshed workflow has 5 unique explicit context profiles; all 20 semantic signatures and fixture hashes are unique. An independent fixture-shape pass found 5–6 shapes per workflow.
- Full offline audit: positive oracle **600/600**, negative oracle **600/600**, fixture files **1,760** hash/size checks, evaluator files **600** hash checks, exact duplicates **0**, near duplicates **0**.
- Deterministic regeneration: all 220 target instance IDs, manifest entry hashes, signatures and fixture hashes reproduced exactly. Full runtime-plan compilation: **600 compiled, 0 failed**; all 220 affected plans reproduce byte-for-byte and all 380 non-target plans remain byte-identical to the pre-refresh version.
- Offline pytest: **209 passed**. No Guest or Qwen was started; these checks do not establish real-GUI solvability.
- Current manifest SHA-256: d31d44eab41b6c263459ccc9cd5f2fd80f676d9d3957747a24bac642e7d53642.

The diversity labels describe differences in fixed initial task context and fixture structure. They do not imply 11 different operation workflows, real-agent robustness, or new interaction mechanisms.
