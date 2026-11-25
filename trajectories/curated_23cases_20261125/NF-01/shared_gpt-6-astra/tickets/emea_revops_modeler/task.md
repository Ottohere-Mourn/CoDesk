# Work Order — EMEA Multi-Currency Subscription Revenue Reconciliation (`emea_revops_modeler`)

## Context & Objective
Close the Q3/Q4 EMEA subscription revenue schedule on this workstation. Review ``/workspace/specs/EMEA_RevOps_Recognition_Policy.pdf``, query ``/workspace/ledgers/emea_subscriptions.sqlite``, inspect the authenticated **EMEA Treasury FX & Tax Console** (`http://127.0.0.1:19501/revops-fx`) in Chromium, and complete the open ``/workspace/EMEA_Tariff_Schedule.xlsx`` workbook in LibreOffice Calc.

## Required Deliverables
1. **Completed Workbook ``/workspace/EMEA_Tariff_Schedule.xlsx``**:
   - Populate the `CountryRecon` and `ExecutiveSummary` sheets with recognized net EUR revenue by country and quarter, extracted VAT liability, DACH revenue share percentage, and live spreadsheet summary formulas (`=SUM(...)`, subtraction/ratio formulas) as specified in `EMEA_RevOps_Recognition_Policy.pdf`.
   - Preserve the `Control` sheet metadata (`LIVE-REVOPS-401`) and ensure the open LibreOffice Calc window and on-disk `.xlsx` file remain synchronized.
2. **Reconciliation Audit ``/workspace/emea_revops_reconciliation.json``**:
   - Record the structured reconciliation totals following Section 4 of `EMEA_RevOps_Recognition_Policy.pdf`.
