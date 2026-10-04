# Matrix Workflow Implementation V1

Date: 2026-10-03
Canonical repository: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`, branch `v0`.
Baseline commit before this work: `4faf56e4cdc406ac6b06c9e6d94a9b7775f20eea`.

## Decision

The five-family scope is unchanged. Five additional workflow IDs now have deterministic fixture contracts, actor procedures, private evaluators, reset/provenance wiring, and a single-worker Guest runner. Offline evaluator positive/negative controls passed. Only **F-N1 Solo A and Solo B** reached real Guests in this round. Therefore this round does **not** establish `MINIMAL_15_WORKFLOW_SUITE_READY`; the additional workflows remain prototype candidates, and instance-schema design should wait for their scripted gates.

## Implemented task contracts

| ID | Family | Actor A goal | Actor B goal | Shared state and workflow | Oracle / contamination guard | Recovery |
|---|---|---|---|---|---|---|
| F-N1 | Focus / Input Routing | Replace `doc-a.fodt` paragraph with `A-FINAL-731`. | Replace `doc-b.fodt` paragraph with `B-FINAL-204`. | Two distinct Writer top-level windows; B edits doc B between A's observation and resume. | Parse saved FODT by file path; require each target value and exact peer draft/goal depending condition. | A explicitly reactivates doc A; B reasserts its independent target. |
| C-N1 | Clipboard State | Copy the Browser HTML table into Writer as a real table. | Copy the assigned URL from Browser and submit it. | X11 clipboard owner/payload changes from rich table to URL before A pastes. | ODF table row/cell matrix, Writer guard, Browser URL/revision, X11 target list and payload digest. | A recopies table from Browser and replaces the Writer target. |
| A-N1 | Application Context | Submit `A-READY-531` to SPA route A. | Submit `B-APPROVE-824` to SPA route B. | Same Chromium window and tab; B changes History API route while A's earlier form action is pending. | Route-keyed private values/revisions and route event JSONL; capture unchanged X11 window ID across turns. | A reopens route A, observes it, and submits again. |
| S-N1 | Selection / Active Object | Bold only the `ALPHA` range. | Bold only the `BETA` range. | Same Writer document/window; B changes the active text range before A applies formatting. | Saved ODF bold spans, exact document text/guard, read-only UNO range snapshot and active X11 window ID. | A reselects `ALPHA`; B reapplies its range if needed. |
| U-N1 | Undo / Redo History | Make a temporary first-line edit, then Undo to restore `A-LINE: keep`. | Set the second line to `B-LINE: final`. | Same Writer document/window/history; A's Undo follows B's normal edit. | Exact saved ODF paragraphs and before/after operation-state snapshots; window IDs must remain the same. | Restore A's seed line and reapply B's independent line. |

MA-ID creates independent Guest desktops from the same fixture and runs the same A→B→A turn order. MA-SD binds both actors to one Guest. Evaluators read hidden state in the runner and do not expose it through `ActorContext`.

## Validation results

| Workflow | Solo A | Solo B | MA-ID | MA-SD naive exposure | MA-SD recovery | Offline oracle controls | Status |
|---|---|---|---|---|---|---|---|
| F-N1 | **PASS, one real Guest** | **PASS, one real Guest** | Not run | Not run | Not run | PASS | **KEEP provisionally; incomplete gate** |
| C-N1 | Not run | Not run | Not run | Not run | Not run | PASS | **DEFER** pending real rich-MIME round trip |
| A-N1 | Not run | Not run | Not run | Not run | Not run | PASS | **DEFER** pending same-tab route Guest proof |
| S-N1 | Not run | Not run | Not run | Not run | Not run | PASS | **DEFER** pending UNO/range Guest proof |
| U-N1 | Not run | Not run | Not run | Not run | Not run | PASS | **DEFER** pending Writer undo-grouping proof |

Offline command on A6000:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
"$CODESK_PYTHON" -m pytest -q tests/test_matrix_workflows_v1.py
"$CODESK_PYTHON" -m py_compile scripts/run_matrix_workflow_v1.py swcub/tasks/matrix_workflows_v1.py
```

Result: **7 passed**; both new Python modules compile. Tests include exact positive states, wrong-document contamination, flattened-table rejection, route mismatch, wrong-span formatting, and lost Undo peer edit.

### F-N1 Solo A real-Guest evidence

- Run IDs: `matrix-v1-FN1-solo-a-20261003T052000Z` and `matrix-v1-FN1-solo-b-20261003T054000Z`
- Condition: `solo_a`; actor implementation: scripted GUI, no model.
- Guest host: A6000 canonical node; Guest: OSWorld V2.1 QEMU desktop.
- Result: actor A goal PASS; non-target integrity PASS; joint PASS; evaluator completed; fresh-Guest reset PASS.
- Readiness observed a visible 1920×1080 desktop and accessibility tree (153,345 chars) after two transient blank-frame retries. Writer opened with the expected document title, accepted GUI input, and saved the expected value. The GUI screenshot is retained at:
  `artifacts/matrix-workflows-v1/matrix-v1-FN1-solo-a-20261003T052000Z/guest-artifacts/osworld-763b948309e0/guest-screen.png`.
- Ownership ledger: 2 Guest containers created and both destroyed with matching project/run/owner labels; `all_containers_have_destroy_record=true`, `labels_consistent=true`.
- Full report, event trace, provenance, reset report, readiness screenshots and overlay are retained beneath:
  `artifacts/matrix-workflows-v1/matrix-v1-FN1-solo-a-20261003T052000Z/`.
- Solo B independently opened `doc-b.fodt`, saved `B-FINAL-204`, passed its path-bound evaluator, and passed fresh-Guest reset with a consistent ownership ledger. Its artifacts are under `artifacts/matrix-workflows-v1/matrix-v1-FN1-solo-b-20261003T054000Z/`. The two Solo passes do not prove MA-ID, MA-SD exposure or recovery.

## Qwen smoke

No Qwen Solo smoke was run. The known 4090 SSH endpoint timed out at `0.0.15.250:22` during the preflight. A6000 inference remains frozen by instruction, and GPUs 1 and 2 had substantial existing VRAM allocations; no GPU was used. This is an unavailable inference host, **not** a Qwen task failure.

## Why additional Guest runs paused

Immediately before the Guest smokes, Docker showed no active containers, memory available was about 206 GiB, and CPU PSI `some avg10` was 8.38%. During/after the two sequential single-worker smokes, CPU pressure rose: host load reached `203.84` on 144 logical CPUs and CPU PSI `some avg10` reached `41.62%`; after the second run it was still `36.46%` with load `176.11`. The run's Guest used up to 4 vCPU and was closed/reset through its ownership ledger. No other process or resource was inspected or touched. More Guest runs were paused to avoid adding sustained CPU pressure to a busy multi-user host.

## Family mapping and workflow count

A-02 is mapped to **Selection / Active Object** in current taxonomy. Its historical ID, code, runs and evidence remain intact; no old artifact was edited. The current mapping counts 15 workflow IDs across the five frozen families: Focus 4, Clipboard 4, Application Context 2, Selection 3, Undo/Redo 2. Only the previous ten anchors retain their earlier validation status; this count must not be described as 15 validated workflows.

| Workflow | Decision this round | Reason |
|---|---|---|
| F-N1 | KEEP provisionally | Distinct Writer document identities; Solo A and Solo B each passed save/evaluator/fresh-Guest reset once. MA-ID / MA-SD / recovery remain outstanding. |
| C-N1 | DEFER | Design/oracle preserve actual table structure, but whether Chromium selection yields stable rich MIME and Writer retains it is untested. |
| A-N1 | DEFER | Deterministic SPA contract and route-keyed oracle exist; route/window evidence awaits Guest execution. |
| S-N1 | DEFER | Separate text-range mechanism is specified; UNO selection and formatting must be proven in real Writer. |
| U-N1 | DEFER | History mechanism is distinct in contract; Writer Undo grouping and causal peer-edit reversion need Guest evidence. |

None is rejected on evidence in this round. None is fully validated either. Thus **do not** begin instance-schema design yet.

## Next actions

1. When A6000 CPU PSI/load returns to the pre-run safe band, run F-N1 MA-ID, MA-SD, then recovery; preserve each attempt.
2. Run C-N1 Solo A/B first. Inspect saved clipboard target MIME and ODF table structure before starting MA-ID/MA-SD. Reject if the paste becomes only plain text.
3. For A-N1, verify same Chromium XID/tab while the route event changes A→B; then test Solo A/B before shared turns.
4. For S-N1, calibrate the UNO observer and exact ranges in Solo A/B; require same XID and unchanged document text before shared turns.
5. For U-N1, first verify Writer's saved undo grouping in Solo A and the independent B edit in Solo B; only then run shared history and explicit recovery.
6. Qwen feasibility remains blocked until the previously approved 4090 endpoint becomes reachable. Use only that existing 2×4090 BF16 path; do not switch inference to A6000.
7. After each workflow meets Solo A/B, MA-ID, MA-SD exposure, recovery, evaluator, reset and provenance gates, decide KEEP/REJECT. Begin instance-schema design only after the 15-workflow claim is supported or the suite is explicitly revised to a smaller validated count.

## Resource gate recheck — 2026-10-03 13:51 +08:00

No scripted Guest run was started in this recheck. Read-only host state: 144 logical CPUs; load average 154.42 / 151.17 / 151.69; CPU PSI some avg10 32.38%, avg60 24.54%, avg300 23.73%; vmstat showed runnable queue 232 and about 90% user CPU during the sample. RAM available was about 205 GiB. Swap use was 6.5/8 GiB; swap in/out was transient (first sample 1/10 KiB/s, then 0/0).

No CoDesk-labeled Docker Guest and no QEMU Guest process were active. Process-level load summary showed four jiaodian Python processes at approximately 2180–2650% CPU and one daiyang Python process at approximately 465% CPU. No command-line arguments, working directories, or private project files were inspected.

Decision: **BLOCKED_RESOURCE**. Do not start MA-ID or MA-SD under this pressure. No Qwen request was attempted. Existing valid evidence remains F-N1 Solo A and Solo B (one each); all other new workflow Guest gates remain outstanding. The formal validated-workflow count remains the historical 10; the 15-workflow mapping is not ready. Recheck after load falls below 144 and CPU PSI some avg10 returns near the prior pre-run band, with no unowned Guest/QEMU activity.
