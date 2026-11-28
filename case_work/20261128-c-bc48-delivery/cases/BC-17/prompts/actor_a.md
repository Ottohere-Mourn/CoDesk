Reconcile the accounts-receivable ledger in `~/workspace/erp_reconcile/erp_ledger.db`.

Use `reconciliation_rules.pdf` and the source tables. Count only POSTED payments. For each of AR-501, AR-502, and AR-503, compare the posted-payment sum with the invoice face amount and set the correct invoice status without altering payment rows. Export those three reconciled invoices with the payment totals to `~/workspace/erp_reconcile/out/ar_reconciliation.csv`. Verify the result in the local audit page at `http://127.0.0.1:18117/audit/ar`.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
