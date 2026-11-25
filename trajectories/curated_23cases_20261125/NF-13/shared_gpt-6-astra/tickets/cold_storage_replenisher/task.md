# Work Order — Frozen Safety-Stock Imputation & Cold-Room Bay Replenishment (`cold_storage_replenisher`)

## Context & Objective
Size 98%-service-level `(s, S)` frozen pallet bays using the live **NotebookHub** Python kernel (`http://127.0.0.1:19513/notebook` in Chromium), consult ``/workspace/specs/SOP_Ops_Replenishment.pdf`` and ``/workspace/specs/ammonia_tariff_scan.png``, commit your frozen bay allocation in ``/workspace/shared_docs/cold_chain_plan.json`` and the open ``/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx`` Calc workbook within the facility ammonia-rack cap, and write ``/workspace/replenishment_audit.json``.

## Deliverables
1. **Shared Plan ``/workspace/shared_docs/cold_chain_plan.json`` & Calc Workbook ``/workspace/shared_docs/Ammonia_Rack_Schedule.xlsx``**: Commit `frozen_bays` (`frozen_status = 'COMMITTED'`, `BaySchedule!B3` & `C3='COMMITTED'`) while preserving chilled fields and keeping the open LibreOffice Calc window synchronized with disk.
2. **Audit JSON ``/workspace/replenishment_audit.json``**: Follow Section 3 of ``SOP_Ops_Replenishment.pdf``.
