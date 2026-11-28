You are completing a Q4 finance audit in a local enterprise portal.

The Chromium window is open at http://127.0.0.1:8090/. Sign in with the demo account fin_auditor and password FinA-5107-demo. In Finance > Invoices, verify the vendor, purchase-order ID, and amount for each invoice below against the values shown here, then approve each matching invoice:

- INV-5107 — Northstar Components — PO-7104 — USD 1280.50
- INV-5112 — Meridian Office — PO-7118 — USD 642.00
- INV-5121 — Pine Ridge Logistics — PO-7131 — USD 2395.75

Export the Finance Ledger as a CSV. Save a readable final copy at ~/workspace/fin_audit_q4.csv. The file must contain exactly these three invoice records with the columns invoice_id, vendor, invoice_date, po_id, amount_usd, approval_status. Preserve the displayed invoice dates and amounts, and verify all three rows show APPROVED in the portal and in the saved CSV. The portal's downloaded file is named ~/Downloads/export_report.csv; your required deliverable is the copy at the workspace path above.

If the portal presents a sign-in page again, sign in with the same account and continue from the invoice list. Do not change unrelated invoices or vendor records.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify that your final CSV opens and has the required columns and rows before finishing.
