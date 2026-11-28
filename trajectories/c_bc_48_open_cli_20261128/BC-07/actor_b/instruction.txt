Process Q4 outbound shipment release in the North Depot Dispatch Console at `http://127.0.0.1:8092/`, open in Google Chrome.

Read `~/workspace/dispatch/warehouse_rules.pdf` and filter `outbound_orders.csv` to determine the six eligible orders, excluding credit-held or failed-QA records. In the Outbound view, stage only those orders and run Phase 1 Compliance Check. Review any customs mismatches, look up the approved override codes in `customs_overrides.csv`, apply the correct codes, and complete Phase 2 Final Release with the returned release token.

Verify in the console that the six selected orders are RELEASED with required override codes. Save `~/workspace/dispatch/outbound_audit.json` with order IDs, override codes, release token, and final status. Do not change unrelated orders.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them. Verify the console state and audit JSON before finishing.
