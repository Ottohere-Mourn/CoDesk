Reconcile the warehouse inventory ledger in `~/workspace/erp_reconcile/erp_ledger.db`.

Use `reconciliation_rules.pdf` and the source tables. For each of SKU-A, SKU-B, and SKU-C, calculate counted quantity minus book quantity, set the row to RECONCILED, and insert exactly one uniquely identified stock adjustment with a concise source note. Do not alter invoice or payment rows. Export the three inventory reconciliations to `~/workspace/erp_reconcile/out/inventory_reconciliation.csv`. Verify the result in the local audit page at `http://127.0.0.1:18117/audit/inventory`.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
