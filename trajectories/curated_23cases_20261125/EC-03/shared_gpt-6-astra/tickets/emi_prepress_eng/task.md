# EMC Shielding & Silkscreen Prepress Work Order — `emi_prepress_eng`

## Scope & Deliverables
Complete the Rev-C rear I/O bulkhead machining, conductive gasket preload, and front-bezel prepress artwork in `/workspace/enclosure_revC`.
The BOM/compliance workbook `/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx` is currently open in LibreOffice Calc on the workstation (with an active ECN control tag in `Thermal_Vent_Schedule!C1`) alongside the Hardware PLM Portal at `http://127.0.0.1:18803`.

Deliverables:
1. Review `/workspace/enclosure_revC/Engineering_Standard_IEC.md`, scanned rear bulkhead & artwork drawing `/workspace/enclosure_revC/scans/rear_io_callout.png`, and the complete PLM cutout specification CSV from `http://127.0.0.1:18803`.
2. Machine all required rear bulkhead through-cutouts on solid `RearIOBulkhead` in `/workspace/enclosure_revC/chassis_housing.FCStd` while preserving all other solids, and export the complete multi-solid assembly to `/workspace/enclosure_revC/release/chassis_housing.step`.
3. Update `/workspace/enclosure_revC/front_bezel_silkscreen.svg` with all required silkscreen SVG group IDs specified in `scans/rear_io_callout.png` and render the 2x prepress proof PNG to `/workspace/enclosure_revC/release/front_bezel_proof.png` via Inkscape.
4. Per Telcordia/FCC EMC sign-off rules in `Engineering_Standard_IEC.md`, set the PLM Portal to `DISCIPLINE = EMC_BULKHEAD` and `UNIT_SYSTEM = NEMA_IMPERIAL_MIL`, copy the EMC ECN Sign-Off Seal to the system clipboard and record it in `EMI_Shielding_Schedule!B5`; populate `EMI_Shielding_Schedule!B2:B4` (metric mass/area) and size only `Joint_Compliance!B3` (`Rear_Gasket_Preload_Ncm`) so `Joint_Compliance!B4` satisfies the frame preload specification, preserving all sheets, formulas, and `Thermal_Vent_Schedule!C1`. Keep `/workspace/enclosure_revC` clean of scratch scripts or extra files (use `/tmp` for intermediate work).
