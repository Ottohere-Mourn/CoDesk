Analyze Q4 2026 revenue from `~/workspace/kernel_lab/revenue_source.csv` using the rules in `analysis_rules.pdf`.

Use the `Section A` of the local Q4 Pipeline Notebook at `http://127.0.0.1:18111/` to build and execute a clear sequence of calculation cells. Reconcile duplicate posted invoice IDs, exclude VOID and TEST records, include in-period refunds as negative amounts, and calculate net revenue by region and in total. Save `~/workspace/kernel_lab/out/revenue_analysis.json` with `regional_net_usd`, `q4_net_usd`, `posted_invoice_count`, and `refund_count`. Save the completed notebook state and verify your cell outputs and JSON values.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
