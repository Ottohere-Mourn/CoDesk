# CoDesk case portfolio ? consolidated branch handoff

Date: 2026-11-13
Branch: `codex/all-codesk-cases-20261113`
Remote: `git@github.com:Ottohere-Mourn/CoDesk.git`
Scope: case definitions, fixtures, app/runner code, tests and result summaries from the 13-case dual-agent portfolio, the Human-Agent scripted-normal-user extension, and the 2026-11-12/13 additional dual-agent pilot branch.

## Executive counts

There are **19 one-time dual-agent cases** with an effective result satisfying the core tuple `MA-ID/Independent PASS + Shared FAIL + Shared+Lock FAIL`, after applying the original handoff's validity and quality audit. This is a pilot-screening count, not repeatability or probability evidence.

Separately, **7 Human-Agent normal-user cases** have one effective natural-Shared observation in which User fails while the real GUI Agent passes, with passing controls as detailed below. One additional Human-Agent case (HA-MAIL) has the same impact only under a deliberately fixed 25-second start-offset probe; it is not counted as a natural-shared case. These two actor compositions are complementary and should not be mixed into one statistical denominator.

Therefore, at the **case-task pilot level**, the merged portfolio contains **26 cases with a one-time qualifying observation under their track-specific criterion** (19 dual-agent + 7 Human-Agent natural impact), plus 1 separately reported controlled Human-Agent probe. The repo contains more than 26 designed/implemented workflows: not every inventory item has full valid experiment evidence, and some have overlapping underlying mechanisms. No case has a second valid triplet/repeat required by this handoff.

## 1. Core dual-agent cases: 19 rostered, 14+5 qualified once

### Earlier 19-case portfolio

The branch `codex/13-case-handoff-20261104` handoff contains a 19-workflow roster and reports 14 cases meeting the strict one-time tuple:

1. Case 3 ? VS Code repair + browser retest, cross-window input misrouting.
2. C-03 Clipboard ? shared clipboard payload overwrite.
3. A-01 Application Context ? stale Enter in a non-target browser tab.
4. S-01 Selection / Active Object ? stale input after shared active-cell/object change.
5. U-01 Undo/Redo ? shared undo history.
6. CWD-1 ? shared terminal working-directory drift.
7. VIEW-1 ? shared viewport/scroll offset and stale screen coordinates.
8. AUTH-1 ? shared active reviewer/submitter identity.
9. PAY-1 ? a completed payment uses a stale timesheet snapshot.
10. DATA-REL1 ? staging export goes stale after a dataset-policy revision.
11. W1 Warehouse Receiving v0.2.7 ? QA clipboard text overwrites a held-lot reference.
12. AP-1 Remittance v0.2.1 ? a credit memo makes a ready payment draft stale.
13. SITEACT-STATE1 ? readiness snapshot remains stale after a HOLD/deviation update.
14. CRM-LU1 ? a legacy full-record form overwrites a billing email update.

The remaining five roster items are not counted: Case 2 is a neutral all-pass control; Case 4 did not meet the tuple (its effective lock arm passed); F-01 lacks a normal Shared business failure; EDIT-1 has dirty terminal attribution; FIND-1 lacks a matched valid baseline/evaluator. Full definitions, run IDs, and boundaries: [`13-case handoff`](handoff/13-case-handoff/HANDOFF.md), [`QUALIFIED_CASE_AUDIT_20261108.md`](handoff/13-case-handoff/QUALIFIED_CASE_AUDIT_20261108.md).

### Latest dual-agent candidate screen

The `three-new-dualagent-cases` branch has an 11-item active/replacement roster. Five have one effective tuple-quality hit (not repeated):

- VIDEO-REVIEW1 ? shared video/storyboard frame cursor and worklist.
- COMMUNITY-PANTRY1 ? pantry allocation workflow.
- LIBRARY-ROOM1 ? community-room booking plus safety closure.
- AP-CLIPBOARD1 ? invoice/reimbursement reference handoff.
- EXAM-ACCESS1 ? approved exam accommodations and seating.

Six are deliberately not counted: S1 SHELTER-INTAKE1 and K2 ROUTE-RECON1 have mutually incompatible terminal goals; K1 COURT-SERVICE1 is all-pass; Q1 ROUTE-LIVE1 has a tuple-shaped failure but the audited failure mechanism does not match the intended route-state claim; E1 EDIT-MODE1 is recovered by Shared+Lock; V2 WAREHOUSE-LABEL1 is all-pass. Preserve their raw outcomes as no-go/controls. V5 lacks direct clipboard-overwrite telemetry; V6 has accommodation-source wording caveats. See [`three-new-case handoff`](../docs/codesk/THREE_NEW_CASES_HANDOFF_20261112_ZH.md) and each `tasks/paragui/*MODEL_RESULTS*` report.

**Core tuple total: 14 + 5 = 19** one-time qualifying case tasks. This is not 19 independent mechanisms: clipboard variants and stale-artifact/lost-update workflows cluster by mechanism family (e.g., PAY-1 / DATA-REL1 / AP-1 / SITEACT-STATE1 / CRM-LU1).

## 2. Human-Agent normal-user extension

Track definition: Actor A is the real Codex GUI Agent; Actor B is a deterministic scripted normal-user actor with its own task and Oracle. These are separate offline app fixtures. User-only/Agent-only/Independent controls are required; natural Shared results and fixed-schedule mechanism probes are kept separate. The User scripts are open-loop, so they do not provide a measured autonomous recovery strategy.

### Seven natural Shared user-impact pilots

1. **HA-TRIAGE** ? agent reviews ticket/order/policy evidence; user saves a follow-up on another ticket.
2. **HA-PO-ARCHIVE** ? agent reviews purchase-order evidence; user downloads and archives a delivery CSV.
3. **HA-CALENDAR** ? agent drafts a team meeting; user adds a focus block.
4. **EDU-Grade** ? agent prepares rubric-based grading drafts; user records attendance.
5. **Media Library** ? agent assembles a licensed-material collection; user edits and verifies asset metadata.
6. **Facilities WO** ? agent drafts an HVAC maintenance work order; user reports/reserves a projector repair.
7. **Community Garden** ? agent prepares a planting draft; user reads soil data and records watering.

Each has at least one valid User-only/Agent-only/Independent positive control and a natural Shared User FAIL / Agent PASS pilot, except Volunteer Ops v0.2, whose User and Agent both fail under Shared and therefore is not included in these seven.

**Separate controlled probe:** HA-MAIL has a qualifying Shared user-impact result only in a fixed 25-second start-offset probe; its natural Shared run passed both actors. Do not describe HA-MAIL as a natural shared-failure case.

The broader Human-Agent branch contains 17 task-family/app/workflow entries according to its case inventory, but that is not 17 validated Shared-failure results. Other implemented/piloted items include HA-INVENTORY (no qualifying natural user harm) and Code Review / Access Review / Transit Itinerary (some missing current-version Independent controls or Shared outcomes where the Agent also fails). The Linux casebook's five mechanism sketches also overlap thematically with the earlier focus/clipboard/selection/undo families; they are not five extra validated Human-Agent cases.

Primary evidence summaries: [`4-case handoff`](HUMAN_AGENT_4_CASES_HANDOFF_20261111_ZH.md), [`Next-5 validation`](HUMAN_AGENT_NEXT5_VALIDATION_20261112_ZH.md), [`3 new workflows handoff`](HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md), [`Linux casebook`](HUMAN_AGENT_CASEBOOK_LINUX_V1_20261109.md).

## 3. Earlier Case 2/3/4 and five mechanisms

- **Case 2**: service-ticket / review / refund case. The handoffed v1.2 triplet is all-pass and useful as a neutral control; it is not a qualifying shared-fail case.
- **Case 3**: VS Code repair + browser retest; the qualifying v1.4.3 task is the successful case in the 2/3/4 group.
- **Case 4**: Kdenlive timeline + VS Code checklist; preserve its effective lock-PASS evidence and its invalid/evaluator/UI failures; do not promote it into the qualifying tuple.
- Early mechanisms: Focus/Input Routing (F-01), Clipboard (C-03), Application Context (A-01), Selection (S-01), and Undo/Redo (U-01). Only four in that handoff-qualified roster have the strict tuple; F-01 does not.

Current branch consolidation does not rewrite any original result or re-adjudicate a failed task into a pass. Case 2/3/4 definitions and historical reports remain grouped under `case234/` and `docs/handoff/`; mechanism design and evidence remain under the mechanism folders and evidence manifests.

## 4. Branch provenance and included sources

This branch combines the following remote lines of work (source branches remain unchanged):

- `codex/13-case-handoff-20261104` ? the 19-case handoff and its ancestors (Case 2, prior hardening, candidate-repair/mechanism work referenced by that handoff).
- `codex/human-agent-normal-user-v1-20261109` ? Human-Agent code, fixtures, 17-family inventory, pilots and reports.
- `codex/three-new-dualagent-cases-20261112` ? latest 11-item dual-agent replacement roster and pilots.
- The Case 3/Case 4 source branches are checked separately in the aggregate tree where present; their original artifacts remain linked in the Case 2/3/4 handoffs.

Other branches inspected include `codex/candidate-repair-20261104`, `codex/focus-clipboard-pilot-20261102`, `codex/case3-followup`, `codex/case4-hardening`, and older Case2/3/4 work. Ancestor branches already represented in the 13-case tree are not re-merged as independent work. This list will be finalized after the remaining Case 3/4 source imports.

## 5. What is and is not in Git; usage

Git contains source, task cards, fixture builders, app/oracle code, tests, summaries, and run IDs. Large raw Guest overlays, screenshots, and full model traces remain in HealthCare RAID locations named in the source handoffs; they are not silently discarded or copied wholesale into Git. API keys are not included.

### Clone / test

```bash
git clone --branch codex/all-codesk-cases-20261113 git@github.com:Ottohere-Mourn/CoDesk.git
# configure OSWorld_DIR/OSWORLD_PYTHON, SWCUB_SAFETY_ROOT, Guest image/runtime, RAID run output
python -m pytest -q
```

On HealthCare, the case wrappers in `infra/run_human_agent_*.sh` expect `OSWORLD_DIR`, its Python environment, a `swcub.resource_safety` provider through `SWCUB_SAFETY_ROOT`, the existing OSWorld Guest image/runtime, RAID output, and runtime-injected model credentials. Case scripts are not a single universal CLI; check the case's handoff before running it. Never store API keys in source, arguments, logs, or run artifacts. Do not start model/Guest runs as part of merely cloning/testing.

### Main source handoffs

- `docs/handoff/13-case-handoff/HANDOFF.md` ? original 19-case dual-agent portfolio and criteria.
- `docs/HUMAN_AGENT_4_CASES_HANDOFF_20261111_ZH.md`, `docs/HUMAN_AGENT_NEXT5_VALIDATION_20261112_ZH.md`, `docs/HUMAN_AGENT_3_NEW_CASES_HANDOFF_20261111_ZH.md` ? Human-Agent task families and pilot evidence.
- `docs/codesk/THREE_NEW_CASES_HANDOFF_20261112_ZH.md` ? latest dual-agent roster, audited no-go outcomes, and candidate results.

Use one-time tuples as screening evidence only. There are no repeat runs sufficient for confidence intervals or failure-rate claims. Keep workflow novelty distinct from underlying mechanism novelty.
