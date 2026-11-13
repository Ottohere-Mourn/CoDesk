# WAREHOUSE-LABEL1 — mixed bin and parcel label batches

Status: implemented locally, offline controls added; Guest positive/negative controls and GPT-6-Sol arms not yet run.

## Workflow
A shared warehouse print station has one current thermal stock profile. An inventory clerk prints five 2x1 bin-location batches (B-104, B-118, B-203, B-417, B-512). A dispatch coordinator prints five 4x6 parcel batches (P-6201, P-6207, P-6214, P-6228, P-6233). Each item has a specified copy count. The workflow is plausible for a small warehouse switching stock on a shared thermal printer.

## Shared state and expected contention
The browser-based Riverside Logistics Label Desk records the current station-wide media profile. Every print submission snapshots that profile at submit time. Bin and parcel queues are independent; each task has a common final state with the other task (all ten correct output jobs). A wrong profile can be corrected by reprinting, and the oracle accepts any matching correct job; no zero-sum rule or finite quota. MA-ID starts from identical station profiles and independent copies of the same fixture. Shared+Lock is per GUI action only, so a profile change between two print calls can still make the next job use the wrong stock.

## Evidence gate
The offline oracle positive control establishes both tasks can pass jointly. The negative control changes the global profile after an actor selects its stock and before it submits a label; the saved job captures the new profile and fails only that target item. Before a model triplet, run one scripted Guest positive control and confirm one shared Chrome session, profile display, copy entry, saved print jobs, reset, and evaluator isolation. No arm-specific schedule/barrier. If the real model changes or verifies stock before every job and all arms pass, report no-go; do not tune a forced race.

## Novelty and risk
Unlike VIDEO-REVIEW1's shared media time cursor, this uses a global hardware-style output format captured at submission. It is not an OSWorld physical printer test: the Guest uses a local browser print-station simulation so printer-driver availability cannot invalidate the case. It shares the broad printing domain with the rejected PRINT-ROUTE1 candidate, but not its OS printer queue/destination failure; this is a targeted station-profile workflow and must remain a workflow-level addition, not a claim of a wholly new mechanism. Main risk is that a model may notice and recover by reselecting the profile; that is desired evidence, not a reason to remove the check.
