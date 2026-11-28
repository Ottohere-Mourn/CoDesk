You are completing a Q4 supplier-compliance update in a local enterprise portal.

The Chromium window is open at http://127.0.0.1:8090/. Sign in with the demo account ops_buyer and password OpsB-204-demo. In Procurement > Vendors, review the certificate details and update the compliance status for these three suppliers to COMPLIANT:

- V-204 — Northstar Components — ISO-9001-204 — expires 2027-08-31
- V-219 — Meridian Office — SOC2-219 — expires 2027-03-31
- V-233 — Pine Ridge Logistics — C-TPAT-233 — expires 2027-01-31

Export the Supplier Compliance List as a CSV. Save a readable final copy at ~/workspace/vendor_status.csv. The file must contain exactly these three supplier records with the columns vendor_id, vendor_name, certificate_id, certificate_expiry, compliance_status. Preserve the displayed certificate details and verify all three rows show COMPLIANT in the portal and in the saved CSV. The portal's downloaded file is named ~/Downloads/export_report.csv; your required deliverable is the copy at the workspace path above.

If the portal presents a sign-in page again, sign in with the same account and continue from the vendor list. Do not change unrelated vendor records or invoices.

You may choose the desktop GUI, guest_cli, or a combination. guest_cli can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to guest_cli; do not access or alter them. Verify that your final CSV opens and has the required columns and rows before finishing.
