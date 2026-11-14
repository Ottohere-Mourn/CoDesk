# CoDesk case portfolio — consolidated branch handoff

Date: 2026-11-14 (updated with V11–V12)
Branch: `codex/all-codesk-cases-20261113`
Remote: `git@github.com:Ottohere-Mourn/CoDesk.git`
Scope: case definitions, fixtures, app/runner code, tests and result summaries from the 13-case dual-agent portfolio, the Human-Agent scripted-normal-user extension, and the 2026-11-12/13/14 additional dual-agent pilot branches, including the V7–V12 additions.

## Executive counts

There are **25 one-time dual-agent cases** with an effective result satisfying the core tuple `MA-ID/Independent PASS + Shared FAIL + Shared+Lock FAIL`, after applying the original handoff's validity and quality audit. This is a one-time score-pattern screening count (14 earlier 13-case-handoff cases + 5 latest candidate-screen cases + 4 V7–V10 pilots + 2 V11–V12 pilots), not repeatability or probability evidence. V7–V12 are workflow-level variants of shared active-work-area/panel context; runs include Agent-visible observations and Oracle scores, but no independent semantic panel-transition telemetry.

Separately, **7 Human-Agent normal-user cases** have one effective natural-Shared observation in which User fails while the real GUI Agent passes, with passing controls as detailed below. One additional Human-Agent case (HA-MAIL) has the same impact only under a deliberately fixed 25-second start-offset probe; it is not counted as a natural-shared case. These two actor compositions are complementary and should not be mixed into one statistical denominator.

Therefore, at the **case-task pilot level**, the merged portfolio contains **32 cases with a one-time qualifying observation under their track-specific criterion** (25 dual-agent + 7 Human-Agent natural impact), plus 1 separately reported controlled Human-Agent probe. The repo contains 53 rostered workflow entries across the two tracks: not every inventory item has full valid experiment evidence, and some have overlapping underlying mechanisms. No case has a second valid triplet/repeat required by this handoff.

## 1. Core dual-agent cases: 36 rostered, 14+5+4+2=25 qualified once

### Earlier 19-case portfolio

The branch `codex/13-case-handoff-20261104` handoff contains a 19-workflow roster and reports 14 cases meeting the strict one-time tuple:

1. Case 3 — VS Code repair + browser retest, cross-window input misrouting.
2. C-03 Clipboard — shared clipboard payload overwrite.
3. A-01 Application Context — stale Enter in a non-target browser tab.
4. S-01 Selection / Active Object — stale input after shared active-cell/object change.
5. U-01 Undo/Redo — shared undo history.
6. CWD-1 — shared terminal working-directory drift.
7. VIEW-1 — shared viewport/scroll offset and stale screen coordinates.
8. AUTH-1 — shared active reviewer/submitter identity.
9. PAY-1 — a completed payment uses a stale timesheet snapshot.
10. DATA-REL1 — staging export goes stale after a dataset-policy revision.
11. W1 Warehouse Receiving v0.2.7 — QA clipboard text overwrites a held-lot reference.
12. AP-1 Remittance v0.2.1 — a credit memo makes a ready payment draft stale.
13. SITEACT-STATE1 — readiness snapshot remains stale after a HOLD/deviation update.
14. CRM-LU1 — a legacy full-record form overwrites a billing email update.

The remaining five roster items are not counted: Case 2 is a neutral all-pass control; Case 4 did not meet the tuple (its effective lock arm passed); F-01 lacks a normal Shared business failure; EDIT-1 has dirty terminal attribution; FIND-1 lacks a matched valid baseline/evaluator. Full definitions, run IDs, and boundaries: [`13-case handoff`](handoff/13-case-handoff/HANDOFF.md), [`QUALIFIED_CASE_AUDIT_20261108.md`](handoff/13-case-handoff/QUALIFIED_CASE_AUDIT_20261108.md).

### Latest dual-agent candidate screen

The `three-new-dualagent-cases` branch has an 11-item active/replacement roster. Five have one effective tuple-quality hit (not repeated):

- VIDEO-REVIEW1 — shared video/storyboard frame cursor and worklist.
- COMMUNITY-PANTRY1 — pantry allocation workflow.
- LIBRARY-ROOM1 — community-room booking plus safety closure.
- AP-CLIPBOARD1 — invoice/reimbursement reference handoff.
- EXAM-ACCESS1 — approved exam accommodations and seating.

Six are deliberately not counted: S1 SHELTER-INTAKE1 and K2 ROUTE-RECON1 have mutually incompatible terminal goals; K1 COURT-SERVICE1 is all-pass; Q1 ROUTE-LIVE1 has a tuple-shaped failure but the audited failure mechanism does not match the intended route-state claim; E1 EDIT-MODE1 is recovered by Shared+Lock; V2 WAREHOUSE-LABEL1 is all-pass. Preserve their raw outcomes as no-go/controls. V5 lacks direct clipboard-overwrite telemetry; V6 has accommodation-source wording caveats. See [`three-new-case handoff`](../docs/codesk/THREE_NEW_CASES_HANDOFF_20261112_ZH.md) and each `tasks/paragui/*MODEL_RESULTS*` report.

### Four appended workflows: V7–V10

On this aggregate branch, four additional workflows were implemented and each received one MA-ID / Shared / Shared+Lock GPT-6-Sol GUI triplet. All four had MA-ID=1/1, at least one Shared task fail, and at least one Shared+Lock task fail. They add workflow coverage—not four new mechanisms: all use the existing shared active-work-area/form-context family. V9 Shared+Lock also hit the 60-GUI-call ceiling with one of three parts records unfinished, a budget confound. See [cards](FOUR_NEW_DUALAGENT_CASES_V7_V10_20261113_ZH.md) and [full model results](../tasks/paragui/V7_V10_MODEL_RESULTS_20261113_ZH.md).

- V7 LAB-WATER1 — custody intake / bench results.
- V8 CITY-PERMIT1 — permit review-routing / fee receipts.
- V9 FIELD-SERVICE1 — technician scheduling / parts reservation.
- V10 CARE-TRANSITION1 — discharge follow-up plans / equipment dispatch.

### Two appended workflows: V11–V12

V11–V12 each received one valid GPT-6-Sol MA-ID / Shared / Shared+Lock triplet after passing a scripted Guest joint positive control. Both satisfy the same one-time score-pattern tuple. They add library-circulation and synthetic civic-records workflows, not new underlying mechanisms: both expose the existing shared active-panel/current-record family. V12 Shared+Lock has a budget caveat: Review scored 1.0 but used all 60 GUI calls (max_steps); Intake scored 0.0 after reporting that the UI switched away from its panel. The lock-arm tuple is met by Intake’s Oracle failure, not by the other Actor’s budget status. First V11 Shared and first V12 lock attempts had SSH/API transport failures and are explicitly invalid, not counted. See [V11–V12 cards](TWO_NEW_DUALAGENT_CASES_V11_V12_20261114_ZH.md) and [full results](../tasks/paragui/V11_V12_MODEL_RESULTS_20261114_ZH.md).

- V11 LIBRARY-CIRCULATION1 — pending holds / returned-copy processing.
- V12 CIVIC-RECORDS1 — synthetic disclosure review / intake and custody log.

**Core tuple total: 14 + 5 + 4 + 2 = 25** one-time qualifying case tasks. This is not 25 independent mechanisms: clipboard variants and stale-artifact/lost-update workflows cluster by mechanism family (e.g., PAY-1 / DATA-REL1 / AP-1 / SITEACT-STATE1 / CRM-LU1).

## 2. Human-Agent normal-user extension

Track definition: Actor A is the real Codex GUI Agent; Actor B is a deterministic scripted normal-user actor with its own task and Oracle. These are separate offline app fixtures. User-only/Agent-only/Independent controls are required; natural Shared results and fixed-schedule mechanism probes are kept separate. The User scripts are open-loop, so they do not provide a measured autonomous recovery strategy.

### Seven natural Shared user-impact pilots

1. **HA-TRIAGE** — agent reviews ticket/order/policy evidence; user saves a follow-up on another ticket.
2. **HA-PO-ARCHIVE** — agent reviews purchase-order evidence; user downloads and archives a delivery CSV.
3. **HA-CALENDAR** — agent drafts a team meeting; user adds a focus block.
4. **EDU-Grade** — agent prepares rubric-based grading drafts; user records attendance.
5. **Media Library** — agent assembles a licensed-material collection; user edits and verifies asset metadata.
6. **Facilities WO** — agent drafts an HVAC maintenance work order; user reports/reserves a projector repair.
7. **Community Garden** — agent prepares a planting draft; user reads soil data and records watering.

Each has at least one valid User-only/Agent-only/Independent positive control and a natural Shared User FAIL / Agent PASS pilot, except Volunteer Ops v0.2, whose User and Agent both fail under Shared and therefore is not included in these seven.

**Separate controlled probe:** HA-MAIL has a qualifying Shared user-impact result only in a fixed 25-second start-offset probe; its natural Shared run passed both actors. Do not describe HA-MAIL as a natural shared-failure case.

The broader Human-Agent branch contains 17 task-family/app/workflow entries according to its case inventory, but that is not 17 validated Shared-failure results. Other implemented/piloted items include HA-INVENTORY (no qualifying natural user harm) and Code Review / Access Review / Transit Itinerary (some missing current-version Independent controls or Shared outcomes where the Agent also fails). The Linux casebook's five mechanism sketches also overlap thematically with the earlier focus/clipboard/selection/undo families; they are not five extra validated Human-Agent cases.

Primary evidence summaries: [`4-case handoff`](HUMAN_AGENT_4_CASES_HANDOFF_20261111_ZH.md), [`Next-5 validation`](HUMAN_AGENT_NEXT5_VALIDATION_20261112_ZH.md), [`3 new workflows handoff`](HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md), [`Linux casebook`](HUMAN_AGENT_CASEBOOK_LINUX_V1_20261109.md).

## 3. Earlier Case 2/3/4 and five mechanisms

- **Case 2**: service-ticket / review / refund case. The handoffed v1.2 triplet is all-pass and useful as a neutral control; it is not a qualifying shared-fail case.
- **Case 3**: VS Code repair + browser retest; the qualifying v1.4.3 task is the successful case in the 2/3/4 group.
- **Case 4**: Kdenlive timeline + VS Code checklist; preserve its effective lock-PASS evidence and its invalid/evaluator/UI failures; do not promote it into the qualifying tuple.
- Early mechanisms: Focus/Input Routing (F-01), Clipboard (C-03), Application Context (A-01), Selection (S-01), and Undo/Redo (U-01). Only four in that handoff-qualified roster have the strict tuple; F-01 does not.

当前聚合分支不改写原始结果，也不把失败重判为通过。Case 2/3/4 的卡片保存在 `docs/handoff/13-case-handoff/case234/`；Case 2 业务实现位于 `oscombo/collab/ticket_to_resolution/`，Case 3 Lite 代码位于 `oscombo/collab/build_and_verify_lite_v1/`，Case 4 Lite 代码位于 `oscombo/collab/timeline_and_assets_lite_v1/`。Case 3/4 的旧审计报告、Guest 脚本和核心 Fixture 已从各自 hardening/follow-up refs 选择性导入；大体积原始 Guest run artifacts 仍保存在 HealthCare RAID 路径，不在 Git 中。

## 4. Branch provenance and included sources

This branch combines the following remote lines of work (source branches remain unchanged):

- `codex/13-case-handoff-20261104` — the 19-case handoff and its ancestors (Case 2, prior hardening, candidate-repair/mechanism work referenced by that handoff).
- `codex/human-agent-normal-user-v1-20261109` — Human-Agent code, fixtures, 17-family inventory, pilots and reports.
- `codex/three-new-dualagent-cases-20261112` — latest 11-item dual-agent replacement roster and pilots.
- `codex/case3-followup` 与 `codex/case4-hardening`：不是聚合分支的祖先；已将最新 handoff 所引用的 Case 3/4 Lite task package、Oracle、Fixture、runner、tests 与短审计报告按文件快照导入（不合并全部历史 screenshots/raw evidence）。
- `codex/case2-v12`、`case2-hardening`、`case2-healthcare`、`overnight-cases-2-4`：均为 `13-case-handoff` 的祖先，因此随其历史和文件进入聚合分支。
- `codex/case3-lite`、`case4-lite`：不是祖先；其有效代码快照已由后续 `case3-followup` / `case4-hardening` 版本覆盖并随上项导入，不作为额外工作流重复计数。
- `codex/candidate-repair-20261104`、`codex/focus-clipboard-pilot-20261102`：未并入 Git 历史；其早期候选/机制材料在 13-case handoff 的最终 roster、task cards 与 audit 中有后续版本。本分支不把早期重复版本追加计数。
- 远端还看到 `prep/codesk-v1-handoff`、`yuke-osworld`、`collab-cases`、`lyw-dev`、`v0` 等分支：分别是早期 600-instance 基准、队友/早期协作线或历史版本，不属于本轮“我们设计并验证的这批 case”清单，未合并到本聚合分支。

### Aggregate inventory versus usable count

- Dual-Agent: 19 workflows from the 13-case handoff (14 strict tuple hits) + 11 entries in the latest pilot screen (5 strict tuple hits) + 4 V7–V10 additions (4 one-time tuple hits) + 2 V11–V12 additions (2 one-time tuple hits) = 36 rostered attempts, 25 one-time qualified.
- Human-Agent: 17 task-family/app/workflow inventory entries, 7 one-time natural Shared user-impact hits and 1 separately controlled-offset-only probe.
- Across the tracks this is 53 rostered entries, **32 case-workflow pilots with a qualifying one-time observation**, plus the separate HA-MAIL controlled probe. This is not 32 repeated/reliable cases and not one pooled metric. The remaining 21 rostered entries do not meet their track’s main one-time criterion; they remain neutral, invalid, no-go, incomplete, or otherwise not qualified. HA-MAIL’s controlled-offset probe is reported separately. See the linked audits rather than silently dropping outcomes.

## 5. What is and is not in Git; usage

Git contains source, task cards, fixture builders, app/oracle code, tests, summaries, and run IDs. Large raw Guest overlays, screenshots, and full model traces remain in HealthCare RAID locations named in the source handoffs; they are not silently discarded or copied wholesale into Git. API keys are not included.

### Clone / test

```bash
git clone --branch codex/all-codesk-cases-20261113 git@github.com:Ottohere-Mourn/CoDesk.git
# configure OSWorld_DIR/OSWORLD_PYTHON, SWCUB_SAFETY_ROOT, Guest image/runtime, RAID run output
python -m pytest -q
```

On HealthCare, the case wrappers in `infra/run_human_agent_*.sh` expect `OSWORLD_DIR`, its Python environment, a `swcub.resource_safety` provider through `SWCUB_SAFETY_ROOT`, the existing OSWorld Guest image/runtime, RAID output, and runtime-injected model credentials. Case scripts are not a single universal CLI; check the case's handoff before running it. Never store API keys in source, arguments, logs, or run artifacts. Do not start model/Guest runs as part of merely cloning/testing.

Earlier consolidation baseline: the focused harness/Human-Agent/runner suite passed 52 tests; after importing the Case 3/4 Lite packages, their focused tests passed 15/15. A complete suite run before the Lite import reported 409 passed, 1 skipped, and 3 failed in `tests/test_ticket_to_resolution.py`; its positive-path tests do not produce all the newer audit/provenance evidence required by the strict oracle. Therefore the full suite is not green. At the original consolidation snapshot, no model or Guest experiment was started. The later V7–V10 addition passed its focused 21-test Oracle/control suite and four scripted Guest joint positive controls; its 12 one-shot model runs are recorded in the linked results report. The V11–V12 follow-up passed the focused Oracle/reference-control suite (27 tests) and two scripted Guest joint positives; both one-shot model triplets met the screening tuple, with V12 Shared+Lock’s 60-call/max_steps caveat and invalid transport attempts documented separately.

### Main source handoffs

- `docs/handoff/13-case-handoff/HANDOFF.md` — original 19-case dual-agent portfolio and criteria.
- `docs/HUMAN_AGENT_4_CASES_HANDOFF_20261111_ZH.md`, `docs/HUMAN_AGENT_NEXT5_VALIDATION_20261112_ZH.md`, `docs/HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md` — Human-Agent task families and pilot evidence.
- `docs/codesk/THREE_NEW_CASES_HANDOFF_20261112_ZH.md` — latest dual-agent roster, audited no-go outcomes, and candidate results.
- `docs/FOUR_NEW_DUALAGENT_CASES_V7_V10_20261113_ZH.md` and `tasks/paragui/V7_V10_MODEL_RESULTS_20261113_ZH.md` — V7–V10 cards and their one-shot model triplets.
- docs/TWO_NEW_DUALAGENT_CASES_V11_V12_20261114_ZH.md and tasks/paragui/V11_V12_MODEL_RESULTS_20261114_ZH.md — V11–V12 task cards, validity notes and one-shot model triplets.

Use one-time tuples as screening evidence only. There are no repeat runs sufficient for confidence intervals or failure-rate claims. Keep workflow novelty distinct from underlying mechanism novelty.
