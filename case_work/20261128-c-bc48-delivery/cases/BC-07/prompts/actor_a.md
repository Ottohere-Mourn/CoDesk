Process Q4 inbound stock allocation in the North Depot Dispatch Console at `http://127.0.0.1:8092/`, open in Google Chrome.

Read `~/workspace/dispatch/warehouse_rules.pdf` and filter `inbound_manifest.csv` to determine the six compliant inbound orders and their primary bin assignments. In the Inbound view, stage only those orders and run Phase 1 Pre-Check. Review the service's capacity findings, route any affected cold-chain orders to the overflow bin required by the rules, and complete Phase 2 Final Commit with the returned allocation token.

Verify in the console that the six selected orders are RECEIVED in their final bins. Save `~/workspace/dispatch/inbound_audit.json` with the order IDs, final bins, reassignment flags, allocation token, and final status. Do not change unrelated orders.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them. Verify the console state and audit JSON before finishing.
