# Work Order — Perishable Promotional Price Elasticity & Chilled Bay Allocation (`demand_elasticity_ds`)

## Context & Objective
Estimate promotional price elasticities across the perishable catalog using the live **NotebookHub** Python kernel (`http://127.0.0.1:19513/notebook` in Chromium), consult ``/workspace/specs/SOP_DS_Elasticity.pdf`` and ``/workspace/specs/ammonia_tariff_scan.png``, commit your chilled bay allocation in ``/workspace/shared_docs/cold_chain_plan.json`` and the open ``/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx`` Calc workbook within the facility ammonia-rack cap, and write ``/workspace/elasticity_audit.json``.

## Deliverables
1. **Shared Plan ``/workspace/shared_docs/cold_chain_plan.json`` & Calc Workbook ``/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx``**: Commit `chilled_bays` (`chilled_status = 'COMMITTED'`, `BaySchedule!B2` & `C2='COMMITTED'`) while preserving frozen fields and keeping the open LibreOffice Calc window synchronized with disk.
2. **Audit JSON ``/workspace/elasticity_audit.json``**: Follow Section 3 of ``SOP_DS_Elasticity.pdf``.
