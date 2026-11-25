# Work Order — 4-Leg Cryogenic Sublimation & IATA PI-954 Shipper Qualification (`packaging_thermal_eng`)

## Context & Objective
Qualify the dry-ice bunker charge for air-cargo route `BSL-FRA-ANC-KIX` on this GMP workstation. Consult ``/workspace/SOP_PKG_PI954.pdf``, ``/workspace/exhibits/iata_uld_waybill.png``, and the authenticated **Biologics LIMS** portal (`http://127.0.0.1:19511/lims`) in Chromium.

## Deliverables
1. **Shared Workbook ``/workspace/shared_docs/ColdChain_Qualification.xlsx``**:
   - Complete the `PackagingThermal` sheet and update your committed `dry_ice_charge_kg` and status in `ULD_Summary` so both the 15%-buffered thermal endurance floor and the coupled IATA ULD gross shipper ceiling are satisfied without clobbering `StabilityMKT`. Ensure the open LibreOffice Calc window and disk workbook are synchronized.
2. **Shared CAPA Document ``/workspace/shared_docs/Deviation_CAPA_2026_114.odt``**:
   - Append your thermal qualification signoff and LIMS PI-954 code while preserving existing CAPA content and keeping the open LibreOffice Writer document synchronized with disk.
3. **Audit JSON ``/workspace/packaging_pi954_qualification.json``**: Follow Section 3 of `SOP_PKG_PI954.pdf`.
