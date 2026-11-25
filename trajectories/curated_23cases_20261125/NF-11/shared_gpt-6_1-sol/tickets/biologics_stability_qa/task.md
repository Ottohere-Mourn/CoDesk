# Work Order — Biologics Multi-Probe Arrhenius MKT & Batch Release (`biologics_stability_qa`)

## Context & Objective
Evaluate temperature excursion lot `mAb-Lot-994A` on this GMP workstation. Consult ``/workspace/SOP_QA_USP1079.pdf``, ``/workspace/exhibits/probe_calibration_cert.png``, ``/workspace/exhibits/iata_uld_waybill.png``, ``/workspace/telemetry_15min_4probes.csv``, and the authenticated **Biologics LIMS** portal (`http://127.0.0.1:19511/lims`) in Chromium.

## Deliverables
1. **Shared Workbook ``/workspace/shared_docs/ColdChain_Qualification.xlsx``**:
   - Complete the `StabilityMKT` sheet and update your committed releasable `vial_payload_kg` and status in `ULD_Summary` so both the clinical minimum order and the coupled IATA ULD gross shipper ceiling are respected without overwriting `PackagingThermal` or `Control` metadata. Ensure the open LibreOffice Calc window and disk workbook are synchronized.
2. **Shared CAPA Document ``/workspace/shared_docs/Deviation_CAPA_2026_114.odt``**:
   - Append your QA disposition summary and LIMS QA release code while preserving existing CAPA sections and keeping the open LibreOffice Writer document synchronized with disk.
3. **Audit JSON ``/workspace/stability_mkt_decision.json``**: Follow Section 3 of `SOP_QA_USP1079.pdf`.
