# Vendor SLA Addendum Curation & Facility Grant Envelope Work Order — `contract_automation_eng`

## Scope & Deliverables
Reconcile the 10 vendor SLA addenda (`VND-01` .. `VND-10`) across `/workspace/maildesk/maildesk.sqlite` and the live **Procurement Clause Portal** at `http://127.0.0.1:19406/` in Chromium (`127.0.0.1:9222`), and finalize `/workspace/contracts/Contract_Schedule.xlsx` (currently open in LibreOffice Calc with an active desk tag in `Vendor_SLAs!C1`).

Deliverables:
1. **SQLite Vendor Curation (`/workspace/maildesk/maildesk.sqlite`)**:
   - Update `vendor_addenda.curation_status` to `INCLUDED_ACTIVE` for `ACTIVE_APPROVED` vendors and `EXCLUDED_SUSPENDED` for `SUSPENDED_DEBARRED` vendors.
2. **Spreadsheet SLA Table & Grant Sizing (`/workspace/contracts/Contract_Schedule.xlsx`)**:
   - Populate `Vendor_SLAs` rows `2..9` with the 8 active vendors (`Vnd_ID` in `A`, `Vendor_Name` in `B`, `Base_Fee_USD` in `C`, `Rush_Pct` in `D`, and formula `=ROUND(C2*(1+D2/100),2)` .. in `E`), preserving the live desk tag in `Vendor_SLAs!C1`.
   - In `Budget_Envelope`, keep `B7` as `=SUM(Vendor_SLAs!E2:E9)`, size `AV_Contingency_Reserve_USD` (`B8` in `[2100, 3000]`) so `Grant_Utilization_Ratio` (`B11`, formula `=B9/B10` with `B9` `=B5+B7+B8`) lands in `[0.840, 0.885]`, and set `Budget_Envelope!B12` to `procurement_sla_seal` (preserving `Budget_Envelope!B2:B6` and keeping the open Calc window in sync).
3. **PDF & Contract Manifest (`/workspace/contracts/SLA_Summary.pdf` & `/workspace/contracts/CONTRACT_MANIFEST.json`)**:
   - Export `SLA_Summary.pdf` from `Contract_Schedule.xlsx` and write `CONTRACT_MANIFEST.json` with keys `active_vendor_ids` (sorted list of 8 IDs), `suspended_vendor_ids` (sorted list of 2 IDs), `total_active_sla_usd` (float), `av_contingency_reserve_usd` (float), and `procurement_sla_seal`.
