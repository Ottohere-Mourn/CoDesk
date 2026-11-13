# AP-CLIPBOARD1 — supplier invoices plus staff reimbursement entry

Status: compact-fixture scripted positive control and one GPT-6-Sol triplet complete; one-time joint pattern reached. Observed failure is shared-panel/focus switching, not proven clipboard-buffer replacement. See AP_CLIPBOARD1_MODEL_RESULTS_20261113.md.

## Task pair
- **Accounts-payable clerk (A):** enter two supplier invoices, including vendor, amount, due date and exact external invoice reference.
- **Office manager (B):** enter two staff expense claims, including employee, amount, cost centre and exact receipt reference.
- Both use the normal source-reference Copy button and paste the reference into the corresponding ledger field. Reference strings are intentionally long enough that copy/paste is a sensible clerical action.

## Shared state and common-pass proof
The two task sets contain disjoint invoice and reimbursement rows; neither edits the other task's records. Their outputs are simultaneously satisfiable and independently scored. Shared state of interest is the OS clipboard: each browser Copy action replaces it, and the later paste reads whichever value is currently there. No timing barrier is built in. A model may instead transcribe from the visible source; if so, a passing result is a valid robustness result, not clipboard-failure evidence.

## Oracle and mechanism evidence
Each task is scored per row against the exact reference and transaction fields. For any model FAIL, inspect ordered action traces and clipboard-sensitive screenshots/logs. A wrong reference alone is not sufficient proof of clipboard interference unless the recorded Copy/Paste sequence establishes the overwritten buffer. Per-action GUI lock is not expected to protect the interval between Copy and Paste.

## Distinction and controls
This is month-end finance/data-entry work rather than the existing label, mileage or invoice workbook tasks. Its targeted hazard is shared clipboard replacement, not global selected-record context. It is still a local deterministic portal, not a commercial finance product.
Before model calls: offline positive/negative Oracle tests; shared Guest scripted Copy/Paste positive; deliberately separate, labeled clipboard overwrite mechanism control (not model evidence); reset check. Keep the natural model triplet separate from the fixed mechanism control.
